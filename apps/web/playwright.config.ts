import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./a11y-tests",
  fullyParallel: false,
  forbidOnly: Boolean(process.env.CI),
  retries: 0,
  reporter: "list",
  timeout: 180_000,
  use: {
    baseURL: "http://127.0.0.1:3102",
    browserName: "chromium",
    headless: true,
  },
  webServer: [
    {
      command: "node test-fixtures/catalog-api.mjs",
      url: "http://127.0.0.1:8017/health",
      env: { PORT: "8017" },
      reuseExistingServer: false,
      timeout: 30_000,
    },
    {
      command: "npm run dev -- --hostname 127.0.0.1 --port 3102",
      url: "http://127.0.0.1:3102",
      env: {
        ENVIRONMENT: "development",
        API_URL: "http://127.0.0.1:8017",
        NEXT_PUBLIC_API_URL: "http://127.0.0.1:8017",
        SITE_URL: "http://localhost:3102",
        PORT: "3102",
        HOSTNAME: "127.0.0.1",
      },
      reuseExistingServer: false,
      timeout: 120_000,
    },
  ],
});
