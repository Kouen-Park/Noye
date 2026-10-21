# Phase 8 native interruption follow-up — 2026-10-21

This continues [the preceding follow-up](acceptance-2026-10-21-followup.md) on
`feat/mvp-end-to-end`. It records the native parent-exit defect, its fix and
subsequent checks. The owner's authorization is to finish the remaining work and
then merge. Known P1 factual/relationship failures and incomplete final acceptance
remain; this record does not declare Phase 8/MVP completion or authorize an early
merge.

## Bounded managed-backend shutdown

Read-only PID and Ollama runner observations established an actual native OS force
quit during generation. Before the fix, native PID 76228 disappeared while the
runner was generating: 159 tokens preceded parent exit and 218 followed it. Both
managed sidecar processes remained until the model finished, with the last one
exiting **22.034 seconds after the native parent**. The earlier shortcut after a
completed answer remains a failed synchronization attempt, not another active
termination pass.

`aa9335f` starts a daemon **15-second** self-exit deadline when the private parent
stdin protocol receives shutdown or EOF. Normal ingestion cancellation and
Uvicorn's graceful shutdown still run first. The deadline also covers an AnyIO
worker keeping Python alive after its event loop has closed; returning from the
loop must not cancel it. It exits only its own managed backend, without killing
an external service by name or port. This matches the existing native parent's
16-second fallback when the parent survives to enforce it.

The last-resort exit can roll back an uncommitted transaction; it does not promise
to save in-progress edits. Durable jobs recover on the next startup. A production
entry-point subprocess regression holds an uncommitted document replacement in a
real synchronous FastAPI/AnyIO worker indefinitely, closes parent stdin, requires
exit within 18 seconds and reopens the workspace to compare the entire previously
saved document response. The corrected AnyIO focus passed **13 tests, 7 warnings
in 28.16 seconds**. The earlier executor variant is retained separately.

The rebuilt native app was then force-quit during another unchanged, non-streaming
AT-201 request: 588 generated tokens preceded native PID 77971's exit and 636
followed it. Both sidecars disappeared, the last **6.285 seconds after the parent**.
The runner became idle 4.392 seconds after the parent. Consequently this sample
shows active native termination and exit within the bound, **not** that the new
15-second timer fired, nor a causal 22-to-6-second performance improvement. The
indefinitely blocked AnyIO regression tests the actual deadline; frozen-entry
inspection separately proves that the rebuilt bundle contains it.

After native restart, the UI showed the complete saved Korean/English document,
literal Markdown, `37 리터`, `café`, sentinel and Saved status. A read-only native
backend API comparison confirmed **full before/after JSON equality**, SHA-256
`94911980fa07c9eeee0b901f92e379bc36513e99e6f742cee7d1a097006e5cfe`.
The separately owned QA Ollama and Qdrant endpoints both remained healthy, as
expected for external services. No automatic document-generation resume was
started by this comparison. Restart timing and memory consumption were not
benchmarked.

The expanded sidebar was rechecked with five conversations: the conversation
list scrolled independently while the composer and footer remained visible.
An earlier incomplete view was not a reproducible layout defect, so no speculative
CSS change was made. Document loading/creation fixes from `1521748` remain in the
bundle; native Opening document and Saved states were observed.

## Current-code verification

At `aa9335f`, full backend validation passed **1,163 tests, 19 skipped, 24 warnings
in 40.26 seconds** (runner 40.853 seconds). Ruff passed for `app`, and separate
lint/format checks passed for the root desktop entry and new regression. Coverage
still measures `app` only, excluding tests/frozen subprocesses and root
`desktop.py`: **6,594/7,676 statements (85.904%)**, **1,728/2,212 branches (78.119%)**.
Warnings remain in the logs; no leak-free claim is made.

After dedicated model unload, PyInstaller took **31.309 seconds**, native bundling
**21.079 seconds** and strict ad-hoc signature verification passed. Actual bundled
backend checks passed **12 tests, 7 warnings in 46.31 seconds**. The sidecar SHA-256
is `30a6eb28e93947f3fb3904069b9bd1c26f5c2eff79aad7d4cc674032867aa7e3`.
Archive inspection confirms source-document v27/Wiki v13 and executable entry-point
equivalence to the current source, including the 15-second binding.

The initial entry-verifier incorrectly expected literal 15 in `co_consts`; Python
3.14 emits `LOAD_SMALL_INT`. Its full executable-signature comparison had already
passed. The corrected standalone verifier also checks the instruction preceding
the binding. Both methods and the initial error are retained. This correction did
not change product code or retroactively add an assertion to the already executed
build helper.

Frontend code has not changed since the preceding **393 tests / 52 files**,
TypeScript, ESLint and static desktop build passed. Earlier 14-test Rust checks
retain their scope. These are development QA packages, not Developer ID signing
or notarized distribution.

## Published evidence

The [publication index](evidence/2026-10-21-native/publication.json) binds **41 files
/ 155,773 bytes**, plus the index. All published hashes, strict JSON/JSONL, exact
file inventory and common credential-pattern checks passed. Full app-coverage
instrument output stays local; its scope and totals are retained in the analysis.
Runtime databases, backups, weights, environment files and build binaries are
excluded. Earlier frozen evidence is unchanged.

- [Native token/PID analysis](evidence/2026-10-21-native/checks/native-analysis.json)
- [Before-fix observation](evidence/2026-10-21-native/before/native-process-observation.json)
- [After-fix observation](evidence/2026-10-21-native/after/native-process-observation.json)
- [Saved-writing equality](evidence/2026-10-21-native/after/saved-writing-review.json)
- [Backend checks](evidence/2026-10-21-native/checks/checks.json)
- [Actual bundle checks](evidence/2026-10-21-native/checks/build-review.json)
- [Frozen-entry proof](evidence/2026-10-21-native/checks/entry-verification.json)
- [Rejected thinking diagnostic](evidence/2026-10-21-native/checks/thinking-decision.json)
- [Verified service cleanup](evidence/2026-10-21-native/checks/cleanup-services.json)

## Review access and QA service ownership

The preceding automatic approval-review usage-limit failure is historical.
Reviewed execution subsequently returned. The rejected revised relay was never
launched; its unloaded temporary upstream was stopped. An official Ollama server
was restored directly at the unchanged QA endpoint 11439, using existing weights,
so no sandbox bypass or custom relay was needed. Port 11440 was later confirmed
unavailable. The personal Ollama endpoint on 11434 and unrelated Docker containers
were not changed. No weights were pulled or deleted.

The six-source restore acceptance from the earlier record is not repeated here:
this workspace's explicit rebuild recovered the available AT-201 source while
five folder sources were honestly skipped as disabled/unavailable.

After validation, model unload returned 200 and the loaded-model list was empty.
The exact owned QA Ollama PID and QA Qdrant container were verified and stopped;
11439, 11440 and 6339 no longer accepted connections. The QA app and both managed
sidecars were also confirmed gone. The final CUA connection failed to start twice,
so app cleanup used SIGTERM after checking its exact QA executable and PID. This
is lifecycle cleanup, not another native UI/force-quit acceptance pass. No app data,
model weights or container storage was removed.

## Thinking-only relationship diagnostic

Four fixed difficult controls used the unchanged production v13 system/schema
with thinking enabled only in the diagnostic process and a 3,072-token output
budget. One returned judgment matched its exception rubric in **268.483 seconds**.
The other three semantic requests hit the existing 300-second read timeout without
a final judgment: **301.768, 303.893 and 309.351 seconds** per attempted case,
including preflight/overhead. Total elapsed time was **1,185.647 seconds**. This is
one valid matching semantic judgment and three incomplete attempts, not four
semantic passes or a successful correction of the known production failures.

The QA native app still polled model tags until cleanup during the last case.
Inference was sequential and no heavy build/test ran concurrently, but these
observations are not an isolated performance comparison. The real runner log
records cancellation at the final timeout. Exact requests, the one final answer,
errors and diagnostic method are retained; separate reasoning is omitted with
hashes. Thinking is not adopted, timeouts are not hidden by retries, and normal
RAG/default generation remains non-thinking.

## Remaining acceptance

Production remains source-document v27/Wiki v13 with default thinking off.
The preceding fresh relation set matched 5/6, retaining the true contradiction
hidden by an incidental common fact. The rejected candidate's exception false
contradiction and the production common-fact omission remain recorded. General
entailment audits can still approve unsupported claims. Passing JSON, confidence
and narrow literal guards do not establish semantic correctness.

Representative retrieval/quality calibration, physical IME/VoiceOver/removable
storage/sleep, remaining mutation/adoption/failure paths, dedicated authorized
cloud quality/latency, real Developer ID signing/notarization and another-device
trust checks remain open. This machine and its existing QA models cannot supply
the unavailable physical/distribution/cloud resources. No acceptance rubric or
confidence threshold was relaxed. The conditional final merge remains unmet.
