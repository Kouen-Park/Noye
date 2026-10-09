"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { MarkdownContent } from "@/components/documents/document-preview";
import { KnowledgeJobStages } from "@/components/knowledge-job-stages";
import { WikiEditor } from "@/components/wiki/wiki-editor";
import { ALL_WIKI_SOURCES, adoptWiki, generateWiki, listWiki, listWikiJobs, listWikiSources,
  readWiki, readWikiRevision, wikiJobAction, wikiOriginalUrl, wikiPreviewContent, wikiScopeFromUrl, wikiHref, wikiQueryHref, wikiLinkHref,
  type WikiJob, type WikiPage, type WikiRevision, type WikiScope, type WikiSource, type WikiSummary } from "@/lib/wiki";

const openStates = ["queued", "running", "cancelling"];
const button = "min-h-11 rounded-md border border-edge-strong px-3 text-sm hover:bg-sunken disabled:opacity-50";

export function WikiView() {
  const router = useRouter();
  const search = useSearchParams();
  const identifier = search.get("w");
  const urlScope = search.get("scope");
  const scope = useMemo(() => wikiScopeFromUrl(urlScope), [urlScope]);
  const scopeKey = JSON.stringify(scope);
  const activeScope = useRef<string | null>(null);
  const setScope = (scope: WikiScope) => router.push(wikiQueryHref(search.toString(), { scope }), { scroll: false });
  const chooseRevision = (revision: string | null) => router.push(wikiQueryHref(search.toString(), { revision }), { scroll: false });
  const [pages, setPages] = useState<WikiSummary[]>([]);
  const [sources, setSources] = useState<WikiSource[]>([]);
  const [jobs, setJobs] = useState<WikiJob[]>([]);
  const [error, setError] = useState<string | null>(null);
  const fail = useCallback((cause: unknown) => setError(cause instanceof Error ? cause.message : "Wiki request failed."), []);
  const refresh = useCallback(async (signal?: AbortSignal) => {
    if (activeScope.current !== scopeKey) return;
    try {
      const [pages, sources, jobs] = await Promise.all([listWiki(scope, signal), listWikiSources(signal), listWikiJobs(signal)]);
      if (!signal?.aborted && activeScope.current === scopeKey) { setPages(pages); setSources(sources); setJobs(jobs); setError(null); }
    } catch (cause) { if (!signal?.aborted && activeScope.current === scopeKey && !(cause instanceof DOMException && cause.name === "AbortError")) fail(cause); }
  }, [scope, scopeKey, fail]);
  useEffect(() => {
    activeScope.current = scopeKey;
    const controller = new AbortController();
    Promise.resolve().then(() => refresh(controller.signal));
    return () => { activeScope.current = null; controller.abort(); };
  }, [refresh, scopeKey]);
  useEffect(() => {
    if (!jobs.some(job => openStates.includes(job.state))) return;
    const controller = new AbortController();
    const interval = window.setInterval(() => void refresh(controller.signal), 2000);
    return () => { controller.abort(); window.clearInterval(interval); };
  }, [jobs, refresh]);
  async function run(action: () => Promise<unknown>) {
    setError(null);
    try { await action(); await refresh(); } catch (cause) { fail(cause); }
  }
  function sourceSelected(source: WikiSource) {
    return scope.mode === "all" || (scope.mode === "chosen" && (
      scope.source_ids.includes(source.source_id)
      || (source.root_id !== null && scope.root_ids.includes(source.root_id))));
  }
  function selectSource(source: WikiSource, selected: boolean) {
    const current = scope.mode === "all" ? sources.map(source => source.source_id)
      : scope.mode === "chosen" ? [...new Set([...scope.source_ids,
        ...sources.filter(sourceSelected).map(source => source.source_id)])] : [];
    const ids = selected ? [...new Set([...current, source.source_id])] : current.filter(id => id !== source.source_id);
    setScope({ mode: ids.length ? "chosen" : "empty", source_ids: ids, root_ids: [] });
  }
  return <div className="mt-5 space-y-5">
    {error && <p role="alert" className="rounded border border-fail bg-fail-wash p-3 text-fail">{error} <button className={button} onClick={() => void refresh()}>Retry loading</button></p>}
    <details className="rounded-lg border border-edge bg-card p-4">
      <summary className="cursor-pointer text-sm font-semibold">Originals & processing · local Ollama only</summary>
      <p className="mt-3 text-sm text-ink-soft">Choose the material used for summaries and related links. An empty selection reads no sources.</p>
      <label className="mt-3 block text-sm">Material scope<select aria-label="Material scope" value={scope.mode} onChange={e => setScope(e.target.value === "all" ? ALL_WIKI_SOURCES : { mode: "empty", source_ids: [], root_ids: [] })} className="ml-3 min-h-11 rounded border border-edge-strong bg-canvas px-3"><option value="all">All enabled originals</option><option value="empty">No originals</option><option value="chosen" disabled>Chosen originals</option></select></label>
      {sources.length === 0 && <p className="mt-3 text-sm">Connect a folder or upload PDF, Markdown or TXT.</p>}
      <ul className="mt-3 divide-y divide-edge">
        {sources.map(source => <li key={source.source_id} className="flex flex-wrap items-center gap-3 py-3">
          <label className="flex min-h-11 min-w-0 flex-1 items-center gap-3"><input type="checkbox" checked={sourceSelected(source)} onChange={e => selectSource(source, e.target.checked)} /><span className="break-all text-sm">{source.relative_path}<span className="block text-xs text-ink-soft">Source index: {source.processing_state} · {source.availability}</span>{source.error && <span className="block text-xs text-fail">{source.error}</span>}</span></label>
          <button className={button} disabled={!sourceSelected(source) || source.processing_state !== "READY" || source.availability !== "available"} onClick={() => void run(() => generateWiki(source.source_id, scope))}>Summarize locally</button>
        </li>)}
      </ul>
    </details>
    {jobs.length > 0 && <section aria-label="Wiki processing" className="rounded-lg border border-edge bg-card p-4"><h2 className="font-semibold">Wiki jobs</h2><ul className="mt-2 divide-y divide-edge">{jobs.slice(0, 12).map(job => <li key={job.id} className="flex flex-wrap items-center gap-3 py-2 text-sm"><div className="min-w-0 w-full flex-none sm:w-auto sm:flex-1" role="status">{sources.find(s => s.source_id === job.subject_id)?.name ?? "Wiki refresh"}: {job.state} · {job.stage}{job.total > 0 && ` · ${job.completed}/${job.total} batches`}{job.error && <span className="block text-fail">{job.error}</span>}<KnowledgeJobStages events={job.events} /></div>{job.artifact_id && <Link className={button} href={wikiHref(job.artifact_id, scope)}>Open Wiki</Link>}{openStates.includes(job.state) ? <button className={button} onClick={() => void run(() => wikiJobAction(job.id, "cancel"))}>Cancel</button> : ["failed", "interrupted", "cancelled"].includes(job.state) && <button className={button} onClick={() => void run(() => wikiJobAction(job.id, "resume"))}>Retry frozen sources</button>}</li>)}</ul></section>}
    <div className="grid gap-5 lg:grid-cols-[240px_minmax(0,1fr)]">
      <aside aria-label="Wiki pages" className="rounded-lg border border-edge bg-card p-3">
        <h2 className="px-2 font-semibold">Pages</h2>
        {pages.length === 0 && <p className="p-2 text-sm text-ink-soft">No Wiki pages in this scope yet.</p>}
        <ul>{pages.map(page => <li key={page.id}><Link href={wikiHref(page.id, scope)} aria-current={identifier === page.id ? "page" : undefined} className={`mt-1 block rounded p-2 text-sm ${identifier === page.id ? "bg-sunken" : "hover:bg-sunken"}`}><span className="break-words">{page.title}</span><span className="block text-xs text-ink-soft">{page.kind}{page.proposal_count > 0 && ` · ${page.proposal_count} proposals`}</span></Link></li>)}</ul>
      </aside>
      {identifier ? <WikiDetail key={identifier} identifier={identifier} requestedRevision={search.get("revision")} scope={scope} jobStates={jobs.map(j => `${j.id}:${j.state}`).join()} onRevision={chooseRevision} onSaved={() => void refresh()} /> : <p className="p-5 text-ink-soft">Open a source summary, concept, project or saved analysis.</p>}
    </div>
  </div>;
}

function WikiDetail({ identifier, requestedRevision, scope, jobStates, onRevision, onSaved }: { identifier: string; requestedRevision: string | null; scope: WikiScope; jobStates: string; onRevision: (revision: string | null) => void; onSaved: () => void }) {
  const [page, setPage] = useState<WikiPage | null>(null);
  const [historySelection, setHistorySelection] = useState<{ requested: string; revision: WikiRevision | null; scope: string; error: string | null } | null>(null);
  const scopeKey = JSON.stringify(scope);
  const selectionKey = JSON.stringify([identifier, scopeKey, requestedRevision]);
  const activeSelection = useRef<{ key: string } | null>(null);
  useEffect(() => { activeSelection.current = { key: selectionKey }; return () => { activeSelection.current = null; }; }, [selectionKey]);
  const selectedHistory = requestedRevision && historySelection?.scope === scopeKey && historySelection.requested === requestedRevision ? historySelection : null;
  const historical = selectedHistory?.revision ?? null;
  const [error, setError] = useState<string | null>(null);
  const visibleError = selectedHistory?.error ?? error;
  useEffect(() => {
    const controller = new AbortController();
    readWiki(identifier, scope, controller.signal).then(result => { if (!controller.signal.aborted) { setPage(result); setError(null); } }, cause => { if (!controller.signal.aborted) { setPage(null); setError(cause.message); } });
    return () => controller.abort();
  }, [identifier, jobStates, scope]);
  useEffect(() => {
    if (!requestedRevision) return;
    let cancelled = false;
    readWikiRevision(identifier, requestedRevision, scope).then(revision => {
      if (!cancelled) setHistorySelection({ requested: requestedRevision, revision, scope: scopeKey, error: null });
    }, cause => { if (!cancelled) setHistorySelection({ requested: requestedRevision, revision: null, scope: scopeKey, error: cause instanceof Error ? cause.message : "Could not open the revision." }); });
    return () => { cancelled = true; };
  }, [identifier, requestedRevision, scope, scopeKey]);
  async function adopt() {
    if (!historical || !page?.current_revision) return;
    const selection = activeSelection.current;
    try {
      const adopted = await adoptWiki(identifier, historical.id, page.current_revision, scope);
      if (activeSelection.current === selection) { setPage(adopted); onRevision(null); }
      onSaved();
    } catch (cause) { if (activeSelection.current === selection) setError(cause instanceof Error ? cause.message : "Could not adopt this proposal."); }
  }
  const revision = requestedRevision ? historical : page?.revision;
  if (revision && (scope.mode === "empty" || (scope.mode === "chosen" && !revision.evidence.every(e => scope.source_ids.includes(e.source.source_id) || (e.source.root_id !== null && scope.root_ids.includes(e.source.root_id)))))) return <p role="status">This Wiki page is outside the selected material scope.</p>;
  const visibleRelations = historical ? [] : page?.relations ?? [];
  return <div className="min-w-0 space-y-4">
    {visibleError && <p role="alert" className="text-fail">{visibleError}</p>}
    {page?.publication_error && <p role="status" className="text-fail">{page.publication_error}</p>}
    {requestedRevision && page?.revision && <button className={button} onClick={() => onRevision(null)}>Return to current</button>}
    {!revision ? <p role="status">{visibleError ? "No readable Wiki revision in this scope." : requestedRevision ? "Opening saved Wiki revision…" : page ? "No published revision yet. Check the Wiki job." : "Opening Wiki…"}</p> : <>
      <p className="text-sm text-ink-soft">{revision?.origin} revision · {revision?.metadata.model ?? "Maintained Wiki"}{revision?.metadata.processing_seconds !== undefined && ` · ${revision.metadata.processing_seconds.toFixed(1)}s`} · {revision?.metadata.prompt_version}<br />Wiki is interpretation. Verify exact facts, numbers and exceptions in originals.</p>
      {historical && <p role="status" className="text-sm text-ink-soft">Historical Wiki snapshot · {new Date(historical.created_at).toLocaleString()} · verify its saved source versions.</p>}
      {historical ? <section className="rounded-lg border border-edge bg-card p-5">{historical.origin === "proposal" && page?.current_revision && <button className={`${button} mb-4`} onClick={adopt}>Adopt proposal · keep history</button>}<MarkdownContent content={wikiPreviewContent(historical.content, historical.metadata.contributors, scope)} allowImages={false}
        rewriteLink={href => wikiLinkHref(href, scope, historical.metadata.contributors)} /></section> : page ? <WikiEditor key={`${page.id}:${scopeKey}`} page={page} scope={scope} onSaved={saved => { if (activeSelection.current?.key === selectionKey && saved.id === page.id) setPage(saved); onSaved(); }} /> : null}
      <details className="rounded-lg border border-edge bg-card p-4"><summary className="cursor-pointer font-semibold">Original evidence · {revision?.evidence.length ?? 0} passages</summary><ul className="mt-3 space-y-4">{revision?.evidence.map(e => <li key={e.id} className="border-t border-edge pt-3 text-sm"><p>{e.source.name}{e.page_number !== null && ` · page ${e.page_number}`} · {e.current_status}</p><p className="break-all font-mono text-xs text-ink-soft">Source {e.source.source_id} · version {e.source.source_version}<br />Passage {e.passage_index}, characters {e.start}–{e.end}</p><blockquote className="mt-2 whitespace-pre-wrap border-l-2 border-edge-strong pl-3">{e.text}</blockquote>{e.current_status === "available" && <a href={wikiOriginalUrl(e)} target="_blank" rel="noopener noreferrer" className="mt-2 inline-flex min-h-11 items-center text-accent-ink underline">Open original</a>}</li>)}</ul></details>
      <section className="rounded-lg border border-edge bg-card p-4"><h2 className="font-semibold">Relations & backlinks</h2>{visibleRelations.length === 0 && <p className="mt-2 text-sm text-ink-soft">No verified related pages.</p>}<ul className="mt-2 space-y-3">{visibleRelations.map(r => { const back = r.target_id === identifier; return <li key={r.id} className="text-sm"><Link href={wikiHref(back ? r.origin_id : r.target_id, scope, back ? r.revision_id : r.target_revision)} className="text-accent-ink underline">{back ? r.origin_title : r.target_title}</Link> · {r.kind.replaceAll("_", " ")}{back && " · backlink"}{r.target_current_revision && r.target_current_revision !== r.target_revision && " · earlier target revision"}<p className="text-ink-soft">{r.reason}</p></li>; })}</ul>{revision?.metadata.contributors?.map(c => <Link key={c.wiki_id} href={wikiHref(c.wiki_id, scope, c.revision_id)} className="mt-2 block text-sm text-accent-ink underline">Source summary · {c.wiki_id}</Link>)}</section>
      {page && <details className="rounded-lg border border-edge bg-card p-4"><summary className="cursor-pointer font-semibold">Revision history · {page.revisions.length}</summary><ul className="mt-2">{page.revisions.map(r => <li key={r.id}><button className={`${button} my-1 text-left`} onClick={() => onRevision(r.id)}>{r.origin} · {new Date(r.created_at).toLocaleString()} · {r.title}</button></li>)}</ul></details>}
    </>}
  </div>;
}
