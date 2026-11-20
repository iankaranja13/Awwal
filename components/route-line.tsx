"use client";

import { motion } from "motion/react";
import { useT } from "@/lib/store";
import { ROUTE_LADDER, ROUTE_TEXT } from "@/lib/mock";
import type { Route } from "@/lib/types";

/**
 * The signature moment: the care path from self-care to urgent.
 * A saffron line draws along it and the user's stop settles into place.
 */
export function RouteLine({ route }: { route: Route }) {
  const { t, L } = useT();
  const target: Route = route === "SELF_CARE_PROVISIONAL" ? "SELF_CARE" : route;
  const k = ROUTE_LADDER.indexOf(target);
  const provisional = route === "SELF_CARE_PROVISIONAL";
  const n = ROUTE_LADDER.length;

  return (
    <figure aria-label={t("ladderLabel")} className="relative">
      {/* track runs between the first and last dot centres (10% in from each side) */}
      <div aria-hidden className="absolute inset-x-[10%] top-[15px] h-0.5 rounded-full bg-line">
        <motion.div
          className="absolute inset-y-0 start-0 origin-left rounded-full bg-saffron"
          style={{ width: `${(k / (n - 1)) * 100}%` }}
          initial={{ scaleX: 0 }}
          animate={{ scaleX: 1 }}
          transition={{ delay: 0.3, duration: 1, ease: [0.65, 0, 0.35, 1] }}
        />
      </div>

      <ol className="relative grid grid-cols-5">
        {ROUTE_LADDER.map((r) => {
          const mine = r === target;
          return (
            <li key={r} className="flex flex-col items-center gap-3 text-center sm:gap-4" aria-current={mine ? "step" : undefined}>
              <span className="relative grid size-8 place-items-center">
                {mine ? (
                  <>
                    <motion.span
                      className={`absolute inset-0 rounded-full ${
                        provisional ? "border-2 border-dashed border-pine bg-mist" : "bg-pine"
                      }`}
                      initial={{ scale: 0 }}
                      animate={{ scale: 1 }}
                      transition={{ delay: 1.15, type: "spring", stiffness: 420, damping: 18 }}
                    />
                    <motion.span
                      aria-hidden
                      className="absolute inset-0 rounded-full ring-2 ring-pine"
                      initial={{ scale: 1, opacity: 0 }}
                      animate={{ scale: [1, 2], opacity: [0.45, 0] }}
                      transition={{ delay: 1.3, duration: 1, ease: "easeOut" }}
                    />
                  </>
                ) : (
                  <span className="size-2.5 rounded-full bg-mist ring-2 ring-line" />
                )}
              </span>
              <motion.span
                className={mine ? "text-sm font-medium text-ink sm:text-base" : "text-xs text-muted sm:text-sm"}
                initial={mine ? { opacity: 0, y: 4 } : false}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 1.2 }}
              >
                {L(ROUTE_TEXT[r].short)}
              </motion.span>
            </li>
          );
        })}
      </ol>
    </figure>
  );
}
