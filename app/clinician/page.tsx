"use client";

import { useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import { useStore, useT } from "@/lib/store";
import { ROUTE_TEXT, SEEDED_QUEUE } from "@/lib/mock";
import type { Bi, Route } from "@/lib/types";
import { Button, Chip, Label } from "@/components/ui";
import { Icon } from "@/components/icon";
import { BackLink } from "@/components/ui";
import { CheckCircle2, Inbox, NotebookPen, Route as RouteIcon } from "lucide-react";
import { Marker } from "@/components/flag-row";

type Case = { id: string; handle: string; route: Route; waiting: Bi; present: { label: Bi; source?: string }[]; unknown: Bi[] };

const EDITABLE: Route[] = ["ANDROLOGY_UROLOGY", "FERTILITY_SERVICES", "PRIMARY_CARE", "SELF_CARE"];

/** Master-detail: queue on the left, the selected brief on the right. */
export default function ClinicianPage() {
  const { assessment, referral, shares, consent, reviews, signOff } = useStore();
  const { t, L } = useT();
  const [openId, setOpenId] = useState<string | null>(null);

  // The user's own case appears only while shared, unexpired and awaiting review.
  const sharedNow = consent.share_with_clinician && shares.some((s) => !s.revokedAt && new Date(s.expiresAt) > new Date());
  const cases: Case[] = [
    ...(assessment && referral?.status === "clinician_review" && sharedNow
      ? [
          {
            id: "me",
            handle: t("you"),
            route: referral.route,
            waiting: { en: "just now", ar: "الآن" },
            present: assessment.flags.filter((f) => f.state === "PRESENT").map((f) => ({ label: f.label, source: f.source })),
            unknown: assessment.flags.filter((f) => f.state === "NOT_ASSESSABLE").map((f) => f.label),
          },
        ]
      : []),
    ...SEEDED_QUEUE.map((s) => ({ ...s, present: s.present.map((label) => ({ label })) })),
  ];
  const pending = cases.filter((c) => !reviews[c.id]);
  const active = pending.find((c) => c.id === openId);
  const open = (id: string | null) => {
    setOpenId(id);
    // On phones the brief replaces the queue, so start it at the top.
    if (window.matchMedia("(max-width: 1023px)").matches) window.scrollTo({ top: 0 });
  };

  return (
    <div className="grid flex-1 gap-8 py-8 sm:gap-12 sm:py-10 lg:grid-cols-12 lg:gap-16 lg:py-16">
      {/* Phones: master-detail as two screens. The queue hides while a brief is open. */}
      <aside className={`lg:col-span-4 ${active ? "hidden lg:block" : ""}`}>
        <h1 className="display text-xl font-light text-ink">{t("clinicianTitle")}</h1>
        <p className="mt-3 text-base text-muted">
          {pending.length} {t("waiting")}
        </p>
        {pending.length === 0 ? (
          <div className="mt-10 flex items-center gap-3 text-base text-muted">
            <CheckCircle2 className="size-5 text-pine" strokeWidth={1.6} aria-hidden />
            {t("queueEmpty")}
          </div>
        ) : (
          <ul className="mt-10 divide-y divide-line border-y border-line">
            <AnimatePresence initial={false}>
              {pending.map((c) => {
                const on = c.id === openId;
                return (
                  <motion.li key={c.id} layout exit={{ opacity: 0, height: 0 }} className="relative overflow-hidden">
                    {on && <motion.span layoutId="queue-active" className="absolute inset-y-0 start-0 w-0.5 bg-pine" />}
                    <button
                      type="button"
                      aria-current={on ? "true" : undefined}
                      onClick={() => open(c.id)}
                      className="group flex w-full cursor-pointer items-center gap-4 py-5 ps-5 text-start"
                    >
                      <span
                        aria-hidden
                        className={`grid size-10 shrink-0 place-items-center rounded-full text-sm font-medium ${
                          c.id === "me" ? "bg-pine text-paper" : "bg-pine-soft text-pine"
                        }`}
                      >
                        {c.handle.charAt(0)}
                      </span>
                      <span className="flex-1">
                        <span className={`block text-base ${on ? "font-medium text-ink" : "text-ink group-hover:text-pine"}`}>{c.handle}</span>
                        <span className="block text-sm text-muted">
                          {L(ROUTE_TEXT[c.route].short)}, {L(c.waiting)}
                        </span>
                      </span>
                      <Icon name="chevron" className="size-4 text-muted" />
                    </button>
                  </motion.li>
                );
              })}
            </AnimatePresence>
          </ul>
        )}
      </aside>

      <section className={`lg:col-span-8 ${active ? "" : "hidden lg:block"}`}>
        <AnimatePresence mode="wait" initial={false}>
          {active ? (
            <motion.div key={active.id} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}>
              <div className="lg:hidden">
                <BackLink label={t("backToQueue")} onClick={() => open(null)} />
              </div>
              <Brief c={active} onSign={(r, n) => signOff(active.id, r, n)} onDone={() => open(null)} />
            </motion.div>
          ) : (
            <motion.div
              key="empty"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="grid min-h-[22rem] place-items-center rounded-[2rem] border border-dashed border-line text-base text-muted"
            >
              <span className="flex flex-col items-center gap-3">
                <Inbox className="size-7" strokeWidth={1.4} aria-hidden />
                {t("selectCase")}
              </span>
            </motion.div>
          )}
        </AnimatePresence>
      </section>
    </div>
  );
}

function Brief({ c, onSign, onDone }: { c: Case; onSign: (r: Route, note: string) => Promise<boolean>; onDone: () => void }) {
  const { t, L } = useT();
  const { error } = useStore();
  const [route, setRoute] = useState<Route>(c.route);
  const [note, setNote] = useState("");
  const [signed, setSigned] = useState(false);
  const [failed, setFailed] = useState(false);

  const sign = async () => {
    if (signed) return;
    const ok = await onSign(route, note.trim());
    if (!ok) {
      setFailed(true);
      return;
    }
    setSigned(true);
    // Let the confirmation register before the case leaves the queue.
    setTimeout(() => {
      onDone();
    }, 900);
  };

  return (
    <div className="rounded-[1.75rem] bg-paper p-5 sm:rounded-[2rem] sm:p-8 md:p-12">
      <h2 className="display text-xl font-light text-ink">{c.handle}</h2>

      <div className="mt-10 grid gap-10 md:grid-cols-2">
        <div>
          <Label>{t("present")}</Label>
          <ul className="space-y-4 border-t border-line pt-4">
            {c.present.map((p) => (
              <li key={p.label.en} className="flex gap-4">
                <Marker state="PRESENT" />
                <span>
                  <span className="block text-base text-ink">{L(p.label)}</span>
                  {p.source && <span className="block text-sm text-muted">{p.source}</span>}
                </span>
              </li>
            ))}
          </ul>
        </div>
        <div>
          <Label>{t("cantAssess")}</Label>
          <ul className="space-y-4 border-t border-line pt-4">
            {c.unknown.length === 0 ? (
              <li className="text-base text-muted">{t("none")}</li>
            ) : (
              c.unknown.map((u) => (
                <li key={u.en} className="flex gap-4">
                  <Marker state="NOT_ASSESSABLE" />
                  <span className="text-base text-ink">{L(u)}</span>
                </li>
              ))
            )}
          </ul>
        </div>
      </div>

      <div className="mt-10">
        <Label>
          <RouteIcon className="me-1.5 inline size-4 align-[-3px]" strokeWidth={1.6} aria-hidden />
          {t("routeH")}
          {route !== c.route && (
            <span className="text-pine">
              {" "}
              ({t("edited")} {L(ROUTE_TEXT[c.route].short)})
            </span>
          )}
        </Label>
        <div className="flex flex-wrap gap-2">
          {EDITABLE.map((r) => (
            <Chip key={r} selected={route === r} onClick={() => setRoute(r)}>
              {L(ROUTE_TEXT[r].short)}
            </Chip>
          ))}
        </div>
      </div>

      <div className="mt-10">
        <label htmlFor="note" className="mb-2 flex items-center gap-1.5 text-sm text-muted">
          <NotebookPen className="size-4" strokeWidth={1.6} aria-hidden />
          {t("notesH")}
        </label>
        <textarea
          id="note"
          rows={3}
          value={note}
          onChange={(e) => setNote(e.target.value)}
          placeholder={t("notePlaceholder")}
          className="w-full resize-none rounded-2xl bg-mist p-4 text-base text-ink ring-1 ring-line outline-none placeholder:text-muted/70 focus:ring-2 focus:ring-pine"
        />
      </div>

      {failed && error && (
        <p role="alert" className="mt-6 text-sm text-alarm">
          {t("serverError")} {error}
        </p>
      )}

      <div className="mt-8">
        <Button onClick={sign} aria-disabled={signed} className="w-full sm:w-auto">
          <AnimatePresence mode="wait" initial={false}>
            {signed ? (
              <motion.span key="done" initial={{ opacity: 0, scale: 0.8 }} animate={{ opacity: 1, scale: 1 }} className="inline-flex items-center gap-2">
                <Icon name="check" />
                {t("signedOff")}
              </motion.span>
            ) : (
              <motion.span key="sign" exit={{ opacity: 0 }}>
                {t("signOff")}
              </motion.span>
            )}
          </AnimatePresence>
        </Button>
      </div>
    </div>
  );
}
