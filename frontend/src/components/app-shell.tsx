"use client";

import Link from "next/link";
import { createContext, useContext, useEffect, useId, useRef, useState, useSyncExternalStore, type ReactNode } from "react";
import { isTauri } from "@tauri-apps/api/core";

import { BookIcon, ChatIcon, DocumentIcon, FolderIcon, OpenBookIcon, SearchIcon, SettingsIcon, ShelfIcon, SidebarIcon } from "@/components/icons";
import { OPEN_AI_SETTINGS_EVENT, OPEN_SETUP_GUIDE_EVENT, TOGGLE_NAVIGATION_EVENT } from "@/lib/ai-settings";
import { setSidebarCollapsed, useSidebarCollapsed } from "@/lib/workspace-preferences";

const NAV = [
  { group: "Workspace", items: [{ label: "Chat", Icon: ChatIcon, href: "/chat" }, { label: "Search", Icon: SearchIcon, href: "/search" }] },
  { group: "Knowledge", items: [{ label: "Library", Icon: ShelfIcon, href: "/library" }, { label: "Folders", Icon: FolderIcon, href: "/folders" }, { label: "Wiki", Icon: OpenBookIcon, href: "/wiki" }, { label: "Documents", Icon: DocumentIcon, href: "/documents" }] },
];

const WorkspaceLayout = createContext({ readingFocus: false, setReadingFocus: (value: boolean) => { void value; } });
export const useWorkspaceLayout = () => useContext(WorkspaceLayout);
const subscribeDesktop = () => () => {};
const desktopSnapshot = () => isTauri();
const wideSnapshot = () => window.matchMedia?.("(min-width: 768px)").matches ?? true;
const subscribeWide = (callback: () => void) => {
  const query = window.matchMedia?.("(min-width: 768px)");
  query?.addEventListener("change", callback);
  return () => query?.removeEventListener("change", callback);
};

interface AppShellProps {
  children: ReactNode;
  current: string;
  title?: ReactNode;
  description?: ReactNode;
  actions?: ReactNode;
  passageCount?: number;
  fileCount?: number;
  workspace?: boolean;
  sidebar?: ReactNode;
}

export function AppShell({ children, current, title, description, actions, passageCount, fileCount, workspace = false, sidebar }: AppShellProps) {
  const collapsed = useSidebarCollapsed();
  const desktop = useSyncExternalStore(subscribeDesktop, desktopSnapshot, () => false);
  const wide = useSyncExternalStore(subscribeWide, wideSnapshot, () => true);
  const [navigationOpen, setNavigationOpen] = useState(false);
  const [readingFocus, setReadingFocus] = useState(false);
  const navigationId = useId();
  const menuRef = useRef<HTMLButtonElement>(null);
  const navigationRef = useRef<HTMLElement>(null);
  const closeNavigation = () => { setNavigationOpen(false); menuRef.current?.focus(); };
  const toggleNavigation = () => {
    if (readingFocus) setReadingFocus(false);
    else if (wide) setSidebarCollapsed(!collapsed);
    else setNavigationOpen(!navigationOpen);
  };
  useEffect(() => {
    window.addEventListener(TOGGLE_NAVIGATION_EVENT, toggleNavigation);
    return () => window.removeEventListener(TOGGLE_NAVIGATION_EVENT, toggleNavigation);
  });
  useEffect(() => {
    if (!wide && navigationOpen) {
      const navigation = navigationRef.current;
      (navigation?.querySelector<HTMLElement>('a[aria-current="page"]') ?? navigation?.querySelector<HTMLElement>("a"))?.focus();
      const escape = (event: KeyboardEvent) => {
        if (event.key === "Escape") { setNavigationOpen(false); menuRef.current?.focus(); }
      };
      window.addEventListener("keydown", escape);
      return () => window.removeEventListener("keydown", escape);
    }
  }, [wide, navigationOpen]);
  const navigationLabel = readingFocus ? "Exit focus view" : wide
    ? collapsed ? "Expand navigation" : "Collapse navigation"
    : navigationOpen ? "Close navigation" : "Open navigation";

  return <WorkspaceLayout.Provider value={{ readingFocus, setReadingFocus }}>
    <div className="noye-app-shell" data-reading-focus={readingFocus}>
      <aside ref={navigationRef} id={navigationId} className="noye-sidebar" aria-label="Workspace navigation"
        data-collapsed={wide && collapsed} data-mobile-open={!wide && navigationOpen}
        onClick={event => { if (!wide && navigationOpen && event.target instanceof Element && event.target.closest("a, [data-navigation]")) closeNavigation(); }}
        onKeyDown={event => { if (!wide && navigationOpen && event.key === "Escape") closeNavigation(); }}>
        <Link href="/chat" className="noye-brand-link" aria-label="Noye home">
          <BookIcon className="h-5 w-5 shrink-0 text-brand" /><span className="noye-nav-label font-display text-[23px]">Noye</span>
        </Link>
        <nav aria-label="Sections">
          {NAV.map(group => <div key={group.group}>
            <p className="noye-nav-group">{group.group}</p>
            <ul>{group.items.map(({ label, Icon, href }) => <li key={label}>
              <Link href={href} aria-label={label} title={collapsed ? label : undefined} aria-current={label === current ? "page" : undefined} className="noye-nav-link">
                <Icon className="h-4 w-4 shrink-0" /><span className="noye-nav-label">{label}</span>
              </Link>
            </li>)}</ul>
          </div>)}
        </nav>
        {sidebar && <div className="noye-sidebar-content">{sidebar}</div>}
        <div className="noye-sidebar-footer">
          {passageCount !== undefined && <p className="noye-sidebar-meta noye-meta mb-2 px-2"><span className="tabular-nums">{passageCount.toLocaleString()}</span> passages · {fileCount} {fileCount === 1 ? "file" : "files"}</p>}
          {desktop && <>
            <button type="button" className="noye-button" aria-label="AI setup" data-navigation onClick={event => { event.currentTarget.focus(); window.dispatchEvent(new Event(OPEN_SETUP_GUIDE_EVENT)); }}>
              <OpenBookIcon className="h-4 w-4 shrink-0" /><span className="noye-nav-label">AI setup</span>
            </button>
            <button type="button" className="noye-button" aria-label="Settings" title="Settings · ⌘," data-navigation onClick={event => { event.currentTarget.focus(); window.dispatchEvent(new Event(OPEN_AI_SETTINGS_EVENT)); }}>
              <SettingsIcon className="h-4 w-4 shrink-0" /><span className="noye-nav-label">Settings</span>
            </button>
          </>}
          <p className="noye-sidebar-meta noye-meta px-2 pt-2">Local-first workspace</p>
        </div>
      </aside>
      <main className="noye-shell-main">
        <header className="noye-shell-header">
          <button ref={menuRef} type="button" onClick={toggleNavigation} className="noye-button" aria-label={navigationLabel} title={navigationLabel}
            aria-expanded={readingFocus ? false : wide ? !collapsed : navigationOpen} aria-controls={navigationId}>
            <SidebarIcon className="h-4 w-4" />
          </button>
          <div className="noye-shell-heading"><h1>{title ?? current}</h1>{description && <p className="noye-shell-description">{description}</p>}</div>
          {actions && <div className="noye-shell-actions">{actions}</div>}
        </header>
        <div className="noye-shell-body" data-workspace={workspace}>{children}</div>
      </main>
    </div>
  </WorkspaceLayout.Provider>;
}
