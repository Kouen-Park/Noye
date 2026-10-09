import { act, fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";
import SearchPage from "@/app/search/page";
import { searchKnowledge, type SearchResponse } from "@/lib/api";

const nav = vi.hoisted(() => ({ query: "q=alpha", push: vi.fn() }));
vi.mock("next/navigation", () => ({ useRouter: () => nav, useSearchParams: () => new URLSearchParams(nav.query) }));
vi.mock("@/lib/api", async get => ({ ...await get<typeof import("@/lib/api")>(), searchKnowledge: vi.fn() }));
function deferred<T>() { let resolve!: (value: T) => void; let reject!: (reason: unknown) => void; const promise = new Promise<T>((a,b) => { resolve=a; reject=b; }); return { resolve, reject, promise }; }
function result(query: string): SearchResponse { return { query, searched_files: 1, results: [{ content: `${query} passage`, file_id: query, file_name: `${query}.txt`, chunk_index: 0, page_number: null, score: 1 }] }; }
beforeEach(() => { vi.clearAllMocks(); nav.query="q=alpha"; });
it.each(["resolve", "reject"] as const)("ignores an obsolete search %s after URL navigation", async settle => {
  const alpha = deferred<SearchResponse>();
  vi.mocked(searchKnowledge).mockReturnValueOnce(alpha.promise).mockResolvedValueOnce(result("beta"));
  const view = render(<SearchPage />);
  const signal = vi.mocked(searchKnowledge).mock.calls[0][1]?.signal;
  nav.query="q=beta"; view.rerender(<SearchPage />);
  await screen.findByText("beta passage");
  await act(async () => { if (settle === "resolve") alpha.resolve(result("alpha")); else alpha.reject(new Error("obsolete error")); });
  expect(signal?.aborted).toBe(true);
  expect(screen.getByText("beta passage")).toBeInTheDocument();
  expect(screen.queryByText("alpha passage")).not.toBeInTheDocument();
  expect(screen.queryByText("Something went wrong searching.")).not.toBeInTheDocument();
});
it("allows an explicit repeat search to refresh the same query", async () => {
  vi.mocked(searchKnowledge).mockResolvedValue(result("alpha"));
  render(<SearchPage />); await screen.findByText("alpha passage");
  fireEvent.click(screen.getByRole("button", { name: "Search" }));
  await screen.findByText("alpha passage");
  expect(searchKnowledge).toHaveBeenCalledTimes(2);
});
