"use client";

import { useRef, useState } from "react";

import { CheckIcon, CrossIcon } from "@/components/icons";
import type { IntegrityPhase } from "@/hooks/use-library";
import type {
  FileIntegrityProblem,
  IndexProblem,
  IndexStatus,
  RebuildStarted,
} from "@/lib/api";

interface IntegrityPanelProps {
  status: IndexStatus | null;
  phase: IntegrityPhase;
  error: string | null;
  rebuildResult: RebuildStarted | null;
  busyFileIds: string[];
  onCheck: () => Promise<void>;
  onReingest: (fileId: string) => Promise<void>;
  onRebuild: () => Promise<void>;
}

const COPY: Record<Exclude<IndexProblem, "POINTS_MISSING">, string> = {
  MISSING_SOURCE:
    "The saved original is missing. Remove this entry below, then add the original again.",
  SOURCE_CHANGED:
    "The saved original changed after it was indexed. Re-index it to use the current contents.",
  MODEL_CHANGED:
    "Its passages were created by an older embedding model, so this file is not searchable.",
};

function problemCopy(file: FileIntegrityProblem, problem: IndexProblem): string {
  if (problem !== "POINTS_MISSING") return COPY[problem];
  if (file.indexed_points === null || file.expected_points === null) {
    return "Some indexed passages are missing from storage.";
  }
  return `${file.indexed_points} of ${file.expected_points} expected passages remain in the stored index.`;
}

function needsWholeRebuild(status: IndexStatus | null): boolean {
  return Boolean(
    status?.problems.some((file) =>
      file.problems.some(
        (problem) => problem === "MODEL_CHANGED" || problem === "POINTS_MISSING",
      ),
    ),
  );
}

export function IntegrityPanel({
  status,
  phase,
  error,
  rebuildResult,
  busyFileIds,
  onCheck,
  onReingest,
  onRebuild,
}: IntegrityPanelProps) {
  const [confirmingRebuild, setConfirmingRebuild] = useState(false);
  const rebuildButtonRef = useRef<HTMLButtonElement>(null);
  const checking = phase === "checking";
  const rebuilding = phase === "rebuilding";
  const hasProblems = Boolean(status && status.problems.length > 0);
  const rebuildNeeded = needsWholeRebuild(status);
  const pointCheckUnavailable = Boolean(
    status?.deep && !status.point_check_complete,
  );

  return (
    <section
      aria-labelledby="index-health-heading"
      className="mt-5 rounded-lg border border-edge-strong bg-card px-4 py-4"
    >
      <div className="flex flex-wrap items-start gap-3">
        <div className="min-w-0 flex-1">
          <h2 id="index-health-heading" className="text-[17px]">
            Index health
          </h2>
          {phase === "loading" && status === null ? (
            <p className="mt-1 text-[13px] text-ink-soft">Checking your library…</p>
          ) : hasProblems ? (
            <p className="mt-1 flex items-center gap-1.5 text-[13px] text-fail">
              <CrossIcon className="h-3.5 w-3.5 shrink-0" />
              {status!.problems.length} {status!.problems.length === 1 ? "file needs" : "files need"}{" "}
              attention.
            </p>
          ) : (
            <p className="mt-1 flex items-center gap-1.5 text-[13px] text-ink-soft">
              <CheckIcon className="h-3.5 w-3.5 shrink-0" />
              {status
                ? `${status.searchable_files} of ${status.ready_files} ready ${status.ready_files === 1 ? "file is" : "files are"} searchable.`
                : "Index status is unavailable."}
            </p>
          )}
        </div>

        <button
          type="button"
          onClick={() => void onCheck()}
          disabled={checking || rebuilding}
          className="min-h-11 rounded-md border border-edge-strong px-3 text-[12.5px] font-semibold text-ink-soft hover:bg-brand-wash disabled:cursor-wait disabled:opacity-60 md:min-h-0 md:py-2"
        >
          {checking ? "Checking…" : "Check stored index"}
        </button>
      </div>

      {status && !status.deep && (
        <p className="mt-2 text-[12.5px] text-ink-faint">
          Source files and embedding models were checked. Use “Check stored index” to compare
          the expected passages with Qdrant.
        </p>
      )}

      {status?.deep && status.point_check_complete && !hasProblems && (
        <p className="mt-2 rounded-md border border-edge-strong px-3 py-2 text-[12.5px] text-ink-soft">
          Stored index checked. All expected passages are present.
        </p>
      )}

      {pointCheckUnavailable && (
        <div className="mt-3 rounded-md border border-fail bg-fail-wash px-3 py-2">
          <p className="font-semibold text-fail">The stored index could not be checked.</p>
          <p className="mt-1 text-[12.5px] text-fail">
            Make sure Qdrant is running, then check again. This is not reported as damaged data.
          </p>
        </div>
      )}

      {error && (
        <div className="mt-3 rounded-md border border-fail bg-fail-wash px-3 py-2">
          <p className="font-semibold text-fail">{error}</p>
        </div>
      )}

      {status && status.problems.length > 0 && (
        <ul className="mt-3 space-y-2">
          {status.problems.map((file) => {
            const canReingest =
              file.problems.includes("SOURCE_CHANGED") &&
              !file.problems.includes("MODEL_CHANGED") &&
              !file.problems.includes("POINTS_MISSING");
            const busy = busyFileIds.includes(file.file_id);
            return (
              <li
                key={file.file_id}
                className="rounded-md border border-edge-strong bg-canvas px-3 py-3"
              >
                <div className="flex flex-wrap items-start gap-3">
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-[13.5px] font-semibold" title={file.file_name}>
                      {file.file_name}
                    </p>
                    <ul className="mt-1.5 space-y-1 text-[12.5px] text-ink-soft">
                      {file.problems.map((problem) => (
                        <li key={problem}>• {problemCopy(file, problem)}</li>
                      ))}
                    </ul>
                  </div>
                  {canReingest && (
                    <button
                      type="button"
                      onClick={() => void onReingest(file.file_id)}
                      disabled={busy || rebuilding}
                      className="min-h-11 rounded-md border border-edge-strong px-3 text-[12.5px] font-semibold text-accent-ink hover:bg-brand-wash disabled:cursor-wait disabled:opacity-60 md:min-h-0 md:py-2"
                    >
                      {busy ? "Re-indexing…" : "Re-index file"}
                    </button>
                  )}
                </div>
              </li>
            );
          })}
        </ul>
      )}

      {rebuildNeeded && !confirmingRebuild && (
        <button
          ref={rebuildButtonRef}
          type="button"
          onClick={() => setConfirmingRebuild(true)}
          disabled={rebuilding}
          className="mt-3 min-h-11 rounded-md bg-brand px-4 text-[13px] font-semibold text-ink-inverse hover:bg-brand-hover disabled:cursor-wait disabled:opacity-60 md:min-h-0 md:py-2"
        >
          {rebuilding ? "Starting rebuild…" : "Rebuild index"}
        </button>
      )}

      {confirmingRebuild && (
        <div className="mt-3 rounded-md bg-accent-wash px-3 py-3">
          <p className="text-[13px] text-ink">
            Re-index every available source? Local embedding can take several minutes.
          </p>
          <div className="mt-2 flex flex-wrap gap-2">
            <button
              type="button"
              autoFocus
              onClick={() => {
                setConfirmingRebuild(false);
                void onRebuild();
              }}
              className="min-h-11 rounded-md bg-brand px-3 text-[12.5px] font-semibold text-ink-inverse hover:bg-brand-hover md:min-h-0 md:py-2"
            >
              Rebuild index
            </button>
            <button
              type="button"
              onClick={() => {
                setConfirmingRebuild(false);
                rebuildButtonRef.current?.focus();
              }}
              className="min-h-11 rounded-md border border-edge-strong px-3 text-[12.5px] text-ink-soft hover:bg-brand-wash md:min-h-0 md:py-2"
            >
              Keep current index
            </button>
          </div>
        </div>
      )}

      {rebuildResult && (
        <div className="mt-3 rounded-md border border-edge-strong px-3 py-2 text-[12.5px] text-ink-soft">
          <p>
            {rebuildResult.queued === 0
              ? "No files were queued for rebuilding."
              : `${rebuildResult.queued} ${rebuildResult.queued === 1 ? "file is" : "files are"} being rebuilt with ${rebuildResult.embedding_model}. Progress appears on the file cards below.`}
          </p>
          {rebuildResult.collection_recreated && (
            <p className="mt-1">
              The old index used a different vector size, so its collection was recreated.
            </p>
          )}
          {rebuildResult.skipped.length > 0 && (
            <ul className="mt-1">
              {rebuildResult.skipped.map((file) => (
                <li key={file.file_id}>
                  {file.file_name} was skipped — {file.reason}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </section>
  );
}
