import type { WikiJob } from "./wiki";
import { invoke } from "@tauri-apps/api/core";
import { apiBaseUrl } from "./runtime";
import { readAiSettings } from "./ai-settings";
import type { IngestionJob } from "./jobs";

export interface FolderRoot {
  id: string; name: string; kind: "managed" | "connected";
  connected: number; processing: number; organization_prefix: string | null;
  availability: "available" | "unavailable" | "disconnected"; error: string | null;
  recovery_conflicts?: { relative_path: string; message: string }[];
}
export interface FolderSource {
  source_id: string; root_id: string; relative_path: string; name: string;
  version: string; availability: string; processing_state: string;
  error: string | null; manual_category: string | null; job: IngestionJob | null; knowledge_job?: WikiJob | null;
}
export interface FolderEntry {
  relative_path: string; kind: "directory" | "file"; source?: FolderSource | null; excluded?: boolean; remembered?: boolean;
  intake_error?: string | null;
}
export interface FolderTree { root: FolderRoot; entries: FolderEntry[] }
export interface FilingRecord {
  id: string; old_path: string; new_path: string; state: string; error: string | null;
}

export function chooseSourceFolder(kind: FolderRoot["kind"], rootId?: string) {
  return invoke<string | null>("choose_source_folder", { kind, rootId: rootId ?? null });
}
export function revealFolder(rootId: string) {
  return invoke<void>("reveal_source_folder", { rootId, sourceId: null });
}
export function revealSource(sourceId: string) {
  return invoke<void>("reveal_source_folder", { rootId: null, sourceId });
}
export async function folderRequest<T>(path = "", method = "GET", body?: object, signal?: AbortSignal): Promise<T> {
  const settings = await readAiSettings();
  const response = await fetch(apiBaseUrl() + "/folders" + path, { method, signal,
    headers: { "X-Noye-Control": settings.control_token, "Content-Type": "application/json" },
    ...(body ? { body: JSON.stringify(body) } : {}) });
  if (!response.ok) {
    const result = await response.json().catch(() => null);
    throw new Error(typeof result?.detail === "string" ? result.detail :
      result?.detail?.message ?? "Folder operation failed. Check permissions and try again.");
  }
  return response.json();
}
