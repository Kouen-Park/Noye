import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ProviderSelector } from "@/components/provider-selector";
import type { GenerationProvider } from "@/lib/api";
import * as runtime from "@/lib/runtime";

function Harness({ task = "chat" }: { task?: "chat" | "document" }) {
  const [provider, setProvider] = useState<GenerationProvider>("ollama");
  return <ProviderSelector value={provider} onChange={setProvider} task={task} />;
}

function configure(configured: boolean) {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify([
    { id: "ollama", model: "local-model", configured: true },
    { id: "gemini", model: "cloud-model", configured },
  ]), { status: 200 })));
}

describe("ProviderSelector", () => {
  beforeEach(() => configure(true));
  afterEach(() => { vi.unstubAllGlobals(); vi.restoreAllMocks(); });

  it("defaults to local even when Gemini is configured", async () => {
    render(<Harness />);
    await screen.findByRole("option", { name: /cloud-model/ });
    expect(screen.getByRole("combobox")).toHaveValue("ollama");
    expect(screen.getByText(/not sent to Google/)).toBeInTheDocument();
  });

  it("disables cloud until a key is configured", async () => {
    configure(false);
    render(<Harness />);
    expect(await screen.findByRole("option", { name: /cloud-model/ })).toBeDisabled();
    expect(screen.getByText(/set GEMINI_API_KEY/)).toBeInTheDocument();
  });

  it("discloses exactly what chat sends and allows switching back", async () => {
    render(<Harness />);
    await screen.findByRole("option", { name: /cloud-model/ });
    await userEvent.selectOptions(screen.getByRole("combobox"), "gemini");
    expect(screen.getByText(/question, bounded recent conversation context and retrieved document excerpts/)).toBeInTheDocument();
    expect(screen.getByText(/cannot enforce a free tier/)).toBeInTheDocument();
    await userEvent.selectOptions(screen.getByRole("combobox"), "ollama");
    expect(screen.queryByText(/will be sent to Google/)).not.toBeInTheDocument();
  });

  it("describes the document payload separately", async () => {
    render(<Harness task="document" />);
    await screen.findByRole("option", { name: /cloud-model/ });
    await userEvent.selectOptions(screen.getByRole("combobox"), "gemini");
    expect(screen.getByText(/instruction, saved answer and cited file names/)).toBeInTheDocument();
  });

  it("keeps local available when configuration cannot be read", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("offline")));
    render(<Harness />);
    await screen.findByText(/Could not check AI/);
    expect(screen.getByRole("combobox")).toHaveValue("ollama");
    expect(screen.getAllByRole("option", { name: /Cloud API/ }).every((option) => option.hasAttribute("disabled"))).toBe(true);
  });

  it("prevents changing provider during generation", async () => {
    render(<ProviderSelector value="ollama" onChange={vi.fn()} disabled />);
    await waitFor(() => expect(screen.getByRole("combobox")).toBeDisabled());
  });

  it("does not direct desktop users to an unread repository .env", async () => {
    vi.spyOn(runtime, "isDesktopRuntime").mockReturnValue(true);
    configure(false);
    render(<Harness />);
    expect(await screen.findByRole("button", { name: /Manage models and API keys in Settings/ })).toBeInTheDocument();
    expect(screen.queryByText(/project's .env/)).not.toBeInTheDocument();
  });
});
