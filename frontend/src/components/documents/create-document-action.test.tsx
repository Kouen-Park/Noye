import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, it, vi } from "vitest";

import { CreateDocumentAction } from "@/components/documents/create-document-action";
import { mockRouter } from "@/tests/setup";

afterEach(() => vi.unstubAllGlobals());

it("ignores IME confirmation and submits only a later Enter", async () => {
  const fetch = vi.fn().mockImplementation((url: string) => url.endsWith("/documents/generate")
    ? new Promise(() => {})
    : Promise.resolve(new Response(JSON.stringify([{ id: "ollama", model: "local", configured: true }]))));
  vi.stubGlobal("fetch", fetch);
  render(<CreateDocumentAction messageId="message" />);
  await userEvent.click(screen.getByRole("button", { name: "Create document" }));
  const input = screen.getByLabelText("What should this become?");
  fireEvent.compositionStart(input);
  fireEvent.change(input, { target: { value: "회의 정리" } });
  fireEvent.keyDown(input, { key: "Enter", isComposing: true, keyCode: 229 });
  fireEvent.keyDown(input, { key: "Enter", keyCode: 229 });
  expect(fetch.mock.calls.filter(([url]) => url.endsWith("/documents/generate"))).toHaveLength(0);
  expect(input).toBeEnabled();
  fireEvent.compositionEnd(input);
  fireEvent.keyDown(input, { key: "Enter", keyCode: 13 });
  expect(fetch.mock.calls.filter(([url]) => url.endsWith("/documents/generate"))).toHaveLength(1);
});

it("routes the explicit cloud choice from the form to document generation", async () => {
  const fetch = vi.fn().mockImplementation((url: string) => Promise.resolve(new Response(
    JSON.stringify(url.endsWith("/ai/providers")
      ? [
          { id: "ollama", model: "local", configured: true },
          { id: "gemini", model: "cloud", configured: true },
        ]
      : { id: "new-document" }),
    { status: 200 },
  )));
  vi.stubGlobal("fetch", fetch);
  render(<CreateDocumentAction messageId="message" />);
  await userEvent.click(screen.getByRole("button", { name: "Create document" }));
  await screen.findByRole("option", { name: /cloud$/ });
  await userEvent.selectOptions(screen.getByRole("combobox"), "gemini");
  await userEvent.type(screen.getByRole("textbox"), "Make notes");
  await userEvent.click(screen.getByRole("button", { name: "Create" }));
  const generationCall = fetch.mock.calls.find(([url]) => url.endsWith("/documents/generate"));
  expect(JSON.parse(generationCall![1].body)).toEqual({
    message_id: "message", instruction: "Make notes", provider: "gemini",
  });
  expect(mockRouter.push).toHaveBeenCalledWith("/documents?d=new-document");
});

it.each([
  ["ollama", "The local model is writing it."],
  ["gemini", "Gemini is writing it."],
  ["openai", "OpenAI (ChatGPT) is writing it."],
  ["anthropic", "Claude is writing it."],
] as const)("keeps the evidence disclosure and selected %s pending state", async (provider, pending) => {
  const fetch = vi.fn().mockImplementation((url: string) => {
    if (url.endsWith("/documents/generate")) return new Promise(() => {});
    return Promise.resolve(new Response(JSON.stringify(
      ["ollama", "gemini", "openai", "anthropic"].map((id) => ({
        id, model: "test-model", configured: true,
      })),
    ), { status: 200 }));
  });
  vi.stubGlobal("fetch", fetch);
  render(<CreateDocumentAction messageId="message" />);
  await userEvent.click(screen.getByRole("button", { name: "Create document" }));
  expect(screen.getByText(/saved excerpts stay local/)).toBeVisible();
  await screen.findByRole("option", { name: /OpenAI.*test-model/ });
  await userEvent.selectOptions(screen.getByRole("combobox"), provider);
  await userEvent.type(screen.getByRole("textbox"), "Make notes");
  await userEvent.click(screen.getByRole("button", { name: "Create" }));
  expect(screen.getByText(pending)).toBeVisible();
  expect(screen.getByRole("combobox")).toBeDisabled();
  const generationCall = fetch.mock.calls.find(([url]) => url.endsWith("/documents/generate"));
  expect(JSON.parse(generationCall![1].body)).toEqual({
    message_id: "message", instruction: "Make notes", provider,
  });
});
