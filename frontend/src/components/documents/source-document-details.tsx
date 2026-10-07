"use client";

import { type SourceDocument } from "@/lib/source-documents";
import { wikiOriginalUrl } from "@/lib/wiki";

export function SourceDocumentDetails({ document, onRevision }: {
  document: SourceDocument; onRevision: (id: string) => void;
}) {
  const coverage = document.revision.metadata.coverage;
  return <section aria-label="Document source coverage" className="mb-4 rounded-lg border border-edge bg-card p-4 text-sm">
    <p className="font-semibold">{coverage.partial ? "Partial document" : "Selected source text processed"}</p>
    <p className="mt-1 text-xs text-ink-soft">{coverage.inventory_mode === "collection" ? "Collection inventory fixed at job start." : "Relevant sources discovered; the whole library was not reviewed."} {coverage.sources.filter(s => s.state === "processed").length}/{coverage.sources.length} selected sources processed.</p>
    <label className="mt-3 flex flex-wrap items-center gap-2">Revision
      <select className="min-h-11 max-w-full rounded-md border border-edge-strong bg-card px-2" value={document.revision.id} onChange={event => onRevision(event.target.value)}>
        {document.revisions.map(revision => <option key={revision.id} value={revision.id}>{revision.origin} · {new Date(revision.created_at).toLocaleString()}</option>)}
      </select>
    </label>
    <details className="mt-2"><summary className="min-h-11 cursor-pointer">Originals, coverage and saved evidence</summary>
      <ul className="mt-2 space-y-2">{coverage.sources.map(source => <li key={source.source_id}>{source.relative_path} · {source.state} · {source.characters_processed}/{source.characters_read} characters · {source.reason}
        {!!source.no_text_pages.length && ` No text on pages ${source.no_text_pages.join(", ")}.`}</li>)}</ul>
      <ul className="mt-3 space-y-2">{document.revision.metadata.citations.map((citation, n) => <li key={`${citation.id}-${n}`}>
        E{n + 1}: {citation.source.name} · {citation.current_status} · passage {citation.passage_index}
        {citation.current_status === "available" && <a href={wikiOriginalUrl(citation)} target="_blank" rel="noreferrer" className="ml-2 inline-flex min-h-11 items-center text-brand underline">Open original</a>}
        <p className="mt-1 break-all text-xs text-ink-soft">Version: {citation.source.source_version} · characters {citation.quote_start}–{citation.quote_end}</p>
        <blockquote className="mt-1 whitespace-pre-wrap border-l border-edge pl-3 text-xs">{citation.quote}</blockquote>
      </li>)}</ul>
      <p className="mt-2 text-xs text-ink-soft">{document.revision.metadata.model} · {document.revision.metadata.prompt_version} · {document.revision.metadata.processing_seconds}s. Saved evidence describes the first draft; user edits are not re-verified.</p>
    </details>
  </section>;
}
