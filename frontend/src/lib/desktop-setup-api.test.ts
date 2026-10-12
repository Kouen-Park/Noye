import { afterEach, expect, it, vi } from "vitest";

import { getDesktopSetup } from "./api";

afterEach(() => vi.unstubAllGlobals());

it("uses a cancellable GET for desktop setup without sending content", async () => {
  const fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify({ hardware: {} })));
  vi.stubGlobal("fetch", fetch);
  const controller = new AbortController();
  await getDesktopSetup(controller.signal);
  expect(fetch.mock.calls[0][0]).toMatch(/\/runtime\/setup$/);
  expect(fetch.mock.calls[0][1]).toEqual({ signal: controller.signal });
});
