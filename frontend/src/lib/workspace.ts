import { apiBaseUrl } from "./runtime";
import type { AiSettings } from "./ai-settings";

export interface WorkspaceInfo {
  directory: string;
  backup_format: number;
  restore_limit_bytes: number;
}
export interface RestoredWorkspace {
  destination: string;
  missing_sources: string[];
  rebuild_required: boolean;
  workspace_id: string;
  external_roots?: { id: string; name: string; availability: string }[];
  external_originals?: string;
  missing_knowledge_roots?: string[];
}

async function workspaceRequest(settings: AiSettings, path: string, options: RequestInit = {}) {
  const response = await fetch(apiBaseUrl() + "/workspace" + path, {
    ...options, headers: { "X-Noye-Control": settings.control_token, ...options.headers },
  });
  if (!response.ok) {
    const result = await response.json().catch(() => null);
    throw new Error(typeof result?.detail === "string" ? result.detail : "Workspace operation failed.");
  }
  return response;
}
export async function readWorkspace(settings: AiSettings, signal?: AbortSignal): Promise<WorkspaceInfo> {
  return (await workspaceRequest(settings, "", { signal })).json();
}
export async function downloadBackup(settings: AiSettings) {
  const response = await workspaceRequest(settings, "/backup", { method: "POST" });
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = "noye-workspace.noye.zip";
  document.body.appendChild(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 60_000);
}
export async function restoreWorkspace(settings: AiSettings, file: File): Promise<RestoredWorkspace> {
  const body = new FormData();
  body.append("file", file);
  return (await workspaceRequest(settings, "/restore", { method: "POST", body })).json();
}
