# Desktop UI/UX fixes

The desktop audit was repeated against integrated main
`157be0c377ce47e79c798fe10fd70619ddd7b74f` (PR #60), rather than the older
local main. `fix/desktop-uiux` addresses its nine P1 findings, the source-document draft
base P1 found during the first review, and a Wiki draft ownership P1 reproduced
in the final review. The follow-up also resolves the listed P2 items and retains
conflicting recovered writing across repeated backups. No P0 was established. These
fixes contribute to Phase 8 usability acceptance; they do not complete it.

## Resolved findings

| Finding | Result |
| --- | --- |
| P1-01: ordinary or negated questions start document jobs | Only explicit document mode dispatches a job. Its local Ollama disclosure is separate from ordinary chat's selected provider. |
| P1-02: late document saves/history replace another selection | Document identity and request generations guard initial reads, revision selection, save responses and save errors. Save targets the displayed document. |
| P1-03: evidence inspection removes usable chat space | A modal drawer preserves conversation height. Provider/source and document option panels scroll without changing the layout. Escape closes them and restores focus. |
| P1-04: composing Korean/Japanese text dispatches generation | Composition and key code 229 suppress Enter submission; a later ordinary Enter still submits. |
| P1-05: retained Wiki conflicts cannot recover | Users compare the latest saved Markdown, then explicitly reapply or discard the draft. The next save still uses an expected revision. The editor remounts on scope changes. |
| P1-06: disconnected folder history blocks independent upload | Upload deduplication excludes disconnected folder records, without removing originals or evidence history. The copy gets its own ID and path. Active or paused connected folders still block duplicate uploads. |
| P1-07: new conversation ID loses the next question draft | Session state transfers draft and options to the saved conversation ID. |
| P1-08: a returning chat misses its pending answer | The request outlives route components. Returning to its conversation reconnects to progress/completion, including completion before an older initial read. Cached turns preserve chronological order. |
| P1-09: stale search responses replace current results | Query-owned components and aborted effects ignore obsolete success/error responses. Submitting the same query explicitly refreshes it. |
| Additional P1: late Wiki saves delete a replacement editor's retained draft | Save acknowledgements clean up or advance only the saving editor's owned draft; replacement editors retain their authored text and expected revision. |
| Additional P1: source-document draft restoration silently rebases stale work | Drafts preserve expected revision and require explicit comparison for older or unknown bases. Save acknowledgements advance only the saving editor's continued typing. Another window's draft keeps its old base. |

Related fixes refresh document-task cards immediately after dispatch and display
the actual pending chat provider. New-chat drafts retain their selected scope and
document/collection options together. The existing unsafe Markdown test now
asserts the renderer's actual safe contract: no link element is rendered.

## Validation

Commands ran from `frontend` or `backend`, as appropriate:

| Check | Observed result |
| --- | --- |
| `npm test` | Final run: 45 files, 322 tests passed. |
| `npm run lint` | Passed. |
| `npx tsc --noEmit --incremental false` | Passed. |
| `npm run build -- --webpack` | Passed; eight routes prerendered, including `/_not-found`. |
| `npm run desktop:ui` | Passed in static export mode, with eight routes prerendered. |
| `.venv/bin/ruff check app/ desktop.py` | Passed. |
| `.venv/bin/pytest app/tests/ -q` | 995 passed, 19 skipped, 10 dependency/service warnings. Default-port live integration tests were skipped; the isolated live QA below is separate. |
| `npm run desktop:build -- --no-sign --config /private/tmp/noye-uiux-qa-config.json -- --locked` | Passed; unsigned 68.04-MiB Apple Silicon QA app with frozen backend and desktop static UI. |
| `NOYE_TEST_SIDECAR=… .venv/bin/pytest app/tests/test_desktop.py -q -p no:cacheprovider` | Final standalone run: 10 passed, 7 warnings in 11.74s. The first run alongside a web build had 9 passes and a 20-second first-start timeout; unchanged tests passed after the build finished. |
| `git diff --check` | Passed. |

Chromium used synthetic backend/native responses, with exact content viewport
emulation. Chat, Library, Folders, Wiki, Search and Documents loaded without
horizontal overflow or visible error alerts at 1440×900. The document editor
loaded the selected synthetic body. Light/dark chat and evidence layouts were
inspected. Native dialog modality prevented background focus; Escape restored
the answer's inspection button. Option panels also closed on Escape.

| Viewport | Previous conversation height with evidence open | Fixed height, closed or open |
| --- | ---: | ---: |
| 1200×800 | 72.35px | 458.55px |
| 760×560 | 0px | 148.13px |
| 1440×900 | Not measured in the repeated baseline | 558.55px |

At 760×560, provider/source and document options each preserved the 148.13px
conversation area when expanded. Document height stayed 560px, keeping the
composer visible. The evidence drawer was bounded to 520×536px with 12px margins.

## Review

Separate read-only review passes covered chat/search, documents/Wiki and
library/folders. The final Wiki review reproduced two failures independently:
a detached save deleted a replacement editor's retained draft, and successful
Retry loading left the old alert. Both independent regressions passed after the
owner/expected-revision and successful-refresh fixes (two files, two tests). Chat review ran six focused route/state cases. Document review
found the additional draft-base P1; four subsequent focused checks covered
multi-window draft ownership, latest metadata reload and newer revisions arriving
during comparison. The library reviewer exercised disconnect → independent upload
→ reconnect → deletion of the uploaded copy with a real scanner/ingestion fixture;
original bytes, source versions, snapshots and historical evidence remained
readable. Its upload-policy tests passed independently before the fourth
connection/processing combination was added to the committed suite.

The UI review also found that expanded inline controls still exhausted a short
window. Moving them into bounded panels fixed that measured path. Automatic
replacement of a view after an obsolete save was declined because it could
replace a deliberately selected historical revision; explicit comparison remains
available when a subsequent save reports a conflict.

## Follow-up fixes

| Finding | Result |
| --- | --- |
| P2: health counts disagree with actual search eligibility | Folder connection, processing, availability and version guards also apply to the searchable count; integrity diagnosis remains visible. |
| P2: oversized first folder intake silently disappears | Durable intake notices include the relative path and size-limit recovery guidance. Successful intake or removal clears that notice. |
| P2: scanning clears restored writing conflict warnings | Migration 10 separates durable recovery notices from transient root errors; acknowledgement hides notices without deleting either version. Earlier recovery messages migrate forward. |
| P2: Wiki history and current view disagree with URL | History selection, Return to current and proposal adoption update the revision query parameter; Back/Forward owns the visible revision. |
| P2: Wiki material checkboxes reset on reload | Scope changes update the URL while retaining the page, revision and unrelated query keys. Late responses cannot install an obsolete scope or revision. |
| P2: task export link opens the same editor as Open | The duplicate action with ignored export=1 is removed; Open document describes the actual navigation. |
| P2: legacy generation redirects after leaving Chat | A detached message action does not redirect on completion; its pending feedback identifies Documents as the recovery destination. |
| P2: trimmed legacy titles stay dirty after saving | Title normalization happens at dispatch and preserves later title/body edits during acknowledgement. |
| P2: Save as analysis gives no result feedback | Success includes an explicit link to the saved analysis with its original material scope; the original draft remains. |
| P2: Library offers invalid folder-original Remove/Retry paths | File cards, ingestion jobs and integrity diagnostics route folder-owned work to Folders. Stop processing remains available. |
| P2: successful Wiki retry retains the old error | A successful current-scope refresh clears its old failure feedback. |

A backup regression reproduced the omission of previously recovered authored
writing from a subsequent backup. Backups now include retained `knowledge/`
assets and preserve conflicting copies under `Recovered backups/<sha256>/…`
before staging current authored output. The live original and the retained
workspace copy are unchanged.

## Remaining acceptance

The final app used identifier `com.noye.desktopuiuxqa20261009`, a new synthetic
workspace, test-owned Ollama on port 11439 and Qdrant v1.19.1 on port 6339. The
personal workspace and credentials were not imported. A PDF selected through the
native Open dialog became READY with one page and one indexed passage. The live
local answer correctly named NZD 4200 and 24 October 2026; the stored question and
answer timestamps were 14.25 seconds apart in this one run. Returning to the saved
conversation displayed that answer and retained the Korean next-question draft.
The actual WKWebView evidence modal focused Close, displayed the literal saved
passage and identified the original as unchanged. An actual search returned the
single indexed passage with page 1 provenance; health and search both counted
one eligible file. Reading the source API returned bytes identical to the input
PDF. The owned app, Ollama and Qdrant container were stopped after QA.

Physical IME composition, native original-link opening, Markdown/PDF export,
source-driven live generation, cloud inference, other machines and signed/
notarized distribution remain unverified in this pass. The native UI tool timed
out while inspecting Chrome after the original-link click, so that click does
not establish successful opening. No new native PDF pagination claim is made.
Synthetic Chromium layout observations above remain distinct from native QA;
without an approved visual baseline, formal visual regression is inconclusive.
Ordinary Chat session memory remains in-process rather than restart persistence.
After navigating A → B → A during a source-document save, a subsequent save can
require explicit comparison instead of automatically replacing a deliberately
selected historical view.
