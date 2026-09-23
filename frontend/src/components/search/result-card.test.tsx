import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ResultCard } from "@/components/search/result-card";
import type { SearchHit } from "@/lib/api";

function hit(overrides: Partial<SearchHit> = {}): SearchHit {
  return {
    content: "Dijkstra's algorithm takes the smallest estimate from a priority queue.",
    file_id: "file-1",
    file_name: "Algorithms-lecture-07.pdf",
    page_number: 34,
    chunk_index: 5,
    score: 0.68,
    ...overrides,
  };
}

describe("ResultCard", () => {
  it("shows the passage, its file, and its page", () => {
    render(<ResultCard hit={hit()} rank={1} />);
    expect(screen.getByText(/priority queue/)).toBeInTheDocument();
    expect(screen.getByText("Algorithms-lecture-07.pdf")).toBeInTheDocument();
    expect(screen.getByText("page 34")).toBeInTheDocument();
  });

  it("says a pageless source has no pages rather than inventing page 1", () => {
    render(<ResultCard hit={hit({ page_number: null, file_name: "notes.md" })} rank={1} />);
    expect(screen.getByText("no pages")).toBeInTheDocument();
    expect(screen.queryByText(/page 1/)).not.toBeInTheDocument();
  });

  it("links to the source at the cited page", () => {
    render(<ResultCard hit={hit()} rank={1} />);
    const link = screen.getByRole("link", { name: /open/i });
    expect(link).toHaveAttribute("href", expect.stringContaining("/files/file-1/source"));
    expect(link.getAttribute("href")).toContain("#page=34");
  });

  it("links without a page fragment when the format has no pages", () => {
    render(<ResultCard hit={hit({ page_number: null })} rank={1} />);
    expect(screen.getByRole("link", { name: /open/i }).getAttribute("href")).not.toContain(
      "#page=",
    );
  });

  it("names the source in the link, so a list of results is navigable by link", () => {
    render(<ResultCard hit={hit()} rank={1} />);
    expect(
      screen.getByRole("link", { name: "Open Algorithms-lecture-07.pdf at page 34" }),
    ).toBeInTheDocument();
  });

  it("names a pageless source without a page in the link", () => {
    render(<ResultCard hit={hit({ page_number: null, file_name: "notes.md" })} rank={1} />);
    expect(screen.getByRole("link", { name: "Open notes.md" })).toBeInTheDocument();
  });

  it("does not show the similarity score", () => {
    // Similarity is model-dependent and has no user-facing meaning until a
    // threshold is calibrated on real documents, which has not happened.
    render(<ResultCard hit={hit({ score: 0.6812 })} rank={1} />);
    expect(screen.queryByText(/0\.68/)).not.toBeInTheDocument();
  });

  it("shows the rank but hides it from assistive technology", () => {
    // The list order already conveys rank to a screen reader.
    const { container } = render(<ResultCard hit={hit()} rank={3} />);
    const badge = screen.getByText("3");
    expect(badge).toHaveAttribute("aria-hidden", "true");
    expect(container.querySelector("li")).toBeInTheDocument();
  });

  it("opens the source in a new tab safely", () => {
    render(<ResultCard hit={hit()} rank={1} />);
    const link = screen.getByRole("link", { name: /open/i });
    expect(link).toHaveAttribute("target", "_blank");
    expect(link).toHaveAttribute("rel", expect.stringContaining("noopener"));
  });
});
