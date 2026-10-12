import type { DesktopSetup } from "@/lib/api";

export function RuntimeReadiness({ setup }: { setup: DesktopSetup }) {
  const ready = setup.readiness;
  if (!ready) return null;
  return <section aria-label="AI readiness" className="mb-5 rounded-md border border-edge-strong bg-card p-4 text-sm">
    <h3 className="font-semibold">AI readiness</h3>
    <p className="mt-2">Configured local model: {setup.configured_generation_model}</p>
    <p>Local generation: {ready.local_generation_available ? "service running and model installed" : "needs setup"}</p>
    <p>Indexing and search services: {ready.indexing_available ? "available" : "needs setup"}</p>
    {ready.reasons.length > 0 && <ul className="mt-2 list-inside list-disc text-ink-soft">
      {ready.reasons.map((reason) => <li key={reason}>{reason}</li>)}
    </ul>}
    <p className="mt-2 text-ink-soft">
      Cloud keys: {Object.entries(ready.cloud_configuration).filter(([, saved]) => saved).map(([name]) => name).join(", ") || "none saved"}.
      {" "}Saved keys do not confirm API access; no paid test request is sent.
    </p>
    <p className="mt-2 text-ink-soft">Local request limits: {ready.context_tokens} context tokens,
      {" "}{ready.output_tokens} output tokens; conservative input limit {ready.input_byte_limit} UTF-8 bytes.
      Shorten oversized requests; source text is never silently trimmed.</p>
  </section>;
}
