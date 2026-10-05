import { afterEach, expect, it, vi } from "vitest";
import { editWiki, generateWiki, listWiki, readWiki } from "@/lib/wiki";

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
