# Targets, properties and generators

## Property kinds

| Kind | Property | Oracle |
|---|---|---|
| Model-based differential | every read after any history equals the model's | dict, list, set; linear scan; full recomputation |
| Path agreement | every API path promising the same answer gives it (batch/single, packed/unpacked, index at full probe/flat scan, GPU/CPU) | the paths, plus one brute-force anchor |
| Round trip | `load(save(x)) == x` for every writer/reader pair, including cross-class | equality on every field |
| Warm equals cold | same answer with caches cold, warm, or warmed by another reader | a fresh object |
| Rejected op is atomic | an operation that raises leaves every observable unchanged | snapshot before the call |
| Batch/chunk invariance | result independent of batch size, chunk boundary, threads, row order | one-batch run |
| Copy/pickle | a copy works after the original is mutated or freed; pickle works in a fresh process | the original |
| Metamorphic | known input transform gives known output transform (scale, permute, negate, constant offset) | untransformed run |
| Partial oracle | cheap check of an expensive answer (reachable, sorted, in range) | the check; pair with a model |
| Guard totality | every documented mismatch raises on every read path, warm and cold | the documented error |
| Equality/hash/order | equal values hash equally across construction histories | generated equal pairs |
| Validator sensitivity | accepts valid, rejects each single-constraint corruption | constructed corruptions |

## Check these first

- Sizes and modes the existing suite never uses (unaligned `d * bits`, odd dimensions, n=0/1).
- Caches keyed on less than their inputs (path but not content; precision ignored).
- Guards that run only on a cold path.
- State committed before validation finishes (a rejected first call that poisons later ones).
- Objects caching raw pointers or handles (pickle, deepcopy).
- Two writers or readers of one format.

## Generators

- Small pools so operations collide; unequal overwrite values.
- Build a needed conjunction (warm × foreign reader × mode) inside one rule.
- Derive dependent inputs with `st.data()`, `flatmap`, `builds`; avoid `assume`/`.filter` that rejects most draws.
- Draw enumerated domains from the registry: `st.sampled_from(sorted(REGISTRY))`.
- Edge values as their own strategy, mixed in with `st.one_of`.
- Generate delayed reads as well as frequent ones; reads populate caches.
- `event()` every class a property relies on; gate it with `scripts/hypothesis_stats.py`.

## Tolerances

- Exact equality where docs promise "byte-identical" or "same bits".
- Path against path at exact equality; float64 model only within a tolerance scaled to magnitude.
