import { type SearchHit, sourceUrl } from "@/lib/api";

/**
 * One matching passage.
 *
 * The citation is the product's signature (DESIGN.md §7), so the card is built
 * around it: a brass top rule, the file name, and the page set in mono as the
 * evidence it is. The rank number is the numbered badge the Library's chat
 * preview already used, kept so a result and a citation look like the same
 * thing in two places.
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
    <li className="mb-2.5 rounded-lg border border-edge-strong border-t-2 border-t-accent bg-card px-4 py-3.5">
      <div className="flex items-start gap-3">
        <span
          aria-hidden="true"
          className="mt-0.5 grid h-[18px] min-w-[18px] shrink-0 place-items-center rounded-sm bg-brand px-1 font-mono text-[10.5px] font-bold text-ink-inverse"
        >
          {rank}
        </span>

        <div className="min-w-0 flex-1">
          <p className="text-[14.5px] leading-relaxed">{hit.content}</p>

          <div className="mt-2.5 flex flex-wrap items-center gap-x-3 gap-y-1">
            <span className="truncate text-[12.5px] font-semibold" title={hit.file_name}>
              {hit.file_name}
            </span>
            <span className="font-mono text-[11.5px] tabular-nums text-ink-soft">
              {hasPage ? `page ${hit.page_number}` : "no pages"}
            </span>
            <a
              href={sourceUrl(hit.file_id, hit.page_number)}
              target="_blank"
              rel="noopener noreferrer"
              // The accessible name says which source, because a page of
              // results would otherwise be a list of identical "Open source"
              // links to anyone navigating by link.
              aria-label={
                hasPage
                  ? `Open ${hit.file_name} at page ${hit.page_number}`
                  : `Open ${hit.file_name}`
              }
              className="ml-auto min-h-11 rounded-md border border-edge-strong px-2.5 py-1.5 text-[12.5px] font-semibold text-accent-ink hover:bg-brand-wash md:min-h-0"
            >
              Open source
            </a>
          </div>
        </div>
      </div>
    </li>
  );
}
