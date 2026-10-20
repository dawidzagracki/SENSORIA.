import { defineConfig } from "vitest/config";
import { fileURLToPath } from "node:url";

const projectRoot = fileURLToPath(new URL(".", import.meta.url));

export default defineConfig({
  resolve: { alias: { "@": projectRoot } },
  oxc: {
    jsx: "react-jsx",
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./vitest.setup.ts"],
    clearMocks: true,
    restoreMocks: true,
    exclude: [
      "**/node_modules/**",
      "**/dist/**",
      "a11y-tests/**",
      "a11y-stack-tests/**",
    ],
  },
});
