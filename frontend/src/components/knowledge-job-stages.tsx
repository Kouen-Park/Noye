export interface KnowledgeStageEvent {
  sequence: number; stage: string; state: string; completed: number; total: number;
  detail: { reason?: string; error?: string; destination?: string };
}

export function KnowledgeJobStages({ events = [] }: { events?: KnowledgeStageEvent[] }) {
  const stages = new Map<string, KnowledgeStageEvent>();
  for (const event of events) stages.set(event.stage, event);
  const meaningful = [...stages.values()].filter(event => !["checking", "starting", "saving", "complete"].includes(event.stage));
  if (!meaningful.length) return null;
  return <ul aria-label="Processing stages" className="mt-2 space-y-1 text-xs text-ink-soft">
    {meaningful.map(event => <li key={event.stage} className="break-words">
      {event.stage.replaceAll("_", " ")} · {event.state}{event.total > 0 && ` · ${event.completed}/${event.total}`}
      {event.detail.reason && ` · ${event.detail.reason}`}{event.detail.destination && ` · ${event.detail.destination}`}
      {event.detail.error && <span className="block text-fail">{event.detail.error}</span>}
    </li>)}
  </ul>;
}
