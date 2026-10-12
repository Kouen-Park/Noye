/**
 * Inline icons.
 *
 * Every icon is `aria-hidden`: status meaning is carried by the adjacent word
 * (DESIGN.md §3), so an icon that also announced itself would read twice. An
 * icon used without a visible label needs an `aria-label` on its control, not
 * here.
 */

type IconProps = { className?: string };

const base = {
  viewBox: "0 0 24 24",
  fill: "none",
  stroke: "currentColor",
  strokeLinecap: "round" as const,
  strokeLinejoin: "round" as const,
  "aria-hidden": true,
  focusable: false,
};

export function BookIcon({ className }: IconProps) {
  return (
    <svg {...base} strokeWidth={1.7} className={className}>
      <path d="M4 4.5A1.5 1.5 0 0 1 5.5 3H11v18H5.5A1.5 1.5 0 0 1 4 19.5z" />
      <path d="M20 4.5A1.5 1.5 0 0 0 18.5 3H13v18h5.5A1.5 1.5 0 0 0 20 19.5z" />
    </svg>
  );
}

export function ShelfIcon({ className }: IconProps) {
  return (
    <svg {...base} strokeWidth={1.8} className={className}>
      <path d="M4 5h16M4 12h16M4 19h10" />
    </svg>
  );
}

export function SearchIcon({ className }: IconProps) {
  return (
    <svg {...base} strokeWidth={1.8} className={className}>
      <circle cx="11" cy="11" r="7" />
      <path d="M20 20l-4-4" />
    </svg>
  );
}

export function ChatIcon({ className }: IconProps) {
  return (
    <svg {...base} strokeWidth={1.8} className={className}>
      <path d="M21 12a8 8 0 1 1-3.2-6.4L21 5v7z" />
    </svg>
  );
}

export function DocumentIcon({ className }: IconProps) {
  return (
    <svg {...base} strokeWidth={1.8} className={className}>
      <path d="M7 3h7l5 5v13H7z" />
      <path d="M14 3v5h5" />
    </svg>
  );
}

export function PlusIcon({ className }: IconProps) {
  return (
    <svg {...base} strokeWidth={2.2} className={className}>
      <path d="M12 5v14M5 12h14" />
    </svg>
  );
}

export function FolderIcon({ className }: IconProps) {
  return <svg {...base} strokeWidth={1.8} className={className}>
    <path d="M3 7V5h6l2 2h10v13H3z" />
  </svg>;
}

export function OpenBookIcon({ className }: IconProps) {
  return <svg {...base} strokeWidth={1.8} className={className}>
    <path d="M12 5c-3-2-6-2-9-1v15c3-1 6-1 9 1 3-2 6-2 9-1V4c-3-1-6-1-9 1zM12 5v15" />
  </svg>;
}

export function SidebarIcon({ className }: IconProps) {
  return <svg {...base} strokeWidth={1.8} className={className}>
    <rect x="3" y="4" width="18" height="16" rx="2" /><path d="M9 4v16" />
  </svg>;
}

export function SettingsIcon({ className }: IconProps) {
  return <svg {...base} strokeWidth={1.8} className={className}>
    <path d="M4 7h16M4 17h16" /><circle cx="9" cy="7" r="3" fill="var(--sunken)" /><circle cx="15" cy="17" r="3" fill="var(--sunken)" />
  </svg>;
}

export function CheckIcon({ className }: IconProps) {
  return (
    <svg {...base} strokeWidth={2.6} className={className}>
      <path d="M5 13l4 4L19 7" />
    </svg>
  );
}

export function CrossIcon({ className }: IconProps) {
  return (
    <svg {...base} strokeWidth={2.5} className={className}>
      <path d="M6 6l12 12M18 6L6 18" />
    </svg>
  );
}
