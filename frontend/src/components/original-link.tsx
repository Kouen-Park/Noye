"use client";

import { invoke, isTauri } from "@tauri-apps/api/core";
import { useState, type AnchorHTMLAttributes } from "react";
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

export function OriginalLink({ href, children, onClick, ...props }: AnchorHTMLAttributes<HTMLAnchorElement> & { href: string }) {
  const [error, setError] = useState<string | null>(null);
  return <>
    <a {...props} href={href} target="_blank" rel="noopener noreferrer" onClick={event => {
      onClick?.(event);
      if (event.defaultPrevented || !isTauri() || !isOriginalHref(href)) return;
      event.preventDefault();
      setError(null);
      void invoke("open_original", { url: new URL(href, apiBaseUrl()).href }).catch(() => {
        setError("Could not open this original. Check its availability and try again.");
      });
    }}>{children}</a>
    {error && <span role="alert" className="noye-original-error basis-full">{error}</span>}
  </>;
}
