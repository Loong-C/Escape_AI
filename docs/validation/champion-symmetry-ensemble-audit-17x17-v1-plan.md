# 17×17 champion D4-ensemble validation protocol

The raw lineage-C checkpoint failed all six pre-registered symmetry criteria.
This follow-up freezes a direct inference-time correction before observing its
formal result.

The D4 ensemble canonicalizes every input state over the role-aware symmetry
orbit implemented by the C++ rules core. It evaluates all eight orientations,
maps each policy back to the canonical action space, averages policies and
current-player values, normalizes the legal prior, and then maps the shared
answer back to the caller's coordinates. Equivalent states within one request
are deduplicated by their canonical serialization. Underlying model batches are
capped at 256 states to bound CUDA memory during multi-root PUCT.

`configs/symmetry/champion-symmetry-ensemble-audit-17x17-v1.yaml` reuses the
raw audit's source manifest, checkpoint, sampling seed, 128 states per each of
six phase/turn strata, and four 512-simulation PUCT roots per stratum. The only
experimental change is `evaluator.kind: d4-ensemble`, so raw and corrected
metrics are directly comparable.

Before the result is observed, validation requires:

- neural p95 value absolute error and policy L1 no greater than `1e-6`;
- neural top-1 agreement and mean top-5 overlap at least `0.999`;
- 512-simulation PUCT coordinate-local selected-action agreement and mean top-5 overlap at
  least `0.95`.

The neural thresholds test the mathematical correction. The search thresholds
allow rare finite-precision or exact-tie divergence while requiring the
correction to survive tree search. Passing all criteria routes the research
pipeline to a matched-seed first-player/color diagnostic. Failure requires
repairing evaluator canonicalization or PUCT tie handling first.

The same clean commit also runs
`configs/symmetry/champion-symmetry-audit-17x17-v2.yaml`. It preserves the raw
schema-v1 experiment settings but records visit-policy top-1 agreement and the
actual coordinate-local selected-action agreement separately. This corrected
raw result is the comparison baseline; the original result remains immutable.

The formal atomic result belongs outside Git at
`E:\Escape\_AI\runs\champion-symmetry-ensemble-audit-17x17-v1\result.json`.

## Corrected schema-3 rerun

The first schema-2 comparison established exact neural value, L1, and top-1
equivariance, but exposed two metric/search edge cases. Top-5 overlap divided by
five even when fewer than five legal actions remained, and PUCT resolved tied
visits by local numeric action ID. Result schema 3 normalizes top-k by
`min(5, legal actions)`, assigns equal visit counts equal rank, and uses the
state's canonical D4 action order for PUCT selection ties, root noise, final
temperature-zero selection, and seeded sampling.

The immutable corrected rerun uses
`champion-symmetry-audit-17x17-v3.yaml` and
`champion-symmetry-ensemble-audit-17x17-v2.yaml`. All source, model, sampling,
and search budgets remain unchanged. Their result directories use the matching
run IDs under `E:\Escape\_AI\runs`.
