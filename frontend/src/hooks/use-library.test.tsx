import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { useLibrary } from "@/hooks/use-library";
import * as api from "@/lib/api";
import { ApiError, type IndexStatus, type StoredFile } from "@/lib/api";

const SOUND: IndexStatus = {
  embedding_model: "embeddinggemma",
  ready_files: 0,
  searchable_files: 0,
  deep: false,
  point_check_complete: false,
  problems: [],
};

const PROCESSING_FILE: StoredFile = {
  id: "file-1",
  name: "notes.md",
  file_type: "md",
  size: 100,
  status: "UPLOADING",
  error: null,
  page_count: null,
  chunk_count: 0,
  created_at: "2026-09-25T00:00:00Z",
  updated_at: "2026-09-25T00:00:00Z",
};

afterEach(() => {
  vi.restoreAllMocks();
});

function mockInitialLoad() {
  vi.spyOn(api, "listFiles").mockResolvedValue([]);
  vi.spyOn(api, "getIndexStatus").mockResolvedValue(SOUND);
}

describe("useLibrary index integrity", () => {
  it("loads the cheap integrity check without making it a library failure", async () => {
    mockInitialLoad();

    const { result } = renderHook(() => useLibrary());

    await waitFor(() => expect(result.current.phase).toBe("ready"));
    await waitFor(() => expect(result.current.integrityPhase).toBe("ready"));
    expect(api.getIndexStatus).toHaveBeenCalledWith(false, expect.any(AbortSignal));
    expect(result.current.integrity).toEqual(SOUND);
  });

  it("keeps the file list usable when the independent integrity request fails", async () => {
    vi.spyOn(api, "listFiles").mockResolvedValue([]);
    vi.spyOn(api, "getIndexStatus").mockRejectedValue(
      new ApiError(0, "Could not reach the integrity endpoint."),
    );

    const { result } = renderHook(() => useLibrary());

    await waitFor(() => expect(result.current.phase).toBe("ready"));
    await waitFor(() => expect(result.current.integrityPhase).toBe("error"));
    expect(result.current.files).toEqual([]);
    expect(result.current.integrityError).toBe("Could not reach the integrity endpoint.");
  });

  it("runs the point comparison only when the user asks", async () => {
    mockInitialLoad();
    const deep = { ...SOUND, deep: true, point_check_complete: true };
    vi.mocked(api.getIndexStatus).mockResolvedValueOnce(SOUND).mockResolvedValueOnce(deep);
    const { result } = renderHook(() => useLibrary());
    await waitFor(() => expect(result.current.integrityPhase).toBe("ready"));

    await act(async () => result.current.checkIndex());

    expect(api.getIndexStatus).toHaveBeenLastCalledWith(true, undefined);
    expect(result.current.integrity?.point_check_complete).toBe(true);
    expect(result.current.announcement).toBe("The library index is healthy.");
  });

  it("refreshes the file list after a rebuild starts", async () => {
    mockInitialLoad();
    vi.mocked(api.listFiles)
      .mockResolvedValueOnce([])
      .mockResolvedValueOnce([PROCESSING_FILE]);
    vi.spyOn(api, "rebuildIndex").mockResolvedValue({
      queued: 1,
      skipped: [],
      collection_recreated: false,
      embedding_model: "embeddinggemma",
    });
    const { result } = renderHook(() => useLibrary());
    await waitFor(() => expect(result.current.phase).toBe("ready"));

    await act(async () => result.current.rebuildIndex());

    expect(api.rebuildIndex).toHaveBeenCalledTimes(1);
    expect(result.current.files).toEqual([PROCESSING_FILE]);
    expect(result.current.rebuildResult?.queued).toBe(1);
    expect(result.current.announcement).toBe("1 file is being rebuilt.");
  });
});
