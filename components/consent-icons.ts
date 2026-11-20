import { BarChart3, BellRing, ClipboardList, Stethoscope, type LucideIcon } from "lucide-react";
import type { ConsentScope } from "@/lib/types";

export const CONSENT_ICON: Record<ConsentScope, LucideIcon> = {
  intake: ClipboardList,
  share_with_clinician: Stethoscope,
  reminders: BellRing,
  aggregate_analytics: BarChart3,
};
