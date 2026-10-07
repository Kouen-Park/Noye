import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, it, vi } from "vitest";
import { DocumentEditor } from "@/components/documents/document-editor";

afterEach(() => localStorage.clear());
it("restores an unsaved draft after leaving and reopening the document", async () => {
  const props = { title: "Report", content: "# Saved", saving: false, onSave: vi.fn(), documentId: "recover-doc" };
  const first = render(<DocumentEditor {...props} />);
  await userEvent.type(screen.getByLabelText(/document content/i), "\n한국어 edit");
  first.unmount();
  render(<DocumentEditor {...props} />);
  await waitFor(() => expect(screen.getByLabelText(/document content/i)).toHaveValue("# Saved\n한국어 edit"));
  expect(screen.getByRole("status")).toHaveTextContent("Restored your local unsaved draft");
});
it("keeps a historical selected revision read only and exports its body", async () => {
  const onSave = vi.fn();
  localStorage.setItem("noye-document-draft:history-doc", JSON.stringify({ title: "Draft", content: "Unsaved current edit" }));
  render(<DocumentEditor title="Historical" content="# Historical 한국어" saving={false} onSave={onSave}
    readOnly documentId="history-doc" exportUrl="http://localhost:8000/source-documents/history-doc/export.md?revision=rev-old" />);
  expect(screen.getByLabelText(/document content/i)).toHaveValue("# Historical 한국어");
  expect(screen.getByLabelText(/document content/i)).toHaveAttribute("readonly");
  expect(screen.getByRole("button", { name: "Saved" })).toBeDisabled();
  await userEvent.click(screen.getByRole("tab", { name: "Preview" }));
  expect(screen.getByRole("heading", { name: "Historical 한국어" })).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Export .md" })).toHaveAttribute("href", expect.stringContaining("revision=rev-old"));
  expect(onSave).not.toHaveBeenCalled();
  expect(localStorage.getItem("noye-document-draft:history-doc")).toContain("Unsaved current edit");
});
