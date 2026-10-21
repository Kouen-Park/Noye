# Phase 8 follow-up — 2026-10-21

This continues [the October 21 record](acceptance-2026-10-21.md) on
`feat/mvp-end-to-end`. The owner requests completing the remaining work and then
merging. Known quality failures and incomplete acceptance remain; **no final
merge or Phase 8/MVP completion is claimed**.

## Native document loading and creation fix

Native observations exposed an initial `Nothing written yet` display while saved
documents were still loading, and repeated New actions created two blank QA
documents without pending feedback. `1521748` separates pending, failed and empty
lists, adds an explicit list retry, shows an opening state for a known document,
and disables New with `Creating…` while its request is pending. A synchronous
request guard prevents repeated clicks before React commits the disabled state.
Older list responses cannot replace a newer refresh after creation. Existing
writing/editing and saved documents remain unchanged.

Six deferred-request regressions cover initial loading, failure/retry, repeated
creation, stale list responses, opening a selected document and explicit creation
retry after failure. Document focus: **22 passed in 2.14 s**. The first test-edit
invocation used the wrong working-directory-relative path and did not add the six
new tests; its **16-test** result is retained separately, not counted as their
validation. The corrected invocation includes them.

The first full frontend run passed 393 tests/types but failed the React
`set-state-in-effect` lint rule: the initial effect called the same synchronous
loading-state setter as an explicit refresh. Initial loading already starts true;
its fetch is now separate from explicit refresh feedback. The corrected full run
passed **393 tests across 52 files in 10.433 s** (Vitest reports 9.91 s), TypeScript
**1.601 s**, full ESLint **3.940 s**, and desktop static build **40.607 s**.
No linter rule or product assertion was disabled.

The updated native bundle built offline in **21.883 s** and strict local ad-hoc
signature integrity passed. Its sidecar SHA-256 remains
`dd6450e6a7ac9d3122612ae8ef0e4a0400de03fd3a477786d9f99fb295a597aa` before/after,
so the prior v27/v13 full backend and twelve actual frozen-sidecar checks retain
their scope; they were not redundantly rerun. Native executable SHA-256 is
`ff71892baa4c274e48c71b5e26f22cef2b93eb4df80b921d28f7e7330079a0f6`.
This is development signing, not trusted distribution.

## Rejected relationship protocol

Six new controls were fixed before calls, including English/Korean common facts
with additional unrelated details, a real contradictory rule sharing an incidental
lamp detail, unrelated subjects and different conditions. Production v13 matched
**5/6** in **131.666 s**: the incidental common detail hid a genuine import-rule
contradiction. This new failure remains applicable alongside the prior common-fact
omission; the previous 16/17 result is not relabeled as general acceptance.

A temporary candidate added explicit overlap and contradiction-priority guidance.
All six new controls passed and the old Sedum omission was corrected, but the
retained Nasturtium exception became a false contradiction. After **12 completed
valid judgments / 11 rubric matches**, the experiment was interrupted rather than
adopted. One subsequent case had started without a completed judgment; ten cases
were never started. The decision record distinguishes all three states. No rubric,
confidence threshold, product prompt, model setting or existing saved relation
was changed to hide the failure. Production remains Wiki v13, thinking off.

## Native termination and saved writing

The existing QA-only Qdrant container on loopback 6339 was restarted after checking
its name, endpoint and storage. Its old vector collection was missing. A native
stored-index check correctly reported all six missing passage sets. Explicit
rebuild processed the available AT-201 PDF; five folder sources were honestly
skipped because folder processing was disabled/unavailable. This is one-source
search recovery, not a new successful six-source restore.

A native document titled `Phase 8 native interruption QA` was saved with Korean,
English, literal Markdown punctuation, `37 리터`, `café` and a unique sentinel. The
UI reported Saved, and a read-only backend API snapshot confirmed the exact stored
body before termination.

Actual native chat against AT-201 generated runner progress through **623 tokens**
and completed **663 tokens** at **14:28:06**. The OS Command-Option-Shift-Escape
shortcut was requested at **14:28:17.743**, after generation had completed. The old
native/sidecar PIDs disappeared and a new app instance opened, but **this is not
an accepted active-generation force-quit test**. The original non-streaming request
was not changed to streaming merely to create a token marker; the initial stream-
only marker watcher could not certify it. Runner progress excerpts and exact
native-action timing preserve this unsuccessful synchronization.

After native restart and the updated UI rebundle, the same document opened with
its title, all literal Korean/English lines and sentinel, and `All changes saved`.
Native UI preservation passed. A post-relaunch API hash comparison was blocked by
sandbox `Operation not permitted`, so byte-for-byte post-termination equality is
not claimed. Initial shell-only/blank observations are retained: a clean restart
showed the actual workspace, and the newly rebuilt package subsequently showed
its real chat UI and saved document. No permanent blank-window cause or resolution
is asserted.

## Approval-review blocker and evidence

The owned QA server was moved from 11439 to 11440 to prepare a byte-preserving
observation relay at the unchanged application endpoint. Restarting the revised
relay was **not executed**: automatic approval review failed because its usage
limit was reached, with a stated retry time of **4:25 PM**. The tool explicitly
identified a review failure, not a determination that the action was unsafe.
The app's native Services panel exposes no custom endpoint editor, so the proposed
direct-upstream alternative could not be completed there. No sandbox bypass,
unreviewed server launch or private-preference-file mutation was attempted.

The QA app correctly reports the unavailable 11439 endpoint. The upstream QA
process on 11440 and the restarted QA Qdrant container still require verified
cleanup; no post-block unload/stop success is claimed. Personal Ollama/Docker
containers and model files were not changed. Existing model weights were read
without pull/delete. The active-token native test, further model experiments and
remote Git publication await reviewed execution access; the known quality failures
would still prevent conditional final merge even after that access returns.

The [publication index](evidence/2026-10-21-followup/publication.json) binds **39
files / 424,402 bytes**, plus the index, with raw/published hashes and transformations.
All hashes, strict JSON/JSONL, inventory and common credential-pattern checks pass.
Exact completed final answers/requests and interrupted events remain. Separate
reasoning/token-context arrays and repeated successful preflight details are
omitted with hashes; runtime databases, backups, weights, environment files and
private content are excluded. Earlier frozen evidence is unchanged.

- [Relationship decision](evidence/2026-10-21-followup/model/candidate-decision.json)
- [Frontend results](evidence/2026-10-21-followup/checks/frontend-checks-corrected.json)
- [Native package](evidence/2026-10-21-followup/checks/native-ui-build.json)
- [Termination timing](evidence/2026-10-21-followup/checks/native-first-attempt.json)
- [Saved-writing UI review](evidence/2026-10-21-followup/checks/native-recovery-review.json)
- [Review blocker](evidence/2026-10-21-followup/checks/approval-block.json)

General entailment/relationship quality, representative retrieval calibration,
physical IME/VoiceOver/removable storage/sleep, authorized cloud evaluation and
trusted signing/notarization/another-device checks remain open as previously
recorded. None is passed by the document UI fix or saved-writing observation.
