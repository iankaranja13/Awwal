"use client";

/**
 * In-memory journey store. Nothing sensitive is persisted in the browser;
 * only the language choice goes to localStorage (per the build plan).
 * Swap the mock calls for lib/api.ts once Person A's endpoints are live.
 */
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { assess } from "./engine";
import { STRINGS, type StringKey } from "./strings";
import type {
  Answer, Answers, Assessment, AuditEntry, Bi, BookingType, Consent, ConsentScope, Lang, Referral, ReferralStatus, Route, Share,
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
  setConsent: (s: ConsentScope, v: boolean) => void;
  answers: Answers;
  setAnswer: (id: string, a: Answer | undefined) => void;
  topicIndex: number;
  setTopicIndex: (i: number) => void;
  assessment: Assessment | null;
  runAssessment: (override?: Answers) => Assessment;
  referral: Referral | null;
  createReferral: (type: BookingType, providerId: string, slot: string) => void;
  advanceReferral: (by: Referral["events"][number]["by"]) => void;
  cancelReferral: () => void;
  shares: Share[];
  createShare: () => void;
  revokeShare: (id: string) => void;
  audit: AuditEntry[];
  reviews: Record<string, Review>;
  signOff: (caseId: string, route: Route, note: string) => void;
  hidden: boolean;
  setHidden: (h: boolean) => void;
  deleteAll: () => void;
  exportData: () => string;
};

const Ctx = createContext<Store | null>(null);

const NO_CONSENT: Consent = { intake: false, share_with_clinician: false, reminders: false, aggregate_analytics: false };

const A = {
  consent: (s: ConsentScope, v: boolean): Bi => ({
    en: `${v ? "Granted" : "Revoked"}: ${STRINGS[({ intake: "c_intake", share_with_clinician: "c_share", reminders: "c_reminders", aggregate_analytics: "c_analytics" } as const)[s]].en}`,
    ar: `${v ? "منح" : "إلغاء"}: ${STRINGS[({ intake: "c_intake", share_with_clinician: "c_share", reminders: "c_reminders", aggregate_analytics: "c_analytics" } as const)[s]].ar}`,
  }),
};

function pushStatus(r: Referral, to: ReferralStatus, by: Referral["events"][number]["by"]): Referral {
  const next: Referral = { ...r, status: to, events: [...r.events, { to, at: now(), by }] };
  if (to === "booked") {
    next.reminders = [
      { at: now(), text: { en: "Your appointment is set.", ar: "تم تحديد موعدك." } },
      { at: now(), text: { en: "Reminder: appointment tomorrow.", ar: "تذكير: موعدك غدًا." } },
    ];
  }
  if (to === "attended") {
    next.reminders = [...next.reminders, { at: now(), text: { en: "Follow-up check created.", ar: "أُنشئت متابعة." } }];
  }
  if (to === "result_explained") {
    next.outcomeNote = {
      en: "Results discussed. Repeat semen test in 3 months.",
      ar: "نوقشت النتائج. إعادة تحليل السائل المنوي بعد ٣ أشهر.",
    };
  }
  return next;
}

export function StoreProvider({ children }: { children: ReactNode }) {
  // English-only for now. Arabic copy is kept in the data files so it can be re-enabled.
  const [lang, setLangState] = useState<Lang>("en");
  const [consent, setConsentState] = useState<Consent>(NO_CONSENT);
  const [answers, setAnswers] = useState<Answers>({});
  const [topicIndex, setTopicIndex] = useState(0);
  const [assessment, setAssessment] = useState<Assessment | null>(null);
  const [referral, setReferral] = useState<Referral | null>(null);
  const [shares, setShares] = useState<Share[]>([]);
  const [audit, setAudit] = useState<AuditEntry[]>([]);
  const [reviews, setReviews] = useState<Record<string, Review>>({});
  const [hidden, setHidden] = useState(false);

  useEffect(() => {
    document.documentElement.lang = lang;
    document.documentElement.dir = lang === "ar" ? "rtl" : "ltr";
  }, [lang]);

  const log = useCallback((action: Bi, actor: AuditEntry["actor"] = "you") => {
    setAudit((a) => [{ id: uid("au"), at: now(), action, actor }, ...a]);
  }, []);

  const setLang = useCallback((l: Lang) => setLangState(l), []);

  const setConsent = useCallback(
    (s: ConsentScope, v: boolean) => {
      setConsentState((c) => ({ ...c, [s]: v }));
      log(A.consent(s, v));
      if (s === "share_with_clinician" && !v) {
        setShares((sh) => sh.map((x) => (x.revokedAt ? x : { ...x, revokedAt: now() })));
      }
    },
    [log]
  );

  const setAnswer = useCallback((id: string, a: Answer | undefined) => {
    setAnswers((prev) => {
      const next = { ...prev };
      if (a) next[id] = a;
      else delete next[id];
      return next;
    });
  }, []);

  const runAssessment = useCallback((override?: Answers) => {
    const r = assess(override ?? answers);
    setAssessment(r);
    log({ en: `Signals checked (rules ${r.rulesVersion})`, ar: `فحص الإشارات (القواعد ${r.rulesVersion})` }, "system");
    return r;
  }, [answers, log]);

  const createReferral = useCallback(
    (type: BookingType, providerId: string, slot: string) => {
      if (!assessment) return;
      const selfCare = assessment.route === "SELF_CARE" || assessment.route === "SELF_CARE_PROVISIONAL";
      let r: Referral = {
        id: uid("ref"),
        assessmentId: assessment.id,
        route: assessment.route,
        type,
        providerId,
        slot,
        status: "proposed",
        events: [{ to: "proposed", at: now(), by: "you" }],
        reminders: [],
      };
      // Self-care needs no sign-off; everything else waits for a clinician.
      r = selfCare ? pushStatus(pushStatus(r, "confirmed", "system"), "booked", "system") : pushStatus(r, "clinician_review", "system");
      setReferral(r);
      log({ en: "Booking requested", ar: "طلب حجز" });
    },
    [assessment, log]
  );

  const advanceReferral = useCallback(
    (by: Referral["events"][number]["by"]) => {
      setReferral((r) => {
        if (!r) return r;
        const to = NEXT_STATUS[r.status];
        if (!to) return r;
        // Rule 7: no confirmation without clinician sign-off unless self-care
        if (r.status === "clinician_review" && by !== "clinician") return r;
        return pushStatus(r, to, by);
      });
    },
    []
  );

  const cancelReferral = useCallback(() => {
    setReferral((r) => (r ? pushStatus(r, "cancelled", "you") : r));
    log({ en: "Referral cancelled", ar: "أُلغيت الإحالة" });
  }, [log]);

  const createShare = useCallback(() => {
    const exp = new Date(Date.now() + 7 * 864e5).toISOString();
    setShares((s) => [{ id: uid("sh"), recipient: { en: "Reviewing clinician", ar: "الطبيب المراجع" }, createdAt: now(), expiresAt: exp }, ...s]);
    log({ en: "Shared with clinician for 7 days", ar: "مشاركة مع الطبيب لمدة ٧ أيام" });
  }, [log]);

  const revokeShare = useCallback(
    (id: string) => {
      setShares((s) => s.map((x) => (x.id === id ? { ...x, revokedAt: now() } : x)));
      log({ en: "Share revoked", ar: "أُلغيت المشاركة" });
    },
    [log]
  );

  const signOff = useCallback(
    (caseId: string, route: Route, note: string) => {
      setReviews((r) => ({ ...r, [caseId]: { route, note, signedAt: now() } }));
      if (caseId === "me") {
        setReferral((r) => {
          if (!r || r.status !== "clinician_review") return r;
          const confirmed = pushStatus({ ...r, route, clinicianNote: note || undefined }, "confirmed", "clinician");
          return pushStatus(confirmed, "booked", "system");
        });
        log({ en: "Clinician signed off your referral", ar: "اعتمد الطبيب إحالتك" }, "clinician");
      }
    },
    [log]
  );

  const exportData = useCallback(
    () => JSON.stringify({ exportedAt: now(), consent, answers, assessment, referral, shares, audit }, null, 2),
    [consent, answers, assessment, referral, shares, audit]
  );

  const deleteAll = useCallback(() => {
    setAnswers({});
    setAssessment(null);
    setReferral(null);
    setShares([]);
    setTopicIndex(0);
    setConsentState(NO_CONSENT);
    // audit keeps entries, identity removed (prototype has no identity to remove)
    setAudit((a) => [{ id: uid("au"), at: now(), action: { en: "Personal data deleted", ar: "حُذفت البيانات الشخصية" }, actor: "you" }, ...a]);
  }, []);

  const value = useMemo<Store>(
    () => ({
      lang, setLang, consent, setConsent, answers, setAnswer, topicIndex, setTopicIndex, assessment, runAssessment,
      referral, createReferral, advanceReferral, cancelReferral, shares, createShare, revokeShare, audit, reviews, signOff,
      hidden, setHidden, deleteAll, exportData,
    }),
    [lang, setLang, consent, setConsent, answers, setAnswer, topicIndex, assessment, runAssessment, referral, createReferral,
      advanceReferral, cancelReferral, shares, createShare, revokeShare, audit, reviews, signOff, hidden, deleteAll, exportData]
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
