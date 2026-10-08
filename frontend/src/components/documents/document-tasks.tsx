"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { type CoverageSource, type DocumentTask, listDocumentTasks } from "@/lib/source-documents";
import { wikiJobAction } from "@/lib/wiki";

const active = new Set(["queued", "running", "cancelling"]);
export function DocumentTasks({ conversationId }: { conversationId: string | null }) {
  const [tasks, setTasks] = useState<DocumentTask[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [refresh, setRefresh] = useState(0);
  useEffect(() => {
    if (!conversationId) return;
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout>;
    const load = async () => {
      try {
        const result = await listDocumentTasks(conversationId, controller.signal);
        if (controller.signal.aborted) return;
        setTasks(result); setError(null);
        timer = setTimeout(load, result.some(t => t.job && active.has(t.job.state)) ? 2000 : 10000);
      } catch (cause) {
        if (controller.signal.aborted) return;
        setError(cause instanceof Error ? cause.message : "Could not read document progress.");
        timer = setTimeout(load, 10000);
      }
    };
    void load();
    return () => { controller.abort(); clearTimeout(timer); };
  }, [conversationId, refresh]);
  const action = async (id: string, kind: "cancel" | "resume") => {
    try { await wikiJobAction(id, kind); setRefresh(n => n + 1); }
    catch (cause) { setError(cause instanceof Error ? cause.message : "Could not update document job."); }
  };
  return <section aria-label="Document artifacts" className="space-y-3">
    {error && <p role="alert" className="text-sm text-fail">{error}</p>}
    {tasks.map(({ job, request }) => <article key={request.id} className="rounded-lg border border-edge-strong bg-card p-4">
      <p className="text-xs font-semibold text-brand">Source document · Local Ollama</p>
      <h2 className="mt-2 text-base">{request.request.instruction}</h2>
      <p role="status" className="mt-2 text-sm text-ink-soft">{job?.state ?? "Not queued"} · {job?.stage}
        {job && job.total > 0 ? ` · ${job.completed}/${job.total}` : ""}</p>
      <p className="mt-1 text-xs text-ink-soft">Inventory fixed at start: {request.manifest.length} sources.
        {request.plan ? ` Selected: ${request.plan.selected_ids.length}.` : job && active.has(job.state) ? " Discovering relevant sources…" : " Selection not completed."}</p>
      <details className="mt-2 text-xs text-ink-soft"><summary className="min-h-11 cursor-pointer">Sources and coverage</summary>
        <ul className="space-y-2">{((request.report.sources ?? request.manifest) as Partial<CoverageSource>[]).map(source => <li key={source.source_id}>
          {source.relative_path} · {source.state ? `${source.state} · ${source.characters_processed}/${source.characters_read} characters` : "pending"}
          {"reason" in source && source.reason ? ` · ${source.reason}` : ""}
        </li>)}</ul>
      </details>
      {request.report.partial && <p className="text-sm text-ink-soft">Partial result: some material or conclusions remain unresolved. See the document and coverage.</p>}
      {!!request.report.presentation_limits?.length && <ul aria-label="Document structure and language limits" className="mt-1 list-disc pl-5 text-xs text-ink-soft">{request.report.presentation_limits.map((limit, n) => <li key={`${limit.code}-${n}`}>{limit.reason}</li>)}</ul>}
      {(request.clarification || job?.error) && <p role="alert" className="mt-2 text-sm text-fail">{request.clarification ?? job?.error}</p>}
      {request.clarification && <p className="mt-1 text-xs text-ink-soft">Clarify the request or choose sources, then submit a new document request.</p>}
      <div className="mt-2 flex flex-wrap gap-3 text-sm">
        {request.artifact_id && <><Link className="inline-flex min-h-11 items-center font-semibold text-brand underline" href={`/documents?d=${encodeURIComponent(request.artifact_id)}`}>Open document</Link>
          <Link className="inline-flex min-h-11 items-center text-brand underline" href={`/documents?d=${encodeURIComponent(request.artifact_id)}&export=1`}>Edit and export</Link></>}
        {job && active.has(job.state) && <button className="min-h-11 underline" type="button" disabled={job.state === "cancelling"} onClick={() => void action(job.id, "cancel")}>Cancel document job</button>}
        {job && !request.clarification && ["failed", "interrupted", "cancelled"].includes(job.state) && <button className="min-h-11 underline" type="button" onClick={() => void action(job.id, "resume")}>Retry frozen request</button>}
      </div>
      {job && active.has(job.state) && <p className="mt-2 text-xs text-ink-soft">Cancellation is checked between model calls. The current local call may finish first.</p>}
      {request.artifact_id && <p className="mt-1 text-xs text-ink-soft">Saved independently of this chat. PDF export completes separately in the print dialog.</p>}
    </article>)}
  </section>;
}
