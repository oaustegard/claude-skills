# Evidence: Haiku swarm against a Sonnet loop at equal spend (2026-11-09)

Reference, not procedure. Source: `oaustegard/experiments` → `haiku-swarm-poc/RESULTS.md`
(48 runs, $102.30 at list prices, three seeds per arm).

## Design

- **Problems**: three of OpenEvolve's example problems with exact scorers: 26 circles in a unit
  square (score = sum of radii / 2.635983, the best known), the Heilbronn triangle for 11
  points, and 11 unit hexagons in the smallest regular hexagon (both scored against
  AlphaEvolve's published construction).
- **Swarm (this skill's defaults)**: K=4 swarms per round, N=8 Haiku 5.5 proposers at effort
  low (45-word ideas, no code), one Haiku writer at effort medium per swarm.
- **Sonnet loop**: stock OpenEvolve 0.4.1 driving Sonnet 5.5 at effort low, medium and high,
  each problem's own config.
- **Budget**: $3 list-price cap or 60 minutes per run. Every call through `claude -p`.

## Dollars to 99% of the reference (three seeds each)

| problem | swarm | best Sonnet effort | Sonnet at effort low |
|---|---|---|---|
| circle packing | $0.013–0.019 | $0.32–0.44 (medium) | $0.36–0.37 |
| hexagon packing | $0.035–0.060 | $0.53–0.58 (high) | $2.39–2.55, one seed never |
| Heilbronn triangle | $0.09–0.50 | $0.77–1.02 (medium) | $0.46–1.17, one seed never |

At $0.25 spent, every swarm seed scored above its paired Sonnet seed on all three problems.
Given its full $3, Sonnet reached the same final scores (on hexagon at effort high, slightly
higher) and did it in 7–42 minutes; the swarms used their 60 minutes at $0.89–1.39.

## Effort

- **Sonnet's effort is problem-dependent.** Circle packing: high, medium and low within noise.
  Heilbronn: only medium reached 1.0 on all three seeds. Hexagon: low never reached 0.999
  (best 0.9825–0.9978) while high reached 0.99999 or more on all three.
- **Writer at effort low** (proposers already low): all three circle seeds reached 0.999 by
  $0.14–0.21, better than the medium writer; on hexagon none reached 0.999 and on Heilbronn one
  seed never reached 0.99. Keep the writer at medium unless the problem is known to be easy.
- **Haiku 5.5's thinking cannot be switched off through the CLI.** Effort low is the floor; the
  proposers thought 0 tokens on 65% of calls (mean 95).

## Proposers versus the writer alone

On one circle-packing seed, the writer alone (N=0) reached 0.999 at $0.26 against $0.20 with
eight proposers per swarm. SwarmEvolve's own ablation (Appendix A.2) found its agent counts end
the hour at similar scores. One seed on the easiest problem: run an N=0 control on a new
problem before assuming the proposers earn their share (about 60% of the spend).

## Cost structure

- A swarm program costs about a cent: 32 proposer calls and one writer call.
- Programs per dollar: swarm 88–156, Sonnet loop 4–20.
- `claude -p` adds about 1,370 tokens to every call. Without them the swarm arms would have
  cost 12.5% less and the Sonnet arms 3.7% less.

## Scorer loophole

OpenEvolve's hexagon evaluator tests containment with an absolute 1e-6 tolerance on an
unnormalised cross product. A swarm program whose own side estimate had a bug returned an outer
side of 1e-9 and scored 3.9e9. The run's refine swarms then spent their last 40 minutes on that
program. An area bound (11 unit hexagons need an outer side of at least the square root of 11)
rejects it; that is what `score_max` is for.
