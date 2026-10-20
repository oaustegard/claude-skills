---
name: marking-up-pages
description: Let the user draw on a live web page in Chrome (circle, underline, arrow) and type a note per mark, then read back what each mark points at - element, selector, computed styles, React/Vue/Svelte component and source file - plus console errors and failed requests, and fix it. Uses Claude in Chrome. Use when the user wants to mark up, annotate, scrawl on or point at something on a page, says "let me show you", "look at my marks", "I circled it", or asks for visual feedback on a site or local dev server.
metadata:
  version: 0.2.0
---

# Marking up pages

The user draws on the page and notes what is wrong; you get each mark tied to the real DOM element and, on dev builds, its component and source file. The marks are the bug report: read them before answering and don't ask the user to re-describe what they already marked.

Needs the Claude in Chrome tools (`javascript_tool`, `computer`, `tabs_context_mcp`). Load them in one ToolSearch call if they are deferred. The JavaScript tool runs in the page's own world and ignores the page's CSP, which is what makes this work.

## 1. Open the overlay

Use the user's tab (find it with `tabs_context_mcp`). Run the loader first; it is one line and costs nothing:

```js
window.__scrawl ? (__scrawl.show(), __scrawl.status()) : (c => c && JSON.parse(c).version === '0.2.0' ? (0, eval)(JSON.parse(c).src) : 'NO_CACHE')(localStorage.getItem('page-scrawl:src'))
```

If it returns `NO_CACHE`, read `scripts/overlay.js` and pass the whole file as the `text` of `javascript_tool`. The overlay caches itself in that origin's `localStorage`, so after a reload the loader is enough. (Keep the version in the loader equal to `VERSION` in `overlay.js`.)

Then tell the user, briefly: draw on the page; after each mark a note box opens — type or dictate what's wrong, Enter saves; ⌥⇧S toggles drawing so they can click around in between; press **Done** and tell you when finished. Then stop and wait. Don't poll.

If the user opened it themselves with the bookmarklet, skip to step 2. If they instead paste copied marks or attach a `*.scrawl.json` file (the toolbar's **Copy** and **Save** buttons, for use without Claude in Chrome), read that: the file's `summary` field is the same text as `summary()`, and the rest is `export({ points: true })`. You can't screenshot or `focus` marks from a file, so lean on the selectors, text and source locations.

## 2. Read the marks

```js
__scrawl.summary()
```

```text
[page-scrawl · 3 marks · “Settings” · http://localhost:5173/settings · 1440×900 @2x]
- #1 underline over “setings” → `h1` “Notification setings” ‹SettingsForm› src/pages/Settings.tsx:23 — “typo: settings”
  style: font 22px/normal 700 Inter · color rgb(17, 17, 17) · display block · margin 14.7px 0px
- #2 arrow → `button[data-testid="save"]` “Save changes” ‹SaveButton › SettingsForm› src/components/SaveButton.tsx:14 — “hugs the divider”
- #3 circle over “Recieve email updates” → `div.row:nth-of-type(1) > label` ‹Toggle› src/components/Toggle.tsx:9
Failed requests since page load:
  · 404 fetch http://localhost:5173/api/prefs
```

- `→` is the element the mark points at: for a circle, what it encloses; for an underline, the text above it; for an arrow or line, what is at its tip. `also:` lines are other enclosed elements or the arrow's tail.
- `‹A › B›` is the component chain, innermost first, then the source location when the dev build exposes it (React ≤18 `_debugSource`, React 19 stack, Vue `__file`, Svelte `__svelte_meta`, or `data-*` inspector attributes like `data-insp-path`). Production builds give minified names or nothing; fall back to the selector, text and classes.
- The quoted text after `—` is the user's note. A mark with no note means "this" — work out what is wrong from the screenshot.
- `not marked Done yet` means the user may still be drawing; check with them if that's unexpected.

For the full data (bounding boxes, every style, `others`, console errors), use `JSON.stringify(__scrawl.export())`. Pass `{ points: true }` to include stroke points.

**Look at it too.** Hide the toolbar, screenshot, then bring it back:

```js
__scrawl.chrome(false)   /* then computer screenshot; then: */  __scrawl.chrome(true)
```

Badges `1`, `2`, … on the ink match the `#n` numbers. For a mark outside the viewport or a small detail, `__scrawl.focus(n)` scrolls it into view and returns its box `{x0,y0,x1,y1}` in CSS pixels. Screenshot coordinates can differ from CSS pixels (a 1648 px wide viewport may screenshot as a 1512 wide frame): multiply by the screenshot frame width ÷ `viewport.w` from the summary before passing the box to a `computer` zoom. Trust the screen over the summary when they disagree (for example, a circle that grabbed a parent element).

Refer to marks as "#2" when you reply, so the user can find them on the page.

## 3. Fix and verify

When the page is the user's own code (a local dev server, or a repo you have open):

1. Go from each mark to the source: the source location if given, else grep the component name, then the text, then distinctive classes.
2. Make the change.
3. Wait for HMR, or hard-reload the tab (`computer` key `cmd+shift+r`; a plain reload can show a cached page and make a fix look like it failed). Check the change is really on the page (read the marked element's text or style) before judging it. A reload removes the overlay: run the loader again, then `__scrawl.restore()` to bring back the old marks (flagged `restored`), drawn where they were.
4. Screenshot to check each mark is resolved. `__scrawl.ink(false)` hides the ink for a clean "after" shot. Report per mark.

When it's someone else's site, report what each mark points at and what you'd change.

## API

`window.__scrawl`: `status()`, `summary()`, `export(opts)`, `copy()`, `save()`, `focus(n)`, `chrome(bool)`, `ink(bool)`, `draw(bool)`, `show()`, `hide()`, `undo()`, `clear()`, `restore()`, `destroy(forget)`. `destroy(true)` also removes the cached script and saved marks; do that when the user is done with marking up on that site.

## Gotchas

- **Claude in Chrome's output filter** redacts results that look like secrets: version strings like `0.1.0` come back as `[BLOCKED: JWT token]`, and a block of `key value; key value` lines is blocked as cookie data. That's why the summary separates styles with `·`. If a result is blocked, return a smaller or reshaped piece of it instead of retrying the same call.
- **Which browser.** The user may have several Chrome browsers connected, possibly on different machines. A `localhost` URL in that browser is that machine's localhost: check that the page is the app you are editing before changing code for it.
- Ink is pinned to the document and follows page scroll, not scrolling inside inner panes. Cross-origin iframes and closed shadow roots can't be inspected; the mark falls back to the frame or host element.
- While drawing is on, the canvas swallows clicks. Menus that close on outside clicks may close: have the user open the menu with drawing off, then press ⌥⇧S and mark it.
- The overlay records `console.error` and uncaught errors only from when it opened. Failed requests come from the Resource Timing API and cover everything since the page loaded.

## Bookmarklet

`python3 scripts/make_bookmarklet.py out.html` writes a page with a drag-to-bookmarks-bar link, so the user can start marking without asking you first. Without Claude in Chrome on that tab, the toolbar's **Copy** puts the summary on the clipboard and **Save** downloads `<host>-<date>-<time>.scrawl.json`; either can be handed to Claude in any chat. Strict-CSP sites may block it; the JavaScript tool still works there.
