"use client";

export type Language = "en" | "bn";
export interface BilingualText { en: string; bn: string }
export interface LearningProgress {
  completed_step_ids: string[]; is_completed: boolean; updated_at: string | null; percent: number;
}
export interface LearningGuide {
  slug: string; title: BilingualText; summary: BilingualText; category: string; estimated_minutes: number;
  steps: { id: string; title: BilingualText; description: BilingualText; checklist: BilingualText[]; module_path: string }[];
  sources: { title: string; url: string }[]; progress: LearningProgress;
}
export interface GlossaryEntry {
  slug: string; term: BilingualText; definition: BilingualText; example: BilingualText; category: string;
}
export interface GlossaryResult { items: GlossaryEntry[]; categories: string[] }
export interface EducationExplainOptions { language: Language; provider: AIProvider; request_id: string }
export interface BeginnerExplanation {
  user_paper_id: number; language: Language; title: string;
  supported_evidence: { chunk_id: number; document_id: number; document_version: number; page_number: number; paper_title: string; quoted_snippet: string }[];
  beginner_explanation: string; missing_information: string; follow_up_questions: string[];
  provider_used: string; model_used: string; evidence_status: "supported" | "partial_interpretation" | "insufficient_evidence";
  plain_language_interpretation: { focus: "question" | "method" | "findings" | "limitations"; explanation: string; evidence_status: "partial_interpretation"; evidence: BeginnerExplanation["supported_evidence"] }[];
  mode_notice: string; term_explanations: { term: string; definition: string }[];
  response_kind: "beginner_guide_with_source_quotes";
}
export type TeamRole = "owner" | "editor" | "viewer";
export type CollaboratorRole = Exclude<TeamRole, "owner">;
export interface TeamWorkspaceInput { name: string; description: string | null }
export interface TeamWorkspace extends TeamWorkspaceInput {
  id: number; owner_id: number; my_role: TeamRole; member_count: number;
  shared_collection_count: number; note_count: number; created_at: string; updated_at: string;
}
export interface TeamMember {
  user_id: number; username: string; role: TeamRole; invited_by_id: number | null; joined_at: string;
}
export interface SharedTeamPaper {
  user_paper_id: number; title: string; authors: string | null; source: string | null;
  url: string | null; doi: string | null;
}
export interface TeamCollection {
  id: number; collection_id: number; name: string; description: string | null;
  shared_by_id: number; shared_at: string; papers: SharedTeamPaper[]; total_papers?: number; papers_truncated?: boolean;
}
export interface TeamNoteInput { title: string; content: string; user_paper_id?: number | null }
export interface TeamNote extends TeamNoteInput {
  id: number; workspace_id: number; author_id: number; author_username: string;
  created_at: string; updated_at: string;
}
export interface TeamDetail extends TeamWorkspace {
  members: TeamMember[]; collections: TeamCollection[]; notes: TeamNote[];
  members_truncated?: boolean; collections_truncated?: boolean; notes_truncated?: boolean;
}
export type ProjectStatus = "planning" | "active" | "review" | "completed" | "archived";
export type TaskStatus = "todo" | "in_progress" | "done";
export interface ProjectInput {
  title: string; description: string | null; objectives: string[]; status: ProjectStatus;
  target_deadline: string | null; collection_id: number | null;
}
export interface ResearchProject extends ProjectInput {
  id: number; progress_percent: number; revision: number; created_at: string; updated_at: string;
  paper_count: number; task_count: number; completed_task_count: number;
}
export interface ProjectPaper {
  id: number; user_paper_id: number; role_in_project: string | null;
  added_at: string; title: string; authors: string | null; reading_status: ReadingStatus;
}
export interface ProjectNoteInput { title: string; content: string; user_paper_id: number | null }
export interface ResearchNote extends ProjectNoteInput { id: number; project_id: number; created_at: string; updated_at: string }
export interface ProjectTaskInput { title: string; description: string | null; is_milestone: boolean; status: TaskStatus; due_date: string | null }
export interface ProjectTask extends ProjectTaskInput { id: number; project_id: number; completed_at: string | null; created_at: string; updated_at: string }
export interface ProjectDetail extends ResearchProject {
  papers: ProjectPaper[]; notes: ResearchNote[]; tasks: ProjectTask[];
  conversations: Pick<Conversation, "id" | "title" | "language" | "updated_at">[];
}
export type GraphOrigin = "verified_metadata" | "inferred_similarity";
export interface GraphNode { id: string; type: "paper" | "author" | "topic" | "tag" | "project"; label: string; origin: GraphOrigin; provenance: string; user_paper_id?: number | null; project_id?: number | null }
export interface GraphEdge { id: string; source: string; target: string; type: string; origin: GraphOrigin; provenance: string }
export interface KnowledgeGraph { nodes: GraphNode[]; edges: GraphEdge[]; truncated: boolean; limits: { papers: number; nodes: number; edges: number }; project_id: number | null; project_scope?: { total_projects: number; included_projects: number; truncated: boolean } }
export interface AnalyticsOverview {
  totals: { saved_papers: number; indexed_papers: number; analyzed_papers: number; projects: number };
  publication_years: { year: number; count: number; provenance: string }[];
  unknown_publication_year_count: number;
  reading_funnel: { status: ReadingStatus; count: number }[];
  authors: { name: string; count: number }[];
  coauthors: { source: string; target: string; count: number }[];
  venues: { name: string; count: number; provenance: string }[];
  sources: { name: string; count: number }[];
  topics: { name: string; count: number; origin: GraphOrigin }[];
  tags: { id: number; name: string; color: string | null; count: number }[];
  coverage: { saved: number; indexed: number; analyzed: number; indexed_percent: number; analyzed_percent: number; analysis_freshness?: { checked_papers: number; unchecked_papers: number; truncated: boolean; paper_limit: number; chunk_limit: number; chunk_rows_budgeted: number } };
  scope: { project_id: number | null; total_papers: number; included_papers: number; truncated: boolean };
  project_scope?: { total_projects: number; included_projects: number; truncated: boolean };
}
export interface ResearchTimeline {
  items: { id: string; type: string; title: string; occurred_at: string; user_paper_id?: number | null; project_id?: number | null; provenance: string }[];
  truncated: boolean; limit: number; project_id: number | null;
}
export type Theme = "system" | "light" | "dark";
export type Privacy = "private" | "public";

export interface User {
  id: number;
  username: string;
  email: string;
  is_verified: boolean;
}

export interface ProfileInput {
  full_name: string | null;
  bio: string | null;
  institution: string | null;
  academic_role: string | null;
  avatar_url: string | null;
}

export interface Profile extends ProfileInput {
  id: number;
  user_id: number;
  updated_at: string;
}

export interface PreferenceInput {
  language: Language;
  theme: Theme;
  privacy_default: Privacy;
  allow_external_ai: boolean;
}

export interface Preferences extends PreferenceInput {
  id: number;
  user_id: number;
}

export interface SessionInfo {
  id: string;
  ip_address: string | null;
  user_agent: string | null;
  created_at: string;
  expires_at: string;
}

export interface AuditEvent {
  id: number;
  action: string;
  resource_type: string | null;
  resource_id: string | null;
  details: Record<string, unknown> | null;
  created_at: string;
}

export interface PaperInput {
  title: string;
  authors?: string | null;
  abstract?: string | null;
  source?: string | null;
  url?: string | null;
}

export interface Paper extends PaperInput {
  id: number;
}

export interface SavedPaper extends Paper {
  owner_id: number;
  created_at: string;
}

export interface PaginatedPapers {
  items: Paper[];
  page: number;
  size: number;
  total: number;
  pages: number;
}

export type ReadingStatus = "unread" | "reading" | "completed";

export interface ReadingProgress {
  reading_status: ReadingStatus;
  reading_progress_percent: number;
}

export interface LibraryDocument {
  id: number;
  user_paper_id: number;
  original_filename: string;
  size_bytes: number;
  page_count: number;
  status: DocumentProcessingStatus;
  version: number;
}

export type DocumentProcessingStatus =
  | "pending"
  | "processing"
  | "completed"
  | "failed";

export type ProcessingJobStatus =
  | "queued"
  | "running"
  | "completed"
  | "failed";

export interface DocumentMetadata {
  id: number;
  user_paper_id: number;
  page_count: number;
  status: DocumentProcessingStatus;
  version: number;
}

export interface DocumentProcessingJob {
  id: number;
  status: ProcessingJobStatus;
  attempts: number;
  last_error: string | null;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
  document_version: number;
}

export interface DocumentStatus {
  document_id: number;
  status: DocumentProcessingStatus;
  version: number;
  jobs: DocumentProcessingJob[];
}

export interface DocumentPage {
  page_number: number;
  raw_text: string;
  ocr_used: boolean;
  section_heading: string | null;
}

export interface DocumentPageResponse {
  items: DocumentPage[];
  page: number;
  size: number;
  total: number;
  pages: number;
}

export interface LibraryPaper extends ReadingProgress {
  id: number;
  legacy_paper_id: number;
  title: string;
  authors: string | null;
  abstract: string | null;
  source: string | null;
  url: string | null;
  saved_at: string;
  collection_ids: number[];
  tag_ids: number[];
  document: LibraryDocument | null;
}

export interface LibraryPage extends Omit<PaginatedPapers, "items"> {
  items: LibraryPaper[];
}

export interface LibraryCollectionInput {
  name: string;
  description: string | null;
}

export interface LibraryCollection extends LibraryCollectionInput {
  id: number;
  created_at: string;
  updated_at: string;
}

export interface LibraryTagInput {
  name: string;
  color: string | null;
}

export interface LibraryTag extends LibraryTagInput {
  id: number;
}

export interface LibraryAnnotationInput {
  type: "note" | "highlight";
  content: string;
  page_number: number | null;
  color: string | null;
}

export interface LibraryAnnotation extends LibraryAnnotationInput {
  id: number;
  created_at: string;
  updated_at: string;
}

export interface ExternalPaper {
  title: string;
  authors: string[];
  abstract: string;
  url: string;
  source: string;
}

export interface ResearchSearch {
  papers: ExternalPaper[];
  total: number;
}

export type DiscoverySource =
  | "arxiv"
  | "openalex"
  | "crossref"
  | "semantic_scholar"
  | "pubmed";
export type DiscoverySources = DiscoverySource[];
export type DiscoverySort = "relevance" | "date";
export type Sort = DiscoverySort;
export type PublicationType =
  | "article"
  | "review"
  | "preprint"
  | "book"
  | "book_chapter"
  | "conference"
  | "other";

export interface CitationLink {
  title: string;
  doi: string | null;
  url: string | null;
  source: DiscoverySource;
}

export interface DiscoveryPaper {
  title: string;
  authors: string[];
  abstract: string | null;
  doi: string | null;
  publication_date: string | null;
  url: string | null;
  source: DiscoverySource;
  sources: DiscoverySource[];
  external_id: string | null;
  paper_type: string | null;
  citation_count: number | null;
  citation_links: CitationLink[];
}

export interface DiscoverySearchRequest {
  q: string;
  sources: DiscoverySource[];
  year_from?: number;
  year_to?: number;
  publication_type?: PublicationType;
  sort: DiscoverySort;
  limit: number;
  offset: number;
}

export interface DiscoveryResponse {
  items: DiscoveryPaper[];
  total: number;
  offset: number;
  limit: number;
  sources: DiscoverySource[];
  warnings: string[];
}

export type DiscoveryPaperReference = Pick<DiscoveryPaper, "source" | "external_id" | "doi">;

export interface SaveToLibraryResult {
  paper_id: number;
  user_paper_id: number;
  saved: boolean;
  already_saved: boolean;
}

export interface Dashboard {
  user: User;
  profile: Profile;
  verification_status: boolean;
  language: Language;
  privacy_default: Privacy;
  allow_external_ai: boolean;
  saved_papers_count: number;
  recent_papers: SavedPaper[];
  active_sessions_count: number;
  recent_activity: AuditEvent[];
}

export interface ExportCollection {
  id: number;
  name: string;
  description: string | null;
  created_at: string;
}

export interface ExportTag {
  id: number;
  name: string;
  color: string | null;
}

export interface ExportAnnotation {
  id: number;
  user_paper_id: number;
  type: "note" | "highlight";
  content: string;
  page_number: number | null;
  color: string | null;
  created_at: string;
  updated_at: string;
}

export interface ExportDocument {
  id: number;
  user_paper_id: number;
  original_filename: string;
  size_bytes: number;
  page_count: number;
  created_at: string;
}

export interface ExportLibraryItem {
  user_paper_id: number;
  legacy_paper_id: number;
  reading_status: "unread" | "reading" | "completed";
  reading_progress_percent: number;
  collection_ids: number[];
  tag_ids: number[];
  annotations: ExportAnnotation[];
  document: ExportDocument | null;
}

export interface DataExport {
  account: User;
  profile: Profile;
  preferences: Preferences;
  papers: SavedPaper[];
  collections: ExportCollection[];
  tags: ExportTag[];
  library_items: ExportLibraryItem[];
  active_sessions: SessionInfo[];
  audit_logs: Array<AuditEvent & { user_id: number; ip_address: string | null }>;
}

export interface Token {
  access_token: string;
  token_type: string;
}

export interface StatusMessage {
  message: string;
}

export interface VerificationMessage extends StatusMessage {
  debug_token?: string;
}

export class ApiError extends Error {
  readonly status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

export const API_BASE_URL = (
  process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000/api/v1"
).replace(/\/+$/, "");

function validApiBase(): boolean {
  try {
    const url = new URL(API_BASE_URL);
    return (
      (url.protocol === "http:" || url.protocol === "https:") &&
      url.username === "" &&
      url.password === "" &&
      url.search === "" &&
      url.hash === ""
    );
  } catch {
    return false;
  }
}

// Access credentials live only in this browser tab's memory. Never persist them.
let accessToken: string | null = null;
const sessionListeners = new Set<() => void>();

function publishSession(): void {
  sessionListeners.forEach((listener) => listener());
}

export function setAccessToken(token: string): void {
  accessToken = token;
  publishSession();
}

export function clearAccessToken(): void {
  accessToken = null;
  publishSession();
}

export function getAccessToken(): string | null {
  return accessToken;
}

export function subscribeSession(listener: () => void): () => void {
  sessionListeners.add(listener);
  return () => {
    sessionListeners.delete(listener);
  };
}

export function getCurrentSessionId(): string | null {
  // This is a display identifier only. Authorization is always checked by FastAPI.
  if (!accessToken || typeof window === "undefined") return null;
  try {
    const payloadSegment = accessToken.split(".")[1];
    if (!payloadSegment) return null;
    const normalized = payloadSegment.replace(/-/g, "+").replace(/_/g, "/");
    const payload: unknown = JSON.parse(window.atob(normalized));
    if (
      payload !== null &&
      typeof payload === "object" &&
      "sid" in payload &&
      typeof payload.sid === "string"
    ) {
      return payload.sid;
    }
  } catch {
    return null;
  }
  return null;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === "object";
}

function errorMessage(payload: unknown, status: number): string {
  if (status === 401) return "Your session has ended. Please sign in again.";
  if (status === 403) return "You do not have permission to perform this action.";
  if (status === 429) return "Too many requests. Please wait and try again.";
  if (status >= 500) return "The service is unavailable right now. Please try again.";
  if (isRecord(payload)) {
    if (typeof payload.detail === "string" && payload.detail.length < 240) {
      return payload.detail;
    }
    if (Array.isArray(payload.detail)) {
      return "Please check the form fields and try again.";
    }
    if (isRecord(payload.error) && typeof payload.error.message === "string") {
      return payload.error.message.slice(0, 240);
    }
  }
  return "The request could not be completed. Please try again.";
}

type RequestOptions = {
  method?: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
  body?: unknown;
  authenticated?: boolean;
  responseType?: "pdf" | "download";
  expectedMime?: string;
  signal?: AbortSignal;
};

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  if (!validApiBase()) {
    throw new ApiError("The API address is not configured correctly.", 0);
  }
  const authenticated = options.authenticated ?? true;
  const requestToken = accessToken;
  if (authenticated && !requestToken) {
    throw new ApiError("Please sign in to continue.", 401);
  }
  const controller = new AbortController();
  const timeout = globalThis.setTimeout(() => controller.abort(), 25_000);
  const multipart = typeof FormData !== "undefined" && options.body instanceof FormData;
  const requestHeaders: Record<string, string> = {
    Accept: options.responseType === "pdf" ? "application/pdf" : options.expectedMime ?? "application/json",
  };
  if (options.body !== undefined && !multipart) requestHeaders["Content-Type"] = "application/json";
  if (authenticated && requestToken) {
    requestHeaders.Authorization = `Bearer ${requestToken}`;
  }

  try {
    const response = await fetch(`${API_BASE_URL}${path}`, {
      method: options.method ?? "GET",
      headers: requestHeaders,
      body: multipart ? (options.body as FormData) : JSON.stringify(options.body),
      cache: "no-store",
      credentials: "omit",
      signal: options.signal
        ? AbortSignal.any([controller.signal, options.signal])
        : controller.signal,
      referrerPolicy: "no-referrer",
      redirect: "error",
    });
    if (response.status === 204) return undefined as T;
    if (response.ok && options.responseType) {
      const expected = options.responseType === "pdf" ? "application/pdf" : options.expectedMime;
      if (!expected || response.headers.get("Content-Type")?.split(";")[0].trim().toLowerCase() !== expected) {
        throw new ApiError("The service returned an invalid file response.", 502);
      }
      return (await response.blob()) as T;
    }
    let payload: unknown = null;
    try {
      payload = await response.json();
    } catch {
      if (response.ok) throw new ApiError("The service returned an invalid response.", 502);
    }
    if (!response.ok) {
      // A late response from an older session must not sign out a new login.
      if (response.status === 401 && authenticated && accessToken === requestToken) {
        clearAccessToken();
      }
      if (response.status === 401 && !authenticated) {
        throw new ApiError("The email or password is incorrect.", response.status);
      }
      throw new ApiError(errorMessage(payload, response.status), response.status);
    }
    return payload as T;
  } catch (error: unknown) {
    if (error instanceof ApiError) throw error;
    if (controller.signal.aborted) {
      throw new ApiError("The request timed out. Please try again.", 0);
    }
    throw new ApiError("Unable to connect. Check your connection and the API server.", 0);
  } finally {
    globalThis.clearTimeout(timeout);
  }
}

function searchParams(values: Record<string, string | number | undefined>): string {
  const params = new URLSearchParams();
  Object.entries(values).forEach(([key, value]) => {
    if (value !== undefined) params.set(key, String(value));
  });
  return params.toString();
}

export const api = {
  getLearningGuides: (signal?: AbortSignal) => request<LearningGuide[]>("/education/guides", { signal }),
  getLearningGuide: (slug: string, signal?: AbortSignal) => request<LearningGuide>(`/education/guides/${encodeURIComponent(slug)}`, { signal }),
  updateLearningProgress: (slug: string, completed_step_ids: string[], signal?: AbortSignal) => request<LearningProgress>(`/education/guides/${encodeURIComponent(slug)}/progress`, { method: "POST", body: { completed_step_ids }, signal }),
  getGlossary: (q = "", category = "", signal?: AbortSignal) => request<GlossaryResult>(`/education/glossary?${searchParams({ q, category: category || undefined })}`, { signal }),
  explainPaperForBeginners: (paperId: number, body: EducationExplainOptions, signal?: AbortSignal) => request<BeginnerExplanation>(`/education/explain-paper/${paperId}`, { method: "POST", body, signal }),
  getTeams: (limit = 30, offset = 0, signal?: AbortSignal) => request<TeamWorkspace[]>(`/teams?${searchParams({ limit, offset })}`, { signal }),
  createTeam: (body: TeamWorkspaceInput, signal?: AbortSignal) => request<TeamDetail>("/teams", { method: "POST", body, signal }),
  getTeam: (id: number, signal?: AbortSignal) => request<TeamDetail>(`/teams/${id}`, { signal }),
  updateTeam: (id: number, body: Partial<TeamWorkspaceInput>, signal?: AbortSignal) => request<TeamDetail>(`/teams/${id}`, { method: "PUT", body, signal }),
  deleteTeam: (id: number, signal?: AbortSignal) => request<void>(`/teams/${id}`, { method: "DELETE", signal }),
  addTeamMember: (id: number, identifier: string, role: CollaboratorRole, signal?: AbortSignal) => request<TeamMember>(`/teams/${id}/members`, { method: "POST", body: { identifier, role }, signal }),
  updateTeamMember: (id: number, memberId: number, role: CollaboratorRole, signal?: AbortSignal) => request<TeamMember>(`/teams/${id}/members/${memberId}`, { method: "PUT", body: { role }, signal }),
  removeTeamMember: (id: number, memberId: number, signal?: AbortSignal) => request<void>(`/teams/${id}/members/${memberId}`, { method: "DELETE", signal }),
  shareTeamCollection: (id: number, collection_id: number, signal?: AbortSignal) => request<TeamCollection>(`/teams/${id}/collections`, { method: "POST", body: { collection_id }, signal }),
  unshareTeamCollection: (id: number, collectionId: number, signal?: AbortSignal) => request<void>(`/teams/${id}/collections/${collectionId}`, { method: "DELETE", signal }),
  getTeamNotes: (id: number, limit = 100, offset = 0, signal?: AbortSignal) => request<TeamNote[]>(`/teams/${id}/notes?${searchParams({ limit, offset })}`, { signal }),
  createTeamNote: (id: number, body: TeamNoteInput, signal?: AbortSignal) => request<TeamNote>(`/teams/${id}/notes`, { method: "POST", body, signal }),
  updateTeamNote: (id: number, noteId: number, body: Partial<TeamNoteInput>, signal?: AbortSignal) => request<TeamNote>(`/teams/${id}/notes/${noteId}`, { method: "PUT", body, signal }),
  deleteTeamNote: (id: number, noteId: number, signal?: AbortSignal) => request<void>(`/teams/${id}/notes/${noteId}`, { method: "DELETE", signal }),
  getProjects: (limit = 50, offset = 0, signal?: AbortSignal) => request<ResearchProject[]>(`/projects?${searchParams({ limit, offset })}`, { signal }),
  createProject: (body: ProjectInput) => request<ResearchProject>("/projects", { method: "POST", body }),
  getProject: (id: number, signal?: AbortSignal) => request<ProjectDetail>(`/projects/${id}`, { signal }),
  updateProject: (id: number, body: Partial<ProjectInput> & { expected_revision: number }) => request<ProjectDetail>(`/projects/${id}`, { method: "PUT", body }),
  deleteProject: (id: number) => request<void>(`/projects/${id}`, { method: "DELETE" }),
  addProjectPaper: (id: number, user_paper_id: number, role_in_project: string | null) => request<ProjectPaper>(`/projects/${id}/papers`, { method: "POST", body: { user_paper_id, role_in_project } }),
  removeProjectPaper: (id: number, paperId: number) => request<void>(`/projects/${id}/papers/${paperId}`, { method: "DELETE" }),
  getProjectNotes: (id: number) => request<ResearchNote[]>(`/projects/${id}/notes`),
  createProjectNote: (id: number, body: ProjectNoteInput) => request<ResearchNote>(`/projects/${id}/notes`, { method: "POST", body }),
  updateProjectNote: (id: number, noteId: number, body: Partial<ProjectNoteInput>) => request<ResearchNote>(`/projects/${id}/notes/${noteId}`, { method: "PUT", body }),
  deleteProjectNote: (id: number, noteId: number) => request<void>(`/projects/${id}/notes/${noteId}`, { method: "DELETE" }),
  getProjectTasks: (id: number) => request<ProjectTask[]>(`/projects/${id}/tasks`),
  createProjectTask: (id: number, body: ProjectTaskInput) => request<ProjectTask>(`/projects/${id}/tasks`, { method: "POST", body }),
  updateProjectTask: (id: number, taskId: number, body: Partial<ProjectTaskInput>) => request<ProjectTask>(`/projects/${id}/tasks/${taskId}`, { method: "PUT", body }),
  deleteProjectTask: (id: number, taskId: number) => request<void>(`/projects/${id}/tasks/${taskId}`, { method: "DELETE" }),
  linkProjectConversation: (id: number, conversationId: number) => request<Pick<Conversation, "id" | "title" | "language" | "created_at" | "updated_at">>(`/projects/${id}/conversations/${conversationId}`, { method: "POST" }),
  exportProject: (id: number, format: "json" | "markdown") => request<Blob>(`/projects/${id}/export?${searchParams({ format })}`, { responseType: "download", expectedMime: format === "json" ? "application/json" : "text/markdown" }),
  getAnalyticsOverview: (project_id?: number, signal?: AbortSignal) => request<AnalyticsOverview>(`/analytics/overview?${searchParams({ project_id })}`, { signal }),
  getAnalyticsTimeline: (project_id?: number, signal?: AbortSignal) => request<ResearchTimeline>(`/analytics/timeline?${searchParams({ project_id })}`, { signal }),
  getKnowledgeGraph: (project_id?: number, signal?: AbortSignal) => request<KnowledgeGraph>(`/analytics/knowledge-graph?${searchParams({ project_id })}`, { signal }),
  extractDocumentAssets: (documentId: number) => request<AssetExtraction>(`/multimodal/documents/${documentId}/extract`, { method: "POST" }),
  getDocumentAssets: (documentId: number, params: { asset_type?: DocumentAssetType; page_number?: number } = {}, signal?: AbortSignal) =>
    request<DocumentAssets>(`/multimodal/documents/${documentId}/assets?${searchParams(params)}`, { signal }),
  getDocumentAsset: (assetId: number, signal?: AbortSignal) => request<DocumentAssetDetail>(`/multimodal/assets/${assetId}`, { signal }),
  getDocumentAssetImage: (assetId: number, signal?: AbortSignal) => request<Blob>(`/multimodal/assets/${assetId}/image`, { responseType: "download", expectedMime: "image/png", signal }),
  explainDocumentAsset: (assetId: number, body: VisionOptions) => request<VisionAnswer>(`/multimodal/assets/${assetId}/explain`, { method: "POST", body }),
  questionDocumentAsset: (assetId: number, body: VisionOptions & { question: string }) => request<VisionAnswer>(`/multimodal/assets/${assetId}/vqa`, { method: "POST", body }),
  getCitations: (limit = 50, offset = 0, q?: string) => request<Citation[]>(`/citations?${searchParams({ limit, offset, q })}`),
  createCitation: (body: CitationInput) => request<Citation>("/citations", { method: "POST", body }),
  updateCitation: (id: number, body: CitationInput) => request<Citation>(`/citations/${id}`, { method: "PUT", body }),
  deleteCitation: (id: number) => request<void>(`/citations/${id}`, { method: "DELETE" }),
  importCitations: (format: ReferenceFormat, content: string) => request<CitationImportResult>("/citations/import", { method: "POST", body: { format, content } }),
  formatCitations: (citation_ids: number[], style: CitationStyle) => request<FormattedReferences>("/citations/format", { method: "POST", body: { citation_ids, style } }),
  exportCitations: (format: ReferenceFormat, ids: number[] = []) => {
    const params = new URLSearchParams({ format });
    ids.forEach((id) => params.append("citation_ids", String(id)));
    return request<Blob>(`/citations/export?${params}`, { responseType: "download", expectedMime: format === "bibtex" ? "application/x-bibtex" : "application/x-research-info-systems" });
  },
  getWritingDocuments: (limit = 30, offset = 0) => request<WritingDocument[]>(`/writing?${searchParams({ limit, offset })}`),
  createWritingDocument: (body: WritingCreate) => request<WritingDocument>("/writing", { method: "POST", body }),
  getWritingDocument: (id: number) => request<WritingDocument>(`/writing/${id}`),
  updateWritingDocument: (id: number, body: WritingUpdate) => request<WritingDocument>(`/writing/${id}`, { method: "PUT", body }),
  deleteWritingDocument: (id: number) => request<void>(`/writing/${id}`, { method: "DELETE" }),
  getWritingVersions: (id: number) => request<WritingVersion[]>(`/writing/${id}/versions`),
  restoreWritingVersion: (id: number, version: number, expected_revision: number) => request<WritingDocument>(`/writing/${id}/versions/${version}/restore`, { method: "POST", body: { expected_revision } }),
  assistWriting: (id: number, body: WritingAssistInput) => request<WritingSuggestion>(`/writing/${id}/assist`, { method: "POST", body }),
  exportWriting: (id: number, format: WritingExportFormat, style: CitationStyle) => request<Blob>(`/writing/${id}/export?${searchParams({ format, style })}`, { responseType: "download", expectedMime: writingMimeTypes[format] }),
  analyzePaper: (id: number, body: AnalysisOptions) => request<PaperAnalysis>(`/analysis/${id}`, { method: "POST", body }),
  getPaperAnalysis: (id: number, language: Language) => request<PaperAnalysis>(`/analysis/${id}?${searchParams({ language })}`),
  getPaperAnalyses: (limit = 30, offset = 0) => request<PaperAnalysis[]>(`/analysis?${searchParams({ limit, offset })}`),
  comparePapers: (body: PaperComparisonInput) => request<PaperComparison>("/analysis/compare", { method: "POST", body }),
  getPaperComparisons: (limit = 30, offset = 0) => request<PaperComparison[]>(`/analysis/comparisons?${searchParams({ limit, offset })}`),
  getPaperComparison: (id: number) => request<PaperComparison>(`/analysis/comparisons/${id}`),
  getConversations: (limit = 50, offset = 0) => request<Conversation[]>(`/conversations?${searchParams({ limit, offset })}`),
  createConversation: (body: ConversationInput) => request<Conversation>("/conversations", { method: "POST", body }),
  getConversation: (id: number) => request<ConversationHistory>(`/conversations/${id}`),
  deleteConversation: (id: number) => request<void>(`/conversations/${id}`, { method: "DELETE" }),
  sendAssistantMessage: (id: number, body: AssistantQuestion) => request<AssistantMessage>(`/conversations/${id}/messages`, { method: "POST", body }),
  getAIUsage: (signal?: AbortSignal) => request<AIUsageStats>("/ai/usage", { signal }),
  getMe: () => request<User>("/users/me"),
  login: (values: { email: string; password: string }) =>
    request<Token>("/auth/login", { method: "POST", body: values, authenticated: false }),
  register: (values: { username: string; email: string; password: string }) =>
    request<User>("/auth/register", { method: "POST", body: values, authenticated: false }),
  logout: () => request<void>("/auth/logout", { method: "POST" }),
  logoutAll: () => request<void>("/auth/logout-all", { method: "POST" }),
  requestEmailVerification: () =>
    request<VerificationMessage>("/auth/verify-email/request", { method: "POST" }),
  confirmEmailVerification: (token: string) =>
    request<StatusMessage>("/auth/verify-email/confirm", {
      method: "POST",
      body: { token },
      authenticated: false,
    }),
  requestPasswordReset: (email: string) =>
    request<StatusMessage>("/auth/password-reset/request", {
      method: "POST",
      body: { email },
      authenticated: false,
    }),
  confirmPasswordReset: (token: string, newPassword: string) =>
    request<StatusMessage>("/auth/password-reset/confirm", {
      method: "POST",
      body: { token, new_password: newPassword },
      authenticated: false,
    }),
  changePassword: (currentPassword: string, newPassword: string) =>
    request<StatusMessage>("/auth/password-change", {
      method: "POST",
      body: { current_password: currentPassword, new_password: newPassword },
    }),
  getProfile: () => request<Profile>("/users/me/profile"),
  updateProfile: (values: Partial<ProfileInput>) =>
    request<Profile>("/users/me/profile", { method: "PUT", body: values }),
  getPreferences: (signal?: AbortSignal) => request<Preferences>("/users/me/preferences", { signal }),
  updatePreferences: (values: Partial<PreferenceInput>) =>
    request<Preferences>("/users/me/preferences", { method: "PUT", body: values }),
  getSessions: () => request<SessionInfo[]>("/users/me/sessions"),
  revokeSession: (id: string) =>
    request<void>(`/users/me/sessions/${encodeURIComponent(id)}`, { method: "DELETE" }),
  getActivity: (limit = 50) => request<AuditEvent[]>(`/users/me/activity?${searchParams({ limit })}`),
  exportData: () => request<DataExport>("/users/me/export"),
  deleteAccount: () => request<void>("/users/me", { method: "DELETE" }),
  getDashboard: () => request<Dashboard>("/users/me/dashboard"),
  getPapers: (page = 1, size = 10) =>
    request<PaginatedPapers>(`/papers/?${searchParams({ page, size })}`),
  searchPapers: (query: string, page = 1, size = 10) =>
    request<PaginatedPapers>(`/papers/search?${searchParams({ q: query, page, size })}`),
  createPaper: (values: PaperInput) => request<Paper>("/papers/", { method: "POST", body: values }),
  updatePaper: (id: number, values: Partial<PaperInput>) =>
    request<Paper>(`/papers/${id}`, { method: "PUT", body: values }),
  deletePaper: (id: number) => request<StatusMessage>(`/papers/${id}`, { method: "DELETE" }),
  getLibrary: (params: { q?: string; collection_id?: number; tag_id?: number; page: number; size: number }, signal?: AbortSignal) =>
    request<LibraryPage>(`/library/papers?${searchParams(params)}`, { signal }),
  setReadingProgress: (paperId: number, body: ReadingProgress) =>
    request<ReadingProgress & { id: number }>(`/library/papers/${paperId}/progress`, { method: "PATCH", body }),
  getLibraryCollections: (signal?: AbortSignal) => request<LibraryCollection[]>("/library/collections", { signal }),
  getLibraryCollection: (id: number) => request<LibraryCollection>(`/library/collections/${id}`),
  createLibraryCollection: (body: LibraryCollectionInput) =>
    request<LibraryCollection>("/library/collections", { method: "POST", body }),
  updateLibraryCollection: (id: number, body: LibraryCollectionInput) =>
    request<LibraryCollection>(`/library/collections/${id}`, { method: "PATCH", body }),
  deleteLibraryCollection: (id: number) =>
    request<void>(`/library/collections/${id}`, { method: "DELETE" }),
  getLibraryTags: () => request<LibraryTag[]>("/library/tags"),
  getLibraryTag: (id: number) => request<LibraryTag>(`/library/tags/${id}`),
  createLibraryTag: (body: LibraryTagInput) =>
    request<LibraryTag>("/library/tags", { method: "POST", body }),
  updateLibraryTag: (id: number, body: LibraryTagInput) =>
    request<LibraryTag>(`/library/tags/${id}`, { method: "PATCH", body }),
  deleteLibraryTag: (id: number) =>
    request<void>(`/library/tags/${id}`, { method: "DELETE" }),
  setLibraryMembership: (group: "collections" | "tags", groupId: number, paperId: number, include: boolean) =>
    request<void>(`/library/${group}/${groupId}/papers/${paperId}`, { method: include ? "PUT" : "DELETE" }),
  getLibraryAnnotations: (paperId: number, signal?: AbortSignal) =>
    request<LibraryAnnotation[]>(`/library/papers/${paperId}/annotations`, { signal }),
  createLibraryAnnotation: (paperId: number, body: LibraryAnnotationInput) =>
    request<LibraryAnnotation>(`/library/papers/${paperId}/annotations`, { method: "POST", body }),
  updateLibraryAnnotation: (paperId: number, id: number, body: LibraryAnnotationInput) =>
    request<LibraryAnnotation>(`/library/papers/${paperId}/annotations/${id}`, { method: "PATCH", body }),
  deleteLibraryAnnotation: (paperId: number, id: number) =>
    request<void>(`/library/papers/${paperId}/annotations/${id}`, { method: "DELETE" }),
  uploadLibraryPDF: (file: File, title?: string, userPaperId?: number) => {
    const body = new FormData();
    body.set("file", file);
    if (title) body.set("title", title);
    if (userPaperId !== undefined) body.set("user_paper_id", String(userPaperId));
    return request<LibraryDocument & { user_paper_id: number }>("/library/upload", { method: "POST", body });
  },
  getLibraryPDF: (paperId: number, signal?: AbortSignal) =>
    request<Blob>(`/library/papers/${paperId}/pdf`, { responseType: "pdf", signal }),
  deleteLibraryPDF: (paperId: number) =>
    request<void>(`/library/papers/${paperId}/pdf`, { method: "DELETE" }),
  getDocument: (documentId: number, signal?: AbortSignal) =>
    request<DocumentMetadata>(`/documents/${documentId}`, { signal }),
  getDocumentStatus: (documentId: number, signal?: AbortSignal) =>
    request<DocumentStatus>(`/documents/${documentId}/status`, { signal }),
  getDocumentPages: (documentId: number, page = 1, size = 10, signal?: AbortSignal) =>
    request<DocumentPageResponse>(
      `/documents/${documentId}/pages?${searchParams({ page, size })}`,
      { signal },
    ),
  retryDocument: (documentId: number) =>
    request<DocumentStatus>(`/documents/${documentId}/retry`, { method: "POST" }),
  searchResearch: (query: string, limit = 10) =>
    request<ResearchSearch>(`/research/search?${searchParams({ q: query, limit })}`, {
      authenticated: false,
    }),
  searchDiscovery: (values: DiscoverySearchRequest) =>
    request<DiscoveryResponse>("/discovery/search", {
      method: "POST",
      body: values,
      authenticated: false,
    }),
  getDiscoveryDOI: (doi: string) =>
    request<DiscoveryPaper>(`/discovery/doi/${encodeURIComponent(doi.trim())}`, {
      authenticated: false,
    }),
  saveDiscoveryPaper: ({ source, external_id, doi }: DiscoveryPaperReference) =>
    request<SaveToLibraryResult>("/discovery/save-to-library", {
      method: "POST",
      body: { source, external_id, doi },
    }),
};

export type AIProvider = "auto" | "offline" | "local" | "cloud";
export interface ConversationInput {
  title: string; scope_type: "single_paper" | "selected_papers" | "collection";
  scope_paper_ids: number[]; scope_collection_id: number | null; language: Language; project_id?: number | null;
}
export interface Conversation extends ConversationInput { id: number; project_id: number | null; created_at: string; updated_at: string }
export interface SourceCitation {
  id: number; user_paper_id: number; document_id: number | null; chunk_id: number | null;
  paper_title: string; page_number: number; section_heading: string | null;
  quoted_snippet: string; relevance_score: number;
}
export interface AssistantMessage {
  id: number; role: "user" | "assistant"; content: string;
  evidence_status: "supported" | "partial_interpretation" | "insufficient_evidence";
  interpretation: string; missing_information: string; follow_up_questions: string[];
  citations: SourceCitation[]; model_used: string | null; provider_used: string | null; created_at: string;
}
export interface ConversationHistory extends Conversation { messages: AssistantMessage[] }
export interface AssistantQuestion { content: string; provider: AIProvider; request_id: string }
export interface AIQuotaWindow {
  requests: number; tokens: number; request_limit: number; token_limit: number;
  remaining_requests: number; remaining_tokens: number;
}
export interface AIUsageStats {
  hourly: AIQuotaWindow; daily: AIQuotaWindow; active_requests: number;
  max_concurrent_requests: number; window_type: "rolling";
}

export type DocumentAssetType = "figure" | "chart" | "diagram" | "table" | "equation";
export interface AssetExtraction {
  job_id: number; status: "queued" | "running" | "completed" | "failed";
  document_id: number; document_version: number; error_message?: string | null;
}
export interface DocumentAsset {
  id: number; document_id: number; document_version: number; asset_type: DocumentAssetType;
  asset_label: string | null; page_number: number; caption: string | null;
  extracted_text_or_latex: string | null;
  structured_data: { bbox?: number[]; headers?: unknown[]; rows?: unknown[][]; [key: string]: unknown } | null;
  linked_chunk_ids: number[]; ai_explanation: string | null; has_image: boolean;
  created_at: string; updated_at: string;
}
export interface DocumentAssetDetail extends DocumentAsset {
  linked_chunks: Array<{ id: number; page_number: number; section_heading: string | null; content: string }>;
}
export interface DocumentAssets {
  items: DocumentAsset[]; extraction: AssetExtraction | null; is_stale: boolean;
}
export interface VisionOptions { language: Language; provider: AIProvider; request_id: string }
export interface VisionAnswer {
  asset_id: number; language: Language;
  evidence_status: "supported" | "partial_interpretation" | "insufficient_evidence";
  extracted_facts: string[]; visual_interpretation: string; missing_information: string;
  provider_used: string; model_used: string;
  evidence: { page_number: number; asset_label: string | null; linked_chunk_ids: number[] };
}

export type AnalysisField = "abstract_summary" | "research_problem" | "research_objectives" | "methodology" | "datasets" | "models_and_algorithms" | "evaluation_metrics" | "key_results" | "contributions" | "limitations" | "future_work" | "strengths" | "weaknesses";
export type FieldStatus = "supported" | "partial_interpretation" | "not_specified";
export interface AnalysisEvidence {
  field: string; user_paper_id: number; chunk_id: number; document_id: number;
  document_version: number; paper_title: string; page_number: number;
  section_heading: string | null; quoted_snippet: string;
}
export interface ExtractionFields {
  abstract_summary: string; research_problem: string; research_objectives: string[];
  methodology: string; datasets: string[]; models_and_algorithms: string[];
  evaluation_metrics: string[]; key_results: string; contributions: string[];
  limitations: string[]; future_work: string[]; strengths: string[]; weaknesses: string[];
  field_statuses: Record<AnalysisField, FieldStatus>; evidence_links: AnalysisEvidence[];
}
export interface PaperAnalysis extends ExtractionFields {
  id: number; user_paper_id: number; document_id: number | null; document_version: number;
  language: Language; status: "completed" | "failed"; is_stale: boolean;
  error_message: string | null; provider_used: string; model_used: string;
  created_at: string; updated_at: string;
}
export interface ComparisonColumn extends ExtractionFields { user_paper_id: number; paper_title: string }
export interface ResearchGap {
  title: string; description: string; scope: "selected_papers_only";
  evidence_status: "partial_interpretation"; evidence_links: AnalysisEvidence[];
}
export interface PaperComparison {
  id: number; title: string; user_paper_ids: number[]; language: Language;
  comparison_matrix: ComparisonColumn[]; literature_synthesis: string; research_gaps: ResearchGap[];
  evidence_links: AnalysisEvidence[]; provider_used: string; model_used: string;
  created_at: string; is_stale: boolean;
}
export interface AnalysisOptions {
  language: Language; force_refresh: boolean; provider: AIProvider; request_id: string;
}
export interface PaperComparisonInput {
  user_paper_ids: number[]; title: string; language: Language; provider: AIProvider; request_id: string;
}

export type CitationStyle = "apa" | "ieee" | "mla" | "chicago" | "harvard";
export type ReferenceFormat = "bibtex" | "ris";
export type CitationEntryType = "article" | "inproceedings" | "book" | "misc" | "preprint";
export interface CitationInput {
  user_paper_id?: number | null; cite_key?: string; entry_type?: CitationEntryType;
  title?: string; authors?: string[]; year?: number | null; venue?: string | null;
  volume?: string | null; issue?: string | null; pages?: string | null;
  doi?: string | null; url?: string | null; publisher?: string | null;
}
export interface Citation {
  id: number; user_paper_id: number | null; cite_key: string; entry_type: CitationEntryType;
  title: string; authors: string[]; year: number | null; venue: string | null;
  volume: string | null; issue: string | null; pages: string | null; doi: string | null;
  url: string | null; publisher: string | null; is_verified: boolean;
  created_at: string; updated_at: string; warnings: string[];
}
export interface CitationImportResult { items: Citation[]; created: number; duplicates: number; warnings: string[] }
export interface FormattedReferences {
  style: CitationStyle; entries: Array<{ citation_id: number; cite_key: string; in_text: string; bibliography: string; is_verified: boolean }>;
  bibliography: string[]; warnings: string[];
}
export type WritingType = "research_paper" | "research_proposal" | "thesis" | "literature_review";
export interface WritingDraft {
  title: string; doc_type: WritingType; language: Language; outline: string[];
  content_markdown: string; cited_citation_ids: number[];
}
export type WritingCreate = Partial<WritingDraft> & Pick<WritingDraft, "title" | "doc_type" | "language">;
export type WritingUpdate = Partial<WritingDraft> & { expected_revision: number; create_version?: boolean; change_summary?: string };
export interface WritingDocument extends WritingDraft {
  id: number; revision: number; word_count: number; ai_suggestions_log: WritingSuggestion[];
  created_at: string; updated_at: string;
}
export interface WritingVersion {
  id: number; writing_document_id: number; version_number: number; title: string;
  content_markdown: string; change_summary: string | null; created_at: string;
}
export type WritingAction = "draft_section" | "tone" | "grammar" | "paraphrase";
export type WritingSection = "abstract" | "introduction" | "literature_review" | "methodology" | "results_discussion";
export interface WritingAssistInput {
  action: WritingAction; section: WritingSection; text?: string; user_paper_ids: number[];
  provider: AIProvider; request_id: string;
}
export interface WritingSuggestion {
  id: string; kind: "ai_generated_suggestion"; action: WritingAction; section: WritingSection;
  content_markdown: string; evidence_links: AnalysisEvidence[]; provider_used: string;
  model_used: string; created_at: string;
  citation_ids: number[];
}
export type WritingExportFormat = "md" | "tex" | "docx" | "pdf";
const writingMimeTypes: Record<WritingExportFormat, string> = {
  md: "text/markdown", tex: "application/x-tex",
  docx: "application/vnd.openxmlformats-officedocument.wordprocessingml.document", pdf: "application/pdf",
};
