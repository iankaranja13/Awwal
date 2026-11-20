"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useId, useRef, useState } from "react";
import { AnimatePresence, motion, useDragControls } from "motion/react";
import { Icon } from "./icon";
import { isFlowRoute } from "./nav";

/* ---------- Buttons ---------- */

type Variant = "primary" | "quiet" | "alarm";
const btn: Record<Variant, string> = {
  primary:
    "bg-pine px-7 text-paper hover:bg-ink active:scale-[0.985] disabled:bg-line disabled:text-muted disabled:active:scale-100",
  quiet: "px-5 text-pine hover:bg-pine-soft",
  alarm: "bg-alarm px-7 text-white hover:brightness-110 active:scale-[0.985]",
};
const base =
  "inline-flex h-12 items-center justify-center gap-2 rounded-full text-base font-medium transition-[background-color,transform,filter] duration-200 disabled:cursor-not-allowed";

export function Button({
  variant = "primary",
  className = "",
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant }) {
  return <button type="button" className={`${base} ${btn[variant]} ${className}`} {...props} />;
}

export function LinkButton({
  href,
  variant = "primary",
  className = "",
  children,
}: {
  href: string;
  variant?: Variant;
  className?: string;
  children: React.ReactNode;
}) {
  return (
    <Link href={href} className={`${base} ${btn[variant]} ${className}`}>
      {children}
    </Link>
  );
}

export function BackLink({ href, label, onClick }: { href?: string; label: string; onClick?: () => void }) {
  const cls =
    "-ms-2 mb-4 inline-flex h-11 w-fit sm:mb-6 sm:h-10 items-center gap-1 rounded-full pe-3 ps-1 text-sm text-muted transition-colors hover:text-ink";
  const inner = (
    <>
      <Icon name="back" className="size-4" />
      {label}
    </>
  );
  return href ? (
    <Link href={href} className={cls}>
      {inner}
    </Link>
  ) : (
    <button type="button" onClick={onClick} className={cls}>
      {inner}
    </button>
  );
}

/* ---------- Page layout ----------
   Desktop: a split page. The left column holds the heading and the main
   action and stays put; the right column holds the content.
   Narrow windows stack the two. */

export function Page({
  title,
  sub,
  back,
  aside,
  actions,
  children,
}: {
  title: React.ReactNode;
  sub?: React.ReactNode;
  back?: React.ReactNode;
  aside?: React.ReactNode;
  actions?: React.ReactNode;
  children?: React.ReactNode;
}) {
  const flow = isFlowRoute(usePathname());
  return (
    <div className="grid flex-1 gap-8 py-8 sm:gap-12 sm:py-10 lg:grid-cols-12 lg:gap-20 lg:py-16">
      <div className="lg:sticky lg:top-12 lg:col-span-5 lg:self-start">
        {back}
        <h1 className="display text-xl font-light text-ink text-balance md:text-2xl">{title}</h1>
        {sub ? <p className="mt-3 max-w-md text-base text-muted sm:mt-4">{sub}</p> : null}
        {aside}
        {/* Desktop: actions sit under the heading and stay in view */}
        {actions ? <div className="mt-10 hidden flex-wrap items-center gap-3 lg:flex">{actions}</div> : null}
      </div>
      <div className="lg:col-span-7 lg:pt-2">
        {children}
        {/* Phones and tablets: actions come after the content, where the eye ends up.
            Inside the check flow they are pinned to the bottom of the screen. */}
        {actions ? (
          flow ? (
            <>
              <div aria-hidden className="h-32 lg:hidden" />
              <BottomBar>{actions}</BottomBar>
            </>
          ) : (
            <div className="mt-10 flex flex-wrap items-center gap-3 lg:hidden">{actions}</div>
          )
        ) : null}
      </div>
    </div>
  );
}

/** Pinned action bar for phones. The first child is the primary action. */
export function BottomBar({ children, className = "lg:hidden" }: { children: React.ReactNode; className?: string }) {
  return (
    <div
      className={`fixed inset-x-0 bottom-0 z-20 border-t border-line bg-mist/95 px-4 pb-[calc(0.75rem+env(safe-area-inset-bottom))] pt-3 backdrop-blur-md sm:px-6 ${className}`}
    >
      <div className="mx-auto flex max-w-xl flex-col gap-1 [&>*]:w-full">{children}</div>
    </div>
  );
}

/** Section label used inside the content column. */
export function Label({ children }: { children: React.ReactNode }) {
  return <h2 className="mb-2 text-sm text-muted">{children}</h2>;
}

/* ---------- Toggle ---------- */

export function Toggle({
  checked,
  onChange,
  label,
  sub,
  disabled,
  icon,
}: {
  checked: boolean;
  onChange: (v: boolean) => void;
  label: string;
  sub?: string;
  disabled?: boolean;
  icon?: React.ReactNode;
}) {
  const id = useId();
  return (
    <div className="flex items-center gap-4 py-5 sm:gap-6">
      {icon ? (
        <span
          aria-hidden
          className={`grid size-10 shrink-0 place-items-center rounded-full transition-colors duration-300 ${
            checked ? "bg-pine-soft text-pine" : "bg-paper text-muted ring-1 ring-line"
          }`}
        >
          {icon}
        </span>
      ) : null}
      <label htmlFor={id} className="flex-1 cursor-pointer">
        <span className="block text-base text-ink">{label}</span>
        {sub ? <span className="mt-0.5 block text-sm text-muted">{sub}</span> : null}
      </label>
      <button
        id={id}
        type="button"
        role="switch"
        aria-checked={checked}
        disabled={disabled}
        onClick={() => onChange(!checked)}
        className={`relative flex h-7 w-12 shrink-0 cursor-pointer items-center rounded-full p-1 transition-colors duration-300 ${
          checked ? "justify-end bg-pine" : "justify-start bg-line"
        } disabled:opacity-50`}
      >
        <motion.span
          layout
          transition={{ type: "spring", stiffness: 600, damping: 35 }}
          className="block size-5 rounded-full bg-paper shadow-[0_1px_2px_rgba(14,38,36,0.25)]"
        />
      </button>
    </div>
  );
}

/* ---------- Choice chip ---------- */

export function Chip({
  selected,
  onClick,
  children,
  quiet,
}: {
  selected: boolean;
  onClick: () => void;
  children: React.ReactNode;
  quiet?: boolean;
}) {
  return (
    <button
      type="button"
      aria-pressed={selected}
      onClick={onClick}
      className={`relative inline-flex h-11 cursor-pointer items-center gap-1.5 rounded-full sm:h-10 transition-colors duration-200 ${
        quiet ? "px-3 text-sm" : "px-4 text-sm"
      } ${
        selected
          ? "bg-pine text-paper"
          : quiet
            ? "text-muted hover:bg-pine-soft hover:text-ink"
            : "bg-paper text-ink ring-1 ring-line hover:ring-pine/50"
      }`}
    >
      <AnimatePresence initial={false}>
        {selected && (
          <motion.span
            initial={{ width: 0, opacity: 0 }}
            animate={{ width: "auto", opacity: 1 }}
            exit={{ width: 0, opacity: 0 }}
            transition={{ duration: 0.22 }}
            className="inline-flex overflow-hidden"
          >
            <Icon name="check" className="size-4" />
          </motion.span>
        )}
      </AnimatePresence>
      {children}
    </button>
  );
}

/* ---------- Sheet ----------
   Desktop: a drawer from the side. Phones: a sheet from the bottom, in thumb reach. */

function useWide() {
  const [wide, setWide] = useState(true);
  useEffect(() => {
    const m = window.matchMedia("(min-width: 640px)");
    const on = () => setWide(m.matches);
    on();
    m.addEventListener("change", on);
    return () => m.removeEventListener("change", on);
  }, []);
  return wide;
}

export function Sheet({
  open,
  onClose,
  title,
  closeLabel,
  children,
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  closeLabel: string;
  children: React.ReactNode;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const closeRef = useRef(onClose);
  closeRef.current = onClose;
  const titleId = useId();
  const wide = useWide();
  const drag = useDragControls();

  useEffect(() => {
    if (!open) return;
    const prev = document.activeElement as HTMLElement | null;
    ref.current?.focus();
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && closeRef.current();
    window.addEventListener("keydown", onKey);
    document.body.style.overflow = "hidden";
    return () => {
      window.removeEventListener("keydown", onKey);
      document.body.style.overflow = "";
      prev?.focus();
    };
  }, [open]);

  const off = wide ? { x: "100%" } : { y: "100%" };

  return (
    <AnimatePresence>
      {open && (
        <div className="fixed inset-0 z-40 flex items-end justify-end sm:items-stretch">
          <motion.div
            className="absolute inset-0 bg-ink/25"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
          />
          <motion.div
            ref={ref}
            tabIndex={-1}
            role="dialog"
            aria-modal="true"
            aria-labelledby={titleId}
            initial={off}
            animate={{ x: 0, y: 0 }}
            exit={off}
            transition={{ type: "spring", stiffness: 340, damping: 38 }}
            drag={wide ? false : "y"}
            dragControls={drag}
            dragListener={false}
            dragConstraints={{ top: 0, bottom: 0 }}
            dragElastic={{ top: 0, bottom: 0.6 }}
            onDragEnd={(_, info) => {
              if (info.offset.y > 100 || info.velocity.y > 500) onClose();
            }}
            className="relative max-h-[88dvh] w-full overflow-y-auto rounded-t-[1.75rem] bg-paper px-6 pb-[calc(2rem+env(safe-area-inset-bottom))] pt-3 outline-none sm:h-full sm:max-h-none sm:max-w-md sm:rounded-none sm:px-10 sm:py-10"
          >
            <div
              aria-hidden
              onPointerDown={(e) => drag.start(e)}
              className="-mx-6 -mt-3 flex touch-none justify-center pb-4 pt-3 sm:hidden"
            >
              <span className="block h-1 w-10 rounded-full bg-line" />
            </div>
            <div className="mb-6 flex items-center justify-between sm:mb-10">
              <h2 id={titleId} className="text-lg font-normal text-ink">
                {title}
              </h2>
              <button
                type="button"
                onClick={onClose}
                aria-label={closeLabel}
                className="-me-2 grid size-11 cursor-pointer place-items-center rounded-full text-muted hover:bg-mist hover:text-ink sm:size-10"
              >
                <Icon name="close" />
              </button>
            </div>
            {children}
          </motion.div>
        </div>
      )}
    </AnimatePresence>
  );
}

/* ---------- Guard ---------- */

/** Sends the user back if a screen is opened without the state it needs. */
export function useRequire(ok: boolean, to: string) {
  const router = useRouter();
  useEffect(() => {
    if (!ok) router.replace(to);
  }, [ok, to, router]);
  return ok;
}
