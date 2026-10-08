import { afterEach, expect, it, vi } from "vitest";
import { editWiki, generateWiki, listWiki, readWiki, wikiLinkHref, wikiPreviewContent, wikiScopeFromUrl } from "@/lib/wiki";

afterEach(() => vi.unstubAllGlobals());
it("preserves empty scope and source/revision identity in actual requests", async () => {
  const fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve([]) });
  vi.stubGlobal("fetch", fetch);
  const scope = { mode: "empty" as const, source_ids: [], root_ids: [] };
  await listWiki(scope);
  expect(JSON.parse(fetch.mock.calls[0][1].body)).toEqual(scope);
  await generateWiki("source", scope);
  expect(JSON.parse(fetch.mock.calls[1][1].body)).toEqual({ source_id: "source", scope });
  await editWiki("wiki", "revision", "Title", "Markdown");
  expect(JSON.parse(fetch.mock.calls[2][1].body).expected_revision).toBe("revision");
  await readWiki("wiki", scope);
  expect(JSON.parse(fetch.mock.calls[3][1].body)).toEqual(scope);
});
it("retains understandable conflict errors", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false, status: 409, json: () => Promise.resolve({ detail: "This page changed" }) }));
  await expect(editWiki("wiki", "old", "Title", "content")).rejects.toThrow("This page changed");
});
it("preserves chosen scope when opening verified portable Wiki links", () => {
  const scope = { mode: "chosen" as const, source_ids: ["source-one"], root_ids: [] };
  const markdown = "[Source Wiki](../sources/known.md)\n[Unknown](../sources/invented.md)";
  const preview = wikiPreviewContent(markdown, [{ wiki_id: "known" }], scope);
  const target = new URL(preview.match(/\[Source Wiki\]\(([^)]+)\)/)![1], "http://localhost");
  expect(target.pathname).toBe("/wiki/");
  expect(target.searchParams.get("w")).toBe("known");
  expect(wikiScopeFromUrl(target.searchParams.get("scope"))).toEqual(scope);
  expect(preview).toContain("[Unknown](../sources/invented.md)");
  expect(markdown).toContain("../sources/known.md");
});
it("rejects invalid explicit URL scope without broadening it", () => {
  expect(wikiScopeFromUrl("broken").mode).toBe("empty");
  expect(wikiScopeFromUrl(JSON.stringify({ mode: "chosen", source_ids: "all", root_ids: [] })).mode).toBe("empty");
});

it("keeps explicit app links inside the current scope and pins captured contributor revisions", () => {
  const scope = { mode: "chosen" as const, source_ids: ["one"], root_ids: [] };
  const contributors = [{ wiki_id: "basis", revision_id: "saved-revision" }];
  for (const href of ["../sources/basis.md", "/wiki/?w=basis&scope=all&revision=newer",
    "?w=basis", "http://localhost:3000/wiki/?w=basis", "https://tauri.localhost/wiki/?w=basis"]) {
    const target = new URL(wikiLinkHref(href, scope, contributors)!, "http://localhost");
    expect(wikiScopeFromUrl(target.searchParams.get("scope"))).toEqual(scope);
    expect(target.searchParams.get("w")).toBe("basis");
    expect(target.searchParams.get("revision")).toBe("saved-revision");
  }
  const preview = wikiPreviewContent("[Basis](../sources/basis.md)", contributors, scope);
  expect(preview).toContain("revision=saved-revision");
});

it("blocks empty-scope and unverified local paths while retaining explicit external references", () => {
  const chosen = { mode: "chosen" as const, source_ids: ["one"], root_ids: [] };
  for (const href of ["../sources/unverified.md", "../../private.txt", "/files/outside/source", "/chat/"]) {
    expect(wikiLinkHref(href, chosen)).toBeUndefined();
  }
  expect(wikiLinkHref("/wiki/?w=outside", { mode: "empty", source_ids: [], root_ids: [] })).toBeUndefined();
  expect(wikiLinkHref("https://example.com/reference", chosen)).toBe("https://example.com/reference");
  expect(wikiLinkHref("#saved-section", chosen)).toBe("#saved-section");
});
