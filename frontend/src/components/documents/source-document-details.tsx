"use client";

import { type SourceDocument } from "@/lib/source-documents";
import { wikiOriginalUrl } from "@/lib/wiki";
import { OriginalLink } from "@/components/original-link";

export function SourceDocumentRevision({ document, onRevision }: {
  document: SourceDocument; onRevision: (id: string) => void;
}) {
  return <label className="flex flex-wrap items-center gap-2 noye-meta">Revision
    <select className="min-h-9 max-w-full rounded-md border border-edge-strong bg-card px-2 text-xs" value={document.revision.id} onChange={event => onRevision(event.target.value)}>
      {document.revisions.map(revision => <option key={revision.id} value={revision.id}>{revision.origin} · {new Date(revision.created_at).toLocaleString()}</option>)}
    </select>
  </label>;
}

export function SourceDocumentDetails({ document, onRevision, showRevision = true }: {
  document: SourceDocument; onRevision: (id: string) => void; showRevision?: boolean;
}) {
  const coverage = document.revision.metadata.coverage;
  return <section aria-label="Document source coverage" className="shrink-0 border-b border-edge px-4 py-2 text-sm">
    <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
    <p className={`noye-meta flex-1 ${coverage.partial ? "text-fail" : ""}`}><span>{coverage.partial ? "Partial document" : "Selected source text processed"}</span> · {coverage.sources.filter(s => s.state === "processed").length}/{coverage.sources.length} originals</p>
    {showRevision && <SourceDocumentRevision document={document} onRevision={onRevision} />}
    </div>
    <details className="noye-details mt-1"><summary>Originals, coverage and saved evidence{(coverage.synthesis_limits?.length || coverage.presentation_limits?.length) ? " · review limits" : ""}</summary>
    <p className="mt-2 noye-meta">{coverage.inventory_mode === "collection" ? "Collection inventory fixed at job start." : "Relevant sources discovered; the whole library was not reviewed."} {coverage.sources.filter(s => s.state === "processed").length}/{coverage.sources.length} selected sources processed.</p>
    {!!coverage.synthesis_limits?.length && <p className="mt-2 text-xs text-ink-soft">Some conclusions failed evidence verification. Review the saved originals; comparison or translation for those items remains unresolved.</p>}
    {!!coverage.presentation_limits?.length && <div className="mt-2 text-xs text-ink-soft">
      <p className="font-semibold">Document structure and language limits</p>
      <ul className="mt-1 list-disc space-y-1 pl-5">{coverage.presentation_limits.map((limit, n) => <li key={`${limit.code}-${n}`}>{limit.reason}</li>)}</ul>
    </div>}
      <ul className="mt-2 space-y-2">{coverage.sources.map(source => <li key={source.source_id}>{source.relative_path} · {source.state} · {source.characters_processed}/{source.characters_read} characters · {source.reason}
        {!!source.no_text_pages.length && ` No text on pages ${source.no_text_pages.join(", ")}.`}</li>)}</ul>
      <ul className="mt-3 space-y-2">{document.revision.metadata.citations.map((citation, n) => <li key={`${citation.id}-${n}`}>
        E{n + 1}: {citation.source.name}{citation.page_number !== null && ` · page ${citation.page_number}`} · {citation.current_status}
        {citation.current_status === "available" && <OriginalLink href={wikiOriginalUrl(citation)} className="ml-2 inline-flex min-h-9 items-center text-accent-ink underline">Open original</OriginalLink>}
        <blockquote className="mt-1 whitespace-pre-wrap border-l border-edge pl-3 text-sm leading-relaxed">{citation.quote}</blockquote>
        <details className="mt-1"><summary className="min-h-9 cursor-pointer noye-meta">Passage details</summary><p className="mt-1 break-all noye-meta">Version: {citation.source.source_version} · passage {citation.passage_index} · characters {citation.quote_start}–{citation.quote_end}</p><p className="mt-2 whitespace-pre-wrap text-sm">{citation.text}</p></details>
      </li>)}</ul>
      <p className="mt-2 text-xs text-ink-soft">{document.revision.metadata.model} · {document.revision.metadata.prompt_version} · {document.revision.metadata.processing_seconds}s. Model checks can miss errors; verify exact facts against originals. Saved evidence describes the first draft; user edits are not re-verified.</p>
    </details>
  </section>;
}
