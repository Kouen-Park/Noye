import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, it, vi } from "vitest";
import { SourceSelector } from "@/components/chat/source-selector";
import { listFiles } from "@/lib/api";
vi.mock("@/lib/api", async (original) => ({ ...await original<typeof import("@/lib/api")>(), listFiles: vi.fn() }));
beforeEach(() => vi.mocked(listFiles).mockResolvedValue([
  { id: "a", name: "Notes.md", status: "READY", file_type: "md", size: 1, error: null,
    page_count: null, chunk_count: 1, created_at: "now", updated_at: "now" },
]));
it("distinguishes all files from an explicitly empty selection", async () => {
  const change = vi.fn();
  render(<SourceSelector scope={null} onChange={change} disabled={false} />);
  await screen.findByText("Notes.md");
  await userEvent.click(screen.getByText("Search all ready files"));
  await userEvent.click(screen.getByRole("checkbox", { name: "All ready files" }));
  expect(change).toHaveBeenCalledWith([]);
  await userEvent.click(screen.getByRole("checkbox", { name: "Notes.md" }));
  expect(change).toHaveBeenLastCalledWith(["a"]);
});
it("retains missing saved selections until the user removes them", async () => {
  const change = vi.fn();
  render(<SourceSelector scope={["missing"]} onChange={change} disabled={false} />);
  await screen.findByText("Notes.md");
  await userEvent.click(screen.getByText("Search 1 selected files"));
  const missing = screen.getByRole("checkbox", { name: /Unavailable saved file/ });
  expect(missing).toBeChecked();
  expect(screen.getByRole("checkbox", { name: "All ready files" })).not.toBeChecked();
  await userEvent.click(missing);
  expect(change).toHaveBeenCalledWith([]);
});
