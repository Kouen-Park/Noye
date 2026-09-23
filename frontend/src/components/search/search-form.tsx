"use client";

import { useId, useState } from "react";

import { SearchIcon } from "@/components/icons";

/**
 * The query input.
 *
 * Submitting navigates rather than fetching directly, so the query lives in the
 * URL: Back returns to the previous search, a link can be copied, and a reload
 * shows the same results.
 *
 * The field follows the URL by being REMOUNTED — the page gives this component a
 * `key` of the current query — rather than by an effect that copies the prop into
 * state. React 19 rejects that effect outright, and the remount is the pattern
 * React's own guidance points at: the query is this component's identity, not
 * something it synchronises with.
 *
 * A real `<form>`, so Enter submits without a keydown handler and the button is a
 * submit button rather than a click handler on a div.
 */

interface SearchFormProps {
  /** The query in the URL. Seeds the field; changing it should remount. */
  initialQuery: string;
  onSubmit: (query: string) => void;
  pending: boolean;
}

export function SearchForm({ initialQuery, onSubmit, pending }: SearchFormProps) {
  const inputId = useId();
  const [value, setValue] = useState(initialQuery);

  return (
    <form
      role="search"
      onSubmit={(event) => {
        event.preventDefault();
        const query = value.trim();
        if (query === "") return;
        onSubmit(query);
      }}
      className="mt-1"
    >
      <label htmlFor={inputId} className="block text-[13px] font-semibold text-ink-soft">
        What are you looking for?
      </label>

      <div className="mt-1.5 flex flex-wrap gap-2">
        <div className="relative flex min-w-0 flex-1 items-center">
          <SearchIcon className="pointer-events-none absolute left-3 h-4 w-4 text-ink-faint" />
          <input
            id={inputId}
            type="search"
            value={value}
            onChange={(event) => setValue(event.target.value)}
            placeholder="Ask in your own words, not keywords"
            autoComplete="off"
            className="min-h-11 w-full rounded-md border border-edge-strong bg-card pl-9 pr-3 text-[14.5px] placeholder:text-ink-faint"
          />
        </div>
        <button
          type="submit"
          disabled={pending || value.trim() === ""}
          className="min-h-11 rounded-md bg-brand px-5 text-[13.5px] font-semibold text-ink-inverse disabled:cursor-not-allowed disabled:opacity-60"
        >
          {pending ? "Searching…" : "Search"}
        </button>
      </div>
    </form>
  );
}
