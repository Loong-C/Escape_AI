# Escape AI workspace rules

- Perform all repository work in `F:\Personal\Code\Escape_AI`.
- Treat `F:\Personal\Code\Escape` as a read-only source of rules, tests, and reusable visual assets. Never modify or commit that repository as part of Escape AI work.
- The canonical large-artifact root is `G:\Escape\_AI`. Checkpoints, replay buffers, generated games, training runs, and caches belong there, not in Git.
- Git may contain source code, dependency locks, experiment configurations, schemas, checksums, compact fixtures, metric summaries, and research reports.
- Develop on `codex/escape-ai-research`. After each independently verified milestone, create a conventional commit and push it to `origin`. Never force-push. Fast-forward `main` only after all agreed quality gates pass.
- A formal experiment configuration must be committed before the run begins. Its result summary must identify the Git commit, configuration, seeds, hardware, search budget, model hashes, and data hashes needed for reproduction.
- Keep the deterministic rules simulation independent of the future Phaser viewer. The viewer may render serialized states but must not become a rules source of truth.

