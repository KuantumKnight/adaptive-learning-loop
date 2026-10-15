import { FaceLandmarker, FilesetResolver } from "@mediapipe/tasks-vision";
import {
  averageEyeAspectRatio,
  classifyGaze,
  createBlinkState,
  decomposeHeadPose,
  estimateGazeOffset,
  relativeHeadPose,
  smoothHeadPose,
  updateBlinkState,
  type GazeDirection,
  type HeadPose,
} from "./behaviorMetrics";

let landmarker: FaceLandmarker | null = null;
let neutralGazeOffset: number | null = null;
let neutralHeadPose: HeadPose | null = null;
let smoothedGazeOffset: number | null = null;
let smoothedHeadPose: HeadPose | null = null;
let lastGazeDirection: GazeDirection = "CENTER";
let blinkState = createBlinkState();
let calibrationPending = false;
let calibrationSamples: { gaze: number | null; pose: HeadPose | null }[] = [];

self.onmessage = async (event: MessageEvent) => {
  const message = event.data;
  if (message.type === "init") {
    try {
      // Local WASM is served as ES modules; worker contexts need the module loader.
      const fileset = await FilesetResolver.forVisionTasks(
        message.wasmUrl,
        true,
      );
      const options = (delegate: "GPU" | "CPU") => ({
        baseOptions: { modelAssetPath: message.modelUrl, delegate },
        runningMode: "VIDEO" as const,
        numFaces: 2,
        outputFacialTransformationMatrixes: true,
      });
      let delegate: "GPU" | "CPU" = "GPU";
      try {
        landmarker = await FaceLandmarker.createFromOptions(fileset, options("GPU"));
      } catch {
        delegate = "CPU";
        landmarker = await FaceLandmarker.createFromOptions(fileset, options("CPU"));
      }
      self.postMessage({
        type: "ready",
        delegate,
        connections: FaceLandmarker.FACE_LANDMARKS_TESSELATION.map(
          ({ start, end }) => ({ start, end }),
        ),
      });
    } catch (error) {
      self.postMessage({
        type: "error",
        phase: "model",
        message:
          error instanceof Error ? error.message : "Landmark model unavailable",
      });
    }
    return;
  }
  if (message.type === "calibrate") {
    calibrationPending = true;
    calibrationSamples = [];
    blinkState = createBlinkState();
    self.postMessage({ type: "calibration_pending" });
    return;
  }
  if (message.type === "frame" && message.bitmap) {
    if (!landmarker) {
      message.bitmap.close();
      return;
    }
    try {
      const result = landmarker.detectForVideo(
        message.bitmap,
        message.timestamp,
      );
      const faceCount = result.faceLandmarks?.length || 0;
      const ambiguous = faceCount > 1;
      const face = !ambiguous ? result.faceLandmarks?.[0] : undefined;
      const present = Boolean(face);
      let blinkEvent = false;
      let gazeDirection: GazeDirection | null = null;
      let pose: HeadPose | null = null;
      let calibrated = false;

      if (face) {
        const gazeOffset = estimateGazeOffset(face);
        const ear = averageEyeAspectRatio(
          face,
          message.bitmap.width / message.bitmap.height,
        );
        blinkEvent = updateBlinkState(ear, blinkState);
        const detectedPose = decomposeHeadPose(
          result.facialTransformationMatrixes?.[0]?.data,
        );

        if (calibrationPending && (gazeOffset !== null || detectedPose !== null)) {
          blinkEvent = false;
          calibrationSamples.push({ gaze: gazeOffset, pose: detectedPose });
          if (calibrationSamples.length >= 5) {
            const gazes = calibrationSamples.map((sample) => sample.gaze).filter((value): value is number => value !== null);
            const poses = calibrationSamples.map((sample) => sample.pose).filter((value): value is HeadPose => value !== null);
            neutralGazeOffset = gazes.length ? gazes.reduce((sum, value) => sum + value, 0) / gazes.length : null;
            neutralHeadPose = poses.length ? {
              yaw: poses.reduce((sum, value) => sum + value.yaw, 0) / poses.length,
              pitch: poses.reduce((sum, value) => sum + value.pitch, 0) / poses.length,
              roll: poses.reduce((sum, value) => sum + value.roll, 0) / poses.length,
            } : null;
            smoothedGazeOffset = neutralGazeOffset;
            smoothedHeadPose = neutralHeadPose ? { yaw: 0, pitch: 0, roll: 0 } : null;
            lastGazeDirection = "CENTER";
            blinkState = createBlinkState();
            if (ear !== null) updateBlinkState(ear, blinkState);
            calibrationPending = false;
            calibrationSamples = [];
            calibrated = true;
          }
        } else {
          if (gazeOffset !== null) {
            if (neutralGazeOffset === null) neutralGazeOffset = gazeOffset;
            smoothedGazeOffset =
              smoothedGazeOffset === null
                ? gazeOffset
                : smoothedGazeOffset * 0.65 + gazeOffset * 0.35;
            gazeDirection = classifyGaze(
              smoothedGazeOffset,
              neutralGazeOffset,
              lastGazeDirection,
            );
            if (gazeDirection) lastGazeDirection = gazeDirection;
          } else {
            smoothedGazeOffset = null;
          }
          if (detectedPose) {
            if (neutralHeadPose === null) neutralHeadPose = detectedPose;
            const relative = relativeHeadPose(detectedPose, neutralHeadPose);
            pose = smoothHeadPose(smoothedHeadPose, relative);
            smoothedHeadPose = pose;
          } else {
            smoothedHeadPose = null;
          }
        }
      } else {
        if (calibrationPending) calibrationSamples = [];
        updateBlinkState(null, blinkState);
        lastGazeDirection = "CENTER";
        smoothedGazeOffset = null;
        smoothedHeadPose = null;
      }

      const lookingAway =
        gazeDirection === null && pose === null
          ? null
          : gazeDirection !== null && gazeDirection !== "CENTER"
            ? true
            : Boolean(
                pose &&
                  (Math.abs(pose.yaw) >= 20 || Math.abs(pose.pitch) >= 15),
              );
      self.postMessage({
        type: "summary",
        present,
        ambiguous,
        lookingAway,
        blinkEvent,
        gazeDirection,
        headYawDegrees: pose ? Math.round(pose.yaw * 10) / 10 : null,
        headPitchDegrees: pose ? Math.round(pose.pitch * 10) / 10 : null,
        headRollDegrees: pose ? Math.round(pose.roll * 10) / 10 : null,
        calibrated,
        landmarks: (result.faceLandmarks || []).map((face) =>
          face.map(({ x, y }) => ({ x, y })),
        ),
      });
    } catch (error) {
      self.postMessage({
        type: "error",
        phase: "frame",
        message:
          error instanceof Error ? error.message : "Frame processing failed",
      });
    } finally {
      message.bitmap.close();
    }
  }
};
