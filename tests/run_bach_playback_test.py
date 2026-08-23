#!/usr/bin/env python3
"""Check Chaconne bar windows, output modes, and a short real render."""

from __future__ import annotations

import argparse
import importlib.util
import math
import os
import subprocess
import sys
import tempfile
import wave
from pathlib import Path


def load_player(path: Path):
    spec = importlib.util.spec_from_file_location("bach_player", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load the Chaconne player")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def note_rows(score: Path) -> list[tuple[float, float]]:
    rows = []
    for line in score.read_text(encoding="utf-8").splitlines():
        if line.startswith('i "BachNote"'):
            fields = line.split()
            rows.append((float(fields[2]), float(fields[3])))
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--python", required=True, type=Path)
    parser.add_argument("--player", required=True, type=Path)
    parser.add_argument("--csound", required=True, type=Path)
    parser.add_argument("--module", required=True, type=Path)
    parser.add_argument("--csd", required=True, type=Path)
    parser.add_argument("--score", required=True, type=Path)
    parser.add_argument("--performance", required=True, type=Path)
    options = parser.parse_args()
    paths = (options.python, options.player, options.csound, options.module,
             options.csd, options.score, options.performance)
    if any(not path.resolve().is_file() for path in paths):
        print("Bach playback test input is missing", file=sys.stderr)
        return 1
    player = load_player(options.player.resolve())
    failures = []
    bars, strokes = player.parse_score(options.score.resolve())
    tempo = player.parse_tempo(options.performance.resolve())
    opening_durations = tuple(
        player.seconds_at(bars[bar + 1], tempo)
        - player.seconds_at(bars[bar], tempo)
        for bar in range(1, 5)
    )
    wanted_opening = (2.3504, 4.0247, 4.0047, 2.9952)
    if any(abs(value - wanted) > 0.002
           for value, wanted in zip(opening_durations, wanted_opening)):
        failures.append("opening reference timing changed")
    temporary_root = Path(tempfile.gettempdir())
    fixed_include = temporary_root / "hlolli-bach-plan-test.inc"
    first = player.build_plan(
        options.csound.resolve(), options.module.resolve(),
        options.csd.resolve(), options.score.resolve(),
        options.performance.resolve(), fixed_include, 1, None)
    if (first.window_start_beat != 0.0
            or first.muted_preroll_seconds != 0.0
            or first.vibrato_level != 1.0
            or first.distance_meters != 2.5
            or "-odac" not in first.argv
            or "--omacro:VIBRATO_LEVEL=1" not in first.argv
            or "--omacro:VIOLIN_DISTANCE_METERS=2.5" not in first.argv
            or any("--output=" in item for item in first.argv)
            or any("skip_seconds" in item for item in first.argv)):
        failures.append("bar-one realtime plan changed")
    output_plan = player.build_plan(
        options.csound.resolve(), options.module.resolve(),
        options.csd.resolve(), options.score.resolve(),
        options.performance.resolve(), fixed_include, 70,
        temporary_root / "hlolli-bach-plan-test.wav")
    if (output_plan.bar_beat != 206.0
            or output_plan.window_start_beat != 204.994
            or output_plan.muted_preroll_seconds <= 1.0
            or "-odac" in output_plan.argv
            or not all(flag in output_plan.argv
                       for flag in ("-W", "-3", "--nopeaks"))):
        failures.append("bar-70 WAVE plan changed")
    zero_vibrato = player.build_plan(
        options.csound.resolve(), options.module.resolve(),
        options.csd.resolve(), options.score.resolve(),
        options.performance.resolve(), fixed_include, 93, None,
        vibrato_level=0.0)
    if (zero_vibrato.vibrato_level != 0.0
            or "--omacro:VIBRATO_LEVEL=0" not in zero_vibrato.argv):
        failures.append("zero-vibrato plan changed")
    near_listener = player.build_plan(
        options.csound.resolve(), options.module.resolve(),
        options.csd.resolve(), options.score.resolve(),
        options.performance.resolve(), fixed_include, 231, None,
        distance_meters=1.0)
    if (near_listener.distance_meters != 1.0
            or "--omacro:VIOLIN_DISTANCE_METERS=1" not in near_listener.argv):
        failures.append("near-listener plan changed")
    for bar in (70, 71, 248, 249):
        stroke = player.active_stroke(strokes, bars[bar])
        if stroke.start >= bars[bar]:
            failures.append(f"bar {bar} lost its bow preparation")
    for bad in (0, 258):
        try:
            player.build_plan(
                options.csound.resolve(), options.module.resolve(),
                options.csd.resolve(), options.score.resolve(),
                options.performance.resolve(), fixed_include, bad, None)
        except ValueError:
            pass
        else:
            failures.append(f"bar {bad} was accepted")
    for bad_distance in (0.99, 50.01, math.inf):
        try:
            player.build_plan(
                options.csound.resolve(), options.module.resolve(),
                options.csd.resolve(), options.score.resolve(),
                options.performance.resolve(), fixed_include, 231, None,
                distance_meters=bad_distance)
        except ValueError:
            pass
        else:
            failures.append(f"distance {bad_distance} was accepted")
    notes = note_rows(options.score.resolve())
    starts = {start for start, _ in notes}
    for bar, beat in bars.items():
        if beat not in starts:
            failures.append(f"bar {bar} has no exact note onset")
        if any(start < beat < start + duration for start, duration in notes):
            failures.append(f"a note crosses bar {bar}")
    window = player.render_performance(
        options.score.resolve(), tempo, output_plan.window_start_beat,
        output_plan.bar_beat)
    if ('i "BachStroke" 0 ' not in window
            or 'i "BachBar" 1.0060000000000002 0.001 70' not in window
            or 'i "BachBar"' not in window
            or ' 69\n' in window
            or not window.endswith("e\n")):
        failures.append("shifted score window changed")
    if failures:
        for failure in failures:
            print(f"FAIL: {failure}", file=sys.stderr)
        return 1
    try:
        with tempfile.TemporaryDirectory(prefix="hlolli-bach-playback-") as folder:
            outputs = []
            logs = []
            for name in ("first.wav", "second.wav"):
                output = Path(folder) / name
                command = [
                    str(options.python.resolve()), "-B",
                    str(options.player.resolve()),
                    "--csound", str(options.csound.resolve()),
                    "--module", str(options.module.resolve()),
                    "--csd", str(options.csd.resolve()),
                    "--score", str(options.score.resolve()),
                    "--performance", str(options.performance.resolve()),
                    "--start-bar", "257", "--output", str(output),
                ]
                completed = subprocess.run(
                    command, check=False, stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT, text=True, timeout=30)
                if completed.returncode != 0:
                    raise RuntimeError(completed.stdout)
                logs.append(completed.stdout)
                outputs.append(output.read_bytes())
                with wave.open(str(output), "rb") as stream:
                    if (stream.getnchannels(), stream.getsampwidth(),
                            stream.getframerate()) != (2, 3, 48000):
                        raise RuntimeError("late-bar WAVE shape changed")
                    frames = stream.readframes(stream.getnframes())
                if not frames or not any(frames) or frames[:6] == bytes(6):
                    raise RuntimeError("late-bar render is silent or untrimmed")
            if outputs[0] != outputs[1]:
                raise RuntimeError("late-bar render changed on repeat")
            if any("BAR 257" not in log or "BAR 256" in log for log in logs):
                raise RuntimeError("late-bar marker changed")
            descriptor, include_name = tempfile.mkstemp(
                dir=player.short_temporary_root(),
                prefix="hlolli-bach-room-test-", suffix=".inc")
            os.close(descriptor)
            include = Path(include_name)
            raw_dry = Path(folder) / "dry-with-preroll.wav"
            dry = Path(folder) / "dry.wav"
            try:
                dry_plan = player.build_plan(
                    options.csound.resolve(), options.module.resolve(),
                    options.csd.resolve(), options.score.resolve(),
                    options.performance.resolve(), include, 257, raw_dry)
                include.write_text(
                    player.render_performance(
                        options.score.resolve(), tempo,
                        dry_plan.window_start_beat, dry_plan.bar_beat),
                    encoding="utf-8",
                )
                command = list(dry_plan.argv)
                command.insert(-1, "--omacro:ROOM_LEVEL=0")
                completed = subprocess.run(
                    command, cwd=options.csd.resolve().parent, check=False,
                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    text=True, timeout=30)
                if completed.returncode != 0:
                    raise RuntimeError(completed.stdout)
                with wave.open(str(raw_dry), "rb") as stream:
                    frame_bytes = stream.getnchannels() * stream.getsampwidth()
                    guard_frames = math.floor(
                        dry_plan.muted_preroll_seconds * stream.getframerate())
                    guarded = stream.readframes(guard_frames)
                if any(guarded) or len(guarded) != guard_frames * frame_bytes:
                    raise RuntimeError("bar gate opened before its sample")
                player.trim_leading_silence(raw_dry, dry)
                if dry.read_bytes() == outputs[0]:
                    raise RuntimeError("the Chaconne room has no audible output")
            finally:
                include.unlink(missing_ok=True)
    except (OSError, RuntimeError, subprocess.TimeoutExpired,
            wave.Error) as error:
        print(f"Bach playback test failed: {error}", file=sys.stderr)
        return 1
    print("Bach playback and late-bar render checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
