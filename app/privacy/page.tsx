"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import { useStore, useT } from "@/lib/store";
import type { ConsentScope } from "@/lib/types";
import type { StringKey } from "@/lib/strings";
import { Button, Label, Page, Sheet, Toggle } from "@/components/ui";
import { CONSENT_ICON } from "@/components/consent-icons";
import { Download, History, Link2, Link2Off, ShieldCheck, Share2, Trash2, type LucideIcon } from "lucide-react";

const SCOPES: [ConsentScope, StringKey][] = [
  ["intake", "c_intake"],
  ["share_with_clinician", "c_share"],
  ["reminders", "c_reminders"],
  ["aggregate_analytics", "c_analytics"],
];

export default function PrivacyPage() {
  const {
    consent, setConsent, shares, createShare, revokeShare, refreshShares, audit, refreshAudit,
    exportData, deleteAll, busy, error,
  } = useStore();
  const { t, L, date } = useT();
  const router = useRouter();
  const [confirm, setConfirm] = useState(false);
  const [showAll, setShowAll] = useState(false);
  useEffect(() => {
    void refreshAudit();
    void refreshShares();
  }, [refreshAudit, refreshShares]);

  const download = async () => {
    const data = await exportData();
    if (data === null) return;
    const blob = new Blob([data], { type: "application/json" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = "awwal-my-data.json";
    a.click();
    setTimeout(() => URL.revokeObjectURL(a.href), 1000);
  };

  const remove = async () => {
    const ok = await deleteAll();
    if (!ok) return;
    setConfirm(false);
    router.push("/");
  };

  const activity = showAll ? audit : audit.slice(0, 5);
  const activeShare = shares.some((s) => !s.revokedAt);

  return (
    <Page
      title={t("privacyTitle")}
      sub={t("privacySub")}
      actions={
        <>
          <Button variant="quiet" onClick={download}>
            <Download className="size-4" strokeWidth={1.7} aria-hidden />
            {t("exportData")}
          </Button>
          <button
            type="button"
            onClick={() => setConfirm(true)}
            className="inline-flex h-12 cursor-pointer items-center gap-2 rounded-full px-5 text-base font-medium text-alarm transition-colors hover:bg-alarm-soft"
          >
            <Trash2 className="size-4" strokeWidth={1.7} aria-hidden />
            {t("deleteData")}
          </button>
        </>
      }
    >
      {error && (
        <p role="alert" className="mb-8 text-sm text-alarm">
          {t("serverError")} {error}
        </p>
      )}

      <Section title={t("consentH")} icon={ShieldCheck}>
        <div className="divide-y divide-line">
          {SCOPES.map(([s, k]) => (
            <Toggle
              key={s}
              checked={consent[s]}
              onChange={(v) => setConsent(s, v)}
              label={t(k)}
              icon={(() => {
                const I = CONSENT_ICON[s];
                return <I className="size-[1.1rem]" strokeWidth={1.6} />;
              })()}
            />
          ))}
        </div>
      </Section>

      <Section title={t("sharesH")} icon={Share2}>
        <ul className="divide-y divide-line">
          <AnimatePresence initial={false}>
            {shares.map((s) => (
              <motion.li
                key={s.id}
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: "auto" }}
                className="flex items-center justify-between gap-4 overflow-hidden py-4"
              >
                <span className="flex items-center gap-3">
                  <span
                    aria-hidden
                    className={`grid size-10 shrink-0 place-items-center rounded-full ${s.revokedAt ? "bg-paper text-muted ring-1 ring-line" : "bg-pine-soft text-pine"}`}
                  >
                    {s.revokedAt ? <Link2Off className="size-4" strokeWidth={1.7} /> : <Link2 className="size-4" strokeWidth={1.7} />}
                  </span>
                  <span>
                  <span className="block text-base text-ink">{L(s.recipient)}</span>
                  <span className="block text-sm text-muted">
                    {s.revokedAt ? t("revoked") : `${t("expires")} ${date(s.expiresAt)}`}
                  </span>
                  </span>
                </span>
                {!s.revokedAt && (
                  <button
                    type="button"
                    onClick={() => revokeShare(s.id)}
                    className="h-11 shrink-0 cursor-pointer rounded-full px-4 text-sm text-alarm hover:bg-alarm-soft"
                  >
                    {t("revoke")}
                  </button>
                )}
              </motion.li>
            ))}
          </AnimatePresence>
        </ul>
        {shares.length === 0 && <p className="py-4 text-base text-muted">{t("noShares")}</p>}
        {consent.share_with_clinician ? (
          !activeShare && (
            <button type="button" onClick={createShare} className="mt-1 h-10 cursor-pointer text-sm text-pine underline-offset-4 hover:underline">
              {t("shareNow")}
            </button>
          )
        ) : (
          <p className="pt-1 text-sm text-muted">{t("shareNeedsConsent")}</p>
        )}
      </Section>

      <Section title={t("activityH")} icon={History}>
        {audit.length === 0 ? (
          <p className="py-4 text-base text-muted">{t("noActivity")}</p>
        ) : (
          <ul className="divide-y divide-line">
            {activity.map((e) => (
              <li key={e.id} className="flex items-baseline justify-between gap-4 py-3 sm:gap-6">
                <span className="text-base text-ink">{L(e.action)}</span>
                <span className="shrink-0 text-sm tabular-nums text-muted">{date(e.at)}</span>
              </li>
            ))}
          </ul>
        )}
        {audit.length > 5 && (
          <button type="button" onClick={() => setShowAll((v) => !v)} className="mt-2 h-10 cursor-pointer text-sm text-pine">
            {showAll ? t("showLess") : t("showAll")}
          </button>
        )}
      </Section>

      <Sheet open={confirm} onClose={() => setConfirm(false)} title={t("deleteConfirmTitle")} closeLabel={t("close")}>
        <p className="text-base text-ink">{t("deleteConfirmBody")}</p>
        <div className="mt-8 flex flex-col gap-2 sm:mt-10 sm:flex-row sm:flex-wrap sm:gap-3">
          <Button variant="alarm" disabled={busy} onClick={remove}>
            <Trash2 className="size-4" strokeWidth={1.7} aria-hidden />
            {busy ? t("working") : t("deleteConfirm")}
          </Button>
          <Button variant="quiet" onClick={() => setConfirm(false)}>
            {t("keep")}
          </Button>
        </div>
      </Sheet>
    </Page>
  );
}

function Section({ title, icon: I, children }: { title: string; icon: LucideIcon; children: React.ReactNode }) {
  return (
    <section className="mb-12 last:mb-0">
      <Label>
        <span className="inline-flex items-center gap-1.5">
          <I className="size-4" strokeWidth={1.6} aria-hidden />
          {title}
        </span>
      </Label>
      <div className="border-t border-line">{children}</div>
    </section>
  );
}
