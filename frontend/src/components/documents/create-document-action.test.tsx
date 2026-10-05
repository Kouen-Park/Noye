import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, it, vi } from "vitest";

import { CreateDocumentAction } from "@/components/documents/create-document-action";
import { mockRouter } from "@/tests/setup";

afterEach(() => vi.unstubAllGlobals());

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
