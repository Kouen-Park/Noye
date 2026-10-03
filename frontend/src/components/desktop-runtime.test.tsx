import { act, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { DesktopRuntime } from "./desktop-runtime";

const mocks = vi.hoisted(() => ({ isTauri: vi.fn(), invoke: vi.fn(), services: vi.fn(), setUrl: vi.fn() }));
vi.mock("@tauri-apps/api/core", () => ({ isTauri: mocks.isTauri, invoke: mocks.invoke }));
vi.mock("@/lib/runtime", () => ({ setDesktopBaseUrl: mocks.setUrl }));
vi.mock("@/lib/api", () => ({ getRuntimeServices: mocks.services }));
afterEach(() => { vi.resetAllMocks(); vi.useRealTimers(); });

describe("desktop startup", () => {
  it("does not invoke desktop commands in the browser", async () => {
    mocks.isTauri.mockReturnValue(false);
    render(<DesktopRuntime><p>Library</p></DesktopRuntime>);
    expect(await screen.findByText("Library")).toBeVisible();
    expect(mocks.invoke).not.toHaveBeenCalled();
    expect(mocks.services).not.toHaveBeenCalled();
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

  it("shows missing services without blocking access to saved work", async () => {
    mocks.isTauri.mockReturnValue(true);
    mocks.invoke.mockResolvedValue({ state: "ready", url: "http://127.0.0.1:34567", error: null });
    mocks.services.mockResolvedValue({ ollama: false, qdrant: false, generation_model: false, embedding_model: false });
    render(<DesktopRuntime><p>Library</p></DesktopRuntime>);
    await waitFor(() => expect(screen.getByRole("status")).toHaveTextContent("Ollama is not running; Qdrant is not running"));
    expect(screen.getByText("Library")).toBeVisible();
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
