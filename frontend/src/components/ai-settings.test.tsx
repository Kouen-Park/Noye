import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { AiSettingsDialog } from "./ai-settings";
import type { DesktopSetup } from "@/lib/api";

const mocks = vi.hoisted(() => ({ read: vi.fn(), save: vi.fn(), setup: vi.fn(), model: vi.fn() }));
vi.mock("@/lib/ai-settings", async (original) => ({ ...await original<typeof import("@/lib/ai-settings")>(),
  readAiSettings: mocks.read, saveAiSettings: mocks.save, modelRequest: mocks.model }));
vi.mock("@/lib/api", () => ({ getDesktopSetup: mocks.setup }));
vi.mock("./workspace-settings", () => ({ WorkspaceSettings: () => <p>Workspace backup controls</p> }));

const settings = { provider: "ollama", ollama_model: "qwen3.5:4b", openai_model: "gpt-4.1-mini",
  anthropic_model: "claude-haiku-4-5", gemini_model: "gemini-3.8-flash", openai_configured: false,
  anthropic_configured: false, gemini_configured: false, control_token: "synthetic-control", storage_path: "/test/models" };
const setup = { recommendation: { generation: { name: "qwen3.5:0.8b" }, memory_status: "close_apps",
  embedding_model: "embeddinggemma", approximate_embedding_download_bytes: 622000000 },
  services: { ollama: true, qdrant: false, generation_model: true, embedding_model: true },
  installed_models: [{ name: "qwen3.5:4b", size_bytes: 3400000000 },
    { name: "embeddinggemma:latest", size_bytes: 622000000 }, { name: "unused:latest", size_bytes: 1000000 }] } as DesktopSetup;

beforeEach(() => {
  mocks.read.mockResolvedValue({ ...settings }); mocks.setup.mockResolvedValue(structuredClone(setup));
  mocks.save.mockResolvedValue(undefined);
  mocks.model.mockResolvedValue({ state: "idle", model: "", completed: 0, total: 0, error: null });
});
afterEach(() => vi.resetAllMocks());

it("shows a recommendation without starting any model operation", async () => {
  render(<AiSettingsDialog onClose={vi.fn()} />);
  await screen.findByText(/Suggested starting point/);
  expect(screen.getByRole("button", { name: "Download model" })).toBeDisabled();
  expect(mocks.model.mock.calls.every((call) => call[1] === "/job")).toBe(true);
  const rows = screen.getAllByRole("listitem");
  expect(within(rows[0]).getByRole("button", { name: "Delete" })).toBeDisabled();
  expect(within(rows[1]).getByRole("button", { name: "Delete" })).toBeDisabled();
});

it("keeps workspace backup available when AI readiness cannot be checked", async () => {
  mocks.setup.mockRejectedValue(new Error("Backend probe failed."));
  render(<AiSettingsDialog onClose={vi.fn()} />);
  await screen.findByText(/Workspace backup remains available/);
  await userEvent.click(screen.getByRole("button", { name: "Workspace" }));
  expect(screen.getByText("Workspace backup controls")).toBeVisible();
});

it("requires storage confirmation before requesting download", async () => {
  render(<AiSettingsDialog onClose={vi.fn()} />);
  await screen.findByText(/Suggested starting point/);
  await userEvent.click(screen.getByRole("checkbox"));
  await userEvent.click(screen.getByRole("button", { name: "Download model" }));
  await screen.findByText(/Download requested/);
  expect(mocks.model).toHaveBeenCalledWith(expect.anything(), "/pull", "POST", {
    model: "qwen3.5:0.8b", storage_path: "/test/models", confirmed_storage: true });
});

it("requires the exact unused model name for deletion", async () => {
  render(<AiSettingsDialog onClose={vi.fn()} />);
  await screen.findByText(/Suggested starting point/);
  await userEvent.click(within(screen.getAllByRole("listitem")[2]).getByRole("button", { name: "Delete" }));
  expect(screen.getByRole("button", { name: "Confirm deletion" })).toBeDisabled();
  await userEvent.type(screen.getByLabelText(/to confirm deletion/), "unused:latest");
  await userEvent.click(screen.getByRole("button", { name: "Confirm deletion" }));
  await screen.findByText("Model deleted from Ollama.");
  expect(mocks.model).toHaveBeenCalledWith(expect.anything(), "", "DELETE", { model: "unused:latest" });
});

it("saves a masked key only through native settings, then clears the input", async () => {
  render(<AiSettingsDialog onClose={vi.fn()} />);
  await screen.findByText(/Suggested starting point/);
  await userEvent.click(screen.getByRole("button", { name: "Cloud APIs" }));
  const key = screen.getByLabelText("API key", { exact: true });
  expect(key).toHaveAttribute("type", "password");
  await userEvent.type(key, "synthetic-key");
  await userEvent.click(screen.getByRole("button", { name: "Save OpenAI (ChatGPT) settings" }));
  await screen.findByText(/Cloud settings saved securely/);
  expect(mocks.save).toHaveBeenCalledWith(expect.anything(), "openai", "synthetic-key");
  expect(key).toHaveValue("");
  expect(localStorage.length).toBe(0);
});

it("requires explicit confirmation to remove Noye's saved key", async () => {
  mocks.read.mockResolvedValue({ ...settings, openai_configured: true });
  render(<AiSettingsDialog onClose={vi.fn()} />);
  await screen.findByText(/Suggested starting point/);
  await userEvent.click(screen.getByRole("button", { name: "Cloud APIs" }));
  await userEvent.click(screen.getByRole("button", { name: "Remove saved key" }));
  expect(mocks.save).not.toHaveBeenCalled();
  await userEvent.click(screen.getByRole("button", { name: "Confirm key removal" }));
  await screen.findByText("Saved API key removed.");
  expect(mocks.save).toHaveBeenCalledWith(expect.anything(), "openai", undefined, true);
});

it("surfaces save errors and does not claim success", async () => {
  mocks.save.mockRejectedValue("Keychain access denied.");
  render(<AiSettingsDialog onClose={vi.fn()} />);
  await screen.findByText(/Suggested starting point/);
  await userEvent.click(screen.getByRole("button", { name: "Save local model" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Keychain access denied.");
  expect(screen.queryByText("Local model preference saved.")).not.toBeInTheDocument();
});

it("restores opener focus and retains the workspace draft on close", async () => {
  const close = vi.fn();
  const opener = document.createElement("button"); document.body.append(opener); opener.focus();
  const result = render(<AiSettingsDialog onClose={close} />);
  await screen.findByText(/Suggested starting point/);
  fireEvent.click(screen.getByRole("button", { name: "Close" }));
  expect(close).toHaveBeenCalled();
  result.unmount(); await waitFor(() => expect(opener).toHaveFocus()); opener.remove();
});
