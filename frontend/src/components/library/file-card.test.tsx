import { render, screen } from "@testing-library/react";
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
