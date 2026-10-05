"use client";

import { useEffect, useState } from "react";
import { type StoredFile, listFiles } from "@/lib/api";

export function SourceSelector({ scope, onChange, disabled }: {
  scope: string[] | null; onChange: (ids: string[] | null) => void; disabled: boolean;
}) {
  const [files, setFiles] = useState<StoredFile[]>([]);
  const [error, setError] = useState(false);
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    listFiles(controller.signal).then((result) => {
      if (!controller.signal.aborted) { setFiles(result); setError(false); }
    }, () => { if (!controller.signal.aborted) setError(true); });
    return () => controller.abort();
  }, [attempt]);
  const unavailable = scope?.filter((id) => !files.some((file) => file.id === id)) ?? [];
  return <details className="mt-3 text-xs text-ink-soft">
    <summary className="min-h-11 cursor-pointer py-3 font-semibold">
      {scope === null ? "Search all ready files" : scope.length === 0 ? "No files selected" : `Search ${scope.length} selected files`}
    </summary>
    <fieldset disabled={disabled} className="max-h-56 overflow-y-auto rounded-md border border-edge-strong p-3">
      <legend className="sr-only">Files for this conversation</legend>
      <label className="flex min-h-11 items-center gap-2"><input type="checkbox" checked={scope === null}
        onChange={(event) => onChange(event.target.checked ? null : [])} />All ready files</label>
      {files.map((file) => <label key={file.id} className="flex min-h-11 items-center gap-2">
        <input type="checkbox" checked={scope?.includes(file.id) ?? false}
          onChange={(event) => onChange(event.target.checked ? [...(scope ?? []), file.id] : (scope ?? []).filter((id) => id !== file.id))} />
        <span>{file.name}{file.status !== "READY" ? ` · ${file.status.toLowerCase()}` : ""}</span>
      </label>)}
      {unavailable.map((id) => <label key={id} className="flex min-h-11 items-center gap-2">
        <input type="checkbox" checked onChange={() => onChange((scope ?? []).filter((selected) => selected !== id))} />Unavailable saved file ({id})
      </label>)}
      <p className="mt-2">Only selected files with a compatible, ready index are searched. An empty selection searches nothing.</p>
    </fieldset>
    {error && <p role="alert">Could not load files. <button type="button" className="min-h-11 underline" onClick={() => setAttempt((n) => n + 1)}>Retry files</button></p>}
  </details>;
}
