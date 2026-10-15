import { cp, mkdir, writeFile } from 'node:fs/promises'
import { resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const root = resolve(fileURLToPath(new URL('..', import.meta.url)))
const target = resolve(root, 'public/models')
const modelUrl = 'https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task'
await mkdir(target, { recursive: true })
await cp(resolve(root, 'node_modules/@mediapipe/tasks-vision/wasm'), resolve(target, 'wasm'), { recursive: true })
const response = await fetch(modelUrl)
if (!response.ok) throw new Error(`Unable to download pinned MediaPipe model (${response.status})`)
await writeFile(resolve(target, 'face_landmarker.task'), Buffer.from(await response.arrayBuffer()))
console.log('Pinned MediaPipe WASM and face landmarker model written to public/models')
