import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, it, vi } from "vitest";
import { actOnJob, readJobs, type IngestionJob } from "@/lib/jobs";
import { JobsPanel } from "./jobs-panel";

vi.mock("@/lib/jobs", async (original) => ({
  ...await original<typeof import("@/lib/jobs")>(), readJobs: vi.fn(), actOnJob: vi.fn(),
}));
const job = { id: "job", file_id: "file", file_name: "notes.txt", state: "interrupted",
  stage: "embedding", completed: 16, total: 40, attempt: 1,
  error: "Processing was interrupted." } as IngestionJob;
beforeEach(() => { vi.resetAllMocks(); vi.mocked(readJobs).mockResolvedValue([job]); });
it("shows persisted progress and requires an explicit retry", async () => {
  const change = vi.fn();
  render(<JobsPanel revision="one" onChange={change} />);
  await screen.findByText(/16 \/ 40 passages embedded/);
  expect(actOnJob).not.toHaveBeenCalled();
  await userEvent.click(screen.getByRole("button", { name: "Retry from original" }));
  await waitFor(() => expect(actOnJob).toHaveBeenCalledWith("job", "resume"));
  expect(change).toHaveBeenCalled();
});
it("offers cancellation and displays failures", async () => {
  vi.mocked(readJobs).mockResolvedValue([{ ...job, state: "running" }]);
  vi.mocked(actOnJob).mockRejectedValue(new Error("This file is busy."));
  render(<JobsPanel revision="one" onChange={vi.fn()} />);
  await userEvent.click(await screen.findByRole("button", { name: "Stop processing" }));
  await screen.findByRole("alert");
  expect(screen.getByText("This file is busy.")).toBeInTheDocument();
});

it("directs an interrupted folder job to Folders instead of an impossible retry", async () => {
  vi.mocked(readJobs).mockResolvedValue([{ ...job, folder_root_id: "root-1" }]);
  render(<JobsPanel revision="one" onChange={vi.fn()} />);
  expect(await screen.findByRole("link", { name: "Manage in Folders" })).toHaveAttribute("href", "/folders");
  expect(screen.queryByRole("button", { name: "Retry from original" })).not.toBeInTheDocument();
  expect(actOnJob).not.toHaveBeenCalled();
});
