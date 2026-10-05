import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { SavedEvidence } from "@/components/saved-evidence";
import { type ChatCitation, readSourceStatus } from "@/lib/api";

vi.mock("@/lib/api", async (importOriginal) => ({
  ...await importOriginal<typeof import("@/lib/api")>(), readSourceStatus: vi.fn(),
}));

const citation: ChatCitation = {
  file_id: "f1", file_name: "One.md", page_number: null, chunk_indexes: [2], score: 0.9,
  label: "One.md", evidence: {
    version: 1, captured_at: "2026-10-05T00:00:00Z", excerpts: [{
      content: "742 units <script>alert(1)</script>", chunk_index: 2, retrieval_rank: 1,
      score: 0.9, source_hash: "a".repeat(64), index_fingerprint: null, index_metadata: null,
    }],
  },
};

describe("SavedEvidence", () => {
  beforeEach(() => vi.resetAllMocks());

  it("shows saved text safely without querying today's index or file", () => {
    const { container } = render(<SavedEvidence citation={citation} />);
    expect(screen.getByText(citation.evidence!.excerpts[0].content)).toBeVisible();
    expect(container.querySelector("script")).toBeNull();
    expect(readSourceStatus).not.toHaveBeenCalled();
  });

  it.each([
    [{ status: "missing", current_hash: null }, /original missing/i],
    [{ status: "unavailable", current_hash: null }, /could not be checked/i],
    [{ status: "available", current_hash: "b".repeat(64) }, /original changed/i],
    [{ status: "available", current_hash: "a".repeat(64) }, /matches the saved/i],
  ] as const)("compares current originals only on request: %s", async (result, label) => {
    vi.mocked(readSourceStatus).mockResolvedValue(result);
    render(<SavedEvidence citation={citation} />);
    await userEvent.click(screen.getByRole("button", { name: "Check original" }));
    expect(await screen.findByRole("status")).toHaveTextContent(label);
    expect(screen.getByText(citation.evidence!.excerpts[0].content)).toBeVisible();
  });

  it("identifies legacy references without presenting reconstructed text", () => {
    render(<SavedEvidence citation={{ ...citation, evidence: null }} />);
    expect(screen.getByText(/no excerpt was saved/i)).toBeVisible();
    expect(screen.queryByRole("blockquote")).not.toBeInTheDocument();
    expect(readSourceStatus).not.toHaveBeenCalled();
  });

  it("does not label an unknown source revision as unchanged", async () => {
    vi.mocked(readSourceStatus).mockResolvedValue({ status: "available", current_hash: "a".repeat(64) });
    render(<SavedEvidence citation={{ ...citation, evidence: {
      ...citation.evidence!, excerpts: [{ ...citation.evidence!.excerpts[0], source_hash: null }],
    } }} />);
    await userEvent.click(screen.getByRole("button", { name: "Check original" }));
    expect(await screen.findByRole("status")).toHaveTextContent(/version was not recorded/i);
  });
});
