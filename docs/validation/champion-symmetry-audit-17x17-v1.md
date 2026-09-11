# 17×17 champion checkpoint symmetry-audit result

## Outcome

The lineage-C champion has **material orientation sensitivity**. All six
pre-registered low-error criteria failed, so the next milestone is a D4
symmetry-ensemble evaluator before the planned Black-first matched-seed
diagnostic.

The deterministic rules layer passed legal-action and transition equivariance
for role-aware D4 transforms. The observed disagreement therefore belongs to
the learned policy/value function and its amplification by finite-budget PUCT,
not to a failure to exchange White and Black when a transform swaps the goal
axes.

## Protocol and provenance

- audit Git commit: `12ee9a609667d2ec324d55136ae9ada6357efa34`
- configuration:
  `configs/symmetry/champion-symmetry-audit-17x17-v1.yaml`
- configuration SHA-256:
  `78e0d0a5b5e04db528989a47745dd64be3acb3e443cced655f5fbcf2286150ca`
- seed: `20260914`
- checkpoint SHA-256:
  `0257bbee5f97e0c163ecf64eb50160fd8f8b6189b6ac042fd52dced3b0449bf3`
- source-generation Git commit:
  `6b7a08af2bbb678c71e7c644a57285a56a9e5b82`
- source manifest SHA-256:
  `07f4351b3718becaaa2a693b4947ec91ea00d82ccec6e6d309db3254ce4d74bc`
- result:
  `E:\Escape\_AI\runs\champion-symmetry-audit-17x17-v1\result.json`
- result SHA-256:
  `c4a6f511825be9f132c7f2cdf2c4de4fab9adfa29067c7aefe8b1a65abc524e4`
- runtime: 22.50 seconds
- hardware: NVIDIA GeForce RTX 4060 Ti, PyTorch 2.11.0+cu128,
  CUDA 12.8, Windows 11, 28 logical CPUs

The audit sampled 128 distinct states from each phase/turn stratum, for 768
source states and 6,144 neural evaluations. Each source orientation was
compared with its seven non-identity equivalents, producing 5,376 neural
comparisons. Four states per stratum were additionally searched in all eight
orientations with 512 simulations and 16 parallel leaves, producing 168
non-identity PUCT comparisons across 24 roots.

## Pre-registered decision

| Criterion | Required | Observed | Pass |
| --- | ---: | ---: | :---: |
| neural p95 value absolute error | <= 0.05 | 1.889 | no |
| neural p95 policy L1 | <= 0.25 | 1.385 | no |
| neural top-1 agreement | >= 80% | 12.00% | no |
| neural mean top-5 overlap | >= 90% | 22.59% | no |
| PUCT selected-action agreement | >= 60% | 8.33% | no |
| PUCT mean top-5 overlap | >= 75% | 14.52% | no |

The result is not a marginal threshold miss. Policy L1 has range `[0, 2]`, and
the observed neural and search p95 values were 1.385 and 1.902. Neural value
predictions can differ by at most 2; their observed p95 absolute difference was
1.889 and the maximum was 1.999.

## Where the sensitivity appears

| Slice | Neural value MAE | Neural policy L1 | Neural top-1 | Neural top-5 |
| --- | ---: | ---: | ---: | ---: |
| axis-preserving transforms | 0.639 | 0.784 | 12.93% | 23.65% |
| axis-swapping plus role swap | 0.638 | 0.798 | 11.30% | 21.80% |
| opening | 0.576 | 0.668 | 21.48% | 34.31% |
| middlegame | 0.589 | 0.856 | 10.21% | 21.57% |
| late game | 0.751 | 0.852 | 4.30% | 11.90% |
| White to move | 0.646 | 0.931 | 13.47% | 23.96% |
| Black to move | 0.631 | 0.653 | 10.53% | 21.23% |

Axis-preserving and role-swapping transforms are almost equally inconsistent.
This rules out the narrow explanation that only color exchange is mishandled;
the checkpoint has a general coordinate-orientation preference. The problem
also becomes tactically sharper with depth: neural top-1 agreement falls from
21.48% in openings to 4.30% late, while the 512-simulation selected-action
agreement falls from 12.50% to 1.79%.

PUCT did not repair the network disagreement. Its visit-policy mean L1 was
1.345, and the source-selected action averaged rank 73.6 after transformation.
Conversely, the transformed-selected action averaged rank 73.1 in the source
search. This is large enough that a single fixed orientation can materially
change both tactical recommendations and downstream self-play trajectories.

## Interpretation and next step

The current learner consumes serialized replay samples without D4 augmentation,
and the convolutional network is not rotation/reflection equivariant by
construction. Those facts give a direct, testable mechanism for the result,
although this audit alone does not apportion the error between training-data
orientation imbalance and architecture/optimization effects.

Consequently, the existing 1,000-game color split and tactical examples remain
valid observations of the deployed single-orientation agent, but they should
not yet be treated as orientation-independent properties of Escape strategy.
The next implementation will average policy and current-player value over all
eight role-aware orientations, map every policy back to the requested action
space, and expose the ensemble through the same evaluator interface. It must
first demonstrate near-machine-precision neural equivariance and substantially
improved PUCT agreement on this frozen sample. Only then should it be used for
the Black-first matched-seed diagnostic and further strategy-diversity work.

## Limitations

- Neural comparisons use the saved orientation as the reference rather than
  all 28 unordered orientation pairs; every D4 element is nevertheless covered.
- The search audit uses 24 source states. It is a diagnostic of amplification,
  while the 768-state neural audit supplies the higher-powered checkpoint test.
- Finite-budget PUCT includes deterministic action-index tie breaking. That can
  lower exact agreement for close actions, but cannot explain the independently
  observed value and prior-policy discrepancies.
