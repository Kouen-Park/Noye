import { afterEach, describe, expect, it, vi } from "vitest";

import { askQuestion, generateDocument, listAiProviders } from "@/lib/api";

afterEach(() => vi.unstubAllGlobals());

describe("provider requests", () => {
  it("sends the chosen provider for chat and document generation", async () => {
    const fetch = vi.fn().mockImplementation(() => Promise.resolve(
      new Response("{}", { status: 201 }),
    ));
    vi.stubGlobal("fetch", fetch);
    await askQuestion("question", "conversation", "gemini");
    await generateDocument("message", "notes", "gemini");
    expect(JSON.parse(fetch.mock.calls[0][1].body)).toEqual({
      question: "question", conversation_id: "conversation", provider: "gemini",
    });
    expect(JSON.parse(fetch.mock.calls[1][1].body)).toEqual({
      message_id: "message", instruction: "notes", provider: "gemini",
    });
  });

  it("defaults to local for existing callers", async () => {
    const fetch = vi.fn().mockImplementation(() => Promise.resolve(new Response("{}")));
    vi.stubGlobal("fetch", fetch);
    await askQuestion("question");
    await generateDocument("message", "notes");
    for (const call of fetch.mock.calls) {
      expect(JSON.parse(call[1].body).provider).toBe("ollama");
    }
  });

  it("reads only public provider metadata", async () => {
    const providers = [{ id: "gemini", model: "cloud", configured: true }];
    const fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify(providers)));
    vi.stubGlobal("fetch", fetch);
    expect(await listAiProviders()).toEqual(providers);
    expect(fetch.mock.calls[0][0]).toMatch(/\/ai\/providers$/);
  });
});
