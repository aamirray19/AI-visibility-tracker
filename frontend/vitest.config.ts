import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    environment: "jsdom",
    exclude: ["node_modules", ".next", "e2e"],
    globals: true,
    setupFiles: ["./src/test/setup.ts"]
  }
});
