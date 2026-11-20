"use client";

import { MotionConfig } from "motion/react";
import { StoreProvider } from "@/lib/store";
import { Shell } from "./shell";

export function Providers({ children }: { children: React.ReactNode }) {
  return (
    <MotionConfig reducedMotion="user" transition={{ duration: 0.45, ease: [0.22, 1, 0.36, 1] }}>
      <StoreProvider>
        <Shell>{children}</Shell>
      </StoreProvider>
    </MotionConfig>
  );
}
