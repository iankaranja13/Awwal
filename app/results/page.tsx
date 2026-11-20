"use client";

import { useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import { useStore, useT } from "@/lib/store";
import type { FlagResult } from "@/lib/types";
import { Button, Label, LinkButton, Page, useRequire } from "@/components/ui";
import { FlagRow } from "@/components/flag-row";
import { TraceSheet } from "@/components/trace-sheet";
import { Icon } from "@/components/icon";
import { ArrowRight, ListTree } from "lucide-react";

export default function ResultsPage() {
  const { assessment } = useStore();
  const { t } = useT();
  const [showNone, setShowNone] = useState(false);
  const [trace, setTrace] = useState(false);
  if (!useRequire(!!assessment, "/intake") || !assessment) return null;

  const by = (s: FlagResult["state"]) => assessment.flags.filter((f) => f.state === s);
  const present = by("PRESENT");
  const unknown = by("NOT_ASSESSABLE");
  const none = by("NOT_PRESENT_FROM_PROVIDED_DATA");

  return (
    <Page
      title={t("resultsTitle")}
      sub={t("resultsNote")}
      actions={
        <>
          <LinkButton href="/next">
            {t("nextStep")}
            <ArrowRight className="flip-rtl size-5" strokeWidth={1.8} aria-hidden />
          </LinkButton>
          <Button variant="quiet" onClick={() => setTrace(true)}>
            <ListTree className="size-4" strokeWidth={1.6} aria-hidden />
            {t("howDecided")}
          </Button>
        </>
      }
    >
      {present.length > 0 && <Group title={t("gPresent")} flags={present} offset={0} />}
      {unknown.length > 0 && <Group title={t("gUnknown")} flags={unknown} offset={present.length} />}

      {none.length > 0 && (
        <section>
          <button
            type="button"
            aria-expanded={showNone}
            onClick={() => setShowNone((s) => !s)}
            className="flex h-12 w-full cursor-pointer items-center justify-between text-sm text-muted hover:text-ink"
          >
            <span>
              {t("gNone")} ({none.length})
            </span>
            <motion.span animate={{ rotate: showNone ? 90 : 0 }}>
              <Icon name="chevron" className="size-4" />
            </motion.span>
          </button>
          <AnimatePresence initial={false}>
            {showNone && (
              <motion.ul
                initial={{ height: 0, opacity: 0 }}
                animate={{ height: "auto", opacity: 1 }}
                exit={{ height: 0, opacity: 0 }}
                className="divide-y divide-line overflow-hidden border-t border-line"
              >
                {none.map((f) => (
                  <FlagRow key={f.id} flag={f} />
                ))}
              </motion.ul>
            )}
          </AnimatePresence>
        </section>
      )}

      <TraceSheet open={trace} onClose={() => setTrace(false)} assessment={assessment} />
    </Page>
  );
}

function Group({ title, flags, offset }: { title: string; flags: FlagResult[]; offset: number }) {
  return (
    <section className="mb-10">
      <Label>{title}</Label>
      <ul className="divide-y divide-line border-y border-line">
        {flags.map((f, i) => (
          <FlagRow key={f.id} flag={f} delay={0.2 + (offset + i) * 0.07} />
        ))}
      </ul>
    </section>
  );
}
