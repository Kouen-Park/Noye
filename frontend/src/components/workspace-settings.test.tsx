import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, it, vi } from "vitest";

import type { AiSettings } from "@/lib/ai-settings";
import { downloadBackup, readWorkspace, restoreWorkspace } from "@/lib/workspace";
import { WorkspaceSettings } from "./workspace-settings";
import { openWorkspace, readWorkspaceLocations } from "@/lib/native-workspace";

vi.mock("@/lib/native-workspace", () => ({
  openWorkspace: vi.fn(), readWorkspaceLocations: vi.fn(),
}));

vi.mock("@/lib/workspace", () => ({
  downloadBackup: vi.fn(), readWorkspace: vi.fn(), restoreWorkspace: vi.fn(),
}));
const settings = { control_token: "synthetic" } as AiSettings;

beforeEach(() => {
  vi.resetAllMocks();
  vi.mocked(readWorkspace).mockResolvedValue({
    directory: "/synthetic/active", backup_format: 1, restore_limit_bytes: 20 * 1024**3,
  });
  vi.mocked(readWorkspaceLocations).mockResolvedValue({
    current: "/synthetic/active", original: "/synthetic/active", previous: null,
  });
});

it("requires explicit actions and explains what is saved", async () => {
  render(<WorkspaceSettings settings={settings} />);
  await screen.findByText("/synthetic/active");
  expect(downloadBackup).not.toHaveBeenCalled();
  expect(restoreWorkspace).not.toHaveBeenCalled();
  expect(screen.getByText(/Unsaved text is not included/)).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Download workspace backup" }));
  await screen.findByText(/Backup download prepared/);
  expect(downloadBackup).toHaveBeenCalledWith(settings);
});

it("shows a verified new destination and missing originals", async () => {
  vi.mocked(restoreWorkspace).mockResolvedValue({
    destination: "/synthetic/new", missing_sources: ["missing"],
    rebuild_required: true, workspace_id: "synthetic-id",
  });
  render(<WorkspaceSettings settings={settings} />);
  await screen.findByText("/synthetic/active");
  const file = new File(["synthetic zip"], "backup.zip", { type: "application/zip" });
  await userEvent.upload(screen.getByLabelText("Workspace backup file"), file);
  await userEvent.click(screen.getByRole("button", { name: "Restore into a new folder" }));
  await screen.findByText("/synthetic/new");
  expect(screen.getByText(/1 originals were missing/)).toBeInTheDocument();
  expect(restoreWorkspace).toHaveBeenCalledWith(settings, file);
});

it("reports busy backups without claiming success and permits retry", async () => {
  vi.mocked(downloadBackup).mockRejectedValue(new Error("Finish active requests."));
  render(<WorkspaceSettings settings={settings} />);
  await screen.findByText("/synthetic/active");
  await userEvent.click(screen.getByRole("button", { name: "Download workspace backup" }));
  await screen.findByRole("alert");
  expect(screen.queryByText(/Backup download prepared/)).not.toBeInTheDocument();
  await waitFor(() => expect(screen.getByRole("button", { name: "Download workspace backup" })).toBeEnabled());
});

it("requires saved-edit confirmation before switching a verified restore", async () => {
  vi.mocked(restoreWorkspace).mockResolvedValue({
    destination: "/synthetic/new", missing_sources: [], rebuild_required: true, workspace_id: "id",
  });
  render(<WorkspaceSettings settings={settings} />);
  await screen.findByText("/synthetic/active");
  await userEvent.upload(screen.getByLabelText("Workspace backup file"),
    new File(["zip"], "backup.zip", { type: "application/zip" }));
  await userEvent.click(screen.getByRole("button", { name: "Restore into a new folder" }));
  await userEvent.click(await screen.findByRole("button", { name: "Open restored workspace" }));
  expect(screen.getByRole("button", { name: "Confirm switch and restart" })).toBeDisabled();
  expect(openWorkspace).not.toHaveBeenCalled();
  await userEvent.click(screen.getByRole("checkbox"));
  await userEvent.click(screen.getByRole("button", { name: "Confirm switch and restart" }));
  await waitFor(() => expect(openWorkspace).toHaveBeenCalledWith("/synthetic/new"));
});

it("offers return to the original without overwriting either workspace", async () => {
  vi.mocked(readWorkspaceLocations).mockResolvedValue({
    current: "/synthetic/active", original: "/synthetic/original", previous: "/synthetic/previous",
  });
  render(<WorkspaceSettings settings={settings} />);
  await userEvent.click(await screen.findByRole("button", { name: "Reopen original workspace" }));
  await userEvent.click(screen.getByRole("checkbox"));
  await userEvent.click(screen.getByRole("button", { name: "Confirm switch and restart" }));
  await waitFor(() => expect(openWorkspace).toHaveBeenCalledWith(null));
});

it("offers the previous restore after returning to the original workspace", async () => {
  vi.mocked(readWorkspaceLocations).mockResolvedValue({
    current: "/synthetic/original", original: "/synthetic/original", previous: "/synthetic/restored",
  });
  render(<WorkspaceSettings settings={settings} />);
  await userEvent.click(await screen.findByRole("button", { name: "Reopen previous workspace" }));
  expect(screen.queryByRole("button", { name: "Reopen original workspace" })).not.toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Confirm switch and restart" })).toBeDisabled();
  expect(openWorkspace).not.toHaveBeenCalled();
  await userEvent.click(screen.getByRole("checkbox"));
  await userEvent.click(screen.getByRole("button", { name: "Confirm switch and restart" }));
  await waitFor(() => expect(openWorkspace).toHaveBeenCalledWith("/synthetic/restored"));
});

it("reports an invalid selected archive without claiming restore or switching workspaces", async () => {
  vi.mocked(restoreWorkspace).mockRejectedValue(new Error("This is not a valid Noye workspace backup."));
  render(<WorkspaceSettings settings={settings} />);
  await screen.findByText("/synthetic/active");
  const file = new File(["not an archive"], "notes.txt", { type: "text/plain" });
  await userEvent.upload(screen.getByLabelText("Workspace backup file"), file);
  await userEvent.click(screen.getByRole("button", { name: "Restore into a new folder" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("not a valid Noye workspace backup");
  expect(restoreWorkspace).toHaveBeenCalledWith(settings, file);
  expect(screen.queryByText("Verified restored workspace")).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Open restored workspace" })).not.toBeInTheDocument();
  expect(openWorkspace).not.toHaveBeenCalled();
  expect(screen.getByRole("button", { name: "Restore into a new folder" })).toBeEnabled();
});
