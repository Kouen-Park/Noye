import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { StageBar, StatusPill } from "@/components/library/status-indicators";
import { STAGE_COUNT } from "@/lib/status";

describe("StatusPill", () => {
  it("says the state in words, not only in colour", () => {
    // Oxblood and the brand green differ by 1.01:1 in luminance, and red against
    // green is the worst pair for the commonest colour blindness, so the word is
    // the channel that has to carry the meaning.
    render(<StatusPill status="READY" />);
    expect(screen.getByText("Ready")).toBeInTheDocument();
  });

  it("distinguishes a stop from a failure", () => {
    const { unmount } = render(<StatusPill status="FAILED" error="Processing was cancelled." />);
    expect(screen.getByText("Stopped")).toBeInTheDocument();
    unmount();

    render(<StatusPill status="FAILED" error="No extractable text found." />);
    expect(screen.getByText("Needs attention")).toBeInTheDocument();
  });

  it("names work in progress", () => {
    render(<StatusPill status="EMBEDDING" />);
    expect(screen.getByText("Indexing")).toBeInTheDocument();
  });

  it("hides its icons from assistive technology", () => {
    // The adjacent word already says it; an icon that announced itself would
    // read the state twice.
    const { container } = render(<StatusPill status="READY" />);
    for (const svg of container.querySelectorAll("svg")) {
      expect(svg).toHaveAttribute("aria-hidden", "true");
    }
  });
});

describe("StageBar", () => {
  it("exposes the stage as a real progressbar", () => {
    render(<StageBar status="CHUNKING" />);
    const bar = screen.getByRole("progressbar");
    expect(bar).toHaveAttribute("aria-valuenow", "3");
    expect(bar).toHaveAttribute("aria-valuemax", String(STAGE_COUNT));
  });

  it("carries a sentence, not a bare number", () => {
    // "step 3 of 4" alone does not say of what.
    render(<StageBar status="CHUNKING" />);
    expect(screen.getByRole("progressbar")).toHaveAttribute(
      "aria-valuetext",
      "Splitting into passages — step 3 of 4",
    );
  });

  it("shows the same sentence on screen", () => {
    render(<StageBar status="EMBEDDING" />);
    expect(screen.getByText("Making it searchable — step 4 of 4")).toBeInTheDocument();
  });

  it("renders nothing once the file has settled", () => {
    const { container } = render(<StageBar status="READY" />);
    expect(container).toBeEmptyDOMElement();
  });
});
