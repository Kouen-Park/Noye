import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import ChatPage from "@/app/chat/page";
import * as api from "@/lib/api";

const navigation = vi.hoisted(() => ({ query: "", push: vi.fn(), replace: vi.fn() }));
vi.mock("next/navigation", () => ({
  useRouter: () => navigation,
  useSearchParams: () => new URLSearchParams(navigation.query),
}));
vi.mock("@/lib/api", async (original) => ({
  ...await original<typeof api>(),
  listConversations: vi.fn(), readConversation: vi.fn(), askQuestion: vi.fn(),
  renameConversation: vi.fn(), deleteConversation: vi.fn(), listAiProviders: vi.fn(),
}));

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason: unknown) => void;
  const promise = new Promise<T>((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
}
const timestamp = "2026-10-03T00:00:00Z";
function message(id: string, content: string, role: api.Role = "assistant"): api.ChatMessage {
  return { id, content, role, error: null, citations: [], created_at: timestamp };
}
function conversation(id = "c1", messages = [message("m1", "Saved answer")]): api.ChatConversation {
  return { id, title: `Chat ${id}`, created_at: timestamp, updated_at: timestamp, messages };
}
function response(): api.AskResponse {
  return { conversation_id: "saved", conversation_title: "Saved chat", searched_files: 1,
    question: message("q", "My question", "user"), answer: message("a", "New answer") };
}
function send(question = "My question") {
  fireEvent.change(screen.getByLabelText("Ask about your documents"), { target: { value: question } });
  fireEvent.click(screen.getByRole("button", { name: "Ask" }));
}

describe("chat workspace", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    navigation.query = "";
    vi.mocked(api.listConversations).mockResolvedValue([
      { id: "c1", title: "Chat c1", message_count: 2, created_at: timestamp, updated_at: timestamp },
    ]);
    vi.mocked(api.listAiProviders).mockResolvedValue([
      { id: "ollama", model: "local-model", configured: true },
      { id: "gemini", model: "cloud-model", configured: true },
    ]);
    vi.mocked(api.readConversation).mockResolvedValue(conversation());
  });
  afterEach(() => vi.unstubAllGlobals());

  it("keeps library, search and documents reachable and fills a prompt without sending", async () => {
    render(<ChatPage />);
    await screen.findByRole("button", { name: "Open Chat c1" });
    expect(screen.getByRole("link", { name: "Library" })).toHaveAttribute("href", "/library");
    expect(screen.getByRole("link", { name: "Search" })).toHaveAttribute("href", "/search");
    expect(screen.getByRole("link", { name: "Documents" })).toHaveAttribute("href", "/documents");
    await userEvent.click(screen.getByRole("button", { name: "What are the main ideas in these files?" }));
    expect(screen.getByLabelText("Ask about your documents")).toHaveValue("What are the main ideas in these files?");
    expect(screen.getByLabelText("Ask about your documents")).toHaveFocus();
    expect(api.askQuestion).not.toHaveBeenCalled();
  });

  it("disables the composer until the selected conversation is loaded", async () => {
    navigation.query = "c=c1";
    const read = deferred<api.ChatConversation>();
    vi.mocked(api.readConversation).mockReturnValue(read.promise);
    render(<ChatPage />);
    expect(screen.getByLabelText("Ask about your documents")).toBeDisabled();
    await act(async () => read.resolve(conversation()));
    expect(screen.getByText("Saved answer")).toBeInTheDocument();
    expect(screen.getByLabelText("Ask about your documents")).not.toBeDisabled();
  });

  it("ignores an old read after navigating to a different conversation", async () => {
    const old = deferred<api.ChatConversation>();
    navigation.query = "c=c1";
    vi.mocked(api.readConversation).mockReturnValueOnce(old.promise).mockResolvedValueOnce(conversation("c2", [message("m2", "Second answer")]));
    const view = render(<ChatPage />);
    const signal = vi.mocked(api.readConversation).mock.calls[0][1];
    navigation.query = "c=c2";
    view.rerender(<ChatPage />);
    await screen.findByText("Second answer");
    await act(async () => old.resolve(conversation("c1", [message("old", "Stale answer")])));
    expect(signal?.aborted).toBe(true);
    expect(screen.queryByText("Stale answer")).not.toBeInTheDocument();
    expect(screen.getByText("Second answer")).toBeInTheDocument();
  });

  it("allows retrying an opening failure without submitting into an unloaded conversation", async () => {
    navigation.query = "c=c1";
    vi.mocked(api.readConversation).mockRejectedValueOnce(new Error("offline")).mockResolvedValueOnce(conversation());
    render(<ChatPage />);
    await screen.findByText("Could not open that conversation.");
    expect(screen.getByRole("button", { name: "Ask" })).toBeDisabled();
    await userEvent.click(screen.getByRole("button", { name: "Retry opening conversation" }));
    await screen.findByText("Saved answer");
    expect(screen.getByLabelText("Ask about your documents")).not.toBeDisabled();
  });

  it("locks conversation actions while waiting and sends the explicit selected provider", async () => {
    const asked = deferred<api.AskResponse>();
    vi.mocked(api.askQuestion).mockReturnValue(asked.promise);
    render(<ChatPage />);
    await screen.findByRole("option", { name: /cloud-model/ });
    await userEvent.selectOptions(screen.getByRole("combobox"), "gemini");
    send();
    expect(api.askQuestion).toHaveBeenCalledWith("My question", undefined, "gemini");
    expect(screen.getByText("Waiting for Gemini…")).toBeInTheDocument();
    for (const name of ["New chat", "Open Chat c1", "Rename Chat c1", "Delete Chat c1"]) {
      expect(screen.getByRole("button", { name })).toBeDisabled();
    }
    expect(screen.getByRole("combobox")).toBeDisabled();
    await act(async () => asked.resolve(response()));
    expect(screen.getByText("New answer")).toBeInTheDocument();
    expect(navigation.replace).toHaveBeenCalledWith("/chat?c=saved");
    expect(screen.getByRole("button", { name: "New chat" })).not.toBeDisabled();
  });

  it("does not redirect or insert an answer into a route selected with Back during generation", async () => {
    const asked = deferred<api.AskResponse>();
    vi.mocked(api.askQuestion).mockReturnValue(asked.promise);
    const view = render(<ChatPage />);
    await screen.findByRole("option", { name: /local-model/ });
    send();
    navigation.query = "c=c1";
    view.rerender(<ChatPage />);
    await screen.findByText("Saved answer");
    expect(screen.getByLabelText("Ask about your documents")).toBeDisabled();
    await act(async () => asked.resolve(response()));
    expect(screen.queryByText("New answer")).not.toBeInTheDocument();
    expect(navigation.replace).not.toHaveBeenCalled();
    expect(screen.getByLabelText("Ask about your documents")).not.toBeDisabled();
  });

  it("restores a failed question for retry and unlocks navigation", async () => {
    vi.mocked(api.askQuestion).mockRejectedValue(new Error("offline"));
    render(<ChatPage />);
    await screen.findByRole("option", { name: /local-model/ });
    send();
    await screen.findByText("Could not ask that question.");
    expect(screen.getByLabelText("Ask about your documents")).toHaveValue("My question");
    expect(screen.getByRole("button", { name: "New chat" })).not.toBeDisabled();
    expect(screen.queryByText("Waiting for Ollama…")).not.toBeInTheDocument();
  });

  it("does not reset a newly opened route when a previous conversation finishes deleting", async () => {
    navigation.query = "c=c1";
    const removed = deferred<void>();
    vi.mocked(api.deleteConversation).mockReturnValue(removed.promise);
    const view = render(<ChatPage />);
    await screen.findByText("Saved answer");
    await userEvent.click(screen.getByRole("button", { name: "Delete Chat c1" }));
    await userEvent.click(screen.getByRole("button", { name: "Delete" }));
    navigation.query = "c=c2";
    view.rerender(<ChatPage />);
    await act(async () => removed.resolve());
    expect(navigation.replace).not.toHaveBeenCalled();
  });

  it("inspects the selected answer's passages and returns focus on Escape", async () => {
    navigation.query = "c=c1";
    const answer = message("m1", "Cited answer");
    answer.citations = [{ file_id: "f1", file_name: "notes.pdf", page_number: 3, chunk_indexes: [0], score: 0.7, label: "notes.pdf — page 3" }];
    vi.mocked(api.readConversation).mockResolvedValue(conversation("c1", [answer]));
    render(<ChatPage />);
    const inspect = await screen.findByRole("button", { name: /passage consulted/i });
    await userEvent.click(inspect);
    expect(inspect).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByRole("complementary", { name: "Passages consulted" })).toHaveAttribute("id", inspect.getAttribute("aria-controls"));
    expect(screen.getByRole("link", { name: "Open notes.pdf at page 3" })).toHaveAttribute("href", "http://127.0.0.1:8000/files/f1/source#page=3");
    expect(screen.getByRole("button", { name: "Close passages" })).toHaveFocus();
    await userEvent.keyboard("{Escape}");
    expect(screen.queryByRole("complementary", { name: "Passages consulted" })).not.toBeInTheDocument();
    expect(inspect).toHaveFocus();
  });

  it("exposes the mobile menu's expanded state", async () => {
    render(<ChatPage />);
    await screen.findByRole("option", { name: /local-model/ });
    const menu = screen.getByRole("button", { name: "Menu & chats" });
    expect(menu).toHaveAttribute("aria-expanded", "false");
    await userEvent.click(menu);
    expect(screen.getByRole("button", { name: "Close menu" })).toHaveAttribute("aria-expanded", "true");
    await userEvent.click(screen.getByRole("button", { name: "Open Chat c1" }));
    expect(screen.getByRole("button", { name: "Menu & chats" })).toHaveAttribute("aria-expanded", "false");
    expect(navigation.push).toHaveBeenCalledWith("/chat?c=c1");
  });

  it("starts fresh even when New chat is clicked from an unsent new conversation", async () => {
    render(<ChatPage />);
    await screen.findByRole("option", { name: /local-model/ });
    fireEvent.change(screen.getByLabelText("Ask about your documents"), { target: { value: "Unsent draft" } });
    await userEvent.click(screen.getByRole("button", { name: "New chat" }));
    expect(screen.getByLabelText("Ask about your documents")).toHaveValue("");
    expect(api.askQuestion).not.toHaveBeenCalled();
  });

  it("does not animate conversation scrolling when reduced motion is requested", async () => {
    const scroll = vi.fn();
    vi.stubGlobal("matchMedia", vi.fn().mockReturnValue({ matches: true }));
    const original = HTMLElement.prototype.scrollTo;
    HTMLElement.prototype.scrollTo = scroll;
    try {
      render(<ChatPage />);
      await waitFor(() => expect(scroll).toHaveBeenCalledWith(expect.objectContaining({ behavior: "auto" })));
    } finally { HTMLElement.prototype.scrollTo = original; }
  });
});
