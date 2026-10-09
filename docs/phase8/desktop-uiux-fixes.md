# Desktop UI/UX fixes

The desktop audit was repeated against integrated main
`157be0c377ce47e79c798fe10fd70619ddd7b74f` (PR #60), rather than the older
local main. `fix/desktop-uiux` addresses its nine P1 findings and an additional
P1 found during the document durability review. No P0 was established. These
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
| Additional P1: source-document draft restoration silently rebases stale work | Drafts preserve expected revision and require explicit comparison for older or unknown bases. Save acknowledgements advance only the saving editor's continued typing. Another window's draft keeps its old base. |

Related fixes refresh document-task cards immediately after dispatch and display
the actual pending chat provider. New-chat drafts retain their selected scope and
document/collection options together. The existing unsafe Markdown test now
asserts the renderer's actual safe contract: no link element is rendered.

## Validation

Commands ran from `frontend` or `backend`, as appropriate:

| Check | Observed result |
| --- | --- |
| `npm test` | 44 files, 294 tests passed. |
| `npm run lint` | Passed. |
| `npx tsc --noEmit --incremental false` | Passed. |
| `npm run build -- --webpack` | Passed; eight routes prerendered, including `/_not-found`. |
| `npm run desktop:ui` | Passed in static export mode, with eight routes prerendered. |
| `.venv/bin/ruff check app/api/files.py app/db/files.py app/tests/test_files_api.py` | Passed. |
| `.venv/bin/pytest -q app/tests/test_files_api.py app/tests/test_folder_foundation.py app/tests/test_folder_operations.py` | 84 passed, 1 skipped; 8 existing dependency/service warnings. |
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
library/folders. Chat review ran six focused route/state cases. Document review
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

## Remaining acceptance

The packaged Tauri app, WKWebView-specific keyboard behavior, native original
opening, PDF pagination and live local/cloud inference were not exercised in this
pass. The browser native API and service responses were fixtures. An initial web
build failed because sandbox networking could not fetch Google Fonts; the final
web build succeeded with network access. No model fallback or original-file cloud
access was added.

Other P2 audit items remain outside this fix: health/search eligibility counts,
oversized-folder discovery feedback, persistent restore-conflict warnings, Wiki
history/scope URL synchronization, the task export label, legacy generation
navigation after leaving the page, trimmed legacy-title dirty state, and analysis
completion feedback. Ordinary chat session memory is not restart persistence.
Folder-owned Library removal/retry controls still rely on the API's Folders
guidance; ownership-aware controls are a separate follow-up.
