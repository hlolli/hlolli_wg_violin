#!/usr/bin/env python3
"""Check physical contact through the opening dotted-note bow change."""

from __future__ import annotations

import argparse
import math
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import wave

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import run_chaconne_sustain_test as common
import play_bach_chaconne as playback


ENTRY_LIMIT_DB = 1.5
BLOCK_SECONDS = 32 / common.RATE
CONTROL_LINE = re.compile(
    r"BACH_DOTTED_CONTACT\s+([-+0-9.eE]+)\s+([-+0-9.eE]+)\s+"
    r"([-+0-9.eE]+)\s+([-+0-9.eE]+)"
)


def verify_opening_pair(score: Path) -> None:
    notes = []
    for line in score.read_text(encoding="ascii").splitlines():
        if line.startswith('i "BachNote"'):
            fields = line.split()
            notes.append((float(fields[2]), float(fields[3]),
                          int(fields[4]), int(fields[5]), int(fields[17])))
    expected = ((0.0, 1.5, 69, 3, 0), (1.5, 0.5, 69, 3, 1))
    if len(notes) < 4 or (notes[2], notes[3]) != expected:
        raise ValueError("the opening dotted-note contact case changed")


def short_window(
    score: Path, performance: Path,
) -> tuple[str, tuple[float, float], tuple[float, float], tuple[float, float]]:
    bars, strokes = playback.parse_score(score)
    tempo = playback.parse_tempo(performance)
    start = playback.active_stroke(strokes, bars[1]).start
    end = bars[2]
    text = playback.render_performance(score, tempo, start, bars[1])
    lines = []
    for line in text.splitlines():
        fields = line.split()
        if line.startswith('i "BachAudible"'):
            fields[3] = playback.format_number(end - bars[1])
            line = " ".join(fields)
        elif line.startswith('i "'):
            if float(fields[2]) >= end - start - 1.0e-10:
                continue
        elif line.startswith("f 0 "):
            line = f"f 0 {playback.format_number(end - start)}"
        lines.append(line)
    origin = playback.seconds_at(start, tempo)

    def bounds(first: float, last: float) -> tuple[float, float]:
        return (playback.seconds_at(first, tempo) - origin,
                playback.seconds_at(last, tempo) - origin)

    return ("\n".join(lines) + "\n", bounds(1.25, 1.45),
            bounds(1.50, 1.60), bounds(1.80, 1.98))


def trace_score(source: Path, destination: Path) -> None:
    text = re.sub(r'#include "([^"]+)"',
                  lambda match: f'#include "{(source.parent / match[1]).as_posix()}"',
                  source.read_text(encoding="utf-8"))
    voice = "  aLeft, aRight hlolli_wg_violin "
    if text.count(voice) != 1:
        raise ValueError("cannot locate the Chaconne string controller")
    trace = """  if iString == 3 && gkDottedShort[iString] != 0 then
    printks "BACH_DOTTED_CONTACT %.17g %.17g %.17g %.17g\\n", \\
        ksmps / sr, timeinsts(), kStrokeTrigger, kForce, kSpeed
  endif
"""
    destination.write_text(text.replace(voice, trace + voice),
                           encoding="utf-8")


def check_controls(log: str, start: float, end: float) -> None:
    rows = [tuple(map(float, match.groups()))
            for match in CONTROL_LINE.finditer(log)]
    rows = [row for row in rows
            if start + 3 * BLOCK_SECONDS <= row[0] <= end]
    if (not rows or rows[0][0] > start + 5 * BLOCK_SECONDS
            or rows[-1][0] < end - 2 * BLOCK_SECONDS
            or any(later[0] - earlier[0] > 1.5 * BLOCK_SECONDS
                   for earlier, later in zip(rows, rows[1:]))):
        raise ValueError("the dotted-short control trace is incomplete")
    if any(gate <= 0 or force <= 0 or speed == 0
           for _, gate, force, speed in rows):
        raise ValueError("the dotted short loses bow contact")
    for index, control in enumerate(("contact", "force", "speed"), 1):
        values = [row[index] for row in rows]
        if max(values) - min(values) > 1e-8:
            raise ValueError(f"the dotted short changes its commanded {control}")


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
            raise ValueError("a Chaconne contact input is missing")
        verify_opening_pair(options.score.resolve())
        with tempfile.TemporaryDirectory(
                prefix="hlolli-bach-contact-") as folder:
            root = Path(folder)
            include = root / "window.inc"
            text, before, entry, late = short_window(
                options.score.resolve(), options.performance.resolve())
            include.write_text(text, encoding="utf-8")
            output = root / "window.wav"
            csd = root / "contact.csd"
            trace_score(options.csd.resolve(), csd)
            log = common.render(
                options.csound.resolve(), options.module.resolve(),
                csd, include, output, ("BODY_LEVEL=0",))
            check_controls(log, entry[0], late[1])
            samples = common.read_mono(output)
            before_rms = common.rms(samples, before)
            entry_rms = common.rms(samples, entry)
            late_rms = common.rms(samples, late)
        entry_deficit = 20.0 * math.log10(before_rms / entry_rms)
        # The rail can settle after the bow change even with flat commands.
        swell = 20.0 * math.log10(late_rms / entry_rms)
        print(f"dotted-short entry deficit {entry_deficit:.2f} dB")
        print(f"dotted-short internal swell {swell:.2f} dB")
        failures = []
        if entry_deficit > ENTRY_LIMIT_DB:
            failures.append("the short note loses contact at its onset")
        if failures:
            for failure in failures:
                print(f"FAIL: {failure}")
            return 1
        print("Chaconne opening contact continuity passed")
        return 0
    except (OSError, ValueError, subprocess.TimeoutExpired,
            wave.Error) as error:
        print(f"run_chaconne_contact_test.py: {error}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
