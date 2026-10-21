import { defineConfig, devices } from "@playwright/test";

/**
 * Real-flow suite for the presentation stack (`./demo/compose.sh`): every test clicks through the
 * UI against the real API, database, worker and the fake payment gateway.
 *   DEMO_URL=http://localhost:8090 npx playwright test -c playwright.demo.config.ts
 */
export default defineConfig({
  testDir: "./e2e-demo",
  timeout: 90_000,
  expect: { timeout: 15_000 },
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: [["list"]],
  use: {
    baseURL: process.env.DEMO_URL ?? "http://localhost:8090",
    trace: "off",
    // Inside Docker, reach the Compose stack through the host's published ports.
    launchOptions: process.env.DEMO_HOST_MAP
      ? { args: ["--host-resolver-rules=MAP localhost host.docker.internal"] }
      : {},
    screenshot: "only-on-failure",
  },
  projects: [
    {
      name: "desktop",
      use: {
        ...devices["Desktop Chrome"],
        viewport: { width: 1440, height: 900 },
      },
    },
    {
      name: "mobile",
      use: { ...devices["Pixel 7"], viewport: { width: 390, height: 844 } },
    },
  ],
});
