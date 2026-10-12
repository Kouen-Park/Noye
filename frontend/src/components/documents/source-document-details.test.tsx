import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, it, vi } from "vitest";
import { SourceDocumentDetails } from "./source-document-details";
import { type SourceDocument } from "@/lib/source-documents";

const document: SourceDocument = {
  id: "doc", title: "Report", content: "# Report", source_conversation_id: null,
  source_message_id: null, source_instruction: "Write a report", citations: [],
  created_at: "2026-10-08T00:00:00Z", updated_at: "2026-10-08T00:00:00Z",
  revision: { id: "generated", origin: "generated", title: "Report", content: "# Report",
    created_at: "2026-10-08T00:00:00Z", metadata: {
    coverage: { partial: true, inventory_mode: "collection", inventory_count: 0, sources: [],
      presentation_limits: [{ code: "unsupported_heading", reason: "An unsupported heading was replaced with a neutral label." }] },
    citations: [], model: "local", prompt_version: "source-document-v5", processing_seconds: 1,
    request_id: "request", scope: { mode: "all", source_ids: [], root_ids: [] },
  } },
  revisions: [{ id: "generated", origin: "generated", title: "Report", created_at: "2026-10-08T00:00:00Z" }],
};

it("shows the saved revision's explicit presentation limit", () => {
  render(<SourceDocumentDetails document={document} onRevision={vi.fn()} />);
  expect(screen.getByText("Partial document")).toBeInTheDocument();
  expect(screen.getByText("Document structure and language limits")).toBeInTheDocument();
  expect(screen.getByText("An unsupported heading was replaced with a neutral label.")).toBeInTheDocument();
});

it("reads older revisions without claiming the new presentation checks ran", () => {
  const old = structuredClone(document);
  delete old.revision.metadata.coverage.presentation_limits;
  render(<SourceDocumentDetails document={old} onRevision={vi.fn()} />);
  expect(screen.queryByText("Document structure and language limits")).not.toBeInTheDocument();
  expect(screen.getByText("Partial document")).toBeInTheDocument();
});

it("keeps original location, availability and saved passage behind a quiet disclosure", async () => {
  const saved = structuredClone(document);
  saved.revision.metadata.citations = [{
    id: "evidence", source: { source_id: "source", root_id: null, name: "Original 한국어.pdf", source_hash: "hash", source_version: "version", relative_path: "Original 한국어.pdf" },
    page_number: 7, passage_index: 2, start: 10, end: 30, text: "Saved passage context", current_status: "available", quote: "Exact saved quote", quote_start: 11, quote_end: 20,
  }];
  render(<SourceDocumentDetails document={saved} onRevision={vi.fn()} />);
  const disclosure = screen.getByText(/Originals, coverage and saved evidence/);
  expect(disclosure.closest("details")).not.toHaveAttribute("open");
  await userEvent.click(disclosure);
  expect(screen.getByText(/Original 한국어.pdf.*page 7.*available/)).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Open original" })).toHaveAttribute("href", expect.stringMatching(/\/files\/source\/source#page=7$/));
  expect(screen.getByText("Exact saved quote")).toBeInTheDocument();
  await userEvent.click(screen.getByText("Passage details"));
  expect(screen.getByText("Saved passage context")).toBeInTheDocument();
  expect(screen.getByText(/Version: version.*passage 2/)).toBeInTheDocument();
});
