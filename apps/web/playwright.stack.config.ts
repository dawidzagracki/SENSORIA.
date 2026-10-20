import { defineConfig } from "@playwright/test";

/**
 * Browser checks against a running full stack (Caddy → web → API → PostgreSQL).
 * Not part of the default `npm run a11y` (which uses a mocked catalog API).
 *   STACK_URL=http://host.docker.internal:8090 STACK_STATE='{…}' npx playwright test -c playwright.stack.config.ts
 */
export default defineConfig({
  testDir: "./a11y-stack-tests",
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: "list",
  timeout: 120_000,
  use: {
    baseURL: process.env.STACK_URL ?? "http://localhost:8090",
    browserName: "chromium",
    headless: true,
  },
});
