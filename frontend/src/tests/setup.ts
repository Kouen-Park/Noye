import "@testing-library/jest-dom/vitest";

import { cleanup } from "@testing-library/react";
import { afterEach, vi } from "vitest";

/**
 * `next/navigation` needs an app-router context that only a real Next render
 * provides; a component calling `useRouter` outside one throws "invariant expected
 * app router to be mounted". Mocking it here rather than per test file means a
 * component that starts using the router does not break unrelated tests.
 *
 * The mock records calls, so a test that cares about navigation can assert on
 * `mockRouter`. Tests that do not care simply keep working.
 */
export const mockRouter = {
  push: vi.fn(),
  replace: vi.fn(),
  back: vi.fn(),
  forward: vi.fn(),
  refresh: vi.fn(),
  prefetch: vi.fn(),
};

vi.mock("next/navigation", () => ({
  useRouter: () => mockRouter,
  useSearchParams: () => new URLSearchParams(),
  usePathname: () => "/",
}));

// Each test renders into a fresh document. Without this, a query in one test can
// match an element another test left behind, which produces failures that move
// when tests are reordered.
afterEach(() => {
  cleanup();
  for (const spy of Object.values(mockRouter)) spy.mockClear();
});
