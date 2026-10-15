import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "tests/browser",
  timeout: 60_000,
  expect: { timeout: 10_000 },
  use: { baseURL: process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:5193", trace: "retain-on-failure" },
  reporter: process.env.CI ? "github" : "list",
  workers: 1,
  webServer: process.env.PLAYWRIGHT_BASE_URL ? undefined : [
    { command: "python backend/prepare.py && python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8093", url: "http://127.0.0.1:8093/api/health", reuseExistingServer: !process.env.CI, timeout: 60_000 },
    { command: "npm run dev -- --host 127.0.0.1 --port 5193 --strictPort", env: { VITE_API_URL: "http://127.0.0.1:8093/api" }, url: "http://127.0.0.1:5193", reuseExistingServer: !process.env.CI, timeout: 60_000 },
  ],
});
