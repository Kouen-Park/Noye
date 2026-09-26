import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { AppShell } from "@/components/app-shell";

describe("AppShell", () => {
  it("keeps all four navigation items compact on narrow screens", () => {
    const { container } = render(
      <AppShell current="Documents">
        <p>Document content</p>
      </AppShell>,
    );

    const navigation = screen.getByRole("navigation", { name: "Sections" });
    expect(navigation.querySelector("ul")).toHaveClass(
      "gap-0",
      "md:gap-1",
      "overflow-x-auto",
    );

    for (const name of ["Library", "Search", "Chat", "Documents"]) {
      expect(screen.getByRole("link", { name })).toHaveClass(
        "gap-2",
        "px-2",
        "md:gap-3",
        "md:px-3",
      );
    }

    expect(screen.getByRole("link", { name: "Documents" })).toHaveAttribute(
      "aria-current",
      "page",
    );
    expect(container).toHaveTextContent("Document content");
  });
});
