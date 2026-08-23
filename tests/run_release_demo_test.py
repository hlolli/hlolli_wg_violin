#!/usr/bin/env python3
"""Render the public demos and check their public audio shape."""

from __future__ import annotations

import argparse
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import wave


DEMOS = (
    ("solo", "solo_techniques.csd", 16.0),
    ("section", "string_section.csd", 12.0),
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csound", required=True, type=Path)
    parser.add_argument("--module", required=True, type=Path)
    parser.add_argument("--examples", required=True, type=Path)
    options = parser.parse_args()
    try:
        with tempfile.TemporaryDirectory(prefix="hlolli-release-demos-") as folder:
            for name, filename, minimum_seconds in DEMOS:
                source = options.examples / filename
                output = Path(folder) / f"{name}.wav"
                command = [
                    str(options.csound),
                    f"--opcode-lib={options.module}",
                    "--sample-accurate",
                    "--num-threads=1",
                    "-W",
                    "-s",
                    "--nopeaks",
                    "-d",
                    "-m128",
                    "-o",
                    str(output),
                    str(source),
                ]
                completed = subprocess.run(
                    command,
                    check=False,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    timeout=120,
                )
                if completed.returncode != 0:
                    raise RuntimeError(completed.stdout)
                with wave.open(str(output), "rb") as stream:
                    if (
                        stream.getframerate() != 48000
                        or stream.getnchannels() != 2
                        or stream.getsampwidth() != 2
                    ):
                        raise RuntimeError(f"wrong WAVE shape: {name}")
                    frames = stream.getnframes()
                    data = stream.readframes(frames)
                if frames < int(minimum_seconds * 48000):
                    raise RuntimeError(f"short demo: {name}")
                peak = max(abs(value[0]) for value in struct.iter_unpack("<h", data))
                if peak < 32 or peak >= 32767:
                    raise RuntimeError(f"silent or clipped demo: {name}")
                print(f"PASS {name}: frames={frames} peak={peak}")
    except (OSError, RuntimeError, subprocess.TimeoutExpired, wave.Error) as error:
        print(f"release demo test failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
