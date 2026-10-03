"use client";

import Link from "next/link";
import { useId, useRef, useState, type ReactNode } from "react";

import { BookIcon, ChatIcon, DocumentIcon, SearchIcon, ShelfIcon } from "@/components/icons";

const NAV = [
  { label: "Chat", Icon: ChatIcon, href: "/chat" },
  { label: "Library", Icon: ShelfIcon, href: "/library" },
  { label: "Search", Icon: SearchIcon, href: "/search" },
  { label: "Documents", Icon: DocumentIcon, href: "/documents" },
] as const;

interface AppShellProps {
  children: ReactNode;
  current: string;
  passageCount?: number;
  fileCount?: number;
  /** A viewport-sized workspace with its own scrolling conversation. */
  workspace?: boolean;
  sidebar?: ReactNode;
}

export function AppShell({ children, current, passageCount, fileCount, workspace = false, sidebar }: AppShellProps) {
  const [navigationOpen, setNavigationOpen] = useState(false);
  const navigationId = useId();
  const menuRef = useRef<HTMLButtonElement>(null);
  const closeNavigation = () => { setNavigationOpen(false); menuRef.current?.focus(); };

  return (
    <div className={`flex flex-col md:flex-row ${workspace ? "min-h-0 flex-1" : "min-h-full"}`}>
      <aside className={`noye-sidebar flex shrink-0 flex-col border-b border-edge-strong bg-sunken px-3 py-3 md:w-[260px] md:border-r md:border-b-0 md:py-5 ${workspace ? "min-h-0" : "gap-6"}`}>
        <div className="flex items-center justify-between gap-2 px-2">
          <Link href="/chat" className="flex min-h-11 items-center gap-2.5" aria-label="Noye home">
            <BookIcon className="h-5 w-5 text-brand" />
            <span className="font-display text-[24px]">Noye</span>
          </Link>
          {workspace && (
            <button ref={menuRef} type="button" aria-expanded={navigationOpen} aria-controls={navigationId}
              onClick={() => setNavigationOpen(!navigationOpen)}
              className="min-h-11 rounded-md border border-edge-strong px-3 text-sm text-ink md:hidden">
              {navigationOpen ? "Close menu" : "Menu & chats"}
            </button>
          )}
        </div>

        <div id={navigationId}
          onClick={(event) => { if (navigationOpen && event.target instanceof Element && event.target.closest("a, [data-navigation]")) closeNavigation(); }}
          onKeyDown={(event) => { if (navigationOpen && event.key === "Escape") closeNavigation(); }}
          className={workspace
          ? `${navigationOpen ? "flex" : "hidden"} max-h-[50dvh] min-h-0 flex-col gap-5 overflow-y-auto pt-3 md:flex md:max-h-none md:flex-1`
          : "flex flex-col gap-6"}>
          <nav aria-label="Sections">
            <ul className={`flex gap-1 ${workspace ? "flex-col" : "overflow-x-auto md:flex-col md:overflow-visible"}`}>
              {NAV.map(({ label, Icon, href }) => (
                <li key={label}>
                  <Link href={href} aria-current={label === current ? "page" : undefined}
                    className={`flex min-h-11 items-center gap-3 whitespace-nowrap rounded-md px-3 text-sm ${label === current
                      ? "bg-canvas font-semibold text-ink shadow-[inset_2.5px_0_0_var(--brand)]"
                      : "text-ink-soft hover:bg-canvas hover:text-ink"}`}>
                    <Icon className={`h-4 w-4 shrink-0 ${label === current ? "text-brand" : ""}`} />
                    {label}
                  </Link>
                </li>
              ))}
            </ul>
          </nav>
          {sidebar && <div className="min-h-0 md:flex-1 md:overflow-y-auto">{sidebar}</div>}
          {workspace && <p className="hidden border-t border-edge-strong px-2 pt-3 text-xs leading-relaxed text-ink-soft md:block">Your files stay on this machine.<br />Cloud AI is always your choice.</p>}
        </div>

        {passageCount !== undefined && (
          <div className="mt-auto hidden rounded-lg border border-edge-strong bg-canvas px-3 py-3 md:block">
            <p className="font-display text-[22px] leading-tight">
              <span className="font-mono text-accent-ink tabular-nums">{passageCount.toLocaleString()}</span>{" "}
              <span className="text-ink">searchable passages</span>
            </p>
            <p className="text-xs text-ink-soft">indexed across {fileCount} {fileCount === 1 ? "file" : "files"}</p>
          </div>
        )}
      </aside>
      <main className={`min-w-0 flex-1 ${workspace ? "flex min-h-0 flex-col" : "px-5 py-6 md:px-9 md:py-7"}`}>{children}</main>
    </div>
  );
}
