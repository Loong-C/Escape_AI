# 17×17 champion D4-ensemble validation result

## Outcome

The D4 ensemble passed all six pre-registered symmetry gates. Across the full
frozen sample, its neural policy and value were exactly equivariant at the
recorded precision, and its 512-simulation PUCT searches produced identical
mapped visit policies, top-five sets, ranks, and selected actions. The remaining
root-value discrepancy was at float32 rounding scale.

This closes the checkpoint orientation confound at inference time and routes
the research pipeline to the matched-seed first-player/color diagnostic. It
does not yet establish that the ensemble is stronger than the raw agent; that
requires direct game evaluation.

## Protocol and provenance

- audit Git commit: `754e46bd21b0d6f3a3da22b49da6157a53760c89`
- raw configuration:
  `configs/symmetry/champion-symmetry-audit-17x17-v3.yaml`
- raw configuration SHA-256:
  `59e0df7e90003966a47b953177f15b3d2402cbcf4936f33900eb8b18a7d00d99`
- raw result:
  `E:\Escape\_AI\runs\champion-symmetry-audit-17x17-v3\result.json`
- raw result SHA-256:
  `14ab333c702a7697ce345a2cb8b6c281f35b650da255e73e28f6c9c7a9248752`
- ensemble configuration:
  `configs/symmetry/champion-symmetry-ensemble-audit-17x17-v2.yaml`
- ensemble configuration SHA-256:
  `a2a98ec856f1093b206ba1017edb1174573392fced8f3ed1cd817a3c4abf6fec`
- ensemble result:
  `E:\Escape\_AI\runs\champion-symmetry-ensemble-audit-17x17-v2\result.json`
- ensemble result SHA-256:
  `00a509dbcd6dea6226e9b239e588d11bbe997ff4eebda3c5c7e1fb918b505ea1`
- seed: `20260914`
- checkpoint SHA-256:
  `0257bbee5f97e0c163ecf64eb50160fd8f8b6189b6ac042fd52dced3b0449bf3`
- source-generation Git commit:
  `6b7a08af2bbb678c71e7c644a57285a56a9e5b82`
- source manifest SHA-256:
  `07f4351b3718becaaa2a693b4947ec91ea00d82ccec6e6d309db3254ce4d74bc`
- runtime: raw 28.24 seconds; ensemble 61.84 seconds
- hardware: NVIDIA GeForce RTX 4060 Ti, PyTorch 2.11.0+cu128,
  CUDA 12.8, Windows 11, 28 logical CPUs

Both arms used the identical 768 distinct source states: 128 from every
opening/middlegame/late-game by White/Black-to-move stratum. This produced
5,376 non-identity neural comparisons. Both arms also searched the same four
positions per stratum in all eight orientations using 512 PUCT simulations,
16 parallel leaves, no root noise, and temperature zero.

## Direct comparison

| Metric | Raw checkpoint | D4 ensemble |
| --- | ---: | ---: |
| neural p95 value absolute error | 1.889 | 0 |
| neural p95 policy L1 | 1.385 | 0 |
| neural top-1 agreement | 12.00% | 100% |
| neural mean top-5 overlap | 22.70% | 100% |
| PUCT selected-action agreement | 5.36% | 100% |
| PUCT visit-policy top-1 agreement | 7.74% | 100% |
| PUCT mean top-5 overlap | 14.52% | 100% |
| PUCT mean visit-policy L1 | 1.354 | 0 |
| PUCT p95 root-value absolute error | 1.588 | `5.96e-8` |
| mapped rank of source-selected action | 16.49 | 1.00 |
| source rank of mapped transformed selection | 17.75 | 1.00 |

The ensemble passed neural error limits of `1e-6`, neural top-k limits of
99.9%, and search selected-action/top-five limits of 95%. Its maximum observed
root-value error was `1.19e-7`.

## What changed

For every requested state, the evaluator:

1. selects the lexicographically canonical serialized state in its role-aware
   D4 orbit;
2. evaluates all eight orbit members, capped at 256 underlying model inputs per
   CUDA batch;
3. maps their policies into the canonical action coordinates and averages both
   policy and current-player value;
4. maps the shared result back to the caller's coordinates.

Equivalent states in one evaluator call share a single canonical orbit, so the
eight orientations used by the audit do not cause 64 redundant checkpoint
evaluations. PUCT now resolves exact ties, applies root noise, and enumerates
seeded sampling weights in canonical action order. This was necessary because a
local numeric action ID is not preserved by rotation or reflection.

## Interpretation

The experiment separates two claims that were previously entangled:

- the raw checkpoint remains strongly coordinate-sensitive;
- the same learned checkpoint can be made exactly orientation-consistent at
  inference time without retraining or changing the rules.

Therefore the existing checkpoint and generated games remain reusable. The
ensemble is now the appropriate evaluator for experiments intended to measure
properties of Escape rather than artifacts of one coordinate frame. The raw
agent remains a useful ablation and a record of the deployed training policy.

The next experiment must determine whether averaging eight inconsistent views
improves, preserves, or weakens playing strength and whether White's earlier
68.4% score persists once orientation bias is removed. It will use paired seeds
and exchange which evaluator occupies each fixed color role, separating
evaluator strength from White/Black outcome rates before broader strategy
diversity analysis.
