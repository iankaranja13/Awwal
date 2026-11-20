"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import { useStore, useT } from "@/lib/store";
import { BOOKABLE_ROUTES } from "@/lib/mapping";
import { SLOTS } from "@/lib/mock";
import type { BookingType, Lang } from "@/lib/types";
import { BackLink, Button, Chip, Label, Page, Sheet, Toggle, useRequire } from "@/components/ui";

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
            <div role="radiogroup" aria-label={t("bookTitle")} className="grid max-w-md grid-cols-4 rounded-full bg-paper p-1 ring-1 ring-line">
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
                  className={`relative h-10 cursor-pointer rounded-full text-sm transition-colors ${type === ty ? "text-paper" : "text-ink hover:text-pine"}`}
                >
                  {type === ty && (
                    <motion.span
                      layoutId="type-pill"
                      className="absolute inset-0 rounded-full bg-pine"
                      transition={{ type: "spring", stiffness: 500, damping: 40 }}
                    />
                  )}
                  <span className="relative">{t(`t_${ty}` as const)}</span>
                </button>
              ))}
            </div>
            {type === "sample_collection" && (
              <button
                type="button"
                onClick={() => setInfo(true)}
                className="mt-3 cursor-pointer text-sm text-pine underline-offset-4 hover:underline"
              >
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
      <ul className="divide-y divide-line border-y border-line">
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
                    <span className="flex-1 text-base text-ink">{L(p.name)}</span>
                    <span className="text-sm text-muted">
                      {L(p.area)}
                      {type === "sample_collection" && p.homeSampling ? `, ${t("home")}` : ""}
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
                          {SLOTS.map((s, i) => (
                            <Chip key={s.en} selected={slot === i} onClick={() => setSlot(i)}>
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
              <input
                id="phone"
                type="tel"
                autoComplete="tel"
                value={phone}
                onChange={(e) => setPhone(e.target.value)}
                placeholder="+971 50 000 0000"
                className="h-12 w-full rounded-full bg-paper px-5 text-base text-ink ring-1 ring-line outline-none transition-shadow placeholder:text-muted/60 focus:ring-2 focus:ring-pine"
              />
            </div>
            <div className="flex flex-col items-start gap-2">
              <Button disabled={!ready || busy} onClick={submit}>
                {busy ? t("working") : t("requestBooking")}
              </Button>
              {error && (
                <p role="alert" className="text-sm text-alarm">
                  {t("serverError")} {error}
                </p>
              )}
            </div>
            {needsReview && !consent.share_with_clinician && (
              <div className="border-y border-line md:col-span-2">
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
