import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, it, vi } from "vitest";
import type { ReactNode } from "react";

import LibraryPage from "./page";
import { useLibrary, type Library } from "@/hooks/use-library";
import type { StoredFile } from "@/lib/api";

vi.mock("@/hooks/use-library", () => ({ useLibrary: vi.fn() }));
vi.mock("@/components/app-shell", () => ({ AppShell: ({ title, actions, children }: {
  title: ReactNode; actions: ReactNode; children: ReactNode;
}) => <div><h1>{title}</h1><div>{actions}</div>{children}</div> }));
vi.mock("@/components/library/jobs-panel", () => ({ JobsPanel: () => null }));

const stored: StoredFile = { id: "file-1", name: "notes.txt", file_type: "txt", size: 10,
  status: "READY", error: null, page_count: null, chunk_count: 1,
  created_at: "2026-10-12T00:00:00Z", updated_at: "2026-10-12T00:00:00Z" };
let library: Library;
beforeEach(() => {
  library = { files: [], phase: "ready", loadError: null, uploading: [], stoppingIds: [],
    rejected: [], announcement: "", lastAddedId: null,
    integrity: { embedding_model: "embeddinggemma", ready_files: 0, searchable_files: 0,
      deep: false, point_check_complete: false, problems: [] },
    integrityPhase: "ready", integrityError: null, rebuildResult: null,
    reload: vi.fn(), checkIndex: vi.fn().mockResolvedValue(undefined), rebuildIndex: vi.fn().mockResolvedValue(undefined),
    addFiles: vi.fn().mockResolvedValue(undefined), removeFile: vi.fn().mockResolvedValue(undefined),
    retryFile: vi.fn().mockResolvedValue(undefined), cancelFile: vi.fn().mockResolvedValue(undefined), dismissRejection: vi.fn(),
  };
  vi.mocked(useLibrary).mockImplementation(() => library);
});

it("emphasizes the accessible upload affordance only in an empty library", () => {
  const view = render(<LibraryPage />);
  expect(screen.getByLabelText(/Drop files to add them/)).toBeEnabled();
  expect(screen.queryByLabelText("Add files")).not.toBeInTheDocument();
  library = { ...library, files: [stored], uploading: ["new.txt"] };
  view.rerender(<LibraryPage />);
  expect(screen.getByLabelText("Add files")).toBeEnabled();
  expect(screen.queryByLabelText(/Drop files to add them/)).not.toBeInTheDocument();
  expect(screen.getByText(/Adding new.txt/)).toBeVisible();
});

it("keeps compact selection and page-wide drop connected to the same upload action", async () => {
  library.files = [stored];
  render(<LibraryPage />);
  const chosen = new File(["Original"], "chosen.txt", { type: "text/plain" });
  await userEvent.upload(screen.getByLabelText("Add files"), chosen);
  expect(library.addFiles).toHaveBeenCalledTimes(1);
  expect(library.addFiles).toHaveBeenLastCalledWith([chosen]);
  fireEvent.drop(screen.getByText("notes.txt"), { dataTransfer: { files: [chosen] } });
  expect(library.addFiles).toHaveBeenCalledTimes(2);
  expect(library.addFiles).toHaveBeenLastCalledWith([chosen]);
});

it("preserves upload errors and moves focus to a newly added row", () => {
  library.files = [stored];
  library.rejected = [{ key: "refused", name: "oversized.pdf", message: "Reduce this file in Finder." }];
  const view = render(<LibraryPage />);
  expect(screen.getByRole("alert")).toHaveTextContent("oversized.pdf");
  library = { ...library, files: [{ ...stored, id: "new", name: "new.txt", status: "UPLOADING" }, stored], lastAddedId: "new" };
  view.rerender(<LibraryPage />);
  expect(screen.getByText("new.txt").closest("li")).toHaveFocus();
  expect(screen.getByRole("alert")).toHaveTextContent("Reduce this file in Finder.");
});
