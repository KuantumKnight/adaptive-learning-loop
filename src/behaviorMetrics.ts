export type Landmark3D = { x: number; y: number; z?: number };
export type GazeDirection = "LEFT" | "CENTER" | "RIGHT";
export type HeadPose = { yaw: number; pitch: number; roll: number };
export type BlinkState = {
  baseline: number | null;
  closed: boolean;
  armed: boolean;
};

const LEFT_EAR_POINTS = [362, 385, 387, 263, 373, 380] as const;
const RIGHT_EAR_POINTS = [33, 160, 158, 133, 153, 144] as const;
const LEFT_EYE_CORNERS = [263, 362] as const;
const RIGHT_EYE_CORNERS = [33, 133] as const;
const LEFT_IRIS = [474, 475, 476, 477] as const;
const RIGHT_IRIS = [469, 470, 471, 472] as const;

function distance(a: Landmark3D, b: Landmark3D, aspectRatio: number) {
  return Math.hypot(a.x - b.x, (a.y - b.y) / aspectRatio);
}

function pointAt(points: Landmark3D[], index: number) {
  const point = points[index];
  return point && Number.isFinite(point.x) && Number.isFinite(point.y)
    ? point
    : null;
}

export function eyeAspectRatio(
  points: Landmark3D[],
  indices: readonly number[],
  aspectRatio = 4 / 3,
) {
  if (indices.length !== 6) return null;
  const [cornerAIndex, upperAIndex, upperBIndex, cornerBIndex, lowerBIndex, lowerAIndex] = indices;
  const cornerA = pointAt(points, cornerAIndex);
  const upperA = pointAt(points, upperAIndex);
  const upperB = pointAt(points, upperBIndex);
  const cornerB = pointAt(points, cornerBIndex);
  const lowerB = pointAt(points, lowerBIndex);
  const lowerA = pointAt(points, lowerAIndex);
  if (!cornerA || !upperA || !upperB || !cornerB || !lowerB || !lowerA)
    return null;
  const width = distance(cornerA, cornerB, aspectRatio);
  if (width < 1e-6) return null;
  return (
    distance(upperA, lowerA, aspectRatio) +
    distance(upperB, lowerB, aspectRatio)
  ) / (2 * width);
}

export function averageEyeAspectRatio(points: Landmark3D[], aspectRatio = 4 / 3) {
  const left = eyeAspectRatio(points, LEFT_EAR_POINTS, aspectRatio);
  const right = eyeAspectRatio(points, RIGHT_EAR_POINTS, aspectRatio);
  return left === null || right === null ? null : (left + right) / 2;
}

export function createBlinkState(): BlinkState {
  return { baseline: null, closed: false, armed: false };
}

/** Returns true only once when an observed eye closure reopens. */
export function updateBlinkState(ear: number | null, state: BlinkState) {
  if (ear === null || !Number.isFinite(ear)) {
    state.closed = false;
    state.armed = false;
    return false;
  }

  if (state.baseline === null) {
    if (ear >= 0.2) {
      state.baseline = ear;
      state.armed = true;
    }
    return false;
  }

  const closeThreshold = state.baseline * 0.65;
  const openThreshold = state.baseline * 0.78;
  if (state.closed) {
    if (ear >= openThreshold) {
      state.closed = false;
      const counted = state.armed;
      state.armed = true;
      state.baseline = state.baseline * 0.98 + ear * 0.02;
      return counted;
    }
    return false;
  }

  if (ear <= closeThreshold && state.armed) {
    state.closed = true;
    return false;
  }
  if (ear >= openThreshold) {
    state.armed = true;
    state.baseline = state.baseline * 0.98 + ear * 0.02;
  }
  return false;
}

function irisOffset(
  points: Landmark3D[],
  corners: readonly [number, number],
  iris: readonly number[],
) {
  const a = pointAt(points, corners[0]);
  const b = pointAt(points, corners[1]);
  const irisPoints = iris.map((index) => pointAt(points, index));
  if (!a || !b || irisPoints.some((point) => !point)) return null;
  const irisCenterX =
    irisPoints.reduce((sum, point) => sum + point!.x, 0) / irisPoints.length;
  const centerX = (a.x + b.x) / 2;
  const width = Math.abs(b.x - a.x);
  return width < 1e-6 ? null : (irisCenterX - centerX) / width;
}

/** Horizontal iris displacement in image coordinates, normalized by eye width. */
export function estimateGazeOffset(points: Landmark3D[]) {
  const left = irisOffset(points, LEFT_EYE_CORNERS, LEFT_IRIS);
  const right = irisOffset(points, RIGHT_EYE_CORNERS, RIGHT_IRIS);
  return left === null || right === null ? null : (left + right) / 2;
}

/** Direction labels are relative to the learner, facing the camera. */
export function classifyGaze(
  offset: number | null,
  neutralOffset = 0,
  previous: GazeDirection = "CENTER",
): GazeDirection | null {
  if (offset === null || !Number.isFinite(offset)) return null;
  const relative = offset - neutralOffset;
  if (previous === "LEFT" && relative >= 0.08) return "LEFT";
  if (previous === "RIGHT" && relative <= -0.08) return "RIGHT";
  if (relative >= 0.12) return "LEFT";
  if (relative <= -0.12) return "RIGHT";
  return "CENTER";
}

function wrapDegrees(degrees: number) {
  return ((degrees + 180) % 360 + 360) % 360 - 180;
}

/** Decomposes MediaPipe's column-major 4x4 facial rotation matrix. */
export function decomposeHeadPose(matrix: number[] | null | undefined): HeadPose | null {
  if (!matrix || matrix.length < 16 || matrix.some((value) => !Number.isFinite(value)))
    return null;
  const scaleX = Math.hypot(matrix[0], matrix[1], matrix[2]);
  const scaleY = Math.hypot(matrix[4], matrix[5], matrix[6]);
  const scaleZ = Math.hypot(matrix[8], matrix[9], matrix[10]);
  if (scaleX < 1e-6 || scaleY < 1e-6 || scaleZ < 1e-6) return null;
  const r00 = matrix[0] / scaleX;
  const r10 = matrix[1] / scaleX;
  const r20 = matrix[2] / scaleX;
  const r21 = matrix[6] / scaleY;
  const r22 = matrix[10] / scaleZ;
  const yaw = Math.asin(Math.max(-1, Math.min(1, -r20)));
  const pitch = Math.atan2(r21, r22);
  const roll = Math.atan2(r10, r00);
  const degrees = 180 / Math.PI;
  return {
    yaw: wrapDegrees(yaw * degrees),
    pitch: wrapDegrees(pitch * degrees),
    roll: wrapDegrees(roll * degrees),
  };
}

export function relativeHeadPose(pose: HeadPose, neutral: HeadPose): HeadPose {
  return {
    yaw: wrapDegrees(pose.yaw - neutral.yaw),
    pitch: wrapDegrees(pose.pitch - neutral.pitch),
    roll: wrapDegrees(pose.roll - neutral.roll),
  };
}

export function smoothHeadPose(
  previous: HeadPose | null,
  current: HeadPose,
  weight = 0.35,
): HeadPose {
  if (!previous) return current;
  return {
    yaw: wrapDegrees(previous.yaw + wrapDegrees(current.yaw - previous.yaw) * weight),
    pitch: wrapDegrees(previous.pitch + wrapDegrees(current.pitch - previous.pitch) * weight),
    roll: wrapDegrees(previous.roll + wrapDegrees(current.roll - previous.roll) * weight),
  };
}
