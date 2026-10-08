import { render, screen } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import { DocumentTasks } from "./document-tasks";
import { listDocumentTasks, type DocumentTask } from "@/lib/source-documents";

vi.mock("@/lib/source-documents", () => ({ listDocumentTasks: vi.fn() }));
vi.mock("@/lib/wiki", () => ({ wikiJobAction: vi.fn() }));
const task: DocumentTask = {
  job: { id: "job", kind: "source_document", subject_id: "request", state: "failed",
    stage: "starting", completed: 0, total: 0, error: "No sources are allowed.", artifact_id: null },
  request: { id: "request", artifact_id: null, clarification: "Choose sources, then submit a new request.",
    request: { instruction: "Write a project report", conversation_id: "chat", scope: { mode: "empty", source_ids: [], root_ids: [] } },
    manifest: [], plan: null, report: {} },
};
it("shows terminal scope clarification without continuing discovery or retrying the same empty scope", async () => {
  vi.mocked(listDocumentTasks).mockResolvedValue([task]);
  render(<DocumentTasks conversationId="chat" />);
  expect(await screen.findByText(task.request.clarification!)).toBeInTheDocument();
  expect(screen.getByText(/Inventory fixed at start: 0 sources. Selection not completed/)).toBeInTheDocument();
  expect(screen.queryByText(/Discovering relevant sources/)).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Retry frozen request" })).not.toBeInTheDocument();
});
it("links an independent saved partial artifact and keeps PDF success separate", async () => {
  vi.mocked(listDocumentTasks).mockResolvedValue([{ ...task,
    job: { ...task.job!, state: "complete", stage: "complete", error: null, artifact_id: "doc" },
    request: { ...task.request, artifact_id: "doc", clarification: null,
      plan: { selected_ids: ["source"] }, report: { partial: true, presentation_limits: [{ code: "comparison_unresolved", reason: "Separate source notes are not a completed comparison." }] } },
  }]);
  render(<DocumentTasks conversationId="chat" />);
  expect(await screen.findByRole("link", { name: "Open document" })).toHaveAttribute("href", "/documents?d=doc");
  expect(screen.getByRole("link", { name: "Edit and export" })).toHaveAttribute("href", "/documents?d=doc&export=1");
  expect(screen.getByText(/some material or conclusions remain unresolved/)).toBeInTheDocument();
  expect(screen.getByText(/PDF export completes separately/)).toBeInTheDocument();
  expect(screen.getByRole("list", { name: "Document structure and language limits" })).toHaveTextContent("Separate source notes are not a completed comparison.");
});
