"use client";

import { useId, useRef, useState } from "react";

import { PlusIcon } from "@/components/icons";

/**
 * The way files get into the library.
 *
 * Built on a real `<input type="file">` inside a `<label>`, not a div with a
 * drag handler. That is what makes it keyboard-operable and gives it an
 * accessible name for free: Tab reaches the input, Space or Enter opens the
 * picker, and the ring is drawn by `focus-within`. The drag-and-drop handlers
 * are layered on top as an enhancement, never as the only route in.
 *
 * The input is visually hidden with a clip rather than `display: none`, because
 * a hidden-by-display input is removed from the tab order.
 */

const ACCEPT = ".pdf,.md,.markdown,.txt,.text";

interface DropZoneProps {
  onFiles: (files: File[]) => void;
  /** Names of uploads currently in flight, reported under the prompt. */
  uploading: string[];
  disabled?: boolean;
}

export function DropZone({ onFiles, uploading, disabled = false }: DropZoneProps) {
  const inputId = useId();
  const inputRef = useRef<HTMLInputElement>(null);
  const [isDragging, setDragging] = useState(false);

  const hand = (files: FileList | null) => {
    if (!files || files.length === 0) return;
    onFiles(Array.from(files));
    // Clear the input so re-selecting the same file still fires a change event.
    if (inputRef.current) inputRef.current.value = "";
  };

  return (
    <div
      onDragOver={(event) => {
        if (disabled) return;
        event.preventDefault();
        setDragging(true);
      }}
      onDragLeave={() => setDragging(false)}
      onDrop={(event) => {
        if (disabled) return;
        event.preventDefault();
        setDragging(false);
        hand(event.dataTransfer.files);
      }}
      className={`rounded-lg border-[1.5px] border-dashed bg-card text-center transition-colors focus-within:outline focus-within:outline-2 focus-within:outline-offset-2 focus-within:outline-brand ${
        isDragging ? "border-brand bg-brand-wash" : "border-edge-strong"
      } ${disabled ? "opacity-60" : "hover:border-brand hover:bg-brand-wash"}`}
    >
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
        <input
          ref={inputRef}
          id={inputId}
          type="file"
          multiple
          accept={ACCEPT}
          disabled={disabled}
          onChange={(event) => hand(event.target.files)}
          // Visually hidden but still focusable and still labelled.
          className="absolute h-px w-px overflow-hidden [clip:rect(0,0,0,0)]"
        />
      </label>

      {uploading.length > 0 && (
        <p className="border-t border-edge px-6 py-2 text-[13px] text-ink-soft">
          Adding {uploading.length === 1 ? uploading[0] : `${uploading.length} files`}…
        </p>
      )}
    </div>
  );
}
