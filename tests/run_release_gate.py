#!/usr/bin/env python3
"""Run the native sample-rate, block-size, load, and worker gate."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import wave


SCENARIOS = (
    ("long-48k-k32", 1, 48000, 32, 12.0, 1),
    ("dense-control-44k-k1", 2, 44100, 1, 1.5, 1),
    ("dense-control-96k-k64", 2, 96000, 64, 1.5, 1),
    ("four-strings", 3, 48000, 16, 2.0, 1),
    ("eight-handles", 4, 48000, 32, 1.5, 1),
    ("eight-handles-worker", 4, 48000, 32, 1.5, 2),
)


def render(
    csound: Path,
    module: Path,
    csd: Path,
    output: Path,
    case: int,
    sample_rate: int,
    ksmps: int,
    seconds: float,
    threads: int,
) -> str:
    command = [
        str(csound),
        f"--opcode-lib={module}",
        "--sample-accurate",
        f"--num-threads={threads}",
        f"--omacro:TEST_CASE={case}",
        f"--omacro:TEST_SR={sample_rate}",
        f"--omacro:TEST_KSMPS={ksmps}",
        f"--omacro:TEST_SECONDS={seconds:.9g}",
        "-W",
        "-s",
        "--nopeaks",
        "-d",
        "-m128",
        "-o",
        str(output),
        str(csd),
    ]
    completed = subprocess.run(
        command,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        timeout=max(90.0, seconds * 12.0),
    )
    if completed.returncode != 0:
        raise RuntimeError(completed.stdout)
    return completed.stdout


def check_wave(path: Path, sample_rate: int, seconds: float) -> tuple[int, str]:
    with wave.open(str(path), "rb") as stream:
        if stream.getnchannels() != 2 or stream.getsampwidth() != 2:
            raise RuntimeError(f"wrong WAVE shape: {path}")
        if stream.getframerate() != sample_rate:
            raise RuntimeError(f"wrong WAVE rate: {path}")
        frame_count = stream.getnframes()
        data = stream.readframes(frame_count)
    minimum_frames = int(sample_rate * seconds * 0.98)
    if frame_count < minimum_frames:
        raise RuntimeError(f"short WAVE render: {path}")
    samples = struct.iter_unpack("<h", data)
    peak = 0
    nonzero = 0
    for (sample,) in samples:
        peak = max(peak, abs(sample))
        nonzero += sample != 0
    if peak < 8 or nonzero < sample_rate // 20:
        raise RuntimeError(f"silent WAVE render: {path}")
    if peak >= 32767:
        raise RuntimeError(f"bounded output clipped: {path}")
    return peak, hashlib.sha256(data).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csound", required=True, type=Path)
    parser.add_argument("--module", required=True, type=Path)
    parser.add_argument("--prepared-module", type=Path)
    parser.add_argument("--csd", required=True, type=Path)
    options = parser.parse_args()
    required = [options.csound, options.module, options.csd]
    if options.prepared_module is not None:
        required.append(options.prepared_module)
    for path in required:
        if not path.is_file():
            parser.error(f"missing regular file: {path}")

    try:
        with tempfile.TemporaryDirectory(prefix="hlolli-release-") as folder:
            root = Path(folder)
            canonical_digest = ""
            for name, case, rate, ksmps, seconds, threads in SCENARIOS:
                path = root / f"{name}.wav"
                render(
                    options.csound,
                    options.module,
                    options.csd,
                    path,
                    case,
                    rate,
                    ksmps,
                    seconds,
                    threads,
                )
                peak, digest = check_wave(path, rate, seconds)
                print(
                    f"PASS {name}: sr={rate} ksmps={ksmps} "
                    f"threads={threads} peak={peak} sha256={digest}"
                )
                if name == "long-48k-k32":
                    canonical_digest = digest
            if options.prepared_module is not None:
                path = root / "prepared-source.wav"
                render(
                    options.csound,
                    options.prepared_module,
                    options.csd,
                    path,
                    1,
                    48000,
                    32,
                    12.0,
                    1,
                )
                _, digest = check_wave(path, 48000, 12.0)
                if digest != canonical_digest:
                    raise RuntimeError(
                        "prepared WASM source changed the production signal"
                    )
                print("PASS prepared source: native signal is byte exact")
    except (OSError, RuntimeError, subprocess.TimeoutExpired, wave.Error) as error:
        print(f"release gate failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
