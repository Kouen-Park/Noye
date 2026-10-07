"use client";

import { useEffect, useState } from "react";
import { MarkdownContent } from "@/components/documents/document-preview";
import { editWiki, saveWikiAnalysis, wikiPreviewContent, type WikiPage, type WikiScope } from "@/lib/wiki";

export function WikiEditor({ page, scope, onSaved }: {
  page: WikiPage; scope: WikiScope; onSaved: (page: WikiPage) => void;
}) {
  const revision = page.revision!;
  const [draft, setDraft] = useState({ title: revision.title, content: revision.content, expected: revision.id });
  const [baseline, setBaseline] = useState({ title: revision.title, content: revision.content });
  const [writing, setWriting] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const draftKey = `noye:wiki-draft:${page.id}`;
  const dirty = draft.title !== baseline.title || draft.content !== baseline.content;
  if (!dirty && draft.expected !== revision.id) {
    setDraft({ title: revision.title, content: revision.content, expected: revision.id });
    setBaseline({ title: revision.title, content: revision.content });
  }
  useEffect(() => {
    let saved: { draft: typeof draft; baseline: typeof baseline } | null = null;
    try {
      const value = JSON.parse(window.localStorage.getItem(draftKey) ?? "null");
      if (value && typeof value.draft?.title === "string" && typeof value.draft?.content === "string" && typeof value.draft?.expected === "string" && typeof value.baseline?.title === "string" && typeof value.baseline?.content === "string") saved = value;
    } catch { /* The current in-memory draft remains editable if storage is unavailable. */ }
    let mounted = true;
    if (saved) { const restored = saved; Promise.resolve().then(() => { if (mounted) { setDraft(restored.draft); setBaseline(restored.baseline); } }); }
    return () => { mounted = false; };
  }, [draftKey]);
  useEffect(() => {
    const warn = (event: BeforeUnloadEvent) => { if (dirty) event.preventDefault(); };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [dirty]);
  function change(next: typeof draft) {
    setDraft(next);
    try { window.localStorage.setItem(draftKey, JSON.stringify({ draft: next, baseline })); }
    catch { setError("Could not preserve this draft across navigation. Save changes before leaving."); }
  }
  async function save() {
    setSaving(true); setError(null);
    try {
      const result = await editWiki(page.id, draft.expected, draft.title, draft.content, scope);
      setDraft({ ...draft, expected: result.revision!.id });
      setBaseline({ title: draft.title, content: draft.content }); onSaved(result);
      try { window.localStorage.removeItem(draftKey); } catch { /* The saved revision is durable. */ }
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Could not save your changes."); }
    finally { setSaving(false); }
  }
  async function analysis() {
    setSaving(true); setError(null);
    try { onSaved(await saveWikiAnalysis(`${draft.title} analysis`, draft.content, [page.id], scope)); }
    catch (cause) { setError(cause instanceof Error ? cause.message : "Could not save this analysis."); }
    finally { setSaving(false); }
  }
  return <section aria-label="Wiki content" className="min-w-0 rounded-lg border border-edge bg-card p-5">
    <div className="mb-4 flex flex-wrap items-center gap-3">
      <button type="button" onClick={() => setWriting(!writing)} className="min-h-11 rounded border border-edge-strong px-3">{writing ? "Preview" : "Edit Markdown"}</button>
      <button type="button" disabled={!dirty || saving} onClick={save} className="min-h-11 rounded bg-brand px-3 text-on-brand disabled:opacity-50">{saving ? "Saving…" : "Save changes"}</button>
      <button type="button" disabled={saving} onClick={analysis} className="min-h-11 rounded border border-edge-strong px-3">Save as analysis</button>
      {dirty && <span role="status" className="text-sm text-ink-soft">Unsaved edits · local draft retained; save to include in backups</span>}
    </div>
    {error && <p role="alert" className="mb-3 text-fail">{error} Your draft is still here.</p>}
    {draft.expected !== revision.id && dirty && <p role="status" className="mb-3 text-ink-soft">A newer revision is available. Your draft is preserved; saving requires the current revision.</p>}
    {writing ? <div className="space-y-3">
      <label className="block text-sm">Title<input disabled={saving} value={draft.title} onChange={e => change({ ...draft, title: e.target.value })} className="mt-1 block min-h-11 w-full rounded border border-edge-strong bg-canvas px-3" /></label>
      <label className="block text-sm">Markdown<textarea disabled={saving} value={draft.content} onChange={e => change({ ...draft, content: e.target.value })} className="mt-1 block min-h-[55vh] w-full rounded border border-edge-strong bg-canvas p-3 font-mono text-sm" /></label>
    </div> : <MarkdownContent content={wikiPreviewContent(draft.content, revision.metadata.contributors, scope)} allowImages={false} />}
  </section>;
}
