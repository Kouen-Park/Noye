export interface KnowledgeStageEvent {
  sequence: number; stage: string; state: string; completed: number; total: number;
  detail: { reason?: string; error?: string; destination?: string };
}

function stageState(event: KnowledgeStageEvent, jobState: string, currentStage: string) {
  if (event.state !== "running") return event.state;
  // Checkpoints record that a stage was visited. Its old event is not a live
  // status, and finishing the job does not certify every intermediate verdict.
  if (jobState === "complete") return "finished";
  if (["failed", "cancelled", "interrupted"].includes(jobState)) return "stopped";
  if (event.stage === currentStage) {
    if (jobState === "running") return "running";
    if (jobState === "cancelling") return "stopping";
  }
  return "started";
}

export function KnowledgeJobStages({ events = [], jobState, currentStage }: {
  events?: KnowledgeStageEvent[]; jobState: string; currentStage: string;
}) {
  const stages = new Map<string, KnowledgeStageEvent>();
  for (const event of events) stages.set(event.stage, event);
  const meaningful = [...stages.values()].filter(event => !["checking", "starting", "saving", "complete"].includes(event.stage));
  if (!meaningful.length) return null;
  return <ul aria-label="Processing stages" className="mt-2 space-y-1 text-xs text-ink-soft">
    {meaningful.map(event => <li key={event.stage} className="break-words">
      {event.stage.replaceAll("_", " ")} · {stageState(event, jobState, currentStage)}{event.total > 0 && ` · ${event.completed}/${event.total}`}
      {event.detail.reason && ` · ${event.detail.reason}`}{event.detail.destination && ` · ${event.detail.destination}`}
      {event.detail.error && <span className="block text-fail">{event.detail.error}</span>}
    </li>)}
  </ul>;
}
