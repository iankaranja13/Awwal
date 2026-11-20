"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect } from "react";
import { AnimatePresence, motion } from "motion/react";
import { useStore, useT } from "@/lib/store";
import { Icon } from "./icon";

const NAV = [
  { href: "/status", key: "navReferral" },
  { href: "/privacy", key: "privacy" },
  { href: "/clinician", key: "clinicianRole" },
] as const;

export function Shell({ children }: { children: React.ReactNode }) {
  const { hidden, setHidden } = useStore();
  const { t } = useT();
  const path = usePathname();

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape" && hidden) setHidden(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [hidden, setHidden]);

  return (
    <div className="mx-auto flex min-h-dvh w-full max-w-[76rem] flex-col px-6 md:px-12">
      <header className="flex h-20 items-center justify-between border-b border-line">
        <Link href="/" className="display text-xl font-normal text-ink">
          Awwal
        </Link>
        <nav className="flex items-center gap-1 md:gap-2">
          {NAV.map((n) => {
            const active = path.startsWith(n.href);
            return (
              <Link
                key={n.href}
                href={n.href}
                aria-current={active ? "page" : undefined}
                className={`relative hidden h-10 items-center rounded-full px-4 text-sm transition-colors sm:inline-flex ${
                  active ? "text-ink" : "text-muted hover:text-ink"
                }`}
              >
                {t(n.key)}
                {active && (
                  <motion.span layoutId="nav-underline" className="absolute inset-x-4 -bottom-[21px] h-px bg-ink" />
                )}
              </Link>
            );
          })}
          <button
            type="button"
            onClick={() => setHidden(true)}
            className="ms-2 inline-flex h-10 cursor-pointer items-center gap-2 rounded-full px-4 text-sm text-ink ring-1 ring-line transition-colors hover:bg-pine-soft"
          >
            <Icon name="hide" className="size-4" />
            {t("quickHide")}
          </button>
        </nav>
      </header>

      <main className="flex flex-1 flex-col">{children}</main>

      <footer className="flex flex-wrap items-center justify-between gap-2 border-t border-line py-5 text-xs text-muted">
        <span>{t("banner")}</span>
        <span>{t("footerRules")}</span>
      </footer>

      <AnimatePresence>
        {hidden && (
          <motion.div
            key="cover"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.12 }}
            className="fixed inset-0 z-50 bg-white text-neutral-800"
          >
            <div className="mx-auto max-w-[76rem] px-6 pt-8 md:px-12">
              {/* Neutral cover. Click the title (or press Esc) to return. */}
              <button type="button" onClick={() => setHidden(false)} className="text-2xl font-medium">
                {t("notes")}
              </button>
              <p className="mt-10 text-sm text-neutral-400">{t("noNotes")}</p>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
