"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useCallback, useState } from "react";

import { AppShell } from "@/components/app-shell";
import { ResultCard } from "@/components/search/result-card";
import { SearchForm } from "@/components/search/search-form";
import { ApiError, type SearchResponse, searchKnowledge } from "@/lib/api";

/**
 * Search: find a passage by meaning, then open the page it came from.
 *
 * The query lives in the URL (`/search?q=…`), so Back returns to the previous
 * search, a link can be copied, and a reload reproduces the same results. The
 * page reacts to the URL rather than owning the query itself.
 *
 * Four outcomes are deliberately distinct, because one blank results area would
 * conflate them: nothing is indexed yet, the query matched nothing, the search
 * is running, and the backend is unreachable.
 *
 * `useSearchParams` needs a Suspense boundary during prerender — the build fails
 * outright without one — so the part that reads the URL is its own component.
 */
export default function SearchPage() {
  return (
    <AppShell current="Search">
      <h1 className="text-[27px]">Search</h1>
      <p className="mt-1 max-w-[60ch] text-ink-soft">
        Find a passage by what it means, not the words it happens to use. Every result
        opens the page it came from.
      </p>

      <Suspense fallback={<p className="mt-7 text-ink-soft">Opening search…</p>}>
        <SearchView />
      </Suspense>
    </AppShell>
  );
}

type Phase = "idle" | "searching" | "done" | "error";

interface Outcome {
  phase: Phase;
  response: SearchResponse | null;
  error: string | null;
  offline: boolean;
}

const IDLE: Outcome = { phase: "idle", response: null, error: null, offline: false };

function SearchView() {
  const router = useRouter();
  const params = useSearchParams();
  const query = params.get("q")?.trim() ?? "";

  const [outcome, setOutcome] = useState<Outcome>(IDLE);
  /** Which query the current outcome belongs to, so a stale one is ignored. */
  const [settledFor, setSettledFor] = useState<string>("");

  // Deriving from the URL during render rather than syncing in an effect: React
  // 19 rejects a synchronous setState inside an effect body, and the query
  // changing is a render-time fact, not an external event.
  const stale = settledFor !== query;

  const run = useCallback((next: string) => {
    setSettledFor(next);
    if (next === "") {
      setOutcome(IDLE);
      return;
    }
    setOutcome({ phase: "searching", response: null, error: null, offline: false });
    searchKnowledge(next).then(
      (response) => {
        setOutcome({ phase: "done", response, error: null, offline: false });
      },
      (cause: unknown) => {
        setOutcome({
          phase: "error",
          response: null,
          error:
            cause instanceof ApiError ? cause.message : "Something went wrong searching.",
          offline: cause instanceof ApiError && cause.isOffline,
        });
      },
    );
  }, []);

  // The URL is the trigger. Kicking the search off from render-time state means
  // no effect writes state synchronously, which is what React 19 objects to.
  if (stale) {
    run(query);
  }

  const submit = useCallback(
    (next: string) => {
      // Navigating rather than fetching is what keeps the query in the URL.
      router.push(`/search?q=${encodeURIComponent(next)}`);
    },
    [router],
  );

  const { phase, response, error, offline } = outcome;
  const results = response?.results ?? [];
  const searchedFiles = response?.searched_files ?? 0;
  const nothingIndexed = phase === "done" && searchedFiles === 0;
  const noMatches = phase === "done" && !nothingIndexed && results.length === 0;

  return (
    <>
      {/* Keyed on the query so the field follows the URL by remounting, rather
          than through an effect that copies the prop into state. */}
      <SearchForm
        key={query}
        initialQuery={query}
        onSubmit={submit}
        pending={phase === "searching"}
      />

      {/* Results arrive without a page change, so the count is announced. */}
      <p role="status" aria-live="polite" className="sr-only">
        {phase === "searching"
          ? `Searching for ${query}.`
          : phase === "done"
            ? `${results.length} ${results.length === 1 ? "result" : "results"} for ${query}.`
            : ""}
      </p>

      {phase === "idle" && (
        <div className="mt-7 rounded-lg border border-dashed border-edge-strong bg-card px-6 py-12 text-center">
          <p className="font-display text-lg">Ask your library something</p>
          <p className="mx-auto mt-1 max-w-[46ch] text-[13.5px] text-ink-soft">
            Noye compares meaning, so a question in your own words will find the right
            passage even when it shares no keywords with it.
          </p>
        </div>
      )}

      {phase === "searching" && <p className="mt-7 text-ink-soft">Searching your library…</p>}

      {phase === "error" && (
        <div className="mt-7 rounded-lg border border-fail bg-fail-wash px-4 py-4">
          <p className="font-semibold text-fail">{error}</p>
          <p className="mt-1 text-[13px] text-fail">
            {offline
              ? "Noye keeps your files on this machine, so its backend has to be running."
              : "Searching needs the local model and the vector index. Both run on this machine."}
          </p>
          <button
            type="button"
            onClick={() => run(query)}
            className="mt-3 min-h-11 rounded-md bg-fail px-4 text-[13.5px] font-semibold text-canvas md:min-h-0 md:py-2"
          >
            Try again
          </button>
        </div>
      )}

      {nothingIndexed && (
        <div className="mt-7 rounded-lg border border-edge-strong bg-card px-6 py-10 text-center">
          <p className="font-display text-lg">Nothing is searchable yet</p>
          <p className="mx-auto mt-1 max-w-[46ch] text-[13.5px] text-ink-soft">
            Search covers files that have finished indexing. Add something to your library,
            or wait for a file that is still processing.
          </p>
          <a
            href="/library"
            className="mt-3 inline-block min-h-11 rounded-md border border-edge-strong px-4 py-2.5 text-[13.5px] font-semibold text-accent-ink hover:bg-brand-wash md:min-h-0"
          >
            Go to your library
          </a>
        </div>
      )}

      {noMatches && (
        <div className="mt-7 rounded-lg border border-edge-strong bg-card px-6 py-10 text-center">
          <p className="font-display text-lg">Nothing matched that</p>
          <p className="mx-auto mt-1 max-w-[46ch] text-[13.5px] text-ink-soft">
            Searched {searchedFiles} {searchedFiles === 1 ? "file" : "files"}. Try
            describing what you are after differently, or in more words.
          </p>
        </div>
      )}

      {phase === "done" && results.length > 0 && (
        <section aria-labelledby="results-heading" className="mt-7">
          <p
            id="results-heading"
            className="mb-2.5 text-[11px] font-bold uppercase tracking-[0.09em] text-ink-faint"
          >
            {results.length} {results.length === 1 ? "passage" : "passages"} from{" "}
            {searchedFiles} {searchedFiles === 1 ? "file" : "files"}
          </p>
          <ul>
            {results.map((hit, index) => (
              <ResultCard
                key={`${hit.file_id}:${hit.chunk_index}`}
                hit={hit}
                rank={index + 1}
              />
            ))}
          </ul>
        </section>
      )}
    </>
  );
}
