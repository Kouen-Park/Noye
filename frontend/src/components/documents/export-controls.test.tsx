import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, it, vi } from "vitest";
import { exportMarkdown } from "@/lib/native-export";
import { ExportControls } from "./export-controls";

vi.mock("@/lib/native-export", () => ({ exportMarkdown: vi.fn() }));
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
