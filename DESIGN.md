# Noye Design System

The visual and interaction rules for Noye's interface. Implemented in
`frontend/src/styles/tokens.css` (framework-agnostic CSS custom properties) and
exposed to Tailwind in `frontend/src/app/globals.css`.

This document is the source of truth for *why*. `tokens.css` is the source of
truth for *values* — never hardcode a colour in a component.

---

## 1. Direction

**A source-grounded research workspace.**

Direction update, 2026-10-03: both web and desktop now open into a chat-focused
workspace: conversations on the left, readable central prose and a bottom
composer, explicit provider selection with the configured model name, and an
answer-specific passage inspection drawer. The drawer is a native modal dialog
with a scrolling body, inert background and focus restoration on close. It never
takes height from the conversation. Provider/source and document options open in
bounded scrolling panels so short windows retain the conversation and composer.
Below 768px navigation collapses into a menu. Library, Search and
Documents remain accessible. Added 2026-10-05: a desktop-only first-run guide shows
measured hardware, a conservative model candidate and local/Gemini prerequisites.
It uses the shared semantic tokens, with a fixed header/footer and a scrolling
body so loading and long instructions do not hide Skip/Continue. Current and
recommended models are distinct; guide selection never changes the provider.
The guide can be dismissed and reopened without unmounting the workspace.
Settings now provides explicit model installation/deletion, model selection and
Keychain-backed cloud API configuration. The Services section uses quiet rows,
ownership labels and explicit preparation confirmation, not nested status cards.

Retrieved passages are labelled **consulted**, not verified support. No fabricated
retrieval stage or progress percentage appears while waiting for a model. Chat
uses the existing safe Markdown renderer but does not load model-generated images
automatically or opt into document-only printing.
Document creation requires the explicit composer option; ordinary and negated
questions do not select it through keyword matching. Document jobs disclose local
Ollama independently of the provider selected for ordinary chat. Within the app
session, drafts, source scope, document options and pending answers survive route
navigation. This state is not replayed after restart.

Noye turns a person's own files into knowledge they can search, and every answer
points back to the page it came from. The interface is built from that: paper,
ink, a shelf, a citation. Light mode keeps warm off-white, forest actions and brass
markers; the owner-requested dark mode uses charcoal, off-white and muted blue.

The direction comes from a real object — a cloth-bound book with a green cover
and a gold-stamped spine. That keeps it away from the two places AI-built
interfaces cluster: the blue/violet SaaS default, and the cream-plus-terracotta
"editorial" look.

**Restraint is the rule.** Most files in the library will be fine. If every
healthy state is coloured, colour stops meaning anything, so colour is spent on
exceptions and on the one thing that makes Noye Noye: the citation.

---

## 2. Palette

Base palette chosen by the project owner. Four tokens are derived, because the
six base colours cannot cover every job — each derivation is measured, not
guessed.

### Base

| Role | Hex | Notes |
| --- | --- | --- |
| Background | `#F4EFE6` | Warm off-white. The page. |
| Surface | `#DED0B6` | Tan. Structure — sidebar, insets. **Not** card fill in light mode. |
| Primary | `#344E41` | Deep forest green. Anything you act on. |
| Secondary | `#5C4033` | Coffee brown. Display headings. |
| Accent | `#B08D57` | Brass. Fills, rules, edges, progress. **Never text.** |
| Text | `#292421` | Warm near-black. |

### Derived

| Token | Hex | Why it exists |
| --- | --- | --- |
| `--leaf` | `#FBF8F2` | Card fill in light mode. Surface `#DED0B6` as a card fill turns a long list into a wall of tan. |
| `--accent-ink` | `#7a5c28` | Brass is 2.70:1 on the background — unreadable. This is the text-safe sibling at 5.41:1. |
| `--fail` | `#8c1d33` | Oxblood. No failure colour existed, and ingestion has real failure states (scanned PDFs, non-UTF-8 text). |
| `--ink-on-sunken` | `#5b5349` | Sidebar secondary text. The old muted ink measured 4.03:1 on tan; this measures 4.97:1. Dark mode uses `#b3b9c4` at 9.44:1 on the sidebar. |

### Measured contrast — light

| Pair | Ratio | WCAG |
| --- | --- | --- |
| Text on background | 13.40:1 | AA ✓ |
| Text on surface | 10.09:1 | AA ✓ |
| Primary on background | 7.93:1 | AA ✓ |
| Secondary on background | 8.20:1 | AA ✓ |
| Background on primary (filled button) | 9.08:1 | AA ✓ |
| Fail on background | 7.84:1 | AA ✓ |
| Accent-ink on background | 5.41:1 | AA ✓ |
| **Accent on background** | **2.70:1** | **FAIL — decoration only** |
| **White on accent** | **3.09:1** | **FAIL — use dark text on brass** |
| Background → surface | 1.33:1 | elevation reads |
| Background → leaf card | 1.08:1 | too weak alone → **border required** |

### Dark palette — neutral charcoal

Owner-requested update, 2026-10-05: dark mode uses neutral charcoal surfaces,
off-white prose/headings and a muted blue action color. Green, brown and brass
remain in light mode only. Shared semantic tokens keep both modes consistent;
status still requires words/icons, never hue alone.

| Token | Hex | Purpose |
| --- | --- | --- |
| Canvas | `#17191c` | Neutral charcoal workspace |
| Card | `#22252a` | Raised panel |
| Sunken | `#111316` | Inset/sidebar surface |
| Ink/display | `#f0f1f3` | Off-white text without brown headings |
| Ink-soft | `#b3b9c4` | Secondary copy |
| Brand | `#a9b8cc` | Muted blue actions and focus |
| Accent-ink | `#bcc5d2` | Quiet slate highlights |
| Fail | `#eca0a7` | Restrained rose with explicit error text |

This is a token-level palette change, not a claim of packaged-app visual
acceptance. The macOS bundle must be rebuilt before judging it natively.
Calculated dark contrast: ink/card 13.60:1, secondary/card 7.80:1,
faint/card 4.64:1, brand/card 7.62:1, filled-button text/brand 8.75:1,
accent text/wash 8.16:1 and failure text/wash 6.88:1. Strong control borders on
cards measure 3.07:1. These are calculated token contrasts, not browser observations.

---

## 3. Two rules that are easy to get wrong

### Brass is not a text colour

`#B08D57` reaches 2.70:1 on the background and 2.03:1 on tan. It is for fills,
rules, borders, progress bars, and the spine marker on a file card. When brass
*must* carry words, use `--accent-ink` (`#7a5c28`). A brass button takes **dark**
text (4.96:1), never white (3.09:1).

### Status never relies on hue

Two collisions exist in this palette and neither can be designed away:

```
oxblood #8c1d33  vs  primary green #344E41   →  1.01:1   identical luminance
```

Red against green is also the worst possible pair for the most common form of
colour blindness. So every status carries an **icon and a word**, and colour is
only reinforcement:

| State | Colour | Icon | Word |
| --- | --- | --- | --- |
| Uploading / extracting / chunking / embedding | brass | spinner | "Indexing" + the step |
| Ready | *none* | check | "Ready" |
| Failed extraction or indexing | oxblood + 3px left border on the card | cross | "Needs attention" |
| Stopped or interrupted | neutral border and ink | cross | "Stopped" or "Interrupted" |

**Ready is deliberately colourless.** It is the resting state of almost every
file; colouring it would drown the one card that needs attention.

Green is the brand colour here, so it is never reused to mean "success" — a
colour that means both "interactive" and "succeeded" means neither.

---

## 4. Elevation

Light and dark build depth differently, because they have to.

**Light:** the card (`--leaf`) is only 1.08:1 against the background, so the
**border draws the card**. It reads like a sheet of paper with a drawn edge.

**Dark:** fill steps almost vanish at low luminance (a naive brown-on-brown dark
mode measured 1.06:1 and looked like fog). So dark mode **fills** the card to a
1.15:1 charcoal fill step *and* keeps a lighter border. Both channels work together;
controls use the strong 3.07:1 border rather than relying on the fill alone.

Never use shadow as the only elevation cue; it disappears on the dark ground.

---

## 5. Typography

Three roles, three faces.

| Role | Face | Used for |
| --- | --- | --- |
| Display | **Fraunces** (variable serif) | Wordmark, page titles, empty-state headlines. `--ink-display`: coffee brown in light mode, off-white in dark. |
| Body | **Geist Sans** | Everything else. |
| Data | **Geist Mono** | Page numbers, passage counts, file sizes, citation numbers. |

Fraunces is used with restraint — headings only, never body copy, never a whole
paragraph. Its job is to make the product feel like a library, in the one place
a reader's eye lands first.

Mono on numbers is not decoration: page numbers and passage counts are the
product's evidence, and setting them as data makes them scannable in a column.

Scale: `27px` page title, `16-18px` section headline, `14.5px` body,
`12.5px` supporting, `11px` uppercase eyebrow (tracked `.09em`), `10.5px` data.

---

## 6. Shape and spacing

| Token | Value | Used for |
| --- | --- | --- |
| `--radius-sm` | `4px` | Citation badges, small chips |
| `--radius-md` | `8px` | Buttons, inner panels |
| `--radius-lg` | `10px` | Cards, drop zone |
| `--radius-pill` | `999px` | Status pills |

The file-type marker is the one deliberate exception: `3px 6px 6px 3px` with a
3px coloured left edge, so it reads as a book spine.

Card padding `14px 16px`. Gap between cards `9px`. Section eyebrow margin
`26px` above, `10px` below.

---

## 7. The signature

**The citation is the one memorable element**, because it is the one thing Noye
does that a folder of files does not.

In this release it is a filled green numbered badge inline in the text, with
source cards below carrying a brass top rule, the file name, and the page set in
mono. The badge is the only place a saturated fill appears in running text.

Phase 4 (Chat) should develop this further rather than replace it — marginalia,
or an inline expansion that shows the cited passage itself. Any future change to
citations is a change to the product's signature and deserves that weight.

Markdown and text files have no page number by design (a chunk cannot be cited
to a page that does not exist), so the source card reads "no pages" rather than
inventing "page 1".

---

## 8. Voice

Interface copy is written from the reader's side of the screen. Noye's states
describe what happened to *their file*, not what the pipeline did.

| Don't | Do |
| --- | --- |
| `EMBEDDING` | "Creating embeddings — step 3 of 4" |
| `FAILED` after an extraction error | "Needs attention" with the reason below |
| A cancelled ingestion | "Stopped" and "Retry whenever you're ready" |
| "Error: no text extracted" | "No text found in this file. It looks like a scan." |
| "Submit" | "Add files" |
| "No items" | "Nothing on the shelf yet" |

Failure explains what happened and what it means for the person: a scanned PDF
says it will not appear in search. An empty state is an invitation, not a
statement of absence.

Buttons keep their verb through the flow: the button that says "Remove" produces
a result that says "Removed".

---

## 9. Accessibility floor

Non-negotiable, checked before any UI work is called done:

- Body text meets **4.5:1**; large text and non-text indicators meet **3:1**.
- No state is communicated by colour alone (§3).
- Every interactive element has a **visible keyboard focus ring** — 2px
  `--brand`, offset 2px. Never `outline: none` without a replacement.
- The drop zone is reachable and operable by keyboard: it is a real `<button>`
  wrapping the file input, not a bare `<div>` with a drag handler.
- Status changes during ingestion are announced to screen readers via a
  `role="status"` live region, because polling updates without a page change.
- `prefers-reduced-motion: reduce` removes the spinner rotation and the progress
  pulse; the state still reads from icon and text.
- Layout works down to 390px wide; the sidebar collapses rather than scrolling
  horizontally.
- Touch targets ≥ 44px on small screens.

---

## 10. Implementation rules

**Semantic tokens flip themselves.** Tokens are defined with CSS `light-dark()`,
so a component writes `bg-card` and gets the right fill in either mode. Do not
write `dark:` variants for colour — if you find yourself needing one, the token
set is missing a role. Add the role.

**Never hardcode a colour in a component.** If a value is not in `tokens.css`,
it is not part of the design system yet.

**Theme control:** `:root` follows the system. `[data-theme="light"]` and
`[data-theme="dark"]` on `<html>` override it. That is the whole mechanism.

**Browser floor: not raised.** `light-dark()` itself needs Safari 17.5+ /
Chrome 123+, but Turbopack compiles the CSS with Lightning CSS, which downlevels
it to a pair of guard variables and emits the companion rules automatically:

```css
:root { --lightningcss-light: initial; --lightningcss-dark: ; color-scheme: light dark; }
@media (prefers-color-scheme: dark) { :root { --lightningcss-light: ; --lightningcss-dark: initial; } }
[data-theme="dark"] { --lightningcss-light: ; --lightningcss-dark: initial; color-scheme: dark; }
```

Verified in the served stylesheet, including the `[data-theme]` overrides — the
theme switch works because those selectors set `color-scheme`, which is the only
input the polyfill reads. So the effective floor stays Tailwind 4's own
(Safari 16.4+ / Chrome 111+). If the build ever moves off Lightning CSS, re-check
this before assuming the tokens still resolve.

---

## 11. Reuse outside Noye

`frontend/src/styles/tokens.css` has no framework dependency — plain custom
properties on `:root`. To use this system in another project:

1. Copy `tokens.css` in and `@import` it.
2. Components consume `var(--canvas)`, `var(--ink)`, `var(--brand)` and so on.
3. For Tailwind 4, copy the `@theme inline` block from `globals.css`, which maps
   each token to a Tailwind colour name.
4. Read §3 before shipping. The brass-is-not-text rule and the
   status-never-by-hue rule are the two things that will otherwise be got wrong.
