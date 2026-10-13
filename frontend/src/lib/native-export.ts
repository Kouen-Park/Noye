import { invoke } from "@tauri-apps/api/core";
import { isDesktopRuntime } from "./runtime";

export type ExportResult = "saved" | "download" | "cancelled";

export async function exportMarkdown(title: string, content: string): Promise<ExportResult> {
  if (isDesktopRuntime()) {
    return await invoke<boolean>("save_markdown", { title, content }) ? "saved" : "cancelled";
  }
  const url = URL.createObjectURL(new Blob([content], { type: "text/markdown;charset=utf-8" }));
  const link = document.createElement("a");
  link.href = url;
  link.download = `${title.replace(/[\\/:\x00-\x1f]/g, "").trim() || "document"}.md`;
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
  return "download";
}
