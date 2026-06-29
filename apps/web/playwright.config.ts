import { defineConfig, devices } from "@playwright/test";

const WEB_PORT = process.env.PORT ?? "3000";
const API_PORT = process.env.API_PORT ?? "8000";
const baseURL = process.env.PLAYWRIGHT_BASE_URL ?? `http://localhost:${WEB_PORT}`;

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  workers: 1,
  timeout: 120_000,
  expect: { timeout: 30_000 },
  reporter: process.env.CI ? "github" : "list",
  use: {
    ...devices["Desktop Chrome"],
    baseURL,
    trace: "on-first-retry",
    screenshot: "only-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: [
    {
      command: "bash ../../scripts/e2e-api.sh",
      url: `http://127.0.0.1:${API_PORT}/api/v1/health`,
      reuseExistingServer: !process.env.CI,
      timeout: 180_000,
      cwd: __dirname,
    },
    {
      command: "pnpm dev",
      url: `${baseURL}/login`,
      reuseExistingServer: !process.env.CI,
      timeout: 120_000,
      env: {
        ...process.env,
        NEXT_PUBLIC_API_URL: "/api/v1",
        AURORA_API_DEV_URL: `http://127.0.0.1:${API_PORT}`,
      },
    },
  ],
});
