"use client";

/**
 * All of the library's state in one place: the file list, the polling loop that
 * watches files through ingestion, uploads, and deletes.
 *
 * Polling rather than streaming because the backend ingests in a background
 * task and exposes `GET /files/{id}` as the status endpoint — see
 * backend/app/api/files.py. Only files that are still processing are polled, so
 * a settled library makes no requests at all.
 */

import { useCallback, useEffect, useRef, useState } from "react";

import {
  ApiError,
  deleteFile as deleteFileRequest,
  getFile,
  isProcessing,
  listFiles,
  rejectionFor,
  type StoredFile,
  uploadFile,
} from "@/lib/api";
import { completionAnnouncement } from "@/lib/status";

const POLL_INTERVAL_MS = 2000;

/** An upload the backend refused, kept on screen until dismissed. */
export interface RejectedUpload {
  key: string;
  name: string;
  message: string;
}

export type LoadPhase = "loading" | "ready" | "error";

export interface Library {
  files: StoredFile[];
  phase: LoadPhase;
  /** Why the initial load failed. Distinct from a single file failing. */
  loadError: string | null;
  /** Uploads in flight, by display name, so the drop zone can report them. */
  uploading: string[];
  rejected: RejectedUpload[];
  /** The most recent thing worth announcing to a screen reader. */
  announcement: string;
  /** Set after an upload succeeds, so the page can move focus to the new card. */
  lastAddedId: string | null;
  reload: () => void;
  addFiles: (selected: File[]) => Promise<void>;
  removeFile: (id: string) => Promise<void>;
  dismissRejection: (key: string) => void;
}

export function useLibrary(): Library {
  const [files, setFiles] = useState<StoredFile[]>([]);
  const [phase, setPhase] = useState<LoadPhase>("loading");
  const [loadError, setLoadError] = useState<string | null>(null);
  const [uploading, setUploading] = useState<string[]>([]);
  const [rejected, setRejected] = useState<RejectedUpload[]>([]);
  const [announcement, setAnnouncement] = useState("");
  const [lastAddedId, setLastAddedId] = useState<string | null>(null);

  /** Guards against a slow poll round overlapping the next tick. */
  const pollInFlight = useRef(false);

  /** Apply a successful listing. Separated from the fetch so the initial load
   *  can update state from the promise callback rather than synchronously
   *  inside an effect body, which cascades renders. */
  const applyList = useCallback((listed: StoredFile[]) => {
    setFiles(listed);
    setPhase("ready");
    setLoadError(null);
  }, []);

  const applyLoadFailure = useCallback((error: unknown) => {
    setPhase("error");
    setLoadError(
      error instanceof ApiError ? error.message : "Something went wrong loading your library.",
    );
  }, []);

  // Initial load. State is set from the promise's callbacks, not from the
  // effect body.
  useEffect(() => {
    const controller = new AbortController();
    listFiles(controller.signal).then(applyList, (error: unknown) => {
      if (controller.signal.aborted) return;
      applyLoadFailure(error);
    });
    return () => controller.abort();
  }, [applyList, applyLoadFailure]);

  // Poll the files that are still being processed. The effect re-runs whenever
  // the set of processing ids changes, and does nothing while that set is empty.
  const processingIds = files
    .filter((file) => isProcessing(file.status))
    .map((file) => file.id)
    .join(",");

  useEffect(() => {
    if (processingIds === "") return;
    const ids = processingIds.split(",");
    const controller = new AbortController();

    const tick = async () => {
      if (pollInFlight.current) return;
      pollInFlight.current = true;
      try {
        const results = await Promise.allSettled(
          ids.map((id) => getFile(id, controller.signal)),
        );
        if (controller.signal.aborted) return;

        const fresh = results
          .filter(
            (result): result is PromiseFulfilledResult<StoredFile> =>
              result.status === "fulfilled",
          )
          .map((result) => result.value);
        if (fresh.length === 0) return;

        setFiles((current) => {
          const byId = new Map(fresh.map((file) => [file.id, file]));
          let finished: StoredFile | null = null;
          const next = current.map((file) => {
            const updated = byId.get(file.id);
            if (!updated) return file;
            // Remember a file that has just settled, so it can be announced.
            if (isProcessing(file.status) && !isProcessing(updated.status)) {
              finished = updated;
            }
            return updated;
          });
          if (finished) {
            const message = completionAnnouncement(finished);
            if (message) setAnnouncement(message);
          }
          return next;
        });
      } finally {
        pollInFlight.current = false;
      }
    };

    const timer = setInterval(() => void tick(), POLL_INTERVAL_MS);
    return () => {
      controller.abort();
      clearInterval(timer);
    };
  }, [processingIds]);

  const addFiles = useCallback(async (selected: File[]) => {
    if (selected.length === 0) return;

    // Refuse what Noye cannot read before sending it. A dragged file never went
    // through the picker's `accept` filter, so without this the first error a
    // person sees is the API's wording rather than ours.
    const acceptable: File[] = [];
    const refused: RejectedUpload[] = [];
    for (const file of selected) {
      const reason = rejectionFor(file);
      if (reason) {
        refused.push({ key: `${file.name}-${Date.now()}-${refused.length}`, name: file.name, message: reason });
      } else {
        acceptable.push(file);
      }
    }
    if (refused.length > 0) {
      setRejected((current) => [...current, ...refused]);
      setAnnouncement(`${refused[0].name} was not added. ${refused[0].message}`);
    }
    if (acceptable.length === 0) return;

    setUploading((current) => [...current, ...acceptable.map((file) => file.name)]);

    for (const file of acceptable) {
      try {
        const created = await uploadFile(file);
        setFiles((current) => [created, ...current]);
        setLastAddedId(created.id);
        setAnnouncement(`${created.name} was added and is being indexed.`);
      } catch (error) {
        const message =
          error instanceof ApiError
            ? error.message
            : "Something went wrong adding this file.";
        setRejected((current) => [
          ...current,
          { key: `${file.name}-${Date.now()}`, name: file.name, message },
        ]);
        setAnnouncement(`${file.name} was not added. ${message}`);
      } finally {
        setUploading((current) => {
          const index = current.indexOf(file.name);
          if (index === -1) return current;
          return [...current.slice(0, index), ...current.slice(index + 1)];
        });
      }
    }
  }, []);

  const removeFile = useCallback(
    async (id: string) => {
      const target = files.find((file) => file.id === id);
      try {
        await deleteFileRequest(id);
        setFiles((current) => current.filter((file) => file.id !== id));
        setAnnouncement(target ? `${target.name} was removed.` : "The file was removed.");
      } catch (error) {
        const message =
          error instanceof ApiError ? error.message : "Something went wrong removing this file.";
        // A refused delete leaves the file intact on the server, so it stays on
        // screen too — with the reason attached.
        setRejected((current) => [
          ...current,
          { key: `remove-${id}-${Date.now()}`, name: target?.name ?? "This file", message },
        ]);
        setAnnouncement(`${target?.name ?? "The file"} was not removed. ${message}`);
      }
    },
    [files],
  );

  const dismissRejection = useCallback((key: string) => {
    setRejected((current) => current.filter((item) => item.key !== key));
  }, []);

  // Re-list when the tab regains focus. Ingestion can be started from another
  // tab, a second window, or the API directly, and without this the list only
  // ever reflects what this tab did itself. Quiet on purpose: it replaces the
  // list in place rather than showing the loading state again.
  useEffect(() => {
    const onFocus = () => {
      listFiles().then(
        (listed) => {
          setFiles(listed);
          setPhase("ready");
          setLoadError(null);
        },
        () => {
          // A failed background refresh leaves the last known list alone. The
          // next deliberate action reports the failure loudly enough.
        },
      );
    };
    window.addEventListener("focus", onFocus);
    return () => window.removeEventListener("focus", onFocus);
  }, []);

  const reload = useCallback(() => {
    setPhase("loading");
    listFiles().then(applyList, applyLoadFailure);
  }, [applyList, applyLoadFailure]);

  return {
    files,
    phase,
    loadError,
    uploading,
    rejected,
    announcement,
    lastAddedId,
    reload,
    addFiles,
    removeFile,
    dismissRejection,
  };
}
