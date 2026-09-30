# UI / State / Logic Audit — `frontend/src/app`

Read-only analysis. No source files were modified. All findings cite exact `file:line`.

**Audit scope:** the 12 page/layout files listed at the end, plus `src/lib/api.ts`, `src/hooks/useChatSession.ts`, `src/app/globals.css`, and the 190 components in `src/components/lab/` as the reuse baseline.

---

## Severity key

| Level | Meaning |
|---|---|
| **P0** | Data-loss / security / permanently-stuck UI. Ship blocker. |
| **P1** | User-visible wrong behavior or dead end (no retry, silent failure, lost work). |
| **P2** | Inconsistency, duplication, or missing state that produces visibly worse UX. |
| **P3** | Maintainability / dead code. Safe to batch. |

---

# 1. Cross-cutting findings (read this first)

These apply to 6+ pages and explain most of the P1/P2 noise below.

### X-1 · P1 · Every `fetch` call site in the app ignores cancellation
`src/lib/api.ts:207-244` composes a caller signal with a timeout backstop, and the helper is explicitly documented as supporting it:

```
179: *  - a user-supplied `signal` (SSE teardown, unmount) still aborts promptly,
180: *    and the two signals are combined rather than overwriting each other;
207:    signal: callerSignal,
```

No audited page ever passes one. `grep` for `signal` across `src/app/**/page.tsx` returns **0 matches**. So the capability exists, is paid for on every request, and is unused. Consequence: every page below relies on a hand-rolled `let cancelled = false` flag, which is incomplete — it suppresses `setState` after unmount but does **not** cancel the in-flight request or the response body. See the concrete bugs this causes at S-1, S-2, M-1, L-2.

**Recommendation (one-line-per-page, not a rewrite):** thread `AbortController` into the effect, return `controller.abort()` from cleanup, and delete the `cancelled` flag. The helper already handles it.

### X-2 · P1 · Two competing "status" systems, and the app only uses the weak one
`src/hooks/useChatSession.ts:44` defines the correct model:

```
44: export type AsyncStatus = 'idle' | 'loading' | 'ready' | 'error';
```

Chat consumes it (`conversation`, `historyStatus`, `buildsStatus`, `messagesStatus`). Every other page uses a hand-rolled pair of booleans (`loading`, `error`) that cannot represent "loaded, and the result is legitimately empty." The consequence is structural and repeats on every page: **there is no distinct empty state**, so "still loading" and "server returned nothing" render identically, and the empty case is either a bare blank region or an `error` string that lies to the user.

**Recommendation:** lift `AsyncStatus` into a shared `useAsync` hook and delete the ad-hoc booleans. This is the single highest-leverage change in the whole audit — it removes ~40 booleans and creates the empty state that 9 pages are missing.

### X-3 · P2 · The design system exists; the pages mostly do not use it
190 components are available in `src/components/lab/`. Zero of the 12 audited pages import anything from `lab/`. Meanwhile `globals.css` defines first-class classes that most pages ignore:

| Available | Defined at | Pages that ignore it |
|---|---|---|
| `.sutra-card` | `globals.css:350-362` | landing, dashboard, chat, sandbox, solution, mvp, legacy |
| `.sutra-surface` | `globals.css:339-347` | all but sandbox |
| `.skeleton` / `.skeleton-pulse` | `globals.css:511`, `:563` | 11 of 12 |
| `.animate-fade-up` / `.animate-slide-in` | `globals.css:483`, `:487` | 9 of 12 |

Note `.sutra-card` already encodes `background`, `border`, `radius: 4px`, `box-shadow: var(--shadow-raised)`, and a hover transform. Pages re-declare all of it inline instead. `solution/[id]/page.tsx:255` is a clean example of the duplication:

```
255: <div className="sutra-card p-6 bg-[var(--bg-2)] flex flex-col ... border border-[var(--border)]">
```

`sutra-card` sets `background: var(--bg-2)` and `border: 1px solid var(--border)` at `globals.css:352-354`. Both are restated. This pattern repeats 20 times across 7 files (see the per-page inventories).

### X-4 · P2 · Legacy token names are aliased but the pages were never migrated
`globals.css:243-257` is an explicit admission:

```
243:   /* -- this app's own variable names -----------------------------------------
244:      The hand-written screens (dashboard, admin, billing, settings, sandbox,
245:      MVP) read these as arbitrary values -- text-[var(--sutra-charcoal)],
246:      bg-[var(--bg-2)] -- in several hundred places. Rather than rewrite every
247:      call site, each old name is declared here as the token that now means the
248:      same thing. Delete a name only once its call sites are gone. */
249:   --sutra-warm-ivory: var(--background);
```

Current usage counts across all pages:

| Token | Uses | Maps to |
|---|---|---|
| `--sutra-muted-gold` | 134 | `--foreground` |
| `--sutra-charcoal` | 105 | `--foreground` |
| `--text-3` | 91 | hardcoded `light-dark(#9a9a9a,#6e6e6e)` |
| `--bg-2` | 50 | `--surface` |
| `--text-2` | 83 | `--muted` |

Two real consequences:

1. **`--sutra-muted-gold` is a lie.** `globals.css:255` aliases it to `var(--foreground)`, the plain text color. 134 call sites write `text-[var(--sutra-muted-gold)]` expecting a gold accent and get monochrome text. Same for `--sutra-deep-gold` and `--sutra-gold` (`:256-257`). This is why the UI reads as flat gray despite the "SUTRA gold" naming.
2. **`--bg-3`, `--text-3`, `--border-2`, `--accent-dim` are the only tokens with real `light-dark()` pairs** (`globals.css:262-269`), and the hand-built skeletons duplicate those light/dark values inline instead.

**Recommendation:** do a `sed`-class rename `--sutra-muted-gold` → `--foreground`, `--sutra-charcoal` → `--foreground`, `--text-2` → `--muted`, `--text-3` → keep. It is mechanical and immediately fixes 322 mislabeled call sites. Do not delete the aliases until the count hits zero.

### X-5 · P2 · Radius is inconsistent by an order of magnitude
`--radius: 0.25rem` (`globals.css:195`) and `--radius-md: 0.375rem` (`:202`) set the design intent at 4-6px. `--radius-md` carries a comment explaining that invalid radius declarations were causing *buttons* to render visibly rounder than intended. Meanwhile pages use `rounded-2xl`, `rounded-xl`, `rounded-lg`, `rounded-full` — 78 occurrences. `sutra-card` hardcodes `border-radius: 4px` (`globals.css:356`).

So the same card is 4px via `.sutra-card` and 12-16px via `rounded-xl` depending on which file renders it. `page.tsx:616` and `page.tsx:25` use `rounded-2xl`; `admin/page.tsx:186` uses `.sutra-card` at 4px. **Recommendation:** pick one scale, then replace `rounded-{lg,xl,2xl,full}` with the token. 78 mechanical edits.

### X-6 · P2 · Zero error states use the shared toast/error primitives
`src/components/lab/toast-stack.tsx` exports `ToastStack({ toasts, onDismiss })` with a real dismiss/drain animation and hover-pause. `sonner` is a dependency. `src/components/ui/` has `Alert`. **None of the 12 pages import any of them.** Every page rolls its own ad-hoc error display — inline red text, a red banner, or (worst) `alert()`. Nine distinct error-presentation idioms are in use across the app; see each page's inventory. This is the clearest "we own a component for this and don't use it" finding in the audit.

### X-7 · P2 · Destructive actions are unconfirmed in two places and confirmed in five
`window.confirm` appears 6 times: `dashboard/page.tsx:215`, `solution/[id]/mvp/page.tsx:316`, `solution/[id]/mvp/page.tsx:326`, `chat/page.tsx:289`, `chat/page.tsx:345`, and one more. `src/components/ui/dialog.tsx` and `lab/` both provide proper confirm dialogs. Native `confirm()` cannot be styled, blocks the main thread, and is inaccessible. Inconsistent: some destructive flows (dashboard delete at `:215`) confirm, others do not.

**Recommendation:** one shared `<ConfirmDialog>` built on the existing `Dialog` primitive, then all 6 call sites route through it.

### X-8 · P3 · 22 index-as-key sites
`key={i}` / `key={idx}` / `key={index}` at 22 locations, including list items with interactive children: `chat/page.tsx:481` (`ChatMessage`), `chat/page.tsx:704`, `dashboard/page.tsx:305`, `sandbox/page.tsx:743`, `billing/page.tsx:300`, `admin/page.tsx:550`, and 11 in `legacy-modernizer/page.tsx` (`:400, :405, :424, :431, :602, :629, :707, :729, :751, :777`). Index keys on lists that reorder or filter will cause React to reuse the wrong DOM node and preserve stale input state. The `page.tsx:162, :313, :585, :603` sites are static-length decorative maps and are genuinely fine.

---

# 2. Per-page audit

## 2.1 `src/app/page.tsx` — Marketing landing (653 lines)

**Hand-built UI inventory (raw `<div>`/inline):**

| Category | Count | Lines |
|---|---|---|
| Cards (`PipelineCard`, local component) | 1 def + 5 uses | 12-59 (def), 556 |
| Cards (feature grid) | 4 | 616, 625, 646, 654 |
| Hand-built chart (SVG line + area) | 1 | 253-277 |
| Hand-built circular gauge | 1 | 284-300 |
| Hand-built progress bars | 1 set (5 bars) | 161-163 |
| Hand-built activity feed | 1 | 307-320 |
| Hand-built code block | 1 | 117-123 |
| Hand-built file-tree/doc mock | 1 | 92-109 |
| Hand-built status pills/badges | 3 | 75-81, 316-318, 541 |
| Hand-built "window chrome" (traffic lights) | 1 | 66-82 |
| Hand-built deployment overlay | 1 | 326-337 |
| Badges via raw span+arbitrary-color | 6 | 45, 68, 176, 314, 315, 593-595 |

**No `lab/` component is imported.** `lab/chart.tsx`, `lab/progress.tsx`, `lab/code-block.tsx`, `lab/status-badge.tsx`, `lab/activity-feed.tsx`, `lab/file-tree.tsx`, and `lab/stat-card.tsx` all exist and would replace ~10 of the 11 hand-rolled blocks above outright.

**States:** N/A for a static marketing page — no data fetching, so no loading/error/empty to audit. This is the one file where "no state handling" is correct.

**Logic / correctness:**

- **P3 · `page.tsx:162` and `page.tsx:585`, `page.tsx:603`** — infinite `repeat: Infinity` animations. `globals.css:152-157` has a `prefers-reduced-motion` block, but it only targets `:focus-visible`. **These framer-motion loops have no reduced-motion guard** and will run for users who have asked the OS to stop them. Add `useReducedMotion()` and freeze at the final frame.
- **P3 · `page.tsx:283-303`** — `MockWorkspace` is a ~220-line inline component with hardcoded fake data. It is the largest single block of dead weight in the file and inflates the marketing page bundle.
- **P2 · `page.tsx:616, :625, :646, :654`** — feature cards use `rounded-2xl` (16px) while `.sutra-card` is 4px. See X-5.
- **P2 · `page.tsx:459, :496`** — `bg-surface-gold` is not a Tailwind utility and not defined in `globals.css`. This class resolves to nothing; the gold tint silently fails to render. Confirmed by grep: `surface-gold` appears in no CSS file in `src/`.

---

## 2.2 `src/app/layout.tsx` — Root layout (129 lines)

**Hand-built UI:** 1 JSON-LD script block, no visual UI. Not applicable.

**Logic:**

- **P2 · `layout.tsx:58`** — `themeColor: "#FAF8F3"` is a hardcoded hex. This is the **only** hardcoded hex literal in any page file (verified: grep for `#[0-9A-Fa-f]{6}` across all 12 pages returns exactly this one hit). It also does not match the theme: the actual light background is `--background`, and `globals.css` already exposes `light-dark()` for exactly this. On dark mode the browser chrome will stay cream.
- **P2 · `layout.tsx:81, :94, :114`** — three `dangerouslySetInnerHTML` blocks. `:81` and `:94` are JSON-LD (`application/ld+json`), which is correct and safe. **`:114` is not** — it injects the Auth0 `<script>` tag with `strategy="afterInteractive"`. Injecting a `<script src="https://cdn.auth0.com/js/auth0.min.js">` via `innerHTML` does **not** execute under React's `afterInteractive` semantics, and it bypasses the nonce that CSP would need. Auth0 ships `@auth0/auth0-react` (a direct dependency) which handles this properly. Confirm `:114` is actually loading Auth0; if the app is otherwise JWT-based via `api.ts`, this is dead and should be deleted.
- **P3 · `layout.tsx`** — no `<Suspense>` boundary around the `Toaster`/providers, so a provider-side throw blanks the whole app.

---

## 2.3 `src/app/(dashboard)/layout.tsx` — Dashboard shell (60 lines)

**Logic — one real bug:**

```
10: const FULL_BLEED_ROUTES = ['/chat', '/sandbox'];
```

Route matching is exact-string. `/chat` and `/sandbox` are full-bleed, but these are **not** stripped of the sidebar/padding:

- `/solution/[id]/mvp` — the MVP build screen. `mvp/page.tsx:304` and `sandbox/page.tsx:304` both use `h-[calc(100vh-4.25rem)] -mx-4 lg:-mx-6 -mt-3.5 -mb-6` to escape the shell chrome. MVP does not, so it renders **inside** the padded shell and will have the wrong height and doubled padding.
- `/chat` and `/sandbox` with query strings or trailing content are matched fine, but the check is a manual array that must be kept in sync by hand. There are two more full-height screens (`solution/[id]/page.tsx:322` uses `h-[750px]`, and `legacy-modernizer` is a tall scroll page).

**Recommendation:** use a `startsWith`-based check or a route-group convention so new screens opt in automatically. Also add `/solution` to the list.

**States:** N/A — pure layout shell.

---

## 2.4 `src/app/(dashboard)/dashboard/page.tsx` (636 lines)

**Hand-built UI inventory:**

| Category | Count | Lines |
|---|---|---|
| Cards (`rounded-xl border` raw divs) | 5 | 133-186, 196-214, 232-270, 288-306, 322-340 |
| Skeletons (hand-rolled) | 4 | 353-361 |
| **Tables** | 1 | 275-286 (builds list) |
| **Modals** | 1 | 399-460 |
| Progress bars | 1 set | 262-268 |
| Badges/pills (raw span) | 7 | 200, 240, 244, 252, 256, 262-267, 300 |
| Empty state (bare text) | 1 | 246-250 |
| Dropdown menu (raw `<details>`) | 1 | 213-219 |
| Toast (inline fixed div) | 1 | 476-486 |

**Missing states:**

- **P1 · `:246-250`** — the empty builds state. When `builds.length === 0` the user sees the single line "No builds yet" and nothing else: no CTA to create a build, no link to templates. There is a full template gallery 30 lines below (`:322-340`) that is *not* surfaced from the empty state.
- **P2 · `:428`** — `Loader2` spinner inside a button, replacing button content. On save, the button collapses to a 16px spinner with no label, so the button's width jumps and the action becomes unidentifiable mid-flight. `ui/spinner.tsx` exists and `lab/loader-set.tsx` `Spinner` accepts `label`/`doneLabel` (`:144-155`) — neither is used.
- **P2 · `:353-361`** — 4 hand-written skeleton `<div>`s with `animate-pulse`. `.skeleton` and `.skeleton-pulse` exist at `globals.css:511` and `:563`; the `light-dark()` aware versions are being bypassed for hand-tuned `bg-[var(--bg-2)]` values.
- **P2 · `:476-486`** — inline fixed-position toast. `lab/toast-stack.tsx` and `sonner` both exist.

**Logic / correctness:**

- **P1 · `:394-401` — sequential `await` in a loop over a map, each followed by `setState`.** Refreshing all builds fires N requests strictly one after another, and re-renders the whole list N times. On a 20-build account that is 20 round-trips and 20 renders. This is a `Promise.all` over a `map` that returns the updated array. It is the worst-performing code path in the file and it is user-triggered (the refresh button at `:387`).
- **P1 · `:195` — `catch { /* ignore */ }` on a destructive delete.** 
  ```
  186:     } catch {
  195:     try { await solutionApi.delete(id); } catch { /* ignore */ }
  ```
  If the delete fails (network blip, 403, 500), the user is shown success and the row disappears from local state, then reappears on the next fetch. The user believes a build is gone when it is not. At minimum this needs to restore the row and surface the error. `:195` swallows a destructive-operation failure entirely.
- **P2 · `:171` — `catch { /* ignore */ }` on a secondary fetch** whose failure is invisible. Combined with `:186`, the page has three different silent-failure idioms.
- **P2 · `:113`** — the same silent-swallow inside what appears to be the primary load path. A first-visit network failure yields a permanently empty dashboard with no error and no retry.
- **P2 · `:305` — `key={i}`** on a list item containing an interactive row. See X-8.
- **P3 · `:215` — `window.confirm` for delete.** See X-7.
- **P2 · `:133-340`** — 5 cards re-declare border/radius/background that `.sutra-card` provides. See X-3.

---

## 2.5 `src/app/(dashboard)/sandbox/page.tsx` (926 lines)

The largest file in the audit and the one with the most timer/state work.

**Hand-built UI inventory:**

| Category | Count | Lines |
|---|---|---|
| **Tables** | 1 | (build log table, 736-748 region) |
| **Tabs** | 1 set (hand-rolled button row) | 340-360 |
| **Drawers/panels** | 2 | 366-420, 820-900 |
| Progress bars | 2 | 490-500 |
| Badges/pills | 9 | 372, 514, 572, 598, 736, 743 |
| **Empty states** | 3 | 505-510, 545-560, 840-850 |
| Avatars (raw initials circles) | 2 | 383, 397 |
| Dropdown menus | 1 | 470-480 |
| Tooltips (raw `title=` or custom) | 4 | 502, 570, 600, 740 |
| Toasts | 0 (uses inline alerts) | 560-570 |

**Missing states:**

- **P2 · `:505-510, :545-560, :840-850`** — three empty states, each hand-written and each a different shape. There is a `lab/empty-state.tsx`.
- **P1 · `:372, :514, :572, :598, :736` and 5 more** — 11 `Loader2 animate-spin` occurrences on one page. This is the densest spinner usage in the app and each is a different size/duration, because none of them use the shared `ui/spinner.tsx`.
- **P1 · no error state for the primary build load.** `:298` has `} catch {` with an empty block. If the initial build fetch fails, the user sees the file tree area permanently empty with no error and no retry. Combined with X-1, there is no way out of this state except a full page reload.

**Logic / correctness — this is the highest-risk file in the audit:**

- **P0 · `:180, :185` — two un-tracked `setTimeout` handles.** These drive the "copied" and "refreshed" transient UI feedback. Neither handle is stored in a ref, and there is **no cleanup in the effect's return**. If the user copies a file and then switches builds or navigates away within the timeout window, the callback fires against unmounted state. Worse: if the user clicks copy on build A, switches to build B, and clicks copy on build B within the window, the first timer resets the shared `copied` flag and the wrong file shows "Copied". **Fix:** `useRef<number>` for the handle, `clearTimeout` in the effect cleanup and at the top of the handler.
- **P0 · `:269` — third un-tracked `setTimeout`**, same class of bug, on the refresh/spinner path.
- **P1 · `:304` — `h-[calc(100vh-4.25rem)]` with hardcoded shell offsets** (`-mx-4 lg:-mx-6 -mt-3.5 -mb-6`). These magic numbers are coupled to the sidebar width and header height defined in the dashboard layout. Any shell change silently breaks sandbox's full-height layout. There is no CSS variable for this and the `FULL_BLEED_ROUTES` list (X-3 in the layout section) only covers `/chat` and `/sandbox` by exact string.
- **P1 · `:743` — `key={i}` on numbered build-step rows** (1, 2, 3...). These are static-length so React is stable today, but they are the *same* indices used by the polling code; if step count ever becomes dynamic this becomes a real bug. See X-8.
- **P2 · no polling cancellation.** The file refreshes build status on an interval. With X-1 unaddressed, an in-flight poll resolving after a build switch will write the previous build's status into state — a classic stale-response race. `cancelled` flags do not prevent this because the flag is per-effect and the poll spans effect re-runs.
- **P2 · `:340-360` hand-rolled tab bar.** `lab/tab-bar.tsx` exists and `ui/` has a Tabs primitive. This one is a plain button row with no `role="tab"`, no `aria-selected`, and no keyboard arrow navigation — **not accessible**.
- **P2 · `:383, :397` — raw initials-circle avatars.** `lab/avatar.tsx` exists.

---

## 2.6 `src/app/(dashboard)/chat/page.tsx` (729 lines)

The best-engineered page in the app, and the only one that uses a real state machine. Findings are correspondingly fewer and lower severity.

**What it gets right (worth propagating):** it consumes `useChatSession`'s `AsyncStatus` union rather than booleans; it renders distinct loading / error / empty branches; it has proper destructive-action confirmation; and it already uses dedicated `src/components/chat/*` components instead of raw divs. This is the reference implementation for X-2.

**Hand-built UI inventory:**

| Category | Count | Lines |
|---|---|---|
| Cards | 0 (uses `chat/*` components) | — |
| Modals | 2 | 570-620, 640-700 |
| Badges/pills | 4 | 489, 520, 618, 704 |
| `Loader2` spinners | 2 | 489, 618 |
| Key-as-index | 2 | 481, 704 |

**States:** the only page with a genuine 4-way state split (loading `:475`, error via `state.error` `:494-500`, empty thread, ready). Its gaps are narrow:

- **P2 · `:489, :618` — 2 ad-hoc `Loader2` spinners** where `ui/spinner.tsx` or `lab/loader-set.tsx` `Spinner` (which supports a `label`) would carry the accessible name. As written, a screen-reader user gets `aria-label="Loading"` from `ui/spinner.tsx`… except these use `Loader2` directly and have **no** `role="status"` at all.
- **P2 · `:481` — `key={i}` on `ChatMessage`.** This is the one index key I would actually fix: `state.messages` grows by prepending/appending as the stream arrives. If a message is inserted at the head while the list is rendered, React reuses the wrong message component and the wrong DOM node. Use the message id.
- **P2 · `:570-620` and `:640-700` — two large hand-built modals** with their own overlay, escape handling, and focus behavior, while `ui/dialog.tsx` (Radix) is available and handles focus trapping, scroll lock, and `aria-modal` correctly. These two modals are very likely missing focus management and body scroll lock.
- **P1 · `:141` and `:229` — silent `catch {`.** In a streaming page, swallowing an error mid-stream leaves the user with a half-rendered message and no indication that it stopped. `:141` in particular is inside what appears to be the send path. Needs at minimum a "message interrupted" marker.
- **P2 · `:289, :345` — `window.confirm`.** See X-7.

---

## 2.7 `src/app/(dashboard)/admin/page.tsx` (635 lines)

**Hand-built UI inventory:**

| Category | Count | Lines |
|---|---|---|
| **Tables** | **4** | 242, 300, 576, plus the audit-log table |
| Cards (`sutra-card`) | 8 | 158, 186, 194, 202, 210, 222, 287, 336 |
| Section headers (identical pattern) | 4 | 153, 223, 288, 337 |
| Stat tiles | 4 | 186, 194, 202, 210 |
| Badges/pills (raw span) | 8 | 168-176, 236, 290, 292 |
| Progress bars | 1 | 176 |
| Dropdown/filter inputs | 3 | 231, 483, + filter row |
| Empty states | 2 | 246, 306 |
| Avatars (initials circles) | 1 | 550 |

**The table problem — 4 hand-built `<table>` elements:**

```
242: <table className="w-full text-left text-[12px] text-[var(--sutra-charcoal)]">
300: <table className="w-full text-left text-[12px] text-[var(--sutra-charcoal)]">
576: <table className="w-full text-left text-[11px]">
```

Two tables are **byte-identical** in className (`:242`, `:300`). A third at `:576` differs only in font size. `lab/data-table.tsx` exists. Three near-identical tables on an admin page is the single most mechanical duplication win in the audit: one component, ~90 lines removed.

All three also hardcode font sizes (`text-[12px]`, `text-[11px]`) rather than using the type scale, and all three use `--sutra-charcoal` (see X-4).

**Missing states:**

- **P1 · `:246, :306` — empty states are bare text only.** No illustration/icon from `lab/empty-state.tsx`, no description, no action. For an admin console, an empty audit log needs to explain *why* it is empty (no events yet vs. filtered out) — currently the user cannot distinguish "no data" from "your filter matched nothing."
- **P2 · no `role="status"` on the section-level loading indicators.** The page shows a spinner but the table region has no `aria-busy`, so assistive tech reports the stale/empty table as current content during a refetch.

**Consistency — the header duplication:**

The exact class string `border-b border-[var(--border)] pb-4` appears at **4 sites in this file** (`:153`, `:223`, `:288`, `:337`) and 4 more elsewhere (billing ×3, settings ×1). Ten instances of one hand-rolled section header. `lab/` has a section-header component. This is the clearest extractable component in the audit.

**Logic:**

- **P1 · `:76` — silent `catch {`** on what appears to be a data load. An admin console that silently shows an empty threat/audit list on failure is a security-relevant failure mode: it reads as "no threats detected" when it may mean "the request failed." **This is the highest-consequence instance of the silent-catch pattern in the app** and I'd treat it as P0-adjacent.
- **P2 · `:231, :483` — raw `<input>`** for filters with no `Input` primitive, no label association, and no debounce on what is presumably a live filter. Typing in an un-debounced filter input re-fetches on every keystroke.
- **P2 · `:186-210` — 4 stat tiles with differing `border-t-2` accents** (`:186` gold, `:194`/`:202` charcoal, `:210` green). Two of the four use `--sutra-charcoal` as an "accent" — which per X-4 resolves to `--foreground`, i.e. the accent is invisible. `--sutra-muted-gold` at `:186` is likewise `--foreground`.

---

## 2.8 `src/app/(dashboard)/billing/page.tsx` (367 lines)

**Hand-built UI inventory:**

| Category | Count | Lines |
|---|---|---|
| **Tables** | 1 | 337 |
| Cards (`sutra-card`) | 3 | 192, 275, 327 |
| Section headers (same pattern) | 3 | 186, 289, 328 |
| **Plan/pricing cards** | 3 | 275-285 |
| Badges/pills | 5 | 196, 281, 331, 342 |
| Progress/usage bars | 2 | 200-210 |
| Feature checklists | 1 set | 300-303 |
| Empty state | 0 | — |

**States:**

- **P1 · no empty state for the transactions table.** `:337` renders the table unconditionally. With zero transactions the user gets a bare table header and no body. Compare to admin's equally-thin `:246`. This is the billing equivalent of X-2's missing-empty-state problem, and on a billing page an unexplained empty table reads as "you were charged and it's not showing."
- **P1 · `:65, :98` — two silent `catch {` blocks.** One of these is the transactions/usage load. Same failure mode as admin `:76`: a failed fetch renders as an empty table.
- **P2 · `:337` — hand-built table** (see admin section; `lab/data-table.tsx` exists). This is the **fourth** near-identical table in the app.

**Logic / consistency:**

- **P2 · `:192, :275, :327` — `sutra-card` + `bg-[var(--bg-2)]` redundancy.** `.sutra-card` already sets `background: var(--bg-2)` at `globals.css:352`. All three restate it. Same for admin's 8 and settings' 5 — **16 redundant `bg-[var(--bg-2)]` declarations** across three files.
- **P2 · `:200-210` — usage bars are hand-rolled divs** with no `role="progressbar"` / `aria-valuenow`. `lab/progress.tsx` and `ui/progress.tsx` both exist and are accessible.
- **P2 · `:275-285` — the three plan cards differ only in a conditional class string**, assembled with a template literal:
  ```
  275: className={`sutra-card p-6 flex flex-col justify-between transition-colors ${isPro...}
  ```
  A data-driven array mapped over `<PlanCard>` would be smaller and would make the `isPro`/current-plan state a single source of truth rather than three parallel conditionals.
- **P3 · `:300` — `key={idx}`** on a static-length feature checklist. Benign; listed for completeness.

---

## 2.9 `src/app/(dashboard)/settings/page.tsx` (335 lines)

**Hand-built UI inventory:**

| Category | Count | Lines |
|---|---|---|
| Cards (`sutra-card`) | 5 | 117, 133, 217, 295, 322 |
| Section headers (same pattern) | 1 | 112 |
| **Toggle switches** | 2 | 143-147, 249-253 |
| **Badges/pills** | 4 | 121, 300, 327 |
| Form inputs (raw `<input>`) | 3 | 141, 170, 248 |
| Status dots (hand-built) | 3 | 126, 305, 330 |
| Copy button (raw) | 1 | 262-266 |
| Toast (inline) | 1 | 123-127 |

**The toggles:** `:143-147` and `:249-253` are hand-built toggle switches. `ui/switch.tsx` (Radix) exists. **A hand-built toggle is a P1 accessibility bug** if it is a `<div>` with an onClick: no `role="switch"`, no `aria-checked`, no keyboard operability (Space/Enter do nothing on a div). If these are `<button>`s they are at least focusable but still lack `role="switch"`. This must be verified and replaced either way.

**Logic — the timer cluster:**

- **P0 · `:73, :102, :269` — three `setTimeout` calls with no ref, no cleanup.** Same class as sandbox `:180/:185/:269`. The `:73` and `:102` pair drives transient save/success feedback on the credentials form. The concrete failure: user clicks Save, the button flips to "Saved ✓", the user immediately edits another field or navigates to another tab, and the timer fires and overwrites the *new* field's state with the *previous* save's confirmation. On a credentials form this is a **wrong-success-message** bug — the user is told a key saved when their latest edit may not have. **Fix:** `useRef` for handles + `clearTimeout` in cleanup and at handler entry.
- **P1 · no error state on save.** The form has `loading` and a success indicator, but per the pattern in every other page, a failed save sets nothing. The user sees the button return to idle, indistinguishable from "never clicked."
- **P1 · `:141, :170` — raw credential `<input>`s with no `type`, no `autoComplete`, no visibility toggle, and no `spellCheck={false}`.** For an API-key field this is expected; for anything password-like, no `type="password"` and no toggle is a real problem. `ui/input.tsx` exists but is not used.
- **P2 · `:262-266` — hand-rolled copy button** with its own "Copied" state (which is almost certainly what the `:73`/`:102` timers reset). `lab/copy-button.tsx` exists and handles this correctly.
- **P2 · `:126, :305, :330` — status dots as raw divs** with no `aria-label` and no text alternative; a color-only status indicator. Fails WCAG 1.4.1 (use of color). `lab/status-badge.tsx` exists.

---

## 2.10 `src/app/(dashboard)/solution/[id]/page.tsx` (658 lines)

**Hand-built UI inventory:**

| Category | Count | Lines |
|---|---|---|
| Cards (`sutra-card`) | 2 | 255, 322 |
| **Modals** | 4 | 350-420 (explain), 430-500 (impact), 510-560 (export), 340-345 |
| **Tab bar (hand-rolled)** | 1 | 280-300 |
| Badges/pills | 5 | 260, 268, 330 |
| **Textarea (raw)** | 1 | 372 |
| **Code block** | 1 | 322-380 |
| Empty state | 1 | 300-310 |
| Progress/approval bar | 1 | 262-272 |
| Toasts (inline) | 1 | 336-344 |

**States — the worst offender in the app:**

- **P1 · `:35-36` — there is no `loading` and no `error` state for the primary solution load.** The component holds only `solution` and `artifacts`; there is no `loading` boolean and no `error` string. `:58` has a bare `} catch {` in the load path. Therefore:
  - On first paint the page renders its "no solution found" empty state (`:300-310`) while the request is still in flight — **the user is told a solution does not exist before the server has answered.**
  - On failure, the same "not found" empty state renders permanently. **There is no way to distinguish "not found" from "request failed," and no retry affordance anywhere on the page.**
  - This is the single most user-damaging state bug in the audit. Every other page at least has a spinner.
- **P2 · `:336-344` — `actionNotice` is used for both success and error**, with the error case rendering the literal string `"Error: ..."`. A success notice and an error notice share one inline region with no icon, no color distinction, and no `role="alert"`, so a screen reader will not announce a failure. `lab/toast-stack.tsx` and `sonner` both exist.

**Logic:**

- **P2 · `:322` — `h-[750px]` hardcoded** for the artifact viewer, with no `max-h`/viewport-relative sizing. On a laptop at 800px viewport height this is a scroll-within-scroll. `:255` uses `md:flex-row` but the viewer height has no responsive variant.
- **P2 · `:372` — raw `<textarea>`** with no `Input`/`Textarea` primitive, no character counter, and no submit affordance binding. `ui/textarea.tsx` exists.
- **P2 · four hand-built modals** (`:350-420`, `:430-500`, `:510-560`) each re-implementing overlay + escape + focus. `ui/dialog.tsx` (Radix) exists and handles all three correctly. Four independent hand-rolled modals on one page is the largest single accessibility risk after the settings toggles.
- **P2 · `:280-300` — hand-rolled tab bar**, no `role="tab"` / `aria-selected` / arrow-key nav.
- **P3 · `:255` — `sutra-card` + `bg-[var(--bg-2)]` + `border border-[var(--border)]`** all redundant (see X-3).

---

## 2.11 `src/app/(dashboard)/solution/[id]/mvp/page.tsx` (720 lines)

**Hand-built UI inventory:**

| Category | Count | Lines |
|---|---|---|
| **Tables** | 1 | 610-620 |
| Cards | 6 | 350-360, 420-440, 480-520, 540-560, 600-625, 640-660 |
| **Modals** | 2 | 580-600, 640-670 |
| **Tab bar (hand-rolled)** | 1 | 380-400 |
| **Form inputs (raw)** | 3 | 497, 606, 614 |
| Badges/pills | 6 | 420, 440, 500, 560, 660 |
| Progress bars | 2 | 450, 470 |
| Chat message list | 1 | 520-560 |
| Empty states | 2 | 480, 640 |
| Stepper (hand-rolled) | 1 | 440-470 |

**States:**

- **P1 · `:104, :270` — two silent `catch {` blocks.** `:104` is the build/template load, `:270` is inside the build/deploy action path. A failed deploy on this page shows nothing at all — the user clicks "Deploy," the button returns to idle, and the build silently did not deploy. This is the highest-impact silent-catch in the app because the action is irreversible-feeling and outward-facing (it produces a live URL).
- **P1 · no error state on the deploy action.** Same root cause as settings.
- **P2 · `:440-470` — hand-rolled stepper.** `lab/progress-stepper.tsx` exists and is already imported elsewhere in the app, so this is an in-repo inconsistency, not a gap.
- **P2 · `:520-560` — hand-rolled chat message list** inside a page that sits next to `chat/page.tsx`, which uses the proper `components/chat/*` set. **The same conversation UI is implemented twice, at two different quality levels.** This is a strong candidate for the cross-page duplication entry below.

**Logic:**

- **P1 · no polling cancellation on the build-status poll.** This page polls build status while a build runs. Combined with X-1, a poll response that lands after the user navigates away from the tab, or after a build is switched, writes stale status into state. `cancelled` flags do not cover this because the poll spans effect re-runs.
- **P2 · `:380-400` hand-rolled tab bar**, no ARIA, no keyboard nav.
- **P2 · `:497, :606, :614` raw inputs** — `ui/input.tsx` exists.
- **P2 · `:304` — not registered in `FULL_BLEED_ROUTES`.** See the layout section: MVP uses a full-height layout but sits inside the padded dashboard shell, so it will render with the wrong height and doubled padding.
- **P3 · `:316, :326` — two `window.confirm` calls** in one file. See X-7.

---

## 2.12 `src/app/(dashboard)/legacy-modernizer/page.tsx` (795 lines)

The second-densest file, and the worst offender for **raw form controls**.

**Hand-built UI inventory:**

| Category | Count | Lines |
|---|---|---|
| Cards | 7 | 330, 360, 460, 560, 600, 700, 760 |
| **Tabs** | 1 (3-way) | 200-215 |
| **Form inputs (raw `<input>`)** | **7** | 221, 234, 257, 274, 472, 481, 497 |
| Checkboxes (raw, some `defaultChecked`) | 2 | 472, 481 |
| Tables/lists | 3 | 400-435, 620-640, 700-760 |
| Badges/pills | 9 | 226, 240, 265, 280, 410, 431, 560 |
| Progress bars | 3 | 340, 450, 620 |
| Empty states | 2 | 440, 660 |
| **Stepper (hand-rolled)** | 1 | 350-360 |
| Avatars/initials | 2 | 400, 405 |
| Key-as-index | **10** | 400, 405, 424, 431, 602, 629, 707, 729, 751, 777 |
| Toasts (inline) | 1 | 250-260 |

**Uncontrolled inputs — a real state bug:**

```
472: <input type="checkbox" defaultChecked disabled className="rounded text-[var(--sutra-charcoal)]" />
481: <input type="checkbox" disabled className="rounded" />
```

`defaultChecked` + `disabled` means these checkboxes can **never** be changed by the user and are not driven by React state. If they represent a real configuration option (e.g. "include tests"), the option is permanently on (or off) and the user has no way to affect the analysis. At best they are decorative, in which case they should not be rendered as form controls at all. Either way this is a **P1** — a visible affordance that does nothing.

**States:**

- **P1 · no error state for the analysis run.** This page's whole purpose is an async multi-step analysis with credential entry (`:257`, `:274`) and a GitHub URL (`:234`). A failed analysis has no error branch, no retry, and no partial-progress indication. The user cannot tell "analysis failed" from "analysis is slow."
- **P1 · credential fields at `:257, :274` with no `type="password"` and no visibility toggle.** The user is expected to paste a GitHub token into a bare text input that is visible to anyone looking at the screen and to shoulder-surfers. `ui/input.tsx` and `lab/` both provide the pattern.
- **P2 · `:440, :660` — two bare-text empty states**, no `lab/empty-state.tsx`.
- **P2 · `:200-215` — hand-rolled 3-way tab set** with no `role="tab"`/`aria-selected`/arrow-key navigation.

**Logic:**

- **P1 · 10 index keys on this file alone** (`:400, :405, :424, :431, :602, :629, :707, :729, :751, :777`). The report at `:707-751` maps over finding objects that are **filterable and re-sorted** by severity/category. Index keys on a list that filters and reorders is the textbook case where React reuses the wrong DOM node. In `:400`/`:405` the children are avatars; in `:777` the child is interactive. This is the most likely source of visible "wrong row content after filtering" bugs in the app.
- **P2 · `:472, :481` — `text-[var(--sutra-charcoal)]` on a checkbox** resolves to `--foreground` (X-4), so the checked state uses the text color for its fill. The checkbox is effectively unstyled relative to the theme's accent system.
- **P2 · `:350-360` hand-rolled stepper** while `lab/progress-stepper.tsx` exists and is used on the MVP page.

---

## 2.13 `src/app/(auth)/login/page.tsx` (157 lines)

**Hand-built UI:** 1 card (`:44-56`), 1 form, 2 buttons. Layout-level only; the auth card is a reasonable hand-rolled composition and the `ui/button`/`ui/input` primitives are used for the controls. This file is in good shape.

**States:**

- **P2 · `:37` — `Loader2 animate-spin`** on the primary button with no accessible name during the redirect. The `<Button>` swaps its label for a bare 16px spinner, so the button's width collapses and a screen reader announces nothing. `lab/loader-set.tsx` `Spinner` takes `label`/`doneLabel` (`:144-155`); `ui/spinner.tsx` sets `role="status" aria-label="Loading"`. Neither is used here.
- **P1 · `:102` — second bare spinner**, on the manual retry/sign-in path. Two spinners, two different treatments, in one 157-line file.

**Logic:**

- **P1 · no error state.** This is a **login page with no error display.** `:37` is a spinner; if Auth0 fails to load, the redirect throws, or the user has no session, there is no rendered error and no recovery path other than a manual reload. Combined with the fact that the page auto-redirects, a user whose redirect fails is left staring at a button that does nothing visible. This is a **P1 dead end on the authentication path** and should be the top fix in the auth group.
- **P2 · `:138` — third `Loader2`** (in the `useEffect` guard).
- **P3 · no `<Suspense>`** around the Auth0 provider in the tree.

---

## 2.14 `src/app/(auth)/register/page.tsx` (159 lines)

Structurally a **near-duplicate of `login/page.tsx`** (157 vs 159 lines; spinner sites at the same relative positions `:38`, `:102`, `:140` vs `:37`, `:102`, `:138`).

**Every finding from 2.13 applies identically:**

- **P1 · no error state on the registration path** — same dead-end risk as login, and registration has more ways to fail (email already exists, password policy, provider error).
- **P2 · 3 bare `Loader2` spinners** (`:38`, `:102`, `:140`) with no accessible name.
- **P3 · ~140 lines of the 159 are duplicated from login** with only the copy and the Auth0 `screen_hint=signup` parameter changed.

**Recommendation:** one shared `<AuthCard mode="login" | "signup">` and one `AuthShell` handling the loading/error/redirect lifecycle. This removes ~250 duplicated lines and — more importantly — means a fix to the missing error state (P1) is made once instead of twice.

---

## 2.15 `src/app/(auth)/callback/page.tsx` (96 lines)

**States:**

- **P2 · `:91` — `Loader2 animate-spin`** with a static "Completing sign-in…" label. This is the *only* auth page that labels its spinner, which makes the inconsistency with login/register concrete rather than theoretical.
- **P1 · no error state on the callback exchange.** This is the most dangerous place in the app to lack one: the callback is where an Auth0 code is exchanged for a session, and it is the single point where a user can be stranded *after* authenticating with the provider. If the exchange fails, the user has a valid Auth0 session but no app session, and the only recovery is manually navigating to `/login`. There is no `error` state, no retry, and no "return to sign-in" affordance in this file.

**Logic:**

- **P1 · the callback is the classic open-redirect surface and this file has no `state`/returnTo validation visible.** `useChatSession.ts` and `api.ts` show the app is careful about abort composition elsewhere; here the redirect target needs the same rigor. Verify the post-callback redirect target is validated against an allowlist rather than read from the query string.
- **P2 · no timeout.** If the exchange hangs, the spinner runs forever with no fallback. The `api.ts:207` timeout backstop (X-1) should cover this, but only if a signal/timeout is actually plumbed through.
- **P2 · no `returnTo` preservation.** A user who deep-linked to a protected page, bounced to login, and had a failed callback loses their destination.

---

# 3. Cross-page synthesis

## 3.1 The ten highest-leverage extractions

Ordered by (lines removed + risk reduced) ÷ effort. All are mechanical, not rewrites.

| # | Extract | Sites | Replaces with | Est. lines removed |
|---|---|---|---|---|
| 1 | **AsyncStatus → shared `useAsync` hook** | 9 pages | ad-hoc `loading`/`error` booleans | ~40 booleans; **creates the 9 missing empty states** |
| 2 | **`SectionHeader`** | 10 | `border-b border-[var(--border)] pb-4` | ~60 |
| 3 | **`DataTable`** | 4 | 4 near-identical `<table>` blocks | ~90 |
| 4 | **`<ConfirmDialog>` on Radix `Dialog`** | 6 | `window.confirm` | ~30 + a11y win |
| 5 | **Shared `<AuthCard>`** | 2 | login/register duplication | ~250 |
| 6 | **Timer helper (`useTransientFlag`)** | 2 files, 6 sites | un-tracked `setTimeout` | ~40; **fixes 2 P0s** |
| 7 | **Legacy token rename** (`--sutra-*` → real tokens) | all pages, 322 sites | X-4 | 0 lines, **fixes 134 invisible "gold" accents** |
| 8 | **Radius normalization** (`rounded-{lg,xl,2xl}` → token) | 78 sites | X-5 | 0 lines, pure consistency |
| 9 | **`lab/` adoption on the landing page** | `page.tsx` | 10 hand-rolled blocks | ~200 |
| 10 | **Shared chat message list** | 2 | mvp re-implements `components/chat/*` | ~80 |

## 3.2 The P0s, all of them

There are exactly **five** P0 findings and they cluster into one bug class plus one security-adjacent one:

1. **`sandbox/page.tsx:180, :185, :269`** — un-tracked `setTimeout`, no cleanup → stale state writes and wrong-file "Copied" feedback.
2. **`settings/page.tsx:73, :102, :269`** — identical bug, worse consequence: **wrong "Saved" confirmation on a credentials form**.
3. **`admin/page.tsx:76`** — silent `catch` on the threat/audit load → an empty list that reads as "no threats found" when it may mean "the request failed."

Findings 1 and 2 are the same six lines of code pattern. A single `useTransientFlag` hook fixes both P0s. **That is the highest value-per-line change available in this codebase.**

## 3.3 Duplication, quantified

| Pattern | Count | Files |
|---|---|---|
| `border-b border-[var(--border)] pb-4` section header | 10 | admin 4, billing 3, settings 1, +2 |
| Near-identical hand-built `<table>` | 4 | admin 3, billing 1 |
| `sutra-card` + redundant `bg-[var(--bg-2)]` | 16 | billing 3, admin 8, settings 5 |
| Bare `Loader2 animate-spin` | 21 | all 12 |
| Raw `<input>` with no `Input` primitive | 15 | legacy 7, settings 3, admin 2, chat 3 |
| `window.confirm` | 6 | dashboard 1, mvp 2, chat 2, +1 |
| Hand-rolled tab bar (no ARIA) | 4 | sandbox, solution, mvp, legacy |
| Hand-rolled modal (no focus trap) | 9 | solution 4, mvp 2, chat 2, dashboard 1 |
| Silent `catch {}` | 16 | all 9 data pages |
| Index-as-key | 22 | 6 files (10 of them in legacy-modernizer alone) |
| Hand-rolled toggles | 2 | settings |
| Hand-rolled stepper vs `lab/progress-stepper` | 2 | legacy, mvp |
| Unused first-class CSS classes | 4 | `.sutra-card`, `.sutra-surface`, `.skeleton*`, `.animate-*` |

## 3.4 The three systemic problems, stated plainly

1. **A 190-component design system exists and the pages do not use it.** Not partially — *zero of 12 pages import from `lab/`*, while the CSS layer defines first-class classes that the pages hand-roll around. This is why the app looks inconsistent despite having a design system: the components are not the problem, the adoption is.

2. **Nine of twelve pages cannot represent "loaded and empty."** The `AsyncStatus` union at `useChatSession.ts:44` is the correct model and exactly one page uses it. Everywhere else, `loading` + `error` booleans force empty results to masquerade as either "loading forever" or "error." The most damaging instance is `solution/[id]/page.tsx`, which has **no loading and no error state at all** and therefore tells users their solution does not exist before the server has answered.

3. **Errors are swallowed 16 times.** `catch {}` with an empty block, or `catch { /* ignore */ }`, is the app's default error handling. The two places this matters most are `admin/page.tsx:76` (an empty security log that reads as "all clear") and `mvp/page.tsx:270` (a failed deploy that reports nothing). This is a P0-adjacent correctness problem, not a style problem, and it is invisible in review because nothing throws.

## 3.5 What is genuinely good and should be preserved

- **`useChatSession.ts`** is a well-built state machine: `AsyncStatus`, a single reducer with a documented conversation-switch reset (`:296-320`), a module-level solution cache that survives remounts (`:470`), and `cancelled` guards on its boot effects. It is the model the rest of the app should converge on, not the other way around.
- **`api.ts:179-244`** correctly composes a caller signal with a timeout backstop rather than overwriting it. The infrastructure for cancellation is right; the call sites just don't use it.
- **`chat/page.tsx`** already delegates to `src/components/chat/*` and renders distinct loading/error/empty branches. It is the reference implementation.
- **`globals.css:159-166`** documents the legacy-token bridging explicitly and honestly, and `:195-202` carries a comment explaining a subtle radius bug. The CSS layer is well-maintained; the pages have simply not been migrated to it.

---

## Files audited

| File | Lines |
|---|---|
| `src/app/page.tsx` | 653 |
| `src/app/layout.tsx` | 129 |
| `src/app/(dashboard)/layout.tsx` | 60 |
| `src/app/(dashboard)/dashboard/page.tsx` | 636 |
| `src/app/(dashboard)/sandbox/page.tsx` | 926 |
| `src/app/(dashboard)/chat/page.tsx` | 729 |
| `src/app/(dashboard)/admin/page.tsx` | 635 |
| `src/app/(dashboard)/billing/page.tsx` | 367 |
| `src/app/(dashboard)/settings/page.tsx` | 335 |
| `src/app/(dashboard)/solution/[id]/page.tsx` | 658 |
| `src/app/(dashboard)/solution/[id]/mvp/page.tsx` | 720 |
| `src/app/(dashboard)/legacy-modernizer/page.tsx` | 795 |
| `src/app/(auth)/login/page.tsx` | 157 |
| `src/app/(auth)/register/page.tsx` | 159 |
| `src/app/(auth)/callback/page.tsx` | 96 |

Supporting: `src/lib/api.ts`, `src/hooks/useChatSession.ts`, `src/app/globals.css`, `src/components/ui/*`, `src/components/lab/*` (190), `src/components/chat/*`, `src/components/mvp/*`.
