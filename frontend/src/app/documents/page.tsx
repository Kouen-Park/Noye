"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useRef, useState } from "react";

import { AppShell, useWorkspaceLayout } from "@/components/app-shell";
import { SourceDocumentDetails, SourceDocumentRevision } from "@/components/documents/source-document-details";
import { editSourceDocument, isSourceDocument, readSourceDocument, sourceDocumentExportUrl, type SourceDocument } from "@/lib/source-documents";
import { DocumentEditor, type DocumentPatch } from "@/components/documents/document-editor";
import { acknowledgeDocumentDraft } from "@/lib/document-draft";
import { DocumentList } from "@/components/documents/document-list";
import { PassageList } from "@/components/chat/passages";
import {
  ApiError,
  type DocumentSummary,
  type NoyeDocument,
  createDocument,
  deleteDocument,
  listDocuments,
  readDocument,
  updateDocument,
} from "@/lib/api";

/**
 * Documents: what a chat answer becomes once it is yours.
 *
 * The open document lives in the URL (`/documents?d=…`), matching search and chat,
 * so Back returns to the previous document and one can be shared as a link.
 *
 * `useSearchParams` needs a Suspense boundary during prerender, so the part that
 * reads the URL is its own component.
 */
export default function DocumentsPage() {
  return (
    <AppShell current="Documents" title="Documents" description="Your writing, saved with its original evidence." workspace>
      <Suspense fallback={<p role="status" className="p-4 text-ink-soft">Opening documents…</p>}>
        <DocumentsView />
      </Suspense>
    </AppShell>
  );
}

function DocumentsView() {
  const router = useRouter();
  const params = useSearchParams();
  const documentId = params.get("d");

  const [documents, setDocuments] = useState<DocumentSummary[]>([]);
  const [loadingList, setLoadingList] = useState(true);
  const [listError, setListError] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const listRequest = useRef(0);
  const createPending = useRef(false);
  const [open, setOpen] = useState<NoyeDocument | SourceDocument | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [offline, setOffline] = useState(false);
  const { readingFocus, setReadingFocus } = useWorkspaceLayout();
  /** Which document the loaded body belongs to, so a stale load is ignored. */
  const [loadedFor, setLoadedFor] = useState<string | null>(null);
  const activeDocument = useRef<string | null>(null);
  const revisionRequest = useRef(0);
  const saveRequest = useRef(0);

  const fail = useCallback((cause: unknown, fallback: string) => {
    setOffline(cause instanceof ApiError && cause.isOffline);
    setError(cause instanceof ApiError ? cause.message : fallback);
  }, []);

  const loadList = useCallback(() => {
    const request = ++listRequest.current;
    listDocuments().then((items) => {
      if (listRequest.current === request) setDocuments(items);
    }, (cause: unknown) => {
      if (listRequest.current === request) setListError(cause instanceof ApiError ? cause.message : "Could not load your documents.");
    }).finally(() => {
      if (listRequest.current === request) setLoadingList(false);
    });
  }, []);

  const refreshList = useCallback(() => {
    setLoadingList(true);
    setListError(null);
    loadList();
  }, [loadList]);

  useEffect(() => {
    loadList();
    return () => { listRequest.current += 1; };
  }, [loadList]);

  useEffect(() => {
    activeDocument.current = documentId;
    const request = ++revisionRequest.current;
    if (!documentId) return;
    const controller = new AbortController();
    readSourceDocument(documentId, undefined, controller.signal).catch(cause => {
      if (cause instanceof ApiError && cause.status === 404) return readDocument(documentId, controller.signal);
      throw cause;
    }).then(document => {
      if (!controller.signal.aborted && revisionRequest.current === request) { setOpen(document); setLoadedFor(documentId); setError(null); }
    }, cause => { if (!controller.signal.aborted && revisionRequest.current === request) { setOpen(null); setLoadedFor(documentId); fail(cause, "Could not open that document."); } });
    return () => { activeDocument.current = null; controller.abort(); };
  }, [documentId, fail]);
  const shown = documentId && loadedFor === documentId && open?.id === documentId ? open : null;
  const sourceDocument = shown && isSourceDocument(shown) ? shown : null;
  const evidenceCount = sourceDocument?.revision.metadata.citations.length ?? shown?.citations.length ?? 0;
  const chooseRevision = (id?: string) => {
    if (!documentId) return;
    const request = ++revisionRequest.current;
    const current = () => activeDocument.current === documentId && revisionRequest.current === request;
    readSourceDocument(documentId, id).then(document => {
      if (current()) { setOpen(document); setError(null); }
    }, cause => { if (current()) fail(cause, "Could not open that revision."); });
  };

  const openDocument = useCallback(
    (id: string) => router.push(`/documents?d=${encodeURIComponent(id)}`),
    [router],
  );

  const startNew = useCallback(() => {
    if (createPending.current) return;
    createPending.current = true;
    setCreating(true);
    setError(null);
    createDocument("Untitled document").then(
      (document) => {
        refreshList();
        router.push(`/documents?d=${encodeURIComponent(document.id)}`);
      },
      (cause: unknown) => fail(cause, "Could not create a document."),
    ).finally(() => { createPending.current = false; setCreating(false); });
  }, [fail, refreshList, router]);

  const save = useCallback(
    async ({ expectedRevision, draftOwner, ...patch }: DocumentPatch) => {
      if (!shown) return;
      const document = shown;
      const revision = ++revisionRequest.current;
      const request = ++saveRequest.current;
      setSaving(true);
      setError(null);
      try {
        const saved = isSourceDocument(document)
          ? await editSourceDocument(document.id, expectedRevision ?? document.revision.id, patch)
          : await updateDocument(document.id, patch);
        if (isSourceDocument(saved) && isSourceDocument(document)) {
          acknowledgeDocumentDraft(document.id, expectedRevision ?? document.revision.id, saved.revision.id, draftOwner);
        }
        if (activeDocument.current === document.id && revisionRequest.current === revision) setOpen(saved);
        refreshList();
      } catch (cause: unknown) {
        if (activeDocument.current === document.id && revisionRequest.current === revision) fail(cause, "Could not save your changes.");
      } finally {
        if (saveRequest.current === request) setSaving(false);
      }
    },
    [fail, shown, refreshList],
  );

  const remove = useCallback(
    (id: string) => {
      deleteDocument(id).then(
        () => {
          refreshList();
          if (id === documentId) router.replace("/documents");
        },
        (cause: unknown) => fail(cause, "Could not delete that document."),
      );
    },
    [documentId, fail, refreshList, router],
  );

  return (
    <div className="noye-workspace">
      <div className="noye-toolbar border-b border-edge">
        <p className="min-w-0 flex-1 truncate text-sm text-ink-soft">{shown?.title ?? "Choose a document"}</p>
        {sourceDocument && <>
          {sourceDocument.revision.metadata.coverage.partial && <span className="noye-meta text-fail">Partial document</span>}
          <SourceDocumentRevision document={sourceDocument} onRevision={chooseRevision} />
        </>}
        <button type="button" aria-pressed={readingFocus} aria-controls="document-list"
          onClick={() => setReadingFocus(!readingFocus)} className="noye-button">
          Focus reading
        </button>
      </div>
      <div className="noye-split">
      <aside id="document-list" aria-label="Document list" hidden={readingFocus} className="noye-secondary-list">
        <DocumentList
          documents={documents}
          currentId={documentId}
          onOpen={openDocument}
          onDelete={remove}
          onNew={startNew}
          loading={loadingList}
          error={listError}
          onRetry={refreshList}
          creating={creating}
        />
      </aside>

      <div className="noye-work-pane">
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

        {shown === null ? documentId && loadedFor !== documentId ? (
          <p role="status" className="p-4 text-ink-soft">Opening document…</p>
        ) : (
          <div
            className="rounded-lg border border-dashed border-edge-strong bg-card px-6 py-12 text-center"
          >
            <p className="font-display text-lg">Nothing open</p>
            <p className="mx-auto mt-1 max-w-[52ch] text-[13.5px] text-ink-soft">
              Ask something in Chat and turn the answer into a document, or start a blank
              one. Either way the text is yours to change.
            </p>
          </div>
        ) : (
          <>
            <DocumentEditor
              key={`${shown.id}:${sourceDocument?.revision.id ?? "legacy"}`}
              title={shown.title}
              content={shown.content}
              onSave={save}
              saving={saving}
              documentId={shown.id}
              revisionId={sourceDocument?.revision.id}
              onCompareLatest={sourceDocument ? async () => {
                const latest = await readSourceDocument(shown.id);
                return { title: latest.title, content: latest.content, revisionId: latest.revision.id };
              } : undefined}
              onReloadLatest={sourceDocument ? () => chooseRevision() : undefined}
              provenance={shown.provenance_markdown}
              readOnly={!!sourceDocument && sourceDocument.revision.id !== sourceDocument.revisions[0]?.id}
              exportUrl={sourceDocument ? sourceDocumentExportUrl(shown.id, sourceDocument.revision.id) : undefined}
            />
            {(sourceDocument || shown.source_instruction !== null || shown.citations.length > 0) && <details aria-label="Document details" className="noye-work-details">
            <summary>Details · {evidenceCount} evidence {evidenceCount === 1 ? "passage" : "passages"}{(sourceDocument?.revision.metadata.coverage.synthesis_limits?.length || sourceDocument?.revision.metadata.coverage.presentation_limits?.length) ? " · review limits" : ""}</summary>
            {sourceDocument && <SourceDocumentDetails document={sourceDocument} onRevision={chooseRevision} showRevision={false} />}
            {shown.source_instruction !== null && (
              <details className="noye-details"><summary>Draft instruction</summary><p className="mt-2 text-sm text-ink-soft">{shown.source_instruction}</p></details>
            )}
            {shown.citations.length > 0 && (
              <details className="noye-details">
                <summary>
                  Evidence saved with the first draft
                </summary>
                <PassageList citations={shown.citations} />
                <p className="mt-1.5 noye-meta">
                  These describe the draft, not what you have written since.
                </p>
              </details>
            )}
            </details>}
          </>
        )}
      </div>
      </div>
    </div>
  );
}
