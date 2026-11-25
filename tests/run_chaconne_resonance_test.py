#!/usr/bin/env python3
"""Check the body-mode build-up in Chaconne bars 89 and 90."""

from __future__ import annotations

import argparse
import cmath
import math
from pathlib import Path
import subprocess
import sys
import tempfile
import wave

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import play_bach_chaconne as playback


RATE = 48000
FFT_SIZE = 8192
# 665 Hz is close to the open E5 fundamental at 659.3 Hz.  With a fixed body
# level that musical partial dominates the local ratio, so it is not a body
# transfer check.  Keep the two separated modes as the regression targets.
MODE_LIMITS = ((1320.0, 24.0, 8.0), (3300.0, 60.0, 8.0))


def check_fixed_bus(csd: Path) -> None:
    source = csd.read_text(encoding="utf-8")
    if "giViolin, 0.78, $SYMPATHETIC_LEVEL, 0" not in source:
        raise ValueError("Chaconne body level is not fixed")
    if any(f"delay gaDry{channel}, ksmps / sr" not in source
           for channel in ("Left", "Right")):
        raise ValueError("Chaconne direct bus is not block delayed")


def short_window(score: Path, performance: Path) -> tuple[str, list[float]]:
    bars, strokes = playback.parse_score(score)
    tempo = playback.parse_tempo(performance)
    start = playback.active_stroke(strokes, bars[89]).start
    end = bars[91]
    text = playback.render_performance(score, tempo, start, bars[89])
    lines = []
    for line in text.splitlines():
        if line.startswith('i "BachAudible"'):
            fields = line.split()
            fields[3] = playback.format_number(end - bars[89])
            line = " ".join(fields)
        elif line.startswith('i "'):
            fields = line.split()
            if float(fields[2]) >= end - start - 1.0e-10:
                continue
        elif line.startswith("f 0 "):
            line = f"f 0 {playback.format_number(end - start)}"
        lines.append(line)
    centres = [
        playback.seconds_at(beat, tempo) - playback.seconds_at(start, tempo)
        for beat in (264.75, 265.5, 266.75, 267.5)
    ]
    return "\n".join(lines) + "\n", centres


def render(csound: Path, module: Path, csd: Path, include: Path,
           output: Path, body_only: bool) -> None:
    command = [
        str(csound), f"--opcode-lib={module}", "--sample-accurate",
        "--num-threads=1", "-W", "-3", "--nopeaks",
        f"--output={output}", f"--smacro:BACH_PERFORMANCE={include}",
        "--omacro:ROOM_LEVEL=0",
    ]
    if body_only:
        command.extend(("--omacro:DIRECT_LEVEL=0", "--omacro:BODY_LEVEL=1"))
    else:
        command.append("--omacro:BODY_LEVEL=0")
    command.append(str(csd))
    completed = subprocess.run(
        command, cwd=csd.parent, check=False, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, text=True, timeout=30)
    if completed.returncode != 0:
        raise ValueError(completed.stdout)


def read_mono(path: Path) -> list[float]:
    with wave.open(str(path), "rb") as stream:
        if (stream.getnchannels(), stream.getsampwidth(),
                stream.getframerate()) != (2, 3, RATE):
            raise ValueError(f"wrong WAVE shape: {path}")
        data = stream.readframes(stream.getnframes())
    samples = []
    for offset in range(0, len(data), 6):
        left = int.from_bytes(data[offset:offset + 3], "little", signed=True)
        right = int.from_bytes(
            data[offset + 3:offset + 6], "little", signed=True)
        samples.append((left + right) / 16777216.0)
    return samples


def fft(values: list[float]) -> list[complex]:
    size = len(values)
    bits = size.bit_length() - 1
    output = [0j] * size
    for index, value in enumerate(values):
        reverse = 0
        source = index
        for _ in range(bits):
            reverse = (reverse << 1) | (source & 1)
            source >>= 1
        output[reverse] = complex(value)
    width = 2
    while width <= size:
        step = cmath.exp(-2j * math.pi / width)
        half = width // 2
        for start in range(0, size, width):
            factor = 1 + 0j
            for index in range(half):
                even = output[start + index]
                odd = factor * output[start + index + half]
                output[start + index] = even + odd
                output[start + index + half] = even - odd
                factor *= step
        width *= 2
    return output


def spectrum(samples: list[float], centre: float) -> list[float]:
    first = round(centre * RATE) - FFT_SIZE // 2
    if first < 0 or first + FFT_SIZE > len(samples):
        raise ValueError("analysis window falls outside the render")
    values = []
    for index in range(FFT_SIZE):
        phase = index / (FFT_SIZE - 1)
        window = 0.5 - 0.5 * math.cos(2 * math.pi * phase)
        values.append(samples[first + index] * window)
    return [abs(value) ** 2 for value in fft(values)[:FFT_SIZE // 2 + 1]]


def mode_prominences(body: list[float], direct: list[float],
                     centres: list[float]) -> dict[float, float]:
    prominences = {target: -math.inf for target, _, _ in MODE_LIMITS}
    for centre in centres:
        body_power = spectrum(body, centre)
        direct_power = spectrum(direct, centre)
        for target, half_width, _ in MODE_LIMITS:
            first = math.ceil((target - half_width) * FFT_SIZE / RATE)
            last = math.floor((target + half_width) * FFT_SIZE / RATE)
            flank_first = math.ceil(
                (target - 3.0 * half_width) * FFT_SIZE / RATE)
            flank_last = math.floor(
                (target + 3.0 * half_width) * FFT_SIZE / RATE)
            core_ratio = (
                (sum(body_power[first:last + 1]) + 1.0e-30) /
                (sum(direct_power[first:last + 1]) + 1.0e-30))
            body_flanks = (sum(body_power[flank_first:first]) +
                           sum(body_power[last + 1:flank_last + 1]))
            direct_flanks = (sum(direct_power[flank_first:first]) +
                             sum(direct_power[last + 1:flank_last + 1]))
            flank_ratio = ((body_flanks + 1.0e-30) /
                           (direct_flanks + 1.0e-30))
            prominence = 10 * math.log10(core_ratio / flank_ratio)
            prominences[target] = max(prominences[target], prominence)
    return prominences


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csound", required=True, type=Path)
    parser.add_argument("--module", required=True, type=Path)
    parser.add_argument("--csd", required=True, type=Path)
    parser.add_argument("--score", required=True, type=Path)
    parser.add_argument("--performance", required=True, type=Path)
    options = parser.parse_args()
    try:
        paths = (options.csound, options.module, options.csd, options.score,
                 options.performance)
        if any(not path.resolve().is_file() for path in paths):
            raise ValueError("a Chaconne resonance input is missing")
        check_fixed_bus(options.csd.resolve())
        with tempfile.TemporaryDirectory(
                prefix="hlolli-bach-resonance-") as folder:
            root = Path(folder)
            include = root / "window.inc"
            text, centres = short_window(
                options.score.resolve(), options.performance.resolve())
            include.write_text(text, encoding="utf-8")
            direct_path = root / "direct.wav"
            body_path = root / "body.wav"
            render(options.csound.resolve(), options.module.resolve(),
                   options.csd.resolve(), include, direct_path, False)
            render(options.csound.resolve(), options.module.resolve(),
                   options.csd.resolve(), include, body_path, True)
            prominences = mode_prominences(
                read_mono(body_path), read_mono(direct_path), centres)
        failures = []
        for target, _, limit in MODE_LIMITS:
            value = prominences[target]
            print(f"body mode {target:.0f} Hz prominence {value:.2f} dB")
            if value > limit:
                failures.append(
                    f"{target:.0f} Hz body mode prominence exceeds "
                    f"{limit:.2f} dB")
        if failures:
            for failure in failures:
                print(f"FAIL: {failure}")
            return 1
        print("Chaconne bars 89-90 body resonance passed")
        return 0
    except (OSError, ValueError, subprocess.TimeoutExpired,
            wave.Error) as error:
        print(f"run_chaconne_resonance_test.py: {error}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
