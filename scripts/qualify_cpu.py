"""Measure the production search on fixed positions before website cutover."""

from __future__ import annotations

import hashlib
import json
import os
import platform
import random
import resource
import sys
import time
from pathlib import Path

from escape_ai import _escape_core
from escape_ai.play.production import app_factory

config_path = Path(sys.argv[1])
config = json.loads(config_path.read_text())
app = app_factory()
from fastapi.testclient import TestClient  # noqa: E402

client = TestClient(app)
rng = random.Random(config["seed"])
samples = []
for target_ply in config["positions_at_random_plies"]:
    state = _escape_core.State(17)
    for _ in range(target_ply):
        if state.outcome["status"] != "playing":
            state = _escape_core.State(17)
        state = state.apply(rng.choice(state.legal_actions()))
    if state.outcome["status"] != "playing":
        state = _escape_core.State(17)
    payload = {
        "posts": state.posts, "ball": {"row": state.ball[0], "col": state.ball[1]},
        "turn": state.turn, "seed": config["seed"],
    }
    started = time.perf_counter()
    response = client.post(
        "/move", json=payload,
        headers={"Authorization": "Bearer " + os.environ["ESCAPE_INFERENCE_KEY"]},
    )
    assert response.status_code == 200, response.text
    move = response.json()["move"]
    assert state.legal_move_kind(move["row"] * 18 + move["col"]) == move["kind"]
    available = next(
        int(line.split()[1]) / 1024 for line in Path("/proc/meminfo").read_text().splitlines()
        if line.startswith("MemAvailable:")
    )
    sample = {
        "target_ply": target_ply, "actual_ply": state.ply,
        "seconds": round(time.perf_counter() - started, 3),
        "peak_rss_mib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024,
        "host_available_mib": available,
        "state_sha256": hashlib.sha256(state.serialize()).hexdigest(),
        "move": move,
    }
    samples.append(sample)
    print(json.dumps(sample), flush=True)
result = {
    "git_commit": os.environ["ESCAPE_SOURCE_COMMIT"],
    "config_sha256": hashlib.sha256(config_path.read_bytes()).hexdigest(),
    "configuration": config, "platform": platform.platform(),
    "cpu": Path("/proc/cpuinfo").read_text(), "model": client.get("/health").json(),
    "samples": samples,
    "passed": all(
        sample["seconds"] <= config["maximum_search_seconds"]
        and sample["peak_rss_mib"] <= config["maximum_peak_rss_mib"]
        and sample["host_available_mib"] >= config["minimum_host_available_mib"]
        for sample in samples
    ),
}
Path(sys.argv[2]).write_text(json.dumps(result, indent=2) + "\n")
print("PASSED", result["passed"], flush=True)
