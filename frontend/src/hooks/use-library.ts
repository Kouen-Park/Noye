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
  cancelFile as cancelFileRequest,
  deleteFile as deleteFileRequest,
  getFile,
  getIndexStatus,
  isProcessing,
  listFiles,
  rebuildIndex as rebuildIndexRequest,
  rejectionFor,
  reingestFile as reingestFileRequest,
  type IndexStatus,
  type RebuildStarted,
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
export type IntegrityPhase = "loading" | "ready" | "checking" | "rebuilding" | "error";

export interface Library {
  files: StoredFile[];
  phase: LoadPhase;
  /** Why the initial load failed. Distinct from a single file failing. */
  loadError: string | null;
  /** Uploads in flight, by display name, so the drop zone can report them. */
  uploading: string[];
  /** Files whose Stop request is waiting for a terminal status. */
  stoppingIds: string[];
  rejected: RejectedUpload[];
  /** The most recent thing worth announcing to a screen reader. */
  announcement: string;
  /** Set after an upload succeeds, so the page can move focus to the new card. */
  lastAddedId: string | null;
  integrity: IndexStatus | null;
  integrityPhase: IntegrityPhase;
  integrityError: string | null;
  rebuildResult: RebuildStarted | null;
  reload: () => void;
  checkIndex: () => Promise<void>;
  rebuildIndex: () => Promise<void>;
  addFiles: (selected: File[]) => Promise<void>;
  removeFile: (id: string) => Promise<void>;
  retryFile: (id: string) => Promise<void>;
  cancelFile: (id: string) => Promise<void>;
  dismissRejection: (key: string) => void;
}

export function useLibrary(): Library {
  const [files, setFiles] = useState<StoredFile[]>([]);
  const [phase, setPhase] = useState<LoadPhase>("loading");
  const [loadError, setLoadError] = useState<string | null>(null);
  const [uploading, setUploading] = useState<string[]>([]);
  const [stoppingIds, setStoppingIds] = useState<string[]>([]);
  const [rejected, setRejected] = useState<RejectedUpload[]>([]);
  const [announcement, setAnnouncement] = useState("");
  const [lastAddedId, setLastAddedId] = useState<string | null>(null);
  const [integrity, setIntegrity] = useState<IndexStatus | null>(null);
  const [integrityPhase, setIntegrityPhase] = useState<IntegrityPhase>("loading");
  const [integrityError, setIntegrityError] = useState<string | null>(null);
  const [rebuildResult, setRebuildResult] = useState<RebuildStarted | null>(null);

  /** Guards against a slow poll round overlapping the next tick. */
  const pollInFlight = useRef(false);
  /** The latest integrity request wins if a focus refresh overlaps a deep check. */
  const integrityRequest = useRef(0);
  /** A settled transition triggers one cheap integrity refresh, not a poll. */
  const processingWasActive = useRef(false);

  /** Apply a successful listing. Separated from the fetch so the initial load
   *  can update state from the promise callback rather than synchronously
   *  inside an effect body, which cascades renders. */
  const applyList = useCallback((listed: StoredFile[]) => {
    setFiles(listed);
    setStoppingIds((current) => current.filter((id) => listed.some((file) => file.id === id && isProcessing(file.status))));
    setPhase("ready");
    setLoadError(null);
  }, []);

  const applyLoadFailure = useCallback((error: unknown) => {
    setPhase("error");
    setLoadError(
      error instanceof ApiError ? error.message : "Something went wrong loading your library.",
    );
  }, []);

  const loadIntegrity = useCallback(
    async (
      deep: boolean,
      options: { announce?: boolean; signal?: AbortSignal } = {},
    ) => {
      const request = ++integrityRequest.current;
      try {
        const result = await getIndexStatus(deep, options.signal);
        if (options.signal?.aborted || request !== integrityRequest.current) return;
        setIntegrity(result);
        setIntegrityPhase("ready");
        setIntegrityError(null);
        if (options.announce) {
          if (deep && !result.point_check_complete) {
            setAnnouncement("The stored index could not be checked. Make sure Qdrant is running.");
          } else if (result.problems.length === 0) {
            setAnnouncement("The library index is healthy.");
          } else {
            setAnnouncement(
              `The index check found ${result.problems.length} ${result.problems.length === 1 ? "file" : "files"} that need attention.`,
            );
          }
        }
      } catch (error) {
        if (options.signal?.aborted || request !== integrityRequest.current) return;
        const message =
          error instanceof ApiError
            ? error.message
            : "Something went wrong checking the library index.";
        setIntegrityPhase("error");
        setIntegrityError(message);
        if (options.announce) setAnnouncement(`The index check failed. ${message}`);
      }
    },
    [],
  );

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

  // Integrity is separate from the file listing: a failed check must not hide a
  // usable library. The cheap source/model check makes no Qdrant round trips.
  useEffect(() => {
    const controller = new AbortController();
    const request = ++integrityRequest.current;
    getIndexStatus(false, controller.signal).then(
      (result) => {
        if (controller.signal.aborted || request !== integrityRequest.current) return;
        setIntegrity(result);
        setIntegrityPhase("ready");
        setIntegrityError(null);
      },
      (error: unknown) => {
        if (controller.signal.aborted || request !== integrityRequest.current) return;
        setIntegrityPhase("error");
        setIntegrityError(
          error instanceof ApiError
            ? error.message
            : "Something went wrong checking the library index.",
        );
      },
    );
    return () => controller.abort();
  }, []);

  // Poll the files that are still being processed. The effect re-runs whenever
  // the set of processing ids changes, and does nothing while that set is empty.
  const processingIds = files
    .filter((file) => isProcessing(file.status))
    .map((file) => file.id)
    .join(",");

  useEffect(() => {
    if (processingIds !== "") {
      processingWasActive.current = true;
      return;
    }
    if (!processingWasActive.current) return;
    processingWasActive.current = false;
    void loadIntegrity(false);
  }, [processingIds, loadIntegrity]);

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

        setStoppingIds((current) =>
          current.filter((id) => !fresh.some((file) => file.id === id && !isProcessing(file.status))),
        );

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
        void loadIntegrity(false);
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
    [files, loadIntegrity],
  );

  const retryFile = useCallback(async (id: string) => {
    const target = files.find((file) => file.id === id);
    try {
      const updated = await reingestFileRequest(id);
      setStoppingIds((current) => current.filter((item) => item !== id));
      setFiles((current) => current.map((file) => file.id === id ? updated : file));
      setAnnouncement(`${updated.name} is being indexed again.`);
    } catch (error) {
      const message = error instanceof ApiError ? error.message : "Could not retry this file.";
      setRejected((current) => [...current, { key: `retry-${id}-${Date.now()}`, name: target?.name ?? "This file", message }]);
      setAnnouncement(`${target?.name ?? "The file"} was not retried. ${message}`);
    }
  }, [files]);

  const cancelFile = useCallback(async (id: string) => {
    const target = files.find((file) => file.id === id);
    setStoppingIds((current) => current.includes(id) ? current : [...current, id]);
    try {
      const updated = await cancelFileRequest(id);
      if (!isProcessing(updated.status)) {
        setFiles((current) => current.map((file) => file.id === id ? updated : file));
        setStoppingIds((current) => current.filter((item) => item !== id));
        setAnnouncement(completionAnnouncement(updated) ?? `${updated.name} was stopped.`);
      } else {
        setAnnouncement(`Stopping ${target?.name ?? "the file"}.`);
      }
    } catch (error) {
      setStoppingIds((current) => current.filter((item) => item !== id));
      const message = error instanceof ApiError ? error.message : "Could not stop this file.";
      setRejected((current) => [...current, { key: `cancel-${id}-${Date.now()}`, name: target?.name ?? "This file", message }]);
      setAnnouncement(`${target?.name ?? "The file"} was not stopped. ${message}`);
    }
  }, [files]);

  const dismissRejection = useCallback((key: string) => {
    setRejected((current) => current.filter((item) => item.key !== key));
  }, []);

  const checkIndex = useCallback(async () => {
    setIntegrityPhase("checking");
    setIntegrityError(null);
    await loadIntegrity(true, { announce: true });
  }, [loadIntegrity]);

  const rebuildIndex = useCallback(async () => {
    setIntegrityPhase("rebuilding");
    setIntegrityError(null);
    setRebuildResult(null);
    try {
      const result = await rebuildIndexRequest();
      setRebuildResult(result);
      setIntegrityPhase("ready");
      setAnnouncement(
        result.queued === 0
          ? "No files were queued for rebuilding."
          : `${result.queued} ${result.queued === 1 ? "file is" : "files are"} being rebuilt.`,
      );

      try {
        const listed = await listFiles();
        applyList(listed);
      } catch {
        setIntegrityError(
          "The rebuild started, but the file list could not be refreshed. It will update when this tab regains focus.",
        );
      }

      if (result.queued === 0) void loadIntegrity(false);
    } catch (error) {
      const message =
        error instanceof ApiError ? error.message : "Something went wrong starting the rebuild.";
      setIntegrityPhase("error");
      setIntegrityError(message);
      setAnnouncement(`The index was not rebuilt. ${message}`);
    }
  }, [applyList, loadIntegrity]);

  // Re-list when the tab regains focus. Ingestion can be started from another
  // tab, a second window, or the API directly, and without this the list only
  // ever reflects what this tab did itself. Quiet on purpose: it replaces the
  // list in place rather than showing the loading state again.
  useEffect(() => {
    const onFocus = () => {
      listFiles().then(
        (listed) => {
          setFiles(listed);
          setStoppingIds((current) => current.filter((id) => listed.some((file) => file.id === id && isProcessing(file.status))));
          setPhase("ready");
          setLoadError(null);
        },
        () => {
          // A failed background refresh leaves the last known list alone. The
          // next deliberate action reports the failure loudly enough.
        },
      );
      void loadIntegrity(false);
    };
    window.addEventListener("focus", onFocus);
    return () => window.removeEventListener("focus", onFocus);
  }, [loadIntegrity]);

  const reload = useCallback(() => {
    setPhase("loading");
    setIntegrityPhase("loading");
    setIntegrityError(null);
    listFiles().then(applyList, applyLoadFailure);
    void loadIntegrity(false);
  }, [applyList, applyLoadFailure, loadIntegrity]);

  return {
    files,
    phase,
    loadError,
    uploading,
    stoppingIds,
    rejected,
    announcement,
    lastAddedId,
    integrity,
    integrityPhase,
    integrityError,
    rebuildResult,
    reload,
    checkIndex,
    rebuildIndex,
    addFiles,
    removeFile,
    retryFile,
    cancelFile,
    dismissRejection,
  };
}
