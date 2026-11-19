"use client";

import { useId, useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import { useT } from "@/lib/store";
import { questionById } from "@/lib/intake";
import type { FlagResult, FlagState } from "@/lib/types";
import { Icon } from "./icon";

/** Shape carries meaning alongside text: filled, dashed, hollow. */
export function Marker({ state }: { state: FlagState }) {
  const cls =
    state === "PRESENT"
      ? "bg-pine"
      : state === "NOT_ASSESSABLE"
        ? "border-[1.5px] border-dashed border-muted"
        : "border-[1.5px] border-line";
  return <span aria-hidden className={`mt-[0.45rem] block size-2.5 shrink-0 rounded-full ${cls}`} />;
}

export function FlagRow({ flag, delay }: { flag: FlagResult; delay?: number }) {
  const [open, setOpen] = useState(false);
  const { t, L, lang } = useT();
  const id = useId();
  const sep = lang === "ar" ? "، " : ", ";
  const stateText =
    flag.state === "PRESENT" ? t("sPresent") : flag.state === "NOT_ASSESSABLE" ? t("sUnknown") : t("sNone");

  return (
    <motion.li
      initial={delay === undefined ? false : { opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ delay: delay ?? 0, duration: 0.4 }}
    >
      <button
        type="button"
        aria-expanded={open}
        aria-controls={id}
        onClick={() => setOpen((o) => !o)}
        className="group flex w-full cursor-pointer items-start gap-4 py-5 text-start"
      >
        <Marker state={flag.state} />
        <span className="flex-1">
          <span className="block text-base text-ink transition-colors group-hover:text-pine">{L(flag.label)}</span>
          <span className="block text-sm text-muted">{stateText}</span>
        </span>
        <motion.span animate={{ rotate: open ? 90 : 0 }} className="mt-1 text-muted">
          <Icon name="chevron" className="size-4" />
        </motion.span>
      </button>

      <AnimatePresence initial={false}>
        {open && (
          <motion.div
            id={id}
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.32, ease: [0.22, 1, 0.36, 1] }}
            className="overflow-hidden"
          >
            <dl className="grid gap-x-10 gap-y-4 pb-6 ps-[1.625rem] text-sm md:grid-cols-2">
              {flag.state === "NOT_ASSESSABLE" && flag.missing.length > 0 ? (
                <div>
                  <dt className="text-muted">{t("unknownLabel")}</dt>
                  <dd className="text-ink">
                    {flag.missing.map((m) => L(questionById(m)?.label ?? { en: m, ar: m })).join(sep)}
                  </dd>
                </div>
              ) : (
                <>
                  <div>
                    <dt className="text-muted">{t("why")}</dt>
                    <dd className="text-ink">{L(flag.why)}</dd>
                  </div>
                  <div>
                    <dt className="text-muted">{t("unknownLabel")}</dt>
                    <dd className="text-ink">{L(flag.unknown)}</dd>
                  </div>
                </>
              )}
              {flag.modifiable && flag.state === "PRESENT" && <p className="text-pine md:col-span-2">{t("changeable")}</p>}
              <p className="text-xs text-muted md:col-span-2">
                {t("source")}: {flag.source}, {t("draft")}
              </p>
            </dl>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.li>
  );
}
