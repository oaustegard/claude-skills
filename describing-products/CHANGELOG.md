# Changelog

## 0.1.0 (2026-10-14)

Imported from Steve Ruiz's `product-description` gist
(steveruizok/83ae5c53f2784ebf8f5fe0a3fb94480f @ f9435a3) and revised.

- Renamed to the repo's gerund convention; flat gist layout split into
  `references/` and `scripts/`. `install.sh` and the gist README dropped.
- `check_links.py` (was `check-links.py`): links inside inline code no longer
  report as broken; `_` in headings and accented letters now slug the way
  GitHub does (both produced false "missing anchor" reports); reference-style
  definitions `[label]: path` are now checked; `<a id/name>` anchors count.
- New `check_structure.py`: the mechanical half of the Phase 4 consistency pass
  (coverage table vs. disk, section order, footer, identical modifier,
  interrupt and cross-cutting rows, empty cells, mixed source commits), which the
  gist left to reading.
- Phase 3 drafters no longer edit `glossary.md`; they propose terms and the
  orchestrator merges once. Parallel writes to one shared file lose terms.
- Interrupt families reconciled: `product-kinds.md` said five, the templates
  used seven rows. Now seven everywhere, in the cancel table's order.
- Writing rules de-duplicated: they live in `goal-template.md`; SKILL.md keeps
  the most-broken five.
- Phase 0 reconnaissance points at `tree-sitting` / `exploring-codebases`;
  related-skill note on `featuring`.
