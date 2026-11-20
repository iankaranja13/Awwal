"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import { useStore, useT } from "@/lib/store";
import { BOOKABLE_ROUTES } from "@/lib/mapping";
import { SLOTS } from "@/lib/mock";
import type { BookingType, Lang } from "@/lib/types";
import { BackLink, BottomBar, Button, Chip, Label, Page, Sheet, Toggle, useRequire } from "@/components/ui";
import { Building2, CalendarCheck, ChevronDown, Clock, Droplet, House, Info, MapPin, Phone, TestTube, Video, type LucideIcon } from "lucide-react";

const TYPE_ICON: Record<BookingType, LucideIcon> = {
  teleconsult: Video,
  blood_test: Droplet,
  sample_collection: TestTube,
  in_person: Building2,
};

const TYPES: BookingType[] = ["teleconsult", "blood_test", "sample_collection", "in_person"];

export default function BookingPage() {
  const {
    assessment, consent, setConsent, createReferral, providers, providersLoading, loadProviders, busy, error,
  } = useStore();
  const { t, L } = useT();
  const router = useRouter();
  const [type, setType] = useState<BookingType>("teleconsult");
  const [langF, setLangF] = useState<Lang | "any">("any");
  const [gender, setGender] = useState<"any" | "male" | "female">("any");
  const [providerId, setProviderId] = useState<string | null>(null);
  const [slot, setSlot] = useState<number | null>(null);
  const [phone, setPhone] = useState("");
  const [info, setInfo] = useState(false);
  const hasAssessment = useRequire(!!assessment, "/intake");
  const bookable = useRequire(!assessment || BOOKABLE_ROUTES.includes(assessment.route), "/next");
  useEffect(() => {
    if (assessment && BOOKABLE_ROUTES.includes(assessment.route)) {
      void loadProviders({ type, language: langF, gender });
    }
  }, [assessment, type, langF, gender, loadProviders]);
  if (!hasAssessment || !bookable || !assessment) return null;

  // Every bookable route needs clinician review before confirmation.
  const needsReview = true;
  const list = providers;
  const phoneOk = phone.replace(/\D/g, "").length >= 9;
  const ready = providerId && slot !== null && phoneOk && consent.share_with_clinician;
  const missing = !providerId
    ? t("needProvider")
    : slot === null
      ? t("needSlot")
      : !phoneOk
        ? t("needPhone")
        : !consent.share_with_clinician
          ? t("needShare")
          : null;
  // Where the missing piece lives, so the hint can take you there.
  const missingTarget = !providerId || slot === null ? "providers" : !phoneOk ? "phone" : "share";
  const goToMissing = () => {
    const el = document.getElementById(missingTarget);
    el?.scrollIntoView({ behavior: "smooth", block: "center" });
    if (missingTarget === "phone") setTimeout(() => (el as HTMLInputElement | null)?.focus({ preventScroll: true }), 400);
  };

  const pick = (id: string) => {
    setProviderId(id === providerId ? null : id);
    setSlot(null);
  };

  const submit = async () => {
    if (!ready || slot === null || !providerId) return;
    const ok = await createReferral(type, providerId, SLOTS[slot].en, phone);
    if (ok) router.push("/status");
  };

  return (
    <Page
      back={<BackLink href="/next" label={t("back")} />}
      title={t("bookTitle")}
      aside={
        <div className="mt-10 space-y-8">
          {/* type: segmented control with a sliding indicator */}
          <div>
            <div role="radiogroup" aria-label={t("bookTitle")} className="grid w-full max-w-md grid-cols-2 gap-1 rounded-[1.5rem] bg-paper p-1 ring-1 ring-line sm:grid-cols-4 sm:gap-0 sm:rounded-full">
              {TYPES.map((ty) => (
                <button
                  key={ty}
                  type="button"
                  role="radio"
                  aria-checked={type === ty}
                  onClick={() => {
                    setType(ty);
                    setProviderId(null);
                    setSlot(null);
                  }}
                  className={`relative h-11 cursor-pointer rounded-full text-sm transition-colors sm:h-10 ${type === ty ? "text-paper" : "text-ink hover:text-pine"}`}
                >
                  {type === ty && (
                    <motion.span
                      layoutId="type-pill"
                      className="absolute inset-0 rounded-full bg-pine"
                      transition={{ type: "spring", stiffness: 500, damping: 40 }}
                    />
                  )}
                  <span className="relative inline-flex items-center justify-center gap-1.5">
                    {(() => {
                      const I = TYPE_ICON[ty];
                      return <I className="size-4 shrink-0" strokeWidth={1.7} aria-hidden />;
                    })()}
                    {t(`t_${ty}` as const)}
                  </span>
                </button>
              ))}
            </div>
            {type === "sample_collection" && (
              <button
                type="button"
                onClick={() => setInfo(true)}
                className="mt-2 inline-flex h-11 cursor-pointer items-center gap-1.5 text-sm text-pine underline-offset-4 hover:underline"
              >
                <Info className="size-4" strokeWidth={1.7} aria-hidden />
                {t("howCollection")}
              </button>
            )}
          </div>

          <FilterRow label={t("fLanguage")}>
            {(["any", "ar", "en"] as const).map((l) => (
              <Chip key={l} selected={langF === l} onClick={() => setLangF(l)}>
                {l === "any" ? t("any") : l === "ar" ? "Arabic" : "English"}
              </Chip>
            ))}
          </FilterRow>
          <FilterRow label={t("fClinician")}>
            {(["any", "male", "female"] as const).map((g) => (
              <Chip key={g} selected={gender === g} onClick={() => setGender(g)}>
                {t(g)}
              </Chip>
            ))}
          </FilterRow>
        </div>
      }
    >
      <ul id="providers" className="scroll-mt-24 divide-y divide-line border-y border-line">
        <AnimatePresence initial={false} mode="popLayout">
          {providersLoading ? (
            <motion.li key="loading" initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="py-8 text-base text-muted">
              {t("loadingProviders")}
            </motion.li>
          ) : list.length === 0 ? (
            <motion.li key="empty" initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="py-8 text-base text-muted">
              {t("noProviders")}
            </motion.li>
          ) : (
            list.map((p) => {
              const on = providerId === p.id;
              return (
                <motion.li key={p.id} layout initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
                  <button
                    type="button"
                    aria-pressed={on}
                    onClick={() => pick(p.id)}
                    className="group flex w-full cursor-pointer items-center gap-5 py-5 text-start"
                  >
                    <span
                      aria-hidden
                      className={`grid size-5 shrink-0 place-items-center rounded-full ring-[1.5px] transition-colors ${on ? "ring-pine" : "ring-line group-hover:ring-pine/50"}`}
                    >
                      {on && <motion.span layoutId="provider-dot" className="size-2.5 rounded-full bg-pine" />}
                    </span>
                    <span className="flex flex-1 flex-col gap-0.5 sm:flex-row sm:items-center sm:justify-between sm:gap-4">
                      <span className="text-base text-ink">{L(p.name)}</span>
                      <span className="inline-flex items-center gap-1 text-sm text-muted">
                        <MapPin className="size-3.5" strokeWidth={1.7} aria-hidden />
                        {L(p.area)}
                        {type === "sample_collection" && p.homeSampling ? (
                          <>
                            <span aria-hidden>·</span>
                            <House className="size-3.5" strokeWidth={1.7} aria-hidden />
                            {t("home")}
                          </>
                        ) : null}
                      </span>
                    </span>
                  </button>
                  <AnimatePresence initial={false}>
                    {on && (
                      <motion.div
                        initial={{ height: 0, opacity: 0 }}
                        animate={{ height: "auto", opacity: 1 }}
                        exit={{ height: 0, opacity: 0 }}
                        className="overflow-hidden"
                      >
                        <div className="flex flex-wrap gap-2 pb-6 ps-10">
                          <span className="sr-only">{t("needSlot")}</span>
                          {SLOTS.map((s, i) => (
                            <Chip key={s.en} selected={slot === i} onClick={() => setSlot(i)}>
                              {slot !== i && <Clock className="size-3.5 text-muted" strokeWidth={1.7} aria-hidden />}
                              {L(s)}
                            </Chip>
                          ))}
                        </div>
                      </motion.div>
                    )}
                  </AnimatePresence>
                </motion.li>
              );
            })
          )}
        </AnimatePresence>
      </ul>

      <AnimatePresence>
        {slot !== null && (
          <motion.div
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            className="mt-10 grid gap-6 md:grid-cols-2 md:items-end"
          >
            <div>
              <label htmlFor="phone" className="block text-base text-ink">
                {t("phone")}
              </label>
              <p className="mb-3 text-sm text-muted">{t("phoneHint")}</p>
              <div className="relative">
              <Phone aria-hidden className="pointer-events-none absolute start-5 top-1/2 size-4 -translate-y-1/2 text-muted" strokeWidth={1.7} />
              <input
                id="phone"
                type="tel"
                autoComplete="tel"
                value={phone}
                onChange={(e) => setPhone(e.target.value)}
                placeholder="+971 50 000 0000"
                className="h-12 w-full rounded-full bg-paper pe-5 ps-12 text-base text-ink ring-1 ring-line outline-none transition-shadow placeholder:text-muted/60 focus:ring-2 focus:ring-pine"
              />
              </div>
            </div>
            <div className="hidden flex-col items-start gap-2 lg:flex">
              <Button disabled={!ready || busy} onClick={submit}>
                <CalendarCheck className="size-5" strokeWidth={1.7} aria-hidden />
                {busy ? t("working") : t("requestBooking")}
              </Button>
              {missing && <p className="text-sm text-muted">{missing}</p>}
              {error && (
                <p role="alert" className="text-sm text-alarm">
                  {t("serverError")} {error}
                </p>
              )}
            </div>
            {needsReview && !consent.share_with_clinician && (
              <div id="share" className="scroll-mt-24 border-y border-line md:col-span-2">
                <Toggle
                  checked={consent.share_with_clinician}
                  onChange={(v) => setConsent("share_with_clinician", v)}
                  label={t("c_share")}
                  sub={t("c_share_sub")}
                />
              </div>
            )}
            {needsReview && <p className="text-sm text-muted md:col-span-2">{t("reviewNote")}</p>}
          </motion.div>
        )}
      </AnimatePresence>

      {/* Phones: the request button is always in reach and says what's still needed */}
      <div aria-hidden className="h-32 lg:hidden" />
      <BottomBar>
        <AnimatePresence mode="wait" initial={false}>
          {missing && (
            <motion.button
              type="button"
              key={missing}
              onClick={goToMissing}
              initial={{ opacity: 0, y: 4 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0 }}
              className="inline-flex h-9 cursor-pointer items-center justify-center gap-1 text-sm text-pine"
              aria-live="polite"
            >
              {missing}
              <ChevronDown className="size-4" strokeWidth={1.8} aria-hidden />
            </motion.button>
          )}
        </AnimatePresence>
        {error && (
          <p role="alert" className="pb-2 text-center text-sm text-alarm">
            {t("serverError")} {error}
          </p>
        )}
        <Button disabled={!ready || busy} onClick={submit}>
          <CalendarCheck className="size-5" strokeWidth={1.7} aria-hidden />
          {busy ? t("working") : t("requestBooking")}
        </Button>
      </BottomBar>

      <Sheet open={info} onClose={() => setInfo(false)} title={t("howCollection")} closeLabel={t("close")}>
        <p className="text-base text-ink">{t("collectionBody")}</p>
      </Sheet>
    </Page>
  );
}

function FilterRow({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <Label>{label}</Label>
      <div className="flex flex-wrap gap-2">{children}</div>
    </div>
  );
}
