"use client";

import { useEffect, useState } from "react";
import { actOnJob, jobIsActive, readJobs, type IngestionJob } from "@/lib/jobs";

export function JobsPanel({ revision, onChange }: { revision: string; onChange: () => void }) {
  const [jobs, setJobs] = useState<IngestionJob[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [refresh, setRefresh] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout>;
    async function load() {
      try {
        const latest = await readJobs(controller.signal);
        if (controller.signal.aborted) return;
        setJobs(latest);
        setError(null);
        if (latest.some(jobIsActive)) timer = setTimeout(load, 1500);
      } catch (caught) {
        if (!controller.signal.aborted) setError((caught as Error).message);
      }
    }
    void load();
    return () => { controller.abort(); clearTimeout(timer); };
  }, [revision, refresh]);

  async function act(job: IngestionJob, action: "cancel" | "resume") {
    setBusy(job.id);
    setError(null);
    try {
      await actOnJob(job.id, action);
      setRefresh((value) => value + 1);
      onChange();
    } catch (caught) { setError((caught as Error).message); }
    finally { setBusy(null); }
  }
  const visible = jobs.filter((job) => job.state !== "complete");
  if (!visible.length && !error) return null;
  return (
    <section className="mt-5 rounded-lg border border-edge bg-card p-4" aria-label="Processing jobs">
      <h2 className="font-semibold">Processing jobs</h2>
      <p className="mt-1 text-[13px] text-ink-soft">
        Progress is saved between embedding batches. Interrupted jobs wait for your retry,
        which processes the original again. Noye runs one file at a time.
      </p>
      {error && <div role="alert" className="mt-2 text-fail">{error}
        <button type="button" className="ml-3 underline" onClick={() => setRefresh((v) => v + 1)}>
          Refresh jobs
        </button>
      </div>}
      <ul className="mt-3 space-y-3">
        {visible.map((job) => (
          <li key={job.id} className="border-t border-edge pt-2 text-[13px]">
            <strong>{job.file_name}</strong> · attempt {job.attempt} · {job.state}
            <p className="text-ink-soft">{job.stage}
              {job.total > 0 && " · " + job.completed + " / " + job.total + " passages embedded"}
            </p>
            {job.error && <p className="text-fail">{job.error}</p>}
            {jobIsActive(job)
              ? <button type="button" className="mt-1 underline" disabled={busy === job.id || job.state === "cancelling"}
                  onClick={() => void act(job, "cancel")}>
                  {job.state === "cancelling" ? "Stopping after the current batch…" : "Stop processing"}
                </button>
              : <button type="button" className="mt-1 underline" disabled={busy === job.id}
                  onClick={() => void act(job, "resume")}>Retry from original</button>}
          </li>
        ))}
      </ul>
    </section>
  );
}
