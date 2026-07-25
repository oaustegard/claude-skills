# converting-files

Convert a file from one format to another inside the Claude.ai container —
documents, images, audio, video — by routing to the right engine among
`pandoc`, `libreoffice` (headless), ImageMagick, and `ffmpeg`.

The value is the **routing**, not the subprocess call: pandoc mangles a real
`.docx` into PDF (LibreOffice is the tool); pandoc is *better* than LibreOffice
from markup; `mp4 → gif` is an ffmpeg job, not ImageMagick. `scripts/convert.py`
is a dispatcher that picks the engine by format pair.

```bash
# Confirm the route without running anything:
python3 scripts/convert.py --plan in.docx out.pdf

# Convert:
python3 scripts/convert.py in.docx out.pdf      # LibreOffice
python3 scripts/convert.py notes.md notes.docx  # pandoc
python3 scripts/convert.py clip.mp4 clip.gif    # ffmpeg
```

Full routing table, batch usage, engine-flag passthrough, and the gotchas that
cost a re-run (LibreOffice naming, headless single-instance, markup→jira
anchors, IM6 policy) live in **[SKILL.md](./SKILL.md)**. Version history in
**[CHANGELOG.md](./CHANGELOG.md)**.

### Why not VERT (or any web converter)

VERT (vert.sh) is a Svelte/WASM browser app wrapping these same engines for a
human at a tab who wants local privacy — no importable CLI or library. In the
container the native binaries are already present with full filesystem access
and no browser memory ceiling, so they're strictly faster and more capable for
programmatic use. This skill is the in-container equivalent of what VERT does in
a tab.
