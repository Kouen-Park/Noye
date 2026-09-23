import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { MessageBubble } from "@/components/chat/message-bubble";
import type { ChatMessage } from "@/lib/api";

function message(overrides: Partial<ChatMessage> = {}): ChatMessage {
  return {
    id: "m1",
    role: "assistant",
    content: "It takes the smallest estimate from a priority queue.",
    error: null,
    citations: [],
    created_at: "2026-09-23T00:00:00+00:00",
    ...overrides,
  };
}

describe("MessageBubble", () => {
  it("shows a question", () => {
    render(<MessageBubble message={message({ role: "user", content: "How does it work?" })} />);
    expect(screen.getByText("How does it work?")).toBeInTheDocument();
  });

  it("shows an answer", () => {
    render(<MessageBubble message={message()} />);
    expect(screen.getByText(/priority queue/)).toBeInTheDocument();
  });

  it("offers passages on an answer that has them", () => {
    render(
      <MessageBubble
        message={message({
          citations: [
            {
              file_id: "f1",
              file_name: "Algorithms.pdf",
              page_number: 34,
              chunk_indexes: [5],
              score: 0.7,
              label: "Algorithms.pdf — page 34",
            },
          ],
        })}
      />,
    );
    expect(screen.getByRole("button", { name: /passage consulted/i })).toBeInTheDocument();
  });

  it("offers nothing to inspect on an answer with no passages", () => {
    render(<MessageBubble message={message({ citations: [] })} />);
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });

  it("reports a failed turn with its reason, and says the question survived", () => {
    render(
      <MessageBubble
        message={message({ content: "", error: "Could not reach Ollama." })}
      />,
    );
    expect(screen.getByText("This went unanswered")).toBeInTheDocument();
    expect(screen.getByText("Could not reach Ollama.")).toBeInTheDocument();
    expect(screen.getByText(/your question is still here/i)).toBeInTheDocument();
  });

  it("does not offer passages on a failed turn", () => {
    render(<MessageBubble message={message({ content: "", error: "down" })} />);
    expect(screen.queryByRole("button", { name: /passage/i })).not.toBeInTheDocument();
  });

  it("preserves the line breaks someone typed", () => {
    render(
      <MessageBubble message={message({ role: "user", content: "line one\nline two" })} />,
    );
    expect(screen.getByText(/line one/)).toHaveClass("whitespace-pre-wrap");
  });
});
