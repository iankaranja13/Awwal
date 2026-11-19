/**
 * Shared contract between the UI and the rules engine.
 * Person A's real engine must return these shapes; the UI only reads them.
 */

export type Lang = "en" | "ar";
export type Bi = { en: string; ar: string };

/* ---------- Consent ---------- */
export type ConsentScope = "intake" | "share_with_clinician" | "reminders" | "aggregate_analytics";
export type Consent = Record<ConsentScope, boolean>;

/* ---------- Intake ---------- */
export type AnswerStatus = "answered" | "unsure" | "prefer_not" | "skipped";
export type Answer = { status: AnswerStatus; value?: string | number };
export type Answers = Record<string, Answer>;

export type Option = { value: string; label: Bi };

export type Question =
  | { id: string; kind: "choice"; label: Bi; options: Option[]; showIf?: { id: string; equals: string } }
  | { id: string; kind: "number"; label: Bi; unit: Bi; min: number; max: number };

export type Topic = {
  id: string;
  title: Bi;
  why: Bi;
  questions: Question[];
};

/* ---------- Assessment ---------- */
export type FlagState = "PRESENT" | "NOT_PRESENT_FROM_PROVIDED_DATA" | "NOT_ASSESSABLE";

export type Route =
  | "URGENT"
  | "ANDROLOGY_UROLOGY"
  | "FERTILITY_SERVICES"
  | "PRIMARY_CARE"
  | "SELF_CARE"
  | "SELF_CARE_PROVISIONAL";

export type FlagResult = {
  id: string;
  label: Bi;
  state: FlagState;
  redFlag: boolean;
  modifiable: boolean;
  why: Bi; // plain-language reason (template text, not generated)
  unknown: Bi; // what is still not known
  source: string; // guideline reference
  missing: string[]; // question ids that blocked assessment
};

export type TraceStep = {
  step: string;
  label: Bi;
  detail: Bi;
  ms: number;
};

export type Assessment = {
  id: string;
  rulesVersion: string;
  createdAt: string;
  flags: FlagResult[];
  route: Route;
  routeReason: Bi;
  missing: { id: string; label: Bi }[];
  redFlagsUnanswered: boolean;
  explanationSource: "template" | "llm";
  trace: TraceStep[];
};

/* ---------- Booking & referral ---------- */
export type BookingType = "teleconsult" | "blood_test" | "sample_collection";

export type Provider = {
  id: string;
  name: Bi;
  area: Bi;
  types: BookingType[];
  languages: Lang[];
  clinicianGender: "male" | "female";
  homeSampling: boolean;
};

export type ReferralStatus =
  | "proposed"
  | "clinician_review"
  | "confirmed"
  | "booked"
  | "attended"
  | "result_explained"
  | "closed"
  | "cancelled"
  | "no_show";

export type Referral = {
  id: string;
  assessmentId: string;
  route: Route;
  type: BookingType;
  providerId: string;
  slot: string;
  status: ReferralStatus;
  events: { to: ReferralStatus; at: string; by: "you" | "clinician" | "navigator" | "system" }[];
  reminders: { at: string; text: Bi }[];
  outcomeNote?: Bi;
  clinicianNote?: string;
};

/* ---------- Privacy ---------- */
export type Share = { id: string; recipient: Bi; createdAt: string; expiresAt: string; revokedAt?: string };
export type AuditEntry = { id: string; at: string; action: Bi; actor: "you" | "clinician" | "system" };
