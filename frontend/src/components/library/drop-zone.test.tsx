import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { DropZone } from "@/components/library/drop-zone";

function fileInput(): HTMLInputElement {
  // Queried by its accessible name, which only exists if the label really is
  // associated with the input.
  return screen.getByLabelText(/drop files to add them/i) as HTMLInputElement;
}

describe("DropZone", () => {
  it("exposes a real file input that the label names", () => {
    render(<DropZone onFiles={vi.fn()} uploading={[]} />);
    const input = fileInput();
    expect(input.tagName).toBe("INPUT");
    expect(input.type).toBe("file");
    expect(input.multiple).toBe(true);
  });

  it("keeps the input OUTSIDE its label", () => {
    // A label that both wraps its control and points at it with `for` triggers
    // the control's activation twice, which can cancel Chrome's file chooser so
    // no change event fires at all: the picker opens, a file is chosen, and
    // nothing happens. This assertion is here because that actually shipped.
    render(<DropZone onFiles={vi.fn()} uploading={[]} />);
    const input = fileInput();
    const label = document.querySelector("label");
    expect(label).not.toBeNull();
    expect(label!.getAttribute("for")).toBe(input.id);
    expect(label!.contains(input)).toBe(false);
  });

  it("stays reachable by keyboard rather than being display:none", () => {
    render(<DropZone onFiles={vi.fn()} uploading={[]} />);
    const input = fileInput();
    input.focus();
    expect(input).toHaveFocus();
  });

  it("hands over the chosen files", async () => {
    const onFiles = vi.fn();
    render(<DropZone onFiles={onFiles} uploading={[]} />);

    await userEvent.upload(fileInput(), [
      new File(["# Notes"], "notes.md", { type: "text/markdown" }),
    ]);

    expect(onFiles).toHaveBeenCalledTimes(1);
    expect(onFiles.mock.calls[0][0].map((f: File) => f.name)).toEqual(["notes.md"]);
  });

  it("accepts several files at once", async () => {
    const onFiles = vi.fn();
    render(<DropZone onFiles={onFiles} uploading={[]} />);

    await userEvent.upload(fileInput(), [
      new File(["a"], "a.md"),
      new File(["b"], "b.txt"),
    ]);

    expect(onFiles.mock.calls[0][0]).toHaveLength(2);
  });

  it("reports uploads in flight by name", () => {
    render(<DropZone onFiles={vi.fn()} uploading={["lecture.pdf"]} />);
    expect(screen.getByText(/adding lecture\.pdf/i)).toBeInTheDocument();
  });

  it("counts them instead of listing them once there is more than one", () => {
    render(<DropZone onFiles={vi.fn()} uploading={["a.md", "b.md"]} />);
    expect(screen.getByText(/adding 2 files/i)).toBeInTheDocument();
  });

  it("does not offer the input while disabled", () => {
    render(<DropZone onFiles={vi.fn()} uploading={[]} disabled />);
    expect(fileInput()).toBeDisabled();
  });
});
