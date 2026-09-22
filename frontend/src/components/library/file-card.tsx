"use client";

import { useRef, useState } from "react";

import { StageBar, StatusPill } from "@/components/library/status-indicators";
import { isProcessing, type StoredFile } from "@/lib/api";
import { factsLine, isStalled, typeLabel } from "@/lib/status";

/**
 * One file in the library.
 *
 * The type marker on the left reads as a book spine — a 3px coloured edge with
 * asymmetric corners (DESIGN.md §6) — and turns oxblood when the file failed,
 * so a failure is visible while scanning the column of markers alone.
 *
 * Removal is destructive and the backend cannot undo it: the delete drops the
 * vectors, the original, and the row. So it asks first, inline on the card
 * rather than in a modal, which keeps the decision next to the thing it is
 * about and keeps focus local.
 */

interface FileCardProps {
  file: StoredFile;
  onRemove: (id: string) => void;
  /** Lets the page move focus to this card after it is added. */
  registerRef?: (element: HTMLLIElement | null) => void;
}

export function FileCard({ file, onRemove, registerRef }: FileCardProps) {
  const [confirming, setConfirming] = useState(false);
  const removeButtonRef = useRef<HTMLButtonElement>(null);
  const failed = file.status === "FAILED";
  const working = isProcessing(file.status);
  // A file that has sat in one stage past the threshold has stalled. Removal is
  // blocked during normal processing because it races the background task still
  // writing this file's rows — but a file that never finishes would otherwise be
  // unremovable forever, which is worse than that race.
  const stalled = isStalled(file);
  const removable = !working || stalled;

  return (
    <li
      ref={registerRef}
      tabIndex={-1}
      className={`mb-2.5 flex items-start gap-3 rounded-lg border border-edge-strong bg-card px-4 py-3.5 ${
        failed ? "border-l-[3px] border-l-fail" : ""
      }`}
    >
      <span
        aria-hidden="true"
        className={`grid h-11 w-[34px] shrink-0 place-items-center border border-edge-strong bg-canvas text-[9px] font-bold tracking-wider text-ink-soft [border-radius:var(--radius-spine)] ${
          failed ? "border-l-[3px] border-l-fail" : "border-l-[3px] border-l-accent"
        }`}
      >
        {typeLabel(file.file_type)}
      </span>

      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-x-2.5 gap-y-1">
          <span className="truncate font-semibold" title={file.name}>
            {file.name}
          </span>
          <StatusPill status={file.status} />
        </div>

        <p className="mt-0.5 text-[12.5px] text-ink-soft">
          <span className="font-mono tabular-nums">{factsLine(file)}</span>
        </p>

        {working && <StageBar status={file.status} />}

        {stalled && (
          <p className="mt-2 rounded-md border border-edge-strong px-2.5 py-2 text-[12.5px] text-ink-soft">
            This is taking longer than usual. You can remove it and try again.
          </p>
        )}

        {failed && file.error && (
          <p className="mt-2 rounded-md bg-fail-wash px-2.5 py-2 text-[12.5px] text-fail">
            {file.error}
          </p>
        )}

        {failed && (
          // There is no retry endpoint, so "Remove" is the whole set of moves.
          // Saying so turns a dead end into a deliberate next step.
          <p className="mt-1.5 text-[12.5px] text-ink-soft">
            Noye cannot retry this file. Remove it, then add it again once the
            problem is fixed.
          </p>
        )}

        {confirming && (
          <div className="mt-2.5 flex flex-wrap items-center gap-2 rounded-md bg-fail-wash px-2.5 py-2">
            <p className="text-[12.5px] text-fail">
              Remove {file.name}? This cannot be undone.
              {stalled && " It may not have finished indexing, so some of its work could be left behind."}
            </p>
            <div className="ml-auto flex gap-2">
              <button
                type="button"
                autoFocus
                onClick={() => onRemove(file.id)}
                className="min-h-11 rounded-md bg-fail px-3 text-[12.5px] font-semibold text-canvas md:min-h-0 md:py-1.5"
              >
                Remove
              </button>
              <button
                type="button"
                onClick={() => {
                  setConfirming(false);
                  removeButtonRef.current?.focus();
                }}
                className="min-h-11 rounded-md border border-edge-strong px-3 text-[12.5px] text-ink-soft md:min-h-0 md:py-1.5"
              >
                Keep
              </button>
            </div>
          </div>
        )}
      </div>

      {!confirming && (
        <button
          ref={removeButtonRef}
          type="button"
          aria-disabled={!removable}
          onClick={() => {
            if (!removable) return;
            setConfirming(true);
          }}
          className={`min-h-11 shrink-0 rounded-md border border-edge-strong px-2.5 text-[12.5px] md:min-h-0 md:py-1.5 ${
            removable
              ? "text-ink-soft hover:border-fail hover:bg-fail-wash hover:text-fail"
              : "cursor-not-allowed text-ink-faint"
          }`}
        >
          {removable ? (
            "Remove"
          ) : (
            <>
              Remove<span className="sr-only"> — available once indexing finishes</span>
            </>
          )}
        </button>
      )}
    </li>
  );
}
