import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { SearchForm } from "@/components/search/search-form";

function field(): HTMLInputElement {
  return screen.getByLabelText(/what are you looking for/i) as HTMLInputElement;
}

describe("SearchForm", () => {
  it("has a labelled input inside a search landmark", () => {
    render(<SearchForm initialQuery="" onSubmit={vi.fn()} pending={false} />);
    expect(screen.getByRole("search")).toBeInTheDocument();
    expect(field()).toBeInTheDocument();
  });

  it("seeds the field from the URL's query", () => {
    render(<SearchForm initialQuery="dijkstra" onSubmit={vi.fn()} pending={false} />);
    expect(field()).toHaveValue("dijkstra");
  });

  it("submits on Enter, because it is a real form", async () => {
    const onSubmit = vi.fn();
    render(<SearchForm initialQuery="" onSubmit={onSubmit} pending={false} />);

    await userEvent.type(field(), "how does dijkstra choose{Enter}");

    expect(onSubmit).toHaveBeenCalledWith("how does dijkstra choose");
  });

  it("submits on the button too", async () => {
    const onSubmit = vi.fn();
    render(<SearchForm initialQuery="graphs" onSubmit={onSubmit} pending={false} />);

    await userEvent.click(screen.getByRole("button", { name: "Search" }));

    expect(onSubmit).toHaveBeenCalledWith("graphs");
  });

  it("trims the query before handing it over", async () => {
    const onSubmit = vi.fn();
    render(<SearchForm initialQuery="" onSubmit={onSubmit} pending={false} />);

    await userEvent.type(field(), "  dijkstra  {Enter}");

    expect(onSubmit).toHaveBeenCalledWith("dijkstra");
  });

  it("refuses to submit nothing", async () => {
    const onSubmit = vi.fn();
    render(<SearchForm initialQuery="" onSubmit={onSubmit} pending={false} />);

    await userEvent.type(field(), "   {Enter}");

    expect(onSubmit).not.toHaveBeenCalled();
    expect(screen.getByRole("button", { name: "Search" })).toBeDisabled();
  });

  it("says it is working while a search is in flight", () => {
    render(<SearchForm initialQuery="graphs" onSubmit={vi.fn()} pending />);
    const button = screen.getByRole("button", { name: "Searching…" });
    expect(button).toBeDisabled();
  });
});
