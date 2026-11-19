"use client";

import Link from "next/link";
import { AnimatePresence, motion } from "motion/react";
import { useStore, useT } from "@/lib/store";
import { PROVIDERS, SLOTS } from "@/lib/mock";
import type { ReferralStatus } from "@/lib/types";
import { Button, Label, LinkButton, Page } from "@/components/ui";

const STAGES: ReferralStatus[] = ["proposed", "clinician_review", "confirmed", "booked", "attended", "result_explained", "closed"];

export default function StatusPage() {
  const { referral, advanceReferral, cancelReferral } = useStore();
  const { t, L } = useT();

  if (!referral) {
    return (
      <Page title={t("statusTitle")} sub={t("noReferral")} actions={<LinkButton href="/">{t("startAssessment")}</LinkButton>} />
    );
  }

  const provider = PROVIDERS.find((p) => p.id === referral.providerId);
  const slot = SLOTS.find((s) => s.en === referral.slot);
  const ended = referral.status === "cancelled" || referral.status === "no_show";
  const reached = new Set(referral.events.map((e) => e.to));
  const lastReached = STAGES.reduce((acc, s, i) => (reached.has(s) ? i : acc), 0);
  const current = ended ? -1 : STAGES.indexOf(referral.status);
  const fill = lastReached / (STAGES.length - 1);
  const open = !ended && referral.status !== "closed";

  return (
    <Page
      title={t("statusTitle")}
      sub={`${provider ? L(provider.name) : ""}${slot ? `, ${L(slot)}` : ""}, ${t(`t_${referral.type}` as const)}`}
      actions={
        open ? (
          <>
            {/* Demo controls stand in for the navigator. Rule 7: only a clinician can confirm. */}
            {referral.status === "clinician_review" ? (
              <LinkButton href="/clinician" variant="quiet">
                {t("clinicianRole")}
              </LinkButton>
            ) : (
              <Button variant="quiet" onClick={() => advanceReferral("navigator")}>
                {t("demoNext")}
              </Button>
            )}
            <button
              type="button"
              onClick={cancelReferral}
              className="inline-flex h-12 cursor-pointer items-center rounded-full px-5 text-base font-medium text-alarm transition-colors hover:bg-alarm-soft"
            >
              {t("cancel")}
            </button>
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
              <motion.p key="pending" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="text-base text-ink">
                {t("pendingReview")}
              </motion.p>
            )}
          </AnimatePresence>

          {referral.clinicianNote && (
            <p className="border-s-2 border-pine ps-4 text-base text-ink">{referral.clinicianNote}</p>
          )}

          {referral.outcomeNote && (
            <div>
              <Label>{t("outcome")}</Label>
              <p className="text-base text-ink">{L(referral.outcomeNote)}</p>
            </div>
          )}

          {referral.reminders.length > 0 && (
            <div>
              <Label>
                {t("reminders")} ({t("simulated")})
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
