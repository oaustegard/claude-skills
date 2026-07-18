---
name: creating-video
description: "Create video from prompts by overseeing multi-clip AI generation end to end: write a shot list, generate each scene with Google Veo (via the Cloudflare AI Gateway), review the results, and assemble them into a finished cut. Use when the user asks to make/generate a video, a short film, an animatic, or a multi-scene clip from a script or idea; when they mention Veo, text-to-video, or image-to-video; or when acting as the editing/director agent over generated footage. Triggers on 'make a video', 'generate a clip', 'short film', 'video from this script', 'turn this into a video', 'veo', 'text to video', 'storyboard to video'. For transcoding/trimming/merging/GIF/subtitles use processing-video; for reading or summarizing existing video content use parsing-video."
metadata:
  version: 0.1.0
---

# Creating Video

Claude cannot render video itself, but it can direct a generator. This skill drives
a multi-clip pipeline — **script → per-scene Veo generation → review → assembly** —
with Claude as the editing agent overseeing continuity and cut.

Requires `ffmpeg`/`ffprobe` and Cloudflare AI Gateway creds (`/mnt/project/proxy.env`).

## The five stages

1. **Shot list** — break the story into beats, ~5–8 s each, one prompt per shot.
2. **Generate** — `scripts/veo_generate.py`, run detached.
3. **Review** — `parsing-video` on each clip **and** on the assembled cut.
4. **Assemble** — `scripts/assemble.py`, run detached.
5. **Iterate** — re-review, regenerate only the failing scenes.

## Stage 2 — Generation (Veo via Cloudflare AI Gateway)

Auth is CF AI Gateway BYOK: `proxy.env` supplies `CF_ACCOUNT_ID`, `CF_GATEWAY_ID`,
`CF_API_TOKEN`; the Google key lives *inside* the gateway, so both the generate
call and the file download route through it.

**Enumerate models — never hardcode.** Strings change.
```bash
python3 scripts/veo_generate.py --list
# 2026-07-18: veo-3.1-generate-preview / -fast-generate-preview / -lite-generate-preview
```

**Run detached.** Veo takes 1–3 min per clip; `bash_tool` caps at ~50 s. Launch and
adaptive-wait on the `DONE` sentinel:
```bash
# prompts.json = {"1": "...", "2": "...", ...}
set -a; . /mnt/project/proxy.env; set +a
(setsid python3 scripts/veo_generate.py prompts.json --out veo/ \
    --negative "large paper, on-screen text, watermark" &)
# then, in a separate call:
timeout 45 sh -c 'while [ ! -f veo/DONE ]; do sleep 4; done'; cat veo/generate.log
```

**Gotchas (all diagnosed 2026-07-18 — the script already handles them):**
- `personGeneration:"allow_adult"` → HTTP 400. Omit it.
- ~5 concurrent operations max; the 6th returns 429. The script fires in waves and
  refills slots as ops finish.
- The egress proxy 503s on cold start → retry with backoff.
- Output is an 8 s 1280×720 mp4 with native Veo audio.

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

Trims each 8 s clip to its beat, crossfades, drops audio by default, burns the
payoff word, and holds the final frame so the ending lands.
```bash
(setsid python3 scripts/assemble.py veo/scene_1.mp4 ... veo/scene_6.mp4 \
    --out film.mp4 --overlay-last "COMING HOME" --tail-hold 1.3 &)
```
Run detached too — six trims plus a 30 s stitch exceed the bash ceiling on the
single-core container. Diagnosed: abrupt ending → `--tail-hold`.

**Audio: Veo clips carry real generated audio (ambience, foley) — don't drop it
silently.** `assemble.py` mutes by default only because hard-cutting six
independent ambiences is jarring; pass `--keep-audio` to `acrossfade` them into a
continuous bed. Surface the choice to the user rather than deciding for them
(Oskar was surprised audio existed and had been dropped, 2026-07-18).

## Prompt craft — continuity is the hard part

Every failure mode below came from real crits on 2026-07-18. Write against them on
the first pass; they are expensive to fix by regeneration.

- **Lock a character sheet.** One verbatim appearance/wardrobe block, reused in
  every shot with that character. Independent per-shot prompts produced three
  different women and, once, a man's hands where the woman's were required.
- **Lock the setting.** One room/location description across co-located scenes.
- **Name the actor in every shot** ("the same woman's hands") — never leave it to
  the model to infer who is on screen.
- **Prop continuity is the weakest link and is not fully solvable by text.** Name
  the prop's size, color, and attachment point in *every* shot, plus a
  `negativePrompt` against its failure modes. Residual limitation: Veo still drifts
  a prop across independent generations (a leg-scroll migrated between talons and
  tail across shots even with locks). The hard fix is **image-to-video seeding** —
  generate one canonical still of the prop/subject and pass it as the first-frame
  image so the prop is pinned. Reach for it when text locks aren't enough.
- **Spell out scene logic** — physical coherence (open vs closed window), the
  correct order of beats (surprise at the *arrival*, not at the message), and
  *show* the payoff action rather than cutting away from it.
- **Thematic coherence.** Title, on-screen payoff, and story beat should cohere.
  A drifting title/word resolves cleanly when the physical prop *is* the title.
- **On-screen text.** Veo renders words unreliably. Keep "no on-screen text" in the
  prompt and burn the payoff word in assembly (`assemble.py --overlay-last`).

## Scope

- Transcode / trim / merge / GIF / subtitles → **processing-video**.
- Reading, summarizing, or QA of existing video content → **parsing-video** (also
  the review step here).
