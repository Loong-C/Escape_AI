# Shared website deployment (2026-09-29)

Production entry points are `/Escape/`, `/Origametry/` and `/VocaPTest/` on
`https://linkukai.com`. All `/games` paths return 404, with no redirects.

`deploy/unified_server.py` performs the initial migration with configuration backups,
archive validation, Nginx validation, origin checks and rollback on failure.
The VPS serves static files and proxies two loopback ports; no Python model runs there.
A persistent 1 GiB swapfile provides headroom for system maintenance.

`scripts/run_shared_gpu.ps1` supervises two independent CUDA services and one SSH
connection with remote forwards 18765 and 18766. It runs from an immutable deployment
snapshot via the Windows scheduled task `LinkukaiGPU`, at user login. It requires
an awake, connected, signed-in PC. Each backend restarts independently after exit.
The supervisor checks child processes every five seconds. SSH sends a keepalive
every five seconds and exits after two unanswered keepalives, allowing reconnection.
`scripts/enable_shared_gpu_autostart.ps1` installs both the login trigger and an
indefinite one-minute trigger. A running task is left alone; an exited supervisor
is started again. This uses the existing interactive user and does not require
storing a Windows password. It starts after login, not before the login screen.
The protected `gpu-processes.json` records process IDs and creation timestamps;
a replacement supervisor adopts surviving children without duplicate GPU loads or
port conflicts. Its operational events are in `logs/supervisor.log`.

Start manually with `Start-ScheduledTask -TaskName LinkukaiGPU`; inspect with
`Get-ScheduledTask -TaskName LinkukaiGPU` and `Get-ScheduledTaskInfo -TaskName LinkukaiGPU`.
To intentionally suspend automatic recovery, disable the scheduled task first.
Runtime settings and credentials are outside Git under `E:/Escape/_AI/deploy`.
The dedicated SSH key can listen only on the two VPS loopback ports.

The browser checks readiness before starting a game or uploading audio. Nginx checks
upstream readiness before accepting inference requests and normalizes failures to
HTTP 503 with `服务器不可用`. GPU jobs are bounded, with HTTP 429 for busy services.
Escape uses its existing verified champion and 512 simulations. VocaPTest requires
CUDA, prewarms MERT and processes one analysis at a time with batch size 1. Producer
catalog data is exported into the static website so it remains available offline.

Frontend updates must preserve these routes, authentication, readiness checks and
error mappings. Older CPU-only install instructions below are retained for reference;
do not run the CPU installer on this 458 MiB VPS. HAProxy and Xray stay unchanged.

---

# Champion website deployment

Production is live using the local RTX 4060 Ti through the restricted SSH tunnel.
The VPS CPU trial failed and its environment/model/build tools were removed.
See `docs/validation/champion-website-live-20260927.md` for verified URLs,
footprint, runtime task and rollback commands. The CPU instructions below remain
available for future qualification on a larger host.

The Escape repository is read-only. `scripts/build_website.py` archives its
committed source and applies the HTTP client under `deploy/website` in a separate
directory under `E:/Escape/_AI/deploy`. It preserves the original game interface,
tutorial, local two-player mode and hint settings. The client calls the same-origin
`/Escape/api/champion/move` endpoint and never silently falls back to the old AI.
Requests and response bodies have a 30-second deadline and expose the existing
retry button on failure. Server inference does not depend on a browser Worker.
The tutorial overlay fixes distance display timing and supplies minimal worked
examples. All board hints show total escape length including the initial step;
the engine retains its original internal neighbor-distance convention.

## Qualification before cutover

The champion checkpoint is pinned in `play/production.py`. Export with
`scripts/export_champion_onnx.py`; retain its ONNX checksum and equivalence manifest.
CPU inference keeps the original C++ rules, PUCT implementation, eight-view D4
evaluation and 512 simulations. It avoids importing PyTorch and research datasets.

The committed `configs/deployment/champion-cpu-v1.json` fixes the operational
qualification workload and thresholds. Run `scripts/qualify_cpu.py` on the target
host with the production environment and `ESCAPE_SOURCE_COMMIT` set to the deployed
commit. This is an operational test, not new playing-strength evidence. Preserve
the complete JSON result and installed dependency freeze under the artifact root.

Do not cut over unless CPU qualification passes. Otherwise use the authorized
local-GPU fallback and verify a persistent, authenticated loopback SSH tunnel
before changing the public release.

## Runtime and proxy

- Build the C++ extension on Linux into the deployed `src/escape_ai` directory.
- Install `requirements-cpu.txt` into `/opt/escape-champion/venv`.
- Store source/model releases under `/opt/escape-champion/releases/<commit>`;
  `current` points to the selected release.
- `/etc/escape-champion.env` (root-owned, mode 0600) sets `ESCAPE_DEVICE=onnx-cpu`,
  `ESCAPE_ONNX_MODEL`, `ESCAPE_ONNX_SHA256`, and a random `ESCAPE_INFERENCE_KEY`.
- Install `escape-champion.service`; it binds only to loopback, serializes inference,
  rejects concurrent work rather than building a queue, and caps memory at 160 MiB.
- Place `nginx-champion-limits.conf` in Nginx's `conf.d` directory. Include the
  location fragment inside the existing HTTPS server. Create root-only
  `/etc/nginx/snippets/escape-champion-secret.conf` with a `proxy_set_header
  Authorization "Bearer <key>";` directive. Never include the key in client assets
  or Git. Validate `nginx -t` before reloading.

The public proxy limits body size, request rate, simultaneous connections and
timeouts. The backend requires the proxy secret and validates all coordinates and
post codes before invoking C++. The browser sends a position for move suggestion;
this is not an authoritative multiplayer or ranked-game service.

## Release and rollback

Upload the verified website `dist` into a new immutable directory under
`/var/www/linkukai/escape/releases`. Verify file checksums before atomically
switching `/var/www/linkukai/public/Escape`. Save the prior symlink target and
Nginx configuration before changes. Verify both `www.linkukai.com` and
`linkukai.com` through the public proxy, including one actual 512-simulation move.
On any failed verification, atomically restore the previous symlink and Nginx
configuration, run `nginx -t`, and reload. Do not modify HAProxy or Xray.

For local browser QA, set the model environment above and run
`scripts/preview_website.py --dist <website-dist>`. This preview deliberately
injects the proxy key and binds exclusively to `127.0.0.1`; never expose it publicly.
