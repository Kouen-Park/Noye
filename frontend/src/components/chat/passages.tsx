"use client";

import { useState } from "react";

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
        className="flex min-h-11 w-full items-center gap-2 text-left text-[12px] font-bold uppercase tracking-[0.08em] text-ink-faint md:min-h-0"
      >
        <span
          aria-hidden="true"
          className={`inline-block transition-transform ${open ? "rotate-90" : ""}`}
        >
          ▸
        </span>
        {citations.length} {citations.length === 1 ? "passage" : "passages"} consulted
      </button>

      {open && (
        <ol className="mt-2 space-y-1.5">
          {citations.map((citation, index) => {
            const hasPage = citation.page_number !== null;
            return (
              <li
                key={`${citation.file_id}:${citation.page_number}:${index}`}
                className="flex flex-wrap items-center gap-x-2.5 gap-y-1 rounded-md border border-edge border-t-2 border-t-accent bg-canvas px-2.5 py-2"
              >
                <span
                  aria-hidden="true"
                  className="grid h-[17px] min-w-[17px] place-items-center rounded-sm bg-brand px-1 font-mono text-[10px] font-bold text-ink-inverse"
                >
                  {index + 1}
                </span>
                <span className="truncate text-[12.5px] font-semibold" title={citation.file_name}>
                  {citation.file_name}
                </span>
                <span className="font-mono text-[11.5px] tabular-nums text-ink-soft">
                  {hasPage ? `page ${citation.page_number}` : "no pages"}
                </span>
                <a
                  href={sourceUrl(citation.file_id, citation.page_number)}
                  target="_blank"
                  rel="noopener noreferrer"
                  aria-label={
                    hasPage
                      ? `Open ${citation.file_name} at page ${citation.page_number}`
                      : `Open ${citation.file_name}`
                  }
                  className="ml-auto rounded-md border border-edge-strong px-2 py-1 text-[11.5px] font-semibold text-accent-ink hover:bg-brand-wash"
                >
                  Open
                </a>
              </li>
            );
          })}
        </ol>
      )}
    </div>
  );
}
