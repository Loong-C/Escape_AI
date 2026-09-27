# Champion website deployment

The Escape repository is read-only. `scripts/build_website.py` archives its
committed source and applies the worker under `deploy/website` in a separate
directory under `E:/Escape/_AI/deploy`. It preserves the original game interface,
tutorial, local two-player mode and hint settings. The worker calls the same-origin
`/games/Escape/api/champion/move` endpoint and never silently falls back to the old AI.

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
switching `/var/www/linkukai/public/games/Escape`. Save the prior symlink target and
Nginx configuration before changes. Verify both `www.linkukai.com` and
`linkukai.com` through the public proxy, including one actual 512-simulation move.
On any failed verification, atomically restore the previous symlink and Nginx
configuration, run `nginx -t`, and reload. Do not modify HAProxy or Xray.

For local browser QA, set the model environment above and run
`scripts/preview_website.py --dist <website-dist>`. This preview deliberately
injects the proxy key and binds exclusively to `127.0.0.1`; never expose it publicly.
