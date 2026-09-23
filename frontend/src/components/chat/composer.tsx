"use client";

import { useId, useState } from "react";

/**
 * The question box.
 *
 * A textarea rather than an input, because a question about one's own documents
 * is often a sentence or two. Enter sends; Shift+Enter makes a newline, which is
 * the convention people already expect from a chat box.
 *
 * The field is cleared only after the send succeeds in being dispatched, so a
 * rejected question is not lost from the box.
 */

interface ComposerProps {
  onAsk: (question: string) => void;
  pending: boolean;
  /** Disabled while a conversation is loading, or when the backend is unreachable. */
  disabled?: boolean;
}

export function Composer({ onAsk, pending, disabled = false }: ComposerProps) {
  const inputId = useId();
  const [value, setValue] = useState("");
  const blocked = pending || disabled;

  const send = () => {
    const question = value.trim();
    if (question === "" || blocked) return;
    onAsk(question);
    setValue("");
  };

  return (
    <form
      onSubmit={(event) => {
        event.preventDefault();
        send();
      }}
      className="mt-4 border-t border-edge pt-3"
    >
      <label htmlFor={inputId} className="block text-[13px] font-semibold text-ink-soft">
        Ask about your documents
      </label>
      <div className="mt-1.5 flex flex-wrap items-end gap-2">
        <textarea
          id={inputId}
          rows={2}
          value={value}
          disabled={disabled}
          onChange={(event) => setValue(event.target.value)}
          onKeyDown={(event) => {
            // Enter sends, Shift+Enter breaks the line.
            if (event.key === "Enter" && !event.shiftKey) {
              event.preventDefault();
              send();
            }
          }}
          placeholder="What do these files say about…"
          className="min-h-11 min-w-0 flex-1 resize-y rounded-md border border-edge-strong bg-card px-3 py-2 text-[14.5px] placeholder:text-ink-faint disabled:opacity-60"
        />
        <button
          type="submit"
          disabled={blocked || value.trim() === ""}
          className="min-h-11 rounded-md bg-brand px-5 text-[13.5px] font-semibold text-ink-inverse disabled:cursor-not-allowed disabled:opacity-60"
        >
          {pending ? "Thinking…" : "Ask"}
        </button>
      </div>
      <p className="mt-1.5 text-[12px] text-ink-faint">
        Answers come from your own files, on this machine. A local model can take a
        while.
      </p>
    </form>
  );
}
