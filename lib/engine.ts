/**
 * MOCK rules engine for the UI prototype.
 * Mirrors the contract in types.ts so screens can be built before Person A's
 * engine lands. Draft clinical content: requires clinician validation.
 *
 * Three-valued (Kleene) logic: every condition is true, false or null (unknown).
 *   any(true, null) = true     all(false, null) = false     otherwise null
 * null maps to NOT_ASSESSABLE, so missing data is never read as "no risk".
 */
import type { Answers, Assessment, Bi, FlagResult, FlagState, Route, TraceStep } from "./types";
import { questionById } from "./intake";

export const RULES_VERSION = "draft-0.3";

type Tri = boolean | null;
type Cond =
  | { eq: [string, string] }
  | { gte: [string, number] }
  | { all: Cond[] }
  | { any: Cond[] }
  | { not: Cond };

const computed = (id: string, a: Answers): number | string | null => {
  if (id === "bmi") {
    const h = a.height_cm, w = a.weight_kg;
    if (h?.status !== "answered" || w?.status !== "answered") return null;
    const m = Number(h.value) / 100;
    return Number(w.value) / (m * m);
  }
  const ans = a[id];
  return ans?.status === "answered" && ans.value !== undefined ? ans.value : null;
};

function evaluate(c: Cond, a: Answers): Tri {
  if ("eq" in c) {
    const v = computed(c.eq[0], a);
    return v === null ? null : v === c.eq[1];
  }
  if ("gte" in c) {
    const v = computed(c.gte[0], a);
    return v === null ? null : Number(v) >= c.gte[1];
  }
  if ("not" in c) {
    const v = evaluate(c.not, a);
    return v === null ? null : !v;
  }
  if ("all" in c) {
    const r = c.all.map((x) => evaluate(x, a));
    if (r.includes(false)) return false;
    return r.includes(null) ? null : true;
  }
  const r = c.any.map((x) => evaluate(x, a));
  if (r.includes(true)) return true;
  return r.includes(null) ? null : false;
}

type Rule = {
  id: string;
  label: Bi;
  when: Cond;
  requires: string[];
  route: Route;
  redFlag?: boolean;
  modifiable?: boolean;
  why: Bi;
  unknown: Bi;
  source: string;
};

const yes = (id: string): Cond => ({ eq: [id, "yes"] });
const EAU = "EAU Sexual & Reproductive Health guideline";
const AUA = "AUA/ASRM Male Infertility guideline";

const RED_FLAGS: Rule[] = [
  ["rf_pain", "Sudden severe pain", "ألم مفاجئ وشديد"],
  ["rf_lump", "New testicular lump", "كتلة جديدة في الخصية"],
  ["rf_swelling", "Fast-growing swelling", "تورم سريع الازدياد"],
  ["rf_fever", "Fever with pain", "حرارة مع ألم"],
  ["rf_blood", "Blood in semen", "دم في السائل المنوي"],
].map(([id, en, ar]) => ({
  id,
  label: { en, ar },
  when: yes(id),
  requires: [id],
  route: "URGENT" as Route,
  redFlag: true,
  why: { en: "You reported this today.", ar: "ذكرت هذا اليوم." },
  unknown: { en: "The cause. Only an exam can tell.", ar: "السبب. الفحص وحده يحدده." },
  source: EAU,
}));

const RULES: Rule[] = [
  {
    id: "ttc_duration",
    label: { en: "Trying for over a year", ar: "محاولة لأكثر من سنة" },
    when: { all: [{ eq: ["ttc", "trying"] }, { eq: ["ttc_months", "over_12"] }] },
    requires: ["ttc", "ttc_months"],
    route: "FERTILITY_SERVICES",
    why: { en: "After 12 months, both partners are usually checked.", ar: "بعد ١٢ شهرًا يُفحص الشريكان عادةً." },
    unknown: { en: "Your partner's results, if any.", ar: "نتائج الشريك إن وُجدت." },
    source: `${AUA} (threshold set in config)`,
  },
  {
    id: "anatomical",
    label: { en: "Testicular history", ar: "تاريخ يخص الخصية" },
    when: { any: [yes("undescended"), yes("torsion_injury"), yes("varicocele")] },
    requires: ["undescended", "torsion_injury", "varicocele"],
    route: "ANDROLOGY_UROLOGY",
    why: { en: "This can affect sperm production.", ar: "قد يؤثر هذا على إنتاج الحيوانات المنوية." },
    unknown: { en: "Whether it affects you. An exam can tell.", ar: "هل يؤثر عليك. الفحص يوضح ذلك." },
    source: EAU,
  },
  {
    id: "semen_abnormal",
    label: { en: "Past semen result not normal", ar: "نتيجة سابقة غير طبيعية" },
    when: { eq: ["semen_analysis", "abnormal"] },
    requires: ["semen_analysis"],
    route: "ANDROLOGY_UROLOGY",
    why: { en: "One result needs a specialist to interpret.", ar: "النتيجة تحتاج مختصًا لتفسيرها." },
    unknown: { en: "Whether it repeats. Results vary.", ar: "هل تتكرر. النتائج تتفاوت." },
    source: "WHO laboratory manual, 6th ed.",
  },
  {
    id: "steroids",
    label: { en: "Steroids or testosterone", ar: "منشطات أو تستوستيرون" },
    when: yes("steroids"),
    requires: ["steroids"],
    route: "ANDROLOGY_UROLOGY",
    modifiable: true,
    why: { en: "These can pause sperm production.", ar: "قد توقف إنتاج الحيوانات المنوية مؤقتًا." },
    unknown: { en: "How long recovery takes for you.", ar: "مدة التعافي في حالتك." },
    source: AUA,
  },
  {
    id: "cancer_treatment",
    label: { en: "Past cancer treatment", ar: "علاج سابق للسرطان" },
    when: yes("cancer_treatment"),
    requires: ["cancer_treatment"],
    route: "ANDROLOGY_UROLOGY",
    why: { en: "Treatment can affect sperm long term.", ar: "العلاج قد يؤثر على المدى الطويل." },
    unknown: { en: "Your current sperm health.", ar: "حالتك الحالية." },
    source: EAU,
  },
  {
    id: "metabolic",
    label: { en: "Weight, sugar or pressure", ar: "الوزن أو السكر أو الضغط" },
    when: { any: [{ gte: ["bmi", 30] }, yes("diabetes"), yes("blood_pressure")] },
    requires: ["height_cm", "weight_kg", "diabetes", "blood_pressure"],
    route: "PRIMARY_CARE",
    modifiable: true,
    why: { en: "These affect hormones and sperm quality.", ar: "تؤثر على الهرمونات وجودة الحيوانات المنوية." },
    unknown: { en: "Your hormone levels. A blood test shows them.", ar: "مستوى هرموناتك. تحليل الدم يوضحه." },
    source: `${EAU} (BMI cut-off set in config)`,
  },
  {
    id: "infection",
    label: { en: "Past infection", ar: "عدوى سابقة" },
    when: yes("infection"),
    requires: ["infection"],
    route: "PRIMARY_CARE",
    why: { en: "Some infections affect the testes.", ar: "بعض أنواع العدوى تؤثر على الخصيتين." },
    unknown: { en: "Whether there was lasting effect.", ar: "هل بقي أثر دائم." },
    source: EAU,
  },
  {
    id: "sexual_function",
    label: { en: "Changes in sexual function", ar: "تغيّر في الوظيفة الجنسية" },
    when: yes("sexual_changes"),
    requires: ["sexual_changes"],
    route: "PRIMARY_CARE",
    why: { en: "Often linked to treatable causes.", ar: "غالبًا مرتبط بأسباب قابلة للعلاج." },
    unknown: { en: "The cause.", ar: "السبب." },
    source: EAU,
  },
  {
    id: "lifestyle",
    label: { en: "Everyday exposures", ar: "عادات يومية" },
    when: { any: [yes("tobacco"), yes("alcohol"), yes("heat")] },
    requires: ["tobacco", "alcohol", "heat"],
    route: "SELF_CARE",
    modifiable: true,
    why: { en: "These lower sperm quality. Change shows in about 3 months.", ar: "تخفض جودة الحيوانات المنوية. يظهر التحسن خلال نحو ٣ أشهر." },
    unknown: { en: "How much they affect you.", ar: "مدى تأثيرها عليك." },
    source: AUA,
  },
];

const KEY_FOR_PROVISIONAL = ["ttc_duration", "anatomical", "semen_abnormal", "steroids", "cancer_treatment"];

export const ROUTE_RANK: Record<Route, number> = {
  SELF_CARE: 0,
  SELF_CARE_PROVISIONAL: 0,
  PRIMARY_CARE: 1,
  FERTILITY_SERVICES: 2,
  ANDROLOGY_UROLOGY: 3,
  URGENT: 4,
};

function toResult(rule: Rule, a: Answers): FlagResult {
  const v = evaluate(rule.when, a);
  const state: FlagState = v === true ? "PRESENT" : v === false ? "NOT_PRESENT_FROM_PROVIDED_DATA" : "NOT_ASSESSABLE";
  const missing =
    state === "NOT_ASSESSABLE"
      ? rule.requires.filter((q) => {
          const ans = a[q];
          if (q === "ttc_months" && a.ttc?.value !== "trying") return false;
          return !ans || ans.status !== "answered";
        })
      : [];
  return {
    id: rule.id,
    label: rule.label,
    state,
    redFlag: !!rule.redFlag,
    modifiable: !!rule.modifiable,
    why: rule.why,
    unknown: rule.unknown,
    source: rule.source,
    missing,
  };
}

const joinBi = (items: Bi[]): Bi => ({
  en: items.map((i) => i.en).join(", "),
  ar: items.map((i) => i.ar).join("، "),
});

export function assess(a: Answers): Assessment {
  const t0 = performance.now();
  const trace: TraceStep[] = [];
  const mark = (step: string, label: Bi, detail: Bi, from: number) =>
    trace.push({ step, label, detail, ms: Math.max(1, Math.round(performance.now() - from)) });

  // 1. validation + missing-data map
  let t = performance.now();
  const statuses = Object.values(a);
  const answered = statuses.filter((s) => s.status === "answered").length;
  const open = statuses.length - answered;
  mark(
    "validation",
    { en: "Answers checked", ar: "فحص الإجابات" },
    { en: `${answered} answered, ${open} left open`, ar: `${answered} مُجاب، ${open} دون إجابة` },
    t
  );

  // 2. red flags first
  t = performance.now();
  const red = RED_FLAGS.map((r) => toResult(r, a));
  const redPresent = red.filter((f) => f.state === "PRESENT");
  const redUnknown = red.some((f) => f.state === "NOT_ASSESSABLE");
  mark(
    "red_flags",
    { en: "Urgent signs", ar: "العلامات العاجلة" },
    redPresent.length
      ? { en: `${redPresent.length} found. Stopped here.`, ar: `وُجدت ${redPresent.length}. توقف التقييم هنا.` }
      : redUnknown
        ? { en: "Some left open. Route raised.", ar: "بعضها دون إجابة. رُفع المسار." }
        : { en: "None reported", ar: "لا شيء" },
    t
  );

  const base = {
    id: `a_${Math.random().toString(36).slice(2, 9)}`,
    rulesVersion: RULES_VERSION,
    createdAt: new Date().toISOString(),
    explanationSource: "template" as const,
  };

  if (redPresent.length) {
    mark("route", { en: "Route", ar: "المسار" }, { en: "URGENT (static safety text)", ar: "عاجل (نص سلامة ثابت)" }, t0);
    return {
      ...base,
      flags: redPresent,
      route: "URGENT",
      routeReason: joinBi(redPresent.map((f) => f.label)),
      missing: [],
      redFlagsUnanswered: false,
      trace,
    };
  }

  // 3. flags
  t = performance.now();
  const flags = RULES.map((r) => toResult(r, a));
  const present = flags.filter((f) => f.state === "PRESENT");
  const na = flags.filter((f) => f.state === "NOT_ASSESSABLE");
  mark(
    "flags",
    { en: "Signals", ar: "الإشارات" },
    { en: `${present.length} present, ${na.length} can't be assessed`, ar: `${present.length} موجودة، ${na.length} يتعذر تقييمها` },
    t
  );

  // 4. route with fixed precedence; uncertainty only escalates
  t = performance.now();
  let route: Route = "SELF_CARE";
  for (const f of present) {
    const r = RULES.find((x) => x.id === f.id)!.route;
    if (ROUTE_RANK[r] > ROUTE_RANK[route]) route = r;
  }
  const driving = present.filter((f) => RULES.find((x) => x.id === f.id)!.route === route);
  let routeReason: Bi = driving.length
    ? joinBi(driving.map((f) => f.label))
    : { en: "No signals from your answers", ar: "لا إشارات من إجاباتك" };

  if (redUnknown && ROUTE_RANK[route] < ROUTE_RANK.PRIMARY_CARE) {
    route = "PRIMARY_CARE";
    routeReason = { en: "Some urgent questions were left open", ar: "بعض الأسئلة العاجلة بلا إجابة" };
  }
  if (route === "SELF_CARE" && na.some((f) => KEY_FOR_PROVISIONAL.includes(f.id))) {
    route = "SELF_CARE_PROVISIONAL";
  }

  const missingIds = Array.from(
    new Set([...na.flatMap((f) => f.missing), ...red.flatMap((f) => f.missing)])
  );
  const missing = missingIds.map((id) => ({ id, label: questionById(id)?.label ?? { en: id, ar: id } }));

  mark("route", { en: "Route", ar: "المسار" }, { en: route.replaceAll("_", " "), ar: route.replaceAll("_", " ") }, t);
  mark("explanation", { en: "Explanation", ar: "الشرح" }, { en: "Template text (no AI used)", ar: "نص جاهز (دون ذكاء اصطناعي)" }, t);

  return {
    ...base,
    flags: [...flags, ...red.filter((f) => f.state === "NOT_ASSESSABLE")],
    route,
    routeReason,
    missing,
    redFlagsUnanswered: redUnknown,
    trace,
  };
}
