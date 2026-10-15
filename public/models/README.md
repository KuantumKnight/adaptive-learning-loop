# Local MediaPipe assets

Run `npm run fetch:vision` after installing dependencies. It copies the pinned
`@mediapipe/tasks-vision` WASM runtime and downloads the versioned Face
Landmarker model from Google’s MediaPipe model distribution. The application
serves both assets locally; if they are absent, camera status remains
“signal unavailable” and learning continues without webcam evidence.

The pinned model source is:

`https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task`

The runtime and task implementation come from the [MediaPipe repository](https://github.com/google-ai-edge/mediapipe), which is Apache-2.0 licensed; retain the upstream license and notices when redistributing. The web task API documentation is [Face Landmarker for Web](https://ai.google.dev/edge/mediapipe/solutions/vision/face_landmarker/web_js). Confirm the model bundle terms for any distribution outside this academic project.

The model is used only for local landmark summaries. Raw frames and landmarks
are not sent to the API or stored in exports.
