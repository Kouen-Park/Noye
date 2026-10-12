"use client";

import { useState } from "react";
import { SavedEvidence } from "@/components/saved-evidence";
import { OriginalLink } from "@/components/original-link";

import { type ChatCitation, sourceUrl } from "@/lib/api";

/**
 * The passages an answer was given as context.
 *
 * Named for what it is. These are the passages retrieved and handed to the model,
 * not proof that the answer rests on them: vector search always returns its
 * nearest neighbours, so a question the documents do not cover still retrieves
 * passages while the model correctly declines. Calling this "Sources" would claim
 * support that nobody has verified — see the plan's §12.4, which makes this
 * framing a requirement of this branch rather than a nicety.
 *
 * Collapsed by default so an answer reads as prose, and expandable because this
 * phase's own UI requirement is that sources be easy to inspect rather than
 * hidden. Each passage names its file and page and links to the original.
 */

interface PassagesProps {
  citations: ChatCitation[];
}

export function Passages({ citations }: PassagesProps) {
  const [open, setOpen] = useState(false);

  if (citations.length === 0) return null;

  return (
    <div className="mt-3 border-t border-edge pt-2.5">
      <button
        type="button"
        onClick={() => setOpen(!open)}
        aria-expanded={open}
        className="flex min-h-9 w-full items-center gap-2 text-left text-[13px] font-semibold text-ink-soft"
      >
        <span
          aria-hidden="true"
          className={`inline-block transition-transform ${open ? "rotate-90" : ""}`}
        >
          ▸
        </span>
        {citations.length} {citations.length === 1 ? "passage" : "passages"} consulted
      </button>

      {open && <PassageList citations={citations} />}
    </div>
  );
}

/** Shared by the inline disclosure and the chat inspection panel. */
export function PassageList({ citations }: PassagesProps) {
  return (
        <ol className="mt-3 divide-y divide-edge">
          {citations.map((citation, index) => {
            const hasPage = citation.page_number !== null;
            return (
              <li
                key={`${citation.file_id}:${citation.page_number}:${index}`}
                className="space-y-2 py-4 first:pt-0"
              >
                <div className="flex flex-wrap items-center gap-2">
                <span aria-hidden="true" className="text-xs tabular-nums text-ink-soft">{index + 1}.</span>
                <span className="min-w-0 text-sm font-semibold [overflow-wrap:anywhere]" title={citation.file_name}>
                  {citation.file_name}
                </span>
                <span className="text-xs tabular-nums text-ink-soft">
                  {hasPage ? `page ${citation.page_number}` : "no pages"}
                </span>
                </div>
                <div className="flex flex-wrap items-center gap-2 text-xs text-ink-soft">
                <p>Original: {citation.original_status ?? "unknown"}</p>
                {!["missing", "unavailable", "disconnected"].includes(citation.original_status ?? "unknown") && <OriginalLink
                  href={sourceUrl(citation.file_id, citation.page_number)}
                  aria-label={
                    hasPage
                      ? `Open ${citation.file_name} at page ${citation.page_number}`
                      : `Open ${citation.file_name}`
                  }
                  className="noye-button ml-auto text-accent-ink"
                >
                  Open current
                </OriginalLink>}
                </div>
                <div className="min-w-0">
                  <SavedEvidence citation={citation} />
                </div>
              </li>
            );
          })}
        </ol>
  );
}
