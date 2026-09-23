import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { Composer } from "@/components/chat/composer";

function field(): HTMLTextAreaElement {
  return screen.getByLabelText(/ask about your documents/i) as HTMLTextAreaElement;
}

describe("Composer", () => {
  it("has a labelled textarea", () => {
    render(<Composer onAsk={vi.fn()} pending={false} />);
    expect(field().tagName).toBe("TEXTAREA");
  });

  it("sends on Enter", async () => {
    const onAsk = vi.fn();
    render(<Composer onAsk={onAsk} pending={false} />);

    await userEvent.type(field(), "How does it work?{Enter}");

    expect(onAsk).toHaveBeenCalledWith("How does it work?");
  });

  it("makes a newline on Shift+Enter instead of sending", async () => {
    const onAsk = vi.fn();
    render(<Composer onAsk={onAsk} pending={false} />);

    await userEvent.type(field(), "first{Shift>}{Enter}{/Shift}second");

    expect(onAsk).not.toHaveBeenCalled();
    expect(field().value).toBe("first\nsecond");
  });

  it("clears the field after sending", async () => {
    render(<Composer onAsk={vi.fn()} pending={false} />);
    await userEvent.type(field(), "a question{Enter}");
    expect(field()).toHaveValue("");
  });

  it("refuses to send nothing", async () => {
    const onAsk = vi.fn();
    render(<Composer onAsk={onAsk} pending={false} />);

    await userEvent.type(field(), "   {Enter}");

    expect(onAsk).not.toHaveBeenCalled();
    expect(screen.getByRole("button", { name: "Ask" })).toBeDisabled();
  });

  it("trims the question", async () => {
    const onAsk = vi.fn();
    render(<Composer onAsk={onAsk} pending={false} />);
    await userEvent.type(field(), "  spaced  {Enter}");
    expect(onAsk).toHaveBeenCalledWith("spaced");
  });

  it("cannot be sent twice while one answer is in flight", async () => {
    const onAsk = vi.fn();
    render(<Composer onAsk={onAsk} pending />);

    await userEvent.type(field(), "another{Enter}");

    expect(onAsk).not.toHaveBeenCalled();
    expect(screen.getByRole("button", { name: "Thinking…" })).toBeDisabled();
  });

  it("warns that a local model can be slow", () => {
    render(<Composer onAsk={vi.fn()} pending={false} />);
    expect(screen.getByText(/local model can take a while/i)).toBeInTheDocument();
  });

  it("is unusable when disabled", () => {
    render(<Composer onAsk={vi.fn()} pending={false} disabled />);
    expect(field()).toBeDisabled();
  });
});
