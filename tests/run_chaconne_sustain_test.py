#!/usr/bin/env python3
"""Check upper-voice sustain through Chaconne bars 111 and 112."""

from __future__ import annotations

import argparse
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
DECAY_LIMIT_DB = 4.0
CHORD_BEATS = (329.0, 330.0, 331.0, 332.0)


def short_window(
    score: Path, performance: Path,
) -> tuple[str, list[tuple[tuple[float, float], tuple[float, float]]]]:
    bars, strokes = playback.parse_score(score)
    tempo = playback.parse_tempo(performance)
    start = playback.active_stroke(strokes, bars[110]).start
    end = bars[112] + 1.0
    text = playback.render_performance(score, tempo, start, bars[110])
    lines = []
    for line in text.splitlines():
        if line.startswith('i "BachAudible"'):
            fields = line.split()
            fields[3] = playback.format_number(end - bars[110])
            line = " ".join(fields)
        elif line.startswith('i "'):
            fields = line.split()
            if float(fields[2]) >= end - start - 1.0e-10:
                continue
        elif line.startswith("f 0 "):
            line = f"f 0 {playback.format_number(end - start)}"
        lines.append(line)
    origin = playback.seconds_at(start, tempo)
    windows = []
    for beat in CHORD_BEATS:
        # The upper bow plane starts up to 45% into these one-beat chords.
        early = playback.seconds_at(beat + 0.58, tempo) - origin
        early_end = playback.seconds_at(beat + 0.74, tempo) - origin
        late = playback.seconds_at(beat + 0.78, tempo) - origin
        late_end = playback.seconds_at(beat + 0.94, tempo) - origin
        windows.append(((early, early_end), (late, late_end)))
    return "\n".join(lines) + "\n", windows


def render(csound: Path, module: Path, csd: Path,
           include: Path, output: Path,
           extra_macros: tuple[str, ...] = ()) -> str:
    command = [
        str(csound), f"--opcode-lib={module}", "--sample-accurate",
        "--num-threads=1", "-W", "-3", "--nopeaks",
        f"--output={output}", f"--smacro:BACH_PERFORMANCE={include}",
        "--omacro:ROOM_LEVEL=0",
        *(f"--omacro:{macro}" for macro in extra_macros), str(csd),
    ]
    completed = subprocess.run(
        command, cwd=csd.parent, check=False, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, text=True, timeout=30)
    if completed.returncode != 0:
        raise ValueError(completed.stdout)
    return completed.stdout


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


def highpass(samples: list[float], cutoff: float = 700.0) -> list[float]:
    pole = math.exp(-2.0 * math.pi * cutoff / RATE)
    low = 0.0
    result = []
    for sample in samples:
        low = (1.0 - pole) * sample + pole * low
        result.append(sample - low)
    return result


def rms(samples: list[float], bounds: tuple[float, float]) -> float:
    first = round(bounds[0] * RATE)
    last = round(bounds[1] * RATE)
    values = samples[first:last]
    if not values:
        raise ValueError("an analysis window is empty")
    return math.sqrt(sum(value * value for value in values) / len(values))


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
            raise ValueError("a Chaconne sustain input is missing")
        with tempfile.TemporaryDirectory(
                prefix="hlolli-bach-sustain-") as folder:
            root = Path(folder)
            include = root / "window.inc"
            text, windows = short_window(
                options.score.resolve(), options.performance.resolve())
            include.write_text(text, encoding="utf-8")
            output = root / "window.wav"
            render(options.csound.resolve(), options.module.resolve(),
                   options.csd.resolve(), include, output)
            samples = highpass(read_mono(output))
            decays = []
            for early, late in windows:
                early_rms = rms(samples, early)
                late_rms = rms(samples, late)
                decays.append(20.0 * math.log10(early_rms / late_rms))
        worst = max(decays)
        mean = sum(decays) / len(decays)
        print("upper decay by beat: " +
              ", ".join(f"{value:.2f} dB" for value in decays))
        print(f"mean upper decay {mean:.2f} dB; worst {worst:.2f} dB")
        if worst > DECAY_LIMIT_DB:
            print(f"FAIL: upper voice loses more than {DECAY_LIMIT_DB:.2f} dB "
                  "inside one bowed beat")
            return 1
        print("Chaconne bars 111-112 upper sustain passed")
        return 0
    except (OSError, ValueError, subprocess.TimeoutExpired,
            wave.Error) as error:
        print(f"run_chaconne_sustain_test.py: {error}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
