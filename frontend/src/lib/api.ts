/**
 * Client for the Noye backend.
 *
 * Calls go straight from the browser to FastAPI rather than through a Next
 * rewrite. Two reasons: it keeps exercising the backend's CORS allow-list,
 * which is the real protection on a server that has no authentication; and in
 * Phase 5 the desktop build talks directly to a local backend, so a proxy hop
 * here would be a development-only fiction.
 *
 * Types mirror `FileOut` in backend/app/api/files.py. When that changes, this
 * changes with it.
 */

/** Where a file is in the ingestion pipeline. Mirrors `FileStatus`. */
export type FileStatus =
  | "UPLOADING"
  | "EXTRACTING"
  | "CHUNKING"
  | "EMBEDDING"
  | "READY"
  | "FAILED";

/** Supported source formats. Mirrors `FileType`. */
export type FileType = "pdf" | "md" | "txt";

/** A file as the API reports it. `path` is deliberately absent server-side. */
export interface StoredFile {
  id: string;
  name: string;
  file_type: FileType;
  size: number;
  status: FileStatus;
  error: string | null;
  /** Null for formats without pages, and until extraction has run. */
  page_count: number | null;
  chunk_count: number;
  created_at: string;
  updated_at: string;
}

export const TERMINAL_STATUSES: readonly FileStatus[] = ["READY", "FAILED"];

export function isProcessing(status: FileStatus): boolean {
  return !TERMINAL_STATUSES.includes(status);
}

/**
 * What Noye can read, in one place.
 *
 * The file input's `accept` only filters the picker — it does nothing for a
 * dragged file. So the same list drives both the attribute and the check below,
 * and a dropped `.docx` is refused here rather than making a round trip to be
 * refused there.
 */
export const ACCEPTED_EXTENSIONS: readonly string[] = [
  "pdf",
  "md",
  "markdown",
  "txt",
  "text",
];

export const ACCEPT_ATTRIBUTE = ACCEPTED_EXTENSIONS.map((ext) => `.${ext}`).join(",");

/**
 * Why Noye will not take this file, or null if it will.
 *
 * Checked before uploading so the first error a person sees is written for them,
 * naming what Noye does read, rather than being whatever the API happened to
 * say.
 */
export function rejectionFor(file: File): string | null {
  const extension = file.name.includes(".")
    ? file.name.split(".").pop()!.toLowerCase()
    : "";
  if (!ACCEPTED_EXTENSIONS.includes(extension)) {
    return "Noye reads PDF, Markdown, and plain text files. This one isn't one of those.";
  }
  if (file.size === 0) {
    return "This file is empty, so there is nothing to index.";
  }
  return null;
}

/**
 * A failed request, carrying the backend's own explanation.
 *
 * The backend writes its `detail` messages for a person to read, so they are
 * surfaced as-is rather than replaced with a generic message.
 */
export class ApiError extends Error {
  constructor(
    readonly status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }

  /** True when the backend could not be reached at all. */
  get isOffline(): boolean {
    return this.status === 0;
  }
}

const BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

async function request(path: string, init?: RequestInit): Promise<Response> {
  let response: Response;
  try {
    response = await fetch(`${BASE_URL}${path}`, init);
  } catch {
    // A network-level failure is the common case in local development: the
    // backend simply is not running. Status 0 marks that apart from an HTTP
    // error so the UI can tell the user which one happened.
    throw new ApiError(0, "Could not reach Noye's backend.");
  }

  if (!response.ok) {
    throw new ApiError(response.status, await readDetail(response));
  }
  return response;
}

/** Pull FastAPI's `detail` out of an error body, falling back to the status. */
async function readDetail(response: Response): Promise<string> {
  try {
    const body: unknown = await response.json();
    if (body && typeof body === "object" && "detail" in body) {
      const detail = (body as { detail: unknown }).detail;
      if (typeof detail === "string" && detail.length > 0) return detail;
    }
  } catch {
    // Not JSON, or an empty body. Fall through to the generic message.
  }
  return `The request failed (${response.status}).`;
}

/** One matching passage and where it came from. Mirrors `SearchHit`. */
export interface SearchHit {
  content: string;
  file_id: string;
  file_name: string;
  /** Null for formats without pages. Never 0 — that would read as a real page. */
  page_number: number | null;
  chunk_index: number;
  score: number;
}

/** Results for one query. Mirrors `SearchResponse`. */
export interface SearchResponse {
  query: string;
  results: SearchHit[];
  /**
   * How many sources the query could match against. Zero means nothing has
   * finished indexing, which needs different words on screen from a query that
   * simply found nothing.
   */
  searched_files: number;
}

/** Find passages whose meaning matches the query. Searches READY files only. */
export async function searchKnowledge(
  query: string,
  options: { limit?: number; signal?: AbortSignal } = {},
): Promise<SearchResponse> {
  const params = new URLSearchParams({ q: query });
  if (options.limit !== undefined) params.set("limit", String(options.limit));
  const response = await request(`/search?${params}`, { signal: options.signal });
  return (await response.json()) as SearchResponse;
}

/**
 * Where to open a file's saved original.
 *
 * A plain URL rather than a fetch, because the point is to hand it to the
 * browser: a PDF opens in its viewer, and the `#page=N` fragment lands on the
 * cited page. Pageless formats get no fragment rather than a made-up one.
 */
export function sourceUrl(fileId: string, pageNumber: number | null = null): string {
  const base = `${BASE_URL}/files/${encodeURIComponent(fileId)}/source`;
  return pageNumber === null ? base : `${base}#page=${pageNumber}`;
}

// --- chat --------------------------------------------------------------------

export type Role = "user" | "assistant";

/**
 * One passage that was given to the model as context for an answer.
 *
 * Deliberately not "a source that supports the answer". Vector search always
 * returns its nearest neighbours, so a question the documents do not cover still
 * retrieves passages and the model then declines — correctly — while these remain
 * attached. The UI must say what these are rather than implying they prove
 * anything.
 */
export interface ChatCitation {
  file_id: string;
  file_name: string;
  page_number: number | null;
  /** The retrieved chunks behind this citation, so the passages stay inspectable. */
  chunk_indexes: number[];
  score: number;
  /** "Algorithms.pdf — page 34", or just the file name. */
  label: string;
}

/** One turn. `error` is set when answering failed; the question is still stored. */
export interface ChatMessage {
  id: string;
  role: Role;
  content: string;
  error: string | null;
  citations: ChatCitation[];
  created_at: string;
}

export interface ChatConversation {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
  messages: ChatMessage[];
}

/** A conversation in the sidebar. Carries no messages — they are not shown there. */
export interface ConversationSummary {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
  message_count: number;
}

export interface AskResponse {
  conversation_id: string;
  conversation_title: string;
  question: ChatMessage;
  answer: ChatMessage;
  /** Zero means nothing has finished indexing — different from finding no passage. */
  searched_files: number;
}

/**
 * Ask a question, optionally continuing a conversation.
 *
 * No AbortSignal: a local model can take minutes, and abandoning the request
 * would not stop the work or prevent the turn being recorded. The answer is
 * fetched again on the next read either way.
 */
export async function askQuestion(
  question: string,
  conversationId?: string,
): Promise<AskResponse> {
  const response = await request("/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(
      conversationId === undefined
        ? { question }
        : { question, conversation_id: conversationId },
    ),
  });
  return (await response.json()) as AskResponse;
}

/** Conversations, most recently active first. */
export async function listConversations(signal?: AbortSignal): Promise<ConversationSummary[]> {
  const response = await request("/chat/conversations", { signal });
  return (await response.json()) as ConversationSummary[];
}

/** One conversation with its messages and their stored citations. */
export async function readConversation(
  id: string,
  signal?: AbortSignal,
): Promise<ChatConversation> {
  const response = await request(`/chat/conversations/${encodeURIComponent(id)}`, { signal });
  return (await response.json()) as ChatConversation;
}

export async function renameConversation(id: string, title: string): Promise<ChatConversation> {
  const response = await request(`/chat/conversations/${encodeURIComponent(id)}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ title }),
  });
  return (await response.json()) as ChatConversation;
}

/** Delete a conversation. The documents it drew on are untouched. */
export async function deleteConversation(id: string): Promise<void> {
  await request(`/chat/conversations/${encodeURIComponent(id)}`, { method: "DELETE" });
}

// --- documents ---------------------------------------------------------------

/** A source a document's first draft was built from, as it was then. */
export interface DocumentCitation {
  file_id: string;
  file_name: string;
  page_number: number | null;
  chunk_indexes: number[];
  score: number;
  label: string;
}

export interface NoyeDocument {
  id: string;
  title: string;
  /** Markdown, as the user last left it. This is the document, not a cache. */
  content: string;
  /**
   * Where a generated document came from. These may point at a conversation that
   * has since been deleted — a document outlives its scaffolding.
   */
  source_conversation_id: string | null;
  source_message_id: string | null;
  source_instruction: string | null;
  citations: DocumentCitation[];
  created_at: string;
  updated_at: string;
}

/** A document in the list. No body — the list shows titles and dates. */
export interface DocumentSummary {
  id: string;
  title: string;
  excerpt: string;
  is_generated: boolean;
  created_at: string;
  updated_at: string;
}

export async function listDocuments(signal?: AbortSignal): Promise<DocumentSummary[]> {
  const response = await request("/documents", { signal });
  return (await response.json()) as DocumentSummary[];
}

export async function readDocument(
  id: string,
  signal?: AbortSignal,
): Promise<NoyeDocument> {
  const response = await request(`/documents/${encodeURIComponent(id)}`, { signal });
  return (await response.json()) as NoyeDocument;
}

/** Create a document from nothing, or from text the user already has. */
export async function createDocument(
  title: string,
  content = "",
): Promise<NoyeDocument> {
  const response = await request("/documents", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ title, content }),
  });
  return (await response.json()) as NoyeDocument;
}

/**
 * Draft a document from a stored answer.
 *
 * No AbortSignal, for the same reason as `askQuestion`: a local model can take
 * minutes, and abandoning the request would not stop the work.
 */
export async function generateDocument(
  messageId: string,
  instruction: string,
): Promise<NoyeDocument> {
  const response = await request("/documents/generate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message_id: messageId, instruction }),
  });
  return (await response.json()) as NoyeDocument;
}

/**
 * Save an edit. Omitted fields are left alone; an empty `content` is a real
 * value, because a user may clear a document's body.
 */
export async function updateDocument(
  id: string,
  patch: { title?: string; content?: string },
): Promise<NoyeDocument> {
  const response = await request(`/documents/${encodeURIComponent(id)}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(patch),
  });
  return (await response.json()) as NoyeDocument;
}

export async function deleteDocument(id: string): Promise<void> {
  await request(`/documents/${encodeURIComponent(id)}`, { method: "DELETE" });
}

/** Where to download a document's Markdown. A plain URL, handed to the browser. */
export function documentExportUrl(id: string): string {
  return `${BASE_URL}/documents/${encodeURIComponent(id)}/export.md`;
}

// --- index integrity ---------------------------------------------------------

export type IndexProblem =
  | "MISSING_SOURCE"
  | "SOURCE_CHANGED"
  | "MODEL_CHANGED"
  | "POINTS_MISSING";

/** One file whose original or derived index no longer agrees with SQLite. */
export interface FileIntegrityProblem {
  file_id: string;
  file_name: string;
  problems: IndexProblem[];
  searchable: boolean;
  indexed_points: number | null;
  expected_points: number | null;
}

/** Whether the derived index still describes the library. */
export interface IndexStatus {
  embedding_model: string;
  ready_files: number;
  searchable_files: number;
  deep: boolean;
  /** False after a requested deep check when Qdrant could not be inspected. */
  point_check_complete: boolean;
  problems: FileIntegrityProblem[];
}

export interface SkippedRebuildFile {
  file_id: string;
  file_name: string;
  reason: string;
}

/** The rebuild plan accepted by the backend before background work begins. */
export interface RebuildStarted {
  queued: number;
  skipped: SkippedRebuildFile[];
  collection_recreated: boolean;
  embedding_model: string;
}

/** Check cheap source/model integrity, optionally including Qdrant point counts. */
export async function getIndexStatus(
  deep = false,
  signal?: AbortSignal,
): Promise<IndexStatus> {
  const response = await request(`/index/status?deep=${deep}`, { signal });
  return (await response.json()) as IndexStatus;
}

/** Queue every available source for re-ingestion. */
export async function rebuildIndex(): Promise<RebuildStarted> {
  const response = await request("/index/rebuild", { method: "POST" });
  return (await response.json()) as RebuildStarted;
}

// --- files -------------------------------------------------------------------

/** Every file, newest first. */
export async function listFiles(signal?: AbortSignal): Promise<StoredFile[]> {
  const response = await request("/files", { signal });
  return (await response.json()) as StoredFile[];
}

/** One file's current state. This is the polling endpoint. */
export async function getFile(id: string, signal?: AbortSignal): Promise<StoredFile> {
  const response = await request(`/files/${encodeURIComponent(id)}`, { signal });
  return (await response.json()) as StoredFile;
}

/**
 * Upload a file and start ingesting it.
 *
 * Returns as soon as the file is on disk, with the record in `UPLOADING`.
 * Progress is observed by polling {@link getFile}.
 */
export async function uploadFile(file: File, signal?: AbortSignal): Promise<StoredFile> {
  const body = new FormData();
  body.append("file", file);
  // Content-Type is deliberately unset: the browser must add the multipart
  // boundary itself.
  const response = await request("/files", { method: "POST", body, signal });
  return (await response.json()) as StoredFile;
}

/**
 * Delete a source completely — vectors, original, and metadata.
 *
 * Irreversible. The backend removes vectors first and fails the whole request
 * if that step fails, so a rejected delete leaves the file usable.
 */
export async function deleteFile(id: string, signal?: AbortSignal): Promise<void> {
  await request(`/files/${encodeURIComponent(id)}`, { method: "DELETE", signal });
}

/** Start processing the saved original again. */
export async function reingestFile(id: string): Promise<StoredFile> {
  const response = await request(`/files/${encodeURIComponent(id)}/reingest`, { method: "POST" });
  return (await response.json()) as StoredFile;
}

/** Ask the backend to stop a queued or running ingestion. */
export async function cancelFile(id: string): Promise<StoredFile> {
  const response = await request(`/files/${encodeURIComponent(id)}/cancel`, { method: "POST" });
  return (await response.json()) as StoredFile;
}
