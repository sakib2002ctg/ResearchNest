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

export interface DataExport {
  account: User;
  profile: Profile;
  preferences: Preferences;
  papers: SavedPaper[];
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
  method?: "GET" | "POST" | "PUT" | "DELETE";
  body?: unknown;
  authenticated?: boolean;
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
  const requestHeaders: Record<string, string> = { Accept: "application/json" };
  if (options.body !== undefined) requestHeaders["Content-Type"] = "application/json";
  if (authenticated && requestToken) {
    requestHeaders.Authorization = `Bearer ${requestToken}`;
  }

  try {
    const response = await fetch(`${API_BASE_URL}${path}`, {
      method: options.method ?? "GET",
      headers: requestHeaders,
      body: options.body === undefined ? undefined : JSON.stringify(options.body),
      cache: "no-store",
      credentials: "omit",
      signal: controller.signal,
      referrerPolicy: "no-referrer",
      redirect: "error",
    });
    if (response.status === 204) return undefined as T;
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

function searchParams(values: Record<string, string | number>): string {
  const params = new URLSearchParams();
  Object.entries(values).forEach(([key, value]) => params.set(key, String(value)));
  return params.toString();
}

export const api = {
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
