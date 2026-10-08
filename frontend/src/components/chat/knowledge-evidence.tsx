import Link from "next/link";
import { Passages } from "@/components/chat/passages";
import { MarkdownContent } from "@/components/documents/document-preview";
import { wikiHref, wikiLinkHref, wikiPreviewContent, type WikiContributor, type WikiScope } from "@/lib/wiki";
import type { ChatCitation } from "@/lib/api";

export interface KnowledgeSnapshot {
  version: number;
  scope: { mode: WikiScope["mode"]; source_ids?: string[]; root_ids?: string[] };
  manifest?: { source_id: string }[];
  wiki_state: string;
  warnings: string[];
  insufficient_evidence: boolean;
  wiki_pages: { wiki_id: string; revision_id: string; title: string; kind: string;
    origin: string; contributors?: WikiContributor[]; interpretation: string; source_ids: string[]; revision_status: string }[];
}

/** Wiki interpretations and original evidence stay visibly separate, including old answers. */
export function KnowledgeEvidence({ snapshot, citations }: {
  snapshot: KnowledgeSnapshot; citations: ChatCitation[];
}) {
  // Navigation must retain the answer's inventory, including an all/root request.
  // Older snapshots without an inventory can expose only their captured source IDs.
  const sourceIds = snapshot.manifest?.map(source => source.source_id)
    ?? [...new Set(snapshot.wiki_pages.flatMap(page => page.source_ids))];
  const scope: WikiScope = snapshot.scope.mode === "empty"
    ? { mode: "empty", source_ids: [], root_ids: [] }
    : { mode: "chosen", source_ids: sourceIds, root_ids: [] };
  return <section aria-label="Knowledge evidence" className="mt-4 rounded-lg border border-edge bg-card p-4 text-sm">
    <h3 className="font-semibold">Wiki & original evidence</h3>
    <p className="mt-1 text-xs text-ink-soft">Wiki is interpretation. Check exact facts, numbers and exceptions in the original passages saved with this answer.</p>
    {snapshot.insufficient_evidence && <p role="status" className="mt-2 text-ink-soft">No usable original evidence was found in the selected scope.</p>}
    {snapshot.wiki_state === "no_matches" && <p className="mt-2 text-xs text-ink-soft">No relevant current Wiki pages; originals were searched directly.</p>}
    {snapshot.warnings.map(warning => <p key={warning} role="status" className="mt-2 break-words text-xs text-ink-soft">{warning}</p>)}
    {snapshot.wiki_pages.length > 0 && <ul className="mt-3 space-y-3" aria-label="Wiki interpretations">
      {snapshot.wiki_pages.map(page => <li key={page.wiki_id}>
        <Link className="inline-flex min-h-11 items-center text-accent-ink underline"
          href={`${wikiHref(page.wiki_id, scope)}&revision=${encodeURIComponent(page.revision_id)}`}>
          {page.title} · {page.kind}
        </Link>
        <p className="break-all text-xs text-ink-faint">Wiki revision {page.revision_id} · saved interpretation
          {page.revision_status !== "unchanged" && ` · ${page.revision_status}`}</p>
        <details className="mt-1"><summary className="cursor-pointer py-2">Interpretation consulted at the time</summary>
          <div className="mt-2"><MarkdownContent content={wikiPreviewContent(page.interpretation, page.contributors, scope)} allowImages={false}
            rewriteLink={href => wikiLinkHref(href, scope, page.contributors)} /></div>
        </details>
      </li>)}
    </ul>}
    <h4 className="mt-4 font-semibold">Original passages consulted</h4>
    <Passages citations={citations} />
  </section>;
}
