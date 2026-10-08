import type { KnowledgeStageEvent } from "@/components/knowledge-job-stages";
import { ApiError, sourceUrl } from "@/lib/api";
import { apiBaseUrl } from "@/lib/runtime";

export interface WikiScope { mode: "all" | "empty" | "chosen"; source_ids: string[]; root_ids: string[] }
export const ALL_WIKI_SOURCES: WikiScope = { mode: "all", source_ids: [], root_ids: [] };
export function wikiScopeFromUrl(value: string | null): WikiScope {
  if (!value) return ALL_WIKI_SOURCES;
  try {
    const scope = JSON.parse(value);
    if (["all", "empty", "chosen"].includes(scope.mode) && [scope.source_ids, scope.root_ids].every(ids => Array.isArray(ids) && ids.every(id => typeof id === "string"))) return scope;
  } catch { /* Invalid explicit scope must not broaden to all sources. */ }
  return { mode: "empty", source_ids: [], root_ids: [] };
}
export interface WikiContributor { wiki_id: string; revision_id?: string }
export function wikiHref(id: string, scope: WikiScope, revision?: string): string {
  return `/wiki/?w=${encodeURIComponent(id)}&scope=${encodeURIComponent(JSON.stringify(scope))}`
    + (revision ? `&revision=${encodeURIComponent(revision)}` : "");
}

/** Markdown cannot grant a new material scope or arbitrary local-file navigation. */
export function wikiLinkHref(href: string, scope: WikiScope, contributors: WikiContributor[] = []): string | undefined {
  if (!href) return undefined;
  if (href.startsWith("#")) return href;
  let target: URL;
  try { target = new URL(href, "https://noye.invalid/wiki/"); }
  catch { return undefined; }
  const local = target.origin === "https://noye.invalid"
    || (["http:", "https:"].includes(target.protocol)
      && ["localhost", "127.0.0.1", "[::1]", "tauri.localhost"].includes(target.hostname));
  if (!local) return href;
  if (scope.mode === "empty") return undefined;
  let identifier: string | null = null;
  let revision: string | undefined;
  if (["/wiki", "/wiki/"].includes(target.pathname)) {
    identifier = target.searchParams.get("w");
    revision = target.searchParams.get("revision") ?? undefined;
  } else {
    const portable = target.pathname.match(/^\/(?:sources|concepts|projects|analyses)\/([^/]+)\.md$/);
    const contributor = contributors.find(item => item.wiki_id === portable?.[1]);
    identifier = contributor?.wiki_id ?? null;
  }
  if (!identifier) return undefined;
  const captured = contributors.find(item => item.wiki_id === identifier);
  return wikiHref(identifier, scope, captured?.revision_id ?? revision) + target.hash;
}
export function wikiPreviewContent(content: string, contributors: WikiContributor[] | undefined, scope: WikiScope): string {
  let preview = content.replace(/^<!-- Wiki ID: [0-9a-f-]+; model: [^\n]* -->\r?\n\r?\n/, "");
  for (const { wiki_id, revision_id } of contributors ?? []) {
    const target = wikiHref(wiki_id, scope, revision_id);
    preview = preview.replaceAll(`](../sources/${wiki_id}.md)`, `](${target})`);
  }
  return preview;
}
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
  events?: KnowledgeStageEvent[];
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
