"use client";

import { useRouter } from "next/navigation";
import { useEffect, useId, useRef, useState } from "react";

import { ProviderSelector } from "@/components/provider-selector";
import { ApiError, type GenerationProvider, generateDocument } from "@/lib/api";
import { PROVIDER_NAMES } from "@/lib/ai-settings";

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
  const [provider, setProvider] = useState<GenerationProvider>("ollama");
  const activeMessage = useRef<string | null>(null);

  useEffect(() => {
    activeMessage.current = messageId;
    return () => { activeMessage.current = null; };
  }, [messageId]);

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
    generateDocument(messageId, asked, provider).then(
      (document) => {
        // Generation still saves the document after leaving this message. Only
        // navigate while its action remains open in the current workspace.
        if (activeMessage.current !== messageId) return;
        router.push(`/documents?d=${encodeURIComponent(document.id)}`);
      },
      (cause: unknown) => {
        if (activeMessage.current !== messageId) return;
        setPending(false);
        setError(
          cause instanceof ApiError ? cause.message : "Could not draft that document.",
        );
      },
    );
  };

  return (
    <div className="mt-2.5 rounded-md border border-edge-strong bg-canvas px-2.5 py-2">
      <ProviderSelector value={provider} onChange={setProvider} disabled={pending} task="document" />
      <p className="mb-2 text-[12px] text-ink-soft">
        Local Ollama drafts use the saved answer and any saved source excerpts.
        Cloud drafts use the answer and source names only; saved excerpts stay local.
        Older answers without saved excerpts use the answer and references only.
      </p>
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
          if (event.key === "Enter" && !event.nativeEvent.isComposing && event.keyCode !== 229) {
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
          {pending
            ? provider === "ollama" ? "The local model is writing it." : `${PROVIDER_NAMES[provider]} is writing it.`
            : "Takes about as long as an answer."}
        </span>
      </div>
      {pending && <p className="mt-1.5 text-[11.5px] text-ink-faint">If you leave, the saved draft will be available in Documents.</p>}
    </div>
  );
}
