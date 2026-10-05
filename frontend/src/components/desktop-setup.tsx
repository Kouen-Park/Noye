"use client";

import { useEffect, useId, useRef, useState, useSyncExternalStore } from "react";

import { getDesktopSetup, type DesktopSetup } from "@/lib/api";

const SEEN_KEY = "noye.desktop.setup-guide.v1";
const SEEN_EVENT = "noye-setup-guide-seen";

function readSeen() {
  try { return localStorage.getItem(SEEN_KEY) === "seen"; } catch { return false; }
}

function subscribeSeen(listener: () => void) {
  window.addEventListener("storage", listener);
  window.addEventListener(SEEN_EVENT, listener);
  return () => {
    window.removeEventListener("storage", listener);
    window.removeEventListener(SEEN_EVENT, listener);
  };
}

/** Only dismissal is remembered. This is not provider/model configuration. */
export function useSetupGuide() {
  const seen = useSyncExternalStore(subscribeSeen, readSeen, () => true);
  const [requested, setRequested] = useState(false);
  const [dismissed, setDismissed] = useState(false);
  const [storageWarning, setStorageWarning] = useState(false);
  return {
    open: requested || (!seen && !dismissed),
    storageWarning,
    show: () => setRequested(true),
    close: () => {
      try {
        localStorage.setItem(SEEN_KEY, "seen");
        window.dispatchEvent(new Event(SEEN_EVENT));
      } catch { setStorageWarning(true); }
      setRequested(false);
      setDismissed(true);
    },
  };
}

function memory(bytes: number | null) {
  return bytes === null ? "Not available" : `${(bytes / 2 ** 30).toFixed(1)} GiB`;
}

function download(bytes: number | null) {
  return bytes === null ? "Size unknown" : `about ${(bytes / 1e9).toFixed(2)} GB`;
}

const actionClass = "min-h-11 rounded-md border border-edge-strong px-4 py-2 text-sm hover:bg-sunken";

export function DesktopSetupDialog({ onClose, onSettings }: { onClose: () => void; onSettings?: () => void }) {
  const id = useId();
  const dialog = useRef<HTMLDialogElement>(null);
  const heading = useRef<HTMLHeadingElement>(null);
  const [data, setData] = useState<DesktopSetup | null>(null);
  const [error, setError] = useState("");
  const [attempt, setAttempt] = useState(0);
  const [path, setPath] = useState<"local" | "cloud">("local");

  function refresh() {
    setError(""); setData(null); setAttempt((value) => value + 1);
  }

  useEffect(() => {
    const element = dialog.current;
    const previousFocus = document.activeElement;
    element?.showModal();
    heading.current?.focus();
    return () => {
      element?.close();
      if (previousFocus instanceof HTMLElement && previousFocus.isConnected) previousFocus.focus();
    };
  }, []);

  useEffect(() => {
    let active = true;
    const controller = new AbortController();
    const timer = setTimeout(() => {
      controller.abort();
      if (active) setError("The setup check took too long. Try again, or continue to your saved work.");
    }, 10_000);
    getDesktopSetup(controller.signal).then(
      (result) => { if (active && !controller.signal.aborted) setData(result); },
      () => {
        if (active && !controller.signal.aborted) {
          setError("Could not check this computer. Try again, or continue to your saved work.");
        }
      },
    ).finally(() => clearTimeout(timer));
    return () => { active = false; controller.abort(); clearTimeout(timer); };
  }, [attempt]);

  return (
    <dialog
      ref={dialog}
      aria-labelledby={`${id}-title`}
      onCancel={(event) => { event.preventDefault(); onClose(); }}
      className="m-auto h-[min(55rem,calc(100dvh-2rem))] max-h-[calc(100dvh-2rem)] w-[calc(100%-2rem)] max-w-3xl rounded-lg border border-edge-strong bg-canvas p-0 text-ink backdrop:bg-ink/30"
    >
      <div className="flex h-full min-h-0 flex-col">
      <header className="shrink-0 border-b border-edge-strong px-5 pt-5 pb-3 sm:px-8 sm:pt-8">
        <p className="text-xs font-semibold uppercase tracking-widest text-accent-ink">Noye · AI setup</p>
        <div className="mt-2 flex flex-wrap items-center justify-between gap-2">
          <h2 ref={heading} id={`${id}-title`} tabIndex={-1} className="text-[27px] text-ink-display">
            AI on your computer
          </h2>
          <button onClick={onClose} className={`${actionClass} shrink-0`}>Skip for now</button>
        </div>
        <p className="mt-2 text-sm text-ink-soft">
          Start small, keep your work local, and choose cloud generation only when you want it.
          Nothing is installed or changed by this guide.
        </p>
        <button onClick={() => { if (data || error) refresh(); }} aria-disabled={!data && !error} className="mt-2 min-h-11 py-2 text-sm font-semibold text-brand aria-disabled:opacity-60">Check again</button>
      </header>
      <div className="min-h-0 flex-1 overflow-y-auto px-5 sm:px-8">
      {!data && !error && <p role="status" className="py-8 text-sm">Checking memory, storage and local services…</p>}
      {error && <div className="py-6">
        <p role="alert" className="text-sm text-fail">{error}</p>
        <button className={`${actionClass} mt-3`} onClick={refresh}>Try setup check again</button>
      </div>}
      {data && <>
        <HardwareSummary data={data} />
        <fieldset className="my-5">
          <legend className="mb-2 text-sm font-semibold">Choose a setup guide</legend>
          <div className="grid gap-2 sm:grid-cols-2">
            {(["local", "cloud"] as const).map((value) => (
              <label key={value} className={`flex min-h-14 cursor-pointer items-center gap-3 rounded-md border border-edge-strong p-3 text-sm ${path === value ? "bg-accent-wash" : "bg-card"}`}>
                <input type="radio" className="h-4 w-4 accent-brand" name={`${id}-path`} checked={path === value} onChange={() => setPath(value)} />
                <span><strong className="block">{value === "local" ? "Local AI" : "Gemini API"}</strong>
                  <span className="text-xs text-ink-soft">{value === "local" ? "Private generation through Ollama" : "Optional cloud generation"}</span>
                </span>
              </label>
            ))}
          </div>
        </fieldset>
        {path === "local" ? <LocalGuide data={data} /> : <CloudGuide configured={data.gemini_configured} />}
        <details className="mt-5 border-t border-edge-strong pt-2 text-sm">
          <summary className="min-h-11 cursor-pointer py-3">Installed Ollama models ({data.installed_models.length})</summary>
          {!data.services.ollama ? <p className="text-ink-soft">Could not read the Ollama model inventory.</p>
            : data.installed_models.length === 0 ? <p>No models are installed.</p>
              : <ul className="space-y-2">{data.installed_models.map((model) => (
                <li key={model.name} className="flex flex-wrap justify-between gap-2">
                  <span className="break-all font-mono text-xs">{model.name}</span>
                  <span className="text-xs text-ink-soft">{download(model.size_bytes)}</span>
                </li>
              ))}</ul>}
        </details>
      </>}
      </div>
      <footer className="shrink-0 border-t border-edge-strong px-5 py-4 sm:px-8">
        {onSettings && <button onClick={onSettings} className="mr-2 min-h-11 rounded-md bg-brand px-5 py-2 text-sm font-semibold text-ink-inverse">Open AI Settings</button>}
        <button onClick={onClose} className={actionClass}>
          Continue to workspace
        </button>
        <p className="mt-2 text-xs text-ink-soft">This does not mark AI as ready. Reopen this guide with AI setup at any time.</p>
      </footer>
      </div>
    </dialog>
  );
}

function HardwareSummary({ data }: { data: DesktopSetup }) {
  const { hardware } = data;
  return <section aria-label="Computer measurements" className="mt-5">
    <p className="text-sm font-semibold">{hardware.os === "Darwin" ? "macOS" : hardware.os} · {hardware.architecture}</p>
    <dl className="mt-3 grid grid-cols-2 gap-x-4 gap-y-3 text-sm sm:grid-cols-4">
      {[
        ["Total memory", memory(hardware.total_memory_bytes)],
        ["Available estimate", memory(hardware.available_memory_bytes)],
        ["Workspace disk free", memory(hardware.workspace_disk_free_bytes)],
        ["Logical CPUs", hardware.logical_cpus?.toString() ?? "Not available"],
      ].map(([label, value]) => <div key={label}>
        <dt className="text-xs text-ink-soft">{label}</dt><dd className="mt-1 font-mono text-xs">{value}</dd>
      </div>)}
    </dl>
    <p className="mt-3 text-xs text-ink-soft">{hardware.acceleration === "apple_silicon_candidate"
      ? "Apple Silicon detected. Metal acceleration is a candidate, not verified in this check."
      : "Inference acceleration is not verified. Only the smallest model is considered."}</p>
  </section>;
}

function LocalGuide({ data }: { data: DesktopSetup }) {
  const { recommendation, services } = data;
  const model = recommendation.generation;
  const installed = !!model && data.installed_models.some((item) => item.name === model.name);
  return <section aria-label="Local AI guide">
    <h3 className="text-lg text-ink-display">{model ? "A conservative starting point" : "No reliable local recommendation yet"}</h3>
    {model && <p className="mt-2 text-sm"><strong className="font-mono">{model.name}</strong>
      {" · "}{download(model.approximate_download_bytes)} download{installed ? " · Already installed" : " · Not installed"}.
    </p>}
    <p className="mt-2 text-sm text-ink-soft">
      Smaller models use less memory but may give weaker answers. These are Noye estimates for short document questions, not a speed or quality benchmark.
    </p>
    {recommendation.memory_status === "close_apps" && model && <p role="status" className="mt-3 text-sm text-fail">
      Memory is tight right now. Close other apps and check again; this candidate budgets {memory(model.estimated_working_memory_bytes)} of available memory for models and runtime overhead.
    </p>}
    {recommendation.memory_status === "unknown" && <p className="mt-3 text-sm">Available memory could not be confirmed. Model fit is unknown.</p>}
    {recommendation.memory_status === "insufficient_total" && <p className="mt-3 text-sm">Detected total memory is below Noye&apos;s conservative 8 GiB starting threshold. Cloud generation still needs local embeddings and search.</p>}
    {recommendation.workspace_disk_status === "low" && <p className="mt-3 text-sm text-fail">Workspace disk space is low for a fresh model download plus reserve space.</p>}
    <p className="mt-2 text-xs text-ink-soft">Ollama may store models on another disk. Its actual model-storage space must be checked before downloading.</p>
    <dl className="mt-4 space-y-2 border-t border-edge-strong pt-4 text-sm">
      <div><dt className="inline font-semibold">Ollama: </dt><dd className="inline">{services.ollama ? "Model inventory available" : "Unavailable — open or install Ollama yourself"}.</dd></div>
      <div><dt className="inline font-semibold">Current generation: </dt><dd className="inline break-words">{data.configured_generation_model} · {services.generation_model ? "Installed" : "Not confirmed installed"}.</dd></div>
      <div><dt className="inline font-semibold">Local embeddings: </dt><dd className="inline break-words">{recommendation.embedding_model} · {download(recommendation.approximate_embedding_download_bytes)} · {services.embedding_model ? "Installed" : "Not confirmed installed"}.</dd></div>
      <div><dt className="inline font-semibold">Qdrant: </dt><dd className="inline">{services.qdrant ? "Reachable" : "Unavailable — requires separate setup"}.</dd></div>
    </dl>
    <p className="mt-3 text-sm text-ink-soft">Your active model is unchanged by this guide. Open AI Settings to download, select or delete models. Embeddings remain fixed to protect your index.</p>
    <p className="mt-3 text-xs text-ink-soft">
      <a href="https://ollama.com/download" target="_blank" rel="noreferrer" className="inline-flex min-h-11 items-center underline">Ollama installation</a>
      {model && <> · <a href={model.source_url} target="_blank" rel="noreferrer" className="inline-flex min-h-11 items-center underline">Model details</a></>}
      {" · "}Sizes checked {recommendation.catalog_checked_on}; model tags can change.
    </p>
  </section>;
}

function CloudGuide({ configured }: { configured: boolean }) {
  return <section aria-label="Gemini setup guide">
    <h3 className="text-lg text-ink-display">Use Gemini for generation</h3>
    <p className="mt-2 text-sm">{configured
      ? "A Gemini key is already configured in the backend. Select Gemini in the chat or document AI selector when you want to use it."
      : "No Gemini key is configured. Open AI Settings to securely save a Gemini API key in macOS Keychain."}</p>
    <p className="mt-3 text-sm text-ink-soft">Chat sends your question, bounded recent user questions and retrieved excerpts to Google. Document drafting sends your instruction, saved answer and cited file names. Files, embeddings and search stay local, so Ollama embeddings and Qdrant are still needed.</p>
    <p className="mt-3 text-sm text-ink-soft">Free-tier content may be used to improve Google products. Avoid confidential material. Your API project controls billing; Noye cannot enforce free-only usage.</p>
    <p className="mt-3 text-sm text-ink-soft">Opening this guide does not select Gemini, send content, validate your key or activate billing. There is no automatic cloud fallback.</p>
    <a href="https://ai.google.dev/gemini-api/terms" target="_blank" rel="noreferrer" className="mt-3 inline-flex min-h-11 items-center text-sm underline">Google data terms</a>
  </section>;
}
