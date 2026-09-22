import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

/**
 * Vitest for the frontend.
 *
 * `resolve.tsconfigPaths` makes the `@/*` alias from tsconfig.json work in
 * tests, so a test imports exactly what a component imports. jsdom rather than
 * happy-dom because the component tests lean on real label/input association
 * and focus behaviour, which is where jsdom is the more faithful of the two.
 */
export default defineConfig({
  plugins: [react()],
  resolve: {
    tsconfigPaths: true,
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/tests/setup.ts"],
    include: ["src/**/*.test.{ts,tsx}"],
    css: false,
  },
});
