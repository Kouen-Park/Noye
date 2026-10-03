# macOS desktop foundation

This is a local development preview, not the completed desktop MVP or a signed
public release. The app packages the UI and backend; Ollama and Qdrant remain
external prerequisites. Missing services/models are reported inside the app.

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

- Only the bundled backend is managed. The app does not kill processes by port or
  name, and it never controls Docker/Qdrant/Ollama in this milestone.
- The backend reserves a random `127.0.0.1` port and signals readiness after
  schema initialization. API consumers and source/export URLs use that address.
- App close/quit sends a graceful shutdown line. Closed parent stdin also stops
  the backend; the app has an eight-second fallback for its own child process.
- A single-instance guard brings the existing window forward instead of opening
  another backend against the same data.
- Storage is `~/Library/Application Support/com.noye.desktop/`: `app.db`,
  `sources/`, `documents/` and bounded `logs/` survive app replacement/relaunch.
- The desktop's default Qdrant collection is `noye_desktop`; the web default stays
  `noye`. Do not configure two independent workspaces to share one collection.
- No repository `.env` is copied or implicitly read by the desktop backend.
  Environment configuration (or app-data `.env` for non-secret development
  configuration) is supported, but in-app key entry and OS-protected credentials
  are not implemented yet. Never put a key in frontend configuration or Git.
- Local embeddings and Qdrant are still required when Gemini generates answers.
  This foundation does not solve local inference latency or native PDF export.

The existing API remains local/single-user without authentication. It binds only
to loopback and allows the native webview/dev origins; do not expose it remotely.
The frontend has no general shell or filesystem permissions.

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
