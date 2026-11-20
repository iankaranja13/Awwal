"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { motion } from "motion/react";
import { useStore, useT } from "@/lib/store";
import { TOPICS } from "@/lib/intake";
import { ROUTE_TEXT } from "@/lib/mock";
import { BackLink, Button, Label, LinkButton, Page, useRequire } from "@/components/ui";
import { RouteLine } from "@/components/route-line";
import { TraceSheet } from "@/components/trace-sheet";
import { Icon } from "@/components/icon";

export default function NextStepPage() {
  const { assessment, setTopicIndex } = useStore();
  const { t, L } = useT();
  const router = useRouter();
  const [trace, setTrace] = useState(false);
  if (!useRequire(!!assessment, "/intake") || !assessment) return null;

  const { route } = assessment;

  /* ---------- Urgent: static safety text, nothing generated, no booking ---------- */
  if (route === "URGENT") {
    return (
      <>
        <motion.div
          aria-hidden
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="fixed inset-0 -z-10 bg-alarm-soft"
        />
        <div className="grid flex-1 items-center gap-12 py-16 lg:grid-cols-12 lg:gap-20">
          <div className="lg:col-span-7">
            <motion.span
              aria-hidden
              className="mb-10 block size-3.5 rounded-full bg-alarm"
              animate={{ scale: [1, 1.4, 1] }}
              transition={{ duration: 1.6, repeat: 2 }}
            />
            <h1 className="display text-2xl font-normal text-alarm md:text-3xl">{L(ROUTE_TEXT.URGENT.title)}</h1>
            <p className="mt-6 max-w-lg text-lg font-light text-ink">
              {assessment.safety ? L(assessment.safety.body) : t("urgentBody")}
            </p>
          </div>

          <div className="lg:col-span-5">
            <Label>{t("urgentReported")}</Label>
            <p className="text-lg text-ink">{L(assessment.routeReason)}</p>
            <a
              href="tel:998"
              className="mt-10 inline-flex h-14 items-center justify-center gap-2 rounded-full bg-alarm px-10 text-base font-medium text-white transition-[filter,transform] hover:brightness-110 active:scale-[0.985]"
            >
              <Icon name="phone" />
              {t("urgentCall")}
            </a>
            <p className="mt-4 text-base text-ink">{t("urgentEd")}</p>
            <button
              type="button"
              onClick={() => setTrace(true)}
              className="mt-8 cursor-pointer text-sm text-muted underline-offset-4 hover:underline"
            >
              {t("howDecided")}
            </button>
          </div>
        </div>
        <TraceSheet open={trace} onClose={() => setTrace(false)} assessment={assessment} />
      </>
    );
  }

  const provisional = route === "SELF_CARE_PROVISIONAL";
  const selfCare = route === "SELF_CARE";
  const changeable = assessment.flags.filter((f) => f.state === "PRESENT" && f.modifiable);

  const answerMissing = () => {
    const first = assessment.missing[0]?.id;
    const idx = TOPICS.findIndex((tp) => tp.questions.some((q) => q.id === first));
    setTopicIndex(Math.max(0, idx));
    router.push("/intake");
  };

  // Self-care routes need no booking, so they offer none.
  const actions = provisional ? (
    <>
      <Button onClick={answerMissing}>{t("answerMissing")}</Button>
      <LinkButton href="/results" variant="quiet">
        {t("seeResults")}
      </LinkButton>
    </>
  ) : selfCare ? (
    <Button variant="quiet" onClick={() => setTrace(true)}>
      {t("howDecided")}
    </Button>
  ) : (
    <>
      <LinkButton href="/booking">{t("book")}</LinkButton>
      <Button variant="quiet" onClick={() => setTrace(true)}>
        {t("howDecided")}
      </Button>
    </>
  );

  return (
    <Page
      back={<BackLink href="/results" label={t("back")} />}
      title={L(ROUTE_TEXT[route].title)}
      sub={provisional ? t("missingWhy") : `${t("basedOn")}: ${L(assessment.routeReason)}`}
      actions={actions}
      aside={
        !selfCare && !provisional ? <p className="mt-6 text-sm text-muted">{t("reviewNote")}</p> : null
      }
    >
      <div className="rounded-[2rem] bg-paper px-6 pb-10 pt-12 md:px-10">
        <RouteLine route={route} />
      </div>

      {assessment.redFlagsUnanswered && <p className="mt-8 text-base text-alarm">{t("redOpen")}</p>}

      {provisional && (
        <div className="mt-10">
          <Label>{t("missingH")}</Label>
          <ul className="divide-y divide-line border-y border-line">
            {assessment.missing.map((m) => (
              <li key={m.id} className="py-4 text-base text-ink">
                {L(m.label)}
              </li>
            ))}
          </ul>
        </div>
      )}

      {selfCare && changeable.length > 0 && (
        <div className="mt-10">
          <Label>{t("selfCareSteps")}</Label>
          <ul className="divide-y divide-line border-y border-line">
            {changeable.map((f) => (
              <li key={f.id} className="py-4">
                <span className="block text-base text-ink">{L(f.label)}</span>
                <span className="block text-sm text-muted">{L(f.why)}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      <TraceSheet open={trace} onClose={() => setTrace(false)} assessment={assessment} />
    </Page>
  );
}
