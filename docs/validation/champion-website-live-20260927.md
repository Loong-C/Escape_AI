# Champion AI live on Escape

Deployment completed on 2026-09-27. Both
`https://www.linkukai.com/games/Escape/` and
`https://linkukai.com/games/Escape/` serve the champion integration.

## Runtime and provenance

- Website source: Escape `a8174fd79546112cea39cf200db333808f1a0d29`.
- Inference and website adapter: Escape_AI `34116c20d598f963cbd9922dae538e299657a2e5`.
- Supervisor: Escape_AI `4f38950`, copied into the immutable local deployment folder.
- Model: lineage C generation 199, SHA-256
  `0257bbee5f97e0c163ecf64eb50160fd8f8b6189b6ac042fd52dced3b0449bf3`.
- Role-aware D4 ensemble, 512 PUCT simulations, 16 parallel leaves, `c_puct=1.5`,
  temperature zero and no root noise. CUDA runs on the local RTX 4060 Ti.
- Public release: `/var/www/linkukai/escape/releases/champion-34116c2`.
  The prior `a8174fd` release remains available for rollback.
- The Escape source repository was not modified. Research and deployment changes
  were committed and pushed on `codex/escape-ai-research`.

The VPS forwards only to a loopback SSH listener. It does not run an AI Python
process. The dedicated SSH key can create only the specified reverse forward;
the account has no interactive shell. Nginx injects the private API credential,
limits requests and body size, and exposes neither research datasets nor credentials.

## Production verification

1. Both public hostnames returned the pinned CUDA model and a legal 512-simulation
   response before the atomic frontend switch. Observed HTTPS round trips were
   3.608 and 3.023 seconds, including network transit; inference was 1.683 and
   1.191 seconds respectively. These are smoke observations, not latency guarantees.
2. Both hostnames exposed the expected release manifest after cutover; all staged
   files were checked against the manifest before activation.
3. Real Chromium on the public `www` site started a human-Black game. The AI made
   the White opening at (7,9), the human placed at (1,1), and White replied at
   (7,10), advancing to turn 4. The interface displayed `D4 · 512` and both AI
   network requests returned HTTP 200.
4. Desktop 1280×720 and mobile 390×844 screenshots were inspected. The board,
   turn information and controls remain usable. There were no application errors.
   Cloudflare's injected analytics beacon is blocked by the existing self-only
   script CSP; this unrelated analytics error was recorded, and CSP was not weakened.
5. The exact dedicated local tunnel process was terminated once. The supervisor
   created a new tunnel and public CUDA health recovered in 9.19 seconds.
6. After cleanup and reconnect, another public 512-simulation request succeeded;
   inference was 1.157 seconds. Nginx, HAProxy, Xray and SSH remained active, and
   Nginx/sshd configuration checks passed.

Local evidence, screenshots and runtime files are under
`E:/Escape/_AI/deploy/champion-20260927`. Earlier checks also passed all 154 backend
tests, 28 frontend tests, TypeScript, Ruff, strict mypy and the production build.

## Minimal VPS footprint

The CPU qualification failed, so its 241 MiB virtual environment, 8.9 MiB preflight
directory (including the champion ONNX copy and compiler outputs), the exact 52
packages newly installed for this task, and their package cache were removed.
APT removal was first simulated and required an exact match to the original
installation history. No general autoremove or historical-release pruning was used.
Temporary compilation swap had already been disabled and deleted before testing.

The retained new website release occupies 1,876,091 logical bytes (about 1.9 MB).
`/opt/escape-champion` contains only 21,544 logical bytes of management scripts,
logs and rollback metadata (52 KiB allocated). Small Nginx/SSH configuration and
the public tunnel key remain in their normal system directories. Existing releases
and the pre-existing droplet-agent package cache were left intact.

The final VPS check reported 195 MiB available out of 458 MiB RAM, no swap, and
5.4 GiB disk space available. Availability fluctuates with normal system activity.

## Operation and rollback

Windows scheduled task `EscapeChampionGPU` is running. It starts at the current
user's login, restarts an exited inference process and reconnects a lost SSH
tunnel. The task runs hidden and uses the fixed source snapshot, not the mutable
research working tree. Credentials/private key are readable only by the current
Windows account and SYSTEM. Login triggering is configured; an actual logout or
reboot was not performed during validation.

The local computer must remain powered on, signed in, connected and awake for
public AI play. If it is unavailable, the site reports an AI connection error and
offers retry; it does not silently substitute the older AI. Static game pages,
the tutorial and local two-player mode remain hosted on the VPS.

To start the local task manually:

```powershell
Start-ScheduledTask -TaskName EscapeChampionGPU
```

To roll the public website and Nginx routes back on the VPS:

```sh
python3 /opt/escape-champion/management/install_server.py rollback --release champion-34116c2
```

The rollback leaves the GPU task and dedicated tunnel configured; stop the local
task separately if retiring the integration. Do not delete the saved release or
backup metadata before selecting a replacement rollback target.
