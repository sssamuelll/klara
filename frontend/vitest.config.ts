import { defineConfig } from "vitest/config";

export default defineConfig({
  resolve: {
    // stale tsc -b in-tree .js siblings must not shadow .ts (masked a fix once)
    extensions: [".ts", ".tsx", ".mts", ".mjs", ".js", ".jsx", ".json"],
  },
  test: {
    include: ["src/**/*.test.ts"],
  },
});
