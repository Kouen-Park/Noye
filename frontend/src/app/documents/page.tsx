"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useRef, useState } from "react";

import { AppShell } from "@/components/app-shell";
import { SourceDocumentDetails } from "@/components/documents/source-document-details";
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
    <AppShell current="Documents">
      <div>
        <h1 className="text-[27px]">Documents</h1>
        <p className="mt-1 max-w-[60ch] text-ink-soft">
          Turn an answer into something you can keep. Everything here is yours to
          edit — nothing regenerates behind your back.
        </p>
      </div>

      <Suspense fallback={<p className="mt-7 text-ink-soft">Opening documents…</p>}>
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
  const [open, setOpen] = useState<NoyeDocument | SourceDocument | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [offline, setOffline] = useState(false);
  /** Which document the loaded body belongs to, so a stale load is ignored. */
  const [loadedFor, setLoadedFor] = useState<string | null>(null);
  const activeDocument = useRef<string | null>(null);
  const revisionRequest = useRef(0);
  const saveRequest = useRef(0);

  const fail = useCallback((cause: unknown, fallback: string) => {
    setOffline(cause instanceof ApiError && cause.isOffline);
    setError(cause instanceof ApiError ? cause.message : fallback);
  }, []);

  const refreshList = useCallback(() => {
    listDocuments().then(setDocuments, (cause: unknown) =>
      fail(cause, "Could not load your documents."),
    );
  }, [fail]);

  useEffect(() => {
    refreshList();
  }, [refreshList]);

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
    setError(null);
    createDocument("Untitled document").then(
      (document) => {
        refreshList();
        router.push(`/documents?d=${encodeURIComponent(document.id)}`);
      },
      (cause: unknown) => fail(cause, "Could not create a document."),
    );
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
    <div className="mt-6 flex flex-col gap-6 lg:flex-row-reverse">
      <div className="lg:w-[240px] lg:shrink-0">
        <DocumentList
          documents={documents}
          currentId={documentId}
          onOpen={openDocument}
          onDelete={remove}
          onNew={startNew}
        />
      </div>

      <div className="min-w-0 flex-1">
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

        {shown === null ? (
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
            {shown.source_instruction !== null && (
              <p className="mb-3 text-[12.5px] text-ink-soft">
                Drafted from your instruction:{" "}
                <span className="italic">“{shown.source_instruction}”</span>
              </p>
            )}

            {sourceDocument && <SourceDocumentDetails document={sourceDocument} onRevision={chooseRevision} />}
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

            {shown.citations.length > 0 && (
              <div className="mt-4 border-t border-edge pt-3">
                <h2 className="text-[11px] font-bold uppercase tracking-[0.09em] text-ink-faint">
                  Evidence saved with the first draft
                </h2>
                <PassageList citations={shown.citations} />
                <p className="mt-1.5 text-[11.5px] text-ink-faint">
                  These describe the draft, not what you have written since.
                </p>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
