"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { motion } from "motion/react";
import { useT } from "@/lib/store";

const NAV = [
  { href: "/status", key: "navReferral" },
  { href: "/privacy", key: "privacy" },
  { href: "/clinician", key: "clinicianRole" },
] as const;

export function Shell({ children }: { children: React.ReactNode }) {
  const { t } = useT();
  const path = usePathname();

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
        </nav>
      </header>

      <main className="flex flex-1 flex-col">{children}</main>

      <footer className="flex flex-wrap items-center justify-between gap-2 border-t border-line py-5 text-xs text-muted">
        <span>{t("banner")}</span>
        <span>{t("footerRules")}</span>
      </footer>
    </div>
  );
}
