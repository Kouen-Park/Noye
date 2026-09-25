import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { IntegrityPanel } from "@/components/library/integrity-panel";
import type { IndexStatus, RebuildStarted } from "@/lib/api";

function soundStatus(overrides: Partial<IndexStatus> = {}): IndexStatus {
  return {
    embedding_model: "embeddinggemma",
    ready_files: 2,
    searchable_files: 2,
    deep: false,
    point_check_complete: false,
    problems: [],
    ...overrides,
  };
}

function renderPanel(
  options: {
    status?: IndexStatus | null;
    phase?: "loading" | "ready" | "checking" | "rebuilding" | "error";
    error?: string | null;
    rebuildResult?: RebuildStarted | null;
    busyFileIds?: string[];
    onCheck?: () => Promise<void>;
    onReingest?: (fileId: string) => Promise<void>;
    onRebuild?: () => Promise<void>;
  } = {},
) {
  const props = {
    status: options.status === undefined ? soundStatus() : options.status,
    phase: options.phase ?? "ready",
    error: options.error ?? null,
    rebuildResult: options.rebuildResult ?? null,
    busyFileIds: options.busyFileIds ?? [],
    onCheck: options.onCheck ?? vi.fn().mockResolvedValue(undefined),
    onReingest: options.onReingest ?? vi.fn().mockResolvedValue(undefined),
    onRebuild: options.onRebuild ?? vi.fn().mockResolvedValue(undefined),
  };
  render(<IntegrityPanel {...props} />);
  return props;
}

describe("IntegrityPanel", () => {
  it("explains that the cheap check does not include stored point counts", () => {
    renderPanel();

    expect(screen.getByText(/2 of 2 ready files are searchable/i)).toBeInTheDocument();
    expect(screen.getByText(/compare the expected passages with Qdrant/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /check stored index/i })).toBeEnabled();
  });

  it("offers a one-file re-index for a changed source", async () => {
    const onReingest = vi.fn().mockResolvedValue(undefined);
    renderPanel({
      onReingest,
      status: soundStatus({
        problems: [
          {
            file_id: "file-1",
            file_name: "notes.md",
            problems: ["SOURCE_CHANGED"],
            searchable: true,
            indexed_points: null,
            expected_points: null,
          },
        ],
      }),
    });

    expect(screen.getByText(/saved original changed/i)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /re-index file/i }));
    expect(onReingest).toHaveBeenCalledWith("file-1");
  });

  it("requires confirmation before rebuilding for a model mismatch", async () => {
    const onRebuild = vi.fn().mockResolvedValue(undefined);
    renderPanel({
      onRebuild,
      status: soundStatus({
        ready_files: 1,
        searchable_files: 0,
        problems: [
          {
            file_id: "file-1",
            file_name: "lecture.pdf",
            problems: ["MODEL_CHANGED"],
            searchable: false,
            indexed_points: null,
            expected_points: null,
          },
        ],
      }),
    });

    await userEvent.click(screen.getByRole("button", { name: "Rebuild index" }));
    expect(onRebuild).not.toHaveBeenCalled();
    expect(screen.getByText(/local embedding can take several minutes/i)).toBeInTheDocument();

    const rebuildButtons = screen.getAllByRole("button", { name: "Rebuild index" });
    await userEvent.click(rebuildButtons[0]);
    expect(onRebuild).toHaveBeenCalledTimes(1);
  });

  it("does not call an unavailable deep check healthy", () => {
    renderPanel({
      status: soundStatus({ deep: true, point_check_complete: false }),
    });

    expect(screen.getByText(/stored index could not be checked/i)).toBeInTheDocument();
    expect(screen.queryByText(/all expected passages are present/i)).not.toBeInTheDocument();
  });

  it("shows measured missing-point counts instead of a generic warning", () => {
    renderPanel({
      status: soundStatus({
        deep: true,
        point_check_complete: true,
        problems: [
          {
            file_id: "file-1",
            file_name: "notes.md",
            problems: ["POINTS_MISSING"],
            searchable: true,
            indexed_points: 14,
            expected_points: 24,
          },
        ],
      }),
    });

    expect(screen.getByText(/14 of 24 expected passages remain/i)).toBeInTheDocument();
  });

  it("reports queued, recreated and skipped rebuild work", () => {
    renderPanel({
      rebuildResult: {
        queued: 2,
        skipped: [
          { file_id: "gone", file_name: "gone.pdf", reason: "The original is missing." },
        ],
        collection_recreated: true,
        embedding_model: "embeddinggemma",
      },
    });

    expect(screen.getByText(/2 files are being rebuilt with embeddinggemma/i)).toBeInTheDocument();
    expect(screen.getByText(/collection was recreated/i)).toBeInTheDocument();
    expect(screen.getByText(/gone\.pdf was skipped/i)).toBeInTheDocument();
  });
});
