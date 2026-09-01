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
- **The long-item case.** On a 1,273-tag memory corpus of 1,500-character
  documents, the written labels and the direct embedding are complementary:
  0.508 and 0.416 alone, 0.672 interleaved. `--union` exists for that. Long items
  also amplify the register error — under the novelty prompt the same corpus
  reads 0.208, half the control, which is how a prompt bug can look like a
  boundary on the pattern itself.

`scripts/snap.py` — build/snap CLI, tfidf and minilm backends, `--union`,
`--min-score`. Arms and artifacts in
`oaustegard/experiments/hypothetical-classification`.

Also carries the no-API story: `gte-small` int8 (33 MB) snaps the raw query at 0.455
acc@1 against MiniLM-L6's 0.417, and neither Pleias `Monad` (57M) nor `Baguettotron`
(321M) earns a place in the pipeline — 0.425/0.400 as writers and 0.325/0.350 as
rerankers, against a 0.500 no-model control. In a browser, ship the encoder alone.

## [0.1.0] - 2026-09-01

### Other

- Add hallucinating-labels skill (#782)
