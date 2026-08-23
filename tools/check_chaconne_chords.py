#!/usr/bin/env python3
"""Compare the opening Chaconne chord balance with a private recording."""

from __future__ import annotations

import argparse
import cmath
import math
from pathlib import Path
import subprocess
import tempfile
import wave

import check_chaconne_contact as opening
import check_chaconne_sustain as common


RATE = 48000
PITCHES = (("D4", 293.6647679174076),
           ("F4", 349.2282314330039),
           ("A4", 440.0))
ANALYSIS_SECONDS = 0.28
MAX_DEFICIT_DB = 5.0


def read_mono(path: Path) -> list[float]:
    with wave.open(str(path), "rb") as stream:
        if (stream.getnchannels(), stream.getframerate()) != (2, RATE):
            raise ValueError(f"wrong WAVE shape: {path}")
        width = stream.getsampwidth()
        data = stream.readframes(stream.getnframes())
    if width not in (2, 3):
        raise ValueError(f"unsupported WAVE depth: {path}")
    scale = float(1 << (8 * width - 1))
    frame_bytes = 2 * width
    samples = []
    for offset in range(0, len(data), frame_bytes):
        left = int.from_bytes(
            data[offset:offset + width], "little", signed=True)
        right = int.from_bytes(
            data[offset + width:offset + frame_bytes], "little", signed=True)
        samples.append((left + right) / (2.0 * scale))
    return samples


def onset(samples: list[float], label: str) -> int:
    width = round(0.010 * RATE)
    search = samples[:min(len(samples), 15 * RATE)]
    levels = []
    for first in range(0, len(search) - width + 1, width):
        values = search[first:first + width]
        levels.append(math.sqrt(
            sum(value * value for value in values) / len(values)))
    if len(levels) < 50:
        raise ValueError("recording is too short for onset detection")
    threshold = max(1.0e-6, max(levels) * 0.05)
    for index in range(len(levels) - 3):
        if sum(level > threshold for level in levels[index:index + 4]) >= 3:
            return index * width
    raise ValueError(
        f"could not find the first chord in {label}; "
        f"peak window RMS was {max(levels):.9f}")


def tone_power(samples: list[float], first: int, frequency: float) -> float:
    size = round(ANALYSIS_SECONDS * RATE)
    values = samples[first:first + size]
    if len(values) != size:
        raise ValueError("opening chord analysis is incomplete")
    powers = []
    for offset in (-4.0, 0.0, 4.0):
        step = cmath.exp(-2j * math.pi * (frequency + offset) / RATE)
        phase = 1 + 0j
        total = 0j
        for index, value in enumerate(values):
            window = 0.5 - 0.5 * math.cos(
                2.0 * math.pi * index / (size - 1))
            total += value * window * phase
            phase *= step
        powers.append(abs(total) ** 2)
    return sum(powers)


def pitch_entries(samples: list[float], first: int) -> dict[str, float]:
    window_size = round(0.080 * RATE)
    step_size = round(0.005 * RATE)
    count = round(0.750 * RATE)
    entries = {}
    for name, frequency in PITCHES:
        values = []
        for offset in range(0, count - window_size + 1, step_size):
            phase = 1 + 0j
            step = cmath.exp(-2j * math.pi * frequency / RATE)
            total = 0j
            section = samples[first + offset:first + offset + window_size]
            if len(section) != window_size:
                raise ValueError("pitch-entry analysis is incomplete")
            for index, value in enumerate(section):
                window = 0.5 - 0.5 * math.cos(
                    2.0 * math.pi * index / (window_size - 1))
                total += value * window * phase
                phase *= step
            values.append(abs(total))
        threshold = max(values) * 0.15
        entry = next((index for index, value in enumerate(values)
                      if value >= threshold), None)
        if entry is None:
            raise ValueError(f"could not find {name} in the opening chord")
        entries[name] = entry * step_size / RATE
    return entries


def balance(samples: list[float], label: str) -> tuple[int, dict[str, float]]:
    first = onset(samples, label)
    powers = {name: tone_power(samples, first, frequency)
              for name, frequency in PITCHES}
    top = max(powers["A4"], 1.0e-30)
    return first, {
        name: 10.0 * math.log10(max(power, 1.0e-30) / top)
        for name, power in powers.items()
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csound", required=True, type=Path)
    parser.add_argument("--module", required=True, type=Path)
    parser.add_argument("--csd", required=True, type=Path)
    parser.add_argument("--score", required=True, type=Path)
    parser.add_argument("--performance", required=True, type=Path)
    parser.add_argument("--reference", required=True, type=Path)
    options = parser.parse_args()
    try:
        paths = (options.csound, options.module, options.csd, options.score,
                 options.performance, options.reference)
        if any(not path.resolve().is_file() for path in paths):
            raise ValueError("a Chaconne chord input is missing")
        with tempfile.TemporaryDirectory(
                prefix="hlolli-bach-chord-") as folder:
            root = Path(folder)
            include = root / "window.inc"
            text, _before, _entry, _late = opening.short_window(
                options.score.resolve(), options.performance.resolve())
            include.write_text(text, encoding="utf-8")
            output = root / "model.wav"
            common.render(
                options.csound.resolve(), options.module.resolve(),
                options.csd.resolve(), include, output)
            model_samples = read_mono(output)
            model_onset, model = balance(model_samples, "model")
            model_entries = pitch_entries(model_samples, model_onset)
        reference_samples = read_mono(options.reference.resolve())
        reference_onset, reference = balance(reference_samples, "reference")
        reference_entries = pitch_entries(reference_samples, reference_onset)
        print(f"model onset {model_onset / RATE:.3f} s")
        print(f"reference onset {reference_onset / RATE:.3f} s")
        print("model entries " + ", ".join(
            f"{name} {model_entries[name] * 1000:.0f} ms"
            for name, _ in PITCHES))
        print("reference entries " + ", ".join(
            f"{name} {reference_entries[name] * 1000:.0f} ms"
            for name, _ in PITCHES))
        failures = []
        for name in ("D4", "F4"):
            deficit = reference[name] - model[name]
            print(f"{name}/A4 model {model[name]:.2f} dB; "
                  f"reference {reference[name]:.2f} dB; "
                  f"deficit {deficit:.2f} dB")
            if deficit > MAX_DEFICIT_DB:
                failures.append(
                    f"{name} is more than {MAX_DEFICIT_DB:.1f} dB too quiet")
        if failures:
            for failure in failures:
                print(f"FAIL: {failure}")
            return 1
        print("Chaconne opening chord balance passed")
        return 0
    except (OSError, ValueError, subprocess.TimeoutExpired,
            wave.Error) as error:
        print(f"check_chaconne_chords.py: {error}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
