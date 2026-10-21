# Phase 8 acceptance — 2026-10-21

This continues [the October 19–20 record](acceptance-2026-10-19.md) on
`feat/mvp-end-to-end`. All inputs are invented QA sources. Known relation-quality
and remaining native/cloud/calibration/distribution checks remain open;
**this record does not establish Phase 8/MVP or final merge acceptance**.

## Changes and focused checks

- `db63997` changes Wiki claims from interpretation-first to evidence ID, exact
  original quote, then interpretation. The prompt preserves quantity properties
  and keeps independent facts separate (`wiki-grounded-v9`). Existing Wiki
  pipeline/job/database/backup focus: **32 passed, 7 warnings in 1.04 s**.
- `f330787` limits reusable Wiki topic-name hints to names present in the current
  original, preserving Unicode/case/spacing normalization and Latin word
  boundaries (`wiki-grounded-v10`). Unrelated names are omitted before batching;
  translations and aliases may still be proposed without hints. Four new
  regressions check English/Korean names, full-width Unicode and the unrelated
  Betamax prefix. Expanded Wiki focus: **60 passed, 7 warnings in 1.89 s**.
- `61608e9` renders comparison requests as source-attributed tables of assertions
  already verified against originals (`source-document-v25`). There is no later
  factual rewrite that can connect independently reported storage amounts and
  technologies. Citations retain original bytes and locations. Table content
  and filenames are escaped; a comparison with no topical section containing
  multiple sources remains explicitly partial. Non-comparison synthesis retains
  its existing verification/fallback behavior. This removes one observed unsafe
  rewrite path, not all possible extraction or model-audit errors.
- `9fc9347` adds at most one local wording-revision stage when the narrow litre
  guard rejects a capacity/stored-amount swap (`wiki-grounded-v11`). Replacement
  output must pass the same reference, verbatim quote and quantity checks before
  publication. A second rejection is terminal. Invalid references/quotes or
  unavailable/invalid model responses do not trigger revision. Cancellation
  checkpoints surround the additional call; no provider/transport fallback or
  retry was added. Successful revisions are counted in metadata.

Combined source-document/presentation and Wiki pipeline/integration/job/backup
focus: **177 passed, 8 warnings in 3.84 s**. New tests cover bounded revision,
second failure, unavailable model, forged quote, cancellation, unchanged authored
Wiki bytes/history, comparison evidence/citation preservation and partial single-
source comparisons. Ruff and formatting checks passed after formatting the new tests.

Two initial failures are retained. The comparison focus first returned **140
passed, 1 failed** because an older test required a joint model-written sentence;
it now tests the stronger relevant condition that multiple verified sources occur
in the same topical comparison, while separate one-source sections remain partial.
The combined focus first returned **175 passed, 1 failed** because a mock treated
the new `revise_section` task as a relation request and accessed a nonexistent
`target_id`. Its task dispatch now returns the same deliberately bad quantity on
both draft stages. The test still requires refusal, unchanged authored bytes and
unchanged history, and now also checks the exact two-stage bound. Product checks
were not relaxed.

## Earlier whole Wiki failures retained

Fresh v9 and v10 attempts each processed the same two original files. Both saved
faithful independent Alpha facts, removing the earlier SQLite-to-capacity
implication, but refused Beta's remaining stored-amount-to-capacity swap before
publication. Neither is complete Wiki-generation acceptance.

- v9: **88.417 s**. Beta also selected the unrelated existing Alpha topic in its
  refused response.
- v10: **73.872 s**. No Alpha hint reached Beta; the refused response proposed
  Project Beta instead. Quantity wording still failed, so hint isolation alone
  is not successful generation.

## Current whole-workflow checks

The fixed known-corpus sequence runs current production code at `9fc9347` with
qwen3.5:4b, Ollama 0.34.2, 8,192 context/2,048 output, thinking off, dedicated
loopback 11439 and read-only existing weights. Wiki, English comparison and
Korean collection run sequentially, unloading between attempts. No failed job is
resumed automatically. Request-start/return events preserve interruptions as
incomplete work rather than invented completed judgments. Heavy tests/builds do
not overlap inference.

The current whole Wiki attempt completed in **101.209 s** (104.101 s including
CLI setup/ingestion/reporting). Both saved summaries/key points were directly
reviewed against the originals:

- Alpha preserves capacity 37 litres, SQLite use, Sunday write pause and once-
  daily backup as independent facts.
- Beta preserves stores 92 litres, append-only log-file use, Sunday write
  permission and twice-daily backup. One bounded wording revision corrected its
  initial capacity swap; no unsupported instrumental link or capacity remains.
  Its tags use storage, and its project topic identifies Beta.

There were two initial summary calls and one wording-revision call, each with
local-model preflight. No relation candidate triggered inference, so this does
**not** close the retained false-contradiction findings. This is acceptance of the
inspected known Wiki corpus, not a representative fresh benchmark.

The current English comparison completed in **215.591 s** (219.283 s including
CLI setup/ingestion/reporting). All three topical tables were reviewed: storage
capacity versus amount stored and their independently stated technologies, Sunday
write pause versus permission, and once- versus twice-daily backup. There is no
invented instrumental link or numerical difference. Source citations preserve
exact original bytes/locations, with two selected/processed sources and all
120/120 and 95/95 extracted characters processed. The report is structurally
complete on this known corpus. No cross-source synthesis call occurs; the
thirteen model stages still perform discovery, extraction, original audits and
heading checks. Prior and current wall times have different load/cache histories,
so no controlled latency-improvement claim is made.

The v25 Korean collection job completed in **287.154 s** but its saved body was
**not accepted (P1)**: `프로젝트 베타는 92 리터의 용량을 저장합니다.` changes
stored amount into capacity. The old guard missed a property noun after its
quantity, and the model audit approved it. The artifact also honestly marks an
empty planned section partial and repeats schedule facts. Completion and partial
coverage do not establish factual acceptance; that artifact is retained unchanged.

Four fresh Wiki component controls completed in **129.778 s** and all final
summaries/key points were reviewed as faithful. They preserve a 46-litre capacity
with independent technology use, 28 litres stored with an inspection exception
and five-day backups (one quantity revision), an explicitly supported pump means
for storing 17 litres, and Korean inspection/read/write conditions with six-day
backups. Genuine means relationships remain allowed. These are direct synthetic
Passage inputs, not another catalogue/native run or a broad benchmark.

`3a72531` closes the observed postfix-property gap for English/Korean litre
phrases, with new positive/negative, multiple-quantity and line-boundary controls.
It also records the rejected source/synthesis stage and supplies correction data
only on an explicit retry whose current batch contains all prior originals.
Other source batches do not receive it. The failed stage cache is discarded
while valid stages can be reused. Focused source/presentation/Wiki pipeline/
integration checks: **188 passed, 8 warnings in 3.77 s**; an earlier narrow postfix
focus passed **100 tests**. Source prompt identity is v26 and Wiki v12.
`5e407dc` labels new document rendering `source-document-markdown-v4`, reflecting
the new comparison tables; older artifacts retain their existing bodies/metadata.

The fresh v26 Korean attempt refused a capacity swap before saving in **48.323 s**.
One explicit QA resume supplied correction feedback to Beta's original stage only;
it completed in **393.586 s** with faithful quantity/condition wording. It remains
**partial**, with repeated Alpha facts, duplicate neutral headings, unsupported
section topics and omitted Beta log-file detail. The first refusal and the safe
partial body are retained separately; neither is relabeled as complete delivery.

`c0ec344` addresses this plain collection-notes layout: every verified extracted
item is retained under its literal source name, with exact duplicates displayed
once and their citation labels merged. The model title still passes its checks;
speculative section topics are replaced by one neutral extraction section.
A processed source with no verified notes is explicitly named in partial-result
limits. Explicit synthesis/integration/common-theme requests and relevant reports
retain synthesis, and comparisons retain their tables. New identities are
`source-document-v27` / `source-document-markdown-v5`. Source/presentation focus:
**134 passed, 8 warnings in 3.58 s**.

The fresh v27 Korean attempt correctly refused an initial capacity swap in
**39.926 s**. One explicit QA resume completed source-grouped notes in **90.803 s**,
with no synthesis call and no presentation partial flag. Direct review confirms
faithful Beta stored amount/log-file use/Sunday permission/twice-daily backup and
Alpha capacity/Sunday pause/once-daily backup, with exact original citations.
Alpha's SQLite detail was not extracted into these notes, and the append-only
translation is awkward: this summary does not claim exhaustive fact inclusion.
The accepted known-corpus summary and its initial safe refusal remain separate;
this is not a first-attempt success or a general quality benchmark.

A no-inference replay applied each surface's actual current guards to **33**
retained final claims: accepted comparison/Wiki/fresh outputs remain valid and
the recorded unsafe v25 Korean phrase is now refused. This is guard compatibility,
not another semantic evaluation. The initial replay harness wrongly applied the
source-document numeral guard to a faithful Wiki six-day rendering; it was fixed
to use the actual Wiki ID/quote/property checks. The initial method and setup error
are retained; no product assertion was relaxed.

## Relationship classification and adopted protocol

Five new original-passage controls were fixed before any calls and combined with
twelve historical controls. Baseline v12 returned **17 valid / 11 matching**
judgments in **274.193 s**. Four exception rules were falsely called contradictions;
two required links (a shared original fact and a translated alias) were missed.

A dedicated relationship system and evidence/explanation-before-kind schema order
returned **17 valid / 16 matching**: **4/5 new** and **12/12 historical**. All four
false contradictions were corrected; all four genuine same-condition opposites
retained contradiction. Both translated-rule pairs now link. One required link is
still missed: both Sedum originals state the amber indicator fact, while one also
contains independent hourly backups. Its empty result is a failure under the
unchanged rubric, not a semantic pass or a correct refusal. Optional relationship
recall remains incomplete.

The first experiment stopped after 16 completed cases. Those exact results and
request-start events remain retained; only the missing translated case was resumed
(**27.755 s**). Completed-case durations sum to **330.974 s**, not a single uninterrupted
wall-clock benchmark. No repeated sampling or threshold reduction was used.
`relations-manual.json` compares labels and explanations against both originals;
this is primary-agent review, not an independent external evaluation.

`48fcf9d` adopts the tested system for `verify_relation` only, retains the summary/
wording-revision system and accounts for the selected system in the byte budget
(`wiki-grounded-v13`). A no-inference wire comparison proves **all 17** candidate
requests match the adopted system, constrained schema including property order,
full original payload, options and exact UTF-8 budget. It replays final JSON for
parsing only and is not another semantic judgment. Related Wiki/source regression
focus: **130 passed, 8 warnings in 3.29 s**. The initial test invocation used the
wrong interpreter path and ran no tests; the corrected invocation is retained.
A line-length lint finding was fixed without changing the tested system bytes.

## Latest automated checks

At `48fcf9d`, full backend tests passed **1,162 / 19 skipped / 24 warnings in
25.15 s** (runner 25.731 s). `ruff check app` passed. Product coverage excludes test
code and frozen subprocesses: **6,594/7,676 lines (85.904%)** and **1,728/2,212
branches (78.119%)**. Warning notices and SQLite-connection warnings are retained;
this does not establish leak-free operation. Frontend/Rust code is unchanged by
these latest fixes; prior **387 frontend / 14 Rust** and associated build/type/
format/lint results retain their earlier scope. No redundant rerun is claimed.

The rebuilt actual bundled backend passed **12 desktop/folder tests, 7 warnings in
46.61 s** (runner 47.542 s). PyInstaller took **32.726 s**, native bundling **25.049 s**,
and strict ad-hoc signature integrity passed. Archive inspection confirms
`source-document-v27` and `wiki-grounded-v13` in the actual bundled modules.
The backend SHA-256 is
`dd6450e6a7ac9d3122612ae8ef0e4a0400de03fd3a477786d9f99fb295a597aa`.
These are development QA checks, not Developer ID signing, notarization or another
native UI pass. Only the temporary QA profile disables hardened runtime; product
configuration is unchanged.

## Published evidence and cleanup

The bounded synthetic publication contains **94 files / 2,952,855 bytes**, plus
its [publication index](evidence/2026-10-21/publication.json). Every entry records
raw and published SHA-256, byte counts and transformations. All published hashes,
strict JSON/JSONL, exact file inventory and common credential-pattern checks pass.
Exact requests and final response strings remain; separate reasoning, token-context
arrays and repeated successful preflight metadata are omitted with hashes. Runtime
databases, backups, model weights, environment files and personal data are excluded.
October 17/19 evidence is unchanged.

- [Whole-workflow runner](evidence/2026-10-21/model/scenarios.json) and
  [known Wiki review](evidence/2026-10-21/model/wiki-current-manual.json).
- [Comparison review](evidence/2026-10-21/model/comparison-current-manual.json),
  [v25 collection failure](evidence/2026-10-21/model/collection-v25-manual.json),
  [v26 partial retry](evidence/2026-10-21/model/collection-v26-retry-manual.json) and
  [v27 accepted notes/limits](evidence/2026-10-21/model/collection-v27-manual.json).
- [Fresh Wiki review](evidence/2026-10-21/model/fresh-wiki-manual.json),
  [guard replay](evidence/2026-10-21/model/guard-replay.json),
  [relation review](evidence/2026-10-21/model/relations-manual.json) and
  [adopted-wire proof](evidence/2026-10-21/model/relation-wire-equivalence.json).
- [Full checks](evidence/2026-10-21/final/checks.json),
  [coverage](evidence/2026-10-21/final/backend-product-coverage.json),
  [package record](evidence/2026-10-21/final/build-review.json) and
  [QA cleanup](evidence/2026-10-21/cleanup.json).

The resumed QA listener on port 11439 was confirmed unloaded and stopped by its
verified owned PID. Existing model weights were not pulled or deleted, and the
personal Ollama service was not changed. Earlier interrupted request evidence is
retained separately from completed results.

## Remaining acceptance

The known-corpus unsupported comparison rewrite and unsafe Wiki summary were
corrected and inspected in actual generation; the rejected v25 Korean capacity
phrase is now guarded. This is not a general entailment solution. Other explicit
synthesis/report/extraction/audit paths still depend on a fallible local model;
earlier component false approvals/rejections are not relabeled as resolved.
Relationship discovery still misses one required shared-fact link. Representative
quality/retrieval calibration and broader multilingual organization remain open.

The earlier native-device checks remain outstanding: physical IME and VoiceOver,
removable storage and sleep, native active-token force-quit and remaining failure/
adoption paths. Authorized cloud-provider quality/latency and real Developer ID
signing/notarization/another-device checks require resources not available in this
QA run. The earlier busy frozen-startup failure remains retained; this idle pass
does not prove its resolution. No peak-memory/leak-free or broad performance claim
is made. The conditional final merge and Phase 8/MVP completion remain open.
