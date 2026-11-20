/**
 * Live backend client for the Awwal FastAPI API (base path /api/v1).
 * Thin fetch wrapper plus session handling; response mapping lives in
 * lib/mapping.ts so it stays testable without a browser.
 */
import type { ConsentScope, Lang } from "./types";

export const API_BASE = (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1").replace(
  /\/+$/,
  ""
);

/** Backend error envelope: { error: { code, message } }. */
export class ApiError extends Error {
  status: number;
  code: string;

  constructor(status: number, code: string, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
  }
}

type Query = Record<string, string | number | boolean | undefined>;

async function request<T>(
  path: string,
  opts: { method?: string; token?: string; query?: Query; body?: unknown; lang?: Lang } = {}
): Promise<T> {
  const url = new URL(API_BASE + path);
  for (const [k, v] of Object.entries(opts.query ?? {})) {
    if (v !== undefined) url.searchParams.set(k, String(v));
  }
  const headers: Record<string, string> = { Accept: "application/json" };
  if (opts.lang) headers["Accept-Language"] = opts.lang;
  if (opts.token) headers["Authorization"] = `Bearer ${opts.token}`;
  const init: RequestInit = { method: opts.method ?? "GET", headers };
  if (opts.body !== undefined) {
    headers["Content-Type"] = "application/json";
    init.body = JSON.stringify(opts.body);
  }
  let res: Response;
  try {
    res = await fetch(url, init);
  } catch {
    throw new ApiError(0, "CONNECTION_FAILED", `Could not reach the API at ${API_BASE}.`);
  }
  if (res.status === 204) return undefined as T;
  const data: unknown = await res.json().catch(() => null);
  if (!res.ok) {
    const err = (data as { error?: { code?: string; message?: string } } | null)?.error;
    throw new ApiError(res.status, err?.code ?? "REQUEST_FAILED", err?.message ?? res.statusText);
  }
  return data as T;
}

/* ---------- Backend shapes (mirror docs/openapi.json) ---------- */

export type BackendStatus = "answered" | "skipped" | "unsure" | "prefer_not_to_say";
export type BackendAnswer = { value: string | number | boolean | null; status: BackendStatus };
export type BackendAnswers = Record<string, BackendAnswer>;

export type SessionResponse = { user_id: string; handle: string; role: string; token: string };
export type ConsentStateResponse = { state: Record<ConsentScope, boolean>; policy_version: string };

export type AssessFlag = {
  id: string;
  state: "PRESENT" | "NOT_PRESENT_FROM_PROVIDED_DATA" | "NOT_ASSESSABLE";
  domain: string;
  label: string;
  reason_fields: string[];
  missing_fields: string[];
  modifiable: boolean;
  source: string;
  requires_clinical_validation: boolean;
  explanation: string;
  why_we_ask: string | null;
};

export type AssessResponse = {
  assessment_id: string;
  rules_version: string;
  language: Lang;
  urgent: boolean;
  route: string;
  route_reason: string[];
  flags: AssessFlag[];
  missing_items: { item_id: string; why_we_ask: string }[];
  next_step: { text: string; requires_clinician_review: boolean; actions: string[] };
  static_safety_message: { id: string; title: string; body: string } | null;
  disclaimer: string;
  explanation_source: "llm" | "template" | "static";
  trace_id: string;
};

export type TraceStepOut = {
  name: string;
  status: string;
  started_at: string;
  duration_ms: number;
  rules_version: string;
  detail: Record<string, unknown>;
};

export type TraceResponse = {
  trace_id: string;
  assessment_id: string;
  steps: TraceStepOut[];
  duration_ms: number;
};

export type ProviderOut = {
  id: string;
  name: string;
  type: string;
  languages: string[];
  clinician_gender: string;
  tele: boolean;
  home_sampling: boolean;
  notes: string;
  mock: boolean;
};

export type ReferralEventOut = {
  id: string;
  from_status: string | null;
  to_status: string;
  actor_id: string | null;
  at: string;
};

export type ReferralOut = {
  id: string;
  assessment_id: string;
  assessment_route: string;
  user_id: string;
  type: string;
  provider_id: string | null;
  status: string;
  preferred_time: string | null;
  appointment_time: string | null;
  outcome_note: string | null;
  created_at: string;
  updated_at: string;
  events: ReferralEventOut[];
};

export type ReviewResponse = {
  id: string;
  assessment_id: string;
  reviewer_id: string;
  decision: string;
  signed_off_at: string | null;
  referral_id: string;
  referral_status: string;
};

export type ShareOut = {
  id: string;
  recipient_id: string;
  scope: { all: boolean; assessment_ids: string[] };
  expires_at: string;
  revoked_at: string | null;
  created_at: string;
};

export type AuditEntryOut = {
  id: string;
  actor_role: string;
  action: string;
  object_type: string;
  object_id: string | null;
  at: string;
  detail: Record<string, unknown>;
};

/* ---------- Session handling (in-memory only) ---------- */

export type Session = { token: string; userId: string; handle: string; role: string };

let sessionPromise: Promise<Session> | null = null;

/** Create the anonymous session once per page load; retries after failure. */
export function ensureSession(lang: Lang): Promise<Session> {
  sessionPromise ??= request<SessionResponse>("/sessions", {
    method: "POST",
    body: { language: lang },
    lang,
  })
    .then((r) => ({ token: r.token, userId: r.user_id, handle: r.handle, role: r.role }))
    .catch((e: unknown) => {
      sessionPromise = null;
      throw e;
    });
  return sessionPromise;
}

/** Drop the session so the next call starts fresh (used after delete). */
export function resetSession(): void {
  sessionPromise = null;
}

export type DemoRole = "navigator" | "clinician";

const DEMO_CREDS: Record<DemoRole, { handle: string; password: string }> = {
  navigator: {
    handle: process.env.NEXT_PUBLIC_DEMO_NAVIGATOR_HANDLE ?? "navigator-demo",
    password: process.env.NEXT_PUBLIC_DEMO_NAVIGATOR_PASSWORD ?? "navigator-demo",
  },
  clinician: {
    handle: process.env.NEXT_PUBLIC_DEMO_CLINICIAN_HANDLE ?? "clinician-demo",
    password: process.env.NEXT_PUBLIC_DEMO_CLINICIAN_PASSWORD ?? "clinician-demo",
  },
};

const demoPromises: Partial<Record<DemoRole, Promise<Session>>> = {};

/**
 * Log in a seeded demo role. Defaults match the documented seed values in
 * .env.example, so this only works against a seeded dev/demo API.
 */
export function ensureDemoLogin(role: DemoRole): Promise<Session> {
  demoPromises[role] ??= request<SessionResponse>("/auth/login", {
    method: "POST",
    body: DEMO_CREDS[role],
  })
    .then((r) => ({ token: r.token, userId: r.user_id, handle: r.handle, role: r.role }))
    .catch((e: unknown) => {
      delete demoPromises[role];
      throw e;
    });
  return demoPromises[role] as Promise<Session>;
}

/* ---------- Endpoints ---------- */

export const postConsent = (token: string, scope: ConsentScope, granted: boolean) =>
  request<ConsentStateResponse>("/consent", { method: "POST", token, body: { scope, granted } });

export const putIntake = (token: string, answers: BackendAnswers) =>
  request<{ schema_version: string; saved_item_ids: string[]; updated_at: string }>("/intake", {
    method: "PUT",
    token,
    body: { answers },
  });

export const postAssess = (token: string, lang: Lang) =>
  request<AssessResponse>("/assess", { method: "POST", token, query: { lang }, lang });

export const getTrace = (token: string, assessmentId: string) =>
  request<TraceResponse>(`/trace/${assessmentId}`, { token });

export const getProviders = (
  token: string,
  filters: { type?: string; language?: string; clinician_gender?: string } = {}
) => request<ProviderOut[]>("/providers", { token, query: filters });

export const postReferral = (
  token: string,
  body: {
    assessment_id: string;
    type: string;
    provider_id: string;
    preferred_time?: string;
    contact?: { phone?: string };
  }
) => request<ReferralOut>("/referrals", { method: "POST", token, body });

export const getReferral = (token: string, id: string) =>
  request<ReferralOut>(`/referrals/${id}`, { token });

export const patchReferralStatus = (
  token: string,
  id: string,
  body: { to_status: string; appointment_time?: string; outcome_note?: string }
) => request<ReferralOut>(`/referrals/${id}/status`, { method: "PATCH", token, body });

export const postReview = (
  clinicianToken: string,
  body: { assessment_id: string; decision: "approved" | "rejected"; edits?: Record<string, string>; notes?: string }
) => request<ReviewResponse>("/clinician/review", { method: "POST", token: clinicianToken, body });

export const postShare = (
  token: string,
  body: { recipient_id: string; scope: { all: boolean }; expires_in_hours: number }
) => request<ShareOut>("/shares", { method: "POST", token, body });

export const listShares = (token: string) => request<ShareOut[]>("/shares", { token });

export const deleteShare = (token: string, id: string) =>
  request<ShareOut>(`/shares/${id}`, { method: "DELETE", token });

export const getAudit = (token: string) => request<AuditEntryOut[]>("/privacy/audit", { token });

export const getExport = (token: string) => request<unknown>("/export", { token });

export const deleteMe = (token: string) =>
  request<{ removed: Record<string, number>; anonymized_audit_entries: number; consents_kept: number }>(
    "/me",
    { method: "DELETE", token }
  );
