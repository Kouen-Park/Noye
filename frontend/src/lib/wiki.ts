import { ApiError, sourceUrl } from "@/lib/api";
import { apiBaseUrl } from "@/lib/runtime";

export interface WikiScope { mode: "all" | "empty" | "chosen"; source_ids: string[]; root_ids: string[] }
export const ALL_WIKI_SOURCES: WikiScope = { mode: "all", source_ids: [], root_ids: [] };
export interface WikiSource {
  source_id: string; root_id: string | null; relative_path: string; name: string;
  version: string; availability: string; processing_state: string; error: string | null;
}
export interface WikiEvidence {
  id: string; source: { source_id: string; root_id: string | null; name: string;
    source_hash: string; source_version: string; relative_path: string };
  page_number: number | null; passage_index: number; start: number; end: number; text: string;
  current_status: string;
}
export interface WikiRevision {
  id: string; wiki_id: string; parent_id: string | null; origin: "generated" | "user" | "proposal";
  title: string; content: string; created_at: string; evidence: WikiEvidence[];
  metadata: { model?: string; prompt_version?: string; processing_seconds?: number;
    primary_category?: string; tags?: string[]; batch_count?: number;
    contributors?: { wiki_id: string; revision_id: string }[] };
}
export interface WikiSummary {
  id: string; title: string; kind: "source" | "concept" | "project" | "analysis";
  current_revision: string | null; publication_error: string | null; updated_at: string;
  proposal_count: number;
}
export interface WikiPage extends WikiSummary {
  revision: WikiRevision | null;
  revisions: Pick<WikiRevision, "id" | "origin" | "title" | "created_at">[];
  relations: { id: string; origin_id: string; target_id: string; origin_title: string;
    target_title: string; kind: string; reason: string; target_revision: string;
    target_current_revision?: string }[];
}
export interface WikiJob {
  id: string; kind: string; subject_id: string; state: string; stage: string;
  completed: number; total: number; error: string | null; artifact_id: string | null;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try { response = await fetch(`${apiBaseUrl()}${path}`, init); }
  catch (error) { if (error instanceof DOMException && error.name === "AbortError") throw error;
    throw new ApiError(0, "Could not reach Noye's backend."); }
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new ApiError(response.status, typeof body.detail === "string" ? body.detail : "Wiki request failed.");
  }
  return response.json() as Promise<T>;
}
const json = (method: string, value: unknown): RequestInit => ({ method,
  headers: { "Content-Type": "application/json" }, body: JSON.stringify(value) });
export const listWiki = (scope = ALL_WIKI_SOURCES, signal?: AbortSignal) =>
  request<WikiSummary[]>("/wiki/list", { ...json("POST", scope), signal });
export const listWikiSources = (signal?: AbortSignal) => request<WikiSource[]>("/wiki/sources", { signal });
export const readWiki = (id: string, scope = ALL_WIKI_SOURCES, signal?: AbortSignal) =>
  request<WikiPage>(`/wiki/${encodeURIComponent(id)}/read`, { ...json("POST", scope), signal });
export const readWikiRevision = (id: string, revision: string, scope = ALL_WIKI_SOURCES) =>
  request<WikiRevision>(`/wiki/${encodeURIComponent(id)}/revisions/${encodeURIComponent(revision)}/read`, json("POST", scope));
export const generateWiki = (sourceId: string, scope = ALL_WIKI_SOURCES) =>
  request<WikiJob>("/wiki/generate", json("POST", { source_id: sourceId, scope }));
export const editWiki = (id: string, expected: string, title: string, content: string, scope = ALL_WIKI_SOURCES) =>
  request<WikiPage>(`/wiki/${encodeURIComponent(id)}`, json("PATCH", { expected_revision: expected, title, content, scope }));
export const adoptWiki = (id: string, revision: string, expected: string, scope = ALL_WIKI_SOURCES) =>
  request<WikiPage>(`/wiki/${encodeURIComponent(id)}/adopt`, json("POST", { revision_id: revision, expected_revision: expected, scope }));
export const saveWikiAnalysis = (title: string, content: string, wikiIds: string[], scope: WikiScope) =>
  request<WikiPage>("/wiki/analyses", json("POST", { title, content, wiki_ids: wikiIds, scope }));
export const listWikiJobs = (signal?: AbortSignal) =>
  request<WikiJob[]>("/knowledge-jobs", { signal }).then(jobs => jobs.filter(job => job.kind === "wiki"));
export const wikiJobAction = (id: string, action: "cancel" | "resume") =>
  request<WikiJob>(`/knowledge-jobs/${encodeURIComponent(id)}/${action}`, { method: "POST" });
export const wikiOriginalUrl = (evidence: WikiEvidence) =>
  sourceUrl(evidence.source.source_id, evidence.page_number);
