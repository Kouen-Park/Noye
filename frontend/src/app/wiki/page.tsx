import { Suspense } from "react";
import { AppShell } from "@/components/app-shell";
import { WikiView } from "@/components/wiki/wiki-view";

export default function WikiPage() {
  return <AppShell current="Wiki"><h1 className="text-[27px]">Wiki</h1><p className="mt-1 max-w-[70ch] text-ink-soft">Source summaries, related knowledge and writing you can keep. Generated updates preserve your edits as separate revisions.</p><Suspense fallback={<p role="status">Opening Wiki…</p>}><WikiView /></Suspense></AppShell>;
}
