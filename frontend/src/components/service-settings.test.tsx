import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { ServiceSettings } from "./service-settings";
import type { AiSettings, DesktopServiceStatus } from "@/lib/ai-settings";

const request = vi.hoisted(() => vi.fn());
vi.mock("@/lib/ai-settings", () => ({ desktopServiceRequest: request }));
const settings = { control_token: "synthetic-capability" } as AiSettings;
const services = { ollama: false, qdrant: false, generation_model: false, embedding_model: false };
const initial: DesktopServiceStatus = {
  ollama: { state: "offline", ownership: "none", detail: "Not running.", can_start: true },
  qdrant: { state: "offline", ownership: "none", detail: "Not running.", can_start: true },
  docker_installed: true, docker_open_available: true,
};

beforeEach(() => request.mockResolvedValue(structuredClone(initial)));
afterEach(() => vi.resetAllMocks());

it("only reads on opening and requires explicit download/start confirmation", async () => {
  render(<ServiceSettings settings={settings} services={services} onRefresh={vi.fn()} />);
  const start = await screen.findByRole("button", { name: "Start Qdrant" });
  expect(start).toBeDisabled();
  expect(request.mock.calls.every((args) => args[2] === "GET")).toBe(true);
  await userEvent.click(screen.getByRole("checkbox"));
  await userEvent.click(start);
  await waitFor(() => expect(request).toHaveBeenCalledWith(settings, "/start", "POST", {
    service: "qdrant", confirmed: true,
  }, expect.any(AbortSignal)));
});

it("distinguishes external running services and has no stop action", async () => {
  request.mockResolvedValue({ ...initial, ollama: { ...initial.ollama, state: "ready", ownership: "external", detail: "Left running on quit." } });
  render(<ServiceSettings settings={settings} services={services} onRefresh={vi.fn()} />);
  await screen.findByText("Running · external");
  expect(screen.queryByRole("button", { name: "Start Ollama" })).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: /stop/i })).not.toBeInTheDocument();
});

it("shows owned preparation without fabricated overall progress", async () => {
  request.mockResolvedValue({ ...initial, qdrant: { ...initial.qdrant, state: "starting", ownership: "noye", detail: "Downloading the pinned image." } });
  render(<ServiceSettings settings={settings} services={services} onRefresh={vi.fn()} />);
  await screen.findByText("Preparing…");
  expect(screen.getByRole("button", { name: "Start Ollama" })).toBeDisabled();
  expect(screen.queryByRole("progressbar")).not.toBeInTheDocument();
});

it("offers missing prerequisite instructions without running an installer", async () => {
  request.mockResolvedValue({ ...initial, ollama: { ...initial.ollama, can_start: false }, qdrant: { ...initial.qdrant, can_start: false }, docker_open_available: false });
  render(<ServiceSettings settings={settings} services={services} onRefresh={vi.fn()} />);
  await screen.findByRole("link", { name: "Docker Desktop installation guide" });
  expect(screen.getByRole("button", { name: "Start Ollama" })).toBeDisabled();
  expect(screen.queryByRole("button", { name: "Open Docker Desktop" })).not.toBeInTheDocument();
  expect(request).toHaveBeenCalledTimes(1);
});

it("opens Docker explicitly and explains that the shared engine stays running", async () => {
  render(<ServiceSettings settings={settings} services={services} onRefresh={vi.fn()} />);
  await screen.findByRole("button", { name: "Open Docker Desktop" });
  await userEvent.click(screen.getByRole("checkbox"));
  await userEvent.click(screen.getByRole("button", { name: "Open Docker Desktop" }));
  await screen.findByText(/Noye will not close Docker/);
  expect(request).toHaveBeenCalledWith(settings, "/docker", "POST", { confirmed: true }, expect.any(AbortSignal));
});

it("surfaces a failed request and permits retry without claiming startup", async () => {
  render(<ServiceSettings settings={settings} services={services} onRefresh={vi.fn()} />);
  await screen.findByRole("button", { name: "Start Ollama" });
  await userEvent.click(screen.getByRole("checkbox"));
  request.mockRejectedValueOnce(new Error("Port occupied; nothing stopped."));
  await userEvent.click(screen.getByRole("button", { name: "Start Ollama" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Port occupied");
  expect(screen.queryByText(/Running ·/)).not.toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Start Ollama" })).toBeEnabled();
});

it("refreshes model inventory explicitly without saving AI preferences", async () => {
  const refresh = vi.fn().mockResolvedValue(undefined);
  render(<ServiceSettings settings={settings} services={services} onRefresh={refresh} />);
  await screen.findByRole("button", { name: "Refresh status" });
  await userEvent.click(screen.getByRole("button", { name: "Refresh status" }));
  await waitFor(() => expect(refresh).toHaveBeenCalledOnce());
  expect(request.mock.calls.every((args) => args[2] === "GET")).toBe(true);
});

it("aborts panel requests on close but does not send a service-stop mutation", async () => {
  const result = render(<ServiceSettings settings={settings} services={services} onRefresh={vi.fn()} />);
  await screen.findByRole("button", { name: "Start Ollama" });
  const signal = request.mock.calls[0][4] as AbortSignal;
  result.unmount();
  expect(signal.aborted).toBe(true);
  expect(request).toHaveBeenCalledOnce();
});

it("keeps an explicit retry reachable when the first status check fails", async () => {
  request.mockRejectedValueOnce(new Error("Offline"));
  render(<ServiceSettings settings={settings} services={services} onRefresh={vi.fn()} />);
  await screen.findByRole("alert");
  await userEvent.click(screen.getByRole("button", { name: "Refresh status" }));
  await screen.findByRole("button", { name: "Start Qdrant" });
  expect(screen.queryByRole("alert")).not.toBeInTheDocument();
});

it("opens an official setup guide through the bounded desktop bridge", async () => {
  request.mockResolvedValue({ ...initial, ollama: { ...initial.ollama, can_start: false } });
  render(<ServiceSettings settings={settings} services={services} onRefresh={vi.fn()} />);
  await userEvent.click(await screen.findByRole("link", { name: "Ollama installation guide" }));
  await screen.findByText(/No installer was run/);
  expect(request).toHaveBeenCalledWith(settings, "/guide", "POST", { guide: "ollama" }, expect.any(AbortSignal));
});
