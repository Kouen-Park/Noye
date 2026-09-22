import { CheckIcon, CrossIcon } from "@/components/icons";
import type { FileStatus } from "@/lib/api";
import { STAGE_COUNT, stageLabel, stageNumber, statusWord } from "@/lib/status";

/**
 * A file's state as a word, an icon, and — only then — a colour.
 *
 * Ready carries no colour on purpose: it is the resting state of almost every
 * file, and colouring it would drown the one card that needs a decision
 * (DESIGN.md §3). The same section explains why colour is never the only
 * channel: oxblood and the brand green measure 1.01:1 against each other, and
 * red against green is the worst pair for the commonest colour blindness.
 */

export function StatusPill({ status, error = null }: { status: FileStatus; error?: string | null }) {
  const word = statusWord(status, error);
  const shared =
    "inline-flex items-center gap-1 rounded-full py-[3px] pl-[6px] pr-2 text-[11px] font-bold";

  if (status === "READY") {
    return (
      <span className={`${shared} border border-edge-strong font-semibold text-ink-soft`}>
        <CheckIcon className="h-3 w-3" />
        {word}
      </span>
    );
  }

  if (status === "FAILED") {
    if (word === "Stopped" || word === "Interrupted") {
      return (
        <span className={`${shared} border border-edge-strong text-ink-soft`}>
          <CrossIcon className="h-3 w-3" />
          {word}
        </span>
      );
    }
    return (
      <span className={`${shared} bg-fail-wash text-fail`}>
        <CrossIcon className="h-3 w-3" />
        {word}
      </span>
    );
  }

  return (
    <span className={`${shared} bg-busy-wash text-busy`}>
      <Spinner />
      {word}
    </span>
  );
}

/**
 * A ring that turns while work is happening.
 *
 * Under `prefers-reduced-motion` the global rule in globals.css runs the
 * animation to completion instantly, leaving a static ring. No meaning is lost,
 * because the word beside it says "Indexing".
 */
function Spinner() {
  return (
    <span
      aria-hidden="true"
      className="noye-spin h-[10px] w-[10px] rounded-full border-[1.5px] border-edge-strong border-t-current"
    />
  );
}

/**
 * The four stages of ingestion as four segments.
 *
 * Exposed as a real progressbar so the stage is available to assistive
 * technology, not only to the eye. `aria-valuetext` carries the sentence rather
 * than the bare number, because "step 3 of 4" alone does not say of what.
 */
export function StageBar({ status }: { status: FileStatus }) {
  const step = stageNumber(status);
  if (step === null) return null;
  const label = stageLabel(status);

  return (
    <div className="mt-2.5">
      <div
        role="progressbar"
        aria-valuemin={0}
        aria-valuemax={STAGE_COUNT}
        aria-valuenow={step}
        aria-valuetext={label}
        className="flex gap-[5px]"
      >
        {Array.from({ length: STAGE_COUNT }, (_, index) => {
          const position = index + 1;
          const done = position < step;
          const now = position === step;
          return (
            <span
              key={position}
              className={`h-[3px] flex-1 rounded-sm ${
                done ? "bg-accent" : now ? "noye-pulse bg-accent" : "bg-edge-strong"
              }`}
            />
          );
        })}
      </div>
      <p className="mt-1.5 text-[12.5px] text-accent-ink">{label}</p>
    </div>
  );
}
