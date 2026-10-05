"use client";

import { useEffect, useId, useState } from "react";

import type { AiSettings } from "@/lib/ai-settings";
import { openWorkspace, readWorkspaceLocations, type WorkspaceLocations } from "@/lib/native-workspace";
import { downloadBackup, readWorkspace, restoreWorkspace, type RestoredWorkspace, type WorkspaceInfo } from "@/lib/workspace";

const button = "min-h-11 rounded-md border border-edge-strong px-4 py-2 text-sm font-semibold disabled:opacity-50";

export function WorkspaceSettings({ settings }: { settings: AiSettings }) {
  const id = useId();
  const [workspace, setWorkspace] = useState<WorkspaceInfo | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState<"backup" | "restore" | null>(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [restored, setRestored] = useState<RestoredWorkspace | null>(null);
  const [locations, setLocations] = useState<WorkspaceLocations | null>(null);
  const [selected, setSelected] = useState<string | null | undefined>(undefined);
  const [confirmed, setConfirmed] = useState(false);
  const [switching, setSwitching] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    readWorkspace(settings, controller.signal).then(setWorkspace).catch((cause) => {
      if (!controller.signal.aborted) setError(cause instanceof Error ? cause.message : "Could not read workspace.");
    });
    readWorkspaceLocations().then((value) => {
      if (!controller.signal.aborted) setLocations(value);
    }).catch(() => { /* Native selection is unavailable in the web client. */ });
    return () => controller.abort();
  }, [settings]);

  async function act(kind: "backup" | "restore") {
    setBusy(kind); setError(""); setNotice("");
    try {
      if (kind === "backup") {
        await downloadBackup(settings);
        setNotice("Backup download prepared. Keep the archive in a safe place.");
      } else if (file) {
        setRestored(await restoreWorkspace(settings, file));
        setNotice("Backup verified and restored into a new folder. Your current workspace is unchanged.");
      }
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not complete this operation.");
    } finally { setBusy(null); }
  }

  async function switchWorkspace() {
    if (selected === undefined || !confirmed) return;
    setSwitching(true); setError("");
    try { await openWorkspace(selected); }
    catch (cause) {
      setError(cause instanceof Error ? cause.message : String(cause));
      setSwitching(false);
    }
  }

  return <section aria-label="Workspace backup and restore" className="space-y-6">
    <div><h3 className="text-lg text-ink-display">Workspace data</h3>
      <p className="mt-2 break-all font-mono text-xs text-ink-soft">{workspace?.directory ?? "Reading workspace…"}</p>
    </div>
    {error && <p role="alert" className="text-sm text-fail">{error}</p>}
    {notice && <p role="status" className="text-sm text-ink-soft">{notice}</p>}
    <div className="border-t border-edge-strong pt-5"><h3 className="text-lg text-ink-display">Back up saved work</h3>
      <p className="mt-2 text-sm text-ink-soft">Includes originals, conversations, edited documents and saved excerpts. API keys, models and the rebuildable vector index are excluded.</p>
      <p className="mt-2 text-sm text-ink-soft">Finish processing and save your document edits first. Unsaved text is not included.</p>
      <button className={button + " mt-3"} disabled={busy !== null || !workspace} onClick={() => void act("backup")}>{busy === "backup" ? "Preparing backup…" : "Download workspace backup"}</button>
    </div>
    <div className="border-t border-edge-strong pt-5"><h3 className="text-lg text-ink-display">Restore a backup</h3>
      <p className="mt-2 text-sm text-ink-soft">Restores into a new folder after checking every file and the database. Existing folders are never overwritten. Search needs an explicit index rebuild.</p>
      <label htmlFor={id + "-backup"} className="mt-3 block text-sm font-semibold">Workspace backup file</label>
      <input id={id + "-backup"} type="file" accept=".zip" disabled={busy !== null} className="mt-2 block max-w-full text-sm" onChange={(event) => { setFile(event.target.files?.[0] ?? null); setRestored(null); }} />
      <button className={button + " mt-3"} disabled={busy !== null || !file} onClick={() => void act("restore")}>{busy === "restore" ? "Verifying and restoring…" : "Restore into a new folder"}</button>
      {restored && <div className="mt-4 rounded-md border border-edge-strong bg-card p-4">
        <p className="text-sm font-semibold">Verified restored workspace</p>
        <p className="mt-2 break-all font-mono text-xs">{restored.destination}</p>
        <p className="mt-2 text-sm text-ink-soft">{restored.missing_sources.length ? restored.missing_sources.length + " originals were missing from the backup. Saved conversations and documents remain available." : "Originals, saved conversations and documents are ready. Rebuild the index before searching."}</p>
        <p className="mt-2 text-sm text-ink-soft">Your current workspace stays open.</p>
        <button className={button + " mt-3"} disabled={busy !== null || switching}
          onClick={() => { setSelected(restored.destination); setConfirmed(false); }}>
          Open restored workspace
        </button>
      </div>}
    </div>
    {locations && locations.current !== locations.original && <div className="border-t border-edge-strong pt-5">
      <h3 className="text-lg text-ink-display">Other saved workspaces</h3>
      <button className={button + " mt-3"} disabled={switching}
        onClick={() => { setSelected(null); setConfirmed(false); }}>Reopen original workspace</button>
      {locations.previous && locations.previous !== locations.original && locations.previous !== locations.current &&
        <button className={button + " ml-2 mt-3"} disabled={switching}
          onClick={() => { setSelected(locations.previous); setConfirmed(false); }}>Reopen previous workspace</button>}
    </div>}
    {selected !== undefined && <div className="rounded-md border border-edge-strong bg-card p-4">
      <h3 className="font-semibold">Switch workspace and restart Noye</h3>
      <p className="mt-2 break-all text-sm">{selected ?? locations?.original ?? "Original workspace"}</p>
      <p className="mt-2 text-sm text-ink-soft">
        Save document edits first. Unsaved text will close. Active processing stops;
        unfinished jobs will offer a retry. Both workspace folders remain on disk.
      </p>
      <label className="mt-3 flex items-start gap-2 text-sm"><input type="checkbox" checked={confirmed}
        disabled={switching} onChange={(event) => setConfirmed(event.target.checked)} />
        I saved my edits and want to restart in this workspace.</label>
      <button className={button + " mt-3"} disabled={!confirmed || switching}
        onClick={() => void switchWorkspace()}>{switching ? "Restarting Noye…" : "Confirm switch and restart"}</button>
      <button className={button + " ml-2 mt-3"} disabled={switching}
        onClick={() => setSelected(undefined)}>Keep current workspace</button>
    </div>}
  </section>;
}
