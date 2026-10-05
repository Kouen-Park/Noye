"use client";

import { useState } from "react";

import { type ChatCitation, readSourceStatus } from "@/lib/api";

export function SavedEvidence({ citation }: { citation: ChatCitation }) {
  const [status, setStatus] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const snapshot = citation.evidence;

  if (!snapshot) {
    return <p className="w-full text-[12px] text-ink-soft">Legacy citation: no excerpt was saved. The original version is unknown.</p>;
  }

  const checkOriginal = async () => {
    setPending(true);
    try {
      const original = await readSourceStatus(citation.file_id);
      const hashes = snapshot.excerpts.map((excerpt) => excerpt.source_hash);
      setStatus(original.status === "missing"
        ? "Original missing. The saved excerpts remain available."
        : original.status === "unavailable"
          ? "The original could not be checked."
          : hashes.some((hash) => hash && hash !== original.current_hash)
            ? "Original changed since these excerpts were indexed."
            : hashes.some((hash) => !hash) || hashes.length === 0
              ? "The original version was not recorded."
              : "Original matches the saved source version.");
    } catch {
      setStatus("The original could not be checked. Try again.");
    } finally {
      setPending(false);
    }
  };

  return (
    <div className="w-full space-y-2 border-t border-edge pt-2 text-[12px] text-ink-soft">
      <p>Saved excerpts · {new Date(snapshot.captured_at).toLocaleString()}</p>
      {snapshot.excerpts.map((excerpt, index) => (
        <div key={`${excerpt.retrieval_rank}:${index}`}>
          <blockquote className="whitespace-pre-wrap break-words border-l-2 border-accent pl-2 text-ink">{excerpt.content}</blockquote>
          <details className="mt-1">
            <summary className="cursor-pointer">Source version · chunk {excerpt.chunk_index}</summary>
            <p className="break-all font-mono text-[11px]">{excerpt.source_hash ? `SHA-256: ${excerpt.source_hash}` : "Original version unknown"}</p>
          </details>
        </div>
      ))}
      <button type="button" disabled={pending} onClick={checkOriginal} className="min-h-11 rounded-md border border-edge-strong px-2 disabled:opacity-60">
        {pending ? "Checking original…" : "Check original"}
      </button>
      {status && <p role="status">{status}</p>}
      <p>These are the passages provided to the model; they do not verify every sentence.</p>
    </div>
  );
}
