# Champion website integration — prepared, not deployed

## Selected agent

Lineage C generation 199, checkpoint
`0257bbee5f97e0c163ecf64eb50160fd8f8b6189b6ac042fd52dced3b0449bf3`, with
role-aware eight-view D4 evaluation, 512 PUCT simulations, 16 parallel leaves,
`c_puct=1.5`, zero temperature and no root noise. This selection follows the
completed championship and 2,000-game raw/D4 comparison, not checkpoint recency.

The ONNX export is
`9265c64979c75e8ea239e01e2b6724c10a6fbc3f07aa9765bd92af3a9f1bd962`.
Across 32 positions generated with seed 20260927, maximum D4 policy error was
8.94e-8 and maximum value error was 2.242e-6 against PyTorch. This verifies
numerical equivalence within the export tolerances; it is not another strength test.

## Implementation and validation

- Backend and committed CPU qualification protocol: commit `1673817`.
- Original website source: Escape commit `a8174fd79546112cea39cf200db333808f1a0d29`.
  The source repository remains unchanged. All integration code lives in Escape_AI.
- The public-facing adapter preserves the game UI and replaces its worker with
  same-origin champion inference. Busy/unavailable service errors are explicit.
- A request generation guard prevents replies from a previous game affecting a
  restarted game, including old errors and completion callbacks.
- Backend: 154 tests passed; Ruff and strict mypy passed.
- Website: TypeScript, all 28 existing tests, and production build passed.
- Real Chromium at `http://127.0.0.1:8766/games/Escape/`: human White placed at
  (1,1), champion Black replied at (9,12), and UI advanced to turn 3 with
  `D4 · 512` displayed. Normal operation produced no console warnings or errors.
- Browser fault injection: a delayed real response was discarded after restart;
  a deliberate 503 displayed a retry control, and retry received a real HTTP 200
  response from the champion. The injected 503 produced the expected browser
  network error; it was not an unhandled application exception.
- Screenshots at 1280×720 and 390×844 were inspected. Board and controls remain
  readable and aligned; the mobile actions continue below the initial viewport.
- Browser plugin was unavailable; the installed Playwright CLI was used.

Artifacts are under `E:/Escape/_AI/deploy/champion-20260927`. The final build is
`website-v4/source/dist`; screenshots are `desktop.png` and `mobile.png`.
The local CPU ONNX preview completed one observed move in 11.237 seconds, with
a measured process peak working set of about 125.2 MiB. These are Windows preview
measurements, not VPS qualification. A separate local PyTorch single-thread
opening smoke took 2.876 seconds; it uses a different runtime and position.

## Production status and remaining gate

The existing `lab-vps` SSH host is 139.59.239.152, reports hostname
`LinkukaiInSingapore`, one virtual CPU, 458 MiB RAM, no swap and no GPU.
Its active website release is `/var/www/linkukai/escape/releases/a8174fd`.
The local release HTML, public `www.linkukai.com/games/Escape/`, and public
`linkukai.com/games/Escape/` all had SHA-256
`eb5f6d4652c07d7784c4d941bb1e5b60bee860b3ae0dbe1d778fbb7e7c1efc64`.

Python build prerequisites and an isolated `/opt/escape-champion/venv` were
installed for the requested CPU qualification. No inference source or model was
uploaded, no inference daemon was installed, no Nginx configuration was changed,
and the public release symlink was not switched.

Automatic approval review rejected the source/model upload twice, including
after the matching-site hash evidence. It requires explicit user authorization
for these payloads to SSH target `lab-vps` / `139.59.239.152`. That confirmation
was requested. CPU qualification and public deployment remain pending it.

After approval: upload only the committed inference source and pinned model;
build the canonical extension; run the committed CPU qualification protocol
within a memory limit; choose VPS CPU only if its thresholds pass, otherwise use
the user-authorized local GPU fallback. Validate the proxy and a live move before
and after an atomic website release switch. Retain the previous release for rollback.
