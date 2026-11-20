"use client";

/**
 * Journey store, backed by the live Awwal API. Session, answers and journey
 * state live in memory only; nothing sensitive is persisted in the browser.
 */
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import {
  ApiError,
  deleteMe,
  deleteShare,
  ensureDemoLogin,
  ensureSession,
  getAudit,
  getExport,
  getProviders,
  getReferral,
  getTrace,
  listShares,
  patchReferralStatus,
  postAssess,
  postConsent,
  postReferral,
  postReview,
  postShare,
  putIntake,
  resetSession,
} from "./api";
import {
  BOOKABLE_ROUTES,
  mapAuditEntry,
  mapProvider,
  mapReferral,
  mapShare,
  mergeAssessment,
  redFlagsOpen,
  slotToDate,
  toBackendAnswers,
  type ActorIds,
} from "./mapping";
import { STRINGS, type StringKey } from "./strings";
import type {
  Answer, Answers, Assessment, AuditEntry, Bi, BookingType, Consent, ConsentScope, Lang, Provider,
  Referral, ReferralStatus, Route, Share,
} from "./types";

const uid = (p: string) => `${p}_${Math.random().toString(36).slice(2, 9)}`;
const now = () => new Date().toISOString();

export const NEXT_STATUS: Partial<Record<ReferralStatus, ReferralStatus>> = {
  proposed: "clinician_review",
  clinician_review: "confirmed",
  confirmed: "booked",
  booked: "attended",
  attended: "result_explained",
  result_explained: "closed",
};

export type Review = { route: Route; note: string; signedAt: string };

type Store = {
  lang: Lang;
  setLang: (l: Lang) => void;
  consent: Consent;
  setConsent: (s: ConsentScope, v: boolean) => Promise<void>;
  answers: Answers;
  setAnswer: (id: string, a: Answer | undefined) => void;
  topicIndex: number;
  setTopicIndex: (i: number) => void;
  assessment: Assessment | null;
  runAssessment: (override?: Answers) => Promise<Assessment | null>;
  providers: Provider[];
  providersLoading: boolean;
  loadProviders: (filters: { type: BookingType; language: Lang | "any"; gender: "any" | "male" | "female" }) => Promise<void>;
  referral: Referral | null;
  createReferral: (type: BookingType, providerId: string, slotEn: string, phone: string) => Promise<boolean>;
  advanceReferral: (by: Referral["events"][number]["by"]) => Promise<boolean>;
  closeReferral: (outcomeNote: string) => Promise<boolean>;
  cancelReferral: () => Promise<boolean>;
  shares: Share[];
  createShare: () => Promise<void>;
  revokeShare: (id: string) => Promise<void>;
  refreshShares: () => Promise<void>;
  audit: AuditEntry[];
  refreshAudit: () => Promise<void>;
  reviews: Record<string, Review>;
  signOff: (caseId: string, route: Route, note: string) => Promise<boolean>;
  hidden: boolean;
  setHidden: (h: boolean) => void;
  deleteAll: () => Promise<boolean>;
  exportData: () => Promise<string | null>;
  busy: boolean;
  error: string | null;
  clearError: () => void;
};

const Ctx = createContext<Store | null>(null);

const NO_CONSENT: Consent = { intake: false, share_with_clinician: false, reminders: false, aggregate_analytics: false };

export function StoreProvider({ children }: { children: ReactNode }) {
  // English-only for now. Arabic copy is kept in the data files so it can be re-enabled.
  const [lang, setLangState] = useState<Lang>("en");
  const [consent, setConsentState] = useState<Consent>(NO_CONSENT);
  const [answers, setAnswers] = useState<Answers>({});
  const [topicIndex, setTopicIndex] = useState(0);
  const [assessment, setAssessment] = useState<Assessment | null>(null);
  const [providers, setProviders] = useState<Provider[]>([]);
  const [providersLoading, setProvidersLoading] = useState(false);
  const [referral, setReferral] = useState<Referral | null>(null);
  const [shares, setShares] = useState<Share[]>([]);
  const [audit, setAudit] = useState<AuditEntry[]>([]);
  const [reviews, setReviews] = useState<Record<string, Review>>({});
  const [hidden, setHidden] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    document.documentElement.lang = lang;
    document.documentElement.dir = lang === "ar" ? "rtl" : "ltr";
  }, [lang]);

  const clearError = useCallback(() => setError(null), []);

  const wrap = useCallback(async <T,>(fn: () => Promise<T>): Promise<T | null> => {
    setBusy(true);
    setError(null);
    try {
      return await fn();
    } catch (e) {
      setError(e instanceof ApiError ? `${e.code}: ${e.message}` : "Unexpected error.");
      return null;
    } finally {
      setBusy(false);
    }
  }, []);

  const log = useCallback((action: Bi, actor: AuditEntry["actor"] = "you") => {
    setAudit((a) => [{ id: uid("au"), at: now(), action, actor }, ...a]);
  }, []);

  /** Actor ids used to render referral event authors ("you", "clinician"...). */
  const actorIds = useCallback(async (): Promise<ActorIds> => {
    const [s, c, n] = await Promise.all([
      ensureSession(lang),
      ensureDemoLogin("clinician"),
      ensureDemoLogin("navigator"),
    ]);
    return { userId: s.userId, clinicianId: c.userId, navigatorId: n.userId };
  }, [lang]);

  const setLang = useCallback((l: Lang) => setLangState(l), []);

  const setConsent = useCallback(
    (s: ConsentScope, v: boolean) =>
      wrap(async () => {
        const session = await ensureSession(lang);
        const res = await postConsent(session.token, s, v);
        setConsentState((c) => ({ ...c, ...res.state }));
        if (s === "share_with_clinician" && !v) {
          const rows = await listShares(session.token);
          await Promise.all(rows.filter((r) => !r.revoked_at).map((r) => deleteShare(session.token, r.id)));
          setShares((sh) => sh.map((x) => (x.revokedAt ? x : { ...x, revokedAt: now() })));
        }
      }).then(() => undefined),
    [wrap, lang]
  );

  const setAnswer = useCallback((id: string, a: Answer | undefined) => {
    setAnswers((prev) => {
      const next = { ...prev };
      if (a) next[id] = a;
      else delete next[id];
      return next;
    });
  }, []);

  const runAssessment = useCallback(
    (override?: Answers) =>
      wrap(async () => {
        const session = await ensureSession(lang);
        const final = override ?? answers;
        await putIntake(session.token, toBackendAnswers(final));
        // Assessed twice so results read instantly in both languages.
        const [enRes, arRes] = await Promise.all([
          postAssess(session.token, "en"),
          postAssess(session.token, "ar"),
        ]);
        const trace = await getTrace(session.token, enRes.assessment_id);
        const merged = mergeAssessment(enRes, arRes, trace, redFlagsOpen(final));
        setAssessment(merged);
        log(
          {
            en: `Signals checked (rules ${merged.rulesVersion})`,
            ar: `فحص الإشارات (القواعد ${merged.rulesVersion})`,
          },
          "system"
        );
        return merged;
      }),
    [wrap, lang, answers, log]
  );

  const loadProviders: Store["loadProviders"] = useCallback(
    (filters) =>
      wrap(async () => {
        setProvidersLoading(true);
        try {
          const session = await ensureSession(lang);
          const rows = await getProviders(session.token, {
            type: filters.type,
            language: filters.language === "any" ? undefined : filters.language,
            clinician_gender: filters.gender === "any" ? undefined : filters.gender,
          });
          setProviders(rows.map(mapProvider));
        } finally {
          setProvidersLoading(false);
        }
      }).then(() => undefined),
    [wrap, lang]
  );

  const refreshShares = useCallback(
    () =>
      wrap(async () => {
        const session = await ensureSession(lang);
        const rows = await listShares(session.token);
        setShares(rows.map(mapShare));
      }).then(() => undefined),
    [wrap, lang]
  );

  const createShare = useCallback(
    () =>
      wrap(async () => {
        const session = await ensureSession(lang);
        const clinician = await ensureDemoLogin("clinician");
        const created = await postShare(session.token, {
          recipient_id: clinician.userId,
          scope: { all: true },
          expires_in_hours: 7 * 24,
        });
        setShares((s) => [mapShare(created), ...s]);
      }).then(() => undefined),
    [wrap, lang]
  );

  const revokeShare = useCallback(
    (id: string) =>
      wrap(async () => {
        const session = await ensureSession(lang);
        const revoked = await deleteShare(session.token, id);
        setShares((s) => s.map((x) => (x.id === id ? mapShare(revoked) : x)));
      }).then(() => undefined),
    [wrap, lang]
  );

  const createReferral = useCallback(
    (type: BookingType, providerId: string, slotEn: string, phone: string) =>
      wrap(async () => {
        if (!assessment) return;
        const session = await ensureSession(lang);
        if (!BOOKABLE_ROUTES.includes(assessment.route)) return;
        const rows = await listShares(session.token);
        if (!rows.some((r) => !r.revoked_at)) {
          const clinician = await ensureDemoLogin("clinician");
          const created = await postShare(session.token, {
            recipient_id: clinician.userId,
            scope: { all: true },
            expires_in_hours: 7 * 24,
          });
          setShares((s) => [mapShare(created), ...s]);
        } else {
          setShares(rows.map(mapShare));
        }
        const created = await postReferral(session.token, {
          assessment_id: assessment.id,
          type,
          provider_id: providerId,
          preferred_time: slotToDate(slotEn, new Date()),
          contact: { phone },
        });
        const mapped = mapReferral(created, await actorIds());
        setReferral({ ...mapped, slot: slotEn });
        return true;
      }).then((v) => v !== null),
    [wrap, lang, assessment, actorIds]
  );

  const advanceReferral = useCallback(
    (by: Referral["events"][number]["by"]) =>
      wrap(async () => {
        if (!referral) return;
        const to = NEXT_STATUS[referral.status];
        // Rule 7: only a clinician sign-off leaves review, via the review endpoint.
        if (!to || to === "closed" || referral.status === "clinician_review") return;
        const session = await ensureSession(lang);
        const token =
          by === "clinician"
            ? (await ensureDemoLogin("clinician")).token
            : by === "navigator"
              ? (await ensureDemoLogin("navigator")).token
              : session.token;
        const updated = await patchReferralStatus(token, referral.id, {
          to_status: to,
          appointment_time:
            to === "booked" ? (referral.appointmentAt ?? slotToDate("", new Date())) : undefined,
        });
        const mapped = mapReferral(updated, await actorIds());
        setReferral((r) => (r ? { ...mapped, slot: r.slot, clinicianNote: r.clinicianNote } : mapped));
        return true;
      }).then((v) => v !== null),
    [wrap, lang, referral, actorIds]
  );

  const closeReferral = useCallback(
    (outcomeNote: string) =>
      wrap(async () => {
        if (!referral || referral.status !== "result_explained" || !outcomeNote.trim()) return;
        const clinician = await ensureDemoLogin("clinician");
        const updated = await patchReferralStatus(clinician.token, referral.id, {
          to_status: "closed",
          outcome_note: outcomeNote.trim(),
        });
        const mapped = mapReferral(updated, await actorIds());
        setReferral((r) => (r ? { ...mapped, slot: r.slot, clinicianNote: r.clinicianNote } : mapped));
        return true;
      }).then((v) => v !== null),
    [wrap, referral, actorIds]
  );

  const cancelReferral = useCallback(
    () =>
      wrap(async () => {
        if (!referral || !["clinician_review", "booked"].includes(referral.status)) return;
        const session = await ensureSession(lang);
        const updated = await patchReferralStatus(session.token, referral.id, { to_status: "cancelled" });
        const mapped = mapReferral(updated, await actorIds());
        setReferral((r) => (r ? { ...mapped, slot: r.slot, clinicianNote: r.clinicianNote } : mapped));
        return true;
      }).then((v) => v !== null),
    [wrap, lang, referral, actorIds]
  );

  const refreshAudit = useCallback(
    () =>
      wrap(async () => {
        const session = await ensureSession(lang);
        const rows = await getAudit(session.token);
        const server = rows.map(mapAuditEntry);
        setAudit((prev) => {
          const local = prev.filter((e) => e.id.startsWith("au_"));
          return [...local, ...server].sort((a, b) => (a.at < b.at ? 1 : -1));
        });
      }).then(() => undefined),
    [wrap, lang]
  );

  const signOff = useCallback(
    async (caseId: string, route: Route, note: string): Promise<boolean> => {
      if (caseId !== "me") {
        setReviews((r) => ({ ...r, [caseId]: { route, note, signedAt: now() } }));
        return true;
      }
      const done = await wrap(async () => {
        if (!assessment || !referral || referral.status !== "clinician_review") {
          throw new ApiError(0, "NOTHING_TO_REVIEW", "No referral is waiting for review.");
        }
        const session = await ensureSession(lang);
        const clinician = await ensureDemoLogin("clinician");
        await postReview(clinician.token, {
          assessment_id: assessment.id,
          decision: "approved",
          edits: route !== referral.route ? { route } : undefined,
          notes: note.trim() || undefined,
        });
        setReviews((r) => ({ ...r, [caseId]: { route, note, signedAt: now() } }));
        const updated = await getReferral(session.token, referral.id);
        const mapped = mapReferral(updated, await actorIds());
        setReferral((r) =>
          r ? { ...mapped, slot: r.slot, clinicianNote: note.trim() || r.clinicianNote } : mapped
        );
        log({ en: "Clinician signed off your referral", ar: "اعتمد الطبيب إحالتك" }, "clinician");
        return true;
      });
      return done ?? false;
    },
    [wrap, lang, assessment, referral, actorIds, log]
  );

  const exportData = useCallback(async (): Promise<string | null> => {
    const data = await wrap(async () => {
      const session = await ensureSession(lang);
      return getExport(session.token);
    });
    return data === null ? null : JSON.stringify(data, null, 2);
  }, [wrap, lang]);

  const deleteAll = useCallback(
    () =>
      wrap(async () => {
        const session = await ensureSession(lang);
        await deleteMe(session.token);
        resetSession();
        setAnswers({});
        setAssessment(null);
        setReferral(null);
        setShares([]);
        setProviders([]);
        setTopicIndex(0);
        setConsentState(NO_CONSENT);
        setAudit([
          {
            id: uid("au"),
            at: now(),
            action: { en: "Personal data deleted", ar: "حُذفت البيانات الشخصية" },
            actor: "you",
          },
        ]);
        return true;
      }).then((v) => v !== null),
    [wrap, lang]
  );

  const value = useMemo<Store>(
    () => ({
      lang, setLang, consent, setConsent, answers, setAnswer, topicIndex, setTopicIndex, assessment,
      runAssessment, providers, providersLoading, loadProviders, referral, createReferral,
      advanceReferral, closeReferral, cancelReferral, shares, createShare, revokeShare, refreshShares,
      audit, refreshAudit, reviews, signOff, hidden, setHidden, deleteAll, exportData,
      busy, error, clearError,
    }),
    [lang, setLang, consent, setConsent, answers, setAnswer, topicIndex, setTopicIndex, assessment, runAssessment,
      providers, providersLoading, loadProviders, referral, createReferral, advanceReferral,
      closeReferral, cancelReferral, shares, createShare, revokeShare, refreshShares, audit,
      refreshAudit, reviews, signOff, hidden, deleteAll, exportData, busy, error, clearError]
  );

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useStore() {
  const s = useContext(Ctx);
  if (!s) throw new Error("useStore must be used inside StoreProvider");
  return s;
}

/** Translation helpers bound to the current language. */
export function useT() {
  const { lang } = useStore();
  return useMemo(
    () => ({
      lang,
      t: (k: StringKey) => STRINGS[k][lang],
      L: (b: Bi) => b[lang],
      num: (n: number) => new Intl.NumberFormat(lang === "ar" ? "ar-AE" : "en-GB").format(n),
      date: (iso: string) =>
        new Intl.DateTimeFormat(lang === "ar" ? "ar-AE" : "en-GB", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" }).format(new Date(iso)),
    }),
    [lang]
  );
}
