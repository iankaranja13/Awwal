type Name = "chevron" | "back" | "shield" | "check" | "close" | "phone" | "download" | "trace";

const PATHS: Record<Name, React.ReactNode> = {
  chevron: <path d="M9 6l6 6-6 6" />,
  back: <path d="M15 6l-6 6 6 6" />,
  shield: <path d="M12 3l7 3v5c0 4.5-3 8.3-7 10-4-1.7-7-5.5-7-10V6l7-3z" />,
  check: <path d="M5 12.5l4.5 4.5L19 7.5" />,
  close: <path d="M6 6l12 12M18 6L6 18" />,
  phone: <path d="M5 4h4l2 5-2.5 1.5a11 11 0 005 5L15 13l5 2v4a1 1 0 01-1 1A16 16 0 014 5a1 1 0 011-1z" />,
  download: <path d="M12 4v11m0 0l-4.5-4.5M12 15l4.5-4.5M5 20h14" />,
  trace: <path d="M5 5h.01M5 12h.01M5 19h.01M9 5h10M9 12h10M9 19h10" />,
};

/** Directional icons (chevron, back) get .flip-rtl so they mirror in Arabic. */
export function Icon({ name, className = "size-5", label }: { name: Name; className?: string; label?: string }) {
  const flip = name === "chevron" || name === "back" ? " flip-rtl" : "";
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.6}
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className + flip}
      aria-hidden={label ? undefined : true}
      role={label ? "img" : undefined}
      aria-label={label}
    >
      {PATHS[name]}
    </svg>
  );
}
