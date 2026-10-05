import { afterEach, expect, it, vi } from "vitest";
import { desktopServiceRequest, type AiSettings } from "./ai-settings";

const settings = { control_token: "synthetic-capability" } as AiSettings;
afterEach(() => { vi.unstubAllGlobals(); vi.useRealTimers(); });

it("sends the desktop capability and explicit service confirmation, not cloud keys", async () => {
  const fetch = vi.fn().mockResolvedValue(new Response("{}"));
  vi.stubGlobal("fetch", fetch);
  await desktopServiceRequest(settings, "/start", "POST", { service: "qdrant", confirmed: true });
  expect(fetch).toHaveBeenCalledWith("http://127.0.0.1:8000/services/start", expect.objectContaining({
    method: "POST", headers: { "X-Noye-Control": "synthetic-capability", "Content-Type": "application/json" },
    body: JSON.stringify({ service: "qdrant", confirmed: true }),
  }));
});

it("has a ten-second deadline and clears its timer after completion", async () => {
  vi.useFakeTimers();
  let signal: AbortSignal;
  vi.stubGlobal("fetch", vi.fn((_url, options) => {
    signal = options.signal;
    return new Promise((_resolve, reject) => signal.addEventListener("abort", () => reject(new Error("Timed out"))));
  }));
  const pending = desktopServiceRequest(settings);
  const rejected = expect(pending).rejects.toThrow("Timed out");
  await vi.advanceTimersByTimeAsync(10_000);
  await rejected;
  expect(signal!.aborted).toBe(true);
  expect(vi.getTimerCount()).toBe(0);
});

it("forwards panel cancellation without requesting a service stop", async () => {
  const outer = new AbortController();
  const fetch = vi.fn((_url, options) => new Promise((_resolve, reject) => {
    options.signal.addEventListener("abort", () => reject(new Error("Panel closed")));
  }));
  vi.stubGlobal("fetch", fetch);
  const pending = desktopServiceRequest(settings, "", "GET", undefined, outer.signal);
  const rejected = expect(pending).rejects.toThrow("Panel closed");
  outer.abort(); await rejected;
  expect(fetch).toHaveBeenCalledOnce();
  expect(fetch.mock.calls[0][1].method).toBe("GET");
});

it("returns sanitized API error detail without claiming preparation", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ detail: "Port occupied" }), { status: 409 })));
  await expect(desktopServiceRequest(settings, "/start", "POST", {})).rejects.toThrow("Port occupied");
});
