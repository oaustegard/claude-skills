# hallucinating-labels

Assign items to a closed label vocabulary too large to put in a prompt. A cheap
model writes the label it thinks the vocabulary would use; an embedder snaps that
writing onto the nearest legal value. The schema is never sent to the model, and
the output is always in-vocabulary.

See `SKILL.md` for the full reference, the measured boundary, and the prompt.

## Quick start

```bash
python3 scripts/snap.py build --vocab categories.txt --out .snap-index.pkl
# write labels yourself, 40 per call, using the register prompt in SKILL.md
python3 scripts/snap.py snap --index .snap-index.pkl --labels written.txt --k 3
```

`--backend minilm` needs `sentence-transformers`; the default `tfidf` needs only
`scikit-learn`.

## Read the boundary before adopting it

When the whole vocabulary fits in a prompt, ship it and ask for a constrained
choice instead — that scored 0.701 acc@1 on WANDS against this pattern's 0.564.
This pattern is for the case where the tokens are the problem, and there it beats
every model-free baseline.

Two more measured rules, both in `SKILL.md`: anchor the prompt on the
vocabulary's **register**, never on novelty (a Haiku subagent that obeyed
"never-seen-before" scored 0.100 against a 0.500 no-model control), and use
`--union` when items are long documents rather than short phrases.

Origin: Doug Turnbull, ["Don't classify. Hallucinate!"](https://softwaredoug.com/blog/2026/08/10/hypothetical-classifications), 2026-08-10.
Arms and artifacts: `oaustegard/experiments/hypothetical-classification`.
