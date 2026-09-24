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
});
