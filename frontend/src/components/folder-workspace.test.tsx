import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, it, vi } from "vitest";
import { FolderWorkspace } from "./folder-workspace";
import { chooseSourceFolder, folderRequest } from "@/lib/folders";
import { actOnJob } from "@/lib/jobs";

vi.mock("@/lib/runtime", () => ({ isDesktopRuntime: () => true }));
vi.mock("@/lib/jobs", () => ({ actOnJob: vi.fn(), jobIsActive: () => false }));
vi.mock("@/lib/folders", () => ({ chooseSourceFolder: vi.fn(), folderRequest: vi.fn(),
  revealFolder: vi.fn(), revealSource: vi.fn() }));

let root: { id: string; name: string; kind: string; connected: number; processing: number;
  organization_prefix: string | null; availability: string; error: null };
let remembered = false;
beforeEach(() => {
  remembered = false;
  vi.resetAllMocks();
  root = { id: "root-1", name: "Synthetic knowledge", kind: "connected", connected: 1,
    processing: 1, organization_prefix: null, availability: "available", error: null };
  vi.mocked(chooseSourceFolder).mockResolvedValue(null);
  vi.mocked(folderRequest).mockImplementation(async (path = "", method = "GET", body) => {
    if (method === "PATCH") { Object.assign(root, body);
      if ((body as { disconnect?: boolean })?.disconnect) { root.connected = 0; root.availability = "disconnected"; }
      return root; }
    if (path.endsWith("/filing")) return [];
    if (path.endsWith("/tree")) return { root: { ...root }, entries: [
      { relative_path: "sources", kind: "directory", remembered },
      { relative_path: "sources/inbox", kind: "directory" },
      { relative_path: "sources/inbox/note.txt", kind: "file", source: {
        source_id: "source-1", root_id: root.id, relative_path: "sources/inbox/note.txt", name: "note.txt",
        version: "version-1", availability: root.availability, processing_state: "FAILED", error: "Interrupted",
        manual_category: null, job: { id: "job-1", state: "interrupted", total: 40, completed: 16, stage: "embedding", attempt: 1 },
      } },
    ] };
    return [{ ...root }];
  });
});

it("uses the native picker and cancellation never sends a path to an HTTP registration", async () => {
  render(<FolderWorkspace />);
  await screen.findByText("Synthetic knowledge");
  await userEvent.click(screen.getByRole("button", { name: "Connect existing folder" }));
  expect(chooseSourceFolder).toHaveBeenCalledWith("connected");
  expect(vi.mocked(folderRequest).mock.calls.some(call => call[1] === "POST")).toBe(false);
  expect(screen.getByText(/Disconnecting preserves originals/)).toBeInTheDocument();
});

it("requires an explicitly chosen organization area and preserves disconnect semantics", async () => {
  render(<FolderWorkspace />);
  const optin = await screen.findByRole("checkbox");
  expect(optin).not.toBeChecked(); expect(optin).toBeDisabled();
  await userEvent.selectOptions(screen.getByLabelText("Organization area"), "sources");
  await userEvent.click(optin);
  await waitFor(() => expect(folderRequest).toHaveBeenCalledWith("/root-1", "PATCH", { organization_prefix: "sources" }));
  await userEvent.click(screen.getByRole("button", { name: "Disconnect" }));
  await waitFor(() => expect(folderRequest).toHaveBeenCalledWith("/root-1", "PATCH", { disconnect: true }));
  await screen.findByRole("button", { name: "Reconnect folder" });
});

it("shows interrupted progress and explicitly retries the existing ingestion job", async () => {
  render(<FolderWorkspace />);
  await screen.findByText(/16 \/ 40/);
  await userEvent.click(screen.getByRole("button", { name: "Retry from original" }));
  expect(actOnJob).toHaveBeenCalledWith("job-1", "resume");
});

it("keeps a manual destination draft when collision-safe filing is rejected", async () => {
  root.organization_prefix = "sources";
  render(<FolderWorkspace />);
  await userEvent.click(await screen.findByRole("button", { name: "File manually" }));
  const destination = screen.getByLabelText("Relative destination");
  await userEvent.type(destination, "sources/Topic/collision.txt");
  vi.mocked(folderRequest).mockImplementationOnce(async () => { throw new Error("Destination exists. Original preserved."); });
  await userEvent.click(screen.getByRole("button", { name: "Move original & fix category" }));
  await screen.findByRole("alert");
  expect(destination).toHaveValue("sources/Topic/collision.txt");
  expect(folderRequest).toHaveBeenCalledWith("/root-1/file", "POST", {
    source_id: "source-1", destination: "sources/Topic/collision.txt", expected_version: "version-1", manual: true,
  });
});


it("retains the authorized filing area while an unavailable folder shows remembered locations", async () => {
  root.organization_prefix = "sources";
  root.availability = "unavailable";
  remembered = true;
  render(<FolderWorkspace />);
  await screen.findByRole("button", { name: "Re-select folder" });
  expect(screen.getByLabelText("Organization area")).toHaveValue("sources");
  expect(screen.getByRole("button", { name: "Open in Finder" })).toBeDisabled();
  expect(screen.getByRole("button", { name: "File manually" })).toBeDisabled();
  expect(screen.getByText(/Registered location/)).toBeInTheDocument();
});
