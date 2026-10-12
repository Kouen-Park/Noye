import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { OriginalLink } from "./original-link";

const mocks = vi.hoisted(() => ({ invoke: vi.fn(), isTauri: vi.fn() }));
vi.mock("@tauri-apps/api/core", () => mocks);
vi.mock("@/lib/runtime", () => ({ apiBaseUrl: () => "http://127.0.0.1:34567" }));
beforeEach(() => { vi.resetAllMocks(); mocks.invoke.mockResolvedValue(null); });

describe("original opening", () => {
  it("opens the active source page explicitly in the native browser", () => {
    mocks.isTauri.mockReturnValue(true);
    render(<OriginalLink href="/files/f1/source#page=3">Open current</OriginalLink>);
    fireEvent.click(screen.getByRole("link"));
    expect(mocks.invoke).toHaveBeenCalledWith("open_original", { url: "http://127.0.0.1:34567/files/f1/source#page=3" });
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
    fireEvent.click(screen.getByRole("link"));
    expect(mocks.invoke).not.toHaveBeenCalled();
  });
  it("reports failure and permits a successful retry", async () => {
    mocks.isTauri.mockReturnValue(true);
    mocks.invoke.mockRejectedValueOnce(new Error("missing"));
    render(<OriginalLink href="/files/f1/source">Open</OriginalLink>);
    fireEvent.click(screen.getByRole("link"));
    expect(await screen.findByRole("alert")).toHaveTextContent("Could not open");
    fireEvent.click(screen.getByRole("link"));
    await waitFor(() => expect(screen.queryByRole("alert")).not.toBeInTheDocument());
    expect(mocks.invoke).toHaveBeenCalledTimes(2);
  });
});
