---
name: drawing-video
description: "Turn a short video into a narrated comic strip. Use when the user uploads a video (.mov/.mp4/etc.) and asks to make a comic from it, narrate it, draw it, Attenborough it, storyboard the clip, or otherwise wants a stills-plus-narration comic strip derived from footage. Covers probing and extracting frames, GROUNDING the actual storyline (native Gemini video parse or frame reading), composing narration in a chosen voice, generating comic panels with Gemini image models anchored to the real stills, QA-ing the panels, and compositing a titled strip. Do NOT use for plain video transcoding or trimming (that is processing-video) or for original illustration from a text prompt (that is invoking-gemini)."
metadata:
  version: 1.0.0
---

# drawing-video

Footage in, narrated comic strip out. Five stages: **probe → ground → narrate → draw → QA/compose**. The hard part is not the drawing; it is not lying about what the footage shows. One stage is a gate.

Requires: `processing-video` (ffmpeg, present), `invoking-gemini` (image + video models), `proxy.env` (CF gateway creds — auto-read by the gemini client).

---

## Stage 0 — Probe & extract frames

```bash
ffprobe -v quiet -show_entries format=duration -of csv=p=0 in.mov
mkdir -p frames
ffmpeg -v error -i in.mov -vf "fps=1,scale=640:-1" frames/f_%03d.png   # 1/sec, downscaled
```

Keep full-resolution stills too — you will feed them to the image model as reference.
For a subject hidden in clutter, pull a few full-res frames at specific timestamps:
`ffmpeg -v error -ss 11 -i in.mov -frames:v 1 hr.png`.

---

## Stage 1 — GROUND THE STORYLINE (the gate)

**Never narrate a scene whose subjects and action you have not confirmed from the footage.** Diagnosed failure 2026-07-18: built an entire "indoor cyclist in a garage" storyline off thumbnail-sized frames of a video that was actually a leashed dog watching a deer — no bicycle in any frame, the leash visible in four. Then fed the fiction to the image model, which dutifully drew it. A wrong storyline launders a hallucination into finished art. The absence of a clear read is not license to invent a vivid one.

Two ways to ground. **Prefer Mode B** — it is the more reliable and reads the whole clip, not sampled stills.

### Mode B (recommended): native video understanding via gemini-3.5-flash

`gemini-3.5-flash` parses video directly. Compress first, send as inline data.

```bash
ffmpeg -v error -i in.mov -vf "scale=480:-2,fps=8" -c:v libx264 -crf 30 -preset veryfast -an small.mp4
```

```python
import sys, base64; sys.path.append('/mnt/skills/user/invoking-gemini/scripts')
from gemini_client import get_cf_credentials, _cf_request
from pathlib import Path
c = get_cf_credentials()
b = base64.b64encode(Path("small.mp4").read_bytes()).decode()
prompt = ("Watch this video and describe the actual storyline in 3-4 sentences: which "
          "subjects appear, what happens, the arc. Be literal — only what is visibly present.")
contents = [{"parts": [{"inlineData": {"mimeType": "video/mp4", "data": b}}, {"text": prompt}]}]
resp = _cf_request("gemini-3.5-flash", contents,
                   {"temperature": 0.3, "thinkingConfig": {"thinkingLevel": "minimal"},
                    "maxOutputTokens": 600}, c)
print("".join(p.get("text","") for p in resp["candidates"][0]["content"]["parts"]))
```

Inline works for small files (verified: a 22s 4K clip compressed to 2.3 MB). For long clips, sample frames (below) or use the File API. `gemini-2.5-flash-image` is not a parser — this is `gemini-3.5-flash` (text/multimodal).

### Mode A: read the frames yourself

Build a contact sheet (`PIL` grid of `frames/*.png`), then **view enough full-resolution frames to name every subject and the action out loud** before writing a word of narration. If you cannot tell what a shape is, extract a higher-res crop at that timestamp and look again. Do not proceed on a guess.

Either way, end Stage 1 with one plain paragraph: subjects, setting, arc. If the user has already told you the storyline, that paragraph is authority — use it verbatim and skip re-derivation.

---

## Stage 2 — Narrate

Write the caption text: one short caption per panel (4 panels is the default; 3–6 is the range). Match the requested voice (David Attenborough hushed-drama is the common ask; dial the stakes above what the mundane footage deserves). Captions must be short enough to render legibly in a box — one or two sentences.

Keep a **character/setting bible** in one line: the exact look of each recurring subject (breed/colour, leash colour, the woods, the light). You will paste it into every panel prompt so the panels stay consistent.

---

## Stage 3 — Draw the panels

Model: **`gemini-3-pro-image`** (GA; was `gemini-3-pro-image-preview`). There is **no Gemini 3.5 *image* model** — 3.5 is text-only; the current image line is `gemini-3-pro-image` and `gemini-3.1-flash-image`. Do not use `gemini-2.5-flash-image`.

Four rules, each from a diagnosed defect on 2026-07-18:

1. **Anchor every panel to real stills.** Pass TWO images per panel: a single shared *anchor* still (canonical setting + subject) and the panel's own still. Instruct: "First reference = canonical setting+subject; second = this panel's framing; redraw as a comic panel." This is what keeps the drawn scene faithful instead of inventing.
2. **State continuity explicitly.** "All N panels are ONE comic: identical setting, identical <subject> design (<character bible>)." Without it the woods and the animal drift panel to panel.
3. **Constrain creatures with negatives.** The image model turned an adult doe into a spotted fawn. Say "adult doe, uniform tan, NO white spots, NOT a fawn" — spell out what it is *not*.
4. **Lock the caption box.** "Place ONE caption box at the top containing EXACTLY this text and NOTHING else — no extra words, no stray letters, no style notes: '<caption>'. Do not write any other text anywhere." Stray style words leaked into a caption box until this was added.

Run panels detached and adaptive-wait — `bash_tool` times out at ~50s and image-pro calls are slow. Launch all panels in parallel threads in one detached script writing a `DONE` sentinel; poll with `timeout 45 sh -c 'while [ ! -f DONE ]; do sleep 3; done'`. Build the request with `_cf_request(model, contents, {"temperature":0.65,"responseModalities":["IMAGE","TEXT"]}, creds)`; extract the image from the part whose key is `inlineData`/`inline_data`.

---

## Stage 4 — QA, then compose

**QA before shipping — do not present unseen panels.** If the local image viewer is available, look at every panel. If it is not (it went dark mid-session on 2026-07-18), QA through Gemini vision instead:

```python
from gemini_client import invoke_gemini
invoke_gemini(prompt=("QA this comic panel. JSON only: setting, subject, deer, "
   "deer_spotted_fawn (true only if white baby spots), caption (verbatim), palette."),
   model="flash", image_path="panel_1.png", max_output_tokens=500, thinking_level="minimal")
```

Check per panel: subjects match the grounded storyline, setting/subject consistent across panels, captions verbatim with no stray text, creatures correct (adult vs fawn). Regenerate only the panels that fail — single-panel regen is cheap.

**Compose** with PIL. Strip any baked border first — image-model panels arrive with inconsistent baked frames (one dark, others white), which reads as a mismatched-border defect. Crop a uniform ~10px inset off every panel, then draw one identical border on all. Add a title band. Save to `/mnt/user-data/outputs/`, then `present_files`.

---

## Pitfall summary (all diagnosed 2026-07-18, one session)

- Confabulated the storyline from thumbnails → **Stage 1 gate; prefer Mode B**.
- Wrong prompt made the image model draw the fiction → **anchor to real stills**.
- Woods/subject drifted between panels → **shared anchor + explicit continuity**.
- Doe rendered as a spotted fawn → **negative constraints on creatures**.
- Style words leaked into a caption box → **lock the caption text**.
- Panel-1 border differed → **strip baked borders, apply one uniform frame**.
- Guessed "Gemini 3.5 image" → **no such model; use `gemini-3-pro-image`, bin 2.5-flash-image**.
- Local image viewer unavailable → **QA via Gemini vision, never ship unseen**.
