import { describe, expect, it } from "vitest";
import { documentScope, isDocumentIntent } from "@/lib/source-documents";

describe("document intent and source scopes", () => {
  it("preserves all, empty and chosen", () => {
    expect(documentScope(null).mode).toBe("all");
    expect(documentScope([]).mode).toBe("empty");
    expect(documentScope(["source-a"])).toEqual({ mode: "chosen", source_ids: ["source-a"], root_ids: [] });
  });
  it("recognizes explicit Korean and English creation requests", () => {
    expect(isDocumentIntent("Write a report comparing the projects.")).toBe(true);
    expect(isDocumentIntent("지금까지 강의자료의 요약 노트를 만들어 줘.")).toBe(true);
    expect(isDocumentIntent("Compare the project approaches.")).toBe(false);
    expect(isDocumentIntent("What is a report?")).toBe(false);
  });
});
