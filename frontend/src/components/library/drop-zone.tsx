"use client";

import { useId, useState } from "react";

import { PlusIcon } from "@/components/icons";
import { ACCEPT_ATTRIBUTE } from "@/lib/api";

/**
 * The way files get into the library.
 *
 * Built on a real `<input type="file">`, not a div with a click handler, so it
 * is keyboard-operable and carries its own accessible name: Tab reaches the
 * input, Space or Enter opens the picker, and the ring is drawn by
 * `focus-within` on the box. Drag-and-drop is layered on as an enhancement —
 * the page handles the drop itself, at window level, so a near-miss still
 * lands.
 *
 * Two things here are deliberate, because getting either wrong silently breaks
 * file selection in Chrome:
 *
 *  - The input is a SIBLING of the label, never a descendant. A label that both
 *    wraps its control and points at it with `for` triggers the control's
 *    activation behaviour twice, which can cancel the file chooser and fire no
 *    `change` event at all — the picker opens, a file is chosen, and nothing
 *    happens.
 *
 *  - The input's value is cleared on CLICK, not after `change`. Clearing it
 *    after the selection is what lets re-picking the same file work, but doing
 *    it in the change handler means mutating the input in the same tick as
 *    reading its files. Clearing on the way in is equivalent and touches
 *    nothing that is still being read.
 *
 * It is hidden with `sr-only`, which keeps it focusable — `display: none` would
 * take it out of the tab order.
 */

interface DropZoneProps {
  onFiles: (files: File[]) => void;
  /** Names of uploads currently in flight, reported under the prompt. */
  uploading: string[];
  disabled?: boolean;
}

export function DropZone({ onFiles, uploading, disabled = false }: DropZoneProps) {
  const inputId = useId();
  const [isDragging, setDragging] = useState(false);

  return (
    <div
      onDragOver={(event) => {
        if (disabled) return;
        event.preventDefault();
        setDragging(true);
      }}
      onDragLeave={() => setDragging(false)}
      // The drop is handled once, at window level, by the page. This only
      // clears the highlight, so the two cannot both upload the same file.
      onDrop={() => setDragging(false)}
      className={`rounded-lg border-[1.5px] border-dashed bg-card text-center transition-colors focus-within:outline focus-within:outline-2 focus-within:outline-offset-2 focus-within:outline-brand ${
        isDragging ? "border-brand bg-brand-wash" : "border-edge-strong"
      } ${disabled ? "opacity-60" : "hover:border-brand hover:bg-brand-wash"}`}
    >
      <input
        id={inputId}
        type="file"
        multiple
        accept={ACCEPT_ATTRIBUTE}
        disabled={disabled}
        // Clearing on the way in means picking the same file twice in a row
        // still produces a change event.
        onClick={(event) => {
          (event.currentTarget as HTMLInputElement).value = "";
        }}
        onChange={(event) => {
          const chosen = event.currentTarget.files;
          if (!chosen || chosen.length === 0) return;
          onFiles(Array.from(chosen));
        }}
        className="sr-only"
      />

      <label
        htmlFor={inputId}
        className={`flex flex-col items-center px-6 py-7 ${disabled ? "" : "cursor-pointer"}`}
      >
        <span className="mb-2 grid h-8 w-8 place-items-center rounded-full bg-brand text-ink-inverse">
          <PlusIcon className="h-4 w-4" />
        </span>
        <span className="font-display text-base">Drop files to add them</span>
        <span className="mt-1 text-[13px] text-ink-soft">
          or select them · PDF, Markdown, plain text
        </span>
      </label>

      {uploading.length > 0 && (
        <p
          className="border-t border-edge px-6 py-2 text-[13px] text-ink-soft"
          data-testid="uploading-line"
        >
          Adding {uploading.length === 1 ? uploading[0] : `${uploading.length} files`}…
        </p>
      )}
    </div>
  );
}
