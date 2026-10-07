import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, it, vi } from "vitest";
import { WikiView } from "@/components/wiki/wiki-view";
import * as api from "@/lib/wiki";

const query = vi.hoisted(() => ({ value: "" }));
vi.mock("next/navigation", () => ({ useSearchParams: () => new URLSearchParams(query.value) }));
vi.mock("@/lib/wiki", async importOriginal => ({ ...await importOriginal<typeof import("@/lib/wiki")>(), listWiki: vi.fn(), listWikiSources: vi.fn(), listWikiJobs: vi.fn(), readWiki: vi.fn(), readWikiRevision: vi.fn(), generateWiki: vi.fn(), wikiJobAction: vi.fn() }));
const sources: api.WikiSource[] = ["one", "two"].map(id => ({ source_id: id, root_id: "root", relative_path: id + ".txt", name: id, version: "hash", availability: "available", processing_state: "READY", error: null }));
beforeEach(() => {
  vi.clearAllMocks();
  query.value = "";
  vi.mocked(api.listWiki).mockResolvedValue([]);
  vi.mocked(api.listWikiSources).mockResolvedValue(sources);
  vi.mocked(api.listWikiJobs).mockResolvedValue([]);
});

it("closes historical content when the material scope changes", async () => {
  query.value = "w=wiki";
  const revision: api.WikiRevision = { id: "current", wiki_id: "wiki", parent_id: null, origin: "generated", title: "Notes", content: "Current summary", created_at: "2026-10-07", evidence: [], metadata: {} };
  const old = { ...revision, id: "old", content: "Historical broader material" };
  vi.mocked(api.readWiki).mockResolvedValue({ id: "wiki", title: "Notes", kind: "source", current_revision: "current", publication_error: null, updated_at: "2026-10-07", proposal_count: 0, revision, revisions: [old], relations: [] });
  vi.mocked(api.readWikiRevision).mockResolvedValue(old);
  render(<WikiView />);
  await userEvent.click(await screen.findByRole("button", { name: /generated.*Notes/ }));
  expect(await screen.findByText("Historical broader material")).toBeInTheDocument();
  await userEvent.click(screen.getAllByRole("checkbox")[1]);
  await waitFor(() => expect(screen.queryByText("Historical broader material")).not.toBeInTheDocument());
  expect(screen.queryByRole("button", { name: "Return to current" })).not.toBeInTheDocument();
});

it("carries scope in page, artifact, contributor and relation links for new tabs", async () => {
  const scope = { mode: "chosen", source_ids: ["one"], root_ids: [] };
  query.value = `w=wiki&scope=${encodeURIComponent(JSON.stringify(scope))}`;
  const revision: api.WikiRevision = { id: "current", wiki_id: "wiki", parent_id: null, origin: "generated", title: "Notes", content: "Current summary", created_at: "2026-10-07", evidence: [], metadata: { contributors: [{ wiki_id: "basis", revision_id: "basis-revision" }] } };
  const page: api.WikiPage = { id: "wiki", title: "Notes", kind: "source", current_revision: "current", publication_error: null, updated_at: "2026-10-07", proposal_count: 0, revision, revisions: [], relations: [{ id: "edge", origin_id: "wiki", target_id: "target", origin_title: "Notes", target_title: "Related", kind: "shared_subject", reason: "Same evidence", target_revision: "target-revision" }] };
  vi.mocked(api.listWiki).mockResolvedValue([page]);
  vi.mocked(api.readWiki).mockResolvedValue(page);
  vi.mocked(api.listWikiJobs).mockResolvedValue([{ id: "job", kind: "wiki", subject_id: "one", state: "complete", stage: "complete", completed: 1, total: 1, error: null, artifact_id: "wiki" }]);
  render(<WikiView />);
  await screen.findByRole("link", { name: "Related" });
  for (const name of [/Notes\s*source/, "Open Wiki", "Related", "Source summary · basis"]) {
    const href = (await screen.findByRole("link", { name })).getAttribute("href")!;
    expect(JSON.parse(new URL(href, "http://localhost").searchParams.get("scope")!)).toEqual(scope);
  }
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


it("resolves a changed URL scope once without repeated refreshes", async () => {
  const { rerender } = render(<WikiView />);
  await screen.findByText("one.txt");
  const chosen = { mode: "chosen", source_ids: ["one"], root_ids: [] };
  query.value = `scope=${encodeURIComponent(JSON.stringify(chosen))}`;
  rerender(<WikiView />);
  await waitFor(() => expect(api.listWiki).toHaveBeenLastCalledWith(chosen, expect.any(AbortSignal)));
  const count = vi.mocked(api.listWiki).mock.calls.length;
  rerender(<WikiView />);
  await waitFor(() => expect(screen.getAllByRole("checkbox")[1]).not.toBeChecked());
  expect(api.listWiki).toHaveBeenCalledTimes(count);
  query.value = "scope=" + encodeURIComponent(JSON.stringify({ mode: "empty", source_ids: [], root_ids: [] }));
  rerender(<WikiView />);
  await waitFor(() => expect(api.listWiki).toHaveBeenLastCalledWith({ mode: "empty", source_ids: [], root_ids: [] }, expect.any(AbortSignal)));
});

it("opens an allowed saved revision when the current Wiki has expanded outside scope", async () => {
  const scope = { mode: "chosen", source_ids: ["one"], root_ids: [] };
  query.value = `w=wiki&revision=saved&scope=${encodeURIComponent(JSON.stringify(scope))}`;
  vi.mocked(api.readWiki).mockRejectedValue(new Error("Current Wiki is outside the selected material scope."));
  const evidence: api.WikiEvidence = { id: "e1", source: { source_id: "one", root_id: "root", name: "one.txt",
    source_hash: "saved-hash", source_version: "saved-hash", relative_path: "one.txt" },
    page_number: null, passage_index: 0, start: 0, end: 13, text: "Saved original", current_status: "stale" };
  vi.mocked(api.readWikiRevision).mockResolvedValue({ id: "saved", wiki_id: "wiki", parent_id: null,
    origin: "generated", title: "Saved notes", content: "Saved scoped interpretation", created_at: "2026-10-07",
    evidence: [evidence], metadata: {} });
  render(<WikiView />);
  expect(await screen.findByText("Saved scoped interpretation")).toBeInTheDocument();
  expect(screen.getByText(/Historical Wiki snapshot/)).toBeInTheDocument();
  expect(screen.getByText("Saved original")).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Return to current" })).not.toBeInTheDocument();
  expect(screen.queryByText("Opening Wiki…")).not.toBeInTheDocument();
});
