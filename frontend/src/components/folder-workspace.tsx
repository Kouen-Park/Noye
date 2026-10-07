"use client";

import { useEffect, useState } from "react";
import { actOnJob, jobIsActive } from "@/lib/jobs";
import { isDesktopRuntime } from "@/lib/runtime";
import { chooseSourceFolder, folderRequest, revealFolder, revealSource,
  type FolderRoot, type FolderTree, type FolderEntry, type FilingRecord } from "@/lib/folders";

const actionClass = "min-h-11 rounded-md border border-edge-strong px-3 text-sm hover:bg-sunken disabled:opacity-50";

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
  return <div className="mt-6">
    <p className="max-w-[70ch] text-sm text-ink-soft">
      Connect an existing folder to keep its structure, or choose a managed knowledge folder.
      Noye detects PDF, Markdown and TXT changes while open and catches up on the next launch.
      Disconnecting preserves originals, saved evidence and writing.
    </p>
    <div className="mt-4 flex flex-wrap gap-2">
      <button className={actionClass} disabled={busy} onClick={() => void choose("connected")}>Connect existing folder</button>
      <button className={actionClass} disabled={busy} onClick={() => void choose("managed")}>Choose managed folder</button>
      <button className={actionClass} disabled={busy} onClick={reload}>Refresh folders</button>
    </div>
    {error && <p role="alert" className="mt-3 text-fail">{error}</p>}
    {!trees.length && !error && <p className="mt-6 text-ink-faint">No folders connected yet.</p>}
    <div className="mt-5 space-y-5">
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
  return <section className="rounded-lg border border-edge-strong bg-card p-4" aria-label={root.name}>
    <div className="flex flex-wrap items-start justify-between gap-3">
      <div><h2 className="text-lg font-semibold">{root.name}</h2>
        <p className="text-sm text-ink-soft">{root.kind === "managed" ? "Managed knowledge folder" : "Connected existing folder"}
          {" · "}{root.availability}{" · "}{root.processing ? "Processing enabled" : "Processing paused"}</p>
      </div>
      <div className="flex flex-wrap gap-2">
        <button className={actionClass} disabled={busy || !root.connected || root.availability !== "available"} onClick={() => void act(() => revealFolder(root.id))}>Open in Finder</button>
        {root.connected ? <>
          {root.availability === "unavailable" && <button className={actionClass} disabled={busy} onClick={() => void act(() => chooseSourceFolder(root.kind, root.id))}>Re-select folder</button>}
          <button className={actionClass} disabled={busy} onClick={() => void act(() => update({ processing: !root.processing }))}>
            {root.processing ? "Pause processing" : "Resume processing"}</button>
          <button className={actionClass} disabled={busy} onClick={() => void act(() => folderRequest(`/${root.id}/reconcile`, "POST"))}>Reconcile & recover</button>
          <button className={actionClass} disabled={busy} onClick={() => void act(() => update({ disconnect: true }))}>Disconnect</button>
        </> : <button className={actionClass} disabled={busy} onClick={() => void act(() => chooseSourceFolder(root.kind, root.id))}>Reconnect folder</button>}
      </div>
    </div>
    {root.error && <p className="mt-2 text-sm text-fail">{root.error}</p>}
    {error && <p role="alert" className="mt-2 text-fail">{error}</p>}
    <div className="my-4 border-y border-edge py-3 text-sm">
      <label className="flex min-h-11 items-center gap-2">
        <input type="checkbox" disabled={busy || !root.connected || (!root.organization_prefix && !area)}
          checked={!!root.organization_prefix} onChange={event => void act(() => update({ organization_prefix: event.target.checked ? area : null }))} />
        Allow automatic filing inside the selected subfolder
      </label>
      <label className="flex flex-wrap items-center gap-2">Organization area
        <select className="min-h-11 rounded border border-edge-strong bg-canvas px-2" value={area}
          disabled={busy || !!root.organization_prefix} onChange={event => setArea(event.target.value)}>
          <option value="">Choose a subfolder</option>
          {entries.filter(entry => entry.kind === "directory" && !entry.excluded && !entry.remembered).map(entry =>
            <option key={entry.relative_path} value={entry.relative_path}>{entry.relative_path}</option>)}
          {root.organization_prefix && !entries.some(entry => entry.relative_path === root.organization_prefix && !entry.remembered && !entry.excluded) &&
            <option value={root.organization_prefix}>{root.organization_prefix}</option>}
        </select>
      </label>
      <p className="mt-2 text-xs text-ink-faint">Filing stays inside this area, preserves original bytes and never overwrites a name collision. Wiki and generated documents are excluded from intake.</p>
    </div>
    <FolderBranch entries={entries} prefix="" busy={busy} act={act} root={root} />
    {filing.filter(record => record.state !== "complete").map(record => <p key={record.id} className="mt-2 text-sm text-fail">
      Filing {record.state}: {record.old_path} → {record.new_path}. {record.error}
    </p>)}
  </section>;
}

function FolderBranch({ entries, prefix, busy, act, root }: {
  entries: FolderEntry[]; prefix: string; busy: boolean; root: FolderRoot;
  act: (operation: () => Promise<unknown>) => Promise<void>;
}) {
  const children = entries.filter(entry => entry.relative_path.slice(0, entry.relative_path.lastIndexOf("/") + 1) === prefix);
  return <ul className="space-y-1 pl-3">
    {children.map(entry => entry.kind === "directory"
      ? <li key={entry.relative_path}><details open><summary className="min-h-8 cursor-pointer py-1 text-sm font-medium">{entry.relative_path.split("/").pop()}{entry.excluded && " · Excluded from intake"}{entry.remembered && " · Registered location"}</summary>
          <FolderBranch entries={entries} prefix={entry.relative_path + "/"} busy={busy} act={act} root={root} />
        </details></li>
      : <SourceRow key={entry.relative_path} entry={entry} root={root} busy={busy} act={act} />)}
    {!children.length && !prefix && <li className="py-2 text-sm text-ink-faint">No accessible source files. Check the connection or add files in Finder.</li>}
  </ul>;
}

function SourceRow({ entry, root, busy, act }: {
  entry: FolderEntry; root: FolderRoot; busy: boolean;
  act: (operation: () => Promise<unknown>) => Promise<void>;
}) {
  const source = entry.source;
  const [destination, setDestination] = useState("");
  const [filing, setFiling] = useState(false);
  return <li className="border-t border-edge py-2 text-sm">
    <div className="flex flex-wrap items-center gap-2">
      <span className="min-w-0 break-all font-medium">{entry.relative_path.split("/").pop()}</span>
      <span className="text-xs text-ink-soft">{source ? `${source.availability} · ${source.processing_state}` : entry.excluded ? "Excluded from intake" : "Waiting for discovery / unsupported format"}</span>
      {source && <>
        <button className={actionClass} disabled={busy || source.availability !== "available"} onClick={() => void act(() => revealSource(source.source_id))}>Finder</button>
        {source.job && (jobIsActive(source.job)
          ? <button className={actionClass} disabled={busy || source.job.state === "cancelling"} onClick={() => void act(() => actOnJob(source.job!.id, "cancel"))}>Cancel processing</button>
          : source.job.state !== "complete" && <button className={actionClass} disabled={busy || !root.processing || source.availability !== "available"} onClick={() => void act(() => actOnJob(source.job!.id, "resume"))}>Retry from original</button>)}
        {root.organization_prefix && <button className={actionClass} disabled={busy || source.availability !== "available"} onClick={() => setFiling(!filing)}>File manually</button>}
      </>}
    </div>
    {source?.job && source.job.total > 0 && <p className="mt-1 text-xs text-ink-soft">{source.job.stage} · {source.job.completed} / {source.job.total} · attempt {source.job.attempt}</p>}
    {source?.manual_category && <p className="mt-1 text-xs text-ink-soft">Manually fixed: {source.manual_category}</p>}
    {source?.error && <p className="mt-1 text-fail">{source.error}</p>}
    {filing && source && <form className="mt-2 flex flex-wrap gap-2" onSubmit={event => {
      event.preventDefault(); void act(() => folderRequest(`/${root.id}/file`, "POST", {
        source_id: source.source_id, destination, expected_version: source.version, manual: true,
      }));
    }}>
      <label className="flex items-center gap-2">Relative destination
        <input className="min-h-11 rounded border border-edge-strong bg-canvas px-2" value={destination} required
          placeholder={`${root.organization_prefix}/Topic/${source.name}`} onChange={event => setDestination(event.target.value)} />
      </label><button className={actionClass} disabled={busy}>Move original & fix category</button>
    </form>}
  </li>;
}
