"use client";

import { useEffect, useId, useRef, useState } from "react";

import { DocumentPreview } from "@/components/documents/document-preview";
import { ExportControls } from "@/components/documents/export-controls";
import { documentDraftKey } from "@/lib/document-draft";

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
export interface DocumentPatch { title: string; content: string; expectedRevision?: string; draftOwner?: string }
interface RevisionComparison { title: string; content: string; revisionId: string }

interface DocumentEditorProps {
  title: string;
  content: string;
  /** Saves both, and resolves when the server has it. */
  onSave: (patch: DocumentPatch) => Promise<void>;
  saving: boolean;
  /** Reported up because PDF export needs the rendered document on screen. */
  onViewChange?: (view: Tab) => void;
  documentId?: string;
  provenance?: string;
  readOnly?: boolean;
  exportUrl?: string;
  revisionId?: string;
  onCompareLatest?: () => Promise<RevisionComparison>;
  onReloadLatest?: () => void;
}

export function DocumentEditor({
  title,
  content,
  onSave,
  saving,
  onViewChange,
  documentId,
  provenance = "",
  readOnly = false,
  exportUrl,
  revisionId,
  onCompareLatest,
  onReloadLatest,
}: DocumentEditorProps) {
  const bodyId = useId();
  const titleId = useId();
  const [tab, setTab] = useState<Tab>("write");
  const [draftTitle, setDraftTitle] = useState(title);
  const [draftContent, setDraftContent] = useState(content);
  const [includeProvenance, setIncludeProvenance] = useState(false);
  const [draftReady, setDraftReady] = useState(!documentId || readOnly);
  const [restored, setRestored] = useState(false);
  const [expectedRevision, setExpectedRevision] = useState<string | null>(revisionId ?? null);
  const [reviewRequired, setReviewRequired] = useState(false);
  const [comparison, setComparison] = useState<RevisionComparison | null>(null);
  const [comparing, setComparing] = useState(false);
  const [comparisonError, setComparisonError] = useState<string | null>(null);
  const [baseline, setBaseline] = useState({ title, content });
  const [draftOwner] = useState(() => crypto.randomUUID());
  const textarea = useRef<HTMLTextAreaElement>(null);

  const base = revisionId ? baseline : { title, content };
  const dirty = draftTitle !== base.title || draftContent !== base.content;
  const exportContent = draftContent + (includeProvenance && provenance ? `\n\n${provenance}` : "");

  useEffect(() => {
    if (!documentId || readOnly) return;
    let live = true;
    queueMicrotask(() => {
      if (!live) return;
      try {
        const raw = localStorage.getItem(documentDraftKey(documentId));
        const draft = raw ? JSON.parse(raw) : null;
        if (draft && typeof draft.title === "string" && typeof draft.content === "string"
          && (draft.title !== title || draft.content !== content)) {
          setDraftTitle(draft.title); setDraftContent(draft.content); setRestored(true);
          if (revisionId) {
            const expected = typeof draft.expectedRevision === "string" ? draft.expectedRevision : null;
            setExpectedRevision(expected);
            setReviewRequired(expected !== revisionId);
          }
        }
      } catch { /* Storage may be unavailable; saved revisions remain on the server. */ }
      setDraftReady(true);
    });
    return () => { live = false; };
  }, [documentId, readOnly, title, content, revisionId]);
  useEffect(() => {
    if (!documentId || readOnly || !draftReady) return;
    try {
      const key = documentDraftKey(documentId);
      if (dirty) localStorage.setItem(key, JSON.stringify({ title: draftTitle, content: draftContent, expectedRevision, owner: draftOwner }));
      else localStorage.removeItem(key);
    } catch { /* Export and manual save remain available if local storage is full. */ }
  }, [documentId, readOnly, draftReady, dirty, draftTitle, draftContent, expectedRevision, draftOwner]);

  // Warn before losing unsaved work. The browser's own dialog, because a custom
  // one cannot block navigation.
  useEffect(() => {
    if (!dirty) return;
    const warn = (event: BeforeUnloadEvent) => event.preventDefault();
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [dirty]);

  const save = () => {
    if (!draftReady || !dirty || saving || readOnly || reviewRequired || comparing) return;
    const savedTitle = draftTitle.trim() || base.title;
    // Match the value sent to the server now. Normalizing after the response
    // would overwrite title edits made while the save was pending.
    setDraftTitle(savedTitle);
    void onSave({ title: savedTitle, content: draftContent,
      ...(revisionId && expectedRevision ? { expectedRevision, draftOwner } : {}) });
  };

  const compareLatest = async () => {
    if (!onCompareLatest) return;
    setComparing(true); setComparisonError(null);
    try { setComparison(await onCompareLatest()); }
    catch (cause) { setComparisonError(cause instanceof Error ? cause.message : "Could not load the latest revision."); }
    finally { setComparing(false); }
  };
  const resolveComparison = (keepDraft: boolean) => {
    if (!comparison) return;
    setExpectedRevision(comparison.revisionId); setReviewRequired(false);
    setBaseline({ title: comparison.title, content: comparison.content });
    if (!keepDraft) { setDraftTitle(comparison.title); setDraftContent(comparison.content); }
    if (documentId) {
      try {
        if (keepDraft) localStorage.setItem(documentDraftKey(documentId), JSON.stringify({ title: draftTitle, content: draftContent, expectedRevision: comparison.revisionId, owner: draftOwner }));
        else localStorage.removeItem(documentDraftKey(documentId));
      } catch { /* The in-memory draft remains available. */ }
    }
    setComparison(null); setComparisonError(null);
    onReloadLatest?.();
  };

  return (
    <section aria-label="Document editor" className="noye-editor">
      <div className="noye-toolbar items-end">
        <div className="min-w-0 flex-1">
          <label htmlFor={titleId} className="block text-[12px] font-semibold text-ink-soft">
            Title
          </label>
          <input
            id={titleId}
            readOnly={readOnly}
            value={draftTitle}
            onChange={(event) => setDraftTitle(event.target.value)}
            className="mt-1 min-h-10 w-full rounded-md border border-edge-strong bg-card px-2.5 text-base"
          />
        </div>
        <button
          type="button"
          onClick={save}
          disabled={!draftReady || !dirty || saving || readOnly || reviewRequired || comparing}
          className="noye-button bg-brand font-semibold text-ink-inverse disabled:cursor-not-allowed disabled:opacity-60"
        >
          {saving ? "Saving…" : dirty ? "Save" : "Saved"}
        </button>
      </div>

      <div className="noye-toolbar border-b border-edge">
      <div
        role="tablist"
        aria-label="Editor view"
        className="flex gap-1"
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
            className={`noye-button border-transparent ${
              tab === value
                ? "border-b-2 border-brand font-semibold text-ink"
                : "text-ink-soft hover:text-ink"
            }`}
          >
            {value === "write" ? "Write" : "Preview"}
          </button>
        ))}
      </div>
      <span role="status" className="noye-meta">{readOnly ? "Historical revision · read only" : dirty ? "Unsaved changes" : "All changes saved"}</span>
      {documentId && <div className="ml-auto"><ExportControls exportUrl={exportUrl} documentId={documentId} previewVisible={tab === "preview"}
        content={exportContent} title={draftTitle} includeProvenance={includeProvenance}
        onProvenanceChange={setIncludeProvenance} /></div>}
      </div>

      <div className="noye-editor-body">
      {restored && dirty && <p role="status" className="mb-3 text-xs text-ink-soft">Restored your local unsaved draft. Save to include it in workspace backups.</p>}
      {reviewRequired && <p role="alert" className="mb-3 text-sm text-fail">This draft has an older or unknown base revision. Compare it with the latest saved revision before saving.</p>}
      {comparisonError && <p role="alert" className="mb-3 text-sm text-fail">{comparisonError} Your draft is still here.</p>}
      {revisionId && dirty && onCompareLatest && <button type="button" disabled={saving || comparing} onClick={compareLatest}
        className="mb-3 min-h-11 rounded border border-edge-strong px-3 text-sm">{comparing ? "Loading latest revision…" : "Compare with latest revision"}</button>}
      {comparison && <section aria-label="Resolve document conflict" className="mb-4 space-y-3 rounded border border-edge-strong bg-canvas p-4">
        <p className="font-semibold">Review the latest saved revision before choosing.</p>
        <p className="text-sm text-ink-soft">Your draft remains below. Reapplying it makes your next save replace the revision shown here; it does not merge automatically.</p>
        <label className="block text-sm">Latest saved title<input readOnly value={comparison.title} className="mt-1 block w-full rounded border border-edge bg-card p-2" /></label>
        <label className="block text-sm">Latest saved Markdown<textarea readOnly value={comparison.content} className="mt-1 block min-h-40 w-full rounded border border-edge bg-card p-2 font-mono text-sm" /></label>
        <div className="flex flex-wrap gap-3">
          <button type="button" onClick={() => resolveComparison(true)} className="min-h-11 rounded border border-edge-strong px-3">Reapply my draft to this revision</button>
          <button type="button" onClick={() => resolveComparison(false)} className="min-h-11 rounded border border-edge-strong px-3">Use latest saved content</button>
        </div>
      </section>}
        {tab === "write" ? (
          <div className="flex h-full min-h-0 flex-col">
            <label htmlFor={bodyId} className="sr-only">
              Document content, in Markdown
            </label>
            <textarea
              id={bodyId}
              ref={textarea}
              readOnly={readOnly}
              value={draftContent}
              onChange={(event) => setDraftContent(event.target.value)}
              onKeyDown={(event) => {
                // The shortcut people already have in their fingers.
                if ((event.metaKey || event.ctrlKey) && event.key === "s") {
                  event.preventDefault();
                  save();
                }
              }}
              autoCorrect="off"
              autoCapitalize="none"
              spellCheck={false}
              placeholder="# Your document&#10;&#10;Markdown works here."
              className="noye-editor-input w-full rounded-md border border-edge-strong bg-card p-4 font-mono text-sm leading-relaxed placeholder:text-ink-soft"
            />
            <p className="mt-1.5 noye-meta">
              Markdown. ⌘S saves.
            </p>
          </div>
        ) : (
          <DocumentPreview content={draftContent} provenance={includeProvenance ? provenance : ""} />
        )}
      </div>
    </section>
  );
}
