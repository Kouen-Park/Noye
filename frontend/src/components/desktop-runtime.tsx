"use client";

import { invoke, isTauri } from "@tauri-apps/api/core";
import { useEffect, useState, useSyncExternalStore, type ReactNode } from "react";

import { getRuntimeServices, type RuntimeServices } from "@/lib/api";
import { setDesktopBaseUrl } from "@/lib/runtime";
import { DesktopSetupDialog, useSetupGuide } from "./desktop-setup";

interface BackendStatus {
  state: "starting" | "ready" | "failed";
  url: string | null;
  error: string | null;
}

const subscribe = () => () => {};
const clientMode = () => isTauri() ? "desktop" : "web";
const serverMode = () => "starting";

/** No API-using children mount until the app's own backend is ready. */
export function DesktopRuntime({ children }: { children: ReactNode }) {
  const mode = useSyncExternalStore(subscribe, clientMode, serverMode);
  const [state, setState] = useState<"starting" | "ready" | "failed">("starting");
  const [error, setError] = useState("");

  useEffect(() => {
    if (!isTauri()) {
      return;
    }
    let stopped = false;
    let timer: ReturnType<typeof setTimeout>;
    let invokeTimer: ReturnType<typeof setTimeout>;
    const deadline = Date.now() + 30_000;
    async function check() {
      try {
        const status = await Promise.race([
          invoke<BackendStatus>("backend_status"),
          new Promise<never>((_, reject) => {
            invokeTimer = setTimeout(() => reject(new Error(
              "Noye is not responding. Quit the app and reopen it.",
            )), 5_000);
          }),
        ]).finally(() => clearTimeout(invokeTimer));
        if (stopped) return;
        if (status.state === "failed") throw new Error(status.error ?? "Noye could not start.");
        if (status.state === "ready" && status.url) {
          setDesktopBaseUrl(status.url);
          setState("ready");
        } else if (Date.now() > deadline) {
          throw new Error("The backend is taking too long to start. Quit Noye and try again.");
        } else {
          timer = setTimeout(check, 300);
        }
      } catch (cause) {
        if (!stopped) {
          setError(cause instanceof Error ? cause.message : "Noye could not start its backend.");
          setState("failed");
        }
      }
    }
    void check();
    return () => { stopped = true; clearTimeout(timer); clearTimeout(invokeTimer); };
  }, []);

  if (mode === "web") return children;
  if (state === "ready") return <DesktopWorkspace>{children}</DesktopWorkspace>;
  return (
    <main className="mx-auto flex min-h-screen max-w-lg flex-col justify-center gap-3 p-8">
      <h1 className="text-3xl">{state === "failed" ? "Noye could not start" : "Starting Noye"}</h1>
      <p role={state === "failed" ? "alert" : "status"} className="text-ink-soft">
        {state === "failed" ? error : "Opening your local workspace…"}
      </p>
      {state === "failed" && <p className="text-sm text-ink-soft">Quit and reopen the app. Your saved files and conversations are unchanged.</p>}
    </main>
  );
}

function DesktopWorkspace({ children }: { children: ReactNode }) {
  const setup = useSetupGuide();
  return <>
    <DesktopServices onSetup={setup.show} />
    {setup.storageWarning && <p role="status" className="px-5 py-2 text-xs text-ink-soft">Could not remember this guide&apos;s dismissal. It may reopen on your next launch.</p>}
    {children}
    {setup.open && <DesktopSetupDialog onClose={setup.close} />}
  </>;
}

function DesktopServices({ onSetup }: { onSetup: () => void }) {
  const [services, setServices] = useState<RuntimeServices | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout>;
    async function check() {
      try {
        const result = await getRuntimeServices(controller.signal);
        if (!controller.signal.aborted) { setServices(result); setFailed(false); }
      } catch {
        if (!controller.signal.aborted) setFailed(true);
      }
      if (!controller.signal.aborted) timer = setTimeout(check, 15_000);
    }
    void check();
    return () => { controller.abort(); clearTimeout(timer); };
  }, []);

  const needsAttention = failed || (!!services && !Object.values(services).every(Boolean));
  const missing = services ? [
    !services.ollama ? "Ollama is not running" : null,
    !services.qdrant ? "Qdrant is not running" : null,
    services.ollama && !services.generation_model ? "the generation model is not installed" : null,
    services.ollama && !services.embedding_model ? "the embedding model is not installed" : null,
  ].filter(Boolean).join("; ") : "";

  return (
    <aside aria-label="Desktop AI setup" className={`flex shrink-0 flex-wrap items-center justify-between gap-x-4 border-b border-edge-strong px-5 text-sm text-ink ${needsAttention ? "bg-accent-wash py-2" : "bg-canvas"}`}>
      {needsAttention ? <p role="status" className="min-w-0 flex-1">
        {failed ? "Could not check local services." : `Local setup needs attention: ${missing}.`}
        {" "}Saved work stays accessible. Search and AI need Qdrant and local embeddings; cloud generation does not replace them.
      </p> : <span className="text-xs text-ink-soft">Local-first workspace</span>}
      <button onClick={(event) => {
        // WebKit does not always focus a pointer-clicked button before showModal.
        event.currentTarget.focus();
        onSetup();
      }} className="min-h-11 shrink-0 px-2 py-2 text-sm font-semibold text-brand">AI setup</button>
    </aside>
  );
}
