# Production qualification: VPS rejected, local GPU verified

Update: the dedicated tunnel and local task were subsequently authorized and
deployed. See `champion-website-live-20260927.md` for the completed deployment and
VPS cleanup. The pending-approval status below is a historical checkpoint.

The user authorized uploading inference source and the champion model to
`lab-vps` (139.59.239.152). The operational workload was committed before execution
in `configs/deployment/champion-cpu-v1.json`; deployed inference source is commit
`34116c20d598f963cbd9922dae538e299657a2e5`.

## VPS result

- Hardware: one DO-Regular virtual CPU, 458 MiB RAM, no GPU; Python 3.12.3.
- Checkpoint SHA-256:
  `0257bbee5f97e0c163ecf64eb50160fd8f8b6189b6ac042fd52dced3b0449bf3`.
- ONNX SHA-256:
  `9265c64979c75e8ea239e01e2b6724c10a6fbc3f07aa9765bd92af3a9f1bd962`.
- Seed: 20260927. D4 ensemble, 512 PUCT simulations, 16 parallel leaves,
  `c_puct=1.5`, one CPU thread, maximum inference batch 256.
- The first opening took **12.425 seconds**, exceeding the precommitted 12-second
  threshold. It returned legal action (row 6, column 8).
- That sample reported peak RSS 104.309 MiB and host available memory 141.949 MiB.
  Its serialized state SHA-256 was
  `aeef4a2affb99985f24a7148f7795db2496debcd5fe3917211d5544d1a75af39`.
- Subsequent work reached the **160 MiB cgroup memory ceiling** and the isolated
  process was OOM-killed. Only one of six planned samples completed; no six-sample
  result is claimed. Systemd reported 15.611 seconds runtime and 14.816 CPU seconds.
- Result: **failed resource qualification**. Do not serve this configuration on
  the existing VPS. The Nginx, HAProxy and Xray services remained active.

The C++ core was compiled with GCC using C++20/O2; Python bindings used O0 to reduce
compiler resource requirements. A temporary 256 MiB swap file was used only for
compilation. It was disabled and removed before the inference test, which ran
without swap. This operational result is not a playing-strength comparison.

Full logs, resolved Python dependencies, model/export manifest and build scripts
are under `E:/Escape/_AI/deploy/champion-20260927`; corresponding server preflight
artifacts are under `/opt/escape-champion/preflight`.

## Authorized fallback smoke

The unchanged pinned source was extracted into an independent local directory
and paired with the existing Windows C++ extension. A real FastAPI request on the
RTX 4060 Ti (8 GiB) completed the same seeded opening in **593 ms**, with the same
legal move. The response identifies CUDA, D4, 512 simulations and the pinned
checkpoint hash. Model/service load took 1.548 seconds. The complete response is
`gpu-smoke.json` under the artifact directory. This smoke opens no public port.

## Release status

The verified website is staged at
`/var/www/linkukai/escape/releases/champion-34116c2`; its manifest checksums match.
Nginx now has restricted same-origin champion API locations, but the active game
symlink still points at the original `a8174fd` release. It has not switched to the
new worker. The intended GPU backend is not yet connected.

Automatic approval review rejected the dedicated SSH account/public-key setup,
sshd changes and retrieval of the newly generated AI API credential. The user was
asked to authorize those specific steps plus a local login-started supervisor.
They remain unexecuted pending that response. The private tunnel key stays local;
it is not uploaded. Once authorized, verify the complete tunnel/API path before
activating the staged website, then test both public hostnames and browser play.
