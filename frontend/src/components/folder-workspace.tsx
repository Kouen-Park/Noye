"use client";

import { useEffect, useId, useState } from "react";
import Link from "next/link";
import { KnowledgeJobStages } from "@/components/knowledge-job-stages";
import { wikiJobAction, wikiHref } from "@/lib/wiki";
import { reingestFile } from "@/lib/api";
import { actOnJob, jobIsActive } from "@/lib/jobs";
import { isDesktopRuntime } from "@/lib/runtime";
import { chooseSourceFolder, folderRequest, revealFolder, revealSource,
  type FolderRoot, type FolderTree, type FolderEntry, type FilingRecord } from "@/lib/folders";

const actionClass = "noye-button text-ink-soft";

export function FolderWorkspace() {
  const [trees, setTrees] = useState<FolderTree[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [revision, setRevision] = useState(0);
  const reload = () => setRevision(value => value + 1);
  useEffect(() => {
    if (!isDesktopRuntime()) return;
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout>;
    async function load() {
      try {
        const roots = await folderRequest<FolderRoot[]>("", "GET", undefined, controller.signal);
        const latest = await Promise.all(roots.map(root => folderRequest<FolderTree>(
          "/" + encodeURIComponent(root.id) + "/tree", "GET", undefined, controller.signal)));
        if (!controller.signal.aborted) { setTrees(latest); setError(null); }
      } catch (caught) {
        if (!controller.signal.aborted) setError((caught as Error).message);
      } finally {
        if (!controller.signal.aborted) timer = setTimeout(load, 3000);
      }
    }
    void load();
    return () => { controller.abort(); clearTimeout(timer); };
  }, [revision]);
  async function choose(kind: FolderRoot["kind"]) {
    setBusy(true); setError(null);
    try { await chooseSourceFolder(kind); reload(); }
    catch (caught) { setError((caught as Error).message); }
    finally { setBusy(false); }
  }
  if (!isDesktopRuntime()) return <p className="mt-5 text-ink-soft">
    Folder connections are available in the macOS desktop app. Uploads remain available in Library.
  </p>;
  return <div>
    <p className="max-w-[70ch] text-sm text-ink-soft">
      PDF, Markdown and TXT changes are detected while Noye is open.
      <span className="block text-[12px]">Disconnecting preserves originals, saved evidence and writing.</span>
    </p>
    <div className="mt-3 flex flex-wrap items-center gap-2">
      <button className={actionClass} disabled={busy} onClick={() => void choose("connected")}>Connect existing folder</button>
      <button className={actionClass} disabled={busy} onClick={() => void choose("managed")}>Choose managed folder</button>
      <button className={actionClass} disabled={busy} onClick={reload}>Refresh folders</button>
    </div>
    {error && <p role="alert" className="mt-3 text-fail">{error}</p>}
    {!trees.length && !error && <p className="mt-5 text-[13px] text-ink-soft">No folders connected yet.</p>}
    <div className="mt-4 divide-y divide-edge">
      {trees.map(tree => <RootCard key={tree.root.id} tree={tree} onChange={reload} />)}
    </div>
  </div>;
}

function RootCard({ tree, onChange }: { tree: FolderTree; onChange: () => void }) {
  const { root, entries } = tree;
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [area, setArea] = useState(root.organization_prefix ?? "");
  const [filing, setFiling] = useState<FilingRecord[]>([]);
  async function act(operation: () => Promise<unknown>) {
    setBusy(true); setError(null);
    try { await operation(); onChange(); }
    catch (caught) { setError((caught as Error).message); }
    finally { setBusy(false); }
  }
  useEffect(() => {
    const controller = new AbortController();
    void folderRequest<FilingRecord[]>(`/${encodeURIComponent(root.id)}/filing`, "GET", undefined, controller.signal)
      .then(value => { if (!controller.signal.aborted) setFiling(value); })
      .catch(() => { /* Folder errors are reported by the parent request. */ });
    return () => controller.abort();
  }, [root.id, entries]);
  const update = (body: object) => folderRequest(`/${encodeURIComponent(root.id)}`, "PATCH", body);
  return <section className="py-4" aria-label={root.name}>
    <div className="flex flex-wrap items-center justify-between gap-2">
      <div className="min-w-0"><h2 className="text-[14px] font-semibold">{root.name}</h2>
        <p className="mt-0.5 text-[12px] text-ink-soft">{root.kind === "managed" ? "Managed knowledge folder" : "Connected existing folder"}
          {" · "}{root.availability}{" · "}{!root.connected ? "Processing inactive" : root.processing ? "Processing enabled" : "Processing paused"}</p>
        {root.organization_prefix && <p className="text-[12px] text-ink-soft">Automatic filing: {root.organization_prefix}</p>}
      </div>
      <div className="flex flex-wrap gap-1">
        <button className={actionClass} disabled={busy || !root.connected || root.availability !== "available"} onClick={() => void act(() => revealFolder(root.id))}>Open in Finder</button>
        {root.connected ? <>
          {root.availability === "unavailable" && <button className={actionClass} disabled={busy} onClick={() => void act(() => chooseSourceFolder(root.kind, root.id))}>Re-select folder</button>}
          <button className={actionClass} disabled={busy} onClick={() => void act(() => update({ processing: !root.processing }))}>
            {root.processing ? "Pause processing" : "Resume processing"}</button>
        </> : <button className={actionClass} disabled={busy} onClick={() => void act(() => chooseSourceFolder(root.kind, root.id))}>Reconnect folder</button>}
      </div>
    </div>
    {root.error && <p role="alert" className="mt-2 text-[13px] text-fail">{root.error}</p>}
    {!!root.recovery_conflicts?.length && <div role="alert" className="mt-3 border-l-2 border-fail pl-3 text-[13px]">
      <p className="font-semibold">Recovered writing needs review</p>
      <ul className="mt-1 space-y-1">{root.recovery_conflicts.map(issue => <li key={issue.relative_path}>
        {issue.relative_path && <strong className="break-all">{issue.relative_path}: </strong>}{issue.message}
      </li>)}</ul>
      <p className="mt-1 text-[12px] text-ink-soft">Acknowledging hides this warning and keeps both versions.</p>
      <button className={actionClass + " mt-1"} disabled={busy} onClick={() => void act(() => update({ acknowledge_recovery_conflicts: true }))}>Acknowledge recovery conflicts</button>
    </div>}
    {error && <p role="alert" className="mt-2 text-[13px] text-fail">{error}</p>}
    <details className="noye-details my-2 text-[13px]">
      <summary className="cursor-pointer text-ink-soft" aria-label={`Folder options for ${root.name}`}>Folder options</summary>
      <div className="mt-2 border-l-2 border-edge pl-3">
        <div className="mb-2 flex flex-wrap gap-1">
          <button className={actionClass} disabled={busy || !root.connected} onClick={() => void act(() => folderRequest(`/${root.id}/reconcile`, "POST"))}>Reconcile & recover</button>
          {root.connected && <button className={actionClass} disabled={busy} onClick={() => void act(() => update({ disconnect: true }))}>Disconnect</button>}
        </div>
        <label className="flex min-h-8 items-center gap-2">
          <input type="checkbox" disabled={busy || !root.connected || (!root.organization_prefix && !area)}
            checked={!!root.organization_prefix} onChange={event => void act(() => update({ organization_prefix: event.target.checked ? area : null }))} />
          Allow automatic filing inside the selected subfolder
        </label>
        <label className="flex flex-wrap items-center gap-2">Organization area
          <select className="min-h-8 rounded border border-edge-strong bg-canvas px-2" value={area}
            disabled={busy || !!root.organization_prefix} onChange={event => setArea(event.target.value)}>
            <option value="">Choose a subfolder</option>
            {entries.filter(entry => entry.kind === "directory" && !entry.excluded && !entry.remembered).map(entry =>
              <option key={entry.relative_path} value={entry.relative_path}>{entry.relative_path}</option>)}
            {root.organization_prefix && !entries.some(entry => entry.relative_path === root.organization_prefix && !entry.remembered && !entry.excluded) &&
              <option value={root.organization_prefix}>{root.organization_prefix}</option>}
          </select>
        </label>
        <p className="mt-2 max-w-[75ch] text-[12px] text-ink-soft">Filing stays inside this area, preserves original bytes and never overwrites a name collision. Wiki and generated documents are excluded from intake.</p>
        <p className="mt-1 text-[12px] text-ink-soft">Pause a folder to remove derived indexes. Delete physical originals separately in Finder.</p>
      </div>
    </details>
    <FolderBranch entries={entries} prefix="" busy={busy} act={act} root={root} />
    {filing.filter(record => record.state !== "complete").map(record => <p key={record.id} role="alert" className="mt-2 text-[13px] text-fail">
      Filing {record.state}: {record.old_path} → {record.new_path}. {record.error}
    </p>)}
  </section>;
}

function FolderBranch({ entries, prefix, busy, act, root }: {
  entries: FolderEntry[]; prefix: string; busy: boolean; root: FolderRoot;
  act: (operation: () => Promise<unknown>) => Promise<void>;
}) {
  const children = entries.filter(entry => entry.relative_path.slice(0, entry.relative_path.lastIndexOf("/") + 1) === prefix);
  return <ul className={prefix ? "border-l border-edge pl-3" : ""}>
    {children.map(entry => entry.kind === "directory"
      ? <li key={entry.relative_path}><details open><summary className="min-h-8 cursor-pointer py-1 text-[13px] font-medium">{entry.relative_path.split("/").pop()}{entry.excluded && " · Excluded from intake"}{entry.remembered && " · Registered location"}</summary>
          <FolderBranch entries={entries} prefix={entry.relative_path + "/"} busy={busy} act={act} root={root} />
        </details></li>
      : <SourceRow key={entry.relative_path} entry={entry} root={root} busy={busy} act={act} />)}
    {!children.length && !prefix && <li className="py-2 text-[13px] text-ink-soft">No accessible source files. Check the connection or add files in Finder.</li>}
  </ul>;
}

function SourceRow({ entry, root, busy, act }: {
  entry: FolderEntry; root: FolderRoot; busy: boolean;
  act: (operation: () => Promise<unknown>) => Promise<void>;
}) {
  const source = entry.source;
  const [destination, setDestination] = useState("");
  const [filing, setFiling] = useState(false);
  const [detailsOpen, setDetailsOpen] = useState(false);
  const detailsId = useId();
  const knowledge = source?.knowledge_job;
  return <li className="border-t border-edge py-2 text-[13px]">
    <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
      <span className="min-w-0 basis-full break-words font-medium [overflow-wrap:anywhere] sm:flex-1 sm:basis-0">{entry.relative_path.split("/").pop()}</span>
      <span className="text-[12px] text-ink-soft">{entry.intake_error ? "Discovery failed" : source ? `${source.availability} · ${source.processing_state.toLowerCase()}` : entry.excluded ? "Excluded from intake" : "Waiting for discovery / unsupported format"}</span>
      {source && <>
        <button className={actionClass} disabled={busy || source.availability !== "available"} onClick={() => void act(() => revealSource(source.source_id))}>Finder</button>
        {source.job && (jobIsActive(source.job)
          ? <button className={actionClass} disabled={busy || source.job.state === "cancelling"} onClick={() => void act(() => actOnJob(source.job!.id, "cancel"))}>Cancel processing</button>
          : source.job.state !== "complete" && <button className={actionClass} disabled={busy || !root.processing || source.availability !== "available"} onClick={() => void act(() => actOnJob(source.job!.id, "resume"))}>Retry from original</button>)}
        {source.processing_state === "FAILED" && source.job?.state === "complete" && <button className={actionClass} disabled={busy || !root.connected || !root.processing || source.availability !== "available"} onClick={() => void act(() => reingestFile(source.source_id))}>Rebuild from original</button>}
      </>}
      <button type="button" className={actionClass} aria-expanded={detailsOpen} aria-controls={detailsId}
        aria-label={`Source details for ${entry.relative_path}`} onClick={() => setDetailsOpen(value => !value)}>Details</button>
    </div>
    {entry.intake_error && <p role="alert" className="mt-1 text-[12px] text-fail"><span className="break-all">{entry.relative_path}</span>: {entry.intake_error}</p>}
    {source?.error && !entry.intake_error && <p className="mt-1 text-[12px] text-fail">{source.error}</p>}
    {source?.job && source.job.state !== "complete" && source.job.total > 0 && <p className="mt-1 text-[12px] text-ink-soft">{source.job.stage} · {source.job.completed} / {source.job.total} · attempt {source.job.attempt}</p>}
    {knowledge && <div className="mt-1 text-[12px]" aria-label="Source knowledge processing">
      <div className="flex flex-wrap items-center gap-1">
        {knowledge.state !== "complete" && <span className="mr-auto text-ink-soft">Local knowledge · {knowledge.state} · {knowledge.stage}</span>}
        {knowledge.artifact_id && <Link className={actionClass + " inline-flex items-center"} href={wikiHref(knowledge.artifact_id, { mode: "chosen", root_ids: [root.id], source_ids: [] })}>Open Wiki</Link>}
        {["queued", "running", "cancelling"].includes(knowledge.state)
          ? <button className={actionClass} disabled={busy || knowledge.state === "cancelling"} onClick={() => void act(() => wikiJobAction(knowledge.id, "cancel"))}>Cancel knowledge job</button>
          : ["failed", "interrupted", "cancelled"].includes(knowledge.state) && <button className={actionClass} disabled={busy || !root.connected || !root.processing} onClick={() => void act(() => wikiJobAction(knowledge.id, "resume"))}>Retry knowledge stages</button>}
      </div>
      {knowledge.error && <p className="mt-1 text-fail">{knowledge.error}</p>}
    </div>}
    <div id={detailsId} hidden={!detailsOpen} className="mt-2 border-l-2 border-edge pl-3 text-[12px] text-ink-soft">
      <p className="break-all">{entry.relative_path}</p>
      {source?.manual_category && <p className="mt-1">Manually fixed: {source.manual_category}</p>}
      {knowledge && <KnowledgeJobStages events={knowledge.events} jobState={knowledge.state} currentStage={knowledge.stage} />}
      {source && <div className="mt-1 flex flex-wrap gap-1">
        {!root.processing && <button className={actionClass} disabled={busy} onClick={() => void act(() => folderRequest(`/${root.id}/sources/${source.source_id}/remove-derived`, "POST"))}>Remove derived indexes</button>}
        {root.organization_prefix && <button className={actionClass} disabled={busy || source.availability !== "available"} onClick={() => setFiling(!filing)}>File manually</button>}
      </div>}
      {filing && source && <form className="mt-2 flex flex-wrap gap-2" onSubmit={event => {
        event.preventDefault(); void act(() => folderRequest(`/${root.id}/file`, "POST", {
          source_id: source.source_id, destination, expected_version: source.version, manual: true,
        }));
      }}>
        <label className="flex min-w-0 flex-wrap items-center gap-2">Relative destination
          <input className="min-h-8 max-w-full rounded border border-edge-strong bg-canvas px-2" value={destination} required
            placeholder={`${root.organization_prefix}/Topic/${source.name}`} onChange={event => setDestination(event.target.value)} />
        </label><button className={actionClass} disabled={busy}>Move original & fix category</button>
      </form>}
    </div>
  </li>;
}
