import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, it, vi } from "vitest";
import { WikiView } from "@/components/wiki/wiki-view";
import * as api from "@/lib/wiki";

const query = vi.hoisted(() => ({ value: "", listeners: new Set<() => void>(), push: vi.fn() }));
vi.mock("next/navigation", async () => {
  const { useSyncExternalStore } = await import("react");
  return {
    useSearchParams: () => new URLSearchParams(useSyncExternalStore(listener => {
      query.listeners.add(listener); return () => { query.listeners.delete(listener); };
    }, () => query.value, () => query.value)),
    useRouter: () => ({ push: query.push }),
  };
});
vi.mock("@/lib/wiki", async importOriginal => ({ ...await importOriginal<typeof import("@/lib/wiki")>(), listWiki: vi.fn(), listWikiSources: vi.fn(), listWikiJobs: vi.fn(), readWiki: vi.fn(), readWikiRevision: vi.fn(), adoptWiki: vi.fn(), generateWiki: vi.fn(), wikiJobAction: vi.fn() }));
const sources: api.WikiSource[] = ["one", "two"].map(id => ({ source_id: id, root_id: "root", relative_path: id + ".txt", name: id, version: "hash", availability: "available", processing_state: "READY", error: null }));
const currentRevision: api.WikiRevision = { id: "current", wiki_id: "wiki", parent_id: null, origin: "generated", title: "Notes", content: "Current saved content", created_at: "2026-10-07", evidence: [], metadata: {} };
const currentPage: api.WikiPage = { id: "wiki", title: "Notes", kind: "source", current_revision: "current", publication_error: null, updated_at: "2026-10-07", proposal_count: 0, revision: currentRevision, revisions: [], relations: [] };
function deferred<T>() { let resolve!: (value: T) => void; let reject!: (reason: Error) => void; const promise = new Promise<T>((r, j) => { resolve = r; reject = j; }); return { promise, resolve, reject }; }
beforeEach(() => {
  vi.clearAllMocks();
  localStorage.clear();
  query.value = "";
  query.push.mockImplementation((href: string) => {
    query.value = new URL(href, "http://localhost").search.slice(1);
    query.listeners.forEach(listener => listener());
  });
  vi.mocked(api.listWiki).mockResolvedValue([]);
  vi.mocked(api.listWikiSources).mockResolvedValue(sources);
  vi.mocked(api.listWikiJobs).mockResolvedValue([]);
});

it("rechecks the selected historical revision after the material scope changes", async () => {
  query.value = "w=wiki";
  const revision: api.WikiRevision = { id: "current", wiki_id: "wiki", parent_id: null, origin: "generated", title: "Notes", content: "Current summary", created_at: "2026-10-07", evidence: [], metadata: {} };
  const old = { ...revision, id: "old", content: "Historical broader material", evidence: [{
    id: "e", source: { source_id: "two", root_id: "root", name: "two.txt", source_hash: "hash", source_version: "hash", relative_path: "two.txt" },
    page_number: null, passage_index: 0, start: 0, end: 1, text: "Excluded original", current_status: "available",
  }] };
  vi.mocked(api.readWiki).mockResolvedValue({ id: "wiki", title: "Notes", kind: "source", current_revision: "current", publication_error: null, updated_at: "2026-10-07", proposal_count: 0, revision, revisions: [old], relations: [] });
  vi.mocked(api.readWikiRevision).mockResolvedValue(old);
  render(<WikiView />);
  await userEvent.click(await screen.findByRole("button", { name: /generated.*Notes/ }));
  expect(await screen.findByText("Historical broader material")).toBeInTheDocument();
  await userEvent.click(screen.getAllByRole("checkbox")[1]);
  await waitFor(() => expect(screen.queryByText("Historical broader material")).not.toBeInTheDocument());
  expect(new URLSearchParams(query.value).get("revision")).toBe("old");
  expect(api.readWikiRevision).toHaveBeenLastCalledWith("wiki", "old", { mode: "chosen", source_ids: ["one"], root_ids: [] });
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

it("opens historical contributor references at their saved revision and selected scope", async () => {
  const scope = { mode: "chosen", source_ids: ["one"], root_ids: [] };
  query.value = `w=wiki&revision=saved&scope=${encodeURIComponent(JSON.stringify(scope))}`;
  const revision: api.WikiRevision = { id: "current", wiki_id: "wiki", parent_id: null, origin: "generated",
    title: "Notes", content: "Current summary", created_at: "2026-10-08", evidence: [], metadata: {} };
  vi.mocked(api.readWiki).mockResolvedValue({ id: "wiki", title: "Notes", kind: "project", current_revision: "current",
    publication_error: null, updated_at: "2026-10-08", proposal_count: 0, revision, revisions: [], relations: [] });
  vi.mocked(api.readWikiRevision).mockResolvedValue({ ...revision, id: "saved",
    content: "[Historical basis](../sources/basis.md)",
    metadata: { contributors: [{ wiki_id: "basis", revision_id: "basis-saved" }] } });
  render(<WikiView />);
  for (const name of ["Historical basis", "Source summary · basis"]) {
    const link = await screen.findByRole("link", { name });
    const target = new URL(link.getAttribute("href")!, "http://localhost");
    expect(target.searchParams.get("revision")).toBe("basis-saved");
    expect(JSON.parse(target.searchParams.get("scope")!)).toEqual(scope);
  }
});

it("opens relation and backlink references at the revisions that established them", async () => {
  const scope = { mode: "chosen", source_ids: ["one"], root_ids: [] };
  query.value = `w=wiki&scope=${encodeURIComponent(JSON.stringify(scope))}`;
  const revision: api.WikiRevision = { id: "current", wiki_id: "wiki", parent_id: null, origin: "generated",
    title: "Notes", content: "Current summary", created_at: "2026-10-08", evidence: [], metadata: {} };
  vi.mocked(api.readWiki).mockResolvedValue({ id: "wiki", title: "Notes", kind: "source", current_revision: "current",
    publication_error: null, updated_at: "2026-10-08", proposal_count: 0, revision, revisions: [], relations: [
      { id: "forward", origin_id: "wiki", target_id: "other", origin_title: "Notes", target_title: "Related earlier",
        kind: "shared_subject", reason: "Saved comparison", target_revision: "other-saved", target_current_revision: "other-new", revision_id: "current" },
      { id: "back", origin_id: "origin", target_id: "wiki", origin_title: "Origin", target_title: "Notes",
        kind: "shared_subject", reason: "Saved backlink", target_revision: "current", revision_id: "origin-saved" },
    ] });
  render(<WikiView />);
  for (const [name, expected] of [["Related earlier", "other-saved"], ["Origin", "origin-saved"]]) {
    const target = new URL((await screen.findByRole("link", { name })).getAttribute("href")!, "http://localhost");
    expect(target.searchParams.get("revision")).toBe(expected);
    expect(JSON.parse(target.searchParams.get("scope")!)).toEqual(scope);
  }
});

it("preserves the union of chosen roots and explicit sources when narrowing a folder scope", async () => {
  const scope = { mode: "chosen", source_ids: ["three"], root_ids: ["root"] };
  query.value = `scope=${encodeURIComponent(JSON.stringify(scope))}`;
  vi.mocked(api.listWikiSources).mockResolvedValue([...sources,
    { ...sources[0], source_id: "three", root_id: "another", relative_path: "three.txt" },
    { ...sources[0], source_id: "four", root_id: "outside", relative_path: "four.txt" }]);
  render(<WikiView />);
  await screen.findByText("four.txt");
  const boxes = screen.getAllByRole("checkbox");
  expect(boxes[0]).toBeChecked(); expect(boxes[1]).toBeChecked(); expect(boxes[2]).toBeChecked();
  expect(boxes[3]).not.toBeChecked();
  expect(screen.getAllByRole("button", { name: "Summarize locally" })[0]).toBeEnabled();
  await userEvent.click(boxes[0]);
  await waitFor(() => expect(api.listWiki).toHaveBeenLastCalledWith({
    mode: "chosen", source_ids: ["three", "two"], root_ids: [],
  }, expect.any(AbortSignal)));
  expect(screen.getAllByRole("checkbox")[1]).toBeChecked();
  expect(screen.getAllByRole("checkbox")[3]).not.toBeChecked();
});

it("does not select or summarize leftover IDs in an explicitly empty scope", async () => {
  query.value = `scope=${encodeURIComponent(JSON.stringify({ mode: "empty", source_ids: ["one"], root_ids: ["root"] }))}`;
  render(<WikiView />);
  await screen.findByText("one.txt");
  expect(screen.getAllByRole("checkbox").every(box => !(box as HTMLInputElement).checked)).toBe(true);
  expect(screen.getAllByRole("button", { name: "Summarize locally" }).every(button => button.hasAttribute("disabled"))).toBe(true);
});

it("keeps historical and current content aligned with URL navigation in both directions", async () => {
  const scope = { mode: "chosen", source_ids: ["one"], root_ids: [] };
  const currentUrl = `w=wiki&scope=${encodeURIComponent(JSON.stringify(scope))}&filter=notes`;
  query.value = currentUrl;
  const historical = { ...currentRevision, id: "saved", content: "Historical saved content" };
  vi.mocked(api.readWiki).mockResolvedValue({ ...currentPage, revisions: [historical] });
  vi.mocked(api.readWikiRevision).mockResolvedValue(historical);
  const view = render(<WikiView />);
  expect(await screen.findByText("Current saved content")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: /generated.*Notes/ }));
  expect(await screen.findByText("Historical saved content")).toBeInTheDocument();
  const historicalUrl = query.value;
  expect(new URLSearchParams(historicalUrl).get("revision")).toBe("saved");
  expect(query.push).toHaveBeenLastCalledWith(expect.stringContaining("revision=saved"), { scroll: false });
  await userEvent.click(screen.getByRole("button", { name: "Return to current" }));
  expect(new URLSearchParams(query.value).get("revision")).toBeNull();
  expect(new URLSearchParams(query.value).get("w")).toBe("wiki");
  expect(new URLSearchParams(query.value).get("filter")).toBe("notes");
  expect(api.wikiScopeFromUrl(new URLSearchParams(query.value).get("scope"))).toEqual(scope);
  expect(await screen.findByText("Current saved content")).toBeInTheDocument();
  expect(screen.queryByText("Historical saved content")).not.toBeInTheDocument();
  // App Router search params deliver the browser's Back/Forward locations without remounting this page.
  query.value = historicalUrl; view.rerender(<WikiView />);
  await waitFor(() => expect(screen.getByText("Historical saved content")).toBeInTheDocument());
  query.value = currentUrl; view.rerender(<WikiView />);
  await waitFor(() => expect(screen.getByText("Current saved content")).toBeInTheDocument());
  expect(screen.queryByText("Historical saved content")).not.toBeInTheDocument();
});

it("ignores a historical read that finishes after the revision is removed from the URL", async () => {
  query.value = "w=wiki&revision=slow";
  const pending = deferred<api.WikiRevision>();
  vi.mocked(api.readWiki).mockResolvedValue(currentPage);
  vi.mocked(api.readWikiRevision).mockReturnValue(pending.promise);
  const view = render(<WikiView />);
  await screen.findByRole("button", { name: "Return to current" });
  expect(screen.queryByText("Current saved content")).not.toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Return to current" }));
  expect(await screen.findByText("Current saved content")).toBeInTheDocument();
  await act(async () => pending.resolve({ ...currentRevision, id: "slow", content: "Late historical content" }));
  view.rerender(<WikiView />);
  expect(screen.queryByText("Late historical content")).not.toBeInTheDocument();
});

it("offers the current revision after a selected historical read fails", async () => {
  query.value = "w=wiki&revision=missing";
  vi.mocked(api.readWiki).mockResolvedValue(currentPage);
  vi.mocked(api.readWikiRevision).mockRejectedValue(new Error("Revision is unavailable"));
  render(<WikiView />);
  expect(await screen.findByText("Revision is unavailable")).toBeInTheDocument();
  expect(screen.queryByText("Current saved content")).not.toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Return to current" }));
  expect(await screen.findByText("Current saved content")).toBeInTheDocument();
  expect(screen.queryByText("Revision is unavailable")).not.toBeInTheDocument();
});

it("persists checkbox and material scope changes in the URL across reload", async () => {
  query.value = "w=wiki&revision=saved&filter=notes";
  vi.mocked(api.readWiki).mockResolvedValue(currentPage);
  vi.mocked(api.readWikiRevision).mockResolvedValue({ ...currentRevision, id: "saved" });
  const first = render(<WikiView />);
  await screen.findByText("one.txt");
  await userEvent.click(screen.getAllByRole("checkbox")[0]);
  const chosen = { mode: "chosen", source_ids: ["two"], root_ids: [] };
  let params = new URLSearchParams(query.value);
  expect(api.wikiScopeFromUrl(params.get("scope"))).toEqual(chosen);
  expect(params.get("w")).toBe("wiki"); expect(params.get("revision")).toBe("saved"); expect(params.get("filter")).toBe("notes");
  first.unmount();
  render(<WikiView />);
  await screen.findByText("one.txt");
  expect(screen.getAllByRole("checkbox")[0]).not.toBeChecked();
  expect(screen.getAllByRole("checkbox")[1]).toBeChecked();
  await userEvent.selectOptions(screen.getByRole("combobox", { name: "Material scope" }), "empty");
  params = new URLSearchParams(query.value);
  expect(api.wikiScopeFromUrl(params.get("scope"))).toEqual({ mode: "empty", source_ids: [], root_ids: [] });
  expect(params.get("w")).toBe("wiki"); expect(params.get("revision")).toBe("saved");
  await userEvent.selectOptions(screen.getByRole("combobox", { name: "Material scope" }), "all");
  expect(api.wikiScopeFromUrl(new URLSearchParams(query.value).get("scope"))).toEqual(api.ALL_WIKI_SOURCES);
});

it("does not install an obsolete scope list when its request finishes later", async () => {
  const pending = deferred<api.WikiSummary[]>();
  vi.mocked(api.listWiki).mockReturnValueOnce(pending.promise).mockResolvedValue([]);
  render(<WikiView />);
  await waitFor(() => expect(api.listWiki).toHaveBeenCalledOnce());
  act(() => { query.value = `scope=${encodeURIComponent(JSON.stringify({ mode: "empty", source_ids: [], root_ids: [] }))}`; query.listeners.forEach(listener => listener()); });
  await waitFor(() => expect(api.listWiki).toHaveBeenCalledTimes(2));
  await act(async () => pending.resolve([{ ...currentPage, title: "Outside old scope" }]));
  expect(screen.queryByRole("link", { name: /Outside old scope/ })).not.toBeInTheDocument();
  expect(screen.getByText("No Wiki pages in this scope yet.")).toBeInTheDocument();
});

it("ignores a current page read that succeeds after its scope was aborted", async () => {
  query.value = "w=wiki";
  const pending = deferred<api.WikiPage>();
  vi.mocked(api.readWiki).mockReturnValueOnce(pending.promise).mockResolvedValue({ ...currentPage, revision: { ...currentRevision, content: "Chosen current content" } });
  render(<WikiView />);
  await screen.findByText("two.txt");
  const oldSignal = vi.mocked(api.readWiki).mock.calls[0][2]!;
  await userEvent.click(screen.getAllByRole("checkbox")[1]);
  expect(await screen.findByText("Chosen current content")).toBeInTheDocument();
  expect(oldSignal.aborted).toBe(true);
  await act(async () => pending.resolve(currentPage));
  expect(screen.getByText("Chosen current content")).toBeInTheDocument();
  expect(screen.queryByText("Current saved content")).not.toBeInTheDocument();
});

it("ignores a historical read failure after its revision is removed from the URL", async () => {
  query.value = "w=wiki&revision=slow";
  const pending = deferred<api.WikiRevision>();
  vi.mocked(api.readWiki).mockResolvedValue(currentPage);
  vi.mocked(api.readWikiRevision).mockReturnValue(pending.promise);
  render(<WikiView />);
  await userEvent.click(await screen.findByRole("button", { name: "Return to current" }));
  expect(await screen.findByText("Current saved content")).toBeInTheDocument();
  await act(async () => pending.reject(new Error("Obsolete historical read failed")));
  expect(screen.queryByText("Obsolete historical read failed")).not.toBeInTheDocument();
  expect(screen.queryByRole("alert")).not.toBeInTheDocument();
});

it("does not return to an old Wiki or broaden scope after a late proposal adoption", async () => {
  query.value = "w=wiki&revision=proposal";
  const pending = deferred<api.WikiPage>();
  vi.mocked(api.readWiki).mockImplementation(async id => id === "wiki" ? currentPage : { ...currentPage, id, revision: { ...currentRevision, wiki_id: id, content: "Another scoped Wiki" } });
  vi.mocked(api.readWikiRevision).mockResolvedValue({ ...currentRevision, id: "proposal", origin: "proposal" });
  vi.mocked(api.adoptWiki).mockReturnValue(pending.promise);
  render(<WikiView />);
  await userEvent.click(await screen.findByRole("button", { name: "Adopt proposal · keep history" }));
  const chosen: api.WikiScope = { mode: "chosen", source_ids: ["one"], root_ids: [] };
  const nextUrl = api.wikiHref("another", chosen);
  act(() => query.push(nextUrl));
  expect(await screen.findByText("Another scoped Wiki")).toBeInTheDocument();
  await act(async () => pending.resolve({ ...currentPage, revision: { ...currentRevision, id: "adopted", content: "Old adopted result" } }));
  expect(query.push).toHaveBeenCalledTimes(1);
  expect(new URLSearchParams(query.value).get("w")).toBe("another");
  expect(api.wikiScopeFromUrl(new URLSearchParams(query.value).get("scope"))).toEqual(chosen);
  expect(screen.queryByText("Old adopted result")).not.toBeInTheDocument();
});

it("clears the old loading error after the current scope reload succeeds", async () => {
  vi.mocked(api.listWiki).mockRejectedValueOnce(new Error("Could not load Wiki list")).mockResolvedValue([currentPage]);
  render(<WikiView />);
  expect(await screen.findByRole("alert")).toHaveTextContent("Could not load Wiki list");
  await userEvent.click(screen.getByRole("button", { name: "Retry loading" }));
  expect(await screen.findByRole("link", { name: /Notes.*source/ })).toBeInTheDocument();
  expect(screen.queryByRole("alert")).not.toBeInTheDocument();
});
