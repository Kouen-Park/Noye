# macOS desktop preview

Phase 7 adds [workspace backups](phase7/workspace-backup.md),
[durable processing jobs](phase7/durable-jobs.md) and
[verified workspace switching/readiness](phase7/desktop-integration.md).
These implementation checks do not replace Phase 8 native GUI acceptance.

This is a local development preview, not the completed desktop MVP or a signed
public release. The app packages the UI and backend. Installed Ollama and local
Docker Desktop remain prerequisites; Settings offers explicit service preparation,
model management and Keychain-backed cloud configuration. Nothing runs an installer
or enables cloud usage silently. Missing services/models are reported in the app.

Roadmap order: Phase 6 implements the Tauri application; Phase 7 implements the
twelve core workflow improvements; Phase 8 follows with stability/quality refinement
and final packaged-app acceptance. Relevant automated
checks and build validation continue during implementation.

## Build

Use macOS, Xcode Command Line Tools, Rust 1.99+, Node/npm, and the backend Python
environment. This build was validated on Apple Silicon with Python 3.14.7 and
Rust 1.99.0. Build on the native architecture: the sidecar and app must match.
Intel Macs, cross-compilation and other operating systems have not been validated.

From the repository root:

```bash
backend/.venv/bin/pip install -r backend/requirements.txt -r backend/requirements-desktop.txt
cd frontend
npm ci
npm run desktop:build -- --no-sign -- --locked
```

The output is `frontend/src-tauri/target/release/bundle/macos/Noye.app`.
`--no-sign` is for this locally built preview only. Public distribution needs a
separate signing/notarization pass; no Apple account or signing identity was used.
The configuration targets macOS 13+, but compatibility with older macOS versions
has not been tested.

The implementation machine uses an ignored, project-local Rust installation at
`.desktop-tools/`; its shell profile and system PATH were not modified. When
using that installation, set `CARGO_HOME`, `RUSTUP_HOME` and PATH for the current
terminal before entering `frontend`. A normal Rust installation also works.

`desktop:prepare` freezes the backend and exports the frontend. Neither `.env`,
uploaded files, SQLite data, model weights nor logs are bundled. PyInstaller's
generated files/cache and Rust targets are ignored. `desktop:dev` is a separate
development workflow using Next's dev server; packaged builds use no dev server.

## Lifecycle and storage

- The app manages its bundled backend and only Ollama/Qdrant handles explicitly
  started by that backend session. It never kills processes by port/name, stops
  an existing external service or shuts down Docker Desktop.
- The backend reserves a random `127.0.0.1` port and signals readiness after
  schema initialization. API consumers and source/export URLs use that address.
- App close/quit sends a graceful shutdown line. Closed parent stdin also stops
  the backend; the app has a 16-second fallback for its own backend child, allowing
  uvicorn's five-second drain and bounded owned-service cleanup.
- A single-instance guard brings the existing window forward instead of opening
  another backend against the same data.
- Storage is `~/Library/Application Support/com.noye.desktop/`: `app.db`,
  `sources/`, `documents/` and bounded `logs/` survive app replacement/relaunch.
- The desktop's default Qdrant collection is `noye_desktop`; the web default stays
  `noye`. Do not configure two independent workspaces to share one collection.
- No repository `.env` is copied or implicitly read by the desktop backend.
  Environment configuration (or app-data `.env` for non-secret development
  configuration) is supported. In-app cloud keys use macOS Keychain and private
  backend stdin; never put a key in frontend configuration, plaintext `.env` or Git.
- Local embeddings and Qdrant are still required when Gemini generates answers.
  This foundation does not solve local inference latency or native PDF export.

The existing API remains local/single-user without authentication. It binds only
to loopback and allows the native webview/dev origins; do not expose it remotely.
The frontend has no general shell or filesystem permissions.

## Explicit local service preparation

Open **Settings → Services**, review the confirmation, and start Ollama/Qdrant
individually. This performs no inference or model download. Install missing
prerequisites yourself from the offered official guides; only those two fixed
URLs open in the system browser, with no arbitrary URL/command API. If Docker's
engine is stopped, **Open Docker Desktop**, wait for its engine, then retry Qdrant.
Docker Desktop itself remains shared infrastructure and is never closed by Noye.

The desktop capability protects `/services`, `/services/start`, `/services/docker`
and `/services/guide`; the normal web backend cannot use these controls. OS commands
use fixed executables/argument arrays, no shell, bounded output and timeouts. Child
environments are allowlisted; backend keys/control tokens are not inherited.

- Start supports default HTTP localhost/127.0.0.1 services on ports 11434/6333
  on macOS. Advanced/custom endpoints are checked but remain externally managed.
- Ollama runs as an owned `ollama serve` child, bound to `127.0.0.1:11434` with
  `OLLAMA_NO_CLOUD=1`. Its existing model location is preserved; no weights are
  downloaded or deleted by service preparation. An existing healthy Ollama is reused.
- Qdrant uses `qdrant/qdrant:v1.19.1`, matching the repository pin. Only HTTP
  `127.0.0.1:6333:6333` is published. The container has no restart policy, no extra
  capabilities and bounded Docker logs. The image uses its upstream default user;
  this is not a claim of a comprehensive container security audit.
- Only local Docker Desktop socket paths are used; inherited remote Docker hosts
  and contexts are ignored. The pinned public image downloads only after explicit
  confirmation and can take up to ten minutes. Startup health waiting is bounded
  at twenty seconds; no fabricated overall download percentage is shown.
- App-data `desktop-service-id` stores a non-secret stable UUID. Container naming
  and owner labels use it; vectors persist in `qdrant/storage`. Escaping/linked
  storage and separator-containing Docker mount paths are refused. Existing stopped
  containers are reused only after validating ID, image, owner, mount and bindings.
- Ready external services are reused without taking ownership. Unknown occupied
  ports and unhealthy previous-session containers are not killed/restarted. Retry
  may stop/restart only this session's owned unhealthy service. Ownership that
  cannot be verified is not labelled app-owned.
- Normal quit cancels owned preparation/download work, terminates the exact owned
  Ollama child and stops a revalidated immutable Qdrant container ID. It never runs
  container removal, volume pruning or a collection reset; Docker and data persist.
  Forced-kill/crash cleanup and real active-job shutdown still require Phase 8 checks.

A newly prepared Qdrant store does not copy vectors from an external server.
Originals/conversations/documents stay in app-data. If the workspace previously used
another Qdrant store, use Library's stored-index check and explicit rebuild; no
automatic import, re-embedding or destructive rebuild runs during preparation.

## Optional import of existing web data

No import runs automatically. Stop the old web backend and quit Noye first.
Import only into a **new, nonexistent** destination; an existing app-data folder
is refused, even when empty. Do not remove a used desktop workspace to make an
import fit—keep it and arrange an explicit migration/backup instead.

Before the first desktop launch, from the repository root:

```bash
backend/.venv/bin/python backend/desktop.py \
  --import-data /absolute/path/to/Noye/data \
  --data-dir "/Users/YOUR_USER/Library/Application Support/com.noye.desktop"
```

The command copies originals and documents and backs up SQLite (including
committed WAL data), updates paths in the copied database, then exits. The old
workspace is unchanged. It does not copy secrets, logs or vectors, and refuses
symbolic links or source paths outside the source workspace. After opening the
app, explicitly rebuild the index in Library to populate `noye_desktop`; this
uses local embeddings and can take time. Do not search the imported library
before that rebuild. Conversation/document text and stored citations are
preserved independently of the derived index.

The same import option is available on the bundled `noye-backend` executable.

## Validation

Recorded on 2026-10-03; full document/RAG acceptance remains deferred to Phase 8
by request.

```bash
cd backend
.venv/bin/ruff check app/ desktop.py
.venv/bin/pytest app/tests/ -q

# Repeat lifecycle tests against the actual bundled executable:
NOYE_TEST_SIDECAR=/absolute/path/to/Noye.app/Contents/MacOS/noye-backend \
  .venv/bin/pytest app/tests/test_desktop.py -q

cd ../frontend
npm run lint
npm test
npx tsc --noEmit
cargo fmt --manifest-path src-tauri/Cargo.toml --check
cargo test --manifest-path src-tauri/Cargo.toml --locked
cargo clippy --manifest-path src-tauri/Cargo.toml --locked --all-targets -- -D warnings
npm run desktop:build -- --no-sign -- --locked
```

The Python lifecycle tests use temporary workspaces; they cover startup, health,
empty-library reads, native CORS and normal shutdown/closed parent stdin. Import
tests preserve committed WAL data, saved conversations/documents, originals and
rewritten paths while refusing overwrites, escaping source paths and symlinks.
UI tests cover browser compatibility, startup gating/failure, missing services,
runtime links and an unresponsive native command. The native app was observed
opening Library and navigating to Chat/Documents with a missing-services banner;
closing it removed its backend processes and listener. No personal file was
uploaded, migrated, deleted or sent to an AI provider during that observation.

Next.js/eslint-config-next were patched from 16.3.5 to 16.3.8 after the dependency
audit reported [the Next.js ImageResponse advisory](https://github.com/vercel/next.js/security/advisories/GHSA-vcvr-r3jv-pc5j).
Noye does not use `next/og` or `ImageResponse`. The remaining audit warnings concern
the development-only ESLint → fast-glob → micromatch → braces dependency chain.
The registry currently has no patched braces release; the suggested major
ESLint-config downgrade was not applied. This is not a clean full dependency
security audit.

Results: backend **548 passed, 19 skipped**; bundled-backend checks **10 passed**;
frontend **145 passed**; Ruff, ESLint, TypeScript, Rust formatting, Rust unit test
and Clippy passed. The macOS application/static UI build passed and produced a
**67.22 MiB** bundle. `npm audit --omit=dev` reported **0 vulnerabilities**; the
full audit still reports **5 high** development dependency warnings described
above. Skipped live backend checks are not counted as completed acceptance.

Not validated: complete upload/RAG/citation flows, live Gemini quality/latency,
native Markdown/PDF export, real user-data import, crash recovery under active
ingestion, installation/onboarding, secure key persistence, Intel/other Macs,
Windows or Apple-signed/notarized distribution.

## Chat-focused workspace validation

The second desktop milestone was implemented and validated on `feat/tauri-macos`
on 2026-10-03–04.
Both browser and native startup now open Chat. The shared sidebar retains Library,
Search and Documents, with saved conversations and New chat on the left. Answers
use safe Markdown; a selected answer's consulted-passage metadata opens alongside
the conversation on wide screens and above it on smaller screens. The composer
stays at the bottom while messages scroll independently. Provider selection shows
the backend-configured model, not a new installed-model management feature.

Executed frontend checks: `npm test -- --reporter=dot` — **160 passed in 22 files**;
`npm run lint` and `npx tsc --noEmit` passed. The complete
`npm run desktop:build -- --no-sign -- --locked` workflow passed, including the
static UI, frozen backend and **67.22 MiB** Apple Silicon app bundle. Backend/Rust
source did not change; the foundation results above are prior validation, not a
new full backend/Rust test run for this UI milestone.

Browser observations used a temporary static preview and synthetic, in-memory API
responses, with no model calls or personal file reads. Checked prompt-to-composer
focus, Enter submission, visible waiting/disabled conversation actions, returned
answer/new-conversation navigation, passage panel opening, page-link metadata,
Escape/focus return, and Library/Search/Documents navigation. Layouts were viewed
at 1440×900, 768×900, 390×844 and 375×812; measured document scroll width equalled
viewport width at those sizes. Light and explicit dark token modes were inspected.
The final mobile-menu auto-close behavior is covered by the component test.

Axe-core WCAG A/AA checks reported **0 violations** in the inspected light/dark
chat states after sidebar contrast repairs. Initial light sidebar muted text was
**4.03:1** (message counts **2.08:1**); the new token measures **4.97:1** light and
**7.54:1** dark against the sidebar. Captured browser warning/error logs were empty
in the checked chat session. Two local preview samples recorded LCP **288 ms** and
**188 ms**, CLS **0**; these are synthetic local samples, not field performance or
AI latency measurements. INP, exhaustive network accounting and a manual screen
reader audit were not measured. No committed screenshot baseline exists, so visual
regression remains **INCONCLUSIVE**, not a baseline comparison pass.

The rebuilt native app was observed opening the new chat screen with the existing
missing Ollama/Qdrant banner, navigating to Library/Documents and back to Chat.
Quit removed its app/backend processes and loopback listener. The temporary preview
servers were also stopped. No user workspace was imported or modified for QA.

A focused code/interaction review added stale-read/generation/deletion guards,
retryable opening errors, failed-question draft restoration, IME-safe Enter,
reduced-motion scrolling, readable long source names, and stronger sidebar text
contrast. Retrieved metadata is still not proof of answer support; previous turns
are still not model context. Actual RAG/citation opening, Gemini quality/latency,
native PDF export and the final packaged-app acceptance pass remain deferred.

## First-run hardware measurement foundation

Added 2026-10-04: `GET /runtime/hardware` is a read-only measurement API. macOS
memory probes each have a one-second timeout and fixed arguments without a shell;
the synchronous route runs them outside the async event loop. Free plus inactive
pages are an estimate, not guaranteed allocation headroom. Apple Silicon is only
an acceleration candidate: no GPU enumeration, VRAM or throughput is claimed.
Unsupported platforms and denied probes return unknown/null. Disk space is for
the workspace volume, not necessarily a separately configured Ollama model volume.

Executed `.venv/bin/pytest app/tests/test_hardware.py app/tests/test_desktop.py -q`:
**22 passed, 7 warnings** after permitting temporary loopback listeners. Initial
sandboxed lifecycle checks failed because binding a local socket was prohibited;
the new hardware tests passed there. `.venv/bin/ruff check app/` passed.
A direct host probe outside the sandbox returned Darwin/arm64, 8 logical CPUs,
8 GiB total RAM and approximately 1.08 GiB free-plus-inactive memory at that moment.
Inside the sandbox, denied memory queries returned null as designed.

`npm run desktop:build -- --no-sign -- --locked` passed (static UI, frozen backend
and Rust app bundle; **67.22 MiB**). No native window/browser UI was opened for this
backend-only step; the first-run recommendation screen does not exist yet.

No frontend changes, recommendation catalog, automatic installation, provider/key
setup or speed benchmark were implemented in this bounded step. First-run setup
remains incomplete. Full backend/live RAG and native export acceptance were not
rerun; the user's ordinary-usage-only limit narrowed this turn to the foundation.

## Read-only recommendation and first-run guide

Added 2026-10-05 on `feat/tauri-macos`. `GET /runtime/setup` returns measured
hardware, a conservative generation-model candidate, configured model names,
GET-only Ollama inventory/Qdrant health checks and a boolean for Gemini-key
configuration. It never returns the key, calls inference, pulls a model or changes
configuration. Service requests have a 1.5-second HTTP timeout with redirects
disabled; the UI has a separate 10-second deadline and cancels closed/stale checks.
Malformed inventory is not reported as healthy.

The generation catalog's approximate decimal download sizes were checked against
the [official Qwen3.5 library](https://ollama.com/library/qwen3.5) on 2026-10-05.
The existing [EmbeddingGemma](https://ollama.com/library/embeddinggemma) configuration
is preserved (about 0.62 GB); custom embedding sizes remain unknown.

| Candidate | Download | Noye total-RAM threshold | Estimated available-memory budget |
| --- | --- | --- | --- |
| `qwen3.5:0.8b` | 1.0 GB | 8 GiB | 2.5 GiB |
| `qwen3.5:2b` | 2.7 GB | 12 GiB | 5 GiB |
| `qwen3.5:4b` | 3.4 GB | 16 GiB | 6 GiB |
| `qwen3.5:9b` | 6.6 GB | 32 GiB | 10 GiB |

These memory budgets are conservative Noye heuristics for short document questions,
not vendor requirements, maximum-context guarantees or speed/quality benchmarks.
Total RAM and current available memory both influence the result. Tight memory
keeps only a conditional small candidate with a close-apps warning; unknown memory
does not claim fit. Unknown acceleration considers only the smallest candidate.
Workspace disk can warn about low space but cannot validate a different Ollama
model-storage volume. Sizes/tags may change; actual install preflight is still needed.

The desktop-only guide opens after the owned backend is ready. It separates the
recommendation from the active model, shows missing local prerequisites, and offers
local/Gemini explanatory views. Gemini still requires local embeddings and Qdrant.
Cloud disclosures cover the existing chat/document payloads, unpaid-tier data terms
and project-controlled billing; viewing the guide neither enables cloud use nor
proves a configured key works. Secure in-app key entry is not implemented yet.
Only a non-secret dismissal flag is stored, not provider/model/key configuration.
AI setup reopens fresh measurements. The workspace stays mounted so closing/opening
the guide does not discard an in-progress question. Storage failure allows session
dismissal with a warning. This is a guide, not completed installation/onboarding.

Executed checks:

- `.venv/bin/pytest app/tests/ -q -m 'not integration'`: **588 passed, 19 skipped,
  8 warnings**. Live-service checks auto-skipped while Ollama/Qdrant were unavailable;
  these are not a live RAG acceptance pass.
- `.venv/bin/ruff check app/`: passed.
- With `NOYE_TEST_SIDECAR` pointing to the built Apple Silicon backend,
  `.venv/bin/pytest app/tests/test_desktop.py -q`: **10 passed, 7 warnings**,
  including real frozen-child `GET /runtime/setup`, temporary workspace, CORS and
  orderly shutdown checks.
- `npm test -- --reporter=dot`: **175 passed in 24 files**; `npm run lint` and
  `npx tsc --noEmit` passed. Tests cover recommendations/unknown probes, read-only
  API behavior, readiness gating, retry, timeout/abort/late results, guide selection,
  dismissal/storage failure, preserved drafts and focus return.
- `npm run desktop:build -- --no-sign -- --locked` with repository-local Rust
  toolchain paths: passed, including static UI, frozen backend and **67.24 MiB**
  macOS Apple Silicon app bundle. Rust source did not change in this milestone.

Browser QA used a temporary static preview, a simulated native bridge and synthetic
in-memory API responses, not the real Tauri lifecycle, models or personal files.
Observed guide selection without provider change, refreshed readings while keeping
the guide path, installed-model disclosure, Continue/Skip, Escape and opener focus
return, dismissal across reload, and preserved unsent questions across guide use.
Inspected 1440×900, 768×900, 390×844 and 375×812: document scroll width matched the
viewport, and the guide had no horizontal overflow; the middle scrolls while
Skip/Continue remain available. Inspected explicit light and dark token modes.
Native dialog keyboard traversal did not reach background workspace controls;
browser chrome remains keyboard-reachable.

Axe-core WCAG A/AA checks reported **0 violations** in the inspected local/cloud
light/dark guide states after a primary-button contrast repair. Captured browser
warning/error logs were empty. A fixed-size guide reduced measured preview CLS from
**0.428** to **0.0106** in comparable desktop samples; the light sample recorded LCP
**392 ms**. These are synthetic local UI observations, not field performance or AI
latency. INP, exhaustive request accounting and manual screen-reader validation
were not measured. No committed screenshot baseline exists, so formal visual
regression remains **INCONCLUSIVE**.

The native app displayed actual Darwin/arm64 hardware: **8 GiB total RAM**, roughly
**1.2–1.6 GiB available** and **13.1–13.2 GiB workspace disk free** across observations.
It recommended the conditional 0.8b candidate with a tight-memory warning, preserved
the configured 4b model, and reported offline Ollama/Qdrant without blocking Chat.
Guide refresh/local/cloud views, dismissal, reopening, unsent-question preservation
and dismissal across app relaunch were observed. Interaction review repaired
loading layout shifts, button contrast and WebKit pointer-click focus restoration.
The rebuilt native app visibly returned focus to AI setup after Escape. Quit left
no Noye app/backend processes. The temporary preview/API servers were stopped,
their two listeners were absent, and the browser viewport override/tab were cleared.

Remaining: opt-in downloads/progress/cancel/retry, actual model-volume disk checks,
persistent generation-model selection, OS-secure API-key entry and remaining local
service setup. No model was installed or switched and no cloud content was sent.
Live RAG/citation behavior, AI quality/latency, native Markdown/PDF export and final
packaged-app acceptance remain deferred to Phase 8. Other hardware/OSes and signed
distribution remain unvalidated.

## In-app AI management — 2026-10-05

This supersedes the guide-only limitations above. **Settings** opens from the
desktop status bar, AI selector or first-run guide. Local models, Cloud APIs and
Services are separate sections; the workspace remains mounted behind the dialog.

Local models support Qwen 3.5 0.8b/2b/4b/9b and configured embeddinggemma variants.
Downloads are explicit, never select a model automatically and report current
layer progress, not a fabricated overall percentage. The user must confirm an
existing folder on Ollama's actual model-storage volume; the app cannot discover
it reliably from a separate Ollama server. Free space must cover twice the
catalog estimate plus 1 GiB. Downloads time out after 30 minutes, can be cancelled
and retried, and are cancelled on owned-backend shutdown. Partial/shared downloads
may remain in Ollama; Noye does not delete blobs. API contracts follow
[Ollama's documentation](https://github.com/ollama/ollama/blob/main/docs/api.md).

Deletion requires an exact installed name and warns about shared Ollama usage.
Selected generation, fixed embeddings and Noye's in-flight inference are
protected; other apps' active inference is not reliably detectable. Mutations
require loopback Ollama and the native app's random per-process capability.
Changing generation models does not rebuild the index. Embeddings remain fixed.

OpenAI, Claude and Gemini key entry/removal uses the apple-native store in
[keyring 3.6.3](https://docs.rs/keyring/3.6.3/keyring/) under service
`app.noye.desktop.ai`. No plaintext fallback. Only key availability reaches the
UI; `ai-settings.json` stores provider/model names. Keys travel through private
child stdin, never a public HTTP settings endpoint, CLI argument or browser
storage. A failed Keychain/apply operation is reported; missing backend
acknowledgement asks for restart. Existing jobs retain their settings snapshots.
Key removal cannot cancel a provider request already sent.

OpenAI uses [Responses](https://developers.openai.com/api/docs/guides/migrate-to-responses)
with `store: false`; Claude uses [Messages](https://platform.claude.com/docs/en/api/messages/create).
One request, no tools/retry/fallback; malformed/incomplete answers and upstream
errors are sanitized. Saving keys sends no inference request. API usage is separate
from [ChatGPT subscriptions](https://help.openai.com/en/articles/9039756-managing-billing-for-chatgpt-and-the-api-platform)
and [Claude subscriptions](https://support.claude.com/en/articles/9876003-i-have-a-paid-claude-subscription-pro-max-team-or-enterprise-plans-why-do-i-have-to-pay-separately-to-use-the-claude-api-and-console).
Selected-provider payload disclosure remains visible; embeddings/search stay local.

Executed validation:

- `backend/.venv/bin/pytest app/tests/ -q`: **632 passed, 19 skipped, 8 warnings**.
  Live-service checks remain skipped; cloud/model tests use mock transports.
- `backend/.venv/bin/ruff check app/ desktop.py`: passed.
- `npm run lint`, `npx tsc --noEmit`: passed.
- `npm test`: **182 passed, 25 files**, including key masking/clearing, confirmed
  removal, storage confirmation, exact-name deletion and errors.
- `cargo test --locked --manifest-path src-tauri/Cargo.toml`: **3 passed**.
- `NOYE_TEST_SIDECAR=... .venv/bin/pytest app/tests/test_desktop.py -q`:
  **10 passed, 7 warnings**, including private configuration/availability and
  graceful line/EOF shutdown with temporary data.
- `npm run desktop:build -- --no-sign -- --locked`: passed, unsigned
  **67.49 MiB** `Noye.app`.

Browser fixtures: **375×812**, **768×1024**, **1440×900**, light/dark settings,
scrolling with fixed controls, fake-key save/clearing, provider refresh without
changing current AI, unsent draft/opener-focus preservation, download confirmation,
layer progress and cancellation. Observed axe A/AA violations **0**, captured
console errors/warnings **0**. One navigation measured LCP **296 ms**, CLS **0**:
static fixture rendering, not AI latency. INP, exhaustive network accounting and
manual screen-reader coverage were not measured. No committed visual baseline:
formal visual regression **INCONCLUSIVE**.

Native packaged app: local/cloud settings opened with real offline service
readings. The unchanged local preference was saved and backend confirmation
appeared; persisted JSON contained only provider/model names. Key input was a
secure text field. No actual key was saved/removed, paid request made, or model
downloaded/deleted. Native chat-text automation was inconclusive; newly proven
draft preservation applies to browser fixtures/component checks, not native input.

At this checkpoint, service preparation/recovery was pending; the new service
section above supersedes that implementation limit. Actual Keychain permission/
persistence, live model management, cloud authorization and RAG/latency/PDF
acceptance remain Phase 8 checks. Opening Settings alone starts nothing.

### Dark-palette continuation checkpoint (historical)

The owner requested neutral charcoal, off-white text and muted blue actions.
Only dark color tokens and design documentation changed; light mode and service
implementation are unchanged. ESLint and all 182 frontend tests passed. Computed
dark text contrast is recorded in `DESIGN.md`; control-border/card contrast is
3.07:1. Browser/native visual inspection and macOS bundle regeneration had not
been performed at this checkpoint; the continuation below records the new build.

Ollama/Qdrant preparation/recovery and safe owned lifecycle were still pending.
Per the owner's clarification, real model/Keychain/cloud/RAG/PDF acceptance belongs
to Phase 8, not a blocker requiring live tests during Phase 6 implementation.

## Service/palette continuation validation — 2026-10-05

Executed against the final implementation:

- `backend/.venv/bin/pytest app/tests/ -q -m 'not integration'`: **670 passed,
  19 skipped, 8 warnings**. The service-controller tests use fake process/Docker
  boundaries and temporary storage, not live model/container operations. A final
  focused rerun of `app/tests/test_desktop_services.py` passed **38 tests** after
  adding capability and arbitrary-guide rejection assertions.
- `backend/.venv/bin/ruff check app/ desktop.py`: passed.
- `npm test -- --reporter=dot`: **196 passed in 27 files**. New checks cover
  explicit preparation confirmation, external ownership, missing prerequisites,
  bounded service requests, cancellation on panel close, accessible first-check
  retry, fixed-guide requests and model-inventory refresh.
- `npm run lint`, `npx tsc --noEmit`: passed.
- `cargo fmt --manifest-path src-tauri/Cargo.toml --check`, `cargo test --locked`
  (**3 passed**) and `cargo clippy --locked --all-targets -- -D warnings`: passed.
- `npm run desktop:build -- --no-sign -- --locked`: passed, including static UI,
  frozen backend and the final **67.52 MiB** Apple Silicon `Noye.app`. Exported
  CSS contains the new charcoal token. The app was rebuilt, not visually inspected.
- With `NOYE_TEST_SIDECAR` pointing at the final bundle,
  `.venv/bin/pytest app/tests/test_desktop.py -q`: **10 passed, 7 warnings**.
  Temporary-data checks include protected service routes, unconfirmed-start refusal,
  no service-storage creation, private settings acknowledgement, readiness and
  shutdown line/EOF. No prerequisite daemon is started by these checks.

Initial sandboxed full-suite execution had two lifecycle failures because binding
temporary loopback sockets was denied. The authorized rerun passed. Dependency
deprecation/Qdrant compatibility warnings remain; they were not hidden or counted
as failures. The final process check found no matching Noye/backend/dev-server
processes from this work. No browser/native GUI session, installer, Docker image
download, model mutation, real credential operation or cloud inference was run.

Implementation review repaired cancellation during process creation, bounded
streaming-probe/output behavior, ownership of a stopped container with an external
listener, safe container identity revalidation and first-status-failure retry.
The installed macOS WebKit code was inspected: without a new-window handler,
`target="_blank"` is not a system-browser opener. Fixed guide URLs therefore use
the bounded capability-protected OS-open path. Its real browser interaction remains
unvalidated. No independent reviewer or new browser/axe pass ran in this continuation.

Design skills guided these concrete changes:

| Area | Before | After |
| --- | --- | --- |
| Dark palette | Forest/brass and brown headings | Charcoal, off-white and muted blue semantic tokens; light mode unchanged |
| Service setup | Read-only booleans and external setup instructions | Quiet ownership-labelled rows, explicit confirmation, 44px start/retry/open actions |
| Failure handling | First status failure could leave no retry action | Reachable refresh action, bounded requests and separate polling errors |

Calculated color contrast is in `DESIGN.md`; it is not a rendered WCAG or visual
acceptance result. Docker's [CLI reference](https://docs.docker.com/reference/cli/docker/container/run/),
[stop semantics](https://docs.docker.com/reference/cli/docker/container/stop/),
[Ollama configuration](https://docs.ollama.com/faq) and the
[Qdrant quickstart](https://qdrant.tech/documentation/quickstart/) informed the fixed
command plan. Native/macOS behavior is not claimed from Docker/Linux fixtures.

The requested Phase 6 macOS implementation is ready for focused Phase 7 work.
Phase 8 still owns real Docker/Ollama startup/recovery/shutdown, permission prompts,
model/key lifecycle, cloud authorization, latest-palette visual inspection, live
RAG/citations, data persistence under active-job crashes, latency and actual native
Markdown/PDF exports. Signed/notarized distribution, other Macs and Windows remain
unvalidated. These checks were deferred, not marked passed or silently removed.

## Ordered Phase 7 integration validation — 2026-10-05

Phase 6 final source `ab225fd` was merged as #43, followed by #44 (closed #37's
local exposure change), #45 (closed #38's maintenance coordination) and #46
(closed #39's identity change). The identical `feat/` heads were refreshed with
main using normal merges. The four identity conflicts retain desktop settings,
provider forwarding, saved failure turns and both maintenance/identity errors.
Retrieval evaluation then merged cleanly into complete source `f1cdc8b`.

- Final backend: **734 passed, 19 skipped, 8 warnings**; Ruff passed.
- Final frontend: **199 passed across 27 files**; ESLint and TypeScript passed.
  Route type generation/web build passed on the preceding identity snapshot;
  evaluation changes no UI source. Desktop static export passed again.
- Rust tests: **3 passed** at unchanged native source; final format/Clippy passed.
- `npm run desktop:build -- --no-sign -- --locked`: passed, **67.53 MiB** unsigned
  Apple Silicon `Noye.app`, including all integrated backend changes. PyMuPDF's
  distribution metadata required by the fingerprint is present in the build TOC.
- Final `NOYE_TEST_SIDECAR=... .venv/bin/pytest app/tests/test_desktop.py -q`:
  **10 passed, 7 warnings**. Temporary storage, readiness, private configuration
  acknowledgement, control refusal, CORS and line/EOF exit only; no model/daemon
  preparation or native GUI launch.
- Diff/Compose checks passed. A model-free lexical pilot reproduced Recall@5
  **0.7143** and nDCG@5 **0.7656**, not a live AI quality/latency result.

Starlette/PyMuPDF deprecation and an existing Qdrant compatibility warning remain.
No GitHub CI checks were reported; these results are local. Earlier live-service
reports remain historical. No personal workspace/index/container was rebuilt or
removed, no real key/model/cloud call was used, and no rendered native PDF was
inspected. The Phase 8 acceptance list above remains open. Open evidence/drafting
PRs #41/#42 are separate work, and #41's index-identity base branch is retained.
