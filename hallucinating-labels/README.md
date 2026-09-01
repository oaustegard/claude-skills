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

Two more measured rules, both in `SKILL.md`. Anchor the prompt on the
vocabulary's **register**, never on novelty — it is the largest single variable
in the pattern, and the source post gets it wrong. A Haiku subagent that obeyed
"never-seen-before" scored 0.100 against a 0.500 no-model control; on a
distinctive vocabulary the same wording cost 30 points and inverted the verdict.
And pass `--union` for long documents, where the written label and the direct
embedding are complementary (0.508 and 0.416 alone, 0.672 interleaved).

For a no-API setup, `gte-small` int8 is 33 MB and snaps the raw query at 0.455 acc@1;
a tiny local LM in place of the writing half makes it worse, not smaller — see `SKILL.md`.

Origin: Doug Turnbull, ["Don't classify. Hallucinate!"](https://softwaredoug.com/blog/2026/08/10/hypothetical-classifications), 2026-08-10.
Arms and artifacts: `oaustegard/experiments/hypothetical-classification`.
