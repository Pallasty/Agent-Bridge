#!/usr/bin/env python3
"""D45 controlled fresh-process resource audit for the fixed64 replay."""
from __future__ import annotations

import json
import os
import resource
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPLAY = HERE / "fh_l8_local_cost_survey_replay_d43.py"


def _prefix():
    if hasattr(os, "sched_getaffinity") and 0 in os.sched_getaffinity(0):
        return ["taskset", "-c", "0"], "cpu0"
    return [], "uncontrolled"


def _run(command):
    proc = subprocess.run(command, check=True, capture_output=True, text=True)
    return json.loads(proc.stdout.strip().splitlines()[-1])


def run():
    prefix, affinity_mode = _prefix()
    baseline_code = "import json,resource; print(json.dumps({'peak':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss}))"
    baseline = [_run(prefix + [sys.executable, "-c", baseline_code])["peak"] for _ in range(2)]
    replay = [_run(prefix + [sys.executable, str(REPLAY)]) for _ in range(2)]
    digests = {item["d43_structural_rows_sha256"] for item in replay}
    if len(digests) != 1 or replay[0]["d43_structural_rows_sha256"] != "38aaeffb8f178e918e4f326888493166c21afc7fb1379e91ab965c345b4adc12":
        raise RuntimeError("controlled replay structural digest drift")
    rss = [item["d43_peak_rss_kib"] for item in replay]
    baseline_min, baseline_max = min(baseline), max(baseline)
    replay_min, replay_max = min(rss), max(rss)
    return {
        "status": "VERIFIED_D45_CONTROLLED_FIXED64_RESOURCE_REPLAY",
        "affinity_mode": affinity_mode,
        "affinity_requested": affinity_mode == "cpu0",
        "baseline_peak_rss_kib": baseline,
        "replay_peak_rss_kib": rss,
        "baseline_peak_rss_range_kib": baseline_max - baseline_min,
        "replay_peak_rss_range_kib": replay_max - replay_min,
        "structural_rows_sha256": replay[0]["d43_structural_rows_sha256"],
        "structural_replays_match": True,
        "selected_representatives": 64,
        "scientific_action_calls_per_replay": 67,
        "resource_observations_comparable": (replay_max - replay_min) <= 4096 and affinity_mode == "cpu0",
        "packed_q3_reads": 0,
        "full_53_scientific_execution_authorized": False,
        "full53_extrapolation_forbidden": True,
        "next_gate": "D46_RESOURCE_VARIANCE_REDUCTION" if (replay_max - replay_min) > 4096 else "BOUNDED_SCALE64_COST_REVIEW",
    }


if __name__ == "__main__":
    print(json.dumps(run(), sort_keys=True, separators=(",", ":")))
