---
name: reading-business-cards
description: "Preprocesses photographed sheets of many business cards — slicing each into overlapping high-resolution tiles and de-glaring them with container tooling (OpenCV/ImageMagick) — then reads every card via cheap parallel temperature-0 API calls (Haiku or Sonnet) using a distilled extraction prompt, and writes deduped contact fields to a CSV. Use when a user has photos or scans holding multiple business cards per image, mentions glare or unreadable cards, batch card transcription, contact extraction, or wants to read many cards without an expensive in-conversation pass. Triggers on 'business cards', 'card scan', 'extract contacts', 'read these cards', 'card glare', 'too many cards per photo'."
metadata:
  version: 2.1.0
---

# Reading Business Cards

Turn photos or scans that pack many business cards into one image into a clean
contact list. The job is two stages, in order: **preprocess with the script,
then read the tiles it produces.** Read the tiles, not the original sheet — the
original is too low-resolution per card once the model downscales it.

## Why preprocess first

The model downscales any input image to ~1568px on the long edge before it sees
it. A phone photo of 50-60 cards is often 4000-6000px; downscaled to one image,
each card lands ~150px wide — unreadable, which forces you onto a more expensive
model. The script cuts the sheet into overlapping **tiles**, each near the
downscale cap (~1300px), so every card in a tile keeps 500px+ of real
resolution. That resolution recovery is what lets a cheaper model (Sonnet) read
cards that only the expensive one (Opus) could read before — and it lets Opus
read cards from far fewer tiles. **The grid is sized to the reader model** (see
Stage 1): pass `--model` and the script tiles aggressively for Haiku, moderately
for Sonnet, and least for Opus, because a stronger reader has a lower resolution
floor. The floor is set by the *pixels*, not the model's intelligence: at
~220px/card (a whole dense sheet) even Opus reads only company and some names,
not phone/email — so even Opus needs a few tiles for fine print on dense sheets.

De-glaring (illumination flattening + local contrast) is applied to each tile.
It corrects uneven lighting and the haze off glossy cards and plastic binder
sleeves. It cannot recover text where glare has clipped pixels to pure white —
that data is gone (see Limits).

## Stage 1 — Tile the sheets

The person only provides the images and the goal ("read these cards"). Derive
every parameter yourself; do not ask them to choose grid sizes or flags.

Real sheets are messy: cards scattered at angles, packed in binder sleeves,
overlapping, piled. Detecting individual card boundaries fails on all of these.
**Tiling ignores card boundaries** — it slices the sheet into a grid of
overlapping rectangles. Each tile holds a few cards at high resolution; the
overlap means a card split by one tile's edge is whole in its neighbour.

Run it sized to whichever model will read the tiles — pass `--model` and the
script measures each sheet's native card size, then derives the coarsest grid
whose cards still clear that model's OCR floor:

```bash
python3 scripts/prep_cards.py /mnt/user-data/uploads --out /home/claude/cards_work --model opus
```

`--model opus|sonnet|haiku` (or a full id like `claude-opus-4-8`) sets the floor:
Opus tiles least, Haiku most. Default is `sonnet` (the safe middle). On a dense
~660px-card sheet this yields roughly 6 tiles/sheet for Opus, 9-12 for Sonnet,
12-20 for Haiku. If the reader is the in-conversation model (the no-key path,
below), set `--model` to match whatever you're running. Overrides: `--target-px`
forces an explicit tile size, `--card-px` overrides the auto card-size estimate,
`--floor-px` overrides the per-model floor.

It prints the grid it chose per image (e.g.
`auto 3x2 from 4284x5712 [model=opus floor=350 card~668px -> target 2993]`) and
writes tiles to `cards_work/tiles/` (`<sheet>__r{R}_c{C}.png`) plus a
`manifest.json`. If a sheet's cards are smaller than the model's floor even at
native resolution, it warns — that sheet needs a re-shoot, not a finer grid.

Then **verify and self-adjust by inspection** — this is your judgment, not the
person's:
- View one representative tile. If the cards in it are crisp and fully legible,
  proceed to read them all.
- If cards look small or dense (text fuzzy), rerun with a smaller cap for a finer
  grid: `--target-px 1100`.
- If cards are clipped in half at tile edges, rerun with more overlap:
  `--overlap 0.2`.
- If the cards are matte and text-only and a light haze remains, rerun with
  `--binarize`. Skip binarize for color or logo-heavy cards — it flattens them.

De-glaring (illumination flatten + local contrast) is on by default and is
non-destructive. Decide on the extra flags by looking at a tile, then commit to
the full read.

## Stage 2 — Read and extract

There are two ways to read the tiles. **In-session reading is the universal path
and works for everyone, key or no key:** view the tiles with the `view` tool and
transcribe them in this conversation, applying the rules in
`prompts/haiku_extract.md` (one row per fully-visible card, skip edge-clipped
cards that are whole in a neighbour, never invent, `confidence` low when unsure).
The coarse model-sized grid is what makes this tractable — a dozen tiles per
sheet, not eighty — and the conversation model reading them is exactly the model
that reads cards well. Cost here is the subscription's usage allowance, not
per-token dollars; the coarser the grid (Opus), the fewer reads.

**The API runner is an optional optimization, only when an API key is present**
(`API_KEY` in env / `/mnt/project/claude.env`). It sends each tile to a model in
a separate parallel temperature-0 call using the distilled prompt, dedupes, and
writes the CSV — reading outside the chat context, so it is cheaper per token and
runs many tiles at once. Without a key it cannot run; use the in-session path.
The runner bills the API account per token; it buys parallelism and a cheaper
meter, never accuracy.

### Running the API runner (keyed path)

**Validate the model on a sample before the full run.** Haiku is ~6x cheaper but
its OCR is weaker; on phone photos of loose or angled cards it confidently
misreads names and marks the errors `high` confidence. (Gemini's free tier was
tested 2026-06-15 and read these poorly — do not reach for it here.) Tested
guidance:

1. Sample run with Haiku:
   ```bash
   python3 scripts/extract_cards.py --work /home/claude/cards_work \
       --out /home/claude/sample.csv --limit 8
   ```
2. View 2 of the tiles it read and compare against `sample.csv`. Check: are
   names and companies correct? Is `confidence` honest (clear cards `high`,
   blurry/angled `low`)?
3. Decide:
   - Clean, high-resolution, upright cards (e.g. a flatbed scan), Haiku reads
     them correctly → keep Haiku for the full run.
   - Errors, or `high` confidence on wrong text → switch to Sonnet:
     `--model claude-sonnet-4-6`. Sonnet via this same script is far cheaper
     than reading tiles in-conversation and is accurate on messy phone photos.
4. Full run with the chosen model and your real output path:
   ```bash
   python3 scripts/extract_cards.py --work /home/claude/cards_work \
       --out /mnt/user-data/outputs/cards.csv [--model claude-sonnet-4-6]
   ```

The script prints raw vs unique counts and the low-confidence / parse-error
tally. The CSV columns are `sheet, tile, name, title, company, phone, email,
website, address, confidence`.

## Stage 3 — Triage the failures

From the finished CSV, take every row with `confidence = low` (and any
`parse-error`). Re-run just those — extract the relevant tiles into a small work
dir and run `extract_cards.py` on them with `--model claude-sonnet-4-6` (or Opus
in-chat for the worst). Cards still wrong after that are too small, angled, or
glare-clipped in the source — flag them for a re-shoot rather than re-running.

Note Haiku's confidence is not reliable enough to drive this triage on its own;
if you used Haiku, sanity-check `high` rows too, or just use Sonnet for the run.

## Reading tiles by hand (fallback)

If the API runner is unavailable (no key), you can read tiles yourself with the
`view` tool, applying the rules baked into `prompts/haiku_extract.md`: one row
per fully-visible card, skip edge-clipped cards, never invent, `confidence` low
when unsure. Work in batches and write the CSV incrementally. This burns far more
tokens than the runner — prefer the runner.

## Other layouts

Two narrower modes exist for clean inputs. Choose them yourself only when a
spot-check shows the cards are cleanly separated and unrotated; never the
default:
- `--rows R --cols C` (grid slice): exact, for cards in a perfect
  non-overlapping grid. Builds numbered montages instead of tiles.
- `--detect` (contour auto-detect): crops individual well-separated cards.
  Best-effort only — it merges touching cards and misses rotated/glare-covered
  ones. On real scattered or binder sheets it under-detects badly; stay on the
  default tiling.

In both, the read units are numbered montages (`montage_NNN.png`) whose cells
carry a red `#index` matching the manifest; extract one row per `#index`.

## Limits

- Tiling recovers resolution and corrects lighting; it does not invent pixels
  that glare clipped to white. Severe specular blowout is unrecoverable — those
  cards need a re-shoot under diffuse light.
- Cards photographed at an extreme angle or far smaller than their neighbours
  may still read `low`; a finer tile grid helps, a re-shoot helps more.
- `--binarize` trades color/logo fidelity for text crispness. Use it only for
  text-only cards, not as a default.
- Model accuracy is the real bottleneck, not the pipeline. On tested phone
  photos of loose/angled cards, Haiku confidently misread names and companies
  (e.g. "Clint Emerson/CableQuest" → "Cliff Emerson/Quest") and marked errors
  `high` confidence; its inconsistent misreadings also defeated cross-tile
  dedup. Sonnet on the identical tiles read them correctly with calibrated
  confidence. Reserve Haiku for clean, high-resolution, upright scans, and
  validate it on a sample (Stage 2) before trusting a full run.
