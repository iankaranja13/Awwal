"use client";

import { motion } from "motion/react";
import { useT } from "@/lib/store";
import type { Assessment } from "@/lib/types";
import { Sheet } from "./ui";

export function TraceSheet({ open, onClose, assessment }: { open: boolean; onClose: () => void; assessment: Assessment }) {
  const { t, L, num } = useT();
  return (
    <Sheet open={open} onClose={onClose} title={t("traceTitle")} closeLabel={t("close")}>
      <ol className="relative space-y-6 border-s border-line ps-6">
        {assessment.trace.map((s, i) => (
          <motion.li
            key={s.step + i}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.15 + i * 0.06 }}
            className="relative"
          >
            <span aria-hidden className="absolute -start-[1.84rem] top-[0.45rem] size-2 rounded-full bg-pine" />
            <div className="flex items-baseline justify-between gap-4">
              <span className="text-base text-ink">{L(s.label)}</span>
              <span className="text-xs tabular-nums text-muted">{num(s.ms)} ms</span>
            </div>
            <p className="text-sm text-muted">{L(s.detail)}</p>
          </motion.li>
        ))}
      </ol>
      <p className="mt-8 text-xs text-muted">
        {t("rules")} {assessment.rulesVersion}. {t("traceNote")}
      </p>
    </Sheet>
  );
}
