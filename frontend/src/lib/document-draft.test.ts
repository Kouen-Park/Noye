import { beforeEach, expect, it } from "vitest";
import { acknowledgeDocumentDraft, documentDraftKey } from "@/lib/document-draft";

beforeEach(() => localStorage.clear());

it("advances continued typing owned by the saving editor only", () => {
  const key = documentDraftKey("doc");
  localStorage.setItem(key, JSON.stringify({ title: "Notes", content: "Further typing", expectedRevision: "r2", owner: "saving-editor" }));
  acknowledgeDocumentDraft("doc", "r2", "r3", "saving-editor");
  expect(JSON.parse(localStorage.getItem(key)!)).toEqual({ title: "Notes", content: "Further typing", expectedRevision: "r3", owner: "saving-editor" });
});

it("does not advance another window's draft even when it has the same base", () => {
  const key = documentDraftKey("doc");
  const draft = { title: "Notes", content: "Other window's authored work", expectedRevision: "r2", owner: "other-editor" };
  localStorage.setItem(key, JSON.stringify(draft));
  acknowledgeDocumentDraft("doc", "r2", "r3", "saving-editor");
  expect(JSON.parse(localStorage.getItem(key)!)).toEqual(draft);
});
