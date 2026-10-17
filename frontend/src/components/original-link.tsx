"use client";

import { invoke, isTauri } from "@tauri-apps/api/core";
import { useId, useRef, useState, useSyncExternalStore, type HTMLAttributes } from "react";
import { apiBaseUrl } from "@/lib/runtime";

/** Only original-source API URLs use the native bridge; Markdown cannot grant
 * general shell access or navigate to another local service. */
export function isOriginalHref(href: string) {
  try {
    const url = new URL(href, apiBaseUrl());
    return url.origin === new URL(apiBaseUrl()).origin
      && /^\/files\/[^/]+\/source$/.test(url.pathname)
      && !url.search;
  } catch { return false; }
}

const subscribeDesktop = () => () => {};
const desktopSnapshot = () => isTauri();

export function OriginalLink({ href, children, onClick, ...props }: HTMLAttributes<HTMLElement> & { href: string }) {
  const desktop = useSyncExternalStore(subscribeDesktop, desktopSnapshot, () => false);
  const [phase, setPhase] = useState<"idle" | "opening" | "sent" | "error">("idle");
  const pending = useRef(false);
  const messageId = useId();
  if (!desktop || !isOriginalHref(href)) {
    return <a {...props} href={href} target="_blank" rel="noopener noreferrer" onClick={onClick}>{children}</a>;
  }
  const message = {
    idle: "",
    opening: "Opening original…",
    sent: "Sent the original to your default browser.",
    error: "Could not open this original. Check its availability and try again.",
  }[phase];
  return <>
    <button {...props} type="button"
      className={`${props.className ?? ""} noye-original-command`}
      disabled={phase === "opening"} aria-busy={phase === "opening"}
      aria-describedby={[props["aria-describedby"], messageId].filter(Boolean).join(" ")}
      onClick={event => {
      onClick?.(event);
      if (event.defaultPrevented || pending.current) return;
      event.preventDefault();
      pending.current = true;
      setPhase("opening");
      void invoke("open_original", { url: new URL(href, apiBaseUrl()).href }).then(() => {
        setPhase("sent");
      }).catch(() => {
        setPhase("error");
      }).finally(() => {
        pending.current = false;
      });
    }}>{children}</button>
    <span id={messageId} role={phase === "error" ? "alert" : "status"}
      className={`noye-original-message ${phase === "idle" ? "sr-only" : "basis-full noye-meta"}${phase === "error" ? " noye-original-error" : ""}`}>{message}</span>
    <a href={href} className="noye-original-print-link" tabIndex={-1}>{children}</a>
  </>;
}
