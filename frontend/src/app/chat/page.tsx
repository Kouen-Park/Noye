"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useRef, useState } from "react";

import { AppShell } from "@/components/app-shell";
import { Composer } from "@/components/chat/composer";
import { ConversationList } from "@/components/chat/conversation-list";
import { MessageBubble } from "@/components/chat/message-bubble";
import {
  ApiError,
  type ChatMessage,
  type ConversationSummary,
  askQuestion,
  deleteConversation,
  listConversations,
  readConversation,
  renameConversation,
} from "@/lib/api";

/**
 * Chat: ask questions of your own documents and see what the answer was built
 * from.
 *
 * The open conversation lives in the URL (`/chat?c=…`), matching how `/search`
 * keeps its query there: Back returns to the previous conversation and one can be
 * shared as a link.
 *
 * `useSearchParams` needs a Suspense boundary during prerender — the build fails
 * without one — so the part that reads the URL is its own component.
 */
export default function ChatPage() {
  return (
    <AppShell current="Chat">
      <h1 className="text-[27px]">Chat</h1>
      <p className="mt-1 max-w-[60ch] text-ink-soft">
        Ask about the files you have added. Every answer shows the passages it was
        given, so you can check them yourself.
      </p>

      <Suspense fallback={<p className="mt-7 text-ink-soft">Opening chat…</p>}>
        <ChatView />
      </Suspense>
    </AppShell>
  );
}

function ChatView() {
  const router = useRouter();
  const params = useSearchParams();
  const conversationId = params.get("c");

  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [offline, setOffline] = useState(false);
  /** Which conversation the loaded messages belong to, so a stale load is ignored. */
  const [loadedFor, setLoadedFor] = useState<string | null>(null);

  const endRef = useRef<HTMLDivElement>(null);

  const refreshList = useCallback(() => {
    listConversations().then(setConversations, (cause: unknown) => {
      setOffline(cause instanceof ApiError && cause.isOffline);
      setError(cause instanceof ApiError ? cause.message : "Could not load conversations.");
    });
  }, []);

  useEffect(() => {
    refreshList();
  }, [refreshList]);

  // The URL is the trigger for which conversation is shown. Reading it at render
  // time rather than syncing in an effect: React 19 rejects a synchronous
  // setState inside an effect body.
  if (loadedFor !== conversationId) {
    setLoadedFor(conversationId);
    if (conversationId === null) {
      setMessages([]);
      setError(null);
    } else {
      readConversation(conversationId).then(
        (conversation) => setMessages(conversation.messages),
        (cause: unknown) => {
          setMessages([]);
          setOffline(cause instanceof ApiError && cause.isOffline);
          setError(
            cause instanceof ApiError ? cause.message : "Could not open that conversation.",
          );
        },
      );
    }
  }

  // Keep the newest turn in view as the conversation grows.
  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages.length, pending]);

  const ask = useCallback(
    (question: string) => {
      setPending(true);
      setError(null);

      // The question is shown immediately with a provisional id. The server
      // records it too — this is so a slow local model does not leave the person
      // staring at an empty screen wondering whether it registered.
      const provisional: ChatMessage = {
        id: `pending-${Date.now()}`,
        role: "user",
        content: question,
        error: null,
        citations: [],
        created_at: new Date().toISOString(),
      };
      setMessages((current) => [...current, provisional]);

      askQuestion(question, conversationId ?? undefined).then(
        (response) => {
          setPending(false);
          // Replace the provisional turn with the stored pair, so ids and
          // timestamps come from the server rather than from the client's clock.
          setMessages((current) => [
            ...current.filter((message) => message.id !== provisional.id),
            response.question,
            response.answer,
          ]);
          refreshList();
          if (conversationId === null) {
            // A new conversation: put it in the URL without a history entry, so
            // Back leaves chat rather than returning to a blank composer.
            setLoadedFor(response.conversation_id);
            router.replace(`/chat?c=${encodeURIComponent(response.conversation_id)}`);
          }
        },
        (cause: unknown) => {
          setPending(false);
          setMessages((current) =>
            current.filter((message) => message.id !== provisional.id),
          );
          setOffline(cause instanceof ApiError && cause.isOffline);
          setError(
            cause instanceof ApiError ? cause.message : "Could not ask that question.",
          );
        },
      );
    },
    [conversationId, refreshList, router],
  );

  const open = useCallback(
    (id: string) => router.push(`/chat?c=${encodeURIComponent(id)}`),
    [router],
  );

  const startNew = useCallback(() => router.push("/chat"), [router]);

  const rename = useCallback(
    (id: string, title: string) => {
      renameConversation(id, title).then(refreshList, () =>
        setError("Could not rename that conversation."),
      );
    },
    [refreshList],
  );

  const remove = useCallback(
    (id: string) => {
      deleteConversation(id).then(
        () => {
          refreshList();
          if (id === conversationId) router.replace("/chat");
        },
        () => setError("Could not delete that conversation."),
      );
    },
    [conversationId, refreshList, router],
  );

  return (
    <div className="mt-6 flex flex-col gap-6 lg:flex-row-reverse">
      <div className="lg:w-[240px] lg:shrink-0">
        <ConversationList
          conversations={conversations}
          currentId={conversationId}
          onOpen={open}
          onRename={rename}
          onDelete={remove}
          onNew={startNew}
        />
      </div>

      <div className="min-w-0 flex-1">
        {/* An answer arrives without a page change, so it is announced. */}
        <p role="status" aria-live="polite" className="sr-only">
          {pending ? "Thinking about your question." : ""}
        </p>

        {error !== null && (
          <div className="mb-3 rounded-lg border border-fail bg-fail-wash px-4 py-3">
            <p className="font-semibold text-fail">{error}</p>
            {offline && (
              <p className="mt-1 text-[13px] text-fail">
                Noye keeps your files on this machine, so its backend has to be running.
              </p>
            )}
          </div>
        )}

        {messages.length === 0 && !pending ? (
          <div className="rounded-lg border border-dashed border-edge-strong bg-card px-6 py-12 text-center">
            <p className="font-display text-lg">Ask your first question</p>
            <p className="mx-auto mt-1 max-w-[46ch] text-[13.5px] text-ink-soft">
              Answers are built only from the files you have added, and each one shows
              the passages behind it so you can judge them yourself.
            </p>
          </div>
        ) : (
          <ul>
            {messages.map((message) => (
              <MessageBubble key={message.id} message={message} />
            ))}
            {pending && (
              <li className="mb-3">
                <div className="max-w-[68ch] rounded-lg border border-edge-strong bg-card px-3.5 py-2.5">
                  <p className="noye-pulse text-[14.5px] text-ink-soft">
                    Reading your documents…
                  </p>
                </div>
              </li>
            )}
          </ul>
        )}

        <div ref={endRef} />

        <Composer onAsk={ask} pending={pending} />
      </div>
    </div>
  );
}
