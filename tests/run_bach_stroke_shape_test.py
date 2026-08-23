#!/usr/bin/env python3
"""Check the shared Bach bow-stroke control path."""

from __future__ import annotations

import argparse
import math
import re
import struct
import subprocess
import sys
import tempfile
import wave
from pathlib import Path


PHASES = tuple(index / 8 for index in range(9))
LINE = re.compile(
    r"BACH_STROKE\s+([-0-9.]+)\s+(\d+)\s+"
    r"([-+0-9.eE]+)\s+([-+0-9.eE]+)\s+([-+0-9.eE]+)"
)
PITCH_LINE = re.compile(
    r"BACH_PITCH\s+([-+0-9.eE]+)\s+"
    r"([-+0-9.eE]+)\s+([-+0-9.eE]+)"
)
CHORD_LINE = re.compile(
    r"BACH_CHORD\s+(\d+)\s+(\d+)\s+(\d+)\s+"
    r"([-+0-9.eE]+)\s+([-+0-9.eE]+)"
)


def expected(phase: float, chord_size: int) -> tuple[float, float, float]:
    phase = min(1.0, max(0.0, phase))
    shape = phase ** 3 * (10 + phase * (-15 + 6 * phase))
    shoulder = math.sin(math.pi * phase) ** 2
    if chord_size > 1:
        contact = 0.98 - 0.23 * shape + 0.05 * shoulder
        force = 1.10 - 0.15 * shape + 0.07 * shoulder
        speed = 1.05 - 0.08 * shape + 0.07 * shoulder
    else:
        contact = 1.00
        force = 1.00
        speed = 1.00
    return (
        min(1.00, max(0.10, contact)),
        min(1.20, max(0.50, force)),
        min(1.20, max(0.50, speed)),
    )


def render(csound: Path, csd: Path, output: Path) -> tuple[str, bytes, int]:
    completed = subprocess.run(
        [
            str(csound), "--sample-accurate", "--num-threads=1",
            "-W", "-s", "--nopeaks", "-d", "-m128",
            "-o", str(output), str(csd),
        ],
        check=False,
        cwd=csd.parent,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        timeout=20,
    )
    if completed.returncode != 0:
        raise RuntimeError(completed.stdout)
    with wave.open(str(output), "rb") as stream:
        if (stream.getframerate(), stream.getnchannels(),
                stream.getsampwidth()) != (48000, 2, 2):
            raise RuntimeError("rendered the wrong WAVE shape")
        frames = stream.readframes(stream.getnframes())
    peak = max(abs(item[0]) for item in struct.iter_unpack("<h", frames))
    return completed.stdout, frames, peak


def tagged(output: str) -> dict[tuple[float, int], tuple[float, ...]]:
    result = {}
    for match in LINE.finditer(output):
        phase = float(match.group(1))
        chord = int(match.group(2))
        result[(phase, chord)] = tuple(
            float(match.group(index)) for index in range(3, 6)
        )
    return result


def pitch_trace(output: str) -> list[tuple[float, float, float]]:
    return [tuple(float(match.group(index)) for index in range(1, 4))
            for match in PITCH_LINE.finditer(output)]


def chord_traces(output: str) -> dict[tuple[int, int, int], list[tuple[float, float]]]:
    result: dict[tuple[int, int, int], list[tuple[float, float]]] = {}
    for match in CHORD_LINE.finditer(output):
        key = tuple(int(match.group(index)) for index in range(1, 4))
        result.setdefault(key, []).append(
            (float(match.group(4)), float(match.group(5))))
    return result


def first_contact(trace: list[tuple[float, float]]) -> float | None:
    return next((age for age, contact in trace if contact > 0.05), None)


def contact_time(trace: list[tuple[float, float]], threshold: float) -> float:
    return sum(later_age - age
               for (age, contact), (later_age, _) in zip(trace, trace[1:])
               if contact >= threshold)


def contact_at(trace: list[tuple[float, float]], age: float) -> float:
    return next((contact for current_age, contact in trace
                 if current_age >= age), trace[-1][1])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csound", required=True, type=Path)
    parser.add_argument("--csd", required=True, type=Path)
    options = parser.parse_args()
    options.csound = options.csound.resolve()
    options.csd = options.csd.resolve()
    failures = []
    try:
        with tempfile.TemporaryDirectory(
                prefix="hlolli-bach-stroke-") as folder:
            root = Path(folder)
            first_output, first_pcm, first_peak = render(
                options.csound, options.csd, root / "first.wav")
            second_output, second_pcm, second_peak = render(
                options.csound, options.csd, root / "second.wav")
    except (OSError, RuntimeError, subprocess.TimeoutExpired,
            wave.Error) as error:
        print(f"Bach stroke shape test failed: {error}", file=sys.stderr)
        return 1

    first = tagged(first_output)
    second = tagged(second_output)
    first_pitch = pitch_trace(first_output)
    second_pitch = pitch_trace(second_output)
    first_chords = chord_traces(first_output)
    second_chords = chord_traces(second_output)
    wanted = {(phase, chord) for phase in PHASES for chord in (1, 3)}
    wanted.update({(-0.5, 3), (1.5, 3)})
    if set(first) != wanted:
        failures.append("probe keys changed")
    if first != second:
        failures.append("tagged controls changed on repeat")
    if first_pcm != second_pcm:
        failures.append("PCM changed on repeat")
    if first_pitch != second_pitch:
        failures.append("pitch transition changed on repeat")
    if first_chords != second_chords:
        failures.append("chord contact changed on repeat")
    if first_peak == 0 or first_peak >= 32767 or first_peak != second_peak:
        failures.append("PCM was silent, clipped, or changed peak")

    for key, values in first.items():
        expected_values = expected(*key)
        for name, value, wanted_value in zip(
                ("contact", "force", "speed"), values, expected_values):
            if abs(value - wanted_value) > 2.0e-12:
                failures.append(f"{name} changed at {key}")
        contact, force, speed = values
        if not (0.10 <= contact <= 1.00 and
                0.50 <= force <= 1.20 and
                0.50 <= speed <= 1.20):
            failures.append(f"controls left bounds at {key}")

    if first.get((-0.5, 3)) != first.get((0.0, 3)):
        failures.append("negative phase was not clamped")
    if first.get((1.5, 3)) != first.get((1.0, 3)):
        failures.append("late phase was not clamped")
    midpoint = first.get((0.5, 3))
    if midpoint is None or not (
            abs(midpoint[0] - 0.915) < 2.0e-12 and
            abs(midpoint[1] - 1.095) < 2.0e-12 and
            abs(midpoint[2] - 1.08) < 2.0e-12):
        failures.append("mid-stroke shoulder changed")

    if len(first_pitch) < 100:
        failures.append("pitch transition trace is incomplete")
    else:
        old_target = first_pitch[0][1]
        new_target = first_pitch[-1][1]
        onset = next((age for age, target, _ in first_pitch
                      if abs(target - new_target) < 1.0e-9), None)
        before = [frequency for age, _, frequency in first_pitch
                  if onset is not None and age < onset]
        after = [(age, frequency) for age, _, frequency in first_pitch
                 if onset is not None and age >= onset]
        if (onset is None or not before or len(after) < 20
                or old_target <= new_target):
            failures.append("pitch transition probe changed")
        else:
            if abs(1200.0 * math.log2(before[-1] / old_target)) > 0.1:
                failures.append("pitch did not settle before the slur")
            if any(not (new_target <= frequency <= old_target)
                   for _, frequency in after):
                failures.append("pitch transition overshot")
            if any(later > earlier + 1.0e-9
                   for (_, earlier), (_, later) in zip(after, after[1:])):
                failures.append("pitch transition was not monotone")
            settled_ms = None
            for index, (age, _) in enumerate(after):
                held = after[index:index + 5]
                if len(held) == 5 and all(
                        abs(1200.0 * math.log2(
                            frequency / new_target)) <= 20.0
                        for _, frequency in held):
                    settled_ms = 1000.0 * (age - onset)
                    break
            if settled_ms is None or not 6.0 <= settled_ms <= 18.0:
                failures.append("plain slur pitch transition is too abrupt or slow")

    wanted_chords = {
        (1, 0, 1), (2, 1, 0), (2, 0, 1),
        (4, 3, 0), (4, 2, 0), (4, 1, 0), (4, 0, 1),
        (3, 2, 0), (3, 1, 0), (3, 0, 1),
    }
    if set(first_chords) != wanted_chords:
        failures.append("chord contact probe keys changed")
    else:
        single = first_chords[(1, 0, 1)]
        if any(abs(contact - 1.0) > 1.0e-12 for _, contact in single):
            failures.append("single-note contact is not constant")
        double_onsets = [first_contact(first_chords[key]) for key in (
            (2, 1, 0), (2, 0, 1))]
        four_onsets = [first_contact(first_chords[key]) for key in (
            (4, 3, 0), (4, 2, 0), (4, 1, 0), (4, 0, 1))]
        if any(value is None for value in double_onsets + four_onsets):
            failures.append("a chord note never receives bow contact")
        elif (abs(double_onsets[1] - double_onsets[0]) > 0.001
                or abs(four_onsets[1] - four_onsets[0]) > 0.001
                or abs(four_onsets[3] - four_onsets[2]) > 0.001
                or four_onsets[2] - four_onsets[0] < 0.075):
            failures.append("chord does not move between two-string planes")
        for key in ((2, 1, 0), (4, 3, 0), (4, 2, 0), (4, 1, 0)):
            if contact_time(first_chords[key], 0.20) < 0.075:
                failures.append(f"lower chord note {key} got too little bow")
            late = [contact for age, contact in first_chords[key]
                    if age >= 0.23]
            if not late or max(late) > 0.01:
                failures.append(f"lower chord note {key} stayed bowed")
        for key in ((2, 0, 1), (4, 0, 1)):
            late = [contact for age, contact in first_chords[key]
                    if age >= 0.20]
            if not late or min(late) < 0.99:
                failures.append(f"upper chord lead {key} did not sustain")
        long_onsets = [first_contact(first_chords[key]) for key in (
            (3, 2, 0), (3, 1, 0), (3, 0, 1))]
        if (any(value is None for value in long_onsets)
                or abs(long_onsets[1] - long_onsets[0]) > 0.001
                or not 0.58 <= long_onsets[2] - long_onsets[0] <= 0.68):
            failures.append("long chord roll does not follow note duration")
        for key in ((3, 2, 0), (3, 1, 0)):
            if (contact_time(first_chords[key], 0.20) < 0.60
                    or (long_onsets[2] is not None
                        and contact_at(first_chords[key], long_onsets[2])
                        < 0.20)):
                failures.append(f"long lower chord note {key} got too little bow")
            late = [contact for age, contact in first_chords[key]
                    if age >= 0.95]
            if not late or max(late) > 0.01:
                failures.append(f"long lower chord note {key} stayed bowed")
        long_lead = [contact for age, contact in first_chords[(3, 0, 1)]
                     if age >= 0.95]
        if not long_lead or min(long_lead) < 0.99:
            failures.append("long upper chord lead did not sustain")

    if failures:
        for failure in failures:
            print(f"FAIL: {failure}", file=sys.stderr)
        return 1
    print("shared Bach stroke shape checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
