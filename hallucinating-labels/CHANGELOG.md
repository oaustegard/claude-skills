# Changelog — hallucinating-labels

## 0.1.0 — 2026-08-31

Initial. Implements the hallucinate-and-snap pattern from Doug Turnbull's
"Don't classify. Hallucinate!" (softwaredoug.com, 2026-08-10), with three
things measurement added that the post does not carry:

- **The boundary.** Structured output over the full label set scored 0.701 acc@1
  on WANDS against this pattern's 0.564. The post reports the pattern working
  and being cheaper, not the arm it loses to. The skill leads with it.
- **The register correction.** The post's "novel, never-seen-before" prompt is
  safe only with a model too weak to obey it. A Haiku 4.5 subagent obeyed and
  scored 0.100 acc@1 against a 0.500 no-model control; re-anchored on register
  it scored 0.525/0.750. The register wording also beat novelty on Gemini across
  all 468 queries (0.564 vs 0.489), so it is strictly better.
- **The long-item case.** Where item and label do not share a register, writing a
  label scores half the direct embedding (0.200 vs 0.400 on a 1,273-tag memory
  corpus). The union of both beats either (0.496). `--union` exists for that.

`scripts/snap.py` — build/snap CLI, tfidf and minilm backends, `--union`,
`--min-score`. Arms and artifacts in
`oaustegard/experiments/hypothetical-classification`.
