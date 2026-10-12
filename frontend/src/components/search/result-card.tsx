import { type SearchHit, sourceUrl } from "@/lib/api";
import { OriginalLink } from "@/components/original-link";

/**
 * One matching passage.
 *
 * File and page metadata lead the excerpt so a reader can judge its context
 * before opening the original. List order already conveys relevance.
 *
 * The score is deliberately not shown. Similarity is model-dependent and has no
 * user-facing meaning until a threshold is calibrated on real documents, which
 * has not happened — a bare 0.37 would invite the reader to interpret a number
 * nobody can currently explain.
 */

interface ResultCardProps {
  hit: SearchHit;
  /** 1-based position, shown as the badge. */
  rank: number;
}

export function ResultCard({ hit, rank }: ResultCardProps) {
  const hasPage = hit.page_number !== null;

  return (
    <li className="border-b border-edge py-4 first:pt-2">
      <div className="flex items-start gap-3">
        <span
          aria-hidden="true"
          className="mt-3 min-w-5 shrink-0 text-center text-[12px] tabular-nums text-ink-soft"
        >
          {rank}
        </span>

        <div className="min-w-0 flex-1">
          <div className="mb-2 flex flex-wrap items-center gap-x-3 gap-y-1">
            <span className="min-w-0 break-words text-[13px] font-semibold" title={hit.file_name}>
              {hit.file_name}
            </span>
            <span className="text-[12px] tabular-nums text-ink-soft">
              {hasPage ? `page ${hit.page_number}` : "no pages"}
            </span>
            <OriginalLink
              href={sourceUrl(hit.file_id, hit.page_number)}
              // The accessible name says which source, because a page of
              // results would otherwise be a list of identical "Open source"
              // links to anyone navigating by link.
              aria-label={
                hasPage
                  ? `Open ${hit.file_name} at page ${hit.page_number}`
                  : `Open ${hit.file_name}`
              }
              className="ml-auto inline-flex min-h-11 items-center text-[12px] font-medium text-accent-ink underline underline-offset-4"
            >
              Open source
            </OriginalLink>
          </div>
          <p className="whitespace-pre-wrap break-words text-[15px] leading-relaxed">{hit.content}</p>
        </div>
      </div>
    </li>
  );
}
