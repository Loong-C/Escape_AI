"""Build Escape's committed UI with the champion worker, without editing Escape."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import tarfile
from pathlib import Path


def copy_dependencies(source: Path, destination: Path) -> None:
    """Copy installed packages and rebase junctions without writing to the source."""
    links: list[tuple[Path, Path]] = []

    def copy_directory(current: Path, target: Path) -> None:
        target.mkdir(parents=True, exist_ok=True)
        for item in current.iterdir():
            copied = target / item.name
            if item.is_symlink() or os.path.isjunction(item):
                relative = item.resolve().relative_to(source.resolve())
                links.append((copied, destination / relative))
            elif item.is_dir():
                copy_directory(item, copied)
            else:
                shutil.copy2(item, copied)

    copy_directory(source, destination)
    for link, target in links:
        if os.name == "nt" and target.is_dir():
            import _winapi

            _winapi.CreateJunction(str(target), str(link))
        else:
            link.symlink_to(target, target_is_directory=target.is_dir())


def adapt_match_screen(screen: Path) -> None:
    replacements = {
        "AI 搜索深度 {searchStats.depth}，评估 {searchStats.nodes} 个节点":  # noqa: RUF001
            "冠军 AI · D4 · {searchStats.nodes} 次搜索",
        "  const pendingMoveNumber = useRef<number | null>(null);":
            "  const pendingMoveNumber = useRef<number | null>(null);\n"
            "  const aiRequestVersion = useRef(0);",
        "    const requestedMoveNumber = state.moveNumber;":
            "    const requestVersion = ++aiRequestVersion.current;\n"
            "    const requestedMoveNumber = state.moveNumber;",
        "          current.moveNumber !== requestedMoveNumber ||":
            "          requestVersion !== aiRequestVersion.current ||\n"
            "          current.moveNumber !== requestedMoveNumber ||",
        "      .catch((error: Error) => {":
            "      .catch((error: Error) => {\n"
            "        if (requestVersion !== aiRequestVersion.current) return;",
        "      .finally(() => {":
            "      .finally(() => {\n"
            "        if (requestVersion !== aiRequestVersion.current) return;",
        "  function restart(): void {":
            "  function restart(): void {\n"
            "    aiRequestVersion.current += 1;\n"
            "    setAiThinking(false);",
    }
    content = screen.read_text(encoding="utf-8")
    for original, replacement in replacements.items():
        if content.count(original) != 1:
            raise ValueError("source UI changed: review the champion match adapter")
        content = content.replace(original, replacement)
    screen.write_text(content, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=Path("F:/Personal/Code/Escape"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--reuse-dependencies", action="store_true")
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[1]
    source = args.source.resolve()
    output = args.output.resolve()
    if output.exists():
        raise ValueError("use a fresh output directory for an immutable website build")
    git = ["git", "-c", f"safe.directory={source.as_posix()}", "-C", str(source)]
    sha = subprocess.check_output([*git, "rev-parse", "HEAD"], text=True).strip()
    output.mkdir(parents=True)
    archive = output / "source.tar"
    subprocess.run([*git, "archive", "--format=tar", "-o", str(archive), sha], check=True)
    stage = output / "source"
    with tarfile.open(archive) as bundle:
        bundle.extractall(stage, filter="data")
    shutil.copyfile(repo / "deploy/website/ai.worker.ts", stage / "src/ai/ai.worker.ts")
    adapt_match_screen(stage / "src/components/MatchScreen.tsx")
    pnpm = shutil.which("pnpm.cmd") or shutil.which("pnpm")
    if not pnpm:
        raise RuntimeError("pnpm is required")
    if args.reuse_dependencies:
        if (source / "pnpm-lock.yaml").read_text() != (stage / "pnpm-lock.yaml").read_text():
            raise ValueError("installed source lockfile differs from the archived version")
        copy_dependencies(source / "node_modules", stage / "node_modules")
    else:
        subprocess.run([
            pnpm, "install", "--frozen-lockfile", "--store-dir",
            "E:/Escape/_AI/cache/pnpm",
        ], cwd=stage, check=True)
    node = shutil.which("node")
    if not node:
        raise RuntimeError("Node.js is required")
    for command in (
        ["node_modules/typescript/bin/tsc", "-b", "--pretty", "false"],
        ["node_modules/vitest/vitest.mjs", "run"],
        ["node_modules/vite/bin/vite.js", "build"],
    ):
        subprocess.run([node, *command], cwd=stage, check=True)
    manifest = {"escape_source_commit": sha, "adapter": "Escape_AI/deploy/website/ai.worker.ts"}
    (stage / "dist/champion-release.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps({"dist": str(stage / "dist"), **manifest}))


if __name__ == "__main__":
    main()
