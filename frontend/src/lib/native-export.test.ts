import { beforeEach, expect, it, vi } from "vitest";
import { invoke } from "@tauri-apps/api/core";
import { isDesktopRuntime } from "./runtime";
import { exportMarkdown, exportPdf } from "./native-export";
import { downloadBackup } from "./workspace";
import type { AiSettings } from "./ai-settings";

vi.mock("@tauri-apps/api/core", () => ({ invoke: vi.fn() }));
vi.mock("./runtime", () => ({ isDesktopRuntime: vi.fn(), apiBaseUrl: () => "http://127.0.0.1:34567" }));
beforeEach(() => { vi.resetAllMocks(); vi.mocked(isDesktopRuntime).mockReturnValue(true); });

it("saves exact editor text through native selection without a destination or webview download", async () => {
  vi.mocked(invoke).mockResolvedValue(true);
  const text = '<!-- comment -->\n한국어 -- "quoted"\n';
  expect(await exportMarkdown("User writing", text)).toBe("saved");
  expect(invoke).toHaveBeenCalledWith("save_markdown", { title: "User writing", content: text });
});

it("saves a native PDF from the current webview without granting a JavaScript destination", async () => {
  vi.mocked(invoke).mockResolvedValueOnce(true).mockResolvedValueOnce(false);
  expect(await exportPdf("한국어 preview")).toBe("saved");
  expect(invoke).toHaveBeenCalledWith("save_pdf", { title: "한국어 preview" });
  expect(await exportPdf("한국어 preview")).toBe("cancelled");
});

it("keeps web PDF export on the browser print engine", async () => {
  vi.mocked(isDesktopRuntime).mockReturnValue(false);
  const print = vi.spyOn(window, "print").mockImplementation(() => {});
  expect(await exportPdf("Preview")).toBe("download");
  expect(print).toHaveBeenCalledOnce();
  expect(invoke).not.toHaveBeenCalled();
  print.mockRestore();
});

it("does not report a cancelled Markdown dialog as saved", async () => {
  vi.mocked(invoke).mockResolvedValue(false);
  expect(await exportMarkdown("Draft", "unsaved")).toBe("cancelled");
});

it("native backup does not fetch or copy ZIP bytes into JavaScript", async () => {
  const fetch = vi.spyOn(globalThis, "fetch");
  vi.mocked(invoke).mockResolvedValue(true);
  expect(await downloadBackup({ control_token: "synthetic" } as AiSettings)).toBe("saved");
  expect(invoke).toHaveBeenCalledWith("save_workspace_backup");
  expect(fetch).not.toHaveBeenCalled(); fetch.mockRestore();
});

it("retains native backup cancellation and errors for the settings flow", async () => {
  vi.mocked(invoke).mockResolvedValueOnce(false).mockRejectedValueOnce("Choose a new filename.");
  const settings = { control_token: "synthetic" } as AiSettings;
  expect(await downloadBackup(settings)).toBe("cancelled");
  await expect(downloadBackup(settings)).rejects.toBe("Choose a new filename.");
});
