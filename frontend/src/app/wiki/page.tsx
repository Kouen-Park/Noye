import { Suspense } from "react";
import { AppShell } from "@/components/app-shell";
import { WikiView } from "@/components/wiki/wiki-view";

export default function WikiPage() {
  return <AppShell current="Wiki" title="Wiki" description="Source summaries and writing, with original evidence." workspace><Suspense fallback={<p role="status" className="p-4 text-ink-soft">Opening Wiki…</p>}><WikiView /></Suspense></AppShell>;
}
