"use client";

import { useRouter } from "next/navigation";
import { useStore, useT } from "@/lib/store";
import { BackLink, Button, Page, Toggle } from "@/components/ui";
import type { ConsentScope } from "@/lib/types";
import type { StringKey } from "@/lib/strings";

const ITEMS: { scope: ConsentScope; label: StringKey; sub: StringKey }[] = [
  { scope: "intake", label: "c_intake", sub: "c_intake_sub" },
  { scope: "share_with_clinician", label: "c_share", sub: "c_share_sub" },
  { scope: "reminders", label: "c_reminders", sub: "c_reminders_sub" },
  { scope: "aggregate_analytics", label: "c_analytics", sub: "c_analytics_sub" },
];

export default function ConsentPage() {
  const { consent, setConsent, error } = useStore();
  const { t } = useT();
  const router = useRouter();

  return (
    <Page
      back={<BackLink href="/" label={t("back")} />}
      title={t("consentTitle")}
      sub={t("consentNote")}
      actions={
        <Button disabled={!consent.intake} onClick={() => router.push("/intake")}>
          {t("agree")}
        </Button>
      }
    >
      <div className="divide-y divide-line border-y border-line">
        {ITEMS.map((i) => (
          <Toggle
            key={i.scope}
            checked={consent[i.scope]}
            onChange={(v) => setConsent(i.scope, v)}
            label={t(i.label)}
            sub={t(i.sub)}
          />
        ))}
      </div>
      {error && (
        <p role="alert" className="mt-4 text-sm text-alarm">
          {t("serverError")} {error}
        </p>
      )}
    </Page>
  );
}
