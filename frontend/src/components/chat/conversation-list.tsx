"use client";

import { useState } from "react";

import type { ConversationSummary } from "@/lib/api";

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
}

export function ConversationList({
  conversations,
  currentId,
  onOpen,
  onRename,
  onDelete,
  onNew,
}: ConversationListProps) {
  const [editing, setEditing] = useState<string | null>(null);
  const [draft, setDraft] = useState("");
  const [confirming, setConfirming] = useState<string | null>(null);

  return (
    <div>
      <div className="flex items-center justify-between gap-2">
        <h2 className="text-[11px] font-bold uppercase tracking-[0.09em] text-ink-faint">
          Conversations
        </h2>
        <button
          type="button"
          onClick={onNew}
          className="min-h-11 rounded-md border border-edge-strong px-2.5 text-[12.5px] font-semibold text-accent-ink hover:bg-brand-wash md:min-h-0 md:py-1"
        >
          New
        </button>
      </div>

      {conversations.length === 0 ? (
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
                    className="flex gap-1.5"
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
                      className="rounded-md bg-fail px-2.5 py-1 text-[12px] font-semibold text-canvas"
                    >
                      Delete
                    </button>
                    <button
                      type="button"
                      onClick={() => setConfirming(null)}
                      className="rounded-md border border-edge-strong px-2.5 py-1 text-[12px] text-ink-soft"
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
                  aria-current={isCurrent ? "true" : undefined}
                  // Named explicitly, like the Edit and Delete controls beside
                  // it: the visible text already includes the message count, so
                  // without this the three controls for one row are hard to tell
                  // apart when navigating by control.
                  aria-label={`Open ${conversation.title}`}
                  className={`min-h-11 min-w-0 flex-1 rounded-md px-2.5 text-left text-[13px] md:min-h-0 md:py-1.5 ${
                    isCurrent
                      ? "bg-card font-semibold text-ink shadow-[inset_2.5px_0_0_var(--brand)]"
                      : "text-ink-soft hover:bg-card hover:text-ink"
                  }`}
                >
                  <span className="block truncate" title={conversation.title}>
                    {conversation.title}
                  </span>
                  <span className="font-mono text-[10.5px] tabular-nums text-ink-faint">
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
                  className="rounded-md px-1.5 text-[11px] text-ink-faint hover:text-ink"
                >
                  Edit
                </button>
                <button
                  type="button"
                  onClick={() => setConfirming(conversation.id)}
                  aria-label={`Delete ${conversation.title}`}
                  className="rounded-md px-1.5 text-[11px] text-ink-faint hover:text-fail"
                >
                  ✕
                </button>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
