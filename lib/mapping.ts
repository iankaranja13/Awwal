/**
 * Contract layer between the UI shapes (lib/types.ts) and the backend API.
 * Pure functions only: no fetch, no React, so the mapping is testable with
 * plain Node (see tests/integration/test_frontend_contract.py).
 *
 * Answer mapping notes (all approximations are documented, never silent):
 * - Combined screening questions (torsion/injury, erections/desire) pin the
 *   first backend field on "yes" and leave the rest unanswered; "no" clears
 *   every field. The backend snippets are group-worded, so the narrative
 *   stays accurate.
 * - "Not currently trying" derives months_trying = 0 so the
 *   time-to-conceive flag can resolve instead of hanging on an unasked field.
 * - Duration bands map to representative months (3 / 9 / 18) that preserve
 *   the 12-month threshold on both sides.
 */
import type {
  AssessResponse,
  AuditEntryOut,
  BackendAnswers,
  BackendStatus,
  ProviderOut,
  ReferralOut,
  ShareOut,
  TraceResponse,
  TraceStepOut,
} from "./api";
import { questionById } from "./intake";
import type {
  AnswerStatus,
  Answers,
  Assessment,
  AuditEntry,
  Bi,
  BookingType,
  FlagResult,
  Provider,
  Referral,
  ReferralStatus,
  Route,
  Share,
  TraceStep,
} from "./types";

/* ---------- Answers: UI -> backend ---------- */

type AnswerMap =
  | { kind: "bool"; to: [string, ...string[]] }
  | { kind: "choice"; to: string; values: Record<string, string | number | boolean> }
  | { kind: "number"; to: string };

/** Frontend question id -> backend item id(s) plus value coercion. */
export const ANSWER_MAP: Record<string, AnswerMap> = {
  age_band: {
    kind: "choice",
    to: "age_band",
    values: {
      "18_24": "18_24",
      "25_29": "25_29",
      "30_34": "30_34",
      "35_39": "35_39",
      "40_44": "40_44",
      "45_plus": "45_plus",
    },
  },
  ttc: { kind: "choice", to: "trying_to_conceive", values: { trying: "yes", planning: "no", not_now: "no" } },
  ttc_months: { kind: "choice", to: "months_trying", values: { under_6: 3, "6_12": 9, over_12: 18 } },
  rf_pain: { kind: "bool", to: ["testicular_pain_sudden_severe"] },
  rf_lump: { kind: "bool", to: ["testicular_lump"] },
  rf_swelling: { kind: "bool", to: ["testicular_swelling"] },
  rf_fever: { kind: "bool", to: ["fever_with_testicular_pain"] },
  rf_blood: { kind: "bool", to: ["blood_in_semen"] },
  undescended: { kind: "bool", to: ["undescended_testis"] },
  torsion_injury: { kind: "bool", to: ["testicular_torsion", "testicular_injury_or_surgery"] },
  hernia_surgery: { kind: "bool", to: ["hernia_or_genital_surgery"] },
  varicocele: { kind: "bool", to: ["known_varicocele"] },
  genital_infection: { kind: "bool", to: ["genital_infection_or_inflammation"] },
  sti: { kind: "bool", to: ["sti_history"] },
  mumps: { kind: "bool", to: ["mumps_testicular_inflammation"] },
  height_cm: { kind: "number", to: "height_cm" },
  weight_kg: { kind: "number", to: "weight_kg" },
  diabetes: { kind: "bool", to: ["diabetes"] },
  blood_pressure: { kind: "bool", to: ["high_blood_pressure"] },
  cholesterol: { kind: "bool", to: ["high_cholesterol"] },
  tobacco: { kind: "choice", to: "tobacco_vaping_shisha", values: { yes: "current", no: "never" } },
  alcohol: { kind: "choice", to: "alcohol_use", values: { yes: "regular", no: "never" } },
  steroids: {
    kind: "choice",
    to: "anabolic_steroids_or_testosterone",
    values: { yes: "current", no: "never" },
  },
  substances: { kind: "choice", to: "other_substances", values: { yes: "current", no: "never" } },
  heat: { kind: "bool", to: ["occupational_heat_or_chemicals"] },
  cancer_treatment: { kind: "bool", to: ["chemotherapy_or_radiation"] },
  chronic: { kind: "bool", to: ["chronic_conditions"] },
  sexual_changes: {
    kind: "bool",
    to: ["low_desire_or_sexual_function_change", "erectile_or_ejaculation_difficulty"],
  },
  semen_analysis: {
    kind: "choice",
    to: "prior_semen_analysis_result",
    values: { never: "not_done", normal: "normal", abnormal: "abnormal" },
  },
};

const STATUS_MAP: Record<AnswerStatus, BackendStatus> = {
  answered: "answered",
  skipped: "skipped",
  unsure: "unsure",
  prefer_not: "prefer_not_to_say",
};

/** Convert UI answers to the backend intake payload. Unknown ids are dropped. */
export function toBackendAnswers(answers: Answers): BackendAnswers {
  const out: BackendAnswers = {};
  for (const [id, ans] of Object.entries(answers)) {
    const spec = ANSWER_MAP[id];
    if (!spec) continue;
    const targets = spec.kind === "bool" ? spec.to : [spec.to];
    if (ans.status !== "answered") {
      for (const t of targets) out[t] = { value: null, status: STATUS_MAP[ans.status] };
      continue;
    }
    if (spec.kind === "bool") {
      if (ans.value !== "yes" && ans.value !== "no") {
        for (const t of targets) out[t] = { value: null, status: "skipped" };
        continue;
      }
      const yes = ans.value === "yes";
      out[targets[0]] = { value: yes, status: "answered" };
      for (const t of targets.slice(1)) {
        out[t] = yes ? { value: null, status: "skipped" } : { value: false, status: "answered" };
      }
      continue;
    }
    if (spec.kind === "number") {
      out[spec.to] =
        typeof ans.value === "number"
          ? { value: ans.value, status: "answered" }
          : { value: null, status: "skipped" };
      continue;
    }
    const mapped = typeof ans.value === "string" ? spec.values[ans.value] : undefined;
    out[spec.to] =
      mapped === undefined ? { value: null, status: "skipped" } : { value: mapped, status: "answered" };
  }
  const ttc = answers.ttc;
  if (
    ttc?.status === "answered" &&
    (ttc.value === "planning" || ttc.value === "not_now") &&
    out.months_trying === undefined
  ) {
    out.months_trying = { value: 0, status: "answered" };
  }
  return out;
}

/** Backend item id -> frontend question id (for the missing list). */
export const REVERSE_MAP: Record<string, string> = {
  age_band: "age_band",
  trying_to_conceive: "ttc",
  months_trying: "ttc_months",
  testicular_pain_sudden_severe: "rf_pain",
  testicular_lump: "rf_lump",
  testicular_swelling: "rf_swelling",
  fever_with_testicular_pain: "rf_fever",
  blood_in_semen: "rf_blood",
  undescended_testis: "undescended",
  testicular_torsion: "torsion_injury",
  testicular_injury_or_surgery: "torsion_injury",
  hernia_or_genital_surgery: "hernia_surgery",
  known_varicocele: "varicocele",
  genital_infection_or_inflammation: "genital_infection",
  sti_history: "sti",
  mumps_testicular_inflammation: "mumps",
  height_cm: "height_cm",
  weight_kg: "weight_kg",
  diabetes: "diabetes",
  high_blood_pressure: "blood_pressure",
  high_cholesterol: "cholesterol",
  tobacco_vaping_shisha: "tobacco",
  alcohol_use: "alcohol",
  anabolic_steroids_or_testosterone: "steroids",
  other_substances: "substances",
  occupational_heat_or_chemicals: "heat",
  chemotherapy_or_radiation: "cancer_treatment",
  chronic_conditions: "chronic",
  low_desire_or_sexual_function_change: "sexual_changes",
  erectile_or_ejaculation_difficulty: "sexual_changes",
  prior_semen_analysis_result: "semen_analysis",
};

/** Backend red-flag id -> frontend question id (urgent route has no flag rows). */
export const RED_FLAG_QUESTIONS: Record<string, string> = {
  RF_SUDDEN_SEVERE_TESTICULAR_PAIN: "rf_pain",
  RF_TESTICULAR_LUMP: "rf_lump",
  RF_RAPID_SWELLING: "rf_swelling",
  RF_FEVER_WITH_PAIN: "rf_fever",
  RF_BLOOD_IN_SEMEN: "rf_blood",
};

/** Any red-flag question left open escalates the safety warning. */
export function redFlagsOpen(answers: Answers): boolean {
  return Object.values(RED_FLAG_QUESTIONS).some((q) => answers[q]?.status !== "answered");
}

/* ---------- Assessment: backend -> UI ---------- */

const STEP_LABELS: Record<string, Bi> = {
  consent_check: { en: "Permission checked", ar: "فحص الإذن" },
  load_intake: { en: "Answers loaded", ar: "تحميل الإجابات" },
  red_flag_evaluation: { en: "Urgent signs", ar: "العلامات العاجلة" },
  flag_evaluation: { en: "Signals", ar: "الإشارات" },
  triage: { en: "Route", ar: "المسار" },
  explanation: { en: "Explanation", ar: "الشرح" },
  persist: { en: "Saved", ar: "الحفظ" },
};

const num = (v: unknown): number => (typeof v === "number" ? v : 0);
const str = (v: unknown): string => (typeof v === "string" ? v : "");

function describeStep(step: TraceStepOut): Bi {
  switch (step.name) {
    case "consent_check":
      return { en: "Intake permission confirmed", ar: "تم تأكيد إذن الإجابات" };
    case "load_intake": {
      const n = num(step.detail.answered_count);
      return { en: `${n} answers loaded`, ar: `تم تحميل ${n} من الإجابات` };
    }
    case "red_flag_evaluation": {
      const found = Array.isArray(step.detail.present) ? step.detail.present.length : 0;
      return found
        ? {
            en: `${found} found. Stopped here.`,
            ar: `وُجدت ${found}. توقف التقييم هنا.`,
          }
        : { en: "None reported", ar: "لا شيء" };
    }
    case "flag_evaluation": {
      if (step.status === "skipped") {
        return { en: "Skipped: urgent sign found", ar: "تُخطّي: وُجدت علامة عاجلة" };
      }
      const p = num(step.detail.present);
      const na = num(step.detail.not_assessable);
      return {
        en: `${p} present, ${na} can't be assessed`,
        ar: `${p} موجودة، ${na} يتعذر تقييمها`,
      };
    }
    case "triage": {
      const route = str(step.detail.route).replaceAll("_", " ");
      return { en: `Route: ${route}`, ar: `المسار: ${route}` };
    }
    case "explanation": {
      const source = str(step.detail.source);
      return source === "llm"
        ? { en: "Explained by the assistant", ar: "شرحه المساعد" }
        : source === "static"
          ? { en: "Static safety text (no AI used)", ar: "نص سلامة ثابت (دون ذكاء اصطناعي)" }
          : { en: "Template text (no AI used)", ar: "نص جاهز (دون ذكاء اصطناعي)" };
    }
    case "persist":
      return { en: "Signals saved", ar: "حُفظت الإشارات" };
    default:
      return { en: step.status, ar: step.status };
  }
}

function toTraceStep(step: TraceStepOut): TraceStep {
  return {
    step: step.name,
    label: STEP_LABELS[step.name] ?? { en: step.name, ar: step.name },
    detail: describeStep(step),
    ms: Math.max(1, Math.round(step.duration_ms)),
  };
}

function driverReason(ids: string[], flags: FlagResult[]): Bi {
  if (!ids.length) {
    return { en: "No signals from your answers", ar: "لا إشارات من إجاباتك" };
  }
  const labels = ids.map((id) => {
    const fromFlags = flags.find((f) => f.id === id)?.label;
    if (fromFlags) return fromFlags;
    const q = RED_FLAG_QUESTIONS[id];
    return q ? (questionById(q)?.label ?? { en: id, ar: id }) : { en: id, ar: id };
  });
  return {
    en: labels.map((l) => l.en).join(", "),
    ar: labels.map((l) => l.ar).join("، "),
  };
}

/**
 * Merge the English and Arabic assessment responses into one bilingual
 * Assessment. Both responses describe the same stored answers, so route and
 * states always come from the English copy.
 */
export function mergeAssessment(
  en: AssessResponse,
  ar: AssessResponse,
  trace: TraceResponse,
  redOpen: boolean
): Assessment {
  const byId = new Map(ar.flags.map((f) => [f.id, f]));
  const flags: FlagResult[] = en.flags.map((f) => {
    const other = byId.get(f.id);
    return {
      id: f.id,
      label: { en: f.label, ar: other?.label ?? f.label },
      state: f.state,
      redFlag: f.id.startsWith("RF_"),
      modifiable: f.modifiable,
      why: { en: f.explanation, ar: other?.explanation ?? f.explanation },
      unknown: { en: f.why_we_ask ?? "", ar: other?.why_we_ask ?? "" },
      source: f.source,
      missing: f.missing_fields.map((m) => REVERSE_MAP[m] ?? m),
    };
  });
  const safety =
    en.static_safety_message && ar.static_safety_message
      ? {
          title: { en: en.static_safety_message.title, ar: ar.static_safety_message.title },
          body: { en: en.static_safety_message.body, ar: ar.static_safety_message.body },
        }
      : null;
  return {
    id: en.assessment_id,
    rulesVersion: en.rules_version,
    createdAt: new Date().toISOString(),
    flags,
    route: en.route as Route,
    routeReason: driverReason(en.route_reason, flags),
    missing: en.missing_items.map((m) => {
      const qid = REVERSE_MAP[m.item_id] ?? m.item_id;
      return { id: qid, label: questionById(qid)?.label ?? { en: m.item_id, ar: m.item_id } };
    }),
    redFlagsUnanswered: redOpen,
    explanationSource: en.explanation_source,
    safety,
    trace: trace.steps.map(toTraceStep),
  };
}

/* ---------- Providers, referrals, shares, audit ---------- */

const KNOWN_TYPES: BookingType[] = ["teleconsult", "blood_test", "sample_collection", "in_person"];

export function mapProvider(p: ProviderOut): Provider {
  return {
    id: p.id,
    name: { en: p.name, ar: p.name },
    area: { en: p.notes, ar: p.notes },
    // Fail closed: an unknown service type matches no filter.
    types: (KNOWN_TYPES as string[]).includes(p.type) ? [p.type as BookingType] : [],
    languages: p.languages.filter((l): l is "ar" | "en" => l === "ar" || l === "en"),
    clinicianGender: p.clinician_gender === "female" ? "female" : "male",
    homeSampling: p.home_sampling,
  };
}

const STAGE_ORDER: ReferralStatus[] = [
  "proposed",
  "clinician_review",
  "confirmed",
  "booked",
  "attended",
  "result_explained",
  "closed",
];

/** Simulated client-side reminders derived from the current stage. */
export function deriveReminders(status: ReferralStatus): Referral["reminders"] {
  const idx = STAGE_ORDER.indexOf(status);
  const out: Referral["reminders"] = [];
  if (idx >= STAGE_ORDER.indexOf("booked")) {
    out.push(
      { at: new Date().toISOString(), text: { en: "Your appointment is set.", ar: "تم تحديد موعدك." } },
      { at: new Date().toISOString(), text: { en: "Reminder: appointment tomorrow.", ar: "تذكير: موعدك غدًا." } }
    );
  }
  if (idx >= STAGE_ORDER.indexOf("attended")) {
    out.push({
      at: new Date().toISOString(),
      text: { en: "Follow-up check created.", ar: "أُنشئت متابعة." },
    });
  }
  return out;
}

export type ActorIds = { userId: string; clinicianId: string; navigatorId: string };

export function mapReferral(out: ReferralOut, actors: ActorIds): Referral {
  const by = (actorId: string | null): Referral["events"][number]["by"] => {
    if (actorId === null) return "system";
    if (actorId === actors.userId) return "you";
    if (actorId === actors.clinicianId) return "clinician";
    if (actorId === actors.navigatorId) return "navigator";
    return "system";
  };
  const status = out.status as ReferralStatus;
  return {
    id: out.id,
    assessmentId: out.assessment_id,
    route: out.assessment_route as Route,
    type: (KNOWN_TYPES as string[]).includes(out.type) ? (out.type as BookingType) : "teleconsult",
    providerId: out.provider_id ?? "",
    slot: "",
    appointmentAt: out.appointment_time ?? out.preferred_time ?? undefined,
    status,
    events: out.events.map((e) => ({ to: e.to_status as ReferralStatus, at: e.at, by: by(e.actor_id) })),
    reminders: deriveReminders(status),
    outcomeNote: out.outcome_note ? { en: out.outcome_note, ar: out.outcome_note } : undefined,
  };
}

export function mapShare(s: ShareOut): Share {
  return {
    id: s.id,
    recipient: { en: "Reviewing clinician", ar: "الطبيب المراجع" },
    createdAt: s.created_at,
    expiresAt: s.expires_at,
    revokedAt: s.revoked_at ?? undefined,
  };
}

const AUDIT_LABELS: Record<string, Bi> = {
  "consent.updated": { en: "Permissions changed", ar: "تغيير الأذونات" },
  "intake.updated": { en: "Answers saved", ar: "حُفظت الإجابات" },
  "intake.read": { en: "Answers viewed", ar: "عُرضت الإجابات" },
  "referral.created": { en: "Booking requested", ar: "طلب حجز" },
  "referral.transition": { en: "Referral updated", ar: "حُدّثت الإحالة" },
  "share.created": { en: "Shared with clinician", ar: "مشاركة مع الطبيب" },
  "share.revoked": { en: "Share revoked", ar: "أُلغيت المشاركة" },
  "brief.generated": { en: "Clinician brief written", ar: "كُتب ملخص الطبيب" },
  "explanation.generated": { en: "Signals explained", ar: "شُرحت الإشارات" },
};

export function mapAuditEntry(e: AuditEntryOut): AuditEntry {
  return {
    id: e.id,
    at: e.at,
    action: AUDIT_LABELS[e.action] ?? { en: e.action, ar: e.action },
    actor:
      e.actor_role === "user"
        ? "you"
        : e.actor_role === "clinician"
          ? "clinician"
          : e.actor_role === "navigator"
            ? "navigator"
            : "system",
  };
}

/* ---------- Slots ---------- */

/**
 * Turn a slot label ("Tomorrow, 9:30" or "Sat, 11:00") into a future ISO
 * datetime for preferred/appointment time. Anything unparseable or stale
 * falls back to 24 hours from now so the backend "must be future" rule
 * always holds.
 */
export function slotToDate(slotEn: string, now: Date): string {
  const m = slotEn.match(/^(Tomorrow|Sat),\s*(\d{1,2}):(\d{2})$/);
  if (m) {
    const at = new Date(now);
    at.setHours(Number(m[2]), Number(m[3]), 0, 0);
    if (m[1] === "Tomorrow") {
      at.setDate(at.getDate() + 1);
    } else {
      const delta = (6 - at.getDay() + 7) % 7 || 7;
      at.setDate(at.getDate() + delta);
    }
    if (at.getTime() > now.getTime() + 3600_000) return at.toISOString();
  }
  return new Date(now.getTime() + 24 * 3600_000).toISOString();
}

/**
 * Routes the backend accepts for referral creation. Mirror of
 * BOOKABLE_ROUTES in app/services/referral.py; the server still enforces it.
 */
export const BOOKABLE_ROUTES: Route[] = ["ANDROLOGY_UROLOGY", "FERTILITY_SERVICES", "PRIMARY_CARE"];
