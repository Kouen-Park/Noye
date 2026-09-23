import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { Passages } from "@/components/chat/passages";
import type { ChatCitation } from "@/lib/api";

function citation(overrides: Partial<ChatCitation> = {}): ChatCitation {
  return {
    file_id: "file-1",
    file_name: "Algorithms.pdf",
    page_number: 34,
    chunk_indexes: [5],
    score: 0.68,
    label: "Algorithms.pdf — page 34",
    ...overrides,
  };
}

describe("Passages", () => {
  it("calls them passages consulted, not sources", async () => {
    // Vector search always returns its nearest neighbours, so these are what the
    // model was given — not proof the answer rests on them. Calling them
    // "Sources" would claim support nobody has verified.
    render(<Passages citations={[citation()]} />);
    expect(screen.getByRole("button", { name: /1 passage consulted/i })).toBeInTheDocument();
    expect(screen.queryByText(/^sources$/i)).not.toBeInTheDocument();
  });

  it("pluralises the count", () => {
    render(<Passages citations={[citation(), citation({ page_number: 35 })]} />);
    expect(screen.getByRole("button", { name: /2 passages consulted/i })).toBeInTheDocument();
  });

  it("starts collapsed so an answer reads as prose", () => {
    render(<Passages citations={[citation()]} />);
    expect(screen.getByRole("button")).toHaveAttribute("aria-expanded", "false");
    expect(screen.queryByText("Algorithms.pdf")).not.toBeInTheDocument();
  });

  it("expands to show each passage, because inspection is the point", async () => {
    render(<Passages citations={[citation()]} />);

    await userEvent.click(screen.getByRole("button"));

    expect(screen.getByRole("button")).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByText("Algorithms.pdf")).toBeInTheDocument();
    expect(screen.getByText("page 34")).toBeInTheDocument();
  });

  it("links each passage to its source at the cited page", async () => {
    render(<Passages citations={[citation()]} />);
    await userEvent.click(screen.getByRole("button", { name: /passage/i }));

    const link = screen.getByRole("link", { name: "Open Algorithms.pdf at page 34" });
    expect(link.getAttribute("href")).toContain("/files/file-1/source");
    expect(link.getAttribute("href")).toContain("#page=34");
  });

  it("says a pageless source has no pages and links without a fragment", async () => {
    render(
      <Passages
        citations={[citation({ file_name: "notes.md", page_number: null, label: "notes.md" })]}
      />,
    );
    await userEvent.click(screen.getByRole("button", { name: /passage/i }));

    expect(screen.getByText("no pages")).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "Open notes.md" }).getAttribute("href"),
    ).not.toContain("#page=");
  });

  it("renders nothing when an answer had no passages", () => {
    const { container } = render(<Passages citations={[]} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("does not show the similarity score", () => {
    render(<Passages citations={[citation({ score: 0.6812 })]} />);
    expect(screen.queryByText(/0\.68/)).not.toBeInTheDocument();
  });
});
