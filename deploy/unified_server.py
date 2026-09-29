"""Prepare and atomically publish the three static sites on the authorized VPS."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import tarfile
from pathlib import Path

ROOT = Path("/var/www/linkukai")
BACKUP = Path("/opt/linkukai/backups/unified-20260929")
SITE = Path("/etc/nginx/sites-available/linkukai.conf")
SNIPPETS = Path("/etc/nginx/snippets")


def run(*args):
    return subprocess.run(args, check=True, capture_output=True, text=True).stdout


def save(path):
    destination = BACKUP / path.relative_to("/")
    destination.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and not destination.exists():
        shutil.copy2(path, destination)


def prepare(credential):
    BACKUP.mkdir(parents=True, exist_ok=True)
    os.chmod(BACKUP, 0o700)
    save(Path("/etc/fstab"))
    swap = Path("/swapfile")
    if not swap.exists():
        run("fallocate", "-l", "1G", str(swap))
        os.chmod(swap, 0o600)
        run("mkswap", str(swap))
        run("swapon", str(swap))
        with Path("/etc/fstab").open("a") as file:
            file.write("\n/swapfile none swap sw 0 0\n")
    elif "/swapfile" not in Path("/proc/swaps").read_text():
        raise RuntimeError("An inactive swapfile already exists; inspect before changing it")
    limits = Path("/etc/sysctl.d/90-linkukai-swap.conf")
    limits.write_text("vm.swappiness=10\n")
    run("sysctl", "-p", str(limits))
    authorized = Path("/var/lib/escape-inference-tunnel/.ssh/authorized_keys")
    save(authorized)
    text = authorized.read_text()
    if 'permitlisten="127.0.0.1:18766"' not in text:
        if text.count('permitlisten="127.0.0.1:18765"') != 1:
            raise RuntimeError("Unexpected tunnel key restrictions")
        authorized.write_text(
            text.replace(
                'permitlisten="127.0.0.1:18765"',
                'permitlisten="127.0.0.1:18765",permitlisten="127.0.0.1:18766"',
            )
        )
    run("/usr/sbin/sshd", "-t")
    secret = Path(credential).read_text().strip()
    if not re.fullmatch(r"[a-f0-9]{64}", secret):
        raise ValueError("Invalid proxy secret")
    path = SNIPPETS / "vocaptest-secret.conf"
    if path.exists():
        raise RuntimeError("VocaPTest credential already installed")
    path.write_text(f'proxy_set_header Authorization "Bearer {secret}";\n')
    os.chmod(path, 0o600)
    Path(credential).unlink()
    print(run("free", "-m"))


ERRORS = """
location @gpu_unavailable {
    default_type application/json;
    add_header Cache-Control "no-store" always;
    return 503 '{"detail":"服务器不可用"}';
}
location = /games { return 404; }
location ^~ /games/ { add_header Cache-Control "no-store" always; return 404; }
"""


def proxy(port, endpoint, *, secret=None, timeout=5):
    return f"""proxy_pass http://127.0.0.1:{port}/{endpoint};
    proxy_http_version 1.1;
    proxy_set_header Connection "";
    proxy_connect_timeout 2s;
    proxy_read_timeout {timeout}s;
    proxy_send_timeout 30s;
    proxy_next_upstream off;
    proxy_intercept_errors on;
    error_page 500 502 503 504 =503 @gpu_unavailable;
    add_header Cache-Control "no-store" always;
""" + (f"    include /etc/nginx/snippets/{secret};\n" if secret else "")


def escape_routes():
    return (
        """location = /Escape/api/champion/health {
    limit_except GET { deny all; }
    """
        + proxy(18765, "health", timeout=3)
        + """}
location = /_escape_ready {
    internal;
    proxy_pass_request_body off;
    proxy_set_header Content-Length "";
    """
        + proxy(18765, "health", timeout=3)
        + """}
location = /Escape/api/champion/move {
    limit_except POST { deny all; }
    auth_request /_escape_ready;
    client_max_body_size 8k;
    limit_req zone=escape_champion burst=4 nodelay;
    limit_req_status 429;
    limit_conn escape_champion_connections 4;
    limit_conn_status 429;
    """
        + proxy(18765, "move", secret="escape-champion-secret.conf", timeout=25)
        + """}
location ^~ /Escape/api/ { return 404; }
"""
    )


def voca_routes():
    return (
        """location = /VocaPTest { return 308 /VocaPTest/; }
location = /VocaPTest/health {
    limit_except GET { deny all; }
    """
        + proxy(18766, "health", timeout=3)
        + """}
location = /_vocap_ready {
    internal;
    proxy_pass_request_body off;
    proxy_set_header Content-Length "";
    """
        + proxy(18766, "health", timeout=3)
        + """}
location = /VocaPTest/api/analyze/jobs {
    limit_except POST { deny all; }
    auth_request /_vocap_ready;
    client_max_body_size 51m;
    client_body_timeout 20s;
    proxy_request_buffering off;
    limit_req zone=vocap_analysis burst=2 nodelay;
    limit_req_status 429;
    limit_conn vocap_uploads 2;
    limit_conn_status 429;
    """
        + proxy(18766, "api/analyze/jobs", secret="vocaptest-secret.conf", timeout=10)
        + """}
location ^~ /VocaPTest/api/jobs/ {
    limit_except GET { deny all; }
    """
        + proxy(18766, "api/jobs/", secret="vocaptest-secret.conf")
        + """}
location ^~ /VocaPTest/api/ { return 404; }
location ^~ /VocaPTest/catalog/ {
    include /etc/nginx/snippets/vocaptest-security-headers.conf;
    expires -1;
    try_files $uri =404;
}
location ^~ /VocaPTest/assets/ {
    include /etc/nginx/snippets/vocaptest-security-headers.conf;
    expires 1y;
    try_files $uri =404;
}
location /VocaPTest/ {
    include /etc/nginx/snippets/vocaptest-security-headers.conf;
    expires -1;
    try_files $uri $uri/ /VocaPTest/index.html;
}
"""
    )


def apply(release, archives):
    if not re.fullmatch(r"[a-zA-Z0-9._-]{1,70}", release):
        raise ValueError("Invalid release name")
    originals = {}
    links = {}
    for name, archive in zip(("Escape", "Origametry", "VocaPTest"), archives, strict=True):
        target = ROOT / name.lower() / "releases" / release
        if target.exists():
            raise RuntimeError(f"Release already exists: {target}")
        target.mkdir(parents=True)
        with tarfile.open(archive) as bundle:
            for member in bundle.getmembers():
                destination = (target / member.name).resolve()
                if not destination.is_relative_to(target) or not (
                    member.isfile() or member.isdir()
                ):
                    raise ValueError("Unsafe archive")
            bundle.extractall(target, filter="data")
        assert (target / "index.html").is_file()
        assert (target / "release.json").is_file()
        live = ROOT / "public" / name
        if live.exists() or live.is_symlink():
            raise RuntimeError(f"New public path already exists: {live}")
        links[live] = target
    text = SITE.read_text().replace("/games/Escape", "/Escape")
    if "/etc/nginx/snippets/origametry-locations.conf" not in text:
        raise RuntimeError("Unexpected existing site config")
    text = text.replace(
        "    location / {\n        return 404;\n    }",
        "    include /etc/nginx/snippets/unified-locations.conf;\n\n"
        "    location / {\n        return 404;\n    }",
    )
    updates = {
        SITE: text,
        SNIPPETS / "escape-champion-locations.conf": escape_routes(),
        SNIPPETS / "origametry-locations.conf": (SNIPPETS / "origametry-locations.conf")
        .read_text()
        .replace("/games/Origametry", "/Origametry"),
        SNIPPETS / "unified-locations.conf": ERRORS + voca_routes(),
        Path(
            "/etc/nginx/conf.d/vocaptest-limits.conf"
        ): ("limit_req_zone $binary_remote_addr zone=vocap_analysis:1m rate=6r/m;\n"
            "limit_conn_zone $server_name zone=vocap_uploads:1m;\n"),
    }
    try:
        for path, content in updates.items():
            save(path)
            originals[str(path)] = path.read_text() if path.exists() else None
            path.write_text(content)
        for live, target in links.items():
            live.symlink_to(target)
        run("nginx", "-t")
        run("systemctl", "reload", "nginx")
        for name in ("Escape", "Origametry", "VocaPTest"):
            run(
                "curl",
                "-fsS",
                "--max-time",
                "10",
                "--cacert",
                "/etc/nginx/ssl/linkukai/fullchain.pem",
                "--resolve",
                "linkukai.com:443:127.0.0.1",
                f"https://linkukai.com/{name}/",
            )
        (BACKUP / "rollback.json").write_text(
            json.dumps({"files": originals, "links": [str(p) for p in links]})
        )
        print("Published all three sites; configuration and origin checks passed")
    except BaseException:
        for path, content in originals.items():
            if content is None:
                Path(path).unlink(missing_ok=True)
            else:
                Path(path).write_text(content)
        for live in links:
            if live.is_symlink():
                live.unlink()
        run("nginx", "-t")
        run("systemctl", "reload", "nginx")
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="action", required=True)
    pre = sub.add_parser("prepare")
    pre.add_argument("credential")
    cut = sub.add_parser("apply")
    cut.add_argument("release")
    cut.add_argument("archives", nargs=3)
    args = parser.parse_args()
    if args.action == "prepare":
        prepare(args.credential)
    else:
        apply(args.release, args.archives)
