#!/usr/bin/env python3
"""Check the reusable violin listener-distance Module."""

from __future__ import annotations

import argparse
import math
from pathlib import Path
import struct
import subprocess
import tempfile
import wave


RATE = 48000
CHANNELS = 4


def render(csound: Path, csd: Path, output: Path) -> bytes:
    completed = subprocess.run(
        [str(csound), "--sample-accurate", "--num-threads=1",
         "-W", "-s", "--nopeaks", "-d", "-m128",
         "-o", str(output), str(csd)],
        cwd=csd.parent, check=False, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, text=True, timeout=20)
    if completed.returncode != 0:
        raise RuntimeError(completed.stdout)
    with wave.open(str(output), "rb") as stream:
        if (stream.getframerate(), stream.getnchannels(),
                stream.getsampwidth()) != (RATE, CHANNELS, 2):
            raise RuntimeError("distance probe returned the wrong WAVE shape")
        return stream.readframes(stream.getnframes())


def channels(frames: bytes) -> tuple[list[float], ...]:
    result = tuple([] for _ in range(CHANNELS))
    for frame in struct.iter_unpack("<hhhh", frames):
        for channel, value in zip(result, frame):
            channel.append(value / 32768.0)
    return result


def first_nonzero(values: list[float]) -> int | None:
    return next((index for index, value in enumerate(values) if value), None)


def spectral_power(values: list[float], frequency: float) -> float:
    real = 0.0
    imaginary = 0.0
    for index, value in enumerate(values):
        phase = 2.0 * math.pi * frequency * index / RATE
        real += value * math.cos(phase)
        imaginary -= value * math.sin(phase)
    return real * real + imaginary * imaginary


def high_band_ratio(values: list[float]) -> float:
    low = sum(spectral_power(values, frequency)
              for frequency in (2000, 4000, 6000, 8000))
    high = sum(spectral_power(values, frequency)
               for frequency in (12000, 14000, 16000, 18000))
    return high / low if low else math.inf


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csound", required=True, type=Path)
    parser.add_argument("--csd", required=True, type=Path)
    options = parser.parse_args()
    failures = []
    try:
        with tempfile.TemporaryDirectory(
                prefix="hlolli-violin-distance-") as folder:
            root = Path(folder)
            first = render(options.csound.resolve(), options.csd.resolve(),
                           root / "first.wav")
            second = render(options.csound.resolve(), options.csd.resolve(),
                            root / "second.wav")
        if first != second:
            failures.append("distance PCM changed on repeat")
        near, far, near_room, far_room = channels(first)
        if near != near_room:
            failures.append("the 1 metre bypass changed its source")
        near_onset = first_nonzero(near)
        far_onset = first_nonzero(far_room)
        expected = round(3.0 * RATE / 343.0)
        if near_onset != 0:
            failures.append("the 1 metre source gained delay")
        if far_onset is None or abs(far_onset - expected) > 1:
            failures.append("the 4 metre source has wrong travel time")
        near_peak = max(map(abs, near), default=0.0)
        far_room_peak = max(map(abs, far_room), default=0.0)
        if near_peak == 0 or abs(far_room_peak / near_peak - 1.0) > 2.0e-4:
            failures.append("diffuse room energy changed with listener distance")
        if max(map(abs, far), default=0.0) >= far_room_peak:
            failures.append("distant direct sound did not lose extra level")
        near_high = high_band_ratio(near)
        far_high = high_band_ratio(far)
        if far_high >= 0.75 * near_high:
            failures.append(
                "distant direct sound did not lose high frequency: "
                f"{far_high:.6f} vs {near_high:.6f}")
    except (OSError, RuntimeError, subprocess.TimeoutExpired,
            wave.Error) as error:
        print(f"violin distance test failed: {error}")
        return 1
    if failures:
        for failure in failures:
            print(f"FAIL: {failure}")
        return 1
    print("violin listener distance passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
