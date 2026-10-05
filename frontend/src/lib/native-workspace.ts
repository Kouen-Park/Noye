import { invoke } from "@tauri-apps/api/core";

export interface WorkspaceLocations {
  original: string;
  current: string;
  previous: string | null;
}
export function readWorkspaceLocations() {
  return invoke<WorkspaceLocations>("workspace_locations");
}
export function openWorkspace(destination: string | null) {
  return invoke<void>("select_workspace", { destination, confirmed: true });
}
