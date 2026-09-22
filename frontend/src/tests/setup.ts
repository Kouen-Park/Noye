import "@testing-library/jest-dom/vitest";

import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

// Each test renders into a fresh document. Without this, a query in one test can
// match an element another test left behind, which produces failures that move
// when tests are reordered.
afterEach(() => {
  cleanup();
});
