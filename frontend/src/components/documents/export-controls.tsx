"use client";

import { documentExportUrl } from "@/lib/api";
import { useState } from "react";
import { exportMarkdown, exportPdf } from "@/lib/native-export";
import { isDesktopRuntime } from "@/lib/runtime";

/**
 * The two exports.
 *
 * The editor supplies its current text for a native Markdown save on macOS or
 * a browser download on the web. The API link remains a fallback for stored
 * text. The selected provenance mode is shared
 * with the print preview, so both formats include the same material.
 *
 * PDF uses the existing browser/WebKit print engine and print stylesheet.
 * macOS chooses a file in the native save panel, then prints directly to a staged
 * PDF. Web mode uses window.print(). Both remain offline.
 *
 * What the print stylesheet in globals.css does is the other half of that
 * decision: everything not marked `data-print="document"` is hidden, so the page
 * that reaches the PDF is the document, not the application around it. Printing
 * from the Preview tab is therefore required — the raw Markdown in the Write tab
 * is not the document as anyone wants it on paper, which is why this says so
 * rather than silently printing whichever tab happens to be open.
 */

interface ExportControlsProps {
  documentId: string;
  exportUrl?: string;
  /** Whether the rendered document is on screen; PDF needs it. */
  previewVisible: boolean;
  disabled?: boolean;
  content?: string;
  title?: string;
  includeProvenance?: boolean;
  onProvenanceChange?: (include: boolean) => void;
}

export function ExportControls({
  documentId,
  exportUrl,
  previewVisible,
  disabled = false,
  content,
  title = "document",
  includeProvenance = false,
  onProvenanceChange,
}: ExportControlsProps) {
  const [exporting, setExporting] = useState(false);
  const [exportError, setExportError] = useState("");
  const [exportNotice, setExportNotice] = useState("");
  const markdownUrl = new URL(exportUrl ?? documentExportUrl(documentId, includeProvenance), "http://localhost");
  markdownUrl.searchParams.set("provenance", String(includeProvenance));
  return (
    <div aria-label="Document exports" className="flex flex-wrap items-center gap-2">
      <a
        href={disabled || exporting ? undefined : markdownUrl.toString()}
        onClick={async (event) => {
          if (disabled || exporting) { event.preventDefault(); return; }
          if (content === undefined) return;
          event.preventDefault();
          setExporting(true); setExportError(""); setExportNotice("");
          try {
            const result = await exportMarkdown(title, content);
            setExportNotice(result === "saved" ? "Markdown saved." : result === "cancelled" ?
              "Markdown export cancelled." : "Markdown download prepared.");
          } catch (cause) {
            setExportError(cause instanceof Error ? cause.message : String(cause));
          } finally { setExporting(false); }
        }}
        download
        aria-disabled={disabled || exporting}
        className={`noye-button ${
          disabled || exporting
            ? "cursor-not-allowed text-ink-soft"
            : "text-accent-ink hover:bg-brand-wash"
        }`}
      >
        {exporting ? "Exporting…" : "Export .md"}
      </a>

      <button
        type="button"
        onClick={async () => {
          if (disabled || exporting || !previewVisible) return;
          setExporting(true); setExportError(""); setExportNotice("");
          try {
            const result = await exportPdf(title);
            setExportNotice(result === "saved" ? "PDF saved." : result === "cancelled" ?
              "PDF export cancelled." : "PDF print dialog opened.");
          } catch (cause) {
            setExportError(cause instanceof Error ? cause.message : String(cause));
          } finally { setExporting(false); }
        }}
        disabled={disabled || exporting || !previewVisible}
        title={
          previewVisible
            ? isDesktopRuntime() ? "Save the preview as a PDF" : "Uses your browser's print dialog — choose Save as PDF"
            : "Switch to Preview first, so the PDF is the document rather than its Markdown"
        }
        className="noye-button font-semibold text-accent-ink hover:bg-brand-wash disabled:cursor-not-allowed disabled:text-ink-soft"
      >
        Export PDF
      </button>

      <details className="noye-export-options">
      <summary className="noye-button cursor-pointer">Export options</summary>
      <div className="noye-export-options-panel rounded-md border border-edge-strong bg-card p-3 text-ink-soft">
      {onProvenanceChange && <label className="flex min-h-10 items-center gap-2 text-xs">
        <input type="checkbox" checked={includeProvenance} onChange={(event) => onProvenanceChange(event.target.checked)} />Include provenance
      </label>}
      <p className="noye-meta">
        {previewVisible
          ? isDesktopRuntime() ? "PDF saves the current preview." : "PDF uses your browser's print dialog."
          : "Switch to Preview to export a PDF."}
      </p>
      {content !== undefined && <p className="mt-2 text-xs">Exports include the current editor text, including unsaved edits.</p>}
      </div>
      </details>
      {exportError && <p role="alert" className="w-full text-xs text-fail">{exportError} Your editor text is preserved.</p>}
      {exportNotice && <p role="status" className="w-full text-xs text-ink-soft">{exportNotice}</p>}
    </div>
  );
}
