"use client";

import { useEffect, useMemo, useRef } from "react";

import { AppShell } from "@/components/app-shell";
import { CrossIcon } from "@/components/icons";
import { DropZone } from "@/components/library/drop-zone";
import { FileCard } from "@/components/library/file-card";
import { useLibrary } from "@/hooks/use-library";
import { GROUPS, groupOf } from "@/lib/status";

/**
 * The library: everything Noye can search, and the way things get into it.
 *
 * A client component throughout, because the whole page is state — uploads,
 * drag-and-drop, and a polling loop watching files through ingestion. There is
 * nothing here that a server render could usefully produce.
 */
export default function LibraryPage() {
  const library = useLibrary();
  const cardRefs = useRef(new Map<string, HTMLLIElement>());

  // Move focus to a newly added card, so a keyboard user is left beside the
  // thing they just created rather than back at the top of the page.
  useEffect(() => {
    if (!library.lastAddedId) return;
    cardRefs.current.get(library.lastAddedId)?.focus();
  }, [library.lastAddedId]);

  // Catch a drop anywhere on the page, not only inside the zone.
  //
  // Two reasons. A drop that lands just outside the target would otherwise do
  // nothing, with no way for the person to tell a near-miss from a broken
  // feature. And the browser's default action for a file dropped on a document
  // is to NAVIGATE to it, which would throw the page away mid-session.
  const { addFiles } = library;
  useEffect(() => {
    const swallow = (event: DragEvent) => event.preventDefault();
    const onDrop = (event: DragEvent) => {
      event.preventDefault();
      const dropped = event.dataTransfer?.files;
      if (dropped && dropped.length > 0) {
        void addFiles(Array.from(dropped));
      }
    };
    window.addEventListener("dragover", swallow);
    window.addEventListener("drop", onDrop);
    return () => {
      window.removeEventListener("dragover", swallow);
      window.removeEventListener("drop", onDrop);
    };
    // addFiles is a stable callback; the hook's returned object is not, so
    // depending on it here would resubscribe on every render.
  }, [addFiles]);

  const grouped = useMemo(() => {
    return GROUPS.map((group) => ({
      ...group,
      files: library.files.filter((file) => groupOf(file) === group.key),
    })).filter((group) => group.files.length > 0);
  }, [library.files]);

  const indexedFiles = useMemo(
    () => library.files.filter((file) => file.status === "READY"),
    [library.files],
  );
  const passageCount = indexedFiles.reduce((total, file) => total + file.chunk_count, 0);

  const isEmpty = library.phase === "ready" && library.files.length === 0;

  return (
    <AppShell
      current="Library"
      passageCount={library.phase === "ready" ? passageCount : undefined}
      fileCount={indexedFiles.length}
    >
      {/* Ingestion finishes without any page change, so transitions are
          announced here instead. Polite, so it waits for a natural pause. */}
      <p role="status" aria-live="polite" className="sr-only">
        {library.announcement}
      </p>

      <h1 className="text-[27px]">Library</h1>
      <p className="mt-1 max-w-[60ch] text-ink-soft">
        Anything you add here becomes searchable by meaning — and every answer points back to
        the page it came from.
      </p>
      {/* The one claim that is the product's reason to exist. It was previously
          stated only inside the backend-unreachable error, which most people
          will never see. */}
      <p className="mb-6 mt-1 text-[13px] text-ink-faint">
        Everything stays on this machine. Nothing is uploaded anywhere.
      </p>

      <DropZone
        onFiles={(files) => void library.addFiles(files)}
        uploading={library.uploading}
        disabled={library.phase === "error"}
      />

      {library.rejected.length > 0 && (
        <ul className="mt-3 space-y-2">
          {library.rejected.map((rejection) => (
            <li
              key={rejection.key}
              className="flex items-start gap-2 rounded-md border border-fail bg-fail-wash px-3 py-2 text-[13px] text-fail"
            >
              <span className="min-w-0 flex-1">
                <strong className="font-semibold">{rejection.name}</strong> — {rejection.message}
              </span>
              <button
                type="button"
                onClick={() => library.dismissRejection(rejection.key)}
                aria-label={`Dismiss the message about ${rejection.name}`}
                className="shrink-0 rounded-sm p-1"
              >
                <CrossIcon className="h-3.5 w-3.5" />
              </button>
            </li>
          ))}
        </ul>
      )}

      {library.phase === "loading" && (
        <p className="mt-8 text-ink-soft">Opening your library…</p>
      )}

      {library.phase === "error" && (
        <div className="mt-8 rounded-lg border border-fail bg-fail-wash px-4 py-4">
          <p className="font-semibold text-fail">{library.loadError}</p>
          <p className="mt-1 text-[13px] text-fail">
            Noye keeps your files on this machine, so its backend has to be running. Start it
            with <code className="font-mono">uvicorn app.main:app</code> in the{" "}
            <code className="font-mono">backend</code> folder, then try again.
          </p>
          <button
            type="button"
            onClick={library.reload}
            className="mt-3 min-h-11 rounded-md bg-fail px-4 text-[13.5px] font-semibold text-canvas md:min-h-0 md:py-2"
          >
            Try again
          </button>
        </div>
      )}

      {isEmpty && (
        <div className="mt-6 rounded-lg border border-dashed border-edge-strong bg-card px-6 py-12 text-center">
          <p className="font-display text-lg">Nothing on the shelf yet</p>
          <p className="mt-1 text-[13.5px] text-ink-soft">
            Add a lecture PDF, a page of notes, or a text file to begin.
          </p>
        </div>
      )}

      {grouped.map((group) => (
        <section key={group.key} aria-labelledby={`group-${group.key}`}>
          <h2
            id={`group-${group.key}`}
            className="mb-2.5 mt-7 flex items-center gap-2.5 text-[11px] font-bold uppercase tracking-[0.09em] text-ink-faint"
          >
            {group.heading}
            <span aria-hidden="true" className="h-px flex-1 bg-edge" />
          </h2>
          <ul>
            {group.files.map((file) => (
              <FileCard
                key={file.id}
                file={file}
                onRemove={(id) => void library.removeFile(id)}
                onRetry={(id) => void library.retryFile(id)}
                onCancel={(id) => void library.cancelFile(id)}
                stopping={library.stoppingIds.includes(file.id)}
                registerRef={(element) => {
                  if (element) cardRefs.current.set(file.id, element);
                  else cardRefs.current.delete(file.id);
                }}
              />
            ))}
          </ul>
        </section>
      ))}
    </AppShell>
  );
}
