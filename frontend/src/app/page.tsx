"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

/**
 * Client navigation also works in the packaged static export, where there is
 * no Next server to perform a redirect.
 */
export default function Home() {
  const router = useRouter();
  useEffect(() => { router.replace("/chat/"); }, [router]);
  return <p className="p-6 text-ink-soft" role="status">Opening your workspace…</p>;
}
