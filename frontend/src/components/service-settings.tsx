"use client";

import { useEffect, useRef, useState } from "react";
import { desktopServiceRequest, type AiSettings, type DesktopServiceStatus } from "@/lib/ai-settings";
import type { RuntimeServices } from "@/lib/api";

const button = "min-h-11 rounded-md border border-edge-strong px-4 py-2 text-sm font-semibold transition-colors hover:bg-sunken disabled:opacity-50";
const names = { ollama: "Ollama", qdrant: "Qdrant" };

/** Preparation survives closing this panel; only quitting cancels its app-owned job. */
export function ServiceSettings({ settings, services, onRefresh }: {
  settings: AiSettings;
  services: RuntimeServices;
  onRefresh: (signal?: AbortSignal) => Promise<void>;
}) {
  const [status, setStatus] = useState<DesktopServiceStatus | null>(null);
  const [confirmed, setConfirmed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [pollFailed, setPollFailed] = useState(false);
  const [notice, setNotice] = useState("");
  const refresh = useRef(onRefresh);
  const previous = useRef<DesktopServiceStatus | null>(null);
  const lifetime = useRef<AbortController | null>(null);

  useEffect(() => { refresh.current = onRefresh; }, [onRefresh]);
  useEffect(() => {
    const controller = new AbortController();
    lifetime.current = controller;
    let timer: ReturnType<typeof setTimeout>;
    async function check() {
      try {
        const snapshot = await desktopServiceRequest<DesktopServiceStatus>(settings, "", "GET", undefined, controller.signal);
        if (controller.signal.aborted) return;
        setStatus(snapshot); setPollFailed(false);
        if (previous.current && (snapshot.ollama.state !== previous.current.ollama.state || snapshot.qdrant.state !== previous.current.qdrant.state)) {
          await refresh.current(controller.signal);
        }
        previous.current = snapshot;
      } catch {
        if (!controller.signal.aborted) setPollFailed(true);
      }
      if (!controller.signal.aborted) timer = setTimeout(check, 3000);
    }
    void check();
    return () => { controller.abort(); clearTimeout(timer); };
    // The capability is stable for this backend session; preference edits do not restart polling.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [settings.control_token]);

  async function request(path: string, body?: object) {
    setBusy(true); setError(""); setNotice("");
    const signal = lifetime.current?.signal;
    try {
      if (path === "/docker" || path === "/guide") {
        await desktopServiceRequest(settings, path, "POST", body, signal);
        if (!signal?.aborted) setNotice(path === "/guide" ? "Installation guide opened in your browser. No installer was run." : "Docker Desktop opened. Wait for its engine, then start Qdrant. Noye will not close Docker.");
      } else {
        const snapshot = await desktopServiceRequest<DesktopServiceStatus>(settings, path, body ? "POST" : "GET", body, signal);
        if (signal?.aborted) return;
        previous.current = snapshot; setStatus(snapshot);
        setPollFailed(false);
        if (!body) await refresh.current(signal);
      }
    } catch (cause) {
      if (!signal?.aborted) setError(cause instanceof Error ? cause.message : "Could not prepare this service. Try again.");
    } finally { if (!signal?.aborted) setBusy(false); }
  }

  const preparing = status?.ollama.state === "starting" || status?.qdrant.state === "starting";
  return <section aria-label="Local service management">
    <h3 className="text-lg text-ink-display">Local services</h3>
    <p className="mt-1 text-pretty text-sm text-ink-soft">Cloud generation still needs local embeddings and search. Start services only when you need them.</p>
    {error && <p role="alert" className="mt-4 text-sm text-fail">{error}</p>}
    {pollFailed && <p role="alert" className="mt-4 text-sm text-fail">Could not refresh local services. Try Refresh status.</p>}
    {notice && <p role="status" className="mt-4 text-sm text-ink-soft">{notice}</p>}
    {!status && !error && !pollFailed && <p role="status" className="mt-4 text-sm text-ink-soft">Checking service ownership…</p>}
    {!status && (error || pollFailed) && <button className={`${button} mt-4`} disabled={busy} onClick={() => request("")}>Refresh status</button>}
    {status && <>
      <dl className="mt-5 divide-y divide-edge-strong">
        {(["ollama", "qdrant"] as const).map((service) => {
          const item = status[service];
          return <div key={service} className="py-4">
            <dt className="flex flex-wrap items-center justify-between gap-3">
              <span className="text-sm font-semibold">{names[service]}</span>
              <span className={`text-sm ${item.state === "failed" ? "text-fail" : "text-ink-soft"}`}>
                {item.state === "ready" ? `Running · ${item.ownership === "noye" ? "started by Noye" : item.ownership === "external" ? "external" : "ownership unconfirmed"}` : item.state === "starting" ? "Preparing…" : item.state === "failed" ? "Needs attention" : "Not running"}
              </span>
            </dt>
            <dd>
            <p role={item.state === "starting" || item.state === "failed" ? "status" : undefined} className="mt-2 text-pretty text-sm text-ink-soft">{item.detail}</p>
            {item.state !== "ready" && <button className={`${button} mt-3`} disabled={busy || preparing || !confirmed || !item.can_start}
              onClick={() => request("/start", { service, confirmed })}>
              {item.state === "failed" ? `Retry ${names[service]}` : `Start ${names[service]}`}
            </button>}
            {!item.can_start && item.state !== "ready" && <p className="mt-2 text-sm text-ink-soft">
              <a className="inline-flex min-h-11 items-center font-semibold text-brand underline" href={service === "ollama" ? "https://ollama.com/download/mac" : "https://docs.docker.com/desktop/setup/install/mac-install/"} target="_blank" rel="noreferrer" onClick={(event) => { event.preventDefault(); if (!busy) void request("/guide", { guide: service === "ollama" ? "ollama" : "docker" }); }}>
                {service === "ollama" ? "Ollama installation guide" : "Docker Desktop installation guide"}
              </a>
              {" · Install prerequisites yourself; Noye does not run an installer."}
            </p>}
            </dd>
          </div>;
        })}
      </dl>
      <div className="border-t border-edge-strong pt-4">
        <label className="flex min-h-11 items-start gap-3 py-2 text-pretty text-sm">
          <input type="checkbox" className="mt-1 h-4 w-4 shrink-0 accent-brand" checked={confirmed} disabled={busy || preparing} onChange={(event) => setConfirmed(event.target.checked)} />
          I agree to prepare local services. Qdrant may download its pinned Docker image; no AI model is downloaded here.
        </label>
        <p className="mt-2 text-pretty text-sm text-ink-soft">Qdrant uses a persistent Noye folder and localhost port 6333. If another service already uses that port, it is left untouched. App-owned services stop on quit; external services and Docker stay running.</p>
        <p className="mt-2 text-pretty text-sm text-ink-soft">A new Qdrant store does not copy another server&apos;s vectors. If you previously indexed with a different server, check the stored index in Library and explicitly rebuild it.</p>
        <div className="mt-4 flex flex-wrap gap-2">
          {status.docker_open_available && <button className={button} disabled={busy || preparing || !confirmed} onClick={() => request("/docker", { confirmed })}>Open Docker Desktop</button>}
          <button className={button} disabled={busy} onClick={() => request("")}>Refresh status</button>
        </div>
      </div>
    </>}
    <dl className="mt-6 border-t border-edge-strong pt-2">
      {(["generation_model", "embedding_model"] as const).map((model) => <div key={model} className="flex items-center justify-between gap-3 py-2 text-sm">
        <dt>{model === "generation_model" ? "Local generation model" : "Embedding model"}</dt>
        <dd className={services[model] ? "text-ink-soft" : "text-fail"}>{services[model] ? "Installed" : "Not confirmed installed"}</dd>
      </div>)}
    </dl>
    <p className="mt-2 text-sm text-ink-soft">Install or change models in Local models after Ollama is running. Service readiness does not validate model speed or answer quality.</p>
  </section>;
}
