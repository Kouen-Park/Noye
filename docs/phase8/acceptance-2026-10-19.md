# Phase 8 acceptance — 2026-10-19

This record covers October 19–20 and continues [the October 17 record](acceptance-2026-10-17.md) on
`feat/mvp-end-to-end`. Known factual-quality failures remain open; **this record
is not Phase 8/MVP completion or final merge acceptance**.

## Structured thinking compatibility

The interrupted October 17 thinking experiment retained only three completed
judgments. The non-thinking positive control returned valid JSON; both thinking
requests returned an empty final `response` despite HTTP 200, `done: true` and
`done_reason: stop`. Their separate reasoning fields contained JSON-shaped text.
That text was correctly refused as an absent final answer, not accepted as a
semantic judgment. The process and dedicated service were no longer running when
work resumed. The intended sixteen-case comparison was not completed.

A separate October 19 matrix uses one known positive control with the exact same
system text, user payload, schema, 8,192 context/3,072 output settings and installed
`qwen3.5:4b`, through dedicated loopback Ollama **0.34.2**. Endpoint and thinking
configuration vary; original evidence is unchanged.

| Endpoint | Thinking | Final JSON | Observed seconds |
| --- | --- | --- | ---: |
| generate | off | Valid; 478 characters; expected positive | 28.926 |
| chat | off | Valid; same 478-character final response | 5.440 |
| chat | on | Valid; 604 characters; expected positive | 89.837 |
| generate | on | Empty; reasoning is not a final answer | 8.168 |

Load/cache state differs across these sequential calls; this is **not a controlled
latency comparison**, a general endpoint benchmark or a factual-quality suite.
It establishes an observed compatibility difference on this runtime/model. No
internal Ollama root cause is claimed. The [official thinking API contract](https://docs.ollama.com/capabilities/thinking)
separates chat `message.content` from `message.thinking` and generate `response`
from `thinking`.

Commit `0b7368e` shares endpoint/payload construction between source-document and
Wiki structured stages. Configured thinking selects chat before the single request
and validates only final `message.content`. Non-thinking keeps generate with the
same system/prompt/schema/options. There is no automatic retry, provider fallback
or promotion of reasoning into accepted output. Existing completion, strict schema,
reference and publication checks remain. Prompt identities are now
`source-document-v24` and `wiki-grounded-v8`; the default thinking setting remains
false. This compatibility fix by itself does not close factual-quality failures.

Commit `c714e79` makes the existing evaluation recorder recognize tasks inside chat
user messages without changing requests, responses or validation. It previously
would have recorded those calls as `unknown` after the endpoint change.

## Automated and packaged checks

- Local transport/source-document/Wiki focus: **108 passed, 8 warnings in 2.40 s**.
  Tests cover correct endpoint selection, final-content-only validation, refusal
  of reasoning-only/empty/malformed answers, preflight ordering, owned clients
  bypassing inherited proxies and refusing redirects for both structured services.
- Evaluation recorder: **10 passed, 7 warnings in 0.60 s**. Chat task recognition
  preserves exact wire requests/responses; malformed or multimodal content remains
  `unknown` rather than changing transport behavior.
- Changed-file Ruff, formatting and diff checks passed.
- The first focus command ran without local socket permission: **95 passed,
  1 failed, 8 errors**, all failing/erroring cases at test-server bind. The same
  suite under the permitted execution context passed **104 tests**; four further
  thinking/proxy regressions produced the final 108 count. Product assertions were
  not relaxed.

## Actual paired judgment comparison

The fixed suite has four new controls (explicit means, independent purpose,
Korean six-day translation and observed count versus budget), followed by four
known failures/controls (the saved unsafe comparison, unsafe Wiki summary,
four-day translation and adjoining daily backups). Each is evaluated under both
production configurations: non-thinking generate and thinking chat, with identical
system/user/schema/options and counterbalanced pair order. This compares usable
configurations, not thinking alone independently of transport.

A turn interruption ended the first run after one completed non-thinking result.
That result is retained; explicit continuation resumes only missing completed keys.
An in-flight request lost during interruption is not counted as a completed
judgment. Request-start events are now recorded before transport so another
interruption cannot be mistaken for a completed model decision. No product job is
automatically retried and no document is published by these component controls.

All sixteen judgments completed. Exact system, user payload, schema, model and
options match within each pair; endpoint and thinking configuration differ.
The checks compare final answers with labels fixed before calls, separately from
JSON validity. The four new cases all matched in both modes. Known failures did
not resolve:

| Production configuration | Valid final answers | Correct out of 8 | New controls | Known regressions | Sum of row seconds |
| --- | ---: | ---: | ---: | ---: | ---: |
| generate, thinking off | 8 | 4 | 4/4 | 0/4 | 153.321 |
| chat, thinking on | 7 | 5 | 4/4 | 1/4 | 652.821 |

Both configurations falsely approved the saved comparison's unsupported
instrumental link between stored volume and append-only log files. Non-thinking
also approved the saved Wiki SQLite-to-capacity implication; thinking reached the
3,072-token output limit after 198.031 s and was correctly refused as incomplete.
That refusal is **not a correct negative semantic judgment**. Thinking corrected
the faithful four-day translation, while both modes falsely rejected ordinary
adjoining-sentence subject continuity for Gannet's daily backups.

The resumed portion took 762.772 s; all completed rows sum to 806.142 s including
the retained initial row. Interrupted in-flight work is excluded. Pair order was
counterbalanced, but load/cache state and an external model download were not
controlled, so these sums are observations, not a causal latency benchmark.
There was no document publication, automatic product retry or default-setting
change. The QA model was explicitly unloaded and `/api/ps` returned no models.

## Latest packaged validation

At source commit `c714e79`, with model inference unloaded and unit tests using
the normal default environment:

- Full backend: **1,122 passed, 19 skipped, 27 warnings in 23.25 s**.
  Product-only coverage, excluding test code and frozen subprocesses:
  **6,500/7,583 lines (85.718%)** and **1,692/2,176 branches (77.757%)**.
  Dependency notices and garbage-collected unclosed SQLite warnings remain;
  no leak-free or peak-memory claim is made.
- Full backend Ruff passed. Frontend and Rust sources are unchanged; the prior
  387 frontend and 14 Rust results retain their earlier scope and limitations.
- PyInstaller: **31.784 s**. Native app bundle: **21.165 s**.
  Strict local signature integrity passed under the existing development QA
  profile, which does not establish trusted distribution/notarization.
- Actual bundled backend: **12 passed, 7 warnings in 45.19 s**. Embedded Python
  modules contain `source-document-v24` and `wiki-grounded-v8`.
  Bundled backend SHA-256:
  `0cd951fe8f65984e7630156de72152a802bba4d496191544a11c711f64495549`.

No new native window/export observation is claimed from these automated package
checks. The earlier physical IME/VoiceOver, removable storage/sleep, native
active-token force-quit, representative retrieval calibration, authorized cloud
quality/latency and trusted distribution limits remain.

## Alternative local model diagnostic

A new QA-only store on port 11459 downloaded the official local
[`gemma4:e2b-it-qat`](https://ollama.com/library/gemma4:e2b-it-qat) model.
The manifest is
`07ea59a474013479c8b6b802bef095c40e964a1d776ba02f264c0e30e1aede0c`;
its layers total 4,336,357,640 bytes. Official licence/size information was checked
before download. The [official model overview](https://ai.google.dev/gemma/docs/core)
notes that memory depends on the engine and context; catalogue information does
not establish suitability or factual quality on this 8 GiB M2.

The personal model store, default model/provider and user data are unchanged.
The diagnostic uses the same fixed eight cases and unchanged v24 production
non-thinking contract, with model-specific inherited sampling parameters.
It is not a new holdout suite or whole-document/Wiki acceptance.
All eight returned valid final JSON; **6/8** matched labels in **49.700 s**.
The four-day translation and adjoining-subject claims were accepted correctly,
but the same two unsupported comparison/Wiki links were falsely approved.
No model change is adopted from this result.

A candidate prompt appended balanced, unrelated synthetic examples distinguishing
conjunction from instrumental links and normal adjoining-sentence subject
continuity. It ran on the alternative model against these eight prior controls
and eight further controls fixed before candidate inference. The unchanged
production transport/schema/validator returned **16 valid, 14/16 correct**:
prior controls **6/8**, new controls **8/8**, in **90.720 s**. The same two unsafe long claims
remained falsely approved. The new subset has no paired baseline and does not
establish a measured improvement. The candidate was not adopted.

A final focused diagnostic checks only causal/instrumental links in the long
claims and their isolated fragments. It changes the experimental prompt/schema,
not product behavior or factual acceptance. Across eight intended cases, four
returned valid decisions and only three matched labels. One local HTTP 500 and
three non-verbatim extracted-link failures remain failures, not correct refusals.
The dedicated server logged a timeout waiting for its model runner to start;
no memory/root-cause conclusion follows from that log.
The isolated English storage/log-file link still received a valid false approval.
The isolated Korean SQLite link was correctly rejected, which does not establish
a reliable general guard. This protocol is also not adopted.

## Evidence and cleanup

Curated synthetic evidence is published under
[`evidence/2026-10-19/publication.json`](evidence/2026-10-19/publication.json).
The index records raw/published hashes, byte lengths and transformations.
Exact model requests and final answer strings are retained. Separate reasoning,
generate token-context arrays and repeated successful preflight bodies are
omitted with hashes; they are not promoted to evidence or product answers.
Runtime databases, backups, weights, credentials, environment files and private
browser content are excluded. October 17 published evidence is unchanged.

Both dedicated services were verified unloaded, identified by their listening
ports and process names, then stopped. The model installed solely in the new QA
store was deleted through that service and the store reported no models.
Ports 11439/11459 had no listener afterward. The personal 11434 service and
personal weights were not managed by this cleanup.

## Remaining acceptance

Known P1 unsupported relationships and false contradiction classifications remain
open. Successful transport, tests, packaging or safe refusal do not establish
successful factual generation. Phase 8/MVP and conditional final merge remain open.
