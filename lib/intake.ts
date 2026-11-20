import type { Option, Question, Topic } from "./types";

/** Draft intake. Wording and Arabic need clinician + native-speaker review. */

const yesNo: Option[] = [
  { value: "yes", label: { en: "Yes", ar: "نعم" } },
  { value: "no", label: { en: "No", ar: "لا" } },
];

const yn = (id: string, en: string, ar: string): Question => ({
  id,
  kind: "choice",
  label: { en, ar },
  options: yesNo,
});

export const TOPICS: Topic[] = [
  {
    id: "about",
    title: { en: "About you", ar: "عنك" },
    why: { en: "Timing changes which checks make sense.", ar: "التوقيت يحدد الفحوصات المناسبة." },
    questions: [
      {
        id: "age_band",
        kind: "choice",
        label: { en: "Your age", ar: "عمرك" },
        options: [
          { value: "18_29", label: { en: "18–29", ar: "١٨–٢٩" } },
          { value: "30_39", label: { en: "30–39", ar: "٣٠–٣٩" } },
          { value: "40_49", label: { en: "40–49", ar: "٤٠–٤٩" } },
          { value: "50_plus", label: { en: "50+", ar: "+٥٠" } },
        ],
      },
      {
        id: "ttc",
        kind: "choice",
        label: { en: "Hoping for a child?", ar: "هل تخطط لإنجاب طفل؟" },
        options: [
          { value: "trying", label: { en: "Trying now", ar: "نحاول الآن" } },
          { value: "planning", label: { en: "Planning", ar: "نخطط لاحقًا" } },
          { value: "not_now", label: { en: "Not now", ar: "ليس الآن" } },
        ],
      },
      {
        id: "ttc_months",
        kind: "choice",
        label: { en: "For how long?", ar: "منذ متى؟" },
        showIf: { id: "ttc", equals: "trying" },
        options: [
          { value: "under_6", label: { en: "Under 6 months", ar: "أقل من ٦ أشهر" } },
          { value: "6_12", label: { en: "6–12 months", ar: "٦–١٢ شهرًا" } },
          { value: "over_12", label: { en: "Over a year", ar: "أكثر من سنة" } },
        ],
      },
    ],
  },
  {
    id: "now",
    title: { en: "Right now", ar: "الآن" },
    why: { en: "These need care today, not a booking.", ar: "هذه تحتاج رعاية اليوم، لا موعدًا." },
    questions: [
      yn("rf_pain", "Sudden, severe testicular pain", "ألم مفاجئ وشديد في الخصية"),
      yn("rf_lump", "A new lump in a testicle", "كتلة جديدة في الخصية"),
      yn("rf_swelling", "Swelling that is growing fast", "تورم يزداد بسرعة"),
      yn("rf_fever", "Fever with testicular pain", "حرارة مع ألم في الخصية"),
      yn("rf_blood", "Blood in semen", "دم في السائل المنوي"),
    ],
  },
  {
    id: "history",
    title: { en: "Your history", ar: "تاريخك الصحي" },
    why: { en: "Past events can affect sperm years later.", ar: "أحداث سابقة قد تؤثر على الحيوانات المنوية بعد سنوات." },
    questions: [
      yn("undescended", "Undescended testicle as a child", "خصية معلّقة في الطفولة"),
      yn("torsion_injury", "Testicular twist, injury or surgery", "التواء أو إصابة أو جراحة في الخصية"),
      yn("varicocele", "Told you have a varicocele", "تشخيص سابق بدوالي الخصية"),
      yn("infection", "Mumps after puberty, or an STI", "نكاف بعد البلوغ أو عدوى منقولة جنسيًا"),
    ],
  },
  {
    id: "body",
    title: { en: "Your body", ar: "جسمك" },
    why: { en: "Weight and blood sugar affect hormones.", ar: "الوزن والسكر يؤثران على الهرمونات." },
    questions: [
      { id: "height_cm", kind: "number", label: { en: "Height", ar: "الطول" }, unit: { en: "cm", ar: "سم" }, min: 120, max: 230 },
      { id: "weight_kg", kind: "number", label: { en: "Weight", ar: "الوزن" }, unit: { en: "kg", ar: "كغ" }, min: 35, max: 250 },
      yn("diabetes", "Diabetes", "السكري"),
      yn("blood_pressure", "High blood pressure", "ارتفاع ضغط الدم"),
    ],
  },
  {
    id: "habits",
    title: { en: "Habits", ar: "العادات" },
    why: { en: "Most of these can change in about three months.", ar: "معظمها يمكن تغييره خلال نحو ثلاثة أشهر." },
    questions: [
      yn("tobacco", "Smoke, vape or use shisha", "التدخين أو السجائر الإلكترونية أو الشيشة"),
      yn("alcohol", "Alcohol most weeks", "الكحول معظم الأسابيع"),
      yn("steroids", "Steroids or testosterone products", "منشطات أو منتجات تستوستيرون"),
      yn("heat", "Regular heat or chemical exposure", "تعرض منتظم للحرارة أو المواد الكيميائية"),
    ],
  },
  {
    id: "medical",
    title: { en: "Treatment", ar: "العلاج" },
    why: { en: "Some treatments affect sperm production.", ar: "بعض العلاجات تؤثر على إنتاج الحيوانات المنوية." },
    questions: [
      yn("cancer_treatment", "Chemotherapy or radiation", "علاج كيميائي أو إشعاعي"),
      yn("sexual_changes", "Changes in erections or desire", "تغيّر في الانتصاب أو الرغبة"),
    ],
  },
  {
    id: "tests",
    title: { en: "Past tests", ar: "فحوصات سابقة" },
    why: { en: "A past result can save you a repeat test.", ar: "نتيجة سابقة قد توفر عليك فحصًا مكررًا." },
    questions: [
      {
        id: "semen_analysis",
        kind: "choice",
        label: { en: "Semen analysis", ar: "تحليل السائل المنوي" },
        options: [
          { value: "never", label: { en: "Never had one", ar: "لم أجرِه" } },
          { value: "normal", label: { en: "Normal", ar: "طبيعي" } },
          { value: "abnormal", label: { en: "Not normal", ar: "غير طبيعي" } },
        ],
      },
    ],
  },
];

export const ALL_QUESTIONS: Question[] = TOPICS.flatMap((t) => t.questions);
export const questionById = (id: string) => ALL_QUESTIONS.find((q) => q.id === id);
