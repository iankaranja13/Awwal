"use client";

import { motion } from "motion/react";
import { useT } from "@/lib/store";
import { LinkButton } from "@/components/ui";

export default function Welcome() {
  const { t } = useT();
  const promises = [t("promise1"), t("promise2"), t("promise3")];

  return (
    <section className="grid flex-1 items-center gap-16 py-16 lg:grid-cols-12 lg:gap-20">
      <div className="lg:col-span-7">
        <h1 className="display max-w-[14ch] text-2xl font-light text-ink md:text-3xl">{t("welcomeTitle")}</h1>

        {/* The path begins: a saffron mark that draws once. */}
        <div className="relative mt-12 h-px w-full max-w-xl bg-line" aria-hidden>
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

        <div className="mt-12 flex flex-wrap items-center gap-6">
          <LinkButton href="/consent" className="h-14 px-10">
            {t("start")}
          </LinkButton>
          <span className="text-sm text-muted">{t("minutes")}</span>
        </div>
      </div>

      <ul className="divide-y divide-line border-y border-line lg:col-span-5">
        {promises.map((p) => (
          <li key={p} className="py-6 text-lg font-light text-ink">
            {p}
          </li>
        ))}
      </ul>
    </section>
  );
}
