---
name: creating-video
description: "Create video from prompts by overseeing multi-clip AI generation end to end: write a shot list, generate each scene with Gemini Omni Flash (via the Cloudflare AI Gateway), review the results, and assemble them into a finished cut. Use when the user asks to make/generate a video, a short film, an animatic, or a multi-scene clip from a script or idea; when they mention Omni, Veo, text-to-video, or image-to-video; or when acting as the editing/director agent over generated footage. Triggers on 'make a video', 'generate a clip', 'short film', 'video from this script', 'turn this into a video', 'omni', 'veo', 'text to video', 'storyboard to video'. For transcoding/trimming/merging/GIF/subtitles use processing-video; for reading or summarizing existing video content use parsing-video."
metadata:
  version: 0.2.0
---

# Creating Video

Claude cannot render video itself, but it can direct a generator. This skill drives
a multi-clip pipeline — **script → per-scene generation → review → assembly** —
with Claude as the editing agent overseeing continuity and cut.

Requires `ffmpeg`/`ffprobe` and Cloudflare AI Gateway creds (`/mnt/project/proxy.env`).

**Default model: Gemini Omni Flash** (`gemini-omni-flash-preview`, Interactions
API) — Google's own guidance as of 2026-07. It beats Veo on character
consistency, reference-image control, text rendering, and conversational
editing, and generates faster (~30–90 s/clip vs 1–3 min). Fall back to **Veo
3.1** (`scripts/veo_generate.py`, kept intact) only for scene extension,
first+last-frame interpolation, or legacy pipelines — Omni supports neither.

## The five stages

1. **Shot list** — break the story into beats, up to 10 s each, one prompt per shot.
2. **Generate** — `scripts/omni_generate.py`, run detached.
3. **Review** — `parsing-video` on each clip **and** on the assembled cut.
4. **Assemble** — `scripts/assemble.py`, run detached.
5. **Iterate** — re-review, then **edit** failing scenes conversationally
   (cheaper and more stable than regenerating from scratch).

## Stage 2 — Generation (Omni via Cloudflare AI Gateway)

Auth is CF AI Gateway BYOK: `proxy.env` supplies `CF_ACCOUNT_ID`, `CF_GATEWAY_ID`,
`CF_API_TOKEN`; the Google key lives *inside* the gateway. Both the interactions
call and the `files/{id}:download` retrieval route through it (verified 2026-07-20).

**Run detached.** The Interactions API is *synchronous* — the HTTP call holds
open for the whole generation (~30–90 s/clip). `bash_tool` caps at ~50 s. Launch
and adaptive-wait on the `DONE` sentinel:
```bash
# prompts.json = {"1": "...", "2": {"text": "...", "images": ["ref0.png"]}, ...}
set -a; . /mnt/project/proxy.env; set +a
(setsid python3 scripts/omni_generate.py prompts.json --out omni/ \
    --negative "on-screen watermark" &)
# then, in a separate call:
timeout 45 sh -c 'while [ ! -f omni/DONE ]; do sleep 3; done'; cat omni/generate.log
```

**Gotchas (all verified 2026-07-20 — the script already handles them):**
- **No dry run exists.** Even `input:""` returns 200 and bills a full
  generation (~58k video output tokens). Every request costs money; never
  "validate" with a throwaway call.
- No `negativePrompt` parameter (Veo had one; Omni 400s on unsupported
  params). `--negative` folds into the prompt as "Do not include: X."
- Videos >4MB need `delivery:"uri"` → poll `files/{id}` to ACTIVE → download
  via the gateway. The script always uses uri delivery, inline base64 as
  fallback.
- Output is up to 10 s 1280×720 mp4 with synchronized audio + SynthID
  watermark. No video extension, no first↔last-frame interpolation, no
  multi-video referencing — those are Veo territory.
- The egress proxy 503s on cold start → retry with backoff.

**Omni defaults to multi-shot.** Left alone it invents its own cuts inside a
clip, which fights a shot-list pipeline. Every per-scene prompt should say
"single continuous shot" / "no scene cuts" unless the beat wants internal cuts.

## Stage 3 — Review (use the parsing-video skill)

Contact-sheet **each clip and the assembled cut**. Per-clip sheets miss cross-clip
continuity; the full-cut sheet is where character drift, prop jumps, and logic
breaks show up in one read (Oskar, 2026-07-18: review the whole assembly, not just
scenes). Scan every sheet against the **continuity checklist**:

- **Character** — same face/hair/wardrobe across every shot they appear in.
- **Prop** — same identity, size, color, and attachment point shot to shot.
- **Physical logic** — is the world coherent (a window must be open before a bird
  lands on the sill)?
- **Action completeness** — is the key action actually *shown*, not cut around?

## Stage 4 — Assembly (`scripts/assemble.py`)

Trims each clip to its beat, crossfades, drops audio by default, optionally burns
an overlay word, and holds the final frame so the ending lands.
```bash
(setsid python3 scripts/assemble.py omni/scene_1.mp4 ... omni/scene_6.mp4 \
    --out film.mp4 --tail-hold 1.3 &)
```
Run detached too — six trims plus a 30 s stitch exceed the bash ceiling on the
single-core container. Diagnosed: abrupt ending → `--tail-hold`; jarring cuts
between independently generated ambiences → audio dropped by default
(`--keep-audio` to `acrossfade` instead).

## Stage 5 — Iterate by editing, not regenerating

`results.json` stores each scene's `interaction_id`. A failed detail (wrong
color, unwanted object, lighting) is a one-line conversational edit that
preserves everything else:
```bash
python3 scripts/omni_generate.py --edit <interaction_id> \
    "Make the scarf red. Keep everything else the same." --out omni/scene_3_v2.mp4
```
Simple edit prompts work best; append "Keep everything else the same." Reserve
full regeneration for scenes whose composition or action is wrong. (Editing
requires `store=true`, the script's default.)

## Prompt craft — continuity is the hard part

The failure modes below came from real crits on 2026-07-18 (Veo era). Omni
narrows several of them but the disciplines still pay on the first pass.

- **Pin characters and props with reference images** — the first-class fix for
  the drift that text locks never fully solved under Veo. Generate one
  canonical still per character/prop, put it in the scene's `images` list, and
  bind it in the prompt: `the woman <IMAGE_REF_0> is holding <IMAGE_REF_1>`
  (refs start at 0; `<FIRST_FRAME>` pins a starting frame instead).
- **Still lock a character sheet in text.** One verbatim appearance/wardrobe
  block, reused in every shot with that character — references constrain, text
  directs.
- **Lock the setting.** One room/location description across co-located scenes.
- **Name the actor in every shot** ("the same woman's hands") — never leave it to
  the model to infer who is on screen.
- **Spell out scene logic** — physical coherence, the correct order of beats,
  and *show* the payoff action rather than cutting away from it.
- **Timing is promptable.** `[0-3s] ... [3-6s] ...` timecode syntax or natural
  language ("after 3 seconds, ...") controls beats inside a clip.
- **On-screen text now renders reliably** — spell out exactly what any visible
  text should say (signs, labels, title cards). Burning text in assembly
  (`assemble.py --overlay-last`) remains an option for cross-clip title cards.
- **Audio is promptable.** Describe the track ("no dialogue", "calm background
  music") or Omni invents one per clip — which still won't match across clips;
  assembly drops audio by default for that reason.

## Scope

- Transcode / trim / merge / GIF / subtitles → **processing-video**.
- Reading, summarizing, or QA of existing video content → **parsing-video** (also
  the review step here).
- Scene extension / first+last-frame control → the retained Veo path
  (`scripts/veo_generate.py --list` to enumerate models; strings drift).
