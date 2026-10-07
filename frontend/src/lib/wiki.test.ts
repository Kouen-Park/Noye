import { afterEach, expect, it, vi } from "vitest";
import { editWiki, generateWiki, listWiki, readWiki, wikiPreviewContent, wikiScopeFromUrl } from "@/lib/wiki";

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
