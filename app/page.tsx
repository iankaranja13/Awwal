"use client";

import { motion } from "motion/react";
import { useT } from "@/lib/store";
import { ArrowRight, Clock, Lock, Trash2, UserRoundX } from "lucide-react";
import { LinkButton } from "@/components/ui";

export default function Welcome() {
  const { t } = useT();
  const promises = [
    { text: t("promise1"), icon: UserRoundX },
    { text: t("promise2"), icon: Lock },
    { text: t("promise3"), icon: Trash2 },
  ];

  return (
    <section className="grid flex-1 items-center gap-12 py-10 sm:gap-16 sm:py-16 lg:grid-cols-12 lg:gap-20">
      <div className="lg:col-span-7">
        <h1 className="display max-w-[14ch] text-[2.5rem] leading-[1.08] font-light sm:text-2xl text-ink md:text-3xl">{t("welcomeTitle")}</h1>

        {/* The path begins: a saffron mark that draws once. */}
        <div className="relative mt-10 h-px sm:mt-12 w-full max-w-xl bg-line" aria-hidden>
          <motion.span
            className="absolute inset-y-0 start-0 bg-saffron"
            initial={{ width: 0 }}
            animate={{ width: "22%" }}
            transition={{ delay: 0.35, duration: 1.1, ease: [0.22, 1, 0.36, 1] }}
          />
          <motion.span
            className="absolute -top-[3px] start-0 size-[7px] rounded-full bg-saffron"
            initial={{ scale: 0 }}
            animate={{ scale: 1 }}
            transition={{ delay: 0.25, type: "spring", stiffness: 500, damping: 20 }}
          />
        </div>

        <div className="mt-10 flex flex-col items-stretch gap-4 sm:mt-12 sm:flex-row sm:flex-wrap sm:items-center sm:gap-6">
          <LinkButton href="/consent" className="group h-14 px-10">
            {t("start")}
            <ArrowRight className="flip-rtl size-5 transition-transform group-hover:translate-x-0.5" strokeWidth={1.8} aria-hidden />
          </LinkButton>
          <span className="inline-flex items-center justify-center gap-1.5 text-sm text-muted">
            <Clock className="size-4" strokeWidth={1.6} aria-hidden />
            {t("minutes")}
          </span>
        </div>
      </div>

      <ul className="divide-y divide-line border-y border-line lg:col-span-5">
        {promises.map(({ text, icon: I }) => (
          <li key={text} className="flex items-center gap-4 py-5 text-lg font-light text-ink sm:py-6">
            <span aria-hidden className="grid size-10 shrink-0 place-items-center rounded-full bg-paper text-pine ring-1 ring-line">
              <I className="size-[1.15rem]" strokeWidth={1.6} />
            </span>
            {text}
          </li>
        ))}
      </ul>
    </section>
  );
}
