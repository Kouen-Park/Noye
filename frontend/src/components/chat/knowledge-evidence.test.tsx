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
