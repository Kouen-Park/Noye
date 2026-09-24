"use client";

import { useEffect, useId, useRef, useState } from "react";

import { DocumentPreview } from "@/components/documents/document-preview";

/**
 * The editor.
 *
 * Write and Preview are tabs rather than a split pane: at 390px a split pane gives
 * each half too little room to be either, and the document is the thing being
 * worked on rather than a thing being watched.
 *
 * Saving is manual, with an explicit state. Autosave was tempting and rejected: a
 * local model's output is long, edits here are substantial rather than incremental,
 * and an autosave that fired mid-thought would make undo the user's problem. What
 * autosave usually protects against — losing work by navigating away — is handled
 * by warning instead.
 */

type Tab = "write" | "preview";

interface DocumentEditorProps {
  title: string;
  content: string;
  /** Saves both, and resolves when the server has it. */
  onSave: (patch: { title: string; content: string }) => Promise<void>;
  saving: boolean;
  /** Reported up because PDF export needs the rendered document on screen. */
  onViewChange?: (view: Tab) => void;
}

export function DocumentEditor({
  title,
  content,
  onSave,
  saving,
  onViewChange,
}: DocumentEditorProps) {
  const bodyId = useId();
  const titleId = useId();
  const [tab, setTab] = useState<Tab>("write");
  const [draftTitle, setDraftTitle] = useState(title);
  const [draftContent, setDraftContent] = useState(content);
  const textarea = useRef<HTMLTextAreaElement>(null);

  const dirty = draftTitle !== title || draftContent !== content;

  // Warn before losing unsaved work. The browser's own dialog, because a custom
  // one cannot block navigation.
  useEffect(() => {
    if (!dirty) return;
    const warn = (event: BeforeUnloadEvent) => event.preventDefault();
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [dirty]);

  const save = () => {
    if (!dirty || saving) return;
    void onSave({ title: draftTitle.trim() || title, content: draftContent });
  };

  return (
    <div>
      <div className="flex flex-wrap items-end gap-2">
        <div className="min-w-0 flex-1">
          <label htmlFor={titleId} className="block text-[12px] font-semibold text-ink-soft">
            Title
          </label>
          <input
            id={titleId}
            value={draftTitle}
            onChange={(event) => setDraftTitle(event.target.value)}
            className="mt-1 min-h-11 w-full rounded-md border border-edge-strong bg-card px-2.5 text-[14.5px]"
          />
        </div>
        <button
          type="button"
          onClick={save}
          disabled={!dirty || saving}
          className="min-h-11 rounded-md bg-brand px-4 text-[13.5px] font-semibold text-ink-inverse disabled:cursor-not-allowed disabled:opacity-60"
        >
          {saving ? "Saving…" : dirty ? "Save" : "Saved"}
        </button>
      </div>

      <div
        role="tablist"
        aria-label="Editor view"
        className="mt-4 flex gap-1 border-b border-edge"
      >
        {(["write", "preview"] as const).map((value) => (
          <button
            key={value}
            role="tab"
            type="button"
            aria-selected={tab === value}
            onClick={() => {
              setTab(value);
              onViewChange?.(value);
            }}
            className={`min-h-11 rounded-t-md px-3 text-[13px] md:min-h-0 md:py-2 ${
              tab === value
                ? "border-b-2 border-brand font-semibold text-ink"
                : "text-ink-soft hover:text-ink"
            }`}
          >
            {value === "write" ? "Write" : "Preview"}
          </button>
        ))}
        {dirty && (
          <span className="ml-auto self-center text-[12px] text-ink-faint">
            Unsaved changes
          </span>
        )}
      </div>

      <div className="mt-3">
        {tab === "write" ? (
          <>
            <label htmlFor={bodyId} className="sr-only">
              Document content, in Markdown
            </label>
            <textarea
              id={bodyId}
              ref={textarea}
              value={draftContent}
              onChange={(event) => setDraftContent(event.target.value)}
              onKeyDown={(event) => {
                // The shortcut people already have in their fingers.
                if ((event.metaKey || event.ctrlKey) && event.key === "s") {
                  event.preventDefault();
                  save();
                }
              }}
              spellCheck
              placeholder="# Your document&#10;&#10;Markdown works here."
              className="min-h-[420px] w-full resize-y rounded-md border border-edge-strong bg-card p-3 font-mono text-[13.5px] leading-relaxed placeholder:text-ink-faint"
            />
            <p className="mt-1.5 text-[12px] text-ink-faint">
              Markdown. ⌘S saves.
            </p>
          </>
        ) : (
          <DocumentPreview content={draftContent} />
        )}
      </div>
    </div>
  );
}
