"use client";

import { useEffect, useId, useState } from "react";

import { type AiProvider, type GenerationProvider, listAiProviders } from "@/lib/api";

export function ProviderSelector({
  value,
  onChange,
  disabled = false,
  task = "chat",
}: {
  value: GenerationProvider;
  onChange: (provider: GenerationProvider) => void;
  disabled?: boolean;
  task?: "chat" | "document";
}) {
  const id = useId();
  const [providers, setProviders] = useState<AiProvider[] | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    listAiProviders(controller.signal).then(
      (result) => { if (!controller.signal.aborted) setProviders(result); },
      () => { if (!controller.signal.aborted) setError(true); },
    );
    return () => controller.abort();
  }, []);

  const gemini = providers?.find((provider) => provider.id === "gemini");
  const ollama = providers?.find((provider) => provider.id === "ollama");

  return (
    <div className="mb-3 rounded-md border border-edge-strong bg-card px-3 py-2">
      <label htmlFor={id} className="block text-[12px] font-semibold text-ink-soft">
        AI for {task === "chat" ? "this chat" : "this document"}
      </label>
      <select
        id={id}
        value={value}
        disabled={disabled}
        aria-describedby={`${id}-help`}
        onChange={(event) => onChange(event.target.value as GenerationProvider)}
        className="mt-1 min-h-11 w-full rounded-md border border-edge-strong bg-canvas px-2 text-sm disabled:opacity-60"
      >
        <option value="ollama">Ollama · Local{ollama ? ` · ${ollama.model}` : ""}</option>
        <option value="gemini" disabled={!gemini?.configured}>
          Gemini · Cloud API{gemini ? ` · ${gemini.model}` : ""}
        </option>
      </select>
      <p id={`${id}-help`} className="mt-1.5 text-[12px] text-ink-soft">
        {value === "gemini"
          ? task === "chat"
            ? "Your question and retrieved document excerpts will be sent to Google. Files, embeddings and search stay local."
            : "Your instruction, saved answer and cited file names will be sent to Google. The document is saved locally."
          : "Generation runs locally through Ollama. Your content is not sent to Google."}
      </p>
      {value === "gemini" && (
        <p className="mt-1 text-[12px] text-ink-soft">
          Free-tier content may be used to improve Google products. Avoid confidential material.
          {" "}<a className="underline" href="https://ai.google.dev/gemini-api/terms" target="_blank" rel="noreferrer">Data terms</a>.
          {" "}Your API project determines billing; Noye cannot enforce a free tier.
        </p>
      )}
      {providers !== null && !gemini?.configured && (
        <p className="mt-1 text-[12px] text-ink-soft">
          To enable Gemini, set GEMINI_API_KEY in the project&apos;s .env and restart the backend.
          Keep the key out of frontend settings.
        </p>
      )}
      {error && (
        <p className="mt-1 text-[12px] text-fail" role="status">
          Could not check Gemini configuration. Local mode is still selected. Reload to try again.
        </p>
      )}
    </div>
  );
}
