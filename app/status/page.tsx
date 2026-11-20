"use client";

import { useEffect, useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import { useStore, useT } from "@/lib/store";
import { SLOTS } from "@/lib/mock";
import type { ReferralStatus } from "@/lib/types";
import { Button, Label, LinkButton, Page } from "@/components/ui";
import { BellRing, ClipboardList, FastForward, FileText, Hourglass, MessageSquareText, Stethoscope, X } from "lucide-react";

const STAGES: ReferralStatus[] = ["proposed", "clinician_review", "confirmed", "booked", "attended", "result_explained", "closed"];

export default function StatusPage() {
  const {
    referral, advanceReferral, closeReferral, cancelReferral, providers, loadProviders, busy, error,
  } = useStore();
  const { t, L, date } = useT();
  const [outcome, setOutcome] = useState("");
  useEffect(() => {
    if (referral && referral.providerId && !providers.some((p) => p.id === referral.providerId)) {
      void loadProviders({ type: referral.type, language: "any", gender: "any" });
    }
  }, [referral, providers, loadProviders]);

  if (!referral) {
    return (
      <Page
        title={t("statusTitle")}
        sub={t("noReferral")}
        aside={
          <span aria-hidden className="mt-8 grid size-14 place-items-center rounded-full bg-paper text-muted ring-1 ring-line">
            <ClipboardList className="size-6" strokeWidth={1.5} />
          </span>
        }
        actions={<LinkButton href="/" className="w-full sm:w-auto">{t("startAssessment")}</LinkButton>}
      />
    );
  }

  const provider = providers.find((p) => p.id === referral.providerId);
  const slot = SLOTS.find((s) => s.en === referral.slot);
  const when = referral.appointmentAt ? date(referral.appointmentAt) : slot ? L(slot) : "";
  const ended = referral.status === "cancelled" || referral.status === "no_show";
  const reached = new Set(referral.events.map((e) => e.to));
  const lastReached = STAGES.reduce((acc, s, i) => (reached.has(s) ? i : acc), 0);
  const current = ended ? -1 : STAGES.indexOf(referral.status);
  const fill = lastReached / (STAGES.length - 1);
  const open = !ended && referral.status !== "closed";
  const canCancel = referral.status === "clinician_review" || referral.status === "booked";
  // Demo controls stand in for staff, using the role each transition needs.
  const demoBy = referral.status === "attended" ? "clinician" : "navigator";

  return (
    <Page
      title={t("statusTitle")}
      sub={`${provider ? L(provider.name) : ""}${when ? `, ${when}` : ""}, ${t(`t_${referral.type}` as const)}`}
      actions={
        open ? (
          <>
            {/* Demo controls stand in for staff. Rule 7: only a clinician can confirm. */}
            {referral.status === "clinician_review" ? (
              <LinkButton href="/clinician" variant="quiet">
                <Stethoscope className="size-4" strokeWidth={1.7} aria-hidden />
                {t("clinicianRole")}
              </LinkButton>
            ) : referral.status === "result_explained" ? null : (
              <Button variant="quiet" disabled={busy} onClick={() => advanceReferral(demoBy)}>
                <FastForward className="size-4" strokeWidth={1.7} aria-hidden />
                {t("demoNext")}
              </Button>
            )}
            {canCancel && (
              <button
                type="button"
                onClick={() => cancelReferral()}
                disabled={busy}
                className="inline-flex h-12 cursor-pointer items-center gap-2 rounded-full px-5 text-base font-medium text-alarm transition-colors hover:bg-alarm-soft disabled:opacity-50"
              >
                <X className="size-4" strokeWidth={1.8} aria-hidden />
                {t("cancel")}
              </button>
            )}
          </>
        ) : null
      }
    >
      <div className="grid gap-12 md:grid-cols-2">
        <div className="relative">
          <div aria-hidden className="absolute inset-y-6 start-[0.65rem] w-0.5 rounded-full bg-line">
            <motion.div
              className="absolute inset-x-0 top-0 rounded-full bg-saffron"
              initial={false}
              animate={{ height: `${fill * 100}%` }}
              transition={{ duration: 0.8, ease: [0.65, 0, 0.35, 1] }}
            />
          </div>
          <ol className="relative">
            {STAGES.map((s, i) => {
              const done = reached.has(s) && i !== current;
              const isNow = i === current;
              return (
                <li key={s} className="flex h-12 items-center gap-5" aria-current={isNow ? "step" : undefined}>
                  <span className="relative grid size-[1.4rem] place-items-center">
                    {isNow ? (
                      <motion.span
                        key={`now-${s}`}
                        className="absolute inset-0 rounded-full bg-pine"
                        initial={{ scale: 0.3 }}
                        animate={{ scale: 1 }}
                        transition={{ delay: 0.5, type: "spring", stiffness: 420, damping: 18 }}
                      />
                    ) : (
                      <span className={`size-2.5 rounded-full ${done ? "bg-pine" : "bg-mist ring-2 ring-line"}`} />
                    )}
                  </span>
                  <span className={isNow ? "text-base font-medium text-ink" : done ? "text-base text-ink" : "text-base text-muted"}>
                    {t(`st_${s}` as const)}
                  </span>
                </li>
              );
            })}
          </ol>
          {ended && <p className="mt-4 text-base text-alarm">{t(`st_${referral.status}` as const)}</p>}
        </div>

        <div className="space-y-10">
          <AnimatePresence mode="wait">
            {referral.status === "clinician_review" && (
              <motion.p key="pending" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="flex items-start gap-3 rounded-2xl bg-paper p-4 text-base text-ink ring-1 ring-line">
                <Hourglass className="mt-0.5 size-5 shrink-0 text-pine" strokeWidth={1.6} aria-hidden />
                {t("pendingReview")}
              </motion.p>
            )}
          </AnimatePresence>

          {referral.clinicianNote && (
            <p className="flex items-start gap-3 border-s-2 border-pine ps-4 text-base text-ink">
              <MessageSquareText className="mt-0.5 size-5 shrink-0 text-pine" strokeWidth={1.6} aria-hidden />
              {referral.clinicianNote}
            </p>
          )}

          {referral.outcomeNote && (
            <div>
              <Label>
                <span className="inline-flex items-center gap-1.5">
                  <FileText className="size-4" strokeWidth={1.6} aria-hidden />
                  {t("outcome")}
                </span>
              </Label>
              <p className="text-base text-ink">{L(referral.outcomeNote)}</p>
            </div>
          )}

          {referral.status === "result_explained" && (
            <div>
              <Label>{t("outcome")}</Label>
              <textarea
                rows={3}
                value={outcome}
                onChange={(e) => setOutcome(e.target.value)}
                placeholder={t("outcomePlaceholder")}
                className="w-full resize-none rounded-2xl bg-paper p-4 text-base text-ink ring-1 ring-line outline-none placeholder:text-muted/70 focus:ring-2 focus:ring-pine"
              />
              <div className="mt-4">
                <Button disabled={busy || !outcome.trim()} onClick={() => closeReferral(outcome)}>
                  {busy ? t("working") : t("recordOutcome")}
                </Button>
              </div>
            </div>
          )}

          {error && (
            <p role="alert" className="text-sm text-alarm">
              {t("serverError")} {error}
            </p>
          )}

          {referral.reminders.length > 0 && (
            <div>
              <Label>
                <span className="inline-flex items-center gap-1.5">
                  <BellRing className="size-4" strokeWidth={1.6} aria-hidden />
                  {t("reminders")} ({t("simulated")})
                </span>
              </Label>
              <ul className="space-y-2">
                {referral.reminders.map((r, i) => (
                  <motion.li
                    key={i}
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    transition={{ delay: i * 0.08 }}
                    className="text-base text-ink"
                  >
                    {L(r.text)}
                  </motion.li>
                ))}
              </ul>
            </div>
          )}
        </div>
      </div>
    </Page>
  );
}
