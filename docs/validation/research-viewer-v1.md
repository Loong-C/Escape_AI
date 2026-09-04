# Research viewer validation: v1

Date: 2026-09-04

The read-only viewer was exercised against the four-game
`research-smoke-3x3-v1` Parquet dataset. Its FastAPI layer decodes the stored
pre-move C++ states and computes the otherwise unstored final state by applying
the last recorded action.

## Automated checks

- Python: Ruff, strict mypy, and 85 pytest tests passed.
- Viewer: TypeScript project build, two Vitest assertions, and Vite production
  build passed.
- API: game listing, missing-game handling, state decoding, and terminal-state
  reconstruction are covered by `tests/test_viewer_api.py`.

## Browser checks

Playwright loaded the production build through the FastAPI server. The initial
position, two keyboard-driven timeline steps, and terminal position all kept
the React metrics synchronized with the Phaser canvas. A 390 by 844 viewport
stacked the analysis rail below an unobstructed board. Browser console checks
reported zero errors. The only visual issue found, an oversized move marker on
very small boards, was fixed by capping the marker radius.

The smoke data is deliberately a 3 by 3 integration fixture. A 17 by 17 pilot
is required before treating the viewer or generation throughput as formal-run
evidence.
