import { defineConfig, devices } from "@playwright/test";

const frontendPort = Number(process.env.E2E_FRONTEND_PORT ?? 3000);
const backendUrl = process.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000";
const frontendUrl = process.env.E2E_FRONTEND_URL ?? `http://127.0.0.1:${frontendPort}`;
const usesExternalFrontend = Boolean(process.env.E2E_FRONTEND_URL);
const reuseExistingServer = process.env.E2E_REUSE_EXISTING_SERVER !== "false";

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 2 : 0,
  reporter: process.env.CI ? [["list"], ["html", { open: "never" }]] : "list",
  timeout: 60_000,
  expect: {
    timeout: 15_000,
  },
  use: {
    baseURL: frontendUrl,
    trace: "on-first-retry",
    video: "retain-on-failure",
  },
  webServer: usesExternalFrontend
    ? undefined
    : {
        command: `npm run dev -- --port ${frontendPort}`,
        url: frontendUrl,
        reuseExistingServer,
        timeout: 60_000,
        env: {
          VITE_API_BASE_URL: backendUrl,
        },
      },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
});
