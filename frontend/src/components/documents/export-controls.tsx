"use client";

import { documentExportUrl } from "@/lib/api";

/**
 * The two exports.
 *
 * `.md` is a plain link to the backend, which sends exactly the stored body — so
 * the file is the user's work rather than a re-rendering of it. It is a link and
 * not a fetch because the browser should handle the download, including where it
 * lands.
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
}

export function ExportControls({
  documentId,
  previewVisible,
  disabled = false,
}: ExportControlsProps) {
  return (
    <div className="flex flex-wrap items-center gap-2">
      <a
        href={disabled ? undefined : documentExportUrl(documentId)}
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
        onClick={() => window.print()}
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
    </div>
  );
}
