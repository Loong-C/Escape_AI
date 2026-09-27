"""Install a key restricted to the champion's loopback reverse-forward port."""

from __future__ import annotations

import os
import pwd
import subprocess
from pathlib import Path

user = "escape-inference-tunnel"
home = Path("/var/lib/escape-inference-tunnel")
key = Path("/opt/escape-champion/preflight/tunnel-key.pub").read_text().strip()
if not key.startswith("ssh-ed25519 ") or "\n" in key:
    raise ValueError("expected one Ed25519 public key")
try:
    account = pwd.getpwnam(user)
except KeyError:
    subprocess.run([
        "useradd", "--system", "--create-home", "--home-dir", str(home),
        "--shell", "/usr/sbin/nologin", user,
    ], check=True)
    account = pwd.getpwnam(user)
ssh_dir = home / ".ssh"
ssh_dir.mkdir(mode=0o700, exist_ok=True)
authorized = ssh_dir / "authorized_keys"
if authorized.exists():
    raise RuntimeError("tunnel key is already installed")
authorized.write_text(
    'restrict,port-forwarding,permitlisten="127.0.0.1:18765",command="/bin/false" ' + key + "\n",
)
for path, mode in ((ssh_dir, 0o700), (authorized, 0o600)):
    os.chown(path, account.pw_uid, account.pw_gid)
    os.chmod(path, mode)

configuration = Path("/etc/ssh/sshd_config")
original = configuration.read_text()
backup = Path("/opt/escape-champion/backups/champion-34116c2/sshd_config")
backup.write_text(original)
os.chmod(backup, 0o600)
configuration.write_text(original + """

# Escape champion inference tunnel; all other SSH users retain their settings.
Match User escape-inference-tunnel
    AuthenticationMethods publickey
    PasswordAuthentication no
    KbdInteractiveAuthentication no
    AllowTcpForwarding remote
    GatewayPorts no
    PermitTTY no
    X11Forwarding no
    ClientAliveInterval 15
    ClientAliveCountMax 3
    ForceCommand /bin/false
""")
try:
    subprocess.run(["/usr/sbin/sshd", "-t"], check=True)
except subprocess.CalledProcessError:
    configuration.write_text(original)
    raise
subprocess.run(["systemctl", "reload", "ssh"], check=True)
print("Installed restricted champion tunnel key and idle-connection cleanup")
