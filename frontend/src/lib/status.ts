/**
 * Turning pipeline state into what a person reads.
 *
 * The backend's statuses name the work it does (`EMBEDDING`). The library names
 * what is happening to the reader's file ("Creating embeddings — step 3 of 4").
 * DESIGN.md §8 is the rule this file implements; keeping it in one place stops
 * the copy from drifting between components.
 */

import type { FileStatus, FileType, StoredFile } from "@/lib/api";

/** The four observable stages of ingestion, in order. */
export const STAGES: readonly FileStatus[] = ["UPLOADING", "EXTRACTING", "CHUNKING", "EMBEDDING"];

export const STAGE_COUNT = STAGES.length;

/** 1-based position of a processing file in the pipeline, or null if terminal. */
export function stageNumber(status: FileStatus): number | null {
  const index = STAGES.indexOf(status);
  return index === -1 ? null : index + 1;
}

/** What is happening right now, in the reader's terms. */
export function stageLabel(status: FileStatus): string {
  const step = stageNumber(status);
  const what: Record<string, string> = {
    UPLOADING: "Saving the file",
    EXTRACTING: "Reading the text",
    CHUNKING: "Splitting into passages",
    // Not "Creating embeddings". Three of these four stages are already in plain
    // language; that one word was the only place the pipeline's vocabulary
    // leaked into a sentence a person is meant to read while waiting.
    EMBEDDING: "Making it searchable",
  };
  if (step === null) return "";
  return `${what[status]} — step ${step} of ${STAGE_COUNT}`;
}

/**
 * How long a file may sit in one stage before the UI stops pretending it is fine.
 *
 * The backend touches `updated_at` on every status change, so a processing file
 * whose timestamp has gone quiet for this long has stalled. Using the server's
 * own clock avoids the client keeping its own bookkeeping across reloads.
 */
export const STALL_AFTER_MS = 60_000;

export function isStalled(file: StoredFile, now: number = Date.now()): boolean {
  if (!["UPLOADING", "EXTRACTING", "CHUNKING", "EMBEDDING"].includes(file.status)) {
    return false;
  }
  const touched = Date.parse(file.updated_at);
  if (Number.isNaN(touched)) return false;
  return now - touched > STALL_AFTER_MS;
}

/** Stopping and an interrupted run need different copy from extraction failure. */
export function stoppedReason(error: string | null): "cancelled" | "interrupted" | null {
  if (error === "Processing was cancelled.") return "cancelled";
  if (error === "Processing was interrupted.") return "interrupted";
  return null;
}

/** The short word on the status pill. */
export function statusWord(status: FileStatus, error: string | null = null): string {
  if (status === "READY") return "Ready";
  if (status === "FAILED") {
    const reason = stoppedReason(error);
    if (reason === "cancelled") return "Stopped";
    if (reason === "interrupted") return "Interrupted";
    return "Needs attention";
  }
  return "Indexing";
}

/** Which of the three groups a file belongs in. */
export type Group = "attention" | "working" | "ready";

export function groupOf(file: StoredFile): Group {
  if (file.status === "FAILED") return "attention";
  if (file.status === "READY") return "ready";
  return "working";
}

/**
 * Section headings, in the order they appear.
 *
 * Failures come first because they are the only group that needs a decision.
 */
export const GROUPS: readonly { key: Group; heading: string }[] = [
  { key: "attention", heading: "Needs your attention" },
  { key: "working", heading: "Working on it" },
  { key: "ready", heading: "Ready to search" },
];

const TYPE_LABELS: Record<FileType, string> = { pdf: "PDF", md: "MD", txt: "TXT" };

export function typeLabel(type: FileType): string {
  return TYPE_LABELS[type];
}

/**
 * A file size a person can read.
 *
 * Uses a non-breaking space so "2.4 MB" never wraps across a line (DESIGN.md
 * §—typography niceties).
 */
export function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes}\u00a0B`;
  const units = ["KB", "MB", "GB"];
  let value = bytes / 1024;
  let unit = 0;
  while (value >= 1024 && unit < units.length - 1) {
    value /= 1024;
    unit += 1;
  }
  const rounded = value >= 10 ? Math.round(value) : Math.round(value * 10) / 10;
  return `${rounded}\u00a0${units[unit]}`;
}

/** The supporting line under a file's name: size, pages, passages. */
export function factsLine(file: StoredFile): string {
  const parts = [formatSize(file.size)];
  if (file.page_count !== null) {
    parts.push(`${file.page_count}\u00a0${file.page_count === 1 ? "page" : "pages"}`);
  }
  if (file.chunk_count > 0) {
    parts.push(`${file.chunk_count}\u00a0${file.chunk_count === 1 ? "passage" : "passages"}`);
  }
  return parts.join(" · ");
}

/**
 * What a screen reader hears when a file finishes.
 *
 * Only terminal transitions are announced. Narrating every stage would talk
 * over someone trying to read the page.
 */
export function completionAnnouncement(file: StoredFile): string | null {
  if (file.status === "READY") {
    return `${file.name} is ready to search.`;
  }
  if (file.status === "FAILED") {
    const reason = stoppedReason(file.error);
    if (reason === "cancelled") return `${file.name} was stopped.`;
    if (reason === "interrupted") return `${file.name} was interrupted. You can retry it.`;
    return `${file.name} could not be read. ${file.error ?? ""}`.trim();
  }
  return null;
}
