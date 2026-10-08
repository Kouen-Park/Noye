import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, it, vi } from "vitest";
import { WikiEditor } from "@/components/wiki/wiki-editor";
import { ALL_WIKI_SOURCES, editWiki, saveWikiAnalysis, type WikiPage } from "@/lib/wiki";

vi.mock("@/lib/wiki", async importOriginal => ({ ...await importOriginal<typeof import("@/lib/wiki")>(), editWiki: vi.fn(), saveWikiAnalysis: vi.fn() }));
export const page: WikiPage = { id: "wiki", title: "Notes", kind: "source", current_revision: "r1", publication_error: null, updated_at: "2026-10-06", proposal_count: 0, revisions: [], relations: [], revision: { id: "r1", wiki_id: "wiki", parent_id: null, origin: "generated", title: "Notes", content: "# Original", created_at: "2026-10-06", evidence: [], metadata: {} } };
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
