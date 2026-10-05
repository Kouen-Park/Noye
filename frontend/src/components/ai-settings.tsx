"use client";

import { useEffect, useId, useRef, useState } from "react";
import { getDesktopSetup, type DesktopSetup, type GenerationProvider } from "@/lib/api";
import { modelRequest, readAiSettings, saveAiSettings, PROVIDER_NAMES, type AiSettings, type CloudProvider, type ModelJob } from "@/lib/ai-settings";
import { ServiceSettings } from "./service-settings";
import { WorkspaceSettings } from "./workspace-settings";
import { RuntimeReadiness } from "./runtime-readiness";

const button = "min-h-11 rounded-md border border-edge-strong px-4 py-2 text-sm font-semibold hover:bg-sunken disabled:opacity-50";
const input = "mt-1 min-h-11 w-full rounded-md border border-edge-strong bg-canvas px-3 text-sm";
const cloudProviders: CloudProvider[] = ["openai", "anthropic", "gemini"];
const catalog = [ { name: "qwen3.5:0.8b", size: "1.0 GB" }, { name: "qwen3.5:2b", size: "2.7 GB" },
  { name: "qwen3.5:4b", size: "3.4 GB" }, { name: "qwen3.5:9b", size: "6.6 GB" } ];
const size = (bytes: number | null) => bytes === null ? "Size unknown" : `${(bytes / 1e9).toFixed(2)} GB`;

/** An overlay keeps the workspace and unsaved chat/document drafts mounted. */
export function AiSettingsDialog({ onClose }: { onClose: () => void }) {
  const id = useId();
  const dialog = useRef<HTMLDialogElement>(null);
  const title = useRef<HTMLHeadingElement>(null);
  const content = useRef<HTMLDivElement>(null);
  const saved = useRef<AiSettings | null>(null);
  const [settings, setSettings] = useState<AiSettings | null>(null);
  const [setup, setSetup] = useState<DesktopSetup | null>(null);
  const [tab, setTab] = useState<"models" | "cloud" | "services" | "workspace">("models");
  const [provider, setProvider] = useState<CloudProvider>("openai");
  const [secret, setSecret] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const [storage, setStorage] = useState("");
  const [confirmed, setConfirmed] = useState(false);
  const [download, setDownload] = useState("qwen3.5:0.8b");
  const [job, setJob] = useState<ModelJob | null>(null);
  const [deleting, setDeleting] = useState<string | null>(null);
  const [deleteName, setDeleteName] = useState("");
  const [removeKey, setRemoveKey] = useState(false);
  const token = settings?.control_token;

  useEffect(() => {
    if (job?.state !== "complete") return;
    let active = true;
    getDesktopSetup().then((snapshot) => { if (active) setSetup(snapshot); }).catch(() => {});
    return () => { active = false; };
  }, [job?.state]);

  useEffect(() => {
    const previous = document.activeElement;
    const element = dialog.current;
    element?.showModal(); title.current?.focus();
    let active = true;
    readAiSettings().then((values) => {
      if (!active) return;
      saved.current = values; setSettings(values); setStorage(values.storage_path);
    }).catch(() => { if (active) setError("Could not load AI settings. Check Keychain access and reopen Settings."); });
    getDesktopSetup().then((snapshot) => {
      if (!active) return;
      setSetup(snapshot);
      if (snapshot.recommendation.generation) setDownload(snapshot.recommendation.generation.name);
    }).catch(() => { if (active) setError("Could not check AI readiness. Workspace backup remains available."); });
    return () => { active = false; element?.close(); if (previous instanceof HTMLElement && previous.isConnected) previous.focus(); };
  }, []);

  useEffect(() => {
    if (!token) return;
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout>;
    async function check() {
      try {
        const result = await modelRequest<ModelJob>({ control_token: token } as AiSettings, "/job", "GET", undefined, controller.signal);
        if (!controller.signal.aborted) setJob(result);
      } catch { /* An explicit operation reports errors; polling does not erase them. */ }
      if (!controller.signal.aborted) timer = setTimeout(check, 1500);
    }
    void check();
    return () => { controller.abort(); clearTimeout(timer); };
  }, [token]);

  async function act(action: () => Promise<unknown>, message: string) {
    setBusy(true); setError(""); setNotice("");
    try {
      await action();
      setSecret(""); setRemoveKey(false); setDeleting(null); setDeleteName("");
      const values = await readAiSettings();
      saved.current = values; setSettings(values); setNotice(message);
      try { setSetup(await getDesktopSetup()); }
      catch { setError("The change was saved, but AI readiness could not be refreshed."); }
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : typeof cause === "string" ? cause : "Could not complete this change.");
    } finally { setBusy(false); }
  }

  const downloading = job?.state === "downloading";
  const preference = (field: "provider" | "ollama_model" | "openai_model" | "anthropic_model" | "gemini_model") => ({ ...saved.current!, [field]: settings![field] });
  const selectedKey = settings?.[`${provider}_configured`];
  const protectedModel = (name: string) => name === settings?.ollama_model || name === `${settings?.ollama_model}:latest`
    || name === setup?.recommendation.embedding_model || name === `${setup?.recommendation.embedding_model}:latest`;

  return <dialog ref={dialog} aria-labelledby={`${id}-title`} onCancel={(event) => { event.preventDefault(); if (!busy) onClose(); }}
    className="m-auto h-[min(48rem,calc(100dvh-2rem))] max-h-[calc(100dvh-2rem)] w-[calc(100%-2rem)] max-w-3xl rounded-lg border border-edge-strong bg-canvas p-0 text-ink backdrop:bg-ink/30">
    <div className="flex h-full min-h-0 flex-col">
      <header className="shrink-0 border-b border-edge-strong px-5 pt-5 sm:px-7">
        <div className="flex items-center justify-between gap-3">
          <div><p className="text-xs text-ink-soft">Your workspace, your AI</p><h2 ref={title} tabIndex={-1} id={`${id}-title`} className="mt-1 text-2xl text-ink-display">AI Settings</h2></div>
          <button className={button} disabled={busy} onClick={onClose}>Close</button>
        </div>
        <p className="mt-2 text-sm text-ink-soft">Manage local models or connect a cloud API. Saved work stays on this computer.</p>
        <div className="mt-4 flex gap-1" aria-label="Settings sections">
          {(["models", "cloud", "services", "workspace"] as const).map((value) => <button key={value} aria-pressed={tab === value} onClick={() => { setTab(value); setSecret(""); setRemoveKey(false); if (content.current) content.current.scrollTop = 0; }}
            className={`min-h-11 border-b-2 px-3 py-2 text-sm font-semibold ${tab === value ? "border-brand text-brand" : "border-transparent text-ink-soft hover:text-ink"}`}>
            {value === "models" ? "Local models" : value === "cloud" ? "Cloud APIs" : value === "services" ? "Services" : "Workspace"}</button>)}
        </div>
      </header>
      <div ref={content} className="min-h-0 flex-1 overflow-y-auto px-5 py-5 sm:px-7">
        {error && <p role="alert" className="mb-4 rounded-md border border-edge-strong bg-card p-3 text-sm text-fail">{error}</p>}
        {notice && <p role="status" className="mb-4 text-sm text-ink-soft">{notice}</p>}
        {!settings && !error && <p role="status">Opening secure settings…</p>}
        {settings && tab === "workspace" && <WorkspaceSettings settings={settings} />}
        {settings && !setup && tab !== "workspace" && <button className={button}
          onClick={() => { setError(""); getDesktopSetup().then(setSetup).catch(() => setError("Could not check AI readiness. Workspace backup remains available.")); }}>
          Refresh AI readiness
        </button>}
        {settings && setup && tab !== "workspace" && <>
          <RuntimeReadiness setup={setup} />
          {tab === "models" && <section aria-label="Local model management" className="space-y-6">
            <div><h3 className="text-lg text-ink-display">Generation model</h3><p className="mt-1 text-sm text-ink-soft">Switching generation models does not rebuild your document index.</p>
              <label className="mt-3 block text-sm font-semibold" htmlFor={`${id}-local`}>Selected local model</label>
              <select id={`${id}-local`} className={input} value={settings.ollama_model} disabled={busy || downloading} onChange={(e) => setSettings({ ...settings, ollama_model: e.target.value })}>
                {!setup.installed_models.some((m) => m.name === settings.ollama_model) && <option value={settings.ollama_model}>{settings.ollama_model} · not confirmed installed</option>}
                {setup.installed_models.filter((m) => !m.name.startsWith("embeddinggemma") && m.name !== setup.recommendation.embedding_model && m.name !== `${setup.recommendation.embedding_model}:latest`).map((m) => <option key={m.name}>{m.name}</option>)}
              </select>
              <button className={`${button} mt-3`} disabled={busy || downloading} onClick={() => act(() => saveAiSettings(preference("ollama_model")), "Local model preference saved.")}>Save local model</button>
            </div>
            <div className="border-t border-edge-strong pt-5"><h3 className="text-lg text-ink-display">Install a model</h3>
              <p className="mt-1 text-sm text-ink-soft">{setup.recommendation.generation ? `Suggested starting point: ${setup.recommendation.generation.name}.` : "No reliable hardware recommendation yet."} Estimates are not a speed guarantee.</p>
              {setup.recommendation.memory_status === "close_apps" && <p className="mt-2 text-sm text-fail">Available memory is tight. Close other apps before running a local model.</p>}
              <label htmlFor={`${id}-download`} className="mt-3 block text-sm font-semibold">Model to download</label>
              <select id={`${id}-download`} className={input} value={download} disabled={busy || downloading} onChange={(e) => setDownload(e.target.value)}>
                {catalog.map((m) => <option key={m.name} value={m.name}>{m.name} · about {m.size}</option>)}
                <option value={setup.recommendation.embedding_model}>{setup.recommendation.embedding_model} · local embeddings · {size(setup.recommendation.approximate_embedding_download_bytes)}</option>
              </select>
              <label htmlFor={`${id}-storage`} className="mt-3 block text-sm font-semibold">Folder on Ollama&apos;s model-storage volume</label>
              <input id={`${id}-storage`} className={input} value={storage} disabled={busy || downloading} onChange={(e) => { setStorage(e.target.value); setConfirmed(false); }} />
              <label className="mt-2 flex min-h-11 items-start gap-3 py-2 text-sm"><input type="checkbox" className="mt-1 h-4 w-4 shrink-0 accent-brand" checked={confirmed} disabled={busy || downloading} onChange={(e) => setConfirmed(e.target.checked)} />I confirmed this folder is on Ollama&apos;s actual model-storage volume. The suggested home folder may not be correct.</label>
              <button className={`${button} mt-2`} disabled={busy || downloading || !confirmed || !setup.services.ollama} onClick={() => act(async () => setJob(await modelRequest<ModelJob>(settings, "/pull", "POST", { model: download, storage_path: storage, confirmed_storage: confirmed })), "Download requested. The model will not be selected automatically.")}>Download model</button>
              {job && job.state !== "idle" && <div className="mt-4 rounded-md border border-edge-strong bg-card p-3">
                <p role="status" className="break-words text-sm">{job.model} · {job.state}{job.total > 0 && downloading ? ` · current layer ${size(job.completed)} / ${size(job.total)}` : ""}</p>
                {downloading && <><progress className="mt-2 w-full accent-brand" aria-label="Current download layer" max={job.total || 1} value={job.completed} /><button className={`${button} mt-2`} disabled={busy} onClick={() => act(async () => setJob(await modelRequest<ModelJob>(settings, "/cancel", "POST")), "Noye's download request cancelled. Ollama may retain partial files for retry.")}>Cancel download</button></>}
                {job.error && <p role="alert" className="mt-2 text-sm text-fail">{job.error} Use Download model to retry.</p>}
              </div>}
            </div>
            <div className="border-t border-edge-strong pt-5"><h3 className="text-lg text-ink-display">Installed models</h3><p className="mt-1 text-sm text-ink-soft">Deleting a model also affects other apps sharing this Ollama installation. The selected model and local embeddings are protected.</p>
              <ul className="mt-3 divide-y divide-edge-strong">{setup.installed_models.map((m) => <li key={m.name} className="flex flex-wrap items-center justify-between gap-3 py-3"><div className="min-w-0"><p className="break-all font-mono text-xs">{m.name}</p><p className="mt-1 text-xs text-ink-soft">{size(m.size_bytes)}{protectedModel(m.name) ? " · protected" : ""}</p></div><button className={`${button} text-fail`} disabled={busy || downloading || protectedModel(m.name)} onClick={() => { setDeleting(m.name); setDeleteName(""); }}>Delete</button></li>)}</ul>
              {deleting && <div className="mt-3 rounded-md border border-edge-strong bg-card p-4"><label className="text-sm" htmlFor={`${id}-delete`}>Type <strong className="break-all">{deleting}</strong> to confirm deletion.</label><input id={`${id}-delete`} className={input} autoComplete="off" value={deleteName} onChange={(e) => setDeleteName(e.target.value)} /><div className="mt-3 flex flex-wrap gap-2"><button className={`${button} text-fail`} disabled={busy || deleteName !== deleting} onClick={() => act(() => modelRequest(settings, "", "DELETE", { model: deleting }), "Model deleted from Ollama.")}>Confirm deletion</button><button className={button} disabled={busy} onClick={() => setDeleting(null)}>Keep model</button></div></div>}
            </div>
          </section>}
          {tab === "cloud" && <section aria-label="Cloud API settings" className="space-y-5">
            <div><h3 className="text-lg text-ink-display">Bring your own API key</h3><p className="mt-1 text-sm text-ink-soft">Keys are stored in macOS Keychain, never in the workspace or browser storage. ChatGPT and Claude subscriptions do not include API usage.</p></div>
            <label className="block text-sm font-semibold">Cloud provider<select className={input} value={provider} disabled={busy} onChange={(e) => { setProvider(e.target.value as CloudProvider); setSecret(""); setRemoveKey(false); }}>{cloudProviders.map((p) => <option key={p} value={p}>{PROVIDER_NAMES[p]} · {settings[`${p}_configured`] ? "key saved" : "not connected"}</option>)}</select></label>
            <div className="rounded-md border border-edge-strong bg-card p-4"><p className="text-sm font-semibold">{PROVIDER_NAMES[provider]} · {selectedKey ? "Key saved" : "No saved key"}</p>
              <label htmlFor={`${id}-cloud-model`} className="mt-3 block text-sm font-semibold">Model identifier</label><input id={`${id}-cloud-model`} className={input} value={settings[`${provider}_model`]} disabled={busy} onChange={(e) => setSettings({ ...settings, [`${provider}_model`]: e.target.value })} spellCheck={false} />
              <label htmlFor={`${id}-key`} className="mt-3 block text-sm font-semibold">{selectedKey ? "Replace API key (optional)" : "API key"}</label><input id={`${id}-key`} type="password" className={input} value={secret} disabled={busy} onChange={(e) => setSecret(e.target.value)} autoComplete="off" spellCheck={false} autoCapitalize="none" />
              <p className="mt-2 text-xs text-ink-soft">A saved key is never shown again. Saving does not send a test request or activate billing.</p>
              <button className={`${button} mt-3`} disabled={busy || (!selectedKey && !secret.trim())} onClick={() => act(() => saveAiSettings(preference(`${provider}_model`), provider, secret || undefined), "Cloud settings saved securely. Model access has not been tested.")}>Save {PROVIDER_NAMES[provider]} settings</button>
              {selectedKey && <div className="mt-3"><button className={`${button} text-fail`} disabled={busy} onClick={() => setRemoveKey(true)}>Remove saved key</button>{removeKey && <div className="mt-3"><p className="text-sm">Remove only Noye&apos;s {PROVIDER_NAMES[provider]} key from Keychain?</p><button className={`${button} mt-2 text-fail`} disabled={busy} onClick={() => act(() => saveAiSettings({ ...settings, provider: settings.provider === provider ? "ollama" : settings.provider }, provider, undefined, true), "Saved API key removed.")}>Confirm key removal</button></div>}</div>}
            </div>
            <label className="block text-sm font-semibold">Default AI for new work<select className={input} value={settings.provider} disabled={busy} onChange={(e) => setSettings({ ...settings, provider: e.target.value as GenerationProvider })}>{(["ollama", ...cloudProviders] as const).map((p) => <option key={p} value={p} disabled={p !== "ollama" && !settings[`${p}_configured`]}>{PROVIDER_NAMES[p]}</option>)}</select></label>
            <button className={button} disabled={busy} onClick={() => act(() => saveAiSettings(preference("provider")), "Default provider saved. Existing AI selections are unchanged.")}>Save default AI</button>
            <p className="text-sm text-ink-soft">Cloud generation sends your question and retrieved excerpts—or document instructions and the saved answer—to the selected provider. Extraction, embeddings and search stay local. Provider pricing and data terms apply; Noye cannot enforce a free tier.</p>
          </section>}
          {tab === "services" && <ServiceSettings settings={settings} services={setup.services} onRefresh={async (signal) => { const snapshot = await getDesktopSetup(signal); if (!signal?.aborted) setSetup(snapshot); }} />}
        </>}
      </div>
      <footer className="shrink-0 border-t border-edge-strong px-5 py-3 text-xs text-ink-soft sm:px-7">Local by default · No automatic cloud fallback · Downloads stop when Noye quits</footer>
    </div>
  </dialog>;
}
