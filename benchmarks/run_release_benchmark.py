#!/usr/bin/env python3
"""Measure and compare the fixed release workloads."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
from pathlib import Path
import statistics
import subprocess
import sys
import time

try:
    import resource
except ImportError:  # pragma: no cover
    resource = None  # type: ignore[assignment]


CASES = (
    ("silence", 0, 0),
    ("closed_stopped", 1, 1),
    ("open_string", 2, 1),
    ("double_stop", 3, 2),
    ("section_eight_players", 4, 8),
)


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def csound_version(csound: Path) -> str:
    completed = subprocess.run(
        [str(csound), "--version"],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        timeout=30.0,
    )
    if completed.returncode != 0:
        raise RuntimeError(completed.stdout)
    return completed.stdout.strip()


def child_cpu() -> float | None:
    if resource is None:
        return None
    usage = resource.getrusage(resource.RUSAGE_CHILDREN)
    return usage.ru_utime + usage.ru_stime


def run_once(
    csound: Path, module: Path, csd: Path, case: int, seconds: float
) -> float:
    command = [
        str(csound),
        f"--opcode-lib={module}",
        "--sample-accurate",
        "--num-threads=1",
        f"--omacro:BENCH_CASE={case}",
        f"--omacro:BENCH_SECONDS={seconds:.9g}",
        "-n",
        "-d",
        "-m128",
        str(csd),
    ]
    before = child_cpu()
    wall_before = time.perf_counter()
    completed = subprocess.run(
        command,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        timeout=max(90.0, seconds * 15.0),
    )
    wall_elapsed = time.perf_counter() - wall_before
    after = child_cpu()
    if completed.returncode != 0:
        raise RuntimeError(completed.stdout)
    return after - before if before is not None and after is not None else wall_elapsed


def benchmark(
    csound: Path,
    module: Path,
    csd: Path,
    seconds: float,
    repeats: int,
) -> dict[str, object]:
    rows: list[dict[str, object]] = []
    raw: dict[str, list[float]] = {}
    for name, case, voices in CASES:
        run_once(csound, module, csd, case, min(1.0, seconds))
        samples = [
            run_once(csound, module, csd, case, seconds)
            for _ in range(repeats)
        ]
        raw[name] = samples
    silence = statistics.median(raw["silence"])
    for name, _, voices in CASES:
        samples = raw[name]
        median = statistics.median(samples)
        added = max(0.0, median - silence)
        rows.append(
            {
                "name": name,
                "voices": voices,
                "cpu_seconds": samples,
                "median_cpu_seconds": median,
                "cpu_per_rendered_second": added / seconds,
                "cpu_per_voice_rendered_second": (
                    added / (seconds * voices) if voices else 0.0
                ),
            }
        )
    return {
        "schema_version": 1,
        "host": platform.platform(),
        "python": platform.python_version(),
        "csound_version": csound_version(csound),
        "csound_sha256": file_hash(csound),
        "module_sha256": file_hash(module),
        "audio_seconds": seconds,
        "repeats": repeats,
        "cases": rows,
    }


def compare(current: dict[str, object], baseline: dict[str, object]) -> None:
    for field in (
        "schema_version",
        "host",
        "csound_version",
        "csound_sha256",
        "audio_seconds",
        "repeats",
    ):
        if current.get(field) != baseline.get(field):
            raise ValueError(f"baseline {field} does not match this run")
    old_rows = {
        row["name"]: row
        for row in baseline.get("cases", [])  # type: ignore[union-attr]
    }
    current_names = {row["name"] for row in current["cases"]}  # type: ignore[index]
    if current_names != set(old_rows):
        raise ValueError("baseline case set does not match this run")
    for row in current["cases"]:  # type: ignore[index]
        if row["name"] == "silence":
            continue
        old = old_rows.get(row["name"])
        if old is None:
            raise ValueError(f"baseline lacks case: {row['name']}")
        old_cost = float(old["cpu_per_rendered_second"])
        new_cost = float(row["cpu_per_rendered_second"])
        if old_cost <= 0.0:
            raise ValueError(f"baseline cost is not positive: {row['name']}")
        ratio = new_cost / old_cost
        print(f"{row['name']}: ratio={ratio:.4f}")
        if ratio > 1.20:
            raise ValueError(f"performance rose by more than 20%: {row['name']}")


def self_test() -> None:
    facts: dict[str, object] = {
        "schema_version": 1,
        "host": "test-host",
        "csound_version": "test-csound",
        "csound_sha256": "0" * 64,
        "audio_seconds": 10.0,
        "repeats": 7,
        "cases": [
            {
                "name": "silence",
                "cpu_per_rendered_second": 0.0,
            },
            {
                "name": "closed_stopped",
                "cpu_per_rendered_second": 1.0,
            },
        ],
    }
    baseline = json.loads(json.dumps(facts))
    compare(facts, baseline)
    facts["cases"][1]["cpu_per_rendered_second"] = 1.21  # type: ignore[index]
    try:
        compare(facts, baseline)
    except ValueError:
        return
    raise ValueError("comparison accepted a performance rise above 20 percent")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csound", type=Path)
    parser.add_argument("--module", type=Path)
    parser.add_argument("--csd", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--baseline", type=Path)
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--seconds", type=float, default=10.0)
    parser.add_argument("--repeats", type=int, default=7)
    options = parser.parse_args()
    if options.self_test:
        try:
            self_test()
        except ValueError as error:
            print(f"release benchmark self-test failed: {error}", file=sys.stderr)
            return 1
        print("PASS release benchmark comparison self-test")
        return 0
    if options.csound is None or options.module is None or options.csd is None:
        parser.error("--csound, --module, and --csd are required")
    if options.seconds <= 0 or options.repeats < 1:
        parser.error("seconds and repeats must be positive")
    for path in (options.csound, options.module, options.csd):
        if not path.is_file():
            parser.error(f"missing regular file: {path}")
    try:
        result = benchmark(
            options.csound,
            options.module,
            options.csd,
            options.seconds,
            options.repeats,
        )
        print(json.dumps(result, indent=2, sort_keys=True))
        if options.baseline is not None:
            compare(result, json.loads(options.baseline.read_text("utf-8")))
        if options.output is not None:
            options.output.write_text(
                json.dumps(result, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
    except (OSError, RuntimeError, ValueError, subprocess.TimeoutExpired) as error:
        print(f"release benchmark failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
