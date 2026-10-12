"use client";

import { useEffect, useId, useRef, useState } from "react";
import Link from "next/link";

import { StageBar, StatusPill } from "@/components/library/status-indicators";
import { isProcessing, type StoredFile } from "@/lib/api";
import { factsLine, isStalled, stoppedReason, typeLabel } from "@/lib/status";

interface FileCardProps {
  file: StoredFile;
  onRemove: (id: string) => void;
  onRetry: (id: string) => void;
  onCancel: (id: string) => void;
  stopping: boolean;
  registerRef?: (element: HTMLLIElement | null) => void;
}

const actionClass = "min-h-11 rounded-md px-2.5 text-[13px] font-medium text-ink-soft hover:bg-sunken disabled:opacity-60 md:min-h-8";

export function FileCard({ file, onRemove, onRetry, onCancel, stopping, registerRef }: FileCardProps) {
  const [confirming, setConfirming] = useState(false);
  const [detailsOpen, setDetailsOpen] = useState(false);
  const detailsId = useId();
  const removeButtonRef = useRef<HTMLButtonElement>(null);
  const returnFocus = useRef(false);
  const failed = file.status === "FAILED";
  const stopped = failed ? stoppedReason(file.error) : null;
  const working = isProcessing(file.status);
  const stalled = isStalled(file);
  const folderOriginal = Boolean(file.folder_root_id);
  const pagesWithoutText = file.file_type === "pdf" ? file.no_text_pages?.length ?? 0 : 0;

  useEffect(() => {
    if (!confirming && returnFocus.current) {
      returnFocus.current = false;
      removeButtonRef.current?.focus();
    }
  }, [confirming]);

  return <li ref={registerRef} tabIndex={-1}
    className="border-b border-edge px-2 py-2.5 text-[13px] hover:bg-sunken/40 focus-visible:outline-2 focus-visible:outline-brand">
    <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
      <span aria-hidden="true" className="w-9 shrink-0 text-[12px] font-medium text-ink-soft">{typeLabel(file.file_type)}</span>
      <span className="min-w-0 basis-full truncate font-medium sm:flex-1 sm:basis-0" title={file.name}>{file.name}</span>
      <StatusPill status={file.status} error={file.error} />
      <div className={`${confirming && !folderOriginal ? "hidden" : "flex"} flex-wrap items-center gap-1`} hidden={confirming && !folderOriginal}>
        {folderOriginal && <Link href="/folders/" className={actionClass + " inline-flex items-center"}>Manage in Folders</Link>}
        {failed && !folderOriginal && <button type="button" className={actionClass + " text-accent-ink"} onClick={() => onRetry(file.id)}>Retry</button>}
        {working && <button type="button" className={actionClass} disabled={stopping} onClick={() => onCancel(file.id)}>{stopping ? "Stopping…" : "Stop"}</button>}
        {!working && !folderOriginal && <button ref={removeButtonRef} type="button" className={actionClass + " hover:text-fail"} onClick={() => setConfirming(true)}>Remove</button>}
      </div>
      <button type="button" className={actionClass} aria-expanded={detailsOpen} aria-controls={detailsId}
        aria-label={`Details for ${file.name}`} onClick={() => setDetailsOpen(value => !value)}>Details</button>
    </div>

    {working && <div className="ml-12 max-w-xl"><StageBar status={file.status} /></div>}
    {stalled && !stopping && <p className="mt-1 text-ink-soft">This is taking longer than usual. You can stop it, then retry.</p>}
    {pagesWithoutText > 0 && <p className="mt-1 text-[12px] text-ink-soft">{pagesWithoutText} pages have no extracted text. Open Details to inspect them.</p>}
    {failed && <div className="mt-1 text-[12px]">
      {file.error && <p className={stopped ? "text-ink-soft" : "text-fail"}>{file.error}</p>}
      <p className="mt-0.5 text-ink-soft">{folderOriginal ? "Check this source in Folders before retrying."
        : stopped === "cancelled" ? "Retry whenever you're ready."
        : stopped === "interrupted" ? "Retry to finish indexing this file."
        : "Fix the problem, then retry this file."}</p>
    </div>}

    <div id={detailsId} hidden={!detailsOpen} className="mt-2 border-l-2 border-edge pl-3 text-[12px] text-ink-soft">
      <p>{factsLine(file)}</p>
      <p className="mt-1">{folderOriginal ? "Folder original. Manage processing, disconnection and derived indexes in Folders."
        : "Independent upload. Its saved copy stays on this machine."}</p>
      {file.file_type === "pdf" && file.no_text_pages != null && <div className="mt-1">
        <p>Text extracted from {file.extracted_page_count} of {file.page_count} pages.</p>
        {pagesWithoutText > 0 && <p className="mt-1 break-words">Pages: {file.no_text_pages.join(", ")}. These may be blank or image-only; OCR has not been performed.</p>}
      </div>}
    </div>

    {confirming && !folderOriginal && <div className="mt-2 flex flex-wrap items-center gap-2 rounded-md bg-fail-wash px-3 py-2">
      <p className="min-w-0 flex-1 text-[12px] text-fail">Remove {file.name}? This cannot be undone. Saved excerpts in existing conversations and documents are kept.</p>
      <button type="button" autoFocus className="min-h-11 rounded-md bg-fail px-3 text-[13px] font-semibold text-canvas md:min-h-8" onClick={() => onRemove(file.id)}>Remove</button>
      <button type="button" className={actionClass} onClick={() => { returnFocus.current = true; setConfirming(false); }}>Keep</button>
    </div>}
  </li>;
}
