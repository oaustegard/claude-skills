# generative-thinking

Break out of a locked problem frame by picking **one disciplined generative move** — reframe, provocation (Po), random stimulus, SCAMPER, inversion, structured analogy, constraint play, or family traversal — and committing to it before evaluating.

The skill is the interrupt for fixation, not a brainstorming workshop. Pick one move matched to the diagnosis, run it, over-generate and tail-sift (write next to each candidate the probability the old frame would have reached it; drop the likely ones), apply the fire test (*could this output have been produced without the move?*), stop.

See [`SKILL.md`](SKILL.md) for the diagnostic table, per-technique recipes with success signals, LLM-specific sourcing notes, and canonical references. [`references/stimulus-vocabulary.md`](references/stimulus-vocabulary.md) is a 128-noun deck for the hashed random stimulus.

## Provenance

- **Lateral thinking, Po, random stimulus** — Edward de Bono, *Lateral Thinking* (1970), *Serious Creativity* (1992)
- **SCAMPER** — Bob Eberle (1971), built on Alex Osborn's *Applied Imagination* (1953)
- **Oblique Strategies** — Brian Eno & Peter Schmidt (1974–2001)
- **Functional fixedness** (the bias this skill counters) — Karl Duncker (1935/1945); candle problem
- **LLM-specific design fixation** — Wadinambiarachchi et al., CHI 2024 ([doi:10.1145/3613904.3642919](https://doi.org/10.1145/3613904.3642919)): AI-generated examples during ideation *increase* fixation and reduce fluency, variety, originality vs. no-support baseline. Motivates the LLM-sourcing section.
- **Family traversal** — Balestriero, Pesenti & LeCun, [arXiv:2110.09485](https://arxiv.org/abs/2110.09485) (interior ≠ novelty; limits extrapolate, mixtures average)
- **Tail sift** (typicality bias, verbalized-probability prompting) — Jiayi Zhang, Simon Yu, Derek Chong, Anthony Sicilia, Michael R. Tomz, Christopher D. Manning & Weiyan Shi, *Verbalized Sampling*, [arXiv:2510.01171](https://arxiv.org/abs/2510.01171)
- **Hashed internal random stimulus** — Kou Misaki & Takuya Akiba (Sakana AI), *String Seed of Thought*, [arXiv:2510.21150](https://arxiv.org/abs/2510.21150)
- **Structured analogy** — Andrew Shen, Shaul Druckmann & James Zou (Stanford), *Unlocking LLM Creativity in Science through Analogical Reasoning*, [arXiv:2605.11258](https://arxiv.org/abs/2605.11258), built on Dedre Gentner's structure-mapping theory (*Cognitive Science*, 1983)

The three 2025–2026 papers were pointed out by [Stuart Gray](https://bsky.app/profile/sgray.bsky.social); 0.3.0 is the result.

## Complements

- **challenging** — evaluates after generation
- **convening-experts** — synthesizes multiple role-based viewpoints
- **tiling-tree** — exhaustive MECE partitioning of a solution space

This skill generates *distance*, not judgment, coverage, or consensus.
