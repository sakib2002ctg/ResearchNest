"use client";

export type Language = "en" | "bn";
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
  responseType?: "pdf";
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
    Accept: options.responseType === "pdf" ? "application/pdf" : "application/json",
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
    if (response.ok && options.responseType === "pdf") {
      if (response.headers.get("Content-Type")?.split(";")[0].trim().toLowerCase() !== "application/pdf") {
        throw new ApiError("The service returned an invalid PDF response.", 502);
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
  getConversations: (limit = 50, offset = 0) => request<Conversation[]>(`/conversations?${searchParams({ limit, offset })}`),
  createConversation: (body: ConversationInput) => request<Conversation>("/conversations", { method: "POST", body }),
  getConversation: (id: number) => request<ConversationHistory>(`/conversations/${id}`),
  deleteConversation: (id: number) => request<void>(`/conversations/${id}`, { method: "DELETE" }),
  sendAssistantMessage: (id: number, body: AssistantQuestion) => request<AssistantMessage>(`/conversations/${id}/messages`, { method: "POST", body }),
  getAIUsage: () => request<AIUsageStats>("/ai/usage"),
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
  getPreferences: () => request<Preferences>("/users/me/preferences"),
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
  getLibrary: (params: { q?: string; collection_id?: number; tag_id?: number; page: number; size: number }) =>
    request<LibraryPage>(`/library/papers?${searchParams(params)}`),
  setReadingProgress: (paperId: number, body: ReadingProgress) =>
    request<ReadingProgress & { id: number }>(`/library/papers/${paperId}/progress`, { method: "PATCH", body }),
  getLibraryCollections: () => request<LibraryCollection[]>("/library/collections"),
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
  scope_paper_ids: number[]; scope_collection_id: number | null; language: Language;
}
export interface Conversation extends ConversationInput { id: number; created_at: string; updated_at: string }
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
