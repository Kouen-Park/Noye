"use client";

import { useSyncExternalStore } from "react";
import { ApiError, type AskResponse, type GenerationProvider } from "@/lib/api";

interface Completion { conversationId: string; turn?: AskResponse }
interface ChatSession {
  draft: string;
  scope: string[] | null;
  documentMode: boolean;
  collectionMode: boolean;
  pending: { kind: "answer" | "document"; provider: GenerationProvider; question: string } | null;
  completion: Completion | null;
  error: string | null;
}
const EMPTY: ChatSession = { draft: "", scope: null, documentMode: false, collectionMode: false, pending: null, completion: null, error: null };
// Session memory outlives route components, but is never written to disk or
// replayed after an app restart. Completion never navigates an unmounted page.
const sessions = new Map<string, ChatSession>();
const listeners = new Set<() => void>();
const subscribe = (listener: () => void) => { listeners.add(listener); return () => { listeners.delete(listener); }; };
export const chatSessionKey = (id: string | null) => id ? `conversation:${id}` : "new";
export const readChatSession = (key: string) => sessions.get(key) ?? EMPTY;
const busy = () => [...sessions.values()].some(session => session.pending !== null);
function write(key: string, patch: Partial<ChatSession>) {
  sessions.set(key, { ...readChatSession(key), ...patch });
  listeners.forEach(listener => listener());
}
export function useChatSession(key: string) {
  return useSyncExternalStore(subscribe, () => readChatSession(key), () => EMPTY);
}
export function useChatBusy() { return useSyncExternalStore(subscribe, busy, () => false); }
export function setChatDraft(key: string, draft: string) { write(key, { draft }); }
export function setChatOptions(key: string, options: Partial<Pick<ChatSession, "scope" | "documentMode" | "collectionMode">>) { write(key, options); }
export function clearNewChat() { sessions.delete("new"); listeners.forEach(listener => listener()); }
export function resetChatSessions() { sessions.clear(); listeners.forEach(listener => listener()); }

export async function submitChatRequest(key: string, kind: "answer" | "document", provider: GenerationProvider,
  question: string, run: () => Promise<Completion>) {
  if (busy()) return;
  write(key, { pending: { kind, provider, question }, completion: null, error: null });
  try {
    const completion = await run();
    const next = { ...readChatSession(key), pending: null, completion };
    sessions.set(key, next);
    if (key === "new") sessions.set(chatSessionKey(completion.conversationId), next);
    listeners.forEach(listener => listener());
  } catch (cause) {
    const session = readChatSession(key);
    write(key, { pending: null, draft: session.draft.trim() ? session.draft : question,
      error: cause instanceof ApiError ? cause.message : kind === "answer" ? "Could not ask that question." : "Could not start document generation." });
  }
}
