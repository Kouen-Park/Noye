import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, it, vi } from "vitest";
import { FileCard } from "./file-card";
import type { StoredFile } from "@/lib/api";

const file: StoredFile = { id: "source-1", name: "notes.txt", file_type: "txt", size: 20,
  status: "FAILED", error: "Interrupted", page_count: null, chunk_count: 0,
  created_at: "2026-10-09T00:00:00Z", updated_at: "2026-10-09T00:00:00Z" };

it.each(["READY", "FAILED"] as const)("directs %s folder originals to Folders without impossible Remove or Retry", status => {
  const onRemove = vi.fn(), onRetry = vi.fn();
  render(<FileCard file={{ ...file, status, folder_root_id: "root-1" }}
    onRemove={onRemove} onRetry={onRetry} onCancel={vi.fn()} stopping={false} />);
  expect(screen.getByRole("link", { name: "Manage in Folders" })).toHaveAttribute("href", "/folders");
  expect(screen.queryByRole("button", { name: "Remove" })).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Retry" })).not.toBeInTheDocument();
  expect(screen.queryByText(/cannot be undone/)).not.toBeInTheDocument();
  expect(onRemove).not.toHaveBeenCalled(); expect(onRetry).not.toHaveBeenCalled();
});

it("keeps Stop available while a folder original is processing", async () => {
  const onCancel = vi.fn();
  render(<FileCard file={{ ...file, status: "EMBEDDING", folder_root_id: "root-1" }}
    onRemove={vi.fn()} onRetry={vi.fn()} onCancel={onCancel} stopping={false} />);
  await userEvent.click(screen.getByRole("button", { name: "Stop" }));
  expect(onCancel).toHaveBeenCalledWith("source-1");
});

it("preserves Retry and the destructive confirmation for independent uploads", async () => {
  const onRemove = vi.fn(), onRetry = vi.fn();
  render(<FileCard file={file} onRemove={onRemove} onRetry={onRetry} onCancel={vi.fn()} stopping={false} />);
  await userEvent.click(screen.getByRole("button", { name: "Retry" }));
  expect(onRetry).toHaveBeenCalledWith("source-1");
  await userEvent.click(screen.getByRole("button", { name: "Remove" }));
  expect(onRemove).not.toHaveBeenCalled();
  expect(screen.getByText(/This cannot be undone/)).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Remove" }));
  expect(onRemove).toHaveBeenCalledWith("source-1");
});

it("keeps failures visible while Details changes only disclosure state", async () => {
  const onRemove = vi.fn(), onRetry = vi.fn(), onCancel = vi.fn();
  render(<FileCard file={file} onRemove={onRemove} onRetry={onRetry} onCancel={onCancel} stopping={false} />);
  const details = screen.getByRole("button", { name: "Details for notes.txt" });
  expect(details).toHaveAttribute("aria-expanded", "false");
  expect(screen.getByText("Interrupted")).toBeVisible();
  expect(screen.getByText(/Independent upload/)).not.toBeVisible();
  await userEvent.click(details);
  expect(screen.getByText(/Independent upload/)).toBeVisible();
  await userEvent.click(details);
  expect(screen.getByText("Interrupted")).toBeVisible();
  expect(onRemove).not.toHaveBeenCalled(); expect(onRetry).not.toHaveBeenCalled(); expect(onCancel).not.toHaveBeenCalled();
});

it("keeps removal confirmation through Details toggles and returns focus on Keep", async () => {
  const onRemove = vi.fn();
  render(<FileCard file={file} onRemove={onRemove} onRetry={vi.fn()} onCancel={vi.fn()} stopping={false} />);
  const remove = screen.getByRole("button", { name: "Remove" });
  await userEvent.click(remove);
  await userEvent.click(screen.getByRole("button", { name: "Details for notes.txt" }));
  expect(screen.getByText(/This cannot be undone/)).toBeVisible();
  await userEvent.click(screen.getByRole("button", { name: "Keep" }));
  await waitFor(() => expect(remove).toHaveFocus());
  expect(onRemove).not.toHaveBeenCalled();
});

it("shows the extraction warning before Details and reveals actual page numbers", async () => {
  render(<FileCard file={{ ...file, status: "READY", file_type: "pdf", error: null,
    page_count: 4, extracted_page_count: 2, no_text_pages: [2, 4] }}
    onRemove={vi.fn()} onRetry={vi.fn()} onCancel={vi.fn()} stopping={false} />);
  expect(screen.getByText(/2 pages have no extracted text/)).toBeVisible();
  expect(screen.getByText(/Pages: 2, 4/)).not.toBeVisible();
  await userEvent.click(screen.getByRole("button", { name: "Details for notes.txt" }));
  expect(screen.getByText(/Pages: 2, 4/)).toBeVisible();
  expect(screen.queryByText(/verified/i)).not.toBeInTheDocument();
});
