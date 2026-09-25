import { afterEach, describe, expect, it, vi } from "vitest";

import { getIndexStatus, rebuildIndex } from "@/lib/api";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("index integrity API", () => {
  it("opts into the expensive point comparison explicitly", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          embedding_model: "embeddinggemma",
          ready_files: 1,
          searchable_files: 1,
          deep: true,
          point_check_complete: true,
          problems: [],
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
    );
    vi.stubGlobal("fetch", fetchMock);

    const result = await getIndexStatus(true);

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/index/status?deep=true"),
      expect.objectContaining({ signal: undefined }),
    );
    expect(result.point_check_complete).toBe(true);
  });

  it("starts a rebuild with POST and returns its plan", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          queued: 2,
          skipped: [],
          collection_recreated: false,
          embedding_model: "embeddinggemma",
        }),
        { status: 202, headers: { "Content-Type": "application/json" } },
      ),
    );
    vi.stubGlobal("fetch", fetchMock);

    const result = await rebuildIndex();

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/index/rebuild"),
      expect.objectContaining({ method: "POST" }),
    );
    expect(result.queued).toBe(2);
  });
});
