import { act, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useEffect, useState } from "react";
import { AppShell, useWorkspaceLayout } from "./app-shell";
import { setSidebarCollapsed } from "@/lib/workspace-preferences";
import { TOGGLE_NAVIGATION_EVENT } from "@/lib/ai-settings";

vi.mock("@tauri-apps/api/core", () => ({ isTauri: () => false }));
let mounts = 0;
function Draft() {
  const [text, setText] = useState("");
  const { readingFocus, setReadingFocus } = useWorkspaceLayout();
  useEffect(() => { mounts++; }, []);
  return <><input aria-label="Draft" value={text} onChange={event => setText(event.target.value)} />
    <button onClick={() => setReadingFocus(!readingFocus)}>Focus</button></>;
}
beforeEach(() => { mounts = 0; setSidebarCollapsed(false); });
afterEach(() => vi.unstubAllGlobals());

describe("workspace layout", () => {
  it("moves focus into mobile navigation and restores its opener on Escape", () => {
    vi.stubGlobal("matchMedia", () => ({ matches: false, addEventListener: vi.fn(), removeEventListener: vi.fn() }));
    render(<AppShell current="Documents"><Draft /></AppShell>);
    fireEvent.click(screen.getByRole("button", { name: "Open navigation" }));
    // The current page is the useful starting point for keyboard navigation.
    expect(screen.getByRole("link", { name: "Documents" })).toHaveFocus();
    fireEvent.keyDown(window, { key: "Escape" });
    expect(screen.getByRole("button", { name: "Open navigation" })).toHaveFocus();
    expect(screen.getByRole("textbox")).toBeVisible();
    expect(mounts).toBe(1);
  });
  it("preserves the mounted draft through collapse, focus and native sidebar events", () => {
    const { container } = render(<AppShell current="Documents"><Draft /></AppShell>);
    const draft = screen.getByRole("textbox");
    fireEvent.change(draft, { target: { value: "검토 중인 문서" } });
    fireEvent.click(screen.getByRole("button", { name: "Collapse navigation" }));
    expect(localStorage.getItem("noye:sidebar-collapsed")).toBe("true");
    fireEvent.click(screen.getByRole("button", { name: "Focus" }));
    expect(container.querySelector(".noye-app-shell")).toHaveAttribute("data-reading-focus", "true");
    act(() => window.dispatchEvent(new Event(TOGGLE_NAVIGATION_EVENT)));
    expect(container.querySelector(".noye-app-shell")).toHaveAttribute("data-reading-focus", "false");
    act(() => window.dispatchEvent(new Event(TOGGLE_NAVIGATION_EVENT)));
    expect(screen.getByRole("button", { name: "Collapse navigation" })).toBeVisible();
    expect(screen.getByRole("textbox")).toBe(draft);
    expect(draft).toHaveValue("검토 중인 문서");
    expect(mounts).toBe(1);
  });
  it("remembers collapse on remount and remains usable when persistence fails", () => {
    const first = render(<AppShell current="Search">Search</AppShell>);
    fireEvent.click(screen.getByRole("button", { name: "Collapse navigation" }));
    first.unmount();
    render(<AppShell current="Search">Search</AppShell>);
    expect(screen.getByRole("button", { name: "Expand navigation" })).toBeVisible();
    const write = vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => { throw new Error("quota"); });
    fireEvent.click(screen.getByRole("button", { name: "Expand navigation" }));
    expect(screen.getByRole("button", { name: "Collapse navigation" })).toBeVisible();
    write.mockRestore();
  });
  it("responds to another window's preference without resetting content", () => {
    render(<AppShell current="Documents"><Draft /></AppShell>);
    fireEvent.change(screen.getByRole("textbox"), { target: { value: "saved locally" } });
    localStorage.setItem("noye:sidebar-collapsed", "true");
    act(() => window.dispatchEvent(new StorageEvent("storage", { key: "noye:sidebar-collapsed" })));
    expect(screen.getByRole("button", { name: "Expand navigation" })).toBeVisible();
    expect(screen.getByRole("textbox")).toHaveValue("saved locally");
    expect(mounts).toBe(1);
  });
});
