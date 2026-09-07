# Large-artifact storage migration to E drive

Date: 2026-09-07

The canonical large-artifact root changed from `G:\Escape\_AI` to
`E:\Escape\_AI` at the user's request. Training was stopped after a complete
Parquet shard for lineage B generation 27, leaving 100 of 500 games recorded
for that generation.

The migration copied 1,388 files totaling 1,719,775,390 bytes. A fast
file-count and total-byte comparison matched between source and destination;
the user explicitly waived a second full per-file hash pass. Existing shard
and checkpoint SHA-256 values remain recorded in their manifests and progress
files.

The active lineage progress receives a storage-migration provenance record
that identifies the old and new artifact roots and Git commits. Historical
checkpoint metadata is not rewritten. Training resumes from the last atomic
shard boundary, and all subsequent artifacts use the E drive root.

The original G-drive tree was retained as a migration backup because the
execution environment blocked recursive deletion of that root. It is no longer
canonical and must not receive new artifacts.
