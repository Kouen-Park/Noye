import { describe, expect, it } from "vitest";

import type { StoredFile } from "@/lib/api";
import {
  STAGE_COUNT,
  completionAnnouncement,
  factsLine,
  formatSize,
  groupOf,
  isStalled,
  stageLabel,
  stageNumber,
  statusWord,
  stoppedReason,
} from "@/lib/status";

function file(overrides: Partial<StoredFile> = {}): StoredFile {
  return {
    id: "f1",
    name: "notes.md",
    file_type: "md",
    size: 1024,
    status: "READY",
    error: null,
    page_count: null,
    chunk_count: 3,
    created_at: "2026-09-22T00:00:00+00:00",
    updated_at: "2026-09-22T00:00:00+00:00",
    ...overrides,
  };
}

describe("stage wording", () => {
  it("describes every stage in plain language", () => {
    expect(stageLabel("UPLOADING")).toBe("Saving the file — step 1 of 4");
    expect(stageLabel("EXTRACTING")).toBe("Reading the text — step 2 of 4");
    expect(stageLabel("CHUNKING")).toBe("Splitting into passages — step 3 of 4");
    expect(stageLabel("EMBEDDING")).toBe("Making it searchable — step 4 of 4");
  });

  it("never says 'embedding' to the reader", () => {
    // The pipeline's own vocabulary has no meaning to someone waiting for their
    // file, and this was the one stage where it used to leak through.
    for (const status of ["UPLOADING", "EXTRACTING", "CHUNKING", "EMBEDDING"] as const) {
      expect(stageLabel(status).toLowerCase()).not.toContain("embed");
    }
  });

  it("has no stage label for a settled file", () => {
    expect(stageNumber("READY")).toBeNull();
    expect(stageNumber("FAILED")).toBeNull();
    expect(stageLabel("READY")).toBe("");
  });

  it("numbers the stages consistently with the segment count", () => {
    expect(stageNumber("EMBEDDING")).toBe(STAGE_COUNT);
  });
});

describe("status word", () => {
  it("tells a stop apart from a failure", () => {
    expect(statusWord("FAILED", "Processing was cancelled.")).toBe("Stopped");
    expect(statusWord("FAILED", "Processing was interrupted.")).toBe("Interrupted");
    expect(statusWord("FAILED", "No extractable text found.")).toBe("Needs attention");
  });

  it("names the resting and working states", () => {
    expect(statusWord("READY")).toBe("Ready");
    expect(statusWord("CHUNKING")).toBe("Indexing");
  });

  it("reads a stop reason only from the exact backend sentences", () => {
    expect(stoppedReason("Processing was cancelled.")).toBe("cancelled");
    expect(stoppedReason("cancelled")).toBeNull();
    expect(stoppedReason(null)).toBeNull();
  });
});

describe("grouping", () => {
  it("puts a failure in the group that needs a decision", () => {
    expect(groupOf(file({ status: "FAILED", error: "boom" }))).toBe("attention");
  });

  it("separates work in progress from finished work", () => {
    expect(groupOf(file({ status: "EMBEDDING" }))).toBe("working");
    expect(groupOf(file({ status: "READY" }))).toBe("ready");
  });
});

describe("sizes and facts", () => {
  it("keeps the unit from wrapping away from the number", () => {
    // A non-breaking space, so "2.4 MB" never breaks across a line.
    expect(formatSize(2_516_582)).toBe("2.4\u00a0MB");
    expect(formatSize(512)).toBe("512\u00a0B");
  });

  it("rounds larger values to whole units", () => {
    expect(formatSize(14 * 1024 * 1024)).toBe("14\u00a0MB");
  });

  it("omits pages for a format that has none", () => {
    expect(factsLine(file({ page_count: null, chunk_count: 3 }))).toBe("1\u00a0KB · 3\u00a0passages");
  });

  it("reports pages when the format has them, and singularises", () => {
    expect(factsLine(file({ page_count: 1, chunk_count: 1 }))).toBe(
      "1\u00a0KB · 1\u00a0page · 1\u00a0passage",
    );
  });

  it("omits the passage count before anything is indexed", () => {
    expect(factsLine(file({ page_count: null, chunk_count: 0 }))).toBe("1\u00a0KB");
  });
});

describe("announcements", () => {
  it("announces only settled files", () => {
    expect(completionAnnouncement(file({ status: "CHUNKING" }))).toBeNull();
  });

  it("distinguishes ready, stopped, interrupted and failed", () => {
    expect(completionAnnouncement(file({ status: "READY" }))).toBe(
      "notes.md is ready to search.",
    );
    expect(
      completionAnnouncement(file({ status: "FAILED", error: "Processing was cancelled." })),
    ).toBe("notes.md was stopped.");
    expect(
      completionAnnouncement(file({ status: "FAILED", error: "Processing was interrupted." })),
    ).toBe("notes.md was interrupted. You can retry it.");
    expect(
      completionAnnouncement(file({ status: "FAILED", error: "It looks like a scan." })),
    ).toBe("notes.md could not be read. It looks like a scan.");
  });
});

describe("stall detection", () => {
  const touched = "2026-09-22T00:00:00+00:00";
  const at = (msAfter: number) => Date.parse(touched) + msAfter;

  it("calls a processing file stalled once the server's clock goes quiet", () => {
    const processing = file({ status: "EMBEDDING", updated_at: touched });
    expect(isStalled(processing, at(30_000))).toBe(false);
    expect(isStalled(processing, at(90_000))).toBe(true);
  });

  it("never calls a settled file stalled, however old it is", () => {
    expect(isStalled(file({ status: "READY", updated_at: touched }), at(86_400_000))).toBe(false);
    expect(isStalled(file({ status: "FAILED", updated_at: touched }), at(86_400_000))).toBe(
      false,
    );
  });
});
