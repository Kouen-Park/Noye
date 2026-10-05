"use client";

import { useEffect, useId, useRef, useState } from "react";

import { type AiProvider, type GenerationProvider, listAiProviders } from "@/lib/api";
import { isDesktopRuntime } from "@/lib/runtime";
import { AI_SETTINGS_EVENT, OPEN_AI_SETTINGS_EVENT, PROVIDER_NAMES, readAiSettings } from "@/lib/ai-settings";

export function ProviderSelector({
  value,
  onChange,
  disabled = false,
  task = "chat",
  compact = false,
}: {
  value: GenerationProvider;
  onChange: (provider: GenerationProvider) => void;
  disabled?: boolean;
  task?: "chat" | "document";
  compact?: boolean;
}) {
  const id = useId();
  const [providers, setProviders] = useState<AiProvider[] | null>(null);
  const [error, setError] = useState(false);
  const changed = useRef(false);
  const changeHandler = useRef(onChange);
  useEffect(() => { changeHandler.current = onChange; }, [onChange]);

  useEffect(() => {
    const controller = new AbortController();
    const refresh = () => listAiProviders(controller.signal).then(
      (result) => { if (!controller.signal.aborted) { setProviders(result); setError(false); } },
      () => { if (!controller.signal.aborted) setError(true); },
    );
    void refresh();
    window.addEventListener(AI_SETTINGS_EVENT, refresh);
    if (isDesktopRuntime()) readAiSettings().then((settings) => {
      if (!controller.signal.aborted && !changed.current && (settings.provider === "ollama" || settings[`${settings.provider}_configured`])) changeHandler.current(settings.provider);
    }).catch(() => {});
    return () => { controller.abort(); window.removeEventListener(AI_SETTINGS_EVENT, refresh); };
  }, []);

  const gemini = providers?.find((provider) => provider.id === "gemini");
  const ollama = providers?.find((provider) => provider.id === "ollama");
  const cloudName = { gemini: "Google", openai: "OpenAI", anthropic: "Anthropic" }[value as "gemini" | "openai" | "anthropic"];

  return (
    <div className={compact ? "min-w-0" : "mb-3 rounded-md border border-edge-strong bg-card px-3 py-2"}>
      <label htmlFor={id} className="block text-[12px] font-semibold text-ink-soft">
        AI for {task === "chat" ? "this chat" : "this document"}
      </label>
      <select
        id={id}
        value={value}
        disabled={disabled}
        aria-describedby={`${id}-help`}
        onChange={(event) => { changed.current = true; onChange(event.target.value as GenerationProvider); }}
        className="mt-1 min-h-11 w-full rounded-md border border-edge-strong bg-canvas px-2 text-sm disabled:opacity-60"
      >
        <option value="ollama">Ollama · Local{ollama ? ` · ${ollama.model}` : ""}</option>
        <option value="gemini" disabled={!gemini?.configured}>
          Gemini · Cloud API{gemini ? ` · ${gemini.model}` : ""}
        </option>
        {(["openai", "anthropic"] as const).map((id) => {
          const provider = providers?.find((p) => p.id === id);
          return <option key={id} value={id} disabled={!provider?.configured}>{PROVIDER_NAMES[id]} · Cloud API{provider ? ` · ${provider.model}` : ""}</option>;
        })}
      </select>
      <p id={`${id}-help`} className="mt-1.5 text-[12px] text-ink-soft">
        {value !== "ollama"
          ? task === "chat"
            ? `Your question and retrieved document excerpts will be sent to ${cloudName}. Files, embeddings and search stay local.`
            : `Your instruction, saved answer and cited file names will be sent to ${cloudName}. The document is saved locally.`
          : "Generation runs locally through Ollama. Your content is not sent to Google or other cloud AI providers."}
      </p>
      {value === "gemini" && (
        <p className="mt-1 text-[12px] text-ink-soft">
          Free-tier content may be used to improve Google products. Avoid confidential material.
          {" "}<a className="underline" href="https://ai.google.dev/gemini-api/terms" target="_blank" rel="noreferrer">Data terms</a>.
          {" "}Your API project determines billing; Noye cannot enforce a free tier.
        </p>
      )}
      {isDesktopRuntime() && <button className="min-h-11 py-2 text-[12px] font-semibold text-brand" onClick={(event) => { event.currentTarget.focus(); window.dispatchEvent(new Event(OPEN_AI_SETTINGS_EVENT)); }}>Manage models and API keys in Settings</button>}
      {!isDesktopRuntime() && providers !== null && !gemini?.configured && (compact ? (
        <details className="mt-1 text-[12px] text-ink-soft">
          <summary className="min-h-11 cursor-pointer py-3">Gemini setup</summary>
          <p>{isDesktopRuntime()
            ? "Manage API keys in Settings."
            : "To enable Gemini, set GEMINI_API_KEY in the project's .env and restart the backend. Keep the key out of frontend settings."}</p>
        </details>
      ) : (
        <p className="mt-1 text-[12px] text-ink-soft">
          {isDesktopRuntime()
            ? "Manage API keys in Settings."
            : "To enable Gemini, set GEMINI_API_KEY in the project's .env and restart the backend. Keep the key out of frontend settings."}
        </p>
      ))}
      {error && (
        <p className="mt-1 text-[12px] text-fail" role="status">
          Could not check AI configuration. Your AI selection has not changed. Reload to try again.
        </p>
      )}
    </div>
  );
}
