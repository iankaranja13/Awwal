import type { Bi, Route } from "./types";

export const SLOTS: Bi[] = [
  { en: "Tomorrow, 9:30", ar: "غدًا، ٩:٣٠" },
  { en: "Tomorrow, 18:00", ar: "غدًا، ١٨:٠٠" },
  { en: "Sat, 11:00", ar: "السبت، ١١:٠٠" },
];

export const ROUTE_TEXT: Record<Route, { title: Bi; short: Bi }> = {
  URGENT: { title: { en: "Get care now", ar: "اطلب الرعاية الآن" }, short: { en: "Urgent", ar: "عاجل" } },
  ANDROLOGY_UROLOGY: { title: { en: "See a urology specialist", ar: "راجع أخصائي مسالك بولية" }, short: { en: "Specialist", ar: "أخصائي" } },
  FERTILITY_SERVICES: { title: { en: "Book a fertility check", ar: "احجز فحص خصوبة" }, short: { en: "Fertility", ar: "الخصوبة" } },
  PRIMARY_CARE: { title: { en: "See a family doctor", ar: "راجع طبيب الأسرة" }, short: { en: "Doctor", ar: "طبيب" } },
  SELF_CARE: { title: { en: "Start with small changes", ar: "ابدأ بتغييرات بسيطة" }, short: { en: "Self-care", ar: "رعاية ذاتية" } },
  SELF_CARE_PROVISIONAL: { title: { en: "A few answers are missing", ar: "تنقص بعض الإجابات" }, short: { en: "Self-care", ar: "رعاية ذاتية" } },
};

/** Order of stops on the route line, lowest to highest. */
export const ROUTE_LADDER: Route[] = ["SELF_CARE", "PRIMARY_CARE", "FERTILITY_SERVICES", "ANDROLOGY_UROLOGY", "URGENT"];

/** Seeded synthetic cases waiting for clinician review. */
export const SEEDED_QUEUE: {
  id: string;
  handle: string;
  route: Route;
  waiting: Bi;
  present: Bi[];
  unknown: Bi[];
}[] = [
  {
    id: "s1",
    handle: "Falcon 214",
    route: "FERTILITY_SERVICES",
    waiting: { en: "2 h ago", ar: "قبل ساعتين" },
    present: [{ en: "Trying for over a year", ar: "محاولة لأكثر من سنة" }, { en: "Everyday exposures", ar: "عادات يومية" }],
    unknown: [{ en: "Past semen result", ar: "نتيجة سابقة" }],
  },
  {
    id: "s2",
    handle: "Cedar 087",
    route: "PRIMARY_CARE",
    waiting: { en: "5 h ago", ar: "قبل ٥ ساعات" },
    present: [{ en: "Weight, sugar or pressure", ar: "الوزن أو السكر أو الضغط" }],
    unknown: [],
  },
];
