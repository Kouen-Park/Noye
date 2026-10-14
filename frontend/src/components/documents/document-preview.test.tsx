import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { DocumentPreview } from "@/components/documents/document-preview";

describe("DocumentPreview", () => {
  it("renders Markdown structure as real elements", () => {
    render(<DocumentPreview content={"# Heading\n\n- one\n- two\n\n**bold**"} />);
    expect(screen.getByRole("heading", { level: 1, name: "Heading" })).toBeInTheDocument();
    expect(screen.getAllByRole("listitem")).toHaveLength(2);
    expect(screen.getByText("bold").tagName).toBe("STRONG");
  });

  it("renders GFM tables, which the plugin is there for", () => {
    render(<DocumentPreview content={"| a | b |\n| --- | --- |\n| 1 | 2 |"} />);
    expect(screen.getByRole("table")).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "a" })).toBeInTheDocument();
  });

  it("does NOT render raw HTML", () => {
    // The whole reason for react-markdown over a string-to-HTML renderer: the
    // content is model-generated, user-edited, and derived from the user's own
    // files, so a script tag could reach here by way of an ingested PDF.
    const { container } = render(
      <DocumentPreview
        content={'<script>window.pwned = 1</script><img src=x onerror="alert(1)">'}
      />,
    );
    expect(container.querySelector("script")).toBeNull();
    expect(container.querySelector("img")).toBeNull();
  });

  it("shows raw HTML as text rather than swallowing it", () => {
    // Silently dropping it would leave someone wondering where their line went.
    render(<DocumentPreview content={"<b>not bold</b>"} />);
    expect(screen.getByText(/not bold/)).toBeInTheDocument();
  });

  it("marks itself as the printable document", () => {
    // The print stylesheet hides everything without this, so a missing attribute
    // would export a blank page.
    const { container } = render(<DocumentPreview content="# Notes" />);
    expect(container.querySelector('[data-print="document"]')).not.toBeNull();
  });

  it("invites writing when there is nothing to preview", () => {
    render(<DocumentPreview content="   " />);
    expect(screen.getByText(/nothing to preview yet/i)).toBeInTheDocument();
  });

  it("opens links safely in a new tab", () => {
    render(<DocumentPreview content="[link](https://example.com)" />);
    const link = screen.getByRole("link", { name: "link" });
    expect(link).toHaveAttribute("target", "_blank");
    expect(link.getAttribute("rel")).toContain("noopener");
  });

  it("preserves consecutive headings, paragraphs, lists, code and quoted originals when grouping for print", () => {
    render(<DocumentPreview content={
      "# Title\n\nIntro 한국어.\n\n## Conditions\n\nSaturday is **read-only**.\n\n" +
      "## Counts\n\n- 37 litres capacity\n- 92 litres stored\n\n" +
      "### Original\n\n> Exact original -- quote.\n\n## Next\n\n## Last\n\n```\nliteral ->\n```"
    } />);
    expect(screen.getAllByRole("heading").map(h => h.textContent)).toEqual(
      ["Title", "Conditions", "Counts", "Original", "Next", "Last"]);
    expect(screen.getByText("Intro 한국어.")).toBeInTheDocument();
    expect(screen.getByText("read-only")).toBeInTheDocument();
    expect(screen.getAllByRole("listitem").map(li => li.textContent)).toEqual(
      ["37 litres capacity", "92 litres stored"]);
    expect(screen.getByText("Exact original -- quote.")).toBeInTheDocument();
    expect(screen.getByText("literal ->")).toBeInTheDocument();
  });
});
