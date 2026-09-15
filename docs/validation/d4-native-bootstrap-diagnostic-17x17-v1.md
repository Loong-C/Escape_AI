# Random-D4 native bootstrap diagnostic

The fresh `random-d4` lineage did not bootstrap. It was deliberately paused at
an atomic replay-shard boundary after 14,400 of its planned 100,000 games. The
run did not crash, and its replay data and checkpoints remain intact; the stop
prevents another 85,600 games of low-information compute while a preregistered
replacement is validated.

## Preserved run state

- Configuration: `configs/lineages/lineage-d-d4-native-17x17-v1.yaml`, SHA-256
  `5a5910bb5788e6c77a21c6f8bfac08721be6aba46bd1d92af56cafd56c361657`.
- Generation commit:
  `067027bb89d01a0dcdc58d39ded4825e5db713f2`.
- Seed: `20260918`; 64-simulation PUCT; 500 optimizer steps per generation;
  100,000-position replay samples; `random-d4` learner augmentation.
- Completed: 28 generations and 14,000 games, plus four atomic generation-28
  shards containing 400 games. In total there are 14,400 games, 2,281,571
  positions, 144 shards, and 136,622,108 compressed replay bytes.
- Latest checkpoint: `generation-0027.pt`, SHA-256
  `82e69ab352e8187a4c7d6961b5437164d6f686c78ddef9f7b824eb8584f9c412`.
- Paused progress manifest SHA-256:
  `49ed4d1f607d2668b30f0666d73bf64de8afa1534365a3498708a3539722b1c0`.

Resumption would require the recorded configuration and generation commit.
The run is retained as a negative-control ablation and is not a promotion
candidate.

## Evidence for failed bootstrap

| Generation | Total loss | Policy loss | Value loss |
|---:|---:|---:|---:|
| 0 | 6.4495 | 5.4677 | 0.9818 |
| 10 | 6.4620 | 5.4794 | 0.9826 |
| 20 | 6.4721 | 5.4856 | 0.9865 |
| 27 | 6.4733 | 5.4856 | 0.9876 |

Both heads remained at their near-random baselines. This differs from all
three original from-scratch controls. By generation 10, lineage A had reached
total/policy/value losses `5.13/4.83/0.30`; lineage B had learned its value
head (`5.92/5.49/0.43`); and lineage C had reached `5.38/5.02/0.36`.

The concurrently preregistered champion repair did learn under the same
random-D4 replay transform. Across 50,000 games its total loss fell from
4.9327 to 4.1859, policy loss from 4.4935 to 3.8574, and value loss from
0.4392 to 0.3285. This isolates the failure to bootstrapping from an initially
uninformed network rather than to corrupt state/action transforms or a general
learner failure.

The leading interpretation is a self-consistency failure: the raw random
network and raw self-play produce small coordinate-specific asymmetries, while
independently randomizing every learner row averages those early asymmetries
away. An already competent checkpoint supplies a coherent signal and therefore
survives the same augmentation.

## Corrective action

The replacement uses one lexicographically canonical, role-aware D4 state at
both inference and learning time. Every state in an orbit receives the same
neural evaluation, mapped back to source coordinates. Policies on states with
a non-trivial stabilizer are projected onto stabilizer action orbits, so even
the empty board is exactly equivariant. Replay targets are mapped into the same
canonical coordinate system, averaging all equivalent mappings for symmetric
states.

This path costs approximately one neural view per distinct position rather
than the eight views of the proven D4 ensemble. It directly removes the
train/inference mismatch implicated by the failed run. Unit, type, and lint
gates passed before the replacement experiment was registered.
