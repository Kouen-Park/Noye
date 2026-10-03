"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

/**
 * Client navigation also works in the packaged static export, where there is
 * no Next server to perform a redirect. Chat-first navigation follows later.
 */
export default function Home() {
  const router = useRouter();
  useEffect(() => { router.replace("/library/"); }, [router]);
  return <p className="p-6 text-ink-soft" role="status">Opening your library…</p>;
}
