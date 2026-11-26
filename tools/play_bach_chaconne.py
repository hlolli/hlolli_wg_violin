#!/usr/bin/env python3
"""Plan and run the Bach Chaconne listening demo."""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import subprocess
import sys
import tempfile
import wave
from dataclasses import asdict, dataclass
from pathlib import Path


EXPECTED_BARS = 257
EXPECTED_STROKES = 1676
EXPECTED_BEATS = 770.0
BAR_PATTERN = re.compile(r'^i "BachBar"\s+(.+)$')
STROKE_PATTERN = re.compile(r'^i "BachStroke"\s+(.+)$')


@dataclass(frozen=True)
class Stroke:
    start: float
    end: float
    direction: int
    stroke_id: int
    chord_size: int


@dataclass(frozen=True)
class PlaybackPlan:
    start_bar: int
    bar_beat: float
    stroke_id: int
    window_start_beat: float
    muted_preroll_seconds: float
    vibrato_level: float
    distance_meters: float
    infinite_bow: bool
    performance_include: str
    mode: str
    output: str | None
    argv: tuple[str, ...]


def format_number(value: float) -> str:
    text = format(value, ".17g")
    return text if text else "0"


def parse_score(score: Path) -> tuple[dict[int, float], list[Stroke]]:
    bars: dict[int, float] = {}
    strokes: list[Stroke] = []
    for line_number, line in enumerate(
            score.read_text(encoding="utf-8").splitlines(), 1):
        bar_match = BAR_PATTERN.match(line)
        if bar_match:
            fields = bar_match.group(1).split()
            if len(fields) != 3:
                raise ValueError(f"{score}:{line_number}: malformed bar")
            start, duration, number = map(float, fields)
            bar = int(number)
            if number != bar or bar in bars or abs(duration - 0.001) > 1e-12:
                raise ValueError(f"{score}:{line_number}: invalid bar")
            bars[bar] = start
            continue
        stroke_match = STROKE_PATTERN.match(line)
        if not stroke_match:
            continue
        fields = stroke_match.group(1).split()
        if len(fields) != 5:
            raise ValueError(f"{score}:{line_number}: malformed stroke")
        start, duration, direction, stroke_id, chord_size = map(float, fields)
        values = (direction, stroke_id, chord_size)
        integers = tuple(int(value) for value in values)
        if values != integers or duration <= 0:
            raise ValueError(f"{score}:{line_number}: invalid stroke")
        strokes.append(Stroke(
            start, start + duration, integers[0], integers[1], integers[2]))
    if sorted(bars) != list(range(1, EXPECTED_BARS + 1)):
        raise ValueError("score does not contain bars 1 through 257")
    if len(strokes) != EXPECTED_STROKES:
        raise ValueError("score does not contain the fixed bow-stroke plan")
    for index, stroke in enumerate(strokes):
        if (stroke.stroke_id != index + 1
                or stroke.direction != (1 if index % 2 == 0 else -1)
                or stroke.chord_size not in (1, 2, 3, 4)):
            raise ValueError("bow-stroke facts changed")
        if index and not math.isclose(
                strokes[index - 1].end, stroke.start, abs_tol=1e-9):
            raise ValueError("bow strokes leave a gap or overlap")
    if (not math.isclose(strokes[0].start, 0.0, abs_tol=1e-12)
            or not math.isclose(
                strokes[-1].end, EXPECTED_BEATS, abs_tol=1e-9)):
        raise ValueError("bow strokes do not cover the movement")
    return bars, strokes


def parse_tempo(performance: Path) -> list[tuple[float, float]]:
    text = performance.read_text(encoding="utf-8").replace("\\\n", " ")
    rows = [line.strip() for line in text.splitlines()
            if line.lstrip().startswith("t ")]
    if len(rows) != 1:
        raise ValueError("the Chaconne must have one tempo statement")
    fields = rows[0].split()[1:]
    if len(fields) < 2 or len(fields) % 2:
        raise ValueError("the Chaconne tempo statement is malformed")
    values = [float(field) for field in fields]
    pairs = list(zip(values[0::2], values[1::2]))
    if (pairs[0][0] != 0.0
            or any(tempo <= 0 for _, tempo in pairs)
            or any(right[0] <= left[0]
                   for left, right in zip(pairs, pairs[1:]))):
        raise ValueError("the Chaconne tempo statement is invalid")
    return pairs


def seconds_at(beat: float, tempo: list[tuple[float, float]]) -> float:
    if beat < 0:
        raise ValueError("score beat cannot be negative")
    time = 0.0
    for index, (left_beat, left_tempo) in enumerate(tempo):
        left_duration = 60.0 / left_tempo
        if index + 1 == len(tempo):
            return time + (beat - left_beat) * left_duration
        right_beat, right_tempo = tempo[index + 1]
        width = right_beat - left_beat
        right_duration = 60.0 / right_tempo
        if beat < right_beat:
            offset = beat - left_beat
            slope = (right_duration - left_duration) / (2.0 * width)
            return time + (slope * offset + left_duration) * offset
        time += 0.5 * (left_duration + right_duration) * width
    raise ValueError("tempo conversion failed")


def beat_duration_at(beat: float,
                     tempo: list[tuple[float, float]]) -> float:
    for index, (left_beat, left_tempo) in enumerate(tempo):
        left_duration = 60.0 / left_tempo
        if index + 1 == len(tempo):
            return left_duration
        right_beat, right_tempo = tempo[index + 1]
        if beat < right_beat:
            phase = (beat - left_beat) / (right_beat - left_beat)
            return left_duration + phase * (
                60.0 / right_tempo - left_duration)
    raise ValueError("tempo lookup failed")


def active_stroke(strokes: list[Stroke], beat: float) -> Stroke:
    matches = [stroke for stroke in strokes
               if stroke.start <= beat < stroke.end]
    if len(matches) != 1:
        raise ValueError("bar does not have one active bow stroke")
    return matches[0]


def render_performance(score: Path, tempo: list[tuple[float, float]],
                       window_start: float, audible_beat: float) -> str:
    shifted_tempo = [(0.0, 60.0 / beat_duration_at(window_start, tempo))]
    shifted_tempo.extend(
        (beat - window_start, value)
        for beat, value in tempo if beat > window_start)
    tempo_fields = " ".join(
        f"{format_number(beat)} {format_number(value)}"
        for beat, value in shifted_tempo)
    lines = [f"t {tempo_fields}"]
    lines.append(
        f'i "BachAudible" '
        f"{format_number(audible_beat - window_start)} "
        f"{format_number(774.0 - audible_beat)}")
    for line_number, line in enumerate(
            score.read_text(encoding="utf-8").splitlines(), 1):
        if not line.startswith('i "'):
            continue
        fields = line.split()
        if len(fields) < 4:
            raise ValueError(f"{score}:{line_number}: malformed event")
        try:
            start = float(fields[2])
        except ValueError as error:
            raise ValueError(
                f"{score}:{line_number}: invalid event time") from error
        if start + 1e-10 < window_start:
            continue
        if (fields[1] in ('"BachBar"', '"BachMark"')
                and start + 1e-10 < audible_beat):
            continue
        fields[2] = format_number(max(0.0, start - window_start))
        lines.append(" ".join(fields))
    lines.append(f"f 0 {format_number(774.0 - window_start)}")
    lines.append("e")
    lines.append("")
    return "\n".join(lines)


def build_plan(csound: Path, module: Path, csd: Path, score: Path,
               performance: Path, performance_include: Path,
               start_bar: int, output: Path | None,
               rendered_output: Path | None = None,
               vibrato_level: float = 1.0,
               distance_meters: float = 2.5,
               infinite_bow: bool = True,
               bow_guide: Path | None = None) -> PlaybackPlan:
    if not 1 <= start_bar <= EXPECTED_BARS:
        raise ValueError("start bar must be an integer from 1 through 257")
    if not math.isfinite(vibrato_level) or not 0 <= vibrato_level <= 2:
        raise ValueError("vibrato level must be from 0 through 2")
    if (not math.isfinite(distance_meters)
            or not 1 <= distance_meters <= 50):
        raise ValueError("distance must be from 1 through 50 metres")
    for label, path in (("Csound", csound), ("module", module),
                        ("CSD", csd), ("score", score),
                        ("performance", performance)):
        if not path.is_file():
            raise ValueError(f"{label} file does not exist: {path}")
    bars, strokes = parse_score(score)
    tempo = parse_tempo(performance)
    bar_beat = bars[start_bar]
    stroke = active_stroke(strokes, bar_beat)
    stroke_seconds = seconds_at(stroke.start, tempo)
    bar_seconds = seconds_at(bar_beat, tempo)
    argv = [
        str(csound),
        f"--opcode-lib={module}",
        "--sample-accurate",
        "--num-threads=1",
        f"--omacro:VIBRATO_LEVEL={format_number(vibrato_level)}",
        f"--omacro:VIOLIN_DISTANCE_METERS={format_number(distance_meters)}",
        f"--omacro:INFINITE_BOW={int(infinite_bow)}",
        f"--smacro:BACH_PERFORMANCE={performance_include}",
    ]
    if bow_guide is not None:
        if not bow_guide.is_file():
            raise ValueError(f"bow guide file does not exist: {bow_guide}")
        argv.append(f"--omacro:BACH_BOW_GUIDE={bow_guide}")
    if output is None:
        argv.append("-odac")
        mode = "realtime"
    else:
        target = rendered_output if rendered_output is not None else output
        argv.extend(("-W", "-3", "--nopeaks", f"--output={target}"))
        mode = "wave24"
    argv.append(str(csd))
    return PlaybackPlan(
        start_bar=start_bar,
        bar_beat=bar_beat,
        stroke_id=stroke.stroke_id,
        window_start_beat=stroke.start,
        muted_preroll_seconds=bar_seconds - stroke_seconds,
        vibrato_level=vibrato_level,
        distance_meters=distance_meters,
        infinite_bow=infinite_bow,
        performance_include=str(performance_include),
        mode=mode,
        output=str(output) if output is not None else None,
        argv=tuple(argv),
    )


def temporary_path(parent: Path, name: str, suffix: str = ".wav") -> Path:
    descriptor, value = tempfile.mkstemp(
        dir=parent, prefix=f".{name}.", suffix=suffix)
    os.close(descriptor)
    path = Path(value)
    path.unlink()
    return path


def short_temporary_root() -> Path:
    root = Path("/tmp")
    return root if root.is_dir() else Path(tempfile.gettempdir())


def trim_leading_silence(source: Path, destination: Path) -> None:
    temporary = temporary_path(destination.parent, destination.name + ".trim")
    try:
        with wave.open(str(source), "rb") as reader:
            with wave.open(str(temporary), "wb") as writer:
                parameters = reader.getparams()
                if (parameters.nchannels, parameters.sampwidth,
                        parameters.framerate, parameters.comptype) != (
                            2, 3, 48000, "NONE"):
                    raise ValueError("Csound rendered the wrong WAVE shape")
                writer.setparams(parameters)
                frame_bytes = parameters.nchannels * parameters.sampwidth
                zero = bytes(frame_bytes)
                found = False
                while True:
                    frames = reader.readframes(8192)
                    if not frames:
                        break
                    first = 0
                    if not found:
                        while (first < len(frames)
                               and frames[first:first + frame_bytes] == zero):
                            first += frame_bytes
                        found = first < len(frames)
                    if found:
                        writer.writeframesraw(frames[first:])
                if not found:
                    raise ValueError("Csound rendered a silent WAVE file")
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)


def run(options: argparse.Namespace) -> int:
    csound = options.csound.resolve()
    module = options.module.resolve()
    csd = options.csd.resolve()
    score = options.score.resolve()
    performance = options.performance.resolve()
    output = options.output.resolve() if options.output is not None else None
    if output is not None and not output.parent.is_dir():
        raise ValueError(f"output folder does not exist: {output.parent}")
    rendered = (temporary_path(output.parent, output.name)
                if output is not None and not options.plan_only else None)
    if options.plan_only:
        performance_include = (
            short_temporary_root() / "hlolli-bach-chaconne-performance.inc")
    else:
        performance_include = temporary_path(
            short_temporary_root(),
            "hlolli-bach-chaconne-performance", ".inc")
    try:
        plan = build_plan(
            csound, module, csd, score, performance, performance_include,
            options.start_bar, output, rendered,
            vibrato_level=options.vibrato_level,
            distance_meters=options.distance_meters,
            infinite_bow=bool(options.infinite_bow),
            bow_guide=options.bow_guide.resolve() if options.bow_guide else None)
        if options.plan_only:
            print(json.dumps(asdict(plan), indent=2))
            return 0
        performance_include.write_text(
            render_performance(
                score, parse_tempo(performance), plan.window_start_beat,
                plan.bar_beat),
            encoding="utf-8",
        )
        completed = subprocess.run(
            plan.argv, cwd=csd.parent, check=False)
        if completed.returncode != 0:
            return completed.returncode
        if output is not None and rendered is not None:
            if plan.muted_preroll_seconds > 0:
                trim_leading_silence(rendered, output)
            else:
                os.replace(rendered, output)
            print(f"Wrote {output}")
        return 0
    finally:
        if rendered is not None:
            rendered.unlink(missing_ok=True)
        if not options.plan_only:
            performance_include.unlink(missing_ok=True)


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csound", required=True, type=Path)
    parser.add_argument("--module", required=True, type=Path)
    parser.add_argument(
        "--csd", type=Path, default=root / "examples/bach_chaconne.csd")
    parser.add_argument(
        "--score", type=Path,
        default=root / "examples/bach_chaconne_score.inc")
    parser.add_argument(
        "--performance", type=Path,
        default=root / "examples/bach_chaconne_performance.inc")
    parser.add_argument("--start-bar", type=int, default=1)
    parser.add_argument("--vibrato-level", type=float, default=1.0)
    parser.add_argument("--distance-meters", type=float, default=2.5)
    parser.add_argument("--infinite-bow", type=int, choices=(0, 1), default=1)
    parser.add_argument("--bow-guide", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--plan-only", action="store_true")
    options = parser.parse_args()
    try:
        return run(options)
    except (OSError, ValueError, wave.Error) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
