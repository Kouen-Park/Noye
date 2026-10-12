import { describe, expect, it, vi } from "vitest";

describe("desktop backend address", () => {
  it("keeps the web fallback and updates requests and source/export links together", async () => {
    vi.resetModules();
    const runtime = await import("./runtime");
    const api = await import("./api");
    expect(runtime.apiBaseUrl()).toBe("http://127.0.0.1:8000");
    runtime.setDesktopBaseUrl("http://127.0.0.1:34567");
    expect(api.sourceUrl("source", 2)).toBe("http://127.0.0.1:34567/files/source/source#page=2");
    expect(api.documentExportUrl("doc")).toBe("http://127.0.0.1:34567/documents/doc/export.md");
    const fetch = vi.fn().mockResolvedValue(new Response("[]"));
    vi.stubGlobal("fetch", fetch);
    try {
      await api.listFiles();
      expect(fetch.mock.calls[0][0]).toBe("http://127.0.0.1:34567/files");
    } finally { vi.unstubAllGlobals(); }
  });

  it("rejects remote addresses, credentials, paths and fragments", async () => {
    const { setDesktopBaseUrl } = await import("./runtime");
    for (const url of ["https://example.com", "http://localhost:8000", "http://127.0.0.1:8000/path",
      "http://127.0.0.1:0", "http://user:pass@127.0.0.1:8000", "http://127.0.0.1:8000/#page", "http://127.0.0.1:8000/?secret"])
      expect(() => setDesktopBaseUrl(url)).toThrow();
  });
});
