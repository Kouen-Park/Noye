import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, it, vi } from "vitest";
import { WikiEditor } from "@/components/wiki/wiki-editor";
import { ALL_WIKI_SOURCES, editWiki, readWiki, saveWikiAnalysis, type WikiPage } from "@/lib/wiki";

vi.mock("@/lib/wiki", async importOriginal => ({ ...await importOriginal<typeof import("@/lib/wiki")>(), editWiki: vi.fn(), readWiki: vi.fn(), saveWikiAnalysis: vi.fn() }));
export const page: WikiPage = { id: "wiki", title: "Notes", kind: "source", current_revision: "r1", publication_error: null, updated_at: "2026-10-06", proposal_count: 0, revisions: [], relations: [], revision: { id: "r1", wiki_id: "wiki", parent_id: null, origin: "generated", title: "Notes", content: "# Original", created_at: "2026-10-06", evidence: [], metadata: {} } };
function deferred<T>() { let resolve!: (value: T) => void; const promise = new Promise<T>(r => { resolve = r; }); return { promise, resolve }; }
beforeEach(() => { vi.clearAllMocks(); window.localStorage.clear(); });

it("saves edited Markdown with its expected revision", async () => {
  vi.mocked(editWiki).mockResolvedValue({ ...page, revision: { ...page.revision!, id: "r2", origin: "user" } });
  const onSaved = vi.fn();
  render(<WikiEditor page={page} scope={ALL_WIKI_SOURCES} onSaved={onSaved} />);
  await userEvent.click(screen.getByRole("button", { name: "Edit Markdown" }));
  await userEvent.type(screen.getByLabelText("Markdown"), " 한국어 edit");
  await userEvent.click(screen.getByRole("button", { name: "Save changes" }));
  expect(editWiki).toHaveBeenCalledWith("wiki", "r1", "Notes", "# Original 한국어 edit", ALL_WIKI_SOURCES);
  expect(onSaved).toHaveBeenCalled();
});

it("keeps drafts across incoming generated revisions and failed saves", async () => {
  vi.mocked(editWiki).mockRejectedValue(new Error("This page changed. Reload before saving."));
  const view = render(<WikiEditor page={page} scope={ALL_WIKI_SOURCES} onSaved={vi.fn()} />);
  await userEvent.click(screen.getByRole("button", { name: "Edit Markdown" }));
  await userEvent.type(screen.getByLabelText("Markdown"), " authored");
  view.rerender(<WikiEditor page={{ ...page, revision: { ...page.revision!, id: "r2", content: "AI replacement" } }} scope={ALL_WIKI_SOURCES} onSaved={vi.fn()} />);
  expect(screen.getByLabelText("Markdown")).toHaveValue("# Original authored");
  await userEvent.click(screen.getByRole("button", { name: "Save changes" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Your draft is still here");
  expect(screen.getByLabelText("Markdown")).toHaveValue("# Original authored");
});

it("saves a reusable analysis with the explicit material scope", async () => {
  vi.mocked(saveWikiAnalysis).mockResolvedValue({ ...page, id: "analysis" });
  const scope = { mode: "chosen" as const, source_ids: ["one"], root_ids: [] };
  render(<WikiEditor page={page} scope={scope} onSaved={vi.fn()} />);
  await userEvent.click(screen.getByRole("button", { name: "Save as analysis" }));
  expect(saveWikiAnalysis).toHaveBeenCalledWith("Notes analysis", "# Original", ["wiki"], scope);
  const saved = await screen.findByRole("link", { name: "Open saved analysis · Notes" });
  const target = new URL(saved.getAttribute("href")!, "http://localhost");
  expect(target.searchParams.get("w")).toBe("analysis");
  expect(JSON.parse(target.searchParams.get("scope")!)).toEqual(scope);
  expect(target.searchParams.has("revision")).toBe(false);
  expect(screen.getByText("Analysis saved.")).toBeInTheDocument();
});

it("does not load automatic remote images or execute raw HTML", () => {
  const view = render(<WikiEditor page={{ ...page, revision: { ...page.revision!, content: "![Private](https://example.com/tracking.png)\n<script>alert(1)</script>" } }} scope={ALL_WIKI_SOURCES} onSaved={vi.fn()} />);
  expect(view.container.querySelector("img")).toBeNull();
  expect(view.container.querySelector("script")).toBeNull();
});

it("restores an unsaved draft after navigation or restart without losing its version", async () => {
  const first = render(<WikiEditor page={page} scope={ALL_WIKI_SOURCES} onSaved={vi.fn()} />);
  await userEvent.click(screen.getByRole("button", { name: "Edit Markdown" }));
  await userEvent.type(screen.getByLabelText("Markdown"), " recover me");
  first.unmount();
  render(<WikiEditor page={{ ...page, revision: { ...page.revision!, id: "r2", content: "New model output" } }} scope={ALL_WIKI_SOURCES} onSaved={vi.fn()} />);
  await screen.findByText(/local draft retained/);
  await userEvent.click(screen.getByRole("button", { name: "Edit Markdown" }));
  expect(screen.getByLabelText("Markdown")).toHaveValue("# Original recover me");
  vi.mocked(editWiki).mockRejectedValue(new Error("Revision conflict"));
  await userEvent.click(screen.getByRole("button", { name: "Save changes" }));
  expect(editWiki).toHaveBeenCalledWith("wiki", "r1", "Notes", "# Original recover me", ALL_WIKI_SOURCES);
});

it("keeps authored Markdown links scoped and leaves the stored editable body intact", async () => {
  const content = "[Related](/wiki/?w=other&scope=all)\n\n[Unverified](../sources/unknown.md)";
  const scope = { mode: "chosen" as const, source_ids: ["one"], root_ids: [] };
  render(<WikiEditor page={{ ...page, revision: { ...page.revision!, content } }} scope={scope} onSaved={vi.fn()} />);
  const target = new URL(screen.getByRole("link", { name: "Related" }).getAttribute("href")!, "http://localhost");
  expect(JSON.parse(target.searchParams.get("scope")!)).toEqual(scope);
  expect(screen.queryByRole("link", { name: "Unverified" })).not.toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Edit Markdown" }));
  expect(screen.getByLabelText("Markdown")).toHaveValue(content);
});

it("requires review before rebasing a restored draft and keeps revision conflicts enforced", async () => {
  window.localStorage.setItem("noye:wiki-draft:wiki", JSON.stringify({
    draft: { title: "My notes", content: "My retained draft", expected: "r0" },
    baseline: { title: "Old title", content: "Old body" },
  }));
  const latest = { ...page, current_revision: "r2", revision: { ...page.revision!, id: "r2", content: "New saved work" } };
  vi.mocked(readWiki).mockResolvedValue(latest);
  vi.mocked(editWiki).mockRejectedValue(new Error("Revision changed again"));
  const onSaved = vi.fn();
  render(<WikiEditor page={page} scope={ALL_WIKI_SOURCES} onSaved={onSaved} />);
  await screen.findByText(/local draft retained/);
  await userEvent.click(screen.getByRole("button", { name: "Compare with latest revision" }));
  expect(await screen.findByLabelText("Latest saved Markdown")).toHaveValue("New saved work");
  expect(editWiki).not.toHaveBeenCalled();
  await userEvent.click(screen.getByRole("button", { name: "Reapply my draft to this revision" }));
  expect(onSaved).toHaveBeenCalledWith(latest);
  expect(JSON.parse(window.localStorage.getItem("noye:wiki-draft:wiki")!).draft.expected).toBe("r2");
  await userEvent.click(screen.getByRole("button", { name: "Save changes" }));
  expect(editWiki).toHaveBeenCalledWith("wiki", "r2", "My notes", "My retained draft", ALL_WIKI_SOURCES);
  expect(await screen.findByRole("alert")).toHaveTextContent("Revision changed again");
});


it("can discard a conflicting draft after reviewing the latest saved content", async () => {
  localStorage.setItem("noye:wiki-draft:wiki", JSON.stringify({
    draft: { title: "Draft", content: "Retained", expected: "r0" },
    baseline: { title: "Old", content: "Old" },
  }));
  const latest = { ...page, current_revision: "r2", revision: { ...page.revision!, id: "r2", content: "Saved content" } };
  vi.mocked(readWiki).mockResolvedValue(latest);
  const onSaved = (saved: WikiPage) => view.rerender(<WikiEditor page={saved} scope={ALL_WIKI_SOURCES} onSaved={onSaved} />);
  const view = render(<WikiEditor page={page} scope={ALL_WIKI_SOURCES} onSaved={onSaved} />);
  await screen.findByText(/local draft retained/);
  await userEvent.click(screen.getByRole("button", { name: "Compare with latest revision" }));
  await screen.findByLabelText("Latest saved Markdown");
  await userEvent.click(screen.getByRole("button", { name: "Discard my draft and use latest" }));
  await userEvent.click(screen.getByRole("button", { name: "Edit Markdown" }));
  expect(screen.getByLabelText("Markdown")).toHaveValue("Saved content");
  expect(screen.getByRole("button", { name: "Save changes" })).toBeDisabled();
  expect(localStorage.getItem("noye:wiki-draft:wiki")).toBeNull();
});

it("keeps the original draft and expected revision after saving an analysis", async () => {
  const scope = { mode: "chosen" as const, source_ids: ["one"], root_ids: [] };
  vi.mocked(saveWikiAnalysis).mockResolvedValue({ ...page, id: "analysis", title: "Saved analysis" });
  render(<WikiEditor page={page} scope={scope} onSaved={vi.fn()} />);
  await userEvent.click(screen.getByRole("button", { name: "Edit Markdown" }));
  await userEvent.type(screen.getByLabelText("Markdown"), " authored");
  const retained = localStorage.getItem("noye:wiki-draft:wiki");
  await userEvent.click(screen.getByRole("button", { name: "Save as analysis" }));
  expect(await screen.findByRole("link", { name: "Open saved analysis · Saved analysis" })).toBeInTheDocument();
  expect(screen.getByLabelText("Markdown")).toHaveValue("# Original authored");
  expect(screen.getByRole("button", { name: "Save changes" })).toBeEnabled();
  expect(localStorage.getItem("noye:wiki-draft:wiki")).toBe(retained);
  expect(JSON.parse(retained!).draft.expected).toBe("r1");
});

it("reports a failed analysis save without claiming success or losing the draft", async () => {
  vi.mocked(saveWikiAnalysis).mockRejectedValue(new Error("Could not publish analysis"));
  render(<WikiEditor page={page} scope={ALL_WIKI_SOURCES} onSaved={vi.fn()} />);
  await userEvent.click(screen.getByRole("button", { name: "Edit Markdown" }));
  await userEvent.type(screen.getByLabelText("Markdown"), " retained");
  await userEvent.click(screen.getByRole("button", { name: "Save as analysis" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Could not publish analysis");
  expect(screen.queryByRole("link", { name: /Open saved analysis/ })).not.toBeInTheDocument();
  expect(screen.getByLabelText("Markdown")).toHaveValue("# Original retained");
  expect(JSON.parse(localStorage.getItem("noye:wiki-draft:wiki")!).draft.expected).toBe("r1");
});

it("does not remove or acknowledge the replacement editor draft when an older save completes", async () => {
  const pending = deferred<WikiPage>();
  vi.mocked(editWiki).mockReturnValue(pending.promise);
  const oldSaved = vi.fn();
  const first = render(<WikiEditor page={page} scope={ALL_WIKI_SOURCES} onSaved={oldSaved} />);
  await userEvent.click(screen.getByRole("button", { name: "Edit Markdown" }));
  await userEvent.type(screen.getByLabelText("Markdown"), " first");
  await userEvent.click(screen.getByRole("button", { name: "Save changes" }));
  const oldOwner = JSON.parse(localStorage.getItem("noye:wiki-draft:wiki")!).owner;
  first.unmount();
  const scope = { mode: "chosen" as const, source_ids: ["one"], root_ids: [] };
  const second = render(<WikiEditor page={page} scope={scope} onSaved={vi.fn()} />);
  await screen.findByText(/local draft retained/);
  await userEvent.click(screen.getByRole("button", { name: "Edit Markdown" }));
  await userEvent.type(screen.getByLabelText("Markdown"), " later");
  const retained = localStorage.getItem("noye:wiki-draft:wiki");
  expect(JSON.parse(retained!).owner).not.toBe(oldOwner);
  const saved = { ...page, current_revision: "r2", revision: { ...page.revision!, id: "r2", content: "# Original first" } };
  await act(async () => pending.resolve(saved));
  expect(oldSaved).not.toHaveBeenCalled();
  expect(localStorage.getItem("noye:wiki-draft:wiki")).toBe(retained);
  second.unmount();
  render(<WikiEditor page={saved} scope={scope} onSaved={vi.fn()} />);
  await screen.findByText(/local draft retained/);
  await userEvent.click(screen.getByRole("button", { name: "Edit Markdown" }));
  expect(screen.getByLabelText("Markdown")).toHaveValue("# Original first later");
  expect(JSON.parse(localStorage.getItem("noye:wiki-draft:wiki")!).draft.expected).toBe("r1");
});

it("preserves late input in the same editor and advances only its acknowledged base", async () => {
  const pending = deferred<WikiPage>();
  vi.mocked(editWiki).mockReturnValue(pending.promise);
  const onSaved = (saved: WikiPage) => view.rerender(<WikiEditor page={saved} scope={ALL_WIKI_SOURCES} onSaved={onSaved} />);
  const view = render(<WikiEditor page={page} scope={ALL_WIKI_SOURCES} onSaved={onSaved} />);
  await userEvent.click(screen.getByRole("button", { name: "Edit Markdown" }));
  await userEvent.type(screen.getByLabelText("Markdown"), " submitted");
  await userEvent.click(screen.getByRole("button", { name: "Save changes" }));
  const owner = JSON.parse(localStorage.getItem("noye:wiki-draft:wiki")!).owner;
  // A change already delivered to the editor must survive the pending save acknowledgement.
  fireEvent.change(screen.getByLabelText("Markdown"), { target: { value: "# Original submitted later" } });
  const saved = { ...page, current_revision: "r2", revision: { ...page.revision!, id: "r2", content: "# Original submitted" } };
  await act(async () => pending.resolve(saved));
  expect(screen.getByLabelText("Markdown")).toHaveValue("# Original submitted later");
  expect(screen.getByRole("button", { name: "Save changes" })).toBeEnabled();
  await waitFor(() => expect(JSON.parse(localStorage.getItem("noye:wiki-draft:wiki")!)).toMatchObject({
    owner, draft: { content: "# Original submitted later", expected: "r2" }, baseline: { content: "# Original submitted" },
  }));
  await userEvent.click(screen.getByRole("button", { name: "Save changes" }));
  expect(editWiki).toHaveBeenLastCalledWith("wiki", "r2", "Notes", "# Original submitted later", ALL_WIKI_SOURCES);
});
