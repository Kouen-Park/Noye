"use client";

import { useState } from "react";

import type { ConversationSummary } from "@/lib/api";
import { PlusIcon } from "@/components/icons";

/**
 * Past conversations, most recently active first.
 *
 * Renaming is inline rather than in a dialog: the title was derived from the
 * first question, so correcting it is a small edit next to the thing being
 * edited. Deleting asks first, because it cannot be undone — but it says plainly
 * that only the discussion goes, since a user has no way to know from the button
 * whether their documents are at risk.
 */

interface ConversationListProps {
  conversations: ConversationSummary[];
  currentId: string | null;
  onOpen: (id: string) => void;
  onRename: (id: string, title: string) => void;
  onDelete: (id: string) => void;
  onNew: () => void;
  disabled?: boolean;
  loading?: boolean;
}

export function ConversationList({
  conversations,
  currentId,
  onOpen,
  onRename,
  onDelete,
  onNew,
  disabled = false,
  loading = false,
}: ConversationListProps) {
  const [editing, setEditing] = useState<string | null>(null);
  const [draft, setDraft] = useState("");
  const [confirming, setConfirming] = useState<string | null>(null);

  return (
    <fieldset disabled={disabled} aria-label="Conversations" className="min-w-0 disabled:opacity-60">
        <button
          type="button"
          onClick={onNew}
          data-navigation
          className="flex min-h-11 w-full items-center gap-2 rounded-md border border-edge-strong bg-canvas px-3 text-sm font-semibold text-brand hover:bg-brand-wash disabled:cursor-not-allowed"
        >
          <PlusIcon className="h-4 w-4" />New chat
        </button>
        <p className="mt-5 px-2 text-[12px] font-semibold text-ink-soft">Recent conversations</p>

      {loading ? <p role="status" className="mt-2 px-2 text-xs text-ink-soft">Loading conversations…</p> : conversations.length === 0 ? (
        <p className="mt-2 text-[12.5px] text-ink-soft">Nothing asked yet.</p>
      ) : (
        <ul className="mt-2 space-y-1">
          {conversations.map((conversation) => {
            const isCurrent = conversation.id === currentId;

            if (editing === conversation.id) {
              return (
                <li key={conversation.id}>
                  <form
                    onSubmit={(event) => {
                      event.preventDefault();
                      const title = draft.trim();
                      if (title !== "") onRename(conversation.id, title);
                      setEditing(null);
                    }}
                    className="flex min-h-11 gap-1.5"
                  >
                    <input
                      autoFocus
                      value={draft}
                      aria-label="Conversation title"
                      onChange={(event) => setDraft(event.target.value)}
                      onKeyDown={(event) => {
                        if (event.key === "Escape") setEditing(null);
                      }}
                      className="min-w-0 flex-1 rounded-md border border-edge-strong bg-card px-2 py-1.5 text-[12.5px]"
                    />
                    <button
                      type="submit"
                      className="rounded-md bg-brand px-2 text-[12px] font-semibold text-ink-inverse"
                    >
                      Save
                    </button>
                  </form>
                </li>
              );
            }

            if (confirming === conversation.id) {
              return (
                <li
                  key={conversation.id}
                  className="rounded-md bg-fail-wash px-2.5 py-2 text-[12.5px]"
                >
                  <p className="text-fail">
                    Delete this conversation? Your files are not affected.
                  </p>
                  <div className="mt-1.5 flex gap-2">
                    <button
                      type="button"
                      autoFocus
                      onClick={() => {
                        onDelete(conversation.id);
                        setConfirming(null);
                      }}
                      className="min-h-11 rounded-md bg-fail px-2.5 py-1 text-[12px] font-semibold text-ink-inverse"
                    >
                      Delete
                    </button>
                    <button
                      type="button"
                      onClick={() => setConfirming(null)}
                      className="min-h-11 rounded-md border border-edge-strong px-2.5 py-1 text-[12px] text-ink-soft"
                    >
                      Keep
                    </button>
                  </div>
                </li>
              );
            }

            return (
              <li key={conversation.id} className="group flex items-stretch gap-1">
                <button
                  type="button"
                  onClick={() => onOpen(conversation.id)}
                  data-navigation
                  aria-current={isCurrent ? "true" : undefined}
                  // Named explicitly, like the Edit and Delete controls beside
                  // it: the visible text already includes the message count, so
                  // without this the three controls for one row are hard to tell
                  // apart when navigating by control.
                  aria-label={`Open ${conversation.title}`}
                  className={`min-h-11 min-w-0 flex-1 rounded-md px-2.5 py-2 text-left text-[13px] ${
                    isCurrent
                      ? "bg-card font-semibold text-ink shadow-[inset_2.5px_0_0_var(--brand)]"
                      : "text-ink-soft hover:bg-card hover:text-ink"
                  }`}
                >
                  <span className="block truncate" title={conversation.title}>
                    {conversation.title}
                  </span>
                  <span className="font-mono text-[10.5px] tabular-nums text-ink-soft">
                    {conversation.message_count}{" "}
                    {conversation.message_count === 1 ? "message" : "messages"}
                  </span>
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setDraft(conversation.title);
                    setEditing(conversation.id);
                  }}
                  aria-label={`Rename ${conversation.title}`}
                  className="min-h-11 min-w-11 rounded-md px-1.5 text-[11px] text-ink-soft hover:bg-canvas hover:text-ink"
                >
                  Edit
                </button>
                <button
                  type="button"
                  onClick={() => setConfirming(conversation.id)}
                  aria-label={`Delete ${conversation.title}`}
                  className="min-h-11 min-w-11 rounded-md px-1.5 text-[11px] text-ink-soft hover:bg-canvas hover:text-fail"
                >
                  ✕
                </button>
              </li>
            );
          })}
        </ul>
      )}
    </fieldset>
  );
}
