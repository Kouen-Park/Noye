"use client";

import { documentExportUrl } from "@/lib/api";
import { useState } from "react";

/**
 * The two exports.
 *
 * The editor supplies its current text for a Markdown download; the API link
 * remains a fallback for stored text. The selected provenance mode is shared
 * with the print preview, so both formats include the same material.
 *
 * PDF is `window.print()`, per the plan's §13.2. A server-side renderer would need
 * system libraries a user must install before Noye worked at all, which is a real
 * cost for something claiming to run on your machine without setup. The browser
 * already has a PDF engine and it is offline.
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
  previewVisible,
  disabled = false,
  content,
  title = "document",
  includeProvenance = false,
  onProvenanceChange,
}: ExportControlsProps) {
  const [printError, setPrintError] = useState(false);
  return (
    <div className="flex flex-wrap items-center gap-2">
      {onProvenanceChange && <label className="flex min-h-11 items-center gap-2 text-xs text-ink-soft">
        <input type="checkbox" checked={includeProvenance} onChange={(event) => onProvenanceChange(event.target.checked)} />Include provenance
      </label>}
      <a
        href={disabled ? undefined : documentExportUrl(documentId, includeProvenance)}
        onClick={(event) => {
          if (disabled || content === undefined) return;
          event.preventDefault();
          const url = URL.createObjectURL(new Blob([content], { type: "text/markdown;charset=utf-8" }));
          const link = document.createElement("a");
          link.href = url;
          link.download = `${title.replace(/[\\/:\x00-\x1f]/g, "").trim() || "document"}.md`;
          link.click();
          setTimeout(() => URL.revokeObjectURL(url), 1000);
        }}
        download
        aria-disabled={disabled}
        className={`min-h-11 rounded-md border border-edge-strong px-3 py-2 text-[12.5px] font-semibold md:min-h-0 ${
          disabled
            ? "cursor-not-allowed text-ink-faint"
            : "text-accent-ink hover:bg-brand-wash"
        }`}
      >
        Export .md
      </a>

      <button
        type="button"
        onClick={async () => {
          setPrintError(false);
          try { await window.print(); } catch { setPrintError(true); }
        }}
        disabled={disabled || !previewVisible}
        title={
          previewVisible
            ? "Uses your browser's print dialog — choose Save as PDF"
            : "Switch to Preview first, so the PDF is the document rather than its Markdown"
        }
        className="min-h-11 rounded-md border border-edge-strong px-3 text-[12.5px] font-semibold text-accent-ink hover:bg-brand-wash disabled:cursor-not-allowed disabled:text-ink-faint md:min-h-0 md:py-2"
      >
        Export PDF
      </button>

      <p className="text-[11.5px] text-ink-faint">
        {previewVisible
          ? "PDF uses your browser's print dialog."
          : "Switch to Preview to export a PDF."}
      </p>
      {content !== undefined && <p className="w-full text-xs text-ink-soft">Exports include the current editor text, including unsaved edits.</p>}
      {printError && <p role="alert" className="w-full text-xs text-danger">Could not open the print dialog. Try again, or export Markdown.</p>}
    </div>
  );
}
