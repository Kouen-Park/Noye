import { apiBaseUrl } from "@/lib/runtime";

export interface IngestionJob {
  id: string;
  file_id: string;
  file_name: string;
  state: "queued" | "running" | "cancelling" | "complete" | "failed" | "cancelled" | "interrupted";
  stage: string;
  completed: number;
  total: number;
  attempt: number;
  error: string | null;
}

export function jobIsActive(job: IngestionJob) {
  return ["queued", "running", "cancelling"].includes(job.state);
}

export async function readJobs(signal?: AbortSignal): Promise<IngestionJob[]> {
  const response = await fetch((await apiBaseUrl()) + "/jobs", { signal });
  if (!response.ok) throw new Error("Could not load processing jobs. Refresh to try again.");
  return response.json();
}

export async function actOnJob(id: string, action: "cancel" | "resume") {
  const response = await fetch((await apiBaseUrl()) + "/jobs/" + encodeURIComponent(id) + "/" + action,
    { method: "POST" });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.detail ?? "Could not update this job. Refresh to try again.");
  }
}
