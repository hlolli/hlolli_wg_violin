#!/usr/bin/env python3
"""Measure fixed bowed-string workloads without setting a speed gate."""

from __future__ import annotations

import argparse
import platform
import statistics
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, NamedTuple, Sequence

try:
    import resource
except ImportError:  # pragma: no cover - resource exists on supported CI hosts.
    resource = None  # type: ignore[assignment]


class Case(NamedTuple):
    name: str
    number: int
    voices: int


class Timing(NamedTuple):
    cpu_seconds: float
    wall_seconds: float


CASES = (
    Case("silence", 0, 0),
    Case("one_string", 1, 1),
    Case("four_strings_one_handle", 2, 4),
    Case("four_strings_four_handles", 3, 4),
)


def child_cpu() -> float | None:
    if resource is None:
        return None
    usage = resource.getrusage(resource.RUSAGE_CHILDREN)
    return usage.ru_utime + usage.ru_stime


def run_once(
    csound: Path, module: Path, csd: Path, case: Case, seconds: float,
) -> Timing:
    command = [
        str(csound),
        "--opcode-lib={}".format(module),
        "--sample-accurate",
        "--num-threads=1",
        "--omacro:BENCH_CASE={}".format(case.number),
        "--omacro:BENCH_SECONDS={:.9g}".format(seconds),
        "-n",
        "-d",
        "-m128",
        str(csd),
    ]
    cpu_start = child_cpu()
    wall_start = time.perf_counter()
    completed = subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        timeout=max(60.0, 10.0 * seconds),
        check=False,
    )
    wall_elapsed = time.perf_counter() - wall_start
    cpu_stop = child_cpu()
    if completed.returncode != 0:
        raise RuntimeError(
            "{} failed for {}:\n{}".format(
                module, case.name, completed.stdout.rstrip()))
    cpu_elapsed = (cpu_stop - cpu_start
                   if cpu_start is not None and cpu_stop is not None
                   else wall_elapsed)
    return Timing(cpu_elapsed, wall_elapsed)


def measure(
    csound: Path,
    module: Path,
    csd: Path,
    seconds: float,
    repeats: int,
) -> Dict[str, Timing]:
    results: Dict[str, Timing] = {}
    for case in CASES:
        run_once(csound, module, csd, case, min(seconds, 2.0))
        samples = [
            run_once(csound, module, csd, case, seconds)
            for _ in range(repeats)
        ]
        results[case.name] = Timing(
            statistics.median(item.cpu_seconds for item in samples),
            statistics.median(item.wall_seconds for item in samples),
        )
    return results


def incremental_per_voice(
    results: Dict[str, Timing], case: Case, seconds: float,
) -> float:
    if case.voices == 0:
        return 0.0
    added = max(
        0.0,
        results[case.name].cpu_seconds - results["silence"].cpu_seconds,
    )
    return added / (seconds * case.voices)


def print_results(
    title: str, results: Dict[str, Timing], seconds: float,
) -> None:
    print(title)
    print("case                          cpu_s    wall_s  cpu/render  per_voice")
    for case in CASES:
        timing = results[case.name]
        print(
            "{:<28} {:>8.4f} {:>9.4f} {:>11.6f} {:>10.6f}".format(
                case.name,
                timing.cpu_seconds,
                timing.wall_seconds,
                timing.cpu_seconds / seconds,
                incremental_per_voice(results, case, seconds),
            )
        )


def print_comparison(
    current: Dict[str, Timing], baseline: Dict[str, Timing], seconds: float,
) -> None:
    print("old-vs-new incremental bowed cost")
    print("case                            old        new      change")
    for case in CASES[1:]:
        old = incremental_per_voice(baseline, case, seconds)
        new = incremental_per_voice(current, case, seconds)
        change = 100.0 * (new / old - 1.0) if old > 0.0 else float("nan")
        print("{:<28} {:>10.6f} {:>10.6f} {:>9.2f}%".format(
            case.name, old, new, change))


def positive_float(text: str) -> float:
    value = float(text)
    if value <= 0.0:
        raise argparse.ArgumentTypeError("must be greater than zero")
    return value


def positive_int(text: str) -> int:
    value = int(text)
    if value < 1:
        raise argparse.ArgumentTypeError("must be at least one")
    return value


def main(arguments: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csound", required=True, type=Path)
    parser.add_argument("--module", required=True, type=Path)
    parser.add_argument("--csd", required=True, type=Path)
    parser.add_argument("--baseline-module", type=Path)
    parser.add_argument("--seconds", type=positive_float, default=20.0)
    parser.add_argument("--repeats", type=positive_int, default=3)
    options = parser.parse_args(arguments)

    for path, label in (
            (options.csound, "Csound"), (options.module, "module"),
            (options.csd, "CSD")):
        if not path.exists():
            parser.error("{} does not exist: {}".format(label, path))
    if options.baseline_module is not None and not options.baseline_module.exists():
        parser.error(
            "baseline module does not exist: {}".format(
                options.baseline_module))

    print("host: {}".format(platform.platform()))
    print("audio seconds per case: {:.9g}; median of {} runs after warmup".format(
        options.seconds, options.repeats))
    try:
        current = measure(
            options.csound, options.module, options.csd,
            options.seconds, options.repeats)
        print_results("current module", current, options.seconds)
        if options.baseline_module is not None:
            baseline = measure(
                options.csound, options.baseline_module, options.csd,
                options.seconds, options.repeats)
            print_results("baseline module", baseline, options.seconds)
            print_comparison(current, baseline, options.seconds)
    except (OSError, RuntimeError, subprocess.TimeoutExpired) as error:
        print("benchmark failed: {}".format(error), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
