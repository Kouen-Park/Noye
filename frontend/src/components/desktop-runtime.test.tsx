import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { DesktopRuntime } from "./desktop-runtime";
import { AppShell } from "./app-shell";
import { OPEN_AI_SETTINGS_EVENT, TOGGLE_NAVIGATION_EVENT } from "@/lib/ai-settings";

const mocks = vi.hoisted(() => ({ isTauri: vi.fn(), invoke: vi.fn(), services: vi.fn(), setup: vi.fn(), setUrl: vi.fn(), listen: vi.fn() }));
vi.mock("@tauri-apps/api/core", () => ({ isTauri: mocks.isTauri, invoke: mocks.invoke }));
vi.mock("@tauri-apps/api/event", () => ({ listen: mocks.listen }));
vi.mock("./ai-settings", () => ({ AiSettingsDialog: ({ onClose }: { onClose: () => void }) => <div role="dialog" aria-label="Settings"><button onClick={onClose}>Close settings</button></div> }));
vi.mock("@/lib/runtime", () => ({ setDesktopBaseUrl: mocks.setUrl }));
vi.mock("@/lib/api", () => ({ getRuntimeServices: mocks.services, getDesktopSetup: mocks.setup }));
beforeEach(() => { vi.resetAllMocks(); localStorage.setItem("noye.desktop.setup-guide.v1", "seen"); mocks.listen.mockResolvedValue(vi.fn()); });
afterEach(() => { cleanup(); vi.useRealTimers(); localStorage.removeItem("noye.desktop.setup-guide.v1"); });

describe("desktop startup", () => {
  it("does not invoke desktop commands in the browser", async () => {
    mocks.isTauri.mockReturnValue(false);
    render(<DesktopRuntime><p>Library</p></DesktopRuntime>);
    expect(await screen.findByText("Library")).toBeVisible();
    expect(mocks.invoke).not.toHaveBeenCalled();
    expect(mocks.services).not.toHaveBeenCalled();
    expect(mocks.setup).not.toHaveBeenCalled();
  });

  it("waits for the owned backend before rendering children", async () => {
    mocks.isTauri.mockReturnValue(true);
    let ready!: (value: unknown) => void;
    mocks.invoke.mockImplementation(() => new Promise((resolve) => { ready = resolve; }));
    mocks.services.mockResolvedValue({ ollama: true, qdrant: true, generation_model: true, embedding_model: true });
    render(<DesktopRuntime><p>Library</p></DesktopRuntime>);
    expect(screen.queryByText("Library")).not.toBeInTheDocument();
    ready({ state: "ready", url: "http://127.0.0.1:34567", error: null });
    expect(await screen.findByText("Library")).toBeVisible();
    expect(mocks.setUrl).toHaveBeenCalledWith("http://127.0.0.1:34567");
    expect(mocks.invoke).toHaveBeenCalledWith("backend_status");
  });

  it("reports startup failure without mounting API consumers", async () => {
    mocks.isTauri.mockReturnValue(true);
    mocks.invoke.mockResolvedValue({ state: "failed", url: null, error: "The backend stopped." });
    render(<DesktopRuntime><p>Library</p></DesktopRuntime>);
    expect(await screen.findByRole("alert")).toHaveTextContent("The backend stopped.");
    expect(screen.queryByText("Library")).not.toBeInTheDocument();
  });

  it("does not open onboarding or probe hardware until the owned backend is ready", async () => {
    localStorage.removeItem("noye.desktop.setup-guide.v1");
    mocks.isTauri.mockReturnValue(true);
    let ready!: (value: unknown) => void;
    mocks.invoke.mockImplementation(() => new Promise((resolve) => { ready = resolve; }));
    mocks.setup.mockImplementation(() => new Promise(() => {}));
    mocks.services.mockResolvedValue({ ollama: true, qdrant: true, generation_model: true, embedding_model: true });
    render(<DesktopRuntime><p>Library</p></DesktopRuntime>);
    expect(mocks.setup).not.toHaveBeenCalled();
    ready({ state: "ready", url: "http://127.0.0.1:34567", error: null });
    expect(await screen.findByRole("dialog", { name: "AI on your computer" })).toBeVisible();
    expect(mocks.setup).toHaveBeenCalledTimes(1);
    expect(mocks.setUrl).toHaveBeenCalledWith("http://127.0.0.1:34567");
  });

  it("shows missing services without blocking access to saved work", async () => {
    mocks.isTauri.mockReturnValue(true);
    mocks.invoke.mockResolvedValue({ state: "ready", url: "http://127.0.0.1:34567", error: null });
    mocks.services.mockResolvedValue({ ollama: false, qdrant: false, generation_model: false, embedding_model: false });
    render(<DesktopRuntime><p>Library</p></DesktopRuntime>);
    await waitFor(() => expect(screen.getByRole("status")).toHaveTextContent("Ollama is not running; Qdrant is not running"));
    expect(screen.getByText("Library")).toBeVisible();
  });

  it("restores focus to the guide opener even when a pointer click does not focus it", async () => {
    mocks.isTauri.mockReturnValue(true);
    mocks.invoke.mockResolvedValue({ state: "ready", url: "http://127.0.0.1:34567", error: null });
    mocks.services.mockResolvedValue({ ollama: true, qdrant: true, generation_model: true, embedding_model: true });
    mocks.setup.mockRejectedValue(new Error("offline"));
    render(<DesktopRuntime><AppShell current="Library"><p>Library content</p></AppShell></DesktopRuntime>);
    const opener = await screen.findByRole("button", { name: "AI setup" });
    fireEvent.click(opener);
    await screen.findByRole("alert");
    fireEvent.click(screen.getByRole("button", { name: "Skip for now" }));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(opener).toHaveFocus();
  });

  it("hides the healthy service strip and opens settings from keyboard and native menu without remounting content", async () => {
    mocks.isTauri.mockReturnValue(true);
    mocks.invoke.mockResolvedValue({ state: "ready", url: "http://127.0.0.1:34567", error: null });
    mocks.services.mockResolvedValue({ ollama: true, qdrant: true, generation_model: true, embedding_model: true });
    render(<DesktopRuntime><input aria-label="Draft" defaultValue="unfinished" /></DesktopRuntime>);
    const draft = await screen.findByRole("textbox");
    await waitFor(() => expect(mocks.listen).toHaveBeenCalledTimes(1));
    expect(screen.queryByRole("complementary", { name: "Desktop AI setup" })).not.toBeInTheDocument();
    fireEvent.keyDown(window, { key: ",", metaKey: true });
    expect(screen.getByRole("dialog", { name: "Settings" })).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "Close settings" }));
    const listener = mocks.listen.mock.calls[0][1];
    act(() => listener({ payload: "settings" }));
    expect(screen.getByRole("dialog", { name: "Settings" })).toBeVisible();
    expect(screen.getByRole("textbox")).toBe(draft);
    expect(draft).toHaveValue("unfinished");
    const sidebar = vi.fn();
    window.addEventListener(TOGGLE_NAVIGATION_EVENT, sidebar);
    act(() => listener({ payload: "sidebar" }));
    expect(sidebar).toHaveBeenCalledTimes(1);
    window.removeEventListener(TOGGLE_NAVIGATION_EVENT, sidebar);
    act(() => window.dispatchEvent(new Event(OPEN_AI_SETTINGS_EVENT)));
    expect(screen.getByRole("dialog", { name: "Settings" })).toBeVisible();
  });

  it("removes a native listener that resolves after its workspace has unmounted", async () => {
    mocks.isTauri.mockReturnValue(true);
    mocks.invoke.mockResolvedValue({ state: "ready", url: "http://127.0.0.1:34567", error: null });
    mocks.services.mockResolvedValue({ ollama: true, qdrant: true, generation_model: true, embedding_model: true });
    let resolve!: (remove: () => void) => void;
    mocks.listen.mockImplementation(() => new Promise(done => { resolve = done; }));
    const { unmount } = render(<DesktopRuntime><p>Library</p></DesktopRuntime>);
    await screen.findByText("Library");
    const remove = vi.fn();
    unmount();
    await act(async () => resolve(remove));
    expect(remove).toHaveBeenCalledTimes(1);
  });

  it("does not wait forever when the native command stops responding", async () => {
    vi.useFakeTimers();
    mocks.isTauri.mockReturnValue(true);
    mocks.invoke.mockImplementation(() => new Promise(() => {}));
    render(<DesktopRuntime><p>Library</p></DesktopRuntime>);
    await act(() => vi.advanceTimersByTimeAsync(5_001));
    expect(screen.getByRole("alert")).toHaveTextContent("Noye is not responding");
    expect(screen.queryByText("Library")).not.toBeInTheDocument();
  });
});
