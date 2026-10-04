import { invoke } from "@tauri-apps/api/core";
import { apiBaseUrl } from "./runtime";
import type { GenerationProvider } from "./api";

export const AI_SETTINGS_EVENT = "noye-ai-settings-changed";
export const OPEN_AI_SETTINGS_EVENT = "noye-open-ai-settings";
export const PROVIDER_NAMES = { ollama: "Ollama · Local", openai: "OpenAI (ChatGPT)", anthropic: "Claude", gemini: "Gemini" };
export type CloudProvider = Exclude<GenerationProvider, "ollama">;
export interface AiSettings {
  provider: GenerationProvider;
  ollama_model: string;
  openai_model: string;
  anthropic_model: string;
  gemini_model: string;
  openai_configured: boolean;
  anthropic_configured: boolean;
  gemini_configured: boolean;
  control_token: string;
  storage_path: string;
}
export interface ModelJob {
  state: "idle" | "downloading" | "complete" | "cancelled" | "failed";
  model: string;
  completed: number;
  total: number;
  error: string | null;
}
export function readAiSettings() { return invoke<AiSettings>("ai_settings"); }
export async function saveAiSettings(settings: AiSettings, provider?: CloudProvider, credential?: string, removeKey = false) {
  // Whitelist preferences: neither the control capability nor key-availability
  // flags can ever be written into the native preferences file.
  const values = { provider: settings.provider, ollama_model: settings.ollama_model,
    openai_model: settings.openai_model, anthropic_model: settings.anthropic_model, gemini_model: settings.gemini_model };
  await invoke("save_ai_settings", { values, credentialProvider: provider ?? null,
    credential: credential ?? null, removeKey });
  window.dispatchEvent(new Event(AI_SETTINGS_EVENT));
}
export async function modelRequest<T>(settings: AiSettings, path: string, method = "GET", body?: object, signal?: AbortSignal): Promise<T> {
  const response = await fetch(`${apiBaseUrl()}/models${path}`, { method, signal,
    headers: { "X-Noye-Control": settings.control_token, "Content-Type": "application/json" },
    ...(body ? { body: JSON.stringify(body) } : {}) });
  if (!response.ok) {
    const result = await response.json().catch(() => null);
    throw new Error(typeof result?.detail === "string" ? result.detail : "Model operation failed. Try again.");
  }
  return response.json();
}
