import test from "node:test";
import assert from "node:assert/strict";
import {
  classifyGaze,
  createBlinkState,
  decomposeHeadPose,
  estimateGazeOffset,
  eyeAspectRatio,
  relativeHeadPose,
  updateBlinkState,
} from "../src/behaviorMetrics.ts";

test("eye aspect ratio is normalized by eye width", () => {
  const points = Array.from({ length: 6 }, () => ({ x: 0, y: 0 }));
  points[0] = { x: 0, y: 0.5 };
  points[1] = { x: 0.3, y: 0.3 };
  points[2] = { x: 0.7, y: 0.3 };
  points[3] = { x: 1, y: 0.5 };
  points[4] = { x: 0.7, y: 0.7 };
  points[5] = { x: 0.3, y: 0.7 };
  assert.ok(Math.abs(eyeAspectRatio(points, [0, 1, 2, 3, 4, 5]) - 0.3) < 1e-9);
});

test("blink detector counts a closure once after the eyes reopen", () => {
  const state = createBlinkState();
  assert.equal(updateBlinkState(0.3, state), false);
  assert.equal(updateBlinkState(0.16, state), false);
  assert.equal(updateBlinkState(0.15, state), false);
  assert.equal(updateBlinkState(0.3, state), true);
  assert.equal(updateBlinkState(0.3, state), false);
  assert.equal(updateBlinkState(0.15, state), false);
  assert.equal(updateBlinkState(0.3, state), true);
});

test("blink detector does not count a closure that started while unobserved", () => {
  const state = createBlinkState();
  updateBlinkState(0.3, state);
  updateBlinkState(null, state);
  assert.equal(updateBlinkState(0.15, state), false);
  assert.equal(updateBlinkState(0.3, state), false);
});

test("gaze classification uses subject-relative labels with a neutral band and hysteresis", () => {
  assert.equal(classifyGaze(0.13), "LEFT");
  assert.equal(classifyGaze(-0.13), "RIGHT");
  assert.equal(classifyGaze(0.03), "CENTER");
  assert.equal(classifyGaze(0.09, 0, "LEFT"), "LEFT");
  assert.equal(classifyGaze(null), null);
});

test("iris offsets are normalized against eye width", () => {
  const points = Array.from({ length: 478 }, () => ({ x: 0, y: 0.5 }));
  points[263] = { x: 0.8, y: 0.5 };
  points[362] = { x: 0.6, y: 0.5 };
  points[33] = { x: 0.2, y: 0.5 };
  points[133] = { x: 0.4, y: 0.5 };
  for (const index of [474, 475, 476, 477]) points[index] = { x: 0.65, y: 0.5 };
  for (const index of [469, 470, 471, 472]) points[index] = { x: 0.25, y: 0.5 };
  assert.ok(Math.abs(estimateGazeOffset(points) + 0.25) < 1e-9);
});

test("head pose decomposition returns degrees and calibration-relative angles", () => {
  const yaw = 20 * Math.PI / 180;
  const matrix = [
    Math.cos(yaw), 0, -Math.sin(yaw), 0,
    0, 1, 0, 0,
    Math.sin(yaw), 0, Math.cos(yaw), 0,
    0, 0, 0, 1,
  ];
  const pose = decomposeHeadPose(matrix);
  assert.ok(pose);
  assert.ok(Math.abs(pose.yaw - 20) < 0.01);
  assert.ok(Math.abs(pose.pitch) < 0.01);
  assert.ok(Math.abs(pose.roll) < 0.01);
  assert.deepEqual(relativeHeadPose(pose, { yaw: 5, pitch: 2, roll: -3 }), {
    yaw: 15,
    pitch: -2,
    roll: 3,
  });
  assert.ok(Math.abs(decomposeHeadPose(matrix.map((value) => value * 1.7)).yaw - 20) < 0.01);
  assert.equal(decomposeHeadPose(null), null);
});
