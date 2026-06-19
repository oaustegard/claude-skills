# Changelog

## 0.1.0 (2026-06-19)

Initial release. Dispatcher (`scripts/convert.py`) over the four conversion
engines present in the Claude.ai container: pandoc 3.1.3, LibreOffice 24.2
(headless), ImageMagick 6.9 (`convert`), ffmpeg 6.1.

Routing by (source-family → target-family), with the cross-engine cases that a
pandoc-only or single-engine approach gets wrong:
- Office → PDF routed to LibreOffice (layout fidelity), not pandoc.
- markup → Office/PDF routed to pandoc (cleaner from markup).
- legacy binary Office (.doc/.ppt/.xls) routed to LibreOffice (pandoc can't read).
- gif split by source family: png→gif = ImageMagick, mp4→gif = ffmpeg.

Verified live across all four engines: md↔docx roundtrip, md→html, docx→pdf
(LibreOffice rename path), png→jpg, wav→mp3, plus plan-only routing for
gif/legacy/video pairs.

Motivated by a request to wrap VERT (vert.sh) as a skill. VERT is a browser
WASM app over these same engines — no importable CLI/lib, and strictly weaker
than the container's native binaries for programmatic use. Built the native
equivalent instead.

Known fix during build: initial audio/video routing compared the *family*
string against extension sets (`df in AUDIO` where `df=="audio"`), so wav→mp3
returned NO ROUTE. Corrected to compare families to families and extensions to
extensions.

## [0.1.0] - 2026-06-19

### Other

- Add converting-files skill (native pandoc/LibreOffice/ImageMagick/ffmpeg dispatcher) (#704)
