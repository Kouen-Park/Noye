import { act, fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { DesktopSetup } from "@/lib/api";

import { DesktopSetupDialog, useSetupGuide } from "./desktop-setup";

const mocks = vi.hoisted(() => ({ getSetup: vi.fn() }));
vi.mock("@/lib/api", () => ({ getDesktopSetup: mocks.getSetup }));

const fixture: DesktopSetup = {
  hardware: {
    os: "Darwin", architecture: "arm64", logical_cpus: 8,
    total_memory_bytes: 8 * 2 ** 30, available_memory_bytes: 2 ** 30,
    workspace_disk_free_bytes: 15 * 2 ** 30,
    memory_measurement: "free_and_inactive_estimate", acceleration: "apple_silicon_candidate",
  },
  recommendation: {
    generation: {
      name: "qwen3.5:0.8b", approximate_download_bytes: 1_000_000_000,
      minimum_total_memory_bytes: 8 * 2 ** 30, estimated_working_memory_bytes: 2.5 * 2 ** 30,
      source_url: "https://ollama.com/library/qwen3.5:0.8b",
    },
    memory_status: "close_apps", acceleration_unverified: false,
    embedding_model: "embeddinggemma", approximate_embedding_download_bytes: 622_000_000,
    workspace_disk_status: "check_model_location", catalog_checked_on: "2026-10-05",
  },
  services: { ollama: true, qdrant: false, generation_model: true, embedding_model: true },
  installed_models: [{ name: "qwen3.5:4b", size_bytes: 3_400_000_000 }],
  configured_generation_model: "qwen3.5:4b", gemini_configured: false,
};

function Harness() {
  const setup = useSetupGuide();
  return <>
    <button onClick={setup.show}>AI setup</button>
    <label>Unsaved writing<input defaultValue="Keep this draft" /></label>
    {setup.storageWarning && <p role="status">Dismissal could not be remembered.</p>}
    {setup.open && <DesktopSetupDialog onClose={setup.close} />}
  </>;
}

beforeEach(() => {
  localStorage.removeItem("noye.desktop.setup-guide.v1");
  mocks.getSetup.mockResolvedValue(structuredClone(fixture));
});
afterEach(() => {
  vi.restoreAllMocks(); vi.resetAllMocks(); vi.useRealTimers();
  localStorage.removeItem("noye.desktop.setup-guide.v1");
});

describe("desktop setup guidance", () => {
  it("shows measured values, a small candidate, and a busy-memory warning without changing the active model", async () => {
    render(<DesktopSetupDialog onClose={vi.fn()} />);
    expect(await screen.findByText("qwen3.5:0.8b")).toBeVisible();
    expect(screen.getByText("8.0 GiB")).toBeVisible();
    expect(screen.getByRole("status")).toHaveTextContent("Memory is tight");
    expect(screen.getByRole("status")).toHaveTextContent("2.5 GiB");
    expect(screen.getByText(/qwen3.5:4b · Installed/)).toBeVisible();
    expect(screen.getByText(/Your active model is unchanged/)).toBeVisible();
    expect(screen.getByText(/not a speed or quality benchmark/)).toBeVisible();
    expect(mocks.getSetup).toHaveBeenCalledTimes(1);
  });

  it("opens cloud guidance without invoking a provider, asking for a key, or sending content", async () => {
    const user = userEvent.setup();
    render(<DesktopSetupDialog onClose={vi.fn()} />);
    await user.click(await screen.findByRole("radio", { name: /Gemini API/ }));
    expect(screen.getByText(/No Gemini key is configured/)).toBeVisible();
    expect(screen.getByText(/Chat sends your question, bounded recent user questions and retrieved excerpts/)).toBeVisible();
    expect(screen.getByText(/cannot enforce free-only usage/)).toBeVisible();
    expect(screen.getByText(/does not select Gemini/)).toBeVisible();
    expect(screen.queryByRole("textbox")).not.toBeInTheDocument();
    expect(mocks.getSetup).toHaveBeenCalledTimes(1);
  });

  it("shows configured cloud availability, not a live key validation claim", async () => {
    mocks.getSetup.mockResolvedValue({ ...fixture, gemini_configured: true });
    render(<DesktopSetupDialog onClose={vi.fn()} />);
    fireEvent.click(await screen.findByRole("radio", { name: /Gemini API/ }));
    expect(screen.getByText(/A Gemini key is already configured/)).toBeVisible();
    expect(screen.getByText(/validate your key/)).toBeVisible();
  });

  it("reports unknown measurements honestly and does not invent a recommendation", async () => {
    mocks.getSetup.mockResolvedValue({ ...fixture,
      hardware: { ...fixture.hardware, total_memory_bytes: null, available_memory_bytes: null,
        logical_cpus: null, workspace_disk_free_bytes: null, acceleration: "unknown" },
      recommendation: { ...fixture.recommendation, generation: null, memory_status: "unknown" },
    });
    render(<DesktopSetupDialog onClose={vi.fn()} />);
    expect(await screen.findByText("No reliable local recommendation yet")).toBeVisible();
    expect(screen.getAllByText("Not available")).toHaveLength(4);
    expect(screen.getByText(/Model fit is unknown/)).toBeVisible();
    expect(screen.queryByText("0.0 GiB")).not.toBeInTheDocument();
  });

  it("distinguishes an installed candidate and an unavailable inventory", async () => {
    mocks.getSetup.mockResolvedValue({ ...fixture,
      installed_models: [{ name: "qwen3.5:0.8b", size_bytes: null }],
      recommendation: { ...fixture.recommendation, memory_status: "estimated_fit" },
    });
    render(<DesktopSetupDialog onClose={vi.fn()} />);
    expect(await screen.findByText(/Already installed/)).toBeVisible();
    fireEvent.click(screen.getByText("Installed Ollama models (1)"));
    expect(screen.getByText("Size unknown")).toBeVisible();
    expect(screen.queryByText(/Memory is tight/)).not.toBeInTheDocument();
  });

  it("retries a failed read, and saved work is never gated by the check", async () => {
    mocks.getSetup.mockRejectedValueOnce(new Error("offline"));
    const close = vi.fn();
    render(<DesktopSetupDialog onClose={close} />);
    expect(await screen.findByRole("alert")).toHaveTextContent("Could not check this computer");
    expect(screen.getByRole("button", { name: "Continue to workspace" })).toBeEnabled();
    fireEvent.click(screen.getByRole("button", { name: "Try setup check again" }));
    expect(await screen.findByText("qwen3.5:0.8b")).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "Continue to workspace" }));
    expect(close).toHaveBeenCalledOnce();
  });

  it("bounds a hung check and ignores a late response", async () => {
    vi.useFakeTimers();
    let finish!: (value: DesktopSetup) => void;
    mocks.getSetup.mockImplementation(() => new Promise((resolve) => { finish = resolve; }));
    render(<DesktopSetupDialog onClose={vi.fn()} />);
    await act(() => vi.advanceTimersByTimeAsync(10_001));
    expect(screen.getByRole("alert")).toHaveTextContent("took too long");
    expect(mocks.getSetup.mock.calls[0][0].aborted).toBe(true);
    await act(async () => finish(fixture));
    expect(screen.queryByText("qwen3.5:0.8b")).not.toBeInTheDocument();
  });

  it("aborts a pending read when the dialog is closed", () => {
    mocks.getSetup.mockImplementation(() => new Promise(() => {}));
    const view = render(<DesktopSetupDialog onClose={vi.fn()} />);
    const signal = mocks.getSetup.mock.calls[0][0];
    view.unmount();
    expect(signal.aborted).toBe(true);
  });

  it("refreshes a successful check without changing the selected guide", async () => {
    render(<DesktopSetupDialog onClose={vi.fn()} />);
    fireEvent.click(await screen.findByRole("radio", { name: /Gemini API/ }));
    fireEvent.click(screen.getByRole("button", { name: "Check again" }));
    expect(await screen.findByRole("radio", { name: /Gemini API/ })).toBeChecked();
    expect(mocks.getSetup).toHaveBeenCalledTimes(2);
  });

  it("allows skipping from the first viewport even while a check is pending", () => {
    mocks.getSetup.mockImplementation(() => new Promise(() => {}));
    const close = vi.fn();
    render(<DesktopSetupDialog onClose={close} />);
    expect(screen.getByRole("button", { name: "Check again" })).toHaveAttribute("aria-disabled", "true");
    fireEvent.click(screen.getByRole("button", { name: "Skip for now" }));
    expect(close).toHaveBeenCalledOnce();
  });

  it("remembers only dismissal, reopens with fresh readings, and preserves unsaved writing", async () => {
    const view = render(<Harness />);
    await screen.findByText("qwen3.5:0.8b");
    fireEvent.change(screen.getByRole("textbox"), { target: { value: "Do not discard me" } });
    fireEvent.click(screen.getByRole("button", { name: "Continue to workspace" }));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(localStorage.getItem("noye.desktop.setup-guide.v1")).toBe("seen");
    const opener = screen.getByRole("button", { name: "AI setup" });
    opener.focus();
    fireEvent.click(opener);
    await screen.findByText("qwen3.5:0.8b");
    expect(screen.getByRole("textbox")).toHaveValue("Do not discard me");
    expect(mocks.getSetup).toHaveBeenCalledTimes(2);
    fireEvent(screen.getByRole("dialog"), new Event("cancel", { bubbles: true, cancelable: true }));
    expect(opener).toHaveFocus();
    view.unmount();
    render(<Harness />);
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(mocks.getSetup).toHaveBeenCalledTimes(2);
  });

  it("dismisses for this launch when preference storage is unavailable", async () => {
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => { throw new Error("denied"); });
    render(<Harness />);
    await screen.findByText("qwen3.5:0.8b");
    fireEvent.click(screen.getByRole("button", { name: "Continue to workspace" }));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent("could not be remembered");
    fireEvent.click(screen.getByRole("button", { name: "AI setup" }));
    expect(await screen.findByRole("dialog")).toBeVisible();
  });
});
