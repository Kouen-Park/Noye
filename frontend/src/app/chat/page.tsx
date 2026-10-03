"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useId, useRef, useState } from "react";

import { AppShell } from "@/components/app-shell";
import { Composer } from "@/components/chat/composer";
import { ConversationList } from "@/components/chat/conversation-list";
import { MessageBubble } from "@/components/chat/message-bubble";
import { PassageList } from "@/components/chat/passages";
import { BookIcon, CrossIcon } from "@/components/icons";
import { ProviderSelector } from "@/components/provider-selector";
import {
  ApiError, type ChatMessage, type ConversationSummary, type GenerationProvider,
  askQuestion, deleteConversation, listConversations, readConversation, renameConversation,
} from "@/lib/api";

export default function ChatPage() {
  // The URL-selected workspace also works in the desktop static export.
  return <Suspense fallback={<AppShell current="Chat" workspace><p className="p-6 text-ink-soft" role="status">Opening chat…</p></AppShell>}><ChatView /></Suspense>;
}

function ChatView() {
  const router = useRouter();
  const conversationId = useSearchParams().get("c");
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [listLoaded, setListLoaded] = useState(false);
  const [listError, setListError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [newSession, setNewSession] = useState(0);
  const [provider, setProvider] = useState<GenerationProvider>("ollama");
  const live = useRef(false);
  const listRequest = useRef(0);
  const selectedId = useRef(conversationId);
  useEffect(() => { selectedId.current = conversationId; }, [conversationId]);

  const refreshList = useCallback(() => {
    const request = ++listRequest.current;
    listConversations().then(
      (result) => {
        if (!live.current || request !== listRequest.current) return;
        setConversations(result);
        setListLoaded(true);
        setListError(null);
      },
      (cause: unknown) => {
        if (!live.current || request !== listRequest.current) return;
        setListLoaded(true);
        setListError(cause instanceof ApiError ? cause.message : "Could not load conversations.");
      },
    );
  }, []);

  useEffect(() => {
    live.current = true;
    refreshList();
    return () => { live.current = false; };
  }, [refreshList]);

  const rename = (id: string, title: string) => {
    if (busy) return;
    renameConversation(id, title).then(refreshList, () => {
      if (live.current) setListError("Could not rename that conversation.");
    });
  };
  const remove = (id: string) => {
    if (busy) return;
    deleteConversation(id).then(() => {
      if (!live.current) return;
      refreshList();
      if (id === selectedId.current) router.replace("/chat");
    }, () => {
      if (live.current) setListError("Could not delete that conversation.");
    });
  };

  return (
    <AppShell current="Chat" workspace sidebar={
      <>
        <ConversationList conversations={conversations} currentId={conversationId}
          loading={!listLoaded} disabled={busy} onRename={rename} onDelete={remove}
          onOpen={(id) => { if (!busy) router.push(`/chat?c=${encodeURIComponent(id)}`); }}
          onNew={() => { if (!busy) { if (conversationId === null) setNewSession((current) => current + 1); else router.push("/chat"); } }} />
        {listError && <div role="alert" className="mt-3 rounded-md border border-fail bg-fail-wash p-3 text-xs text-fail">
          <p>{listError}</p><button type="button" onClick={refreshList} className="mt-1 min-h-11 underline">Retry conversations</button>
        </div>}
      </>
    }>
      {/* A route change creates a fresh controller. Late reads/answers cannot
          populate the next conversation or redirect it back to the old one. */}
      <ConversationWorkspace key={conversationId ?? `new-${newSession}`} conversationId={conversationId}
        title={conversations.find((conversation) => conversation.id === conversationId)?.title}
        provider={provider} onProviderChange={setProvider} busy={busy} onBusyChange={setBusy}
        refreshList={refreshList} />
    </AppShell>
  );
}

function ConversationWorkspace({ conversationId, title, provider, onProviderChange, busy, onBusyChange, refreshList }: {
  conversationId: string | null;
  title?: string;
  provider: GenerationProvider;
  onProviderChange: (provider: GenerationProvider) => void;
  busy: boolean;
  onBusyChange: (busy: boolean) => void;
  refreshList: () => void;
}) {
  const router = useRouter();
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [savedTitle, setSavedTitle] = useState<string | null>(null);
  const [loaded, setLoaded] = useState(conversationId === null);
  const [loading, setLoading] = useState(conversationId !== null);
  const [attempt, setAttempt] = useState(0);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [draft, setDraft] = useState("");
  const [inspecting, setInspecting] = useState<ChatMessage | null>(null);
  const panelId = useId();
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const sourceButton = useRef<HTMLButtonElement | null>(null);
  const live = useRef(false);
  const inFlight = useRef(false);

  useEffect(() => {
    live.current = true;
    return () => { live.current = false; };
  }, []);

  useEffect(() => {
    if (conversationId === null) return;
    const controller = new AbortController();
    readConversation(conversationId, controller.signal).then(
      (conversation) => {
        if (controller.signal.aborted) return;
        setMessages(conversation.messages);
        setSavedTitle(conversation.title);
        setLoaded(true);
        setLoading(false);
      },
      (cause: unknown) => {
        if (controller.signal.aborted) return;
        setLoading(false);
        setError(cause instanceof ApiError ? cause.message : "Could not open that conversation.");
      },
    );
    return () => controller.abort();
  }, [conversationId, attempt]);

  useEffect(() => {
    const reduced = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
    scrollRef.current?.scrollTo?.({ top: scrollRef.current.scrollHeight, behavior: reduced ? "auto" : "smooth" });
  }, [messages.length, pending]);

  const ask = (question: string) => {
    if (inFlight.current || busy || !loaded) return;
    inFlight.current = true;
    setPending(true);
    onBusyChange(true);
    setError(null);
    const provisional: ChatMessage = {
      id: `pending-${Date.now()}`, role: "user", content: question, error: null,
      citations: [], created_at: new Date().toISOString(),
    };
    setMessages((current) => [...current, provisional]);
    // Do not abort generation: the backend saves the turn even if the user
    // leaves. Only mounted workspace state/navigation may consume its result.
    askQuestion(question, conversationId ?? undefined, provider).then(
      (response) => {
        refreshList();
        if (!live.current) return;
        setMessages((current) => [...current.filter((message) => message.id !== provisional.id), response.question, response.answer]);
        if (conversationId === null) router.replace(`/chat?c=${encodeURIComponent(response.conversation_id)}`);
      },
      (cause: unknown) => {
        refreshList();
        if (!live.current) return;
        setMessages((current) => current.filter((message) => message.id !== provisional.id));
        setDraft((current) => current.trim() === "" ? question : current);
        setError(cause instanceof ApiError ? cause.message : "Could not ask that question.");
      },
    ).finally(() => {
      inFlight.current = false;
      onBusyChange(false);
      if (live.current) setPending(false);
    });
  };

  const closePassages = () => {
    setInspecting(null);
    sourceButton.current?.focus();
  };
  const heading = title ?? savedTitle ?? (conversationId ? "Conversation" : "New conversation");

  return (
    <>
      <header className="shrink-0 border-b border-edge px-5 py-3 md:px-7">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between lg:gap-8">
          <div className="min-w-0 pt-1">
            <p className="mb-1 text-[11px] font-semibold tracking-[0.1em] text-ink-soft uppercase">Research chat</p>
            <h1 className="line-clamp-2 text-xl md:text-[23px]" title={heading}>{heading}</h1>
          </div>
          <div className="min-w-0 lg:w-[350px] lg:shrink-0">
            <ProviderSelector value={provider} onChange={onProviderChange} disabled={busy} compact />
          </div>
        </div>
      </header>

      <div className="flex min-h-0 flex-1 flex-col xl:flex-row">
        <section className="flex min-h-0 min-w-0 flex-1 flex-col" aria-label="Conversation">
          <div ref={scrollRef} className="min-h-0 flex-1 overflow-y-auto overscroll-contain px-5 md:px-8">
            <div className="mx-auto max-w-[720px] py-5">
              {error && <div role="alert" className="mb-4 rounded-lg border border-fail bg-fail-wash p-4 text-sm text-fail">
                <p>{error}</p>
                {!loaded && !loading && <button type="button" onClick={() => { setError(null); setLoading(true); setAttempt((current) => current + 1); }} className="mt-2 min-h-11 underline">Retry opening conversation</button>}
              </div>}
              {loading ? <p role="status" className="py-8 text-sm text-ink-soft">Opening conversation…</p> :
                loaded && messages.length === 0 ? <div className="py-6 md:py-14">
                  <BookIcon className="mb-5 h-8 w-8 text-brand" />
                  <h2 className="max-w-[18ch] font-display text-[32px] leading-tight md:text-[40px]">Your files.<br />A clearer picture.</h2>
                  <p className="mt-4 max-w-[48ch] text-[14px] leading-relaxed text-ink-soft">Ask a question, connect ideas, or find a detail. Noye searches your library and keeps the passages close by.</p>
                  <div className="mt-6 flex flex-col gap-2 sm:flex-row">
                    {["What are the main ideas in these files?", "Compare the approaches in my documents."].map((question) => (
                      <button key={question} type="button" disabled={busy} onClick={() => { setDraft(question); inputRef.current?.focus(); }}
                        className="min-h-11 rounded-lg border border-edge-strong px-3 py-2 text-left text-[13px] text-ink hover:bg-card disabled:opacity-60">{question}</button>
                    ))}
                  </div>
                  <p className="mt-4 text-xs text-ink-soft">Nothing in your library yet? <Link href="/library" className="inline-flex min-h-11 items-center font-semibold text-brand underline underline-offset-4">Add your first file</Link></p>
                </div> : null}
              <ul aria-label="Messages">
                {messages.map((message) => <MessageBubble key={message.id} message={message} panelId={panelId}
                  inspected={inspecting?.id === message.id} onInspect={(selected, button) => { sourceButton.current = button; setInspecting(selected); }} />)}
                {pending && <li className="py-5" role="status"><p className="text-[12px] font-semibold text-brand">Noye</p><p className="mt-2 text-sm text-ink-soft">Waiting for {provider === "gemini" ? "Gemini" : "Ollama"}…</p><p className="mt-1 text-xs text-ink-soft">Your question is being processed. The answer will appear here.</p></li>}
              </ul>
            </div>
          </div>
          <footer className="shrink-0 px-4 pt-2 pb-3 md:px-8 md:pb-4">
            <div className="mx-auto max-w-[720px]">
              {busy && !pending && <p role="status" className="mb-2 text-xs text-ink-soft">An answer is still being saved in another conversation.</p>}
              <Composer onAsk={ask} pending={pending} disabled={!loaded || (busy && !pending)} value={draft} onChange={setDraft} inputRef={inputRef} />
              <p className="mt-2 text-center text-[11px] leading-relaxed text-ink-soft">Each question searches your files. Earlier turns are not sent to the model.</p>
            </div>
          </footer>
        </section>
        {inspecting && <PassagePanel id={panelId} message={inspecting} onClose={closePassages} />}
      </div>
    </>
  );
}

function PassagePanel({ id, message, onClose }: { id: string; message: ChatMessage; onClose: () => void }) {
  const closeRef = useRef<HTMLButtonElement>(null);
  useEffect(() => { closeRef.current?.focus(); }, []);
  return (
    <aside id={id} aria-label="Passages consulted" onKeyDown={(event) => { if (event.key === "Escape") { event.preventDefault(); onClose(); } }}
      className="order-first max-h-[45%] shrink-0 overflow-y-auto border-b border-edge-strong bg-canvas p-4 xl:order-last xl:max-h-none xl:w-[300px] xl:border-b-0 xl:border-l xl:p-5">
      <div className="flex items-center justify-between gap-2">
        <h2 className="text-lg">Passages consulted</h2>
        <button ref={closeRef} type="button" onClick={onClose} aria-label="Close passages"
          className="grid h-11 w-11 shrink-0 place-items-center rounded-md border border-edge-strong text-ink-soft hover:bg-card"><CrossIcon className="h-4 w-4" /></button>
      </div>
      <p className="mt-2 text-xs leading-relaxed text-ink-soft">Retrieved context for this answer, not verified support. Open the originals to check the details.</p>
      <PassageList citations={message.citations} />
      <p className="mt-4 text-xs leading-relaxed text-ink-soft">Saved references remain here if a file is deleted; its original will no longer open.</p>
    </aside>
  );
}
