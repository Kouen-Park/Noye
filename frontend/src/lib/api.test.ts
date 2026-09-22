import { describe, expect, it } from "vitest";

import { ACCEPTED_EXTENSIONS, ACCEPT_ATTRIBUTE, isProcessing, rejectionFor } from "@/lib/api";

function upload(name: string, size = 10): File {
  return new File([new Uint8Array(size)], name);
}

describe("accepted types", () => {
  it("drives the input attribute from the same list as the check", () => {
    // Two lists would drift, and the attribute only filters the picker — a
    // dragged file is never filtered by it at all.
    for (const extension of ACCEPTED_EXTENSIONS) {
      expect(ACCEPT_ATTRIBUTE).toContain(`.${extension}`);
    }
  });
});

describe("rejectionFor", () => {
  it("accepts every supported format, whatever the case", () => {
    expect(rejectionFor(upload("lecture.pdf"))).toBeNull();
    expect(rejectionFor(upload("notes.md"))).toBeNull();
    expect(rejectionFor(upload("notes.MARKDOWN"))).toBeNull();
    expect(rejectionFor(upload("log.TXT"))).toBeNull();
  });

  it("refuses a format Noye cannot read, naming what it can", () => {
    const reason = rejectionFor(upload("report.docx"));
    expect(reason).toMatch(/PDF, Markdown, and plain text/);
  });

  it("refuses a file with no extension at all", () => {
    expect(rejectionFor(upload("README"))).not.toBeNull();
  });

  it("refuses an empty file, because there is nothing to index", () => {
    expect(rejectionFor(upload("empty.md", 0))).toMatch(/empty/);
  });

  it("checks the type before the size, so the more useful reason wins", () => {
    expect(rejectionFor(upload("empty.docx", 0))).toMatch(/PDF, Markdown, and plain text/);
  });
});

describe("isProcessing", () => {
  it("treats only READY and FAILED as settled", () => {
    expect(isProcessing("UPLOADING")).toBe(true);
    expect(isProcessing("EXTRACTING")).toBe(true);
    expect(isProcessing("CHUNKING")).toBe(true);
    expect(isProcessing("EMBEDDING")).toBe(true);
    expect(isProcessing("READY")).toBe(false);
    expect(isProcessing("FAILED")).toBe(false);
  });
});
