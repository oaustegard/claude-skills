<!-- Split from aboard-io/tinylittleoffice skill/tinyoffice/SKILL.md (MIT). Build a link from an example with scripts/tlo.py. -->

# Files, short links, the JS API and the official linter

## Every app's files

Every document downloads as a `.pdf` (its pages as pictures; Print in the browser saves one with the words still words), a picture (`.png`), a web page (`.html`), Markdown (`.md`, footnotes in Markdown's reference form) and its own text (`.tlo`: the TLO with `app: <id>` in its head, which opens as its own app when dropped on the site). A `.zip` of `.tlo` and `.md` files, a folder per app, opens the same way when dropped: every document in it is kept on the device (with Save in browser off, listed to keep or to open). A link that downloads a file as it opens is `#/v1/<app>.<ext>/<payload>`, or `view=<ext>` in the plain form.

## Short links

The API below is this site's. Make a short link at the shortener of the site the link opens on, `tinier.<the site's host>`: the shortener opens only links to its own site. An agent on a development machine running its own copy of the site uses that site's `/tinier/` (the shortener started with `SITE` set to the site's address, `npm run tinier:dev`), and the link it makes opens there; production's shortener accepts only links to production.

A long link can be shortened at tinier.tinylittleoffice.com for an hour, a day, a week or a month. The link is encrypted where it is made (AES-256-GCM, a random key); only the ciphertext goes to the service, and the key travels in the short link's fragment, which browsers never send. A program can do the same:

```
POST https://tinier.tinylittleoffice.com/api   {c, iv, ttl}   → 201 {id, exp}
```

`c` and `iv` are the AES-GCM ciphertext of the long link and its 12-byte IV, base64url; `ttl` is 3600, 86400, 604800 or 2592000 seconds (a month at most). The short link is `https://tinier.tinylittleoffice.com/<id>#<key>` (the key as base64url). A short link cannot be changed or recalled once made; it expires on its own, so make a new one for a new version. The ciphertext may be 16 KiB at most (a link of at most 12,272 characters; `measure` says whether yours fits, `short: {fits, over}`, `over` the characters to cut), and one address may make a hundred links a day (the 101st is 429, with `Retry-After`).

## Who made it

The head may carry `created` (when the document was first written, to the minute) and `by` (who made it, a claim: nothing proves it). Write `by` to say who you are.

## Without a browser

The site serves its own API as a module, for programs and agents; in a browser, Deno or Bun it imports as it is:

```js
import { link, plain, read, text, compare, apps, templates } from 'https://tinylittleoffice.com/api.js';
const url = link('sheet', 'Item | Cost:money\n--- | ---\nRent | 1200\n', { title: 'Budget', by: 'planner-agent' });
read(url).text;                 // the document's TLO text, its title and by in the head
await text(url);                // what the document says, as Markdown: what a screen reader reads on its Display Link
compare(url, revised).changes;  // what the second link changed, block by block
await templates('deck');        // what a deck can start from
```

A document under a password: `await link(app, text, { seal: true })` (or `tinyoffice link --seal`) returns `{ url, password }`: the link holds only ciphertext, and the password is one the app made (twenty random characters). Give the person the password apart from the link, and tell them to send it another way than the link. You cannot choose the password: one handed in (`password:`, `--password`) is refused with "The app makes the password; ask for one with seal."

An agent that would rather send structure than write TLO can send JSON: `fromJson(json)` gives the TLO text (so `link(app, fromJson(json))`, or `tinyoffice link <app> --json doc.json`), and `toJson(text)` (`read(url).json`, `tinyoffice json <link>`) gives the kernel's document as JSON, a head and a list of blocks with their runs.
It is the same document, nothing added or renamed, to the JSON Schema at https://github.com/aboard-io/tinylittleoffice/blob/main/packages/doc/schema/tlo.schema.json; one that does not fit is refused, naming where (`blocks[2].runs[0].t is missing`).

Node does not import a module from a URL: in Node, use the command line, `npx tinylittleoffice` (the npm package `tinylittleoffice`, one file and no dependencies): `link`, `read` (`read --text` for what it says, as Markdown), `file`, `diff`, `lint`, `measure`, `apps`, `templates`.

To learn a shape by example rather than from these pages: `npx tinylittleoffice shapes deck` lists what a deck reads, a line a shape; `npx tinylittleoffice example deck two` prints the smallest document that shows it, its JSON (the kernel's document), and what `lint` and `measure` say of it (with no shape, every one of the app's); `npx tinylittleoffice try deck draft.tlo` (or `-` for stdin) is the loop in one call: the lint, the measures and the JSON of a draft. The API has the same three: `await shapes(app)`, `await example(app, shape)`, `await tryDraft(app, text)`. An agent that can only fetch reads the examples as files: `https://tinylittleoffice.com/examples/<app>.json` (every shape of the app, its text, its plain link and its JSON), and `https://tinylittleoffice.com/llms/<app>.txt`, a page on one app.

The words of a document may be in any language or script, right to left too (the kit sets the direction by the words): write for the reader. A link opens in its reader's browser's language; `link(app, text, { lang: 'ht' })` (or `--lang ht`) makes one that opens in Haitian Creole, or any language the site has (`es`, `pt-br`, `zh-hant`, `he`, `yi`, …), whatever the reader's browser says.

A page of your own can import `https://tinylittleoffice.com/tinyoffice.js` instead: `link({ app, doc, title })` writes the plain link and `embed({ app, doc, title })` the `<iframe>` that shows the document's pages. In the API, `encode`/`decode` are the codec, `parse`/`write` the kernel (the document as a head and blocks, and back), `tlo`/`fromTlo` a `.tlo` file's text, `file(app, text, ext)` a file of the app's own formats that needs no browser.

## Check it, do not look at it

Before you share a link, lint it: `tinyoffice lint <link or file.tlo>` (or `await lint(app, text)` in the API). It says what a reader's eye would have seen, a line a finding, `app · slide or block · the finding · what to do`, and exits 1 when there is one; `--json` gives `{findings: [{app, at, block, kind, words, fix}]}`. The findings:

- `edge-end`: a connection names a thing that is not in the list (a tree draws it not at all).
- `edge-unused`: a connection in a kind that draws none.
- `net-colon`: a network's `- Name: description` line, named by the whole line.
- `comma-number`: a comma inside a number in a Venn's or a table's list, cutting it in two.
- `label-long`: a thing's words too long for its box: set at the smallest size, or cut with "…".
- `label-over`: a connection's label lying over another label or a thing's words.
- `fence-bullets`: bullets on a slide that shows a document, not drawn.
- `title-cut`, `title-small`: a headline cut after two lines, or set at its smallest size.
- `body-over`, `body-small`: a slide's words running off its foot, or set at their smallest size.
- `formula-error`: a table's formula that works out to an error (`#CIRC`, `#REF`, `#DIV/0`, `#NAME`, `#VALUE`, `#NUM`, `#ERR`), in any table, a fenced one too: the cell, the formula, the error and the fix. A total over its own column takes in its own cell when the rows are counted from the header: rows count from the first data row, so the eighth row's total of the seven above is `=SUM(B1:B7)`.
- `doc-link`: a link to a Tiny Little Office document in the words, where the document could be inside this one as a fence.
- `length`: a link past 2,000 characters, which some chat apps cut.

A diagram fenced on a slide is linted too, at its slide. `tinyoffice measure <link or file>` (`measure(app, text)`) gives the numbers behind them as JSON: per slide, the headline's and the words' sizes, the lines they wrapped to, what was cut and the bullets a document hides, what it shows (`shows`); per diagram, its things, its connections drawn and dropped, and each label's size, lines and whether it was cut; per table, its formulas and the ones that fail; `short`, whether the link fits in a short link; and for every document `words` and `headings`, what a reader meets. Set your words from these numbers. `read` gives back the text exactly as written, so what you wrote is what the link holds; `read --text` (`text(url)`) gives what it says, as a screen reader is given it on the Display Link (a diagram's things and connections, a calendar's days), to check that it reads. You never need a browser or a screenshot to check a document: the lint and the measures come from the same layout code that draws the pages. If you do open a development copy of the site, short links need its shortener (`npm run tinier:dev`).
