import { useSyncExternalStore } from "react";

const key = "noye:sidebar-collapsed";
const listeners = new Set<() => void>();
let collapsed: boolean | null = null;

function snapshot() {
  if (collapsed === null) {
    try { collapsed = window.localStorage.getItem(key) === "true"; }
    catch { collapsed = false; }
  }
  return collapsed;
}

function subscribe(listener: () => void) {
  listeners.add(listener);
  const storage = (event: StorageEvent) => {
    if (event.key === key || event.key === null) {
      collapsed = null;
      listeners.forEach(notify => notify());
    }
  };
  window.addEventListener("storage", storage);
  return () => { listeners.delete(listener); window.removeEventListener("storage", storage); };
}

export function setSidebarCollapsed(value: boolean) {
  collapsed = value;
  try { window.localStorage.setItem(key, String(value)); }
  catch { /* Layout stays usable when persistence is unavailable. */ }
  listeners.forEach(notify => notify());
}

export function useSidebarCollapsed() {
  return useSyncExternalStore(subscribe, snapshot, () => false);
}
