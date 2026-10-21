import { beforeEach, expect, it, vi } from "vitest";
import { ApiError } from "@/lib/api";
import { chatSessionKey, clearNewChat, readChatSession, resetChatSessions, setChatDraft, setChatOptions, submitChatRequest } from "@/lib/chat-session";

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (cause: unknown) => void;
  const promise = new Promise<T>((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
}

beforeEach(resetChatSessions);

it.each([null, [], ["missing-selected-source"]])("preserves scope %j and continued typing when a new document request receives its saved ID", async scope => {
  const response = deferred<{ conversationId: string }>();
  setChatOptions("new", { scope, documentMode: true, collectionMode: true });
  const request = submitChatRequest("new", "document", "ollama", "Create notes", () => response.promise);
  setChatDraft("new", "Follow-up written while the request runs");
  response.resolve({ conversationId: "saved" });
  await request;
  clearNewChat();
  expect(readChatSession(chatSessionKey("saved"))).toMatchObject({
    draft: "Follow-up written while the request runs", scope,
    documentMode: true, collectionMode: true, pending: null,
    completion: { conversationId: "saved" }, error: null,
  });
  expect(readChatSession("new").draft).toBe("");
});

it("prevents a second conversation from dispatching while an owned request is pending", async () => {
  const response = deferred<{ conversationId: string }>();
  const first = chatSessionKey("first");
  const second = chatSessionKey("second");
  setChatDraft(second, "Unsent question in another conversation");
  const request = submitChatRequest(first, "answer", "gemini", "Pending question", () => response.promise);
  const duplicate = vi.fn(async () => ({ conversationId: "second" }));
  await submitChatRequest(second, "answer", "ollama", "Another question", duplicate);
  expect(duplicate).not.toHaveBeenCalled();
  expect(readChatSession(first).pending).toMatchObject({ provider: "gemini", question: "Pending question" });
  expect(readChatSession(second)).toMatchObject({ draft: "Unsent question in another conversation", pending: null, completion: null });
  response.resolve({ conversationId: "first" });
  await request;
});

it.each(["", "A newer authored follow-up"])("retains a retryable failure without overwriting draft %j or widening selected sources", async draft => {
  const key = chatSessionKey("saved");
  const response = deferred<{ conversationId: string }>();
  setChatOptions(key, { scope: ["missing-selected-source"] });
  const request = submitChatRequest(key, "answer", "ollama", "Failed question", () => response.promise);
  setChatDraft(key, draft);
  response.reject(new ApiError(503, "Local inference unavailable"));
  await request;
  expect(readChatSession(key)).toMatchObject({
    draft: draft || "Failed question", scope: ["missing-selected-source"],
    pending: null, completion: null, error: "Local inference unavailable",
  });
});
