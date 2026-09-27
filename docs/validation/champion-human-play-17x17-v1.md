# 17×17 champion human-play deployment

The interactive site serves the strongest agent that had completed a formal,
matched-color strength test at implementation time: lineage C generation 199
wrapped in the role-aware D4 ensemble. The underlying checkpoint SHA-256 is
`0257bbee5f97e0c163ecf64eb50160fd8f8b6189b6ac042fd52dced3b0449bf3`.

The choice is evidence-based. At equal 512-simulation PUCT budgets, the D4
evaluator scored 72.825% over 2,000 paired games against raw inference from the
same checkpoint. The checkpoint itself won the 10,000-game three-lineage
championship before the D4 correction was tested. Later training artifacts are
not advertised as stronger until they pass a comparable strength evaluation.

## Runtime contract

- Board: canonical 17×17 rules from the C++ core.
- Evaluator: eight-view role-aware D4 ensemble, maximum inference batch 256.
- Search: 512 PUCT simulations, `c_puct=1.5`, 16 parallel leaves, temperature
  zero, and no root noise.
- Human may start as White or let the AI make the White opening and play Black.
- The browser submits only an action integer. Legality, state transitions,
  terminal adjudication, and the AI reply are all computed on the server.
- Sessions are in memory and intentionally bounded to 64; restarting the local
  service starts fresh games.

The UI exposes the checkpoint prefix, evaluator, search budget, AI value,
search candidates, elapsed time, and move log. The existing analysis-grade
research viewer remains available from the header without becoming a rules
source of truth.

## Launch

From the repository root:

```powershell
pwsh scripts/run_champion_play.ps1
```

Then open `http://127.0.0.1:8765`. The launcher rebuilds the production client,
verifies the champion checkpoint hash once, loads the model on CUDA, and starts
the FastAPI/Phaser site. `-BindHost 0.0.0.0` may be used for trusted LAN access;
public Internet hosting requires a reverse proxy, TLS, authentication, and
request-rate limits around the GPU endpoint.

## Validation

- Python service and FastAPI round-trip tests cover both colors, legal-action
  enforcement, AI replies, unknown sessions, and bounded-session eviction.
- The full Python Ruff and strict mypy gates pass; the focused play/API suite
  passes 6 tests.
- The React client passes TypeScript checking, Vitest, and a Vite production
  build.
- A CUDA smoke loaded the pinned checkpoint in 0.257 seconds and completed a
  512-simulation D4 opening search in 0.844 seconds on the local RTX 4060 Ti.
- A real Chromium run created a White game, clicked A1 on the Phaser canvas,
  received a legal Black reply with search statistics, created a Black game
  after an AI White opening, switched to the 1,000-game research dataset, and
  showed no browser warnings or errors. Desktop and 390×844 responsive views
  were visually inspected.
