"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import { useStore, useT } from "@/lib/store";
import type { ConsentScope } from "@/lib/types";
import type { StringKey } from "@/lib/strings";
import { Button, Label, Page, Sheet, Toggle } from "@/components/ui";
import { Icon } from "@/components/icon";

const SCOPES: [ConsentScope, StringKey][] = [
  ["intake", "c_intake"],
  ["share_with_clinician", "c_share"],
  ["reminders", "c_reminders"],
  ["aggregate_analytics", "c_analytics"],
];

export default function PrivacyPage() {
  const { consent, setConsent, shares, createShare, revokeShare, audit, exportData, deleteAll } = useStore();
  const { t, L, date } = useT();
  const router = useRouter();
  const [confirm, setConfirm] = useState(false);
  const [showAll, setShowAll] = useState(false);

  const download = () => {
    const blob = new Blob([exportData()], { type: "application/json" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = "awwal-my-data.json";
    a.click();
    setTimeout(() => URL.revokeObjectURL(a.href), 1000);
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
            <Icon name="download" className="size-4" />
            {t("exportData")}
          </Button>
          <button
            type="button"
            onClick={() => setConfirm(true)}
            className="inline-flex h-12 cursor-pointer items-center rounded-full px-5 text-base font-medium text-alarm transition-colors hover:bg-alarm-soft"
          >
            {t("deleteData")}
          </button>
        </>
      }
    >
      <Section title={t("consentH")}>
        <div className="divide-y divide-line">
          {SCOPES.map(([s, k]) => (
            <Toggle key={s} checked={consent[s]} onChange={(v) => setConsent(s, v)} label={t(k)} />
          ))}
        </div>
      </Section>

      <Section title={t("sharesH")}>
        <ul className="divide-y divide-line">
          <AnimatePresence initial={false}>
            {shares.map((s) => (
              <motion.li
                key={s.id}
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: "auto" }}
                className="flex items-center justify-between gap-4 overflow-hidden py-4"
              >
                <span>
                  <span className="block text-base text-ink">{L(s.recipient)}</span>
                  <span className="block text-sm text-muted">
                    {s.revokedAt ? t("revoked") : `${t("expires")} ${date(s.expiresAt)}`}
                  </span>
                </span>
                {!s.revokedAt && (
                  <button
                    type="button"
                    onClick={() => revokeShare(s.id)}
                    className="h-10 cursor-pointer rounded-full px-4 text-sm text-alarm hover:bg-alarm-soft"
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

      <Section title={t("activityH")}>
        {audit.length === 0 ? (
          <p className="py-4 text-base text-muted">{t("noActivity")}</p>
        ) : (
          <ul className="divide-y divide-line">
            {activity.map((e) => (
              <li key={e.id} className="flex items-baseline justify-between gap-6 py-3">
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
        <div className="mt-10 flex flex-wrap gap-3">
          <Button
            variant="alarm"
            onClick={() => {
              deleteAll();
              setConfirm(false);
              router.push("/");
            }}
          >
            {t("deleteConfirm")}
          </Button>
          <Button variant="quiet" onClick={() => setConfirm(false)}>
            {t("keep")}
          </Button>
        </div>
      </Sheet>
    </Page>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="mb-12 last:mb-0">
      <Label>{title}</Label>
      <div className="border-t border-line">{children}</div>
    </section>
  );
}
