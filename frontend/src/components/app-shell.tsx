import type { ReactNode } from "react";

import {
  BookIcon,
  ChatIcon,
  DocumentIcon,
  SearchIcon,
  ShelfIcon,
} from "@/components/icons";

/**
 * The application shell: a sidebar naming the product's whole shape, and the
 * page beside it.
 *
 * Chat and Documents are shown as forthcoming rather than hidden, so the
 * library does not read as the entire product. They are `aria-disabled` links
 * without an `href`, which keeps them out of the tab order without pretending
 * they are ordinary text.
 *
 * Below 768px the sidebar becomes a horizontal strip above the content, so the
 * page works down to 390px without side-scrolling (DESIGN.md §9).
 */

const NAV = [
  { label: "Library", Icon: ShelfIcon, href: "/library", soon: false },
  { label: "Search", Icon: SearchIcon, href: "/search", soon: false },
  { label: "Chat", Icon: ChatIcon, href: "/chat", soon: false },
  { label: "Documents", Icon: DocumentIcon, href: "/documents", soon: true },
] as const;

interface AppShellProps {
  children: ReactNode;
  /** Which nav item is the current page. */
  current: string;
  /** Total indexed passages, shown in the sidebar meter. Omit while unknown. */
  passageCount?: number;
  fileCount?: number;
}

export function AppShell({ children, current, passageCount, fileCount }: AppShellProps) {
  return (
    <div className="flex min-h-full flex-col md:flex-row">
      <aside className="flex shrink-0 flex-col gap-6 border-edge-strong bg-sunken px-3 py-4 md:w-[238px] md:border-r md:py-6 border-b md:border-b-0">
        <div className="flex items-center gap-2 px-2">
          <BookIcon className="h-5 w-5 text-brand" />
          <span className="font-display text-xl">Noye</span>
        </div>

        <nav aria-label="Sections">
          <ul className="flex gap-1 overflow-x-auto md:flex-col md:overflow-visible">
            {NAV.map(({ label, Icon, href, soon }) => {
              const isCurrent = label === current;
              const shared =
                "flex min-h-11 items-center gap-3 whitespace-nowrap rounded-md px-3 text-sm";
              if (soon) {
                return (
                  <li key={label}>
                    <span
                      aria-disabled="true"
                      className={`${shared} text-ink-faint`}
                      title={`${label} is not built yet`}
                    >
                      <Icon className="h-4 w-4 shrink-0" />
                      {label}
                      {/* Visible at every width: below md this used to be
                          hidden, leaving a greyed-out item with no explanation
                          for why it does nothing. */}
                      <span className="ml-auto text-[10px] tracking-widest">SOON</span>
                    </span>
                  </li>
                );
              }
              return (
                <li key={label}>
                  <a
                    href={href}
                    aria-current={isCurrent ? "page" : undefined}
                    className={`${shared} ${
                      isCurrent
                        ? "bg-canvas font-semibold text-ink shadow-[inset_2.5px_0_0_var(--brand)]"
                        : "text-ink-soft hover:bg-canvas hover:text-ink"
                    }`}
                  >
                    <Icon
                      className={`h-4 w-4 shrink-0 ${isCurrent ? "text-brand" : ""}`}
                    />
                    {label}
                  </a>
                </li>
              );
            })}
          </ul>
        </nav>

        {passageCount !== undefined && (
          <div className="mt-auto hidden rounded-lg border border-edge-strong bg-canvas px-3 py-3 md:block">
            <p className="font-display text-[22px] leading-tight">
              <span className="font-mono text-accent-ink tabular-nums">
                {passageCount.toLocaleString()}
              </span>{" "}
              <span className="text-ink">searchable passages</span>
            </p>
            <p className="text-xs text-ink-soft">
              indexed across {fileCount} {fileCount === 1 ? "file" : "files"}
            </p>
          </div>
        )}
      </aside>

      <main className="min-w-0 flex-1 px-5 py-6 md:px-9 md:py-7">{children}</main>
    </div>
  );
}
