# Champion mobile request timeout repair

The user reported several minutes of “AI 正在计算” on a phone. At inspection,
the local GPU service and SSH tunnel were healthy; a public move request completed
in 3.289 seconds (1,227 ms inference). This does not identify the exact failure on
the user's phone, but the previous frontend had a reproducible indefinite wait:
a Worker that never answered still showed thinking after 95 simulated seconds,
with no retry button. The timeout existed only inside that Worker.

The deployment overlay now uses asynchronous same-origin HTTP directly. A
30-second deadline covers both connection and response-body waits, even when an
underlying request ignores cancellation. Errors expose the existing retry button;
abandoned games cancel requests, and invalid moves produce a recoverable error.
The champion checkpoint, D4 ensemble and 512-simulation GPU search are unchanged.

Validation before deployment:

- TypeScript build and production Vite build passed.
- All 35 Vitest tests passed, including seven request tests covering success,
  hung connection/body, cancellation, busy/retry and invalid responses.
- Chromium at 390 × 844 with a deliberately nonresponsive Worker and a stalled
  HTTP request: advancing 31 seconds exposed the timeout and retry button;
  retry successfully placed at (7, 9) and advanced to the human's second turn.
- Python build adapter passed Ruff. Escape source remained read-only.

Browser artifacts are under
`E:/Escape/_AI/deploy/champion-20260927/website-http-v1`;
reproduction scripts are in its parent. Browser simulation is not a test on the
user's physical phone. An already-open page must reload to obtain this repair.

## Published verification

Frontend commit `77574d14229cf93cb188714acd0f2c89b2fae577` was published as
`/var/www/linkukai/escape/releases/champion-77574d1`. Both public domains returned
that release manifest. The archive was 552,043 bytes and was removed after
checksum validation and atomic activation; extracted static files total 1,875,859
bytes. No backend, model, dependency or resident process was added to the VPS.

On the public `www` site, Chromium at 390 × 844 with Worker construction forced
to throw completed a real champion request with HTTP 200 and 512 search nodes in
2,399 ms, placed at (7, 9), and advanced to the human's turn. The served entry
asset was `index-ceDqLnpA.js`. The pre-existing blocked Cloudflare analytics beacon
remains unrelated to game requests.

The previous release `champion-34116c2` is retained. A frontend-only rollback can
atomically repoint `/var/www/linkukai/public/games/Escape` to that directory;
the GPU tunnel and Nginx configuration do not need modification. The record is
`/opt/escape-champion/backups/champion-77574d1/website.json`.
