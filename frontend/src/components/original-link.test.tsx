import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { OriginalLink } from "./original-link";

const mocks = vi.hoisted(() => ({ invoke: vi.fn(), isTauri: vi.fn() }));
vi.mock("@tauri-apps/api/core", () => mocks);
vi.mock("@/lib/runtime", () => ({ apiBaseUrl: () => "http://127.0.0.1:34567" }));
beforeEach(() => { vi.resetAllMocks(); mocks.invoke.mockResolvedValue(null); });

describe("original opening", () => {
  it("sends the active source page through a native command button", async () => {
    mocks.isTauri.mockReturnValue(true);
    render(<OriginalLink href="/files/f1/source#page=3">Open current</OriginalLink>);
    const user = userEvent.setup();
    await user.tab();
    expect(screen.getByRole("button")).toHaveFocus();
    await user.keyboard("{Enter}");
    expect(mocks.invoke).toHaveBeenCalledWith("open_original", { url: "http://127.0.0.1:34567/files/f1/source#page=3" });
    await waitFor(() => expect(screen.getByRole("status")).toHaveTextContent("Sent the original"));
    // The printed document keeps its real destination, without command/status UI.
    expect(screen.getByRole("link")).toHaveAttribute("href", "/files/f1/source#page=3");
    expect(screen.getByRole("link")).toHaveAttribute("tabindex", "-1");
  });
  it.each(["https://example.com/files/f1/source", "http://127.0.0.1:34568/files/f1/source", "/services/start", "/files/f1/source?other=1"])("does not grant native opening to %s", href => {
    mocks.isTauri.mockReturnValue(true);
    render(<OriginalLink href={href}>Open</OriginalLink>);
    fireEvent.click(screen.getByRole("link"));
    expect(mocks.invoke).not.toHaveBeenCalled();
  });
  it("keeps normal web links and explicit cancellation", () => {
    mocks.isTauri.mockReturnValue(false);
    const { rerender } = render(<OriginalLink href="/files/f1/source">Open</OriginalLink>);
    expect(screen.getByRole("link")).toHaveAttribute("target", "_blank");
    fireEvent.click(screen.getByRole("link"));
    mocks.isTauri.mockReturnValue(true);
    rerender(<OriginalLink href="/files/f1/source" onClick={event => event.preventDefault()}>Open</OriginalLink>);
    fireEvent.click(screen.getByRole("button"));
    expect(mocks.invoke).not.toHaveBeenCalled();
  });
  it("reports failure and permits a successful retry", async () => {
    mocks.isTauri.mockReturnValue(true);
    mocks.invoke.mockRejectedValueOnce(new Error("missing"));
    render(<OriginalLink href="/files/f1/source">Open</OriginalLink>);
    fireEvent.click(screen.getByRole("button"));
    expect(await screen.findByRole("alert")).toHaveTextContent("Could not open");
    fireEvent.click(screen.getByRole("button"));
    await waitFor(() => expect(screen.queryByRole("alert")).not.toBeInTheDocument());
    expect(mocks.invoke).toHaveBeenCalledTimes(2);
    await waitFor(() => expect(screen.getByRole("status")).toHaveTextContent("Sent the original"));
  });
  it("blocks duplicate handoffs while the native command is pending", async () => {
    mocks.isTauri.mockReturnValue(true);
    let finish!: () => void;
    mocks.invoke.mockReturnValue(new Promise<void>(resolve => { finish = resolve; }));
    render(<OriginalLink href="/files/f1/source">Open</OriginalLink>);
    const action = screen.getByRole("button");
    fireEvent.click(action);
    fireEvent.click(action);
    expect(action).toBeDisabled();
    expect(action).toHaveAttribute("aria-busy", "true");
    expect(screen.getByRole("status")).toHaveTextContent("Opening original");
    expect(mocks.invoke).toHaveBeenCalledTimes(1);
    await act(async () => { finish(); });
    expect(action).not.toBeDisabled();
    expect(screen.getByRole("status")).toHaveTextContent("Sent the original");
  });
});
