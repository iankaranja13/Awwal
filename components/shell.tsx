"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { motion } from "motion/react";
import { Home, ShieldCheck, Stethoscope, ClipboardCheck, Route as RouteIcon, type LucideIcon } from "lucide-react";
import { useStore, useT } from "@/lib/store";
import type { StringKey } from "@/lib/strings";
import { isFlowRoute } from "./nav";

const NAV: { href: string; key: StringKey; icon: LucideIcon }[] = [
  { href: "/status", key: "navReferral", icon: RouteIcon },
  { href: "/privacy", key: "privacy", icon: ShieldCheck },
  { href: "/clinician", key: "clinicianRole", icon: Stethoscope },
];

export function Shell({ children }: { children: React.ReactNode }) {
  const { consent, assessment } = useStore();
  const { t } = useT();
  const path = usePathname();
  const flow = isFlowRoute(path);

  // The centre tab resumes wherever the user is in the check.
  const checkHref = assessment ? "/results" : consent.intake ? "/intake" : "/consent";

  return (
    <div className="mx-auto flex min-h-dvh w-full max-w-[76rem] flex-col px-4 sm:px-6 md:px-12">
      <header className="sticky top-0 z-30 -mx-4 flex h-16 items-center justify-between border-b border-line bg-mist/90 px-4 backdrop-blur-md sm:static sm:mx-0 sm:h-20 sm:bg-transparent sm:px-0 sm:backdrop-blur-none">
        <Link href="/" className="display flex items-center gap-2.5 text-xl font-normal text-ink">
          <span aria-hidden className="grid size-8 place-items-center rounded-[0.6rem] bg-pine text-paper sm:size-9">
            <span className="-mt-0.5 text-lg font-light leading-none">a</span>
          </span>
          Awwal
        </Link>
        <nav className="flex items-center gap-1 md:gap-2">
          {NAV.map((n) => {
            const active = path.startsWith(n.href);
            const I = n.icon;
            return (
              <Link
                key={n.href}
                href={n.href}
                aria-current={active ? "page" : undefined}
                className={`relative hidden h-10 items-center gap-2 rounded-full px-4 text-sm transition-colors sm:inline-flex ${
                  active ? "text-ink" : "text-muted hover:text-ink"
                }`}
              >
                <I className="size-4" strokeWidth={1.6} aria-hidden />
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

      <footer
        className={`flex flex-wrap items-center justify-between gap-2 border-t border-line py-5 text-xs text-muted ${
          flow ? "" : "pb-28 sm:pb-5"
        }`}
      >
        <span>{t("banner")}</span>
        <span>{t("footerRules")}</span>
      </footer>

      {/* Phones: bottom tab bar, hidden inside the linear check flow */}
      {!flow && (
        <nav
          aria-label="Main"
          className="fixed inset-x-0 bottom-0 z-30 border-t border-line bg-paper/95 pb-[env(safe-area-inset-bottom)] backdrop-blur-md sm:hidden"
        >
          <ul className="mx-auto grid h-16 max-w-md grid-cols-5 items-center">
            <Tab href="/" label={t("navHome")} icon={Home} active={path === "/"} />
            <Tab href="/status" label={t("tabReferral")} icon={RouteIcon} active={path.startsWith("/status")} />
            <li className="flex justify-center">
              <Link
                href={checkHref}
                aria-label={t("tabCheck")}
                className="-mt-7 grid size-14 place-items-center rounded-full bg-pine text-paper shadow-[0_6px_16px_-4px_rgba(14,38,36,0.45)] ring-4 ring-mist transition-transform active:scale-95"
              >
                <ClipboardCheck className="size-6" strokeWidth={1.7} aria-hidden />
              </Link>
            </li>
            <Tab href="/privacy" label={t("privacy")} icon={ShieldCheck} active={path.startsWith("/privacy")} />
            <Tab href="/clinician" label={t("tabClinician")} icon={Stethoscope} active={path.startsWith("/clinician")} />
          </ul>
        </nav>
      )}

    </div>
  );
}

function Tab({ href, label, icon: I, active }: { href: string; label: string; icon: LucideIcon; active: boolean }) {
  return (
    <li>
      <Link
        href={href}
        aria-current={active ? "page" : undefined}
        className={`flex flex-col items-center gap-1 py-1 text-[0.7rem] transition-colors ${active ? "text-ink" : "text-muted"}`}
      >
        <span className={`grid h-7 w-12 place-items-center rounded-full transition-colors ${active ? "bg-pine-soft" : ""}`}>
          <I className="size-5" strokeWidth={active ? 1.9 : 1.6} aria-hidden />
        </span>
        {label}
      </Link>
    </li>
  );
}
