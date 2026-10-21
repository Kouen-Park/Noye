import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, it, vi } from "vitest";
import { exportMarkdown, exportPdf } from "@/lib/native-export";
import { ExportControls } from "./export-controls";

vi.mock("@/lib/native-export", () => ({ exportMarkdown: vi.fn(), exportPdf: vi.fn() }));
beforeEach(() => vi.resetAllMocks());

it("keeps cancellation distinct from native saving and permits another export", async () => {
  vi.mocked(exportMarkdown).mockResolvedValueOnce("cancelled").mockResolvedValueOnce("saved");
  render(<ExportControls documentId="doc" title="Draft" content="한국어 -- unsaved" previewVisible />);
  await userEvent.click(screen.getByRole("link", { name: "Export .md" }));
  expect(await screen.findByRole("status")).toHaveTextContent("Markdown export cancelled.");
  await userEvent.click(screen.getByRole("link", { name: "Export .md" }));
  expect(await screen.findByRole("status")).toHaveTextContent("Markdown saved.");
  expect(exportMarkdown).toHaveBeenLastCalledWith("Draft", "한국어 -- unsaved");
});

it("keeps both exports unavailable during PDF saving, then allows cancellation and retry", async () => {
  let finish!: (result: "cancelled") => void;
  vi.mocked(exportPdf).mockReturnValueOnce(new Promise(resolve => { finish = resolve; }))
    .mockResolvedValueOnce("saved");
  render(<ExportControls documentId="doc" title="한국어 draft" content="unsaved" previewVisible />);
  await userEvent.click(screen.getByRole("button", { name: "Export PDF" }));
  expect(screen.getByRole("button", { name: "Export PDF" })).toBeDisabled();
  expect(screen.getByText("Exporting…")).toHaveAttribute("aria-disabled", "true");
  finish("cancelled");
  expect(await screen.findByRole("status")).toHaveTextContent("PDF export cancelled.");
  await userEvent.click(screen.getByRole("button", { name: "Export PDF" }));
  expect(await screen.findByRole("status")).toHaveTextContent("PDF saved.");
  expect(exportPdf).toHaveBeenCalledWith("한국어 draft");
});

it("retains the editor after a PDF error and permits Markdown export", async () => {
  vi.mocked(exportPdf).mockRejectedValueOnce("Could not render PDF.");
  vi.mocked(exportMarkdown).mockResolvedValue("saved");
  render(<ExportControls documentId="doc" content="literal 한국어 -- draft" previewVisible />);
  await userEvent.click(screen.getByRole("button", { name: "Export PDF" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Your editor text is preserved.");
  await userEvent.click(screen.getByRole("link", { name: "Export .md" }));
  expect(await screen.findByRole("status")).toHaveTextContent("Markdown saved.");
  expect(exportMarkdown).toHaveBeenCalledWith("document", "literal 한국어 -- draft");
});

it("reports a failed export, preserves the text and permits retry", async () => {
  vi.mocked(exportMarkdown).mockRejectedValueOnce("Choose a new filename.").mockResolvedValueOnce("saved");
  render(<ExportControls documentId="doc" content="saved and unsaved text" previewVisible />);
  await userEvent.click(screen.getByRole("link", { name: "Export .md" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Choose a new filename. Your editor text is preserved.");
  expect(screen.queryByRole("status")).not.toBeInTheDocument();
  await userEvent.click(screen.getByRole("link", { name: "Export .md" }));
  expect(await screen.findByRole("status")).toHaveTextContent("Markdown saved.");
  expect(screen.queryByRole("alert")).not.toBeInTheDocument();
});
