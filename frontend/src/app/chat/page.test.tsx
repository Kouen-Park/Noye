import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import ChatPage from "@/app/chat/page";
import * as api from "@/lib/api";
import * as sourceDocs from "@/lib/source-documents";
import { resetChatSessions } from "@/lib/chat-session";

const navigation = vi.hoisted(() => ({ query: "", push: vi.fn(), replace: vi.fn() }));
vi.mock("next/navigation", () => ({
  useRouter: () => navigation,
  useSearchParams: () => new URLSearchParams(navigation.query),
}));
vi.mock("@/lib/api", async (original) => ({
  ...await original<typeof api>(),
  listConversations: vi.fn(), readConversation: vi.fn(), askQuestion: vi.fn(),
  renameConversation: vi.fn(), deleteConversation: vi.fn(), listAiProviders: vi.fn(),
  listFiles: vi.fn(), updateConversationScope: vi.fn(),
}));

vi.mock("@/lib/source-documents", async get => ({ ...await get<typeof sourceDocs>(), generateSourceDocument: vi.fn(), listDocumentTasks: vi.fn() }));

function renderChat() {
  const view = render(<ChatPage />);
  fireEvent.click(screen.getByText(/AI & sources/));
  return view;
}

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
    resetChatSessions();
    vi.mocked(sourceDocs.listDocumentTasks).mockResolvedValue([]);
    navigation.query = "";
    vi.mocked(api.listConversations).mockResolvedValue([
      { id: "c1", title: "Chat c1", message_count: 2, created_at: timestamp, updated_at: timestamp },
    ]);
    vi.mocked(api.listAiProviders).mockResolvedValue([
      { id: "ollama", model: "local-model", configured: true },
      { id: "gemini", model: "cloud-model", configured: true },
    ]);
    vi.mocked(api.readConversation).mockResolvedValue(conversation());
    vi.mocked(api.listFiles).mockResolvedValue([]);
  });
  afterEach(() => vi.unstubAllGlobals());

  it("keeps library, search and documents reachable and fills a prompt without sending", async () => {
    renderChat();
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
    renderChat();
    expect(screen.getByLabelText("Ask about your documents")).toBeDisabled();
    await act(async () => read.resolve(conversation()));
    expect(screen.getByText("Saved answer")).toBeInTheDocument();
    expect(screen.getByLabelText("Ask about your documents")).not.toBeDisabled();
  });

  it("ignores an old read after navigating to a different conversation", async () => {
    const old = deferred<api.ChatConversation>();
    navigation.query = "c=c1";
    vi.mocked(api.readConversation).mockReturnValueOnce(old.promise).mockResolvedValueOnce(conversation("c2", [message("m2", "Second answer")]));
    const view = renderChat();
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
    renderChat();
    await screen.findByText("Could not open that conversation.");
    expect(screen.getByRole("button", { name: "Ask" })).toBeDisabled();
    await userEvent.click(screen.getByRole("button", { name: "Retry opening conversation" }));
    await screen.findByText("Saved answer");
    expect(screen.getByLabelText("Ask about your documents")).not.toBeDisabled();
  });

  it("locks conversation actions while waiting and sends the explicit selected provider", async () => {
    const asked = deferred<api.AskResponse>();
    vi.mocked(api.askQuestion).mockReturnValue(asked.promise);
    renderChat();
    await screen.findByRole("option", { name: /cloud-model/ });
    await userEvent.selectOptions(screen.getByRole("combobox"), "gemini");
    send();
    expect(api.askQuestion).toHaveBeenCalledWith("My question", undefined, "gemini", null);
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
    const view = renderChat();
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
    renderChat();
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
    const view = renderChat();
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
    renderChat();
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
    renderChat();
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
    renderChat();
    await screen.findByRole("option", { name: /local-model/ });
    fireEvent.change(screen.getByLabelText("Ask about your documents"), { target: { value: "Unsent draft" } });
    await userEvent.click(screen.getByRole("button", { name: "New chat" }));
    expect(screen.getByLabelText("Ask about your documents")).toHaveValue("");
    expect(api.askQuestion).not.toHaveBeenCalled();
  });

  it("reloads a saved empty scope and waits for a scope update before asking", async () => {
    navigation.query = "c=c1";
    const saved = { ...conversation(), source_scope: [] };
    const update = deferred<api.ChatConversation>();
    vi.mocked(api.readConversation).mockResolvedValue(saved);
    vi.mocked(api.updateConversationScope).mockReturnValue(update.promise);
    vi.mocked(api.askQuestion).mockResolvedValue(response());
    renderChat();
    await screen.findByText("No files selected");
    await userEvent.click(screen.getByText("No files selected"));
    await userEvent.click(screen.getByRole("checkbox", { name: "All ready files" }));
    expect(api.updateConversationScope).toHaveBeenCalledWith("c1", null);
    expect(screen.getByRole("button", { name: "Ask" })).toBeDisabled();
    await act(async () => update.resolve({ ...saved, source_scope: null }));
    expect(screen.getByText("Search all ready files")).toBeInTheDocument();
    send("A scoped question");
    expect(api.askQuestion).toHaveBeenCalledWith("A scoped question", "c1", "ollama", null);
  });

  it("does not animate conversation scrolling when reduced motion is requested", async () => {
    const scroll = vi.fn();
    vi.stubGlobal("matchMedia", vi.fn().mockReturnValue({ matches: true }));
    const original = HTMLElement.prototype.scrollTo;
    HTMLElement.prototype.scrollTo = scroll;
    try {
      renderChat();
      await waitFor(() => expect(scroll).toHaveBeenCalledWith(expect.objectContaining({ behavior: "auto" })));
    } finally { HTMLElement.prototype.scrollTo = original; }
  });

  it.each([
    "How do I write notes without missing important details?",
    "Do not create a document; explain the process instead.",
  ])("keeps %s as a normal question when document mode is off", async question => {
    vi.mocked(api.askQuestion).mockReturnValue(new Promise(() => {}));
    renderChat();
    await screen.findByRole("option", { name: /cloud-model/ });
    await userEvent.selectOptions(screen.getByRole("combobox"), "gemini");
    send(question);
    expect(api.askQuestion).toHaveBeenLastCalledWith(question, undefined, "gemini", null);
    expect(sourceDocs.generateSourceDocument).not.toHaveBeenCalled();
  });

  it("keeps a follow-up draft when a new conversation receives its saved ID", async () => {
    navigation.query = "";
    const asked = deferred<api.AskResponse>();
    vi.mocked(api.askQuestion).mockReturnValue(asked.promise);
    const view = renderChat();
    await screen.findByRole("option", { name: /local-model/ });
    send();
    fireEvent.change(screen.getByLabelText("Ask about your documents"), { target: { value: "Follow-up draft" } });
    await act(async () => asked.resolve(response()));
    navigation.query = "c=saved";
    vi.mocked(api.readConversation).mockResolvedValue(conversation("saved", [response().question, response().answer]));
    view.rerender(<ChatPage />);
    await screen.findByText("New answer");
    expect(screen.getByLabelText("Ask about your documents")).toHaveValue("Follow-up draft");
  });

  it("reconnects to a pending answer after leaving and reopening its conversation", async () => {
    navigation.query = "c=c1";
    const asked = deferred<api.AskResponse>();
    vi.mocked(api.askQuestion).mockReturnValue(asked.promise);
    const first = renderChat();
    await screen.findByText("Saved answer"); send(); first.unmount();
    const returned = renderChat();
    await screen.findByText("Saved answer");
    expect(screen.getByText("Waiting for Ollama…")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Thinking…" })).toBeDisabled();
    await act(async () => asked.resolve({ ...response(), conversation_id: "c1" }));
    await screen.findByText("New answer");
    expect(screen.getByRole("button", { name: "Ask" })).toBeDisabled(); // empty draft, no replay
    expect(api.askQuestion).toHaveBeenCalledTimes(1);
    returned.unmount();
  });

  it("retains the new-chat draft's source and document options across route unmounts", async () => {
    const first = renderChat();
    await screen.findByRole("option", { name: /local-model/ });
    fireEvent.click(screen.getByText("Search all ready files"));
    await userEvent.click(screen.getByRole("checkbox", { name: "All ready files" }));
    fireEvent.click(screen.getByText("Chat options"));
    await userEvent.click(screen.getByRole("checkbox", { name: "Create an editable document" }));
    await userEvent.click(screen.getByRole("checkbox", { name: "Use every source in the selected scope" }));
    fireEvent.change(screen.getByLabelText("Ask about your documents"), { target: { value: "Scoped document draft" } });
    first.unmount();
    renderChat();
    expect(screen.getByLabelText("Ask about your documents")).toHaveValue("Scoped document draft");
    expect(screen.getByText("No files selected")).toBeInTheDocument();
    fireEvent.click(screen.getByText("Document options · Local Ollama"));
    expect(screen.getByRole("checkbox", { name: "Create an editable document" })).toBeChecked();
    expect(screen.getByRole("checkbox", { name: "Use every source in the selected scope" })).toBeChecked();
  });

  it("keeps cached completions in order when a reopened conversation has newer turns", async () => {
    navigation.query = "c=c1";
    vi.mocked(api.askQuestion).mockResolvedValue({ ...response(), conversation_id: "c1" });
    const first = renderChat();
    await screen.findByText("Saved answer"); send();
    await screen.findByText("New answer"); first.unmount();
    vi.mocked(api.readConversation).mockResolvedValue(conversation("c1", [
      response().question, response().answer, message("later-q", "Later question", "user"), message("later-a", "Later answer"),
    ]));
    renderChat();
    await screen.findByText("Later answer");
    const items = screen.getByRole("list", { name: "Messages" }).querySelectorAll("li");
    expect([...items].map(item => item.textContent)).toEqual([
      expect.stringContaining("My question"), expect.stringContaining("New answer"),
      expect.stringContaining("Later question"), expect.stringContaining("Later answer"),
    ]);
  });


  it("uses local document jobs only after explicit selection and refreshes their cards", async () => {
    navigation.query = "c=c1";
    const job = deferred<sourceDocs.DocumentTask>();
    vi.mocked(sourceDocs.generateSourceDocument).mockReturnValue(job.promise);
    renderChat();
    await screen.findByRole("option", { name: /cloud-model/ });
    await screen.findByText("Saved answer");
    await userEvent.selectOptions(screen.getByRole("combobox"), "gemini");
    fireEvent.click(screen.getByText("Chat options"));
    await userEvent.click(screen.getByRole("checkbox", { name: "Create an editable document" }));
    expect(screen.getByLabelText("Ask about your documents")).toHaveAccessibleDescription(/Document jobs use local Ollama/);
    const before = vi.mocked(sourceDocs.listDocumentTasks).mock.calls.length;
    send("Write a report");
    expect(api.askQuestion).not.toHaveBeenCalled();
    expect(screen.getByText("Waiting for Ollama…")).toBeInTheDocument();
    expect(sourceDocs.generateSourceDocument).toHaveBeenCalledWith("Write a report", { mode: "all", root_ids: [], source_ids: [] }, "c1", "auto", expect.any(String));
    await act(async () => job.resolve({ job: null, request: {
      id: "request", artifact_id: null, clarification: null, manifest: [], plan: null, report: {},
      request: { instruction: "Write a report", conversation_id: "c1", scope: { mode: "all", root_ids: [], source_ids: [] } },
    } }));
    await waitFor(() => expect(sourceDocs.listDocumentTasks).toHaveBeenCalledTimes(before + 1));
  });

  it("merges an answer that completes before a stale reopening read", async () => {
    navigation.query = "c=c1";
    const asked = deferred<api.AskResponse>();
    vi.mocked(api.askQuestion).mockReturnValue(asked.promise);
    const first = renderChat();
    await screen.findByText("Saved answer"); send(); first.unmount();
    const stale = deferred<api.ChatConversation>();
    vi.mocked(api.readConversation).mockReturnValue(stale.promise);
    renderChat();
    const turn = { ...response(), conversation_id: "c1" };
    await act(async () => asked.resolve(turn));
    expect(screen.getByText("Opening conversation…")).toBeInTheDocument();
    await act(async () => stale.resolve(conversation("c1", [message("m1", "Saved answer"), turn.question])));
    expect(screen.getByText("New answer")).toBeInTheDocument();
    expect(screen.getAllByText("My question")).toHaveLength(1);
    expect(api.askQuestion).toHaveBeenCalledTimes(1);
  });

});
