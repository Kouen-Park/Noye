import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, it, vi } from "vitest";
import { WikiView } from "@/components/wiki/wiki-view";
import * as api from "@/lib/wiki";

vi.mock("@/lib/wiki", async importOriginal => ({ ...await importOriginal<typeof import("@/lib/wiki")>(), listWiki: vi.fn(), listWikiSources: vi.fn(), listWikiJobs: vi.fn(), generateWiki: vi.fn(), wikiJobAction: vi.fn() }));
const sources: api.WikiSource[] = ["one", "two"].map(id => ({ source_id: id, root_id: "root", relative_path: id + ".txt", name: id, version: "hash", availability: "available", processing_state: "READY", error: null }));
beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(api.listWiki).mockResolvedValue([]);
  vi.mocked(api.listWikiSources).mockResolvedValue(sources);
  vi.mocked(api.listWikiJobs).mockResolvedValue([]);
});

it("deselecting one source from all preserves the remaining chosen scope", async () => {
  render(<WikiView />);
  await screen.findByText("one.txt");
  const boxes = screen.getAllByRole("checkbox");
  await userEvent.click(boxes[0]);
  await waitFor(() => expect(api.listWiki).toHaveBeenLastCalledWith({ mode: "chosen", source_ids: ["two"], root_ids: [] }, expect.any(AbortSignal)));
  await userEvent.click(screen.getAllByRole("checkbox")[1]);
  await waitFor(() => expect(api.listWiki).toHaveBeenLastCalledWith({ mode: "empty", source_ids: [], root_ids: [] }, expect.any(AbortSignal)));
  expect(screen.getAllByRole("button", { name: "Summarize locally" }).every(button => button.hasAttribute("disabled"))).toBe(true);
});

it("shows source indexing failures separately from Wiki errors and offers explicit retry", async () => {
  vi.mocked(api.listWikiSources).mockResolvedValue([{ ...sources[0], processing_state: "FAILED", error: "Source extraction failed" }]);
  vi.mocked(api.listWikiJobs).mockResolvedValue([{ id: "job", kind: "wiki", subject_id: "one", state: "failed", stage: "summarizing", completed: 0, total: 1, error: "Ollama invalid JSON", artifact_id: null }]);
  render(<WikiView />);
  expect(await screen.findByText("Source extraction failed")).toBeInTheDocument();
  expect(await screen.findByText("Ollama invalid JSON")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Retry frozen sources" }));
  expect(api.wikiJobAction).toHaveBeenCalledWith("job", "resume");
  expect(screen.getByRole("button", { name: "Summarize locally" })).toBeDisabled();
});
