"use client";

import { useState } from "react";

import type { DocumentSummary } from "@/lib/api";

/**
 * Past documents, most recently edited first.
 *
 * "Generated" is marked rather than hidden, because a person will want to know
 * which documents started as a draft they then changed and which they wrote
 * themselves — the excerpt alone does not say.
 */

interface DocumentListProps {
  documents: DocumentSummary[];
  currentId: string | null;
  onOpen: (id: string) => void;
  onDelete: (id: string) => void;
  onNew: () => void;
  loading?: boolean;
  error?: string | null;
  onRetry?: () => void;
  creating?: boolean;
}

export function DocumentList({
  documents,
  currentId,
  onOpen,
  onDelete,
  onNew,
  loading = false,
  error = null,
  onRetry,
  creating = false,
}: DocumentListProps) {
  const [confirming, setConfirming] = useState<string | null>(null);

  return (
    <div>
      <div className="flex items-center justify-between gap-2">
        <h2 className="noye-ui-title">
          Documents
        </h2>
        <button
          type="button"
          onClick={onNew}
          disabled={creating}
          className="noye-button"
        >
          {creating ? "Creating…" : "New"}
        </button>
      </div>

      {loading && <p role="status" className="mt-2 text-sm text-ink-soft">Loading documents…</p>}
      {error && <div className="mt-2">
        <p role="alert" className="text-sm text-fail">{error}</p>
        {onRetry && <button type="button" className="noye-button mt-2" onClick={onRetry}>Retry documents</button>}
      </div>}
      {documents.length === 0 ? (!loading && !error && (

        <p className="mt-2 text-[12.5px] text-ink-soft">Nothing written yet.</p>
      )) : (
        <ul className="mt-2 space-y-1">
          {documents.map((document) => {
            if (confirming === document.id) {
              return (
                <li
                  key={document.id}
                  className="rounded-md bg-fail-wash px-2.5 py-2 text-[12.5px]"
                >
                  <p className="text-fail">
                    Delete “{document.title}”? This cannot be undone.
                  </p>
                  <div className="mt-1.5 flex gap-2">
                    <button
                      type="button"
                      autoFocus
                      onClick={() => {
                        onDelete(document.id);
                        setConfirming(null);
                      }}
                      className="rounded-md bg-fail px-2.5 py-1 text-[12px] font-semibold text-canvas"
                    >
                      Delete
                    </button>
                    <button
                      type="button"
                      onClick={() => setConfirming(null)}
                      className="rounded-md border border-edge-strong px-2.5 py-1 text-[12px] text-ink-soft"
                    >
                      Keep
                    </button>
                  </div>
                </li>
              );
            }

            const isCurrent = document.id === currentId;
            return (
              <li key={document.id} className="flex items-stretch gap-1">
                <button
                  type="button"
                  onClick={() => onOpen(document.id)}
                  aria-current={isCurrent ? "true" : undefined}
                  aria-label={`Open ${document.title}`}
                  className={`min-h-11 min-w-0 flex-1 rounded-md px-2.5 text-left text-[13px] md:min-h-0 md:py-1.5 ${
                    isCurrent
                      ? "bg-card font-semibold text-ink shadow-[inset_2.5px_0_0_var(--brand)]"
                      : "text-ink-soft hover:bg-card hover:text-ink"
                  }`}
                >
                  <span className="flex items-center gap-1.5">
                    <span className="block truncate" title={document.title}>
                      {document.title}
                    </span>
                    {document.is_generated && (
                      <span
                        className="shrink-0 rounded-sm bg-accent-wash px-1 text-xs font-semibold text-accent-ink"
                        title="Started as a generated draft"
                      >
                        DRAFTED
                      </span>
                    )}
                  </span>
                  <span className="noye-meta block truncate">
                    {document.excerpt || "Empty"}
                  </span>
                </button>
                <button
                  type="button"
                  onClick={() => setConfirming(document.id)}
                  aria-label={`Delete ${document.title}`}
                  className="rounded-md px-2 text-sm text-ink-soft hover:text-fail"
                >
                  ✕
                </button>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
