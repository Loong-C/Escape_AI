"""Stage a verified champion release, then explicitly activate or roll it back."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import secrets
import shutil
import subprocess
import tarfile
from pathlib import Path

BASE = Path("/opt/escape-champion")
ACTIVE = Path("/var/www/linkukai/public/games/Escape")
NGINX = Path("/etc/nginx/sites-enabled/linkukai.conf")


def run(*args: str) -> None:
    subprocess.run(args, check=True)


def atomic_link(target: Path, link: Path) -> None:
    temporary = link.with_name(link.name + ".champion-next")
    if temporary.exists() or temporary.is_symlink():
        raise RuntimeError(f"unexpected pending link: {temporary}")
    temporary.symlink_to(target)
    temporary.replace(link)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["prepare", "activate", "rollback"])
    parser.add_argument("--release", required=True)
    parser.add_argument("--backend", choices=["cpu", "tunnel"], default="cpu")
    args = parser.parse_args()
    if not re.fullmatch(r"champion-[0-9a-f]{7,40}", args.release):
        raise ValueError("invalid release name")
    website = Path("/var/www/linkukai/escape/releases") / args.release
    backup = BASE / "backups" / args.release
    record_path = backup / "deployment.json"
    if args.command == "rollback":
        record = json.loads(record_path.read_text())
        atomic_link(Path(record["previous_website"]), ACTIVE)
        NGINX.resolve().write_bytes((backup / "nginx.conf").read_bytes())
        run("nginx", "-t")
        run("systemctl", "reload", "nginx")
        print("Rolled back to", record["previous_website"])
        return
    if args.command == "activate":
        if not record_path.is_file():
            raise RuntimeError("prepare the release and save its rollback record first")
        atomic_link(website, ACTIVE)
        print("Activated", website)
        return

    if website.exists() or backup.exists():
        raise RuntimeError("use a fresh immutable release name")
    preflight = BASE / "preflight"
    backup.mkdir(parents=True, mode=0o700)
    record = {"previous_website": str(ACTIVE.resolve()), "backend": args.backend}
    record_path.write_text(json.dumps(record, indent=2) + "\n")
    shutil.copy2(NGINX.resolve(), backup / "nginx.conf")
    website.mkdir(parents=True)
    with tarfile.open(preflight / "website-34116c2.tar.gz") as archive:
        archive.extractall(website, filter="data")
    manifest = json.loads((website / "champion-release.json").read_text())
    for name, expected in manifest["files"].items():
        target = (website / name).resolve()
        target.relative_to(website.resolve())
        if hashlib.sha256(target.read_bytes()).hexdigest() != expected:
            raise ValueError(f"website checksum mismatch: {name}")

    key = secrets.token_hex(32)
    env_path = Path("/etc/escape-champion.env")
    if env_path.exists():
        raise RuntimeError("production environment already exists; do not overwrite secrets")
    environment = {"ESCAPE_INFERENCE_KEY": key}
    if args.backend == "cpu":
        backend = BASE / "releases" / args.release
        shutil.copytree(preflight / "backend", backend)
        shutil.copy2(preflight / "champion.onnx", backend / "champion.onnx")
        environment.update(
            ESCAPE_DEVICE="onnx-cpu",
            ESCAPE_ONNX_MODEL=str(backend / "champion.onnx"),
            ESCAPE_ONNX_SHA256=manifest["onnx_sha256"],
        )
        atomic_link(backend, BASE / "current")
    with env_path.open("x") as stream:
        os.chmod(env_path, 0o600)
        stream.write("".join(f"{name}={value}\n" for name, value in environment.items()))

    templates = preflight / "backend" / "deploy"
    if args.backend == "cpu":
        shutil.copy2(templates / "escape-champion.service", "/etc/systemd/system/")
        run("systemctl", "daemon-reload")
        run("systemctl", "enable", "--now", "escape-champion")

    secret_path = Path("/etc/nginx/snippets/escape-champion-secret.conf")
    with secret_path.open("x") as stream:
        os.chmod(secret_path, 0o600)
        stream.write(f'proxy_set_header Authorization "Bearer {key}";\n')
    shutil.copy2(
        templates / "nginx-champion-limits.conf", "/etc/nginx/conf.d/escape-champion-limits.conf",
    )
    shutil.copy2(
        templates / "nginx-champion-locations.conf",
        "/etc/nginx/snippets/escape-champion-locations.conf",
    )
    original = NGINX.resolve().read_text()
    marker = "    location = /games/Escape {"
    if original.count(marker) != 1:
        raise RuntimeError("unexpected Nginx configuration")
    updated = original.replace(
        marker, "    include /etc/nginx/snippets/escape-champion-locations.conf;\n\n" + marker,
    )
    NGINX.resolve().write_text(updated)
    try:
        run("nginx", "-t")
        run("systemctl", "reload", "nginx")
    except subprocess.CalledProcessError:
        NGINX.resolve().write_text(original)
        run("nginx", "-t")
        run("systemctl", "reload", "nginx")
        raise
    print("Prepared and checksum-verified", website, "with", args.backend, "backend")
    print("Website remains at", record["previous_website"])


if __name__ == "__main__":
    main()
