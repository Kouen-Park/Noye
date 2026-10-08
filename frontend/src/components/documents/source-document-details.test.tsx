import { render, screen } from "@testing-library/react";
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
