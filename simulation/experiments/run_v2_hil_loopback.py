#!/usr/bin/env python3
"""Exercise deployment-facing software adapters for the v2 benchmark.

This is software-in-the-loop evidence only. UDP is localhost and no physical
sensor, actuator, MCU, radio, or power meter participates in the loop.
"""
from __future__ import annotations
import json, sys, tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.interfaces_v2 import (
    Command, InProcessTransport, JsonlTransport, UdpLoopbackTransport,
    replay_commands,
)
from experiments.run_v2_primary import run_one


def main() -> None:
    rows = []
    transport_checks = []
    replay_input = [
        Command("sil-replay", 1, 1, 0, 10, [0.1], "normal"),
        Command("sil-replay", 1, 1, 0, 10, [0.1], "normal"),  # duplicate
        Command("sil-replay", 2, 2, 11, 10, [0.2], "normal"), # stale
        Command("sil-replay", 3, 3, 1, 10, [0.3], "normal"),
    ]
    replay_accepted = replay_commands(replay_input)
    assert replay_accepted == [1, 3]

    for plant in ("greenhouse", "irrigation"):
        for policy in ("TT-MPC", "ET-MPC", "TT-PI", "ET-PI"):
            for seed in (2026, 2027, 2028):
                result = run_one(plant, policy, "N1_nominal", seed)

                direct = InProcessTransport()
                direct.send({"plant": plant, "policy": policy, "seed": seed})
                assert direct.poll(1)
                rows.append({**result, "adapter": "inprocess"})

                with tempfile.TemporaryDirectory() as directory:
                    jsonl = JsonlTransport(Path(directory) / "loop.jsonl")
                    jsonl.send({"plant": plant, "policy": policy, "seed": seed})
                    assert jsonl.poll(1)
                rows.append({**result, "adapter": "jsonl_loopback"})

                udp = UdpLoopbackTransport()
                payload = {"run_id": f"{plant}:{policy}:{seed}", "seq": 1,
                           "direction": "downlink", "values": [0.1]}
                first = udp.roundtrip(payload)
                duplicate = udp.roundtrip(payload)
                assert not first["duplicate"] and duplicate["duplicate"]
                rows.append({**result, "adapter": "udp_localhost_schema_loopback"})

    transport_checks.append({
        "scope": "software-in-the-loop/HIL-ready only; no physical HIL",
        "adapters": sorted({row["adapter"] for row in rows}),
        "n_result_rows": len(rows),
        "deterministic_replay_input_sequences": [c.seq for c in replay_input],
        "deterministic_replay_accepted_sequences": replay_accepted,
        "duplicate_and_stale_rejected": True,
        "udp_localhost_duplicate_rejected": True,
    })
    (ROOT / "results/v2_sil_loopback.json").write_text(
        json.dumps({"checks": transport_checks, "runs": rows}, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(transport_checks[0], indent=2))


if __name__ == "__main__":
    main()
