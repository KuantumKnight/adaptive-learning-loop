import { useCallback, useEffect, useRef, useState } from "react";

type LandmarkPoint = { x: number; y: number };
type FaceLandmarks = (LandmarkPoint | null)[][];
type LandmarkConnection = { start: number; end: number };

export type CameraSignal = {
  enabled: boolean;
  face_present: boolean | null;
  looking_away: boolean | null;
  blink_count: number | null;
  gaze_direction: "LEFT" | "CENTER" | "RIGHT" | null;
  head_yaw_degrees: number | null;
  head_pitch_degrees: number | null;
  head_roll_degrees: number | null;
  ambiguous: boolean | null;
  sustained_seconds: number;
  status: string;
};

// Assets are pinned and served by the Vite app after `npm run fetch:vision`.
// A missing asset is reported as unavailable; it is never converted to a
// positive face measurement.
const WASM_URL = `${window.location.origin}/models/wasm`;
const MODEL_URL = `${window.location.origin}/models/face_landmarker.task`;

export function useCamera() {
  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const workerRef = useRef<Worker | null>(null);
  const workerReadyRef = useRef(false);
  const frameInFlightRef = useRef(false);
  const missingSinceRef = useRef<number | null>(null);
  const blinkCountRef = useRef(0);
  const landmarksRef = useRef<FaceLandmarks>([]);
  const connectionsRef = useRef<LandmarkConnection[]>([]);
  const showLandmarksRef = useRef(true);
  const [showLandmarks, setShowLandmarks] = useState(true);
  const [signal, setSignal] = useState<CameraSignal>({
    enabled: false,
    face_present: null,
    looking_away: null,
    blink_count: null,
    gaze_direction: null,
    head_yaw_degrees: null,
    head_pitch_degrees: null,
    head_roll_degrees: null,
    ambiguous: null,
    sustained_seconds: 0,
    status: "Camera off",
  });
  const [busy, setBusy] = useState(false);

  const drawLandmarks = useCallback(() => {
    const canvas = canvasRef.current;
    const video = videoRef.current;
    const context = canvas?.getContext("2d");
    if (!canvas || !context) return;

    const bounds = canvas.getBoundingClientRect();
    const pixelRatio = window.devicePixelRatio || 1;
    const pixelWidth = Math.round(bounds.width * pixelRatio);
    const pixelHeight = Math.round(bounds.height * pixelRatio);
    if (canvas.width !== pixelWidth || canvas.height !== pixelHeight) {
      canvas.width = pixelWidth;
      canvas.height = pixelHeight;
    }
    context.setTransform(pixelRatio, 0, 0, pixelRatio, 0, 0);
    context.clearRect(0, 0, bounds.width, bounds.height);

    if (
      !showLandmarksRef.current ||
      !video ||
      video.videoWidth === 0 ||
      video.videoHeight === 0
    )
      return;

    // Match the video's centered object-fit: cover crop, including when a
    // camera returns a different aspect ratio from the preview container.
    const scale = Math.max(
      bounds.width / video.videoWidth,
      bounds.height / video.videoHeight,
    );
    const offsetX = (bounds.width - video.videoWidth * scale) / 2;
    const offsetY = (bounds.height - video.videoHeight * scale) / 2;
    const pointAt = (point: LandmarkPoint) => ({
      x: offsetX + point.x * video.videoWidth * scale,
      y: offsetY + point.y * video.videoHeight * scale,
    });

    context.lineWidth = 1.15;
    context.strokeStyle = "rgba(79, 255, 190, 0.95)";
    context.fillStyle = "rgba(255, 220, 80, 1)";
    context.shadowColor = "rgba(0, 0, 0, 0.9)";
    context.shadowBlur = 2;
    for (const face of landmarksRef.current) {
      context.beginPath();
      for (const { start, end } of connectionsRef.current) {
        const from = face[start];
        const to = face[end];
        if (!from || !to) continue;
        const a = pointAt(from);
        const b = pointAt(to);
        context.moveTo(a.x, a.y);
        context.lineTo(b.x, b.y);
      }
      context.stroke();

      for (const point of face) {
        if (!point) continue;
        const { x, y } = pointAt(point);
        context.beginPath();
        context.arc(x, y, 1.8, 0, Math.PI * 2);
        context.fill();
      }
    }
    context.shadowBlur = 0;
  }, []);

  const clearLandmarks = useCallback(() => {
    landmarksRef.current = [];
    drawLandmarks();
  }, [drawLandmarks]);

  const toggleLandmarks = useCallback(() => {
    showLandmarksRef.current = !showLandmarksRef.current;
    setShowLandmarks(showLandmarksRef.current);
    drawLandmarks();
  }, [drawLandmarks]);

  useEffect(() => {
    drawLandmarks();
  }, [drawLandmarks]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || typeof ResizeObserver === "undefined") return;
    const observer = new ResizeObserver(drawLandmarks);
    observer.observe(canvas);
    return () => observer.disconnect();
  }, [drawLandmarks]);

  const stop = useCallback(() => {
    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;
    workerRef.current?.terminate();
    workerRef.current = null;
    workerReadyRef.current = false;
    frameInFlightRef.current = false;
    missingSinceRef.current = null;
    landmarksRef.current = [];
    drawLandmarks();
    if (videoRef.current) videoRef.current.srcObject = null;
    setSignal((prev) => ({
      ...prev,
      enabled: false,
      face_present: null,
      looking_away: null,
      blink_count: blinkCountRef.current,
      gaze_direction: null,
      head_yaw_degrees: null,
      head_pitch_degrees: null,
      head_roll_degrees: null,
      ambiguous: null,
      sustained_seconds: 0,
      status: "Camera off",
    }));
  }, [drawLandmarks]);

  const start = useCallback(async () => {
    setBusy(true);
    workerReadyRef.current = false;
    frameInFlightRef.current = false;
    landmarksRef.current = [];
    showLandmarksRef.current = true;
    setShowLandmarks(true);
    drawLandmarks();
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { width: 640, height: 480, facingMode: "user" },
        audio: false,
      });
      streamRef.current = stream;
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        await videoRef.current.play();
      }
      const worker = new Worker(new URL("./faceWorker.ts", import.meta.url), {
        type: "module",
      });
      workerRef.current = worker;
      worker.onmessage = (event) => {
        const message = event.data;
        if (message.type === "ready") {
          workerReadyRef.current = true;
          connectionsRef.current = Array.isArray(message.connections)
            ? message.connections
            : [];
          drawLandmarks();
          setSignal((prev) => ({
            ...prev,
            blink_count: blinkCountRef.current,
            status: `Camera active · ${message.delegate || "GPU"} model ready; looking for a face…`,
          }));
        }
        if (message.type === "error") {
          if (message.phase === "model") workerReadyRef.current = false;
          frameInFlightRef.current = false;
          clearLandmarks();
          setSignal((prev) => ({
            ...prev,
            face_present: null,
            looking_away: null,
            blink_count: blinkCountRef.current,
            gaze_direction: null,
            head_yaw_degrees: null,
            head_pitch_degrees: null,
            head_roll_degrees: null,
            ambiguous: null,
            sustained_seconds: 0,
            status:
              message.phase === "model"
                ? "Camera active · model unavailable; interaction signals still work"
                : "Camera active · frame signal unavailable",
          }));
        }
        if (message.type === "summary") {
          frameInFlightRef.current = false;
          if (message.blinkEvent === true) blinkCountRef.current += 1;
          landmarksRef.current = Array.isArray(message.landmarks)
            ? message.landmarks
                .filter(Array.isArray)
                .map((face: LandmarkPoint[]) =>
                  face.map((point) =>
                    Number.isFinite(point?.x) && Number.isFinite(point?.y)
                      ? point
                      : null,
                  ),
                )
            : [];
          drawLandmarks();
          const ambiguous = Boolean(message.ambiguous);
          const present = !ambiguous && Boolean(message.present);
          if (!present && !missingSinceRef.current)
            missingSinceRef.current = Date.now();
          if (present) missingSinceRef.current = null;
          const sustained = missingSinceRef.current
            ? Math.floor((Date.now() - missingSinceRef.current) / 1000)
            : 0;
          setSignal((prev) => ({
            ...prev,
            face_present: ambiguous ? null : present,
            looking_away: ambiguous ? null : (message.lookingAway ?? null),
            blink_count: blinkCountRef.current,
            gaze_direction: ambiguous
              ? null
              : (message.gazeDirection ?? null),
            head_yaw_degrees: ambiguous
              ? null
              : (message.headYawDegrees ?? null),
            head_pitch_degrees: ambiguous
              ? null
              : (message.headPitchDegrees ?? null),
            head_roll_degrees: ambiguous
              ? null
              : (message.headRollDegrees ?? null),
            ambiguous,
            sustained_seconds: sustained,
            status: message.calibrated
              ? "Calibration complete · neutral pose set"
              : ambiguous
              ? "Camera active · multiple faces detected"
              : present
                ? "Camera active · face landmarks detected locally"
                : "Camera active · no face detected",
          }));
        }
      };
      worker.onerror = () => {
        workerReadyRef.current = false;
        frameInFlightRef.current = false;
        clearLandmarks();
        setSignal((prev) => ({
          ...prev,
          face_present: null,
          looking_away: null,
          blink_count: blinkCountRef.current,
          gaze_direction: null,
          head_yaw_degrees: null,
          head_pitch_degrees: null,
          head_roll_degrees: null,
          ambiguous: null,
          sustained_seconds: 0,
          status:
            "Camera active · model unavailable; interaction signals still work",
        }));
      };
      worker.postMessage({
        type: "init",
        wasmUrl: WASM_URL,
        modelUrl: MODEL_URL,
      });
      setSignal((prev) => ({
        ...prev,
        enabled: true,
        face_present: null,
        blink_count: blinkCountRef.current,
        gaze_direction: null,
        head_yaw_degrees: null,
        head_pitch_degrees: null,
        head_roll_degrees: null,
        status: "Camera active · loading local landmark model…",
      }));
    } catch {
      workerReadyRef.current = false;
      frameInFlightRef.current = false;
      setSignal((prev) => ({
        ...prev,
        enabled: false,
        face_present: null,
        looking_away: null,
        blink_count: blinkCountRef.current,
        gaze_direction: null,
        head_yaw_degrees: null,
        head_pitch_degrees: null,
        head_roll_degrees: null,
        sustained_seconds: 0,
        status: "Camera unavailable · interaction signals still work",
      }));
    } finally {
      setBusy(false);
    }
  }, [clearLandmarks, drawLandmarks]);

  const calibrate = useCallback(() => {
    workerRef.current?.postMessage({ type: "calibrate" });
    setSignal((prev) => ({
      ...prev,
          status: "Calibrating from five valid frames · look at the screen",
    }));
  }, []);

  useEffect(() => () => stop(), [stop]);

  useEffect(() => {
    if (!signal.enabled) return;
    const timer = window.setInterval(async () => {
      const video = videoRef.current;
      const worker = workerRef.current;
      if (
        !video ||
        !worker ||
        !workerReadyRef.current ||
        frameInFlightRef.current ||
        video.readyState < 2
      )
        return;
      frameInFlightRef.current = true;
      try {
        const bitmap = await createImageBitmap(video);
        worker.postMessage(
          { type: "frame", bitmap, timestamp: performance.now() },
          [bitmap],
        );
      } catch {
        frameInFlightRef.current = false;
        clearLandmarks();
        setSignal((prev) => ({
          ...prev,
          face_present: null,
          looking_away: null,
          blink_count: blinkCountRef.current,
          gaze_direction: null,
          head_yaw_degrees: null,
          head_pitch_degrees: null,
          head_roll_degrees: null,
          ambiguous: null,
          sustained_seconds: 0,
          status: "Camera active · frame unavailable",
        }));
      }
    }, 50);
    return () => window.clearInterval(timer);
  }, [signal.enabled, clearLandmarks]);

  return {
    videoRef,
    canvasRef,
    signal,
    start,
    stop,
    calibrate,
    busy,
    showLandmarks,
    toggleLandmarks,
  };
}
