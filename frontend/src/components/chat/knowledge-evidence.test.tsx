import { render, screen } from "@testing-library/react";
import { expect, it } from "vitest";
import { KnowledgeEvidence, type KnowledgeSnapshot } from "./knowledge-evidence";

const snapshot: KnowledgeSnapshot = { version: 1, scope: { mode: "chosen", source_ids: ["s1"] },
  wiki_state: "matched", warnings: [], insufficient_evidence: false,
  wiki_pages: [{ wiki_id: "w1", revision_id: "r1", title: "Reservoir", kind: "project", origin: "user",
    interpretation: "My interpretation: 999.", source_ids: ["s1"], revision_status: "superseded" }] };

it("links the captured Wiki revision within the original chosen scope and labels interpretation", () => {
  render(<KnowledgeEvidence snapshot={snapshot} citations={[]} />);
  const url = new URL(screen.getByRole("link", { name: "Reservoir · project" }).getAttribute("href")!, "http://localhost");
  expect(url.searchParams.get("revision")).toBe("r1");
  expect(JSON.parse(url.searchParams.get("scope")!)).toEqual({ mode: "chosen", source_ids: ["s1"], root_ids: [] });
  expect(screen.getByText(/Wiki is interpretation/)).toBeInTheDocument();
  expect(screen.getByText(/saved interpretation · superseded/)).toBeInTheDocument();
  expect(screen.getByText("Original passages consulted")).toBeInTheDocument();
});

it("explains Wiki fallback and insufficient evidence without presenting a Wiki as fact", () => {
  render(<KnowledgeEvidence snapshot={{ ...snapshot, wiki_pages: [], insufficient_evidence: true,
    wiki_state: "unavailable", warnings: ["Wiki discovery failed; using verified original passages."] }} citations={[]} />);
  expect(screen.getByText(/No usable original evidence/)).toBeInTheDocument();
  expect(screen.getByText(/Wiki discovery failed/)).toBeInTheDocument();
});

for (const originalScope of [
  { mode: "all" as const },
  { mode: "chosen" as const, root_ids: ["root-one"] },
]) {
  it(`freezes ${JSON.stringify(originalScope)} navigation to the captured inventory`, () => {
    render(<KnowledgeEvidence snapshot={{ ...snapshot, scope: originalScope,
      manifest: [{ source_id: "s1" }, { source_id: "s2" }],
      wiki_pages: [{ ...snapshot.wiki_pages[0], contributors: [{ wiki_id: "w2" }],
        interpretation: "[Related original](../sources/w2.md)" }] }} citations={[]} />);
    const link = screen.getByRole("link", { name: "Reservoir · project" });
    const url = new URL(link.getAttribute("href")!, "http://localhost");
    expect(JSON.parse(url.searchParams.get("scope")!)).toEqual({
      mode: "chosen", source_ids: ["s1", "s2"], root_ids: [],
    });
    const related = new URL(screen.getByRole("link", { name: "Related original" }).getAttribute("href")!, "http://localhost");
    expect(related.searchParams.get("scope")).toBe(url.searchParams.get("scope"));
  });
}

it("keeps an older all-scope snapshot limited to its captured Wiki sources", () => {
  render(<KnowledgeEvidence snapshot={{ ...snapshot, scope: { mode: "all" } }} citations={[]} />);
  const url = new URL(screen.getByRole("link", { name: "Reservoir · project" }).getAttribute("href")!, "http://localhost");
  expect(JSON.parse(url.searchParams.get("scope")!)).toEqual({
    mode: "chosen", source_ids: ["s1"], root_ids: [],
  });
});

it("rewrites inline, reference and autolink Wiki navigation without changing the saved interpretation", () => {
  const interpretation = "[Inline](/wiki/?w=basis&scope=all&revision=newer)\n\n[Reference][ref]\n\n[ref]: /wiki/?w=basis\n\n<http://localhost:3000/wiki/?w=basis>\n\n[Unknown](../sources/unknown.md)";
  const saved = { ...snapshot, manifest: [{ source_id: "s1" }], wiki_pages: [{ ...snapshot.wiki_pages[0],
    contributors: [{ wiki_id: "basis", revision_id: "original-revision" }], interpretation }] };
  render(<KnowledgeEvidence snapshot={saved} citations={[]} />);
  for (const name of ["Inline", "Reference", "http://localhost:3000/wiki/?w=basis"]) {
    const target = new URL(screen.getByRole("link", { name }).getAttribute("href")!, "http://localhost");
    expect(JSON.parse(target.searchParams.get("scope")!)).toEqual({ mode: "chosen", source_ids: ["s1"], root_ids: [] });
    expect(target.searchParams.get("revision")).toBe("original-revision");
  }
  expect(screen.queryByRole("link", { name: "Unknown" })).not.toBeInTheDocument();
  expect(screen.getByText("Unknown")).toBeInTheDocument();
  expect(saved.wiki_pages[0].interpretation).toBe(interpretation);
});
