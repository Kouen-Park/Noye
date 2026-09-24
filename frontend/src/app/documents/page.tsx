"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useState } from "react";

import { AppShell } from "@/components/app-shell";
import { DocumentEditor } from "@/components/documents/document-editor";
import { DocumentList } from "@/components/documents/document-list";
import { ExportControls } from "@/components/documents/export-controls";
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
  const [open, setOpen] = useState<NoyeDocument | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [offline, setOffline] = useState(false);
  const [view, setView] = useState<"write" | "preview">("write");
  /** Which document the loaded body belongs to, so a stale load is ignored. */
  const [loadedFor, setLoadedFor] = useState<string | null>(null);

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

  // The URL decides which document is open. Read at render time rather than
  // synced in an effect, which React 19 rejects.
  if (loadedFor !== documentId) {
    setLoadedFor(documentId);
    setView("write");
    if (documentId === null) {
      setOpen(null);
      setError(null);
    } else {
      readDocument(documentId).then(
        (document) => setOpen(document),
        (cause: unknown) => {
          setOpen(null);
          fail(cause, "Could not open that document.");
        },
      );
    }
  }

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
    async (patch: { title: string; content: string }) => {
      if (!open) return;
      setSaving(true);
      setError(null);
      try {
        const saved = await updateDocument(open.id, patch);
        setOpen(saved);
        refreshList();
      } catch (cause: unknown) {
        fail(cause, "Could not save your changes.");
      } finally {
        setSaving(false);
      }
    },
    [fail, open, refreshList],
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

        {open === null ? (
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
            {open.source_instruction !== null && (
              <p className="mb-3 text-[12.5px] text-ink-soft">
                Drafted from your instruction:{" "}
                <span className="italic">“{open.source_instruction}”</span>
              </p>
            )}

            <DocumentEditor
              key={open.id}
              title={open.title}
              content={open.content}
              onSave={save}
              saving={saving}
              onViewChange={setView}
            />

            <div className="mt-5 border-t border-edge pt-3">
              <ExportControls
                documentId={open.id}
                previewVisible={view === "preview"}
              />
            </div>

            {open.citations.length > 0 && (
              <div className="mt-4 border-t border-edge pt-3">
                <h2 className="text-[11px] font-bold uppercase tracking-[0.09em] text-ink-faint">
                  Passages the first draft was built from
                </h2>
                <ul className="mt-2 space-y-1">
                  {open.citations.map((citation, index) => (
                    <li
                      key={`${citation.file_id}:${citation.page_number}:${index}`}
                      className="text-[12.5px] text-ink-soft"
                    >
                      {citation.label}
                    </li>
                  ))}
                </ul>
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
