import { render, screen } from "@testing-library/react";
import { expect, it } from "vitest";
import { KnowledgeJobStages, type KnowledgeStageEvent } from "./knowledge-job-stages";

const summary: KnowledgeStageEvent = {
  sequence: 4, stage: "summarizing", state: "running", completed: 1, total: 1, detail: {},
};

it("settles a saved checkpoint when the job completes without a new stage event", () => {
  const events = [summary, {
    sequence: 9, stage: "filing", state: "skipped", completed: 0, total: 0,
    detail: { reason: "Automatic organization is disabled for this folder." },
  }];
  const { rerender } = render(<KnowledgeJobStages events={events} jobState="running" currentStage="summarizing" />);
  expect(screen.getByText("summarizing · running · 1/1")).toBeVisible();

  rerender(<KnowledgeJobStages events={events} jobState="complete" currentStage="complete" />);
  expect(screen.getByText("summarizing · finished · 1/1")).toBeVisible();
  expect(screen.queryByText(/running/)).not.toBeInTheDocument();
  expect(screen.getByText(/filing · skipped · Automatic organization is disabled/)).toBeVisible();
});

it("distinguishes past checkpoints from the current stage and a queued retry", () => {
  const events = [{ ...summary, sequence: 2, stage: "classification_summary" }, summary];
  const { rerender } = render(<KnowledgeJobStages events={events} jobState="running" currentStage="summarizing" />);
  expect(screen.getByText("classification summary · started · 1/1")).toBeVisible();
  expect(screen.getByText("summarizing · running · 1/1")).toBeVisible();

  rerender(<KnowledgeJobStages events={events} jobState="queued" currentStage="summarizing" />);
  expect(screen.queryByText(/running/)).not.toBeInTheDocument();
  expect(screen.getByText("summarizing · started · 1/1")).toBeVisible();
});

it.each(["failed", "cancelled", "interrupted"])("stops old checkpoints for a %s job and retains failed evidence checks", jobState => {
  const events = [summary, {
    sequence: 5, stage: "verify_support", state: "failed", completed: 0, total: 0,
    detail: { error: "Unsupported conclusion." },
  }];
  render(<KnowledgeJobStages events={events} jobState={jobState} currentStage="checking" />);
  expect(screen.getByText("summarizing · stopped · 1/1")).toBeVisible();
  expect(screen.queryByText(/running/)).not.toBeInTheDocument();
  expect(screen.getByText(/verify support · failed/)).toBeVisible();
  expect(screen.getByText("Unsupported conclusion.")).toBeVisible();
});

it("shows a cancellation request while its active stage is still stopping", () => {
  render(<KnowledgeJobStages events={[summary]} jobState="cancelling" currentStage="summarizing" />);
  expect(screen.getByText("summarizing · stopping · 1/1")).toBeVisible();
});
