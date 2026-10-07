import { ApiError, type NoyeDocument } from "@/lib/api";
import { apiBaseUrl } from "@/lib/runtime";
import { type WikiScope, type WikiJob, type WikiEvidence } from "@/lib/wiki";

export interface CoverageSource {
  source_id: string; root_id: string | null; relative_path: string; version: string | null;
  availability: string; processing_state: string; state: string; reason: string | null;
  passages_read: number; characters_read: number; characters_processed: number;
  fragments_processed: number; no_text_pages: number[];
}
export interface Coverage { inventory_count: number; inventory_mode: string; partial: boolean; sources: CoverageSource[];
  synthesis_limits?: { section_id: string; reason: string }[] }
export interface DocumentRevision {
  id: string; origin: "generated" | "user"; title: string; content: string; created_at: string;
  metadata: { coverage: Coverage; model: string; prompt_version: string; processing_seconds: number;
    citations: (WikiEvidence & { quote: string; quote_start: number; quote_end: number })[]; request_id: string; scope: WikiScope };
}
export interface SourceDocument extends NoyeDocument {
  revision: DocumentRevision;
  revisions: Pick<DocumentRevision, "id" | "origin" | "title" | "created_at">[];
}
export interface DocumentTask {
  job: WikiJob | null;
  request: { id: string; artifact_id: string | null; clarification: string | null;
    request: { instruction: string; conversation_id: string; scope: WikiScope };
    manifest: { source_id: string; relative_path: string; version: string | null }[];
    plan: { selected_ids: string[] } | null;
    report: Partial<Coverage> };
}
async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try { response = await fetch(`${apiBaseUrl()}/source-documents${path}`, init); }
  catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") throw error;
    throw new ApiError(0, "Could not reach Noye's backend.");
  }
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new ApiError(response.status, typeof body.detail === "string" ? body.detail : "Document request failed.");
  }
  return response.json() as Promise<T>;
}
const json = (method: string, value: unknown): RequestInit => ({ method,
  headers: { "Content-Type": "application/json" }, body: JSON.stringify(value) });
export const generateSourceDocument = (instruction: string, scope: WikiScope, conversationId?: string,
  inventoryMode: "auto" | "collection" | "relevant" = "auto", requestId = crypto.randomUUID()) =>
  request<DocumentTask>("/generate", json("POST", { request_id: requestId, instruction, scope,
    conversation_id: conversationId ?? null, inventory_mode: inventoryMode }));
export const listDocumentTasks = (conversationId: string, signal?: AbortSignal) =>
  request<DocumentTask[]>(`/requests?conversation_id=${encodeURIComponent(conversationId)}`, { signal });
export const readSourceDocument = (id: string, revision?: string, signal?: AbortSignal) =>
  request<SourceDocument>(`/${encodeURIComponent(id)}${revision ? `?revision=${encodeURIComponent(revision)}` : ""}`, { signal });
export const editSourceDocument = (id: string, expected: string, patch: { title: string; content: string }) =>
  request<SourceDocument>(`/${encodeURIComponent(id)}`, json("PATCH", { ...patch, expected_revision: expected }));
export const sourceDocumentExportUrl = (id: string, revision: string, provenance = false) =>
  `${apiBaseUrl()}/source-documents/${encodeURIComponent(id)}/export.md?revision=${encodeURIComponent(revision)}&provenance=${provenance}`;
export function documentScope(ids: string[] | null): WikiScope {
  return { mode: ids === null ? "all" : ids.length ? "chosen" : "empty", source_ids: ids ?? [], root_ids: [] };
}
export function isDocumentIntent(text: string): boolean {
  return /\b(create|write|generate|draft|make)\b.{0,120}\b(document|report|notes|analysis|comparison)\b/i.test(text)
    || /(문서|보고서|노트|비교표|정리본).{0,80}(작성|만들|생성)|(작성|만들|생성).{0,80}(문서|보고서|노트|비교표|정리본)/.test(text);
}

export function isSourceDocument(document: NoyeDocument): document is SourceDocument {
  return "revision" in document && "revisions" in document;
}
