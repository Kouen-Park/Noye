"use client";

import { useId, useState, type RefObject } from "react";

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
  documentMode?: boolean;
  /** Disabled while a conversation is loading, or when the backend is unreachable. */
  disabled?: boolean;
  value?: string;
  onChange?: (value: string) => void;
  inputRef?: RefObject<HTMLTextAreaElement | null>;
}

export function Composer({ onAsk, pending, documentMode = false, disabled = false, value: controlledValue, onChange, inputRef }: ComposerProps) {
  const inputId = useId();
  const [localValue, setLocalValue] = useState("");
  const value = controlledValue ?? localValue;
  const setValue = onChange ?? setLocalValue;
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
      className="rounded-2xl border border-edge-strong bg-card p-3 shadow-sm"
    >
      <label htmlFor={inputId} className="sr-only">
        Ask about your documents
      </label>
      <div className="flex items-end gap-2">
        <textarea
          ref={inputRef}
          id={inputId}
          rows={2}
          value={value}
          disabled={disabled}
          onChange={(event) => setValue(event.target.value)}
          onKeyDown={(event) => {
            // Enter sends, Shift+Enter breaks the line.
            if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing && event.keyCode !== 229) {
              event.preventDefault();
              send();
            }
          }}
          placeholder="What do these files say about…"
          aria-describedby={`${inputId}-help`}
          className="max-h-40 min-h-11 min-w-0 flex-1 resize-y rounded-md bg-card px-2 py-2 text-[15px] placeholder:text-ink-soft disabled:opacity-60"
        />
        <button
          type="submit"
          disabled={blocked || value.trim() === ""}
          className="min-h-11 shrink-0 rounded-full bg-brand px-4 text-[13px] font-semibold text-ink-inverse hover:bg-brand-hover disabled:cursor-not-allowed disabled:opacity-60"
        >
          {pending ? "Thinking…" : "Ask"}
        </button>
      </div>
      <p id={`${inputId}-help`} className="mt-2 px-2 text-[11px] leading-relaxed text-ink-soft">
        {documentMode ? "Enter to create · Shift+Enter for a new line. Document jobs use local Ollama." : "Enter to ask · Shift+Enter for a new line. Uses your selected AI; local models can take a while."}
      </p>
    </form>
  );
}
