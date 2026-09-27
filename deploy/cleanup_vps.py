"""Remove only this deployment's unused CPU trial and newly installed build tools."""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--apply", action="store_true")
args = parser.parse_args()
base = Path("/opt/escape-champion")
if base.resolve() != base:
    raise RuntimeError("unexpected deployment root")
history = Path("/var/log/apt/history.log").read_text()
command = (
    "Commandline: apt-get install -y --no-install-recommends python3-venv python3-dev g++ cmake"
)
blocks = [block for block in history.split("\n\n") if command in block]
if len(blocks) != 1 or "Start-Date: 2026-09-27  07:59:32" not in blocks[0]:
    raise RuntimeError("cannot uniquely identify this task's installation")
installed = next(line.removeprefix("Install: ") for line in blocks[0].splitlines()
                 if line.startswith("Install: "))
packages = re.findall(r"(?:^|, )([a-z0-9+.-]+)(?::[a-z0-9]+)? \(", installed)
if len(packages) != 52:
    raise RuntimeError("unexpected installation package count")
simulation = subprocess.check_output(["apt-get", "--simulate", "purge", *packages], text=True)
removed = set(re.findall(r"^(?:Remv|Purg) ([^\s:]+)", simulation, re.MULTILINE))
if removed != set(packages):
    raise RuntimeError("APT removal would affect a different package set")
print(simulation)
targets = [base / "preflight", base / "venv"]
for target in targets:
    if target.resolve() != target or target.parent != base:
        raise RuntimeError("unsafe cleanup path")
    print("Unused task artifact:", target)
if not args.apply:
    raise SystemExit(0)
for process in Path("/proc").iterdir():
    if not process.name.isdigit():
        continue
    try:
        commandline = (process / "cmdline").read_bytes().split(b"\0")
    except (FileNotFoundError, PermissionError, ProcessLookupError):
        continue
    if commandline and any(commandline[0].startswith(str(target).encode()) for target in targets):
        raise RuntimeError(f"task artifact is still in use by process {process.name}")
for target in targets:
    if target.is_dir():
        shutil.rmtree(target)
subprocess.run(
    ["apt-get", "purge", "-y", *packages], check=True,
    env={**os.environ, "DEBIAN_FRONTEND": "noninteractive"},
)
for archive in Path("/var/cache/apt/archives").glob("*.deb"):
    if archive.name.split("_", 1)[0] in packages:
        archive.unlink()
print("Removed this task's CPU environment, test artifacts, 52 new build packages and their cache.")
