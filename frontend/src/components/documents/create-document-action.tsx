"use client";

import { useRouter } from "next/navigation";
import { useId, useState } from "react";

import { ApiError, generateDocument } from "@/lib/api";

/**
 * Turning an answer into a document.
 *
 * The instruction is asked for rather than assumed. "Make a document from this" has
 * no single meaning — revision notes, a summary, a table — and the instruction is
 * what makes the draft useful as well as what titles it. Offering examples rather
 * than a dropdown keeps it open-ended, since the model takes any instruction.
 *
 * Drafting takes about as long as answering did, so the wait is stated instead of
 * hidden. On success the page navigates to the new document, because the point of
 * the action is to go and edit it.
 */

const EXAMPLES = [
  "Turn this into revision notes",
  "Summarise this in three bullets",
  "Rewrite this as a step-by-step guide",
];

export function CreateDocumentAction({ messageId }: { messageId: string }) {
  const router = useRouter();
  const inputId = useId();
  const [open, setOpen] = useState(false);
  const [instruction, setInstruction] = useState("");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!open) {
    return (
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="mt-2.5 min-h-11 rounded-md border border-edge-strong px-2.5 text-[12px] font-semibold text-accent-ink hover:bg-brand-wash md:min-h-0 md:py-1"
      >
        Create document
      </button>
    );
  }

  const submit = () => {
    const asked = instruction.trim();
    if (asked === "" || pending) return;
    setPending(true);
    setError(null);
    generateDocument(messageId, asked).then(
      (document) => {
        // Navigate rather than clear: the reason to make a document is to work on
        // it, and leaving the person in chat would make them go looking.
        router.push(`/documents?d=${encodeURIComponent(document.id)}`);
      },
      (cause: unknown) => {
        setPending(false);
        setError(
          cause instanceof ApiError ? cause.message : "Could not draft that document.",
        );
      },
    );
  };

  return (
    <div className="mt-2.5 rounded-md border border-edge-strong bg-canvas px-2.5 py-2">
      <label htmlFor={inputId} className="block text-[12px] font-semibold text-ink-soft">
        What should this become?
      </label>
      <input
        id={inputId}
        autoFocus
        value={instruction}
        disabled={pending}
        onChange={(event) => setInstruction(event.target.value)}
        onKeyDown={(event) => {
          if (event.key === "Enter") {
            event.preventDefault();
            submit();
          }
          if (event.key === "Escape") setOpen(false);
        }}
        placeholder="Turn this into revision notes"
        className="mt-1 min-h-11 w-full rounded-md border border-edge-strong bg-card px-2.5 text-[13.5px] placeholder:text-ink-faint disabled:opacity-60"
      />

      {!pending && (
        <div className="mt-1.5 flex flex-wrap gap-1.5">
          {EXAMPLES.map((example) => (
            <button
              key={example}
              type="button"
              onClick={() => setInstruction(example)}
              className="rounded-full border border-edge px-2 py-0.5 text-[11.5px] text-ink-soft hover:border-brand hover:text-ink"
            >
              {example}
            </button>
          ))}
        </div>
      )}

      {error !== null && <p className="mt-1.5 text-[12px] text-fail">{error}</p>}

      <div className="mt-2 flex items-center gap-2">
        <button
          type="button"
          onClick={submit}
          disabled={pending || instruction.trim() === ""}
          className="min-h-11 rounded-md bg-brand px-3 text-[12.5px] font-semibold text-ink-inverse disabled:cursor-not-allowed disabled:opacity-60 md:min-h-0 md:py-1.5"
        >
          {pending ? "Writing…" : "Create"}
        </button>
        <button
          type="button"
          onClick={() => setOpen(false)}
          disabled={pending}
          className="min-h-11 rounded-md border border-edge-strong px-3 text-[12.5px] text-ink-soft md:min-h-0 md:py-1.5"
        >
          Cancel
        </button>
        <span className="text-[11.5px] text-ink-faint">
          {pending ? "The local model is writing it." : "Takes about as long as an answer."}
        </span>
      </div>
    </div>
  );
}
