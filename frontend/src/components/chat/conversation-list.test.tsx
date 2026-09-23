import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { ConversationList } from "@/components/chat/conversation-list";
import type { ConversationSummary } from "@/lib/api";

function conversation(overrides: Partial<ConversationSummary> = {}): ConversationSummary {
  return {
    id: "c1",
    title: "How does Dijkstra choose?",
    created_at: "2026-09-23T00:00:00+00:00",
    updated_at: "2026-09-23T00:00:00+00:00",
    message_count: 4,
    ...overrides,
  };
}

function handlers() {
  return {
    onOpen: vi.fn(),
    onRename: vi.fn(),
    onDelete: vi.fn(),
    onNew: vi.fn(),
  };
}

describe("ConversationList", () => {
  it("invites a first question when empty", () => {
    render(<ConversationList conversations={[]} currentId={null} {...handlers()} />);
    expect(screen.getByText(/nothing asked yet/i)).toBeInTheDocument();
  });

  it("shows each conversation with its message count", () => {
    render(
      <ConversationList conversations={[conversation()]} currentId={null} {...handlers()} />,
    );
    expect(screen.getByText("How does Dijkstra choose?")).toBeInTheDocument();
    expect(screen.getByText("4 messages")).toBeInTheDocument();
  });

  it("singularises a lone message", () => {
    render(
      <ConversationList
        conversations={[conversation({ message_count: 1 })]}
        currentId={null}
        {...handlers()}
      />,
    );
    expect(screen.getByText("1 message")).toBeInTheDocument();
  });

  it("marks the open conversation", () => {
    render(
      <ConversationList conversations={[conversation()]} currentId="c1" {...handlers()} />,
    );
    expect(
      screen.getByRole("button", { name: "Open How does Dijkstra choose?" }),
    ).toHaveAttribute("aria-current", "true");
  });

  it("opens one on click", async () => {
    const h = handlers();
    render(<ConversationList conversations={[conversation()]} currentId={null} {...h} />);

    await userEvent.click(
      screen.getByRole("button", { name: "Open How does Dijkstra choose?" }),
    );

    expect(h.onOpen).toHaveBeenCalledWith("c1");
  });

  it("starts a new one", async () => {
    const h = handlers();
    render(<ConversationList conversations={[]} currentId={null} {...h} />);
    await userEvent.click(screen.getByRole("button", { name: "New" }));
    expect(h.onNew).toHaveBeenCalled();
  });

  it("renames inline, seeded with the current title", async () => {
    const h = handlers();
    render(<ConversationList conversations={[conversation()]} currentId={null} {...h} />);

    await userEvent.click(screen.getByRole("button", { name: /^Rename/ }));
    const input = screen.getByLabelText("Conversation title");
    expect(input).toHaveValue("How does Dijkstra choose?");

    await userEvent.clear(input);
    await userEvent.type(input, "Shortest paths{Enter}");

    expect(h.onRename).toHaveBeenCalledWith("c1", "Shortest paths");
  });

  it("does not rename to nothing", async () => {
    const h = handlers();
    render(<ConversationList conversations={[conversation()]} currentId={null} {...h} />);

    await userEvent.click(screen.getByRole("button", { name: /^Rename/ }));
    const input = screen.getByLabelText("Conversation title");
    await userEvent.clear(input);
    await userEvent.type(input, "   {Enter}");

    expect(h.onRename).not.toHaveBeenCalled();
  });

  it("asks before deleting, and says the files are safe", async () => {
    const h = handlers();
    render(<ConversationList conversations={[conversation()]} currentId={null} {...h} />);

    await userEvent.click(screen.getByRole("button", { name: /^Delete/ }));

    // The button gives no clue whether documents are at risk, so the confirm says.
    expect(screen.getByText(/your files are not affected/i)).toBeInTheDocument();
    expect(h.onDelete).not.toHaveBeenCalled();

    await userEvent.click(screen.getByRole("button", { name: "Delete" }));
    expect(h.onDelete).toHaveBeenCalledWith("c1");
  });

  it("can be backed out of", async () => {
    const h = handlers();
    render(<ConversationList conversations={[conversation()]} currentId={null} {...h} />);

    await userEvent.click(screen.getByRole("button", { name: /^Delete/ }));
    await userEvent.click(screen.getByRole("button", { name: "Keep" }));

    expect(h.onDelete).not.toHaveBeenCalled();
    expect(screen.getByText("How does Dijkstra choose?")).toBeInTheDocument();
  });

  it("names the conversation in its edit and delete controls", () => {
    // A list would otherwise be identical "Edit" and "✕" links to anyone
    // navigating by control.
    render(
      <ConversationList conversations={[conversation()]} currentId={null} {...handlers()} />,
    );
    expect(
      screen.getByRole("button", { name: "Open How does Dijkstra choose?" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Rename How does Dijkstra choose?" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Delete How does Dijkstra choose?" }),
    ).toBeInTheDocument();
  });
});
