# generative-thinking - Changelog


## 0.3.0 — 2026-09-15
- **Tail sift** added to Core discipline: over-generate 5–8 candidates, tag each with the probability the old frame would have produced it, drop those above 0.3. From Verbalized Sampling (Zhang et al., arXiv:2510.01171) — instance and list prompts collapse to the mode; distribution prompts with verbalized probabilities recover it, and the threshold tunes tail depth.
- **Random stimulus** LLM sourcing rewritten. The 0.2.0 claim that an LLM cannot source its own randomness was too strong: String Seed of Thought (Misaki & Akiba, arXiv:2510.21150) shows a written-out long random string, reduced by sum-mod or rolling hash over the whole string, beats injected seeds and RNG tool calls on open-ended diversity. Both measured failure modes recorded (first-character laziness; unwritten derivation). New `references/stimulus-vocabulary.md` — 128 nouns, `hash mod 128`, worked example.
- **Perspective shift → Structured analogy.** "How would [domain] solve this?" is the cross-domain baseline that still mode-collapses in Shen, Druckmann & Zou (arXiv:2605.11258). Replaced with Gentner structure-mapping: extract objects and relations, map by function, search the target domain for a named existing method, transfer back. Fired-if now requires a named method, not a metaphor. Domain menu kept as a starting point.
- Agent-reasoning section names the second fixation mechanism (typicality bias from post-training, independent of context).
- References: Zhang et al. 2025, Misaki & Akiba 2025, Shen et al. 2026, Gentner 1983. Papers surfaced by Stuart Gray.

## 0.2.0 — 2026-07-22
- New move: **Family traversal** — pair-anchored generation. Name the shared family and its parameter, walk past the anchors to limit points, swap the bound object at the supporting constraint, probe the chord (mixtures) last, then sharpen into derivable questions and verify.
- Diagnostic row + quick-reference entry: "two examples, no theory of the space between/beyond them".
- Reference added: Balestriero, Pesenti & LeCun, arXiv:2110.09485 (caution: interior != novelty; mixtures average, limits extrapolate).
- Empirical origin: 2026-07-22 session — frontier framing unified LAC and remax as endpoints, implied and verified the float32 addressing capacity law (cliff at N=4096; llm-as-computer#120).

All notable changes to the `generative-thinking` skill are documented in this file. The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [0.3.0] - 2026-09-16

### Added

- 0.3.0 — tail sift, hashed random stimulus, structured analogy (#797)

## [0.2.0] - 2026-07-23

### Other

- generative-thinking 0.2.0: add Family traversal move

## [0.1.2] - 2026-04-17

### Other

- Add generative-thinking skill v0.1.2 (#550)