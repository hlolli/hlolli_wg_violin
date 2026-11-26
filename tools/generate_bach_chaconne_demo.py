#!/usr/bin/env python3
"""Build and check the fixed Bach Chaconne Csound score."""

from __future__ import annotations

import argparse
import hashlib
import itertools
import math
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path


DIVISION = 384
EXPECTED_NOTES = 3123
EXPECTED_STROKES = 1676
EXPECTED_BARS = 257
EXPECTED_DOTTED_SHORTS = 143
EXPECTED_VIBRATO_NOTES = 1280
EXPECTED_CHORD_ONSETS = 487
EXPECTED_BEATS = 770.0
EXPECTED_EVENT_DIGEST = "6e47c767b094240523908466c6437979212efacb830383b7a84e3d6a94101ddb"
EXPECTED_STROKE_DIGEST = "e72719df37fe09cec5295d5393f329ea084058ad59b81f11fcd159928d791d82"
EXPECTED_SOURCE_DIGEST = "5c9b5e82290fc58b45f7dd1acd6ec1aa0fcec60a214cd2b20688ae34952e42af"
OPEN_PITCHES = (55, 62, 69, 76)
ROLL_TICKS = 24
STROKE_LEAD_BEATS = 0.006
NOTE_PATTERN = re.compile(r'^i "BachNote"\s+(.+)$')
STROKE_PATTERN = re.compile(r'^i "BachStroke"\s+(.+)$')
BAR_PATTERN = re.compile(r'^i "BachBar"\s+(.+)$')
PITCH_CLASS = {
    "c": 0, "cis": 1, "d": 2, "dis": 3, "es": 3, "e": 4,
    "f": 5, "fis": 6, "g": 7, "gis": 8, "a": 9, "ais": 10,
    "bes": 10, "b": 11,
}
DIATONIC_STEP = {
    "c": 0, "cis": 0, "d": 1, "dis": 1, "es": 2, "e": 2,
    "f": 3, "fis": 3, "g": 4, "gis": 4, "a": 5, "ais": 5,
    "bes": 6, "b": 6,
}
PITCH_TOKEN = r"(?:cis|dis|fis|gis|ais|bes|es|[a-g])"
LILY_NOTE_PATTERN = re.compile(
    r"^(" + PITCH_TOKEN + r")([',]*)(\d*)(\.*)$"
)
LILY_REST_PATTERN = re.compile(r"^([rs])(\d*)(\.*)$")
LILY_TOKEN_PATTERN = re.compile(
    r"<[a-gisbe',\s]+>\d*\.*|" + PITCH_TOKEN
    + r"[',]*\d*\.*|[rs]\d*\.*|\\[A-Za-z]+|\d+/\d+|[{}()\[\]|~]"
)
VOICE_NAMES = ("melodyOne", "melodyTwo", "melodyThree", "melodyFour")

DYNAMIC_ANCHORS = (
    (1, 0.58), (8, 0.52), (16, 0.64), (24, 0.45), (32, 0.62),
    (40, 0.68), (48, 0.48), (56, 0.65), (64, 0.54), (72, 0.72),
    (80, 0.60), (88, 0.78), (96, 0.42), (112, 0.68), (128, 0.52),
    (132, 0.38), (133, 0.30), (145, 0.42), (160, 0.52),
    (176, 0.62), (192, 0.72), (208, 0.48), (209, 0.62),
    (224, 0.72), (240, 0.82), (248, 0.58), (257, 0.50),
)

MARKS = (
    (0.0, 0),
    (95.0, 1),
    (395.0, 2),
    (623.0, 3),
    (719.0, 4),
)


@dataclass
class SourceNote:
    start: int
    end: int
    pitch: int
    voice: int
    slur_from_previous: bool
    dots: int
    dotted_short: bool = False


@dataclass
class ScoreNote:
    start: int
    end: int
    pitch: int
    string: int
    direction: int = 0
    legato: int = 0
    dynamic: float = 0.0
    vibrato_depth: float = 0.0
    vibrato_rate: float = 0.0
    gesture: int = 0
    bow_group: int = 0
    rolled: int = 0
    chord_size: int = 1
    voice: int = 0
    lead: int = 1
    chord_rank: int = 0
    source_slur: bool = False
    dotted_short: int = 0


def strip_lily_markup(text: str) -> str:
    marker = "^\\markup"
    while marker in text:
        start = text.index(marker)
        brace = text.index("{", start)
        depth = 1
        cursor = brace + 1
        while depth:
            if cursor >= len(text):
                raise ValueError("unfinished LilyPond markup")
            if text[cursor] == "{":
                depth += 1
            elif text[cursor] == "}":
                depth -= 1
            cursor += 1
        text = text[:start] + text[cursor:]
    return text


def extract_lily_voice(source: str, name: str) -> tuple[str, str]:
    start = source.index(name + " =")
    relative_match = re.search(
        r"\\relative\s+(" + PITCH_TOKEN + r"[',]*)", source[start:]
    )
    if relative_match is None:
        raise ValueError(f"{name} lacks a relative pitch")
    brace = source.index("{", start)
    depth = 1
    cursor = brace + 1
    while depth:
        if cursor >= len(source):
            raise ValueError(f"unfinished {name}")
        if source[cursor] == "{":
            depth += 1
        elif source[cursor] == "}":
            depth -= 1
        cursor += 1
    body = re.sub(r"%[^\n]*", " ", source[brace + 1:cursor - 1])
    body = strip_lily_markup(body)
    body = re.sub(
        r"\\key\s+" + PITCH_TOKEN + r"\s+\\(?:major|minor)", " ", body
    )
    body = re.sub(
        r"\\(?:voiceOne|voiceTwo|voiceThree|voiceFive|trill|fermata)",
        " ", body,
    )
    body = re.sub(r'\\bar\s+"[^"]*"', " ", body)
    body = re.sub(
        r"(" + PITCH_TOKEN + r"[',]*|[rs])\s+(\d+\.*)", r"\1\2", body
    )
    return relative_match.group(1), body


def explicit_lily_pitch(token: str) -> tuple[int, int]:
    match = LILY_NOTE_PATTERN.match(token)
    if match is None:
        raise ValueError(f"invalid LilyPond pitch {token}")
    octave = 3 + match.group(2).count("'") - match.group(2).count(",")
    pitch = 12 * (octave + 1) + PITCH_CLASS[match.group(1)]
    step = octave * 7 + DIATONIC_STEP[match.group(1)]
    return pitch, step


def relative_lily_pitch(token: str, previous_step: int) -> tuple[int, int]:
    match = LILY_NOTE_PATTERN.match(token)
    if match is None:
        raise ValueError(f"invalid LilyPond pitch {token}")
    name = match.group(1)
    step_in_octave = DIATONIC_STEP[name]
    octave = previous_step // 7
    step_delta = step_in_octave - previous_step % 7
    if step_delta > 3:
        octave -= 1
    elif step_delta < -3:
        octave += 1
    octave += match.group(2).count("'") - match.group(2).count(",")
    return 12 * (octave + 1) + PITCH_CLASS[name], octave * 7 + step_in_octave


def lily_duration(token: str, previous: Fraction,
                  previous_dots: int) -> tuple[Fraction, int]:
    match = LILY_NOTE_PATTERN.match(token) or LILY_REST_PATTERN.match(token)
    if match is None:
        raise ValueError(f"invalid LilyPond duration {token}")
    is_note = LILY_NOTE_PATTERN.match(token) is not None
    number = match.group(3 if is_note else 2)
    dots = match.group(4 if is_note else 3)
    if not number:
        return previous, previous_dots
    base = Fraction(4, int(number))
    total = base
    part = base
    for _dot in dots:
        part /= 2
        total += part
    return total, len(dots)


def ticks(value: Fraction) -> int:
    result = value * DIVISION
    if result.denominator != 1:
        raise ValueError("LilyPond duration does not fit the score grid")
    return result.numerator


def parse_lily_voice(source: str, voice: int, name: str) -> list[SourceNote]:
    relative, body = extract_lily_voice(source, name)
    tokens = LILY_TOKEN_PATTERN.findall(body)
    residue = LILY_TOKEN_PATTERN.sub(" ", body)
    if re.sub(r"[\s,.'\"^]+", "", residue):
        raise ValueError(f"unsupported LilyPond syntax in {name}")

    _previous_pitch, previous_step = explicit_lily_pitch(relative)
    time = Fraction(0)
    previous_duration = Fraction(1)
    previous_dots = 0
    scales = [Fraction(1)]
    active_slur = False
    prior_note = False
    notes: list[SourceNote] = []
    cursor = 0
    while cursor < len(tokens):
        token = tokens[cursor]
        if token == "\\times":
            numerator, denominator = map(int, tokens[cursor + 1].split("/"))
            if tokens[cursor + 2] != "{":
                raise ValueError("LilyPond times command lacks a block")
            scales.append(scales[-1] * Fraction(numerator, denominator))
            cursor += 3
            continue
        if token == "{":
            scales.append(scales[-1])
            cursor += 1
            continue
        if token == "}":
            if len(scales) == 1:
                raise ValueError("extra LilyPond block close")
            scales.pop()
            cursor += 1
            continue
        if token == "(":
            active_slur = True
            cursor += 1
            continue
        if token == ")":
            active_slur = False
            cursor += 1
            continue
        if (token.startswith("\\") or token in ("[", "]", "|", "~")
                or re.match(r"^\d+/\d+$", token)):
            cursor += 1
            continue
        if token.startswith("<"):
            close = token.index(">")
            pitch_tokens = token[1:close].split()
            duration, note_dots = lily_duration(
                pitch_tokens[0] + token[close + 1:],
                previous_duration, previous_dots)
            previous_duration = duration
            previous_dots = note_dots
            chord_step = previous_step
            pitches: list[int] = []
            for pitch_token in pitch_tokens:
                pitch, chord_step = relative_lily_pitch(pitch_token, chord_step)
                pitches.append(pitch)
            _first_pitch, previous_step = relative_lily_pitch(
                pitch_tokens[0], previous_step
            )
            note_duration = duration * scales[-1]
            for pitch in pitches:
                notes.append(SourceNote(
                    ticks(time), ticks(time + note_duration), pitch, voice,
                    active_slur and prior_note, note_dots,
                ))
            prior_note = True
            time += note_duration
            cursor += 1
            continue
        if LILY_REST_PATTERN.match(token):
            duration, rest_dots = lily_duration(
                token, previous_duration, previous_dots)
            previous_duration = duration
            previous_dots = rest_dots
            time += duration * scales[-1]
            prior_note = False
            cursor += 1
            continue
        if LILY_NOTE_PATTERN.match(token):
            duration, note_dots = lily_duration(
                token, previous_duration, previous_dots)
            previous_duration = duration
            previous_dots = note_dots
            pitch, previous_step = relative_lily_pitch(token, previous_step)
            note_duration = duration * scales[-1]
            notes.append(SourceNote(
                ticks(time), ticks(time + note_duration), pitch, voice,
                active_slur and prior_note, note_dots,
            ))
            prior_note = True
            time += note_duration
            cursor += 1
            continue
        raise ValueError(f"unsupported LilyPond token {token}")
    if len(scales) != 1 or time != Fraction(int(EXPECTED_BEATS), 1):
        raise ValueError(f"{name} does not span the full movement")
    by_onset: dict[int, list[SourceNote]] = defaultdict(list)
    for note in notes:
        by_onset[note.start].append(note)
    onset_groups = [by_onset[start] for start in sorted(by_onset)]
    for previous, current in zip(onset_groups, onset_groups[1:]):
        previous_durations = {note.end - note.start for note in previous}
        current_durations = {note.end - note.start for note in current}
        if (len(previous_durations) == 1
                and len(current_durations) == 1
                and all(note.dots == 1 for note in previous)
                and all(note.dots == 0 for note in current)
                and max(note.end for note in previous) == current[0].start
                and next(iter(previous_durations))
                == 3 * next(iter(current_durations))):
            for note in current:
                note.dotted_short = True
    return notes


def parse_lilypond(path: Path) -> list[SourceNote]:
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() != EXPECTED_SOURCE_DIGEST:
        raise ValueError("unexpected LilyPond source revision")
    source = data.decode("utf-8")
    notes: list[SourceNote] = []
    for voice, name in enumerate(VOICE_NAMES):
        notes.extend(parse_lily_voice(source, voice, name))
    notes.sort(key=lambda note: (note.start, note.pitch, note.voice, note.end))
    if len(notes) != EXPECTED_NOTES:
        raise ValueError(f"expected {EXPECTED_NOTES} written notes, found {len(notes)}")
    if min(note.pitch for note in notes) != 55 or max(note.pitch for note in notes) != 91:
        raise ValueError("unexpected score pitch range")
    if max(note.end for note in notes) != int(EXPECTED_BEATS * DIVISION):
        raise ValueError("unexpected score length")
    if sum(note.slur_from_previous for note in notes) != 639:
        raise ValueError("unexpected LilyPond slur graph")
    if sum(note.dotted_short for note in notes) != EXPECTED_DOTTED_SHORTS:
        raise ValueError("unexpected dotted-rhythm graph")
    return notes


def assignment_cost(notes: list[SourceNote], strings: tuple[int, ...],
                    last_pitch: list[int | None],
                    last_voice_string: list[int | None]) -> float:
    cost = 0.0
    for note, string in zip(notes, strings):
        pitch = note.pitch
        position = pitch - OPEN_PITCHES[string]
        if position < 0:
            return math.inf
        cost += 0.075 * position * position + 0.32 * string
        if position == 0:
            cost -= 32.0
        if position > 12:
            cost += 3.0 * (position - 12)
        if last_pitch[string] is not None:
            cost += 0.10 * abs(pitch - last_pitch[string])
        if note.slur_from_previous and last_voice_string[note.voice] is not None:
            if string == last_voice_string[note.voice]:
                cost -= 24.0
            else:
                cost += 24.0
    return cost


def choose_strings(group: list[SourceNote], last_pitch: list[int | None],
                   last_voice_string: list[int | None]) -> tuple[list[int], bool]:
    ordered = sorted(group, key=lambda note: (note.pitch, note.voice, note.end))
    candidates: list[tuple[float, tuple[int, ...]]] = []
    for strings in itertools.combinations(range(4), len(ordered)):
        cost = assignment_cost(ordered, strings, last_pitch, last_voice_string)
        if math.isfinite(cost):
            candidates.append((cost, strings))
    if candidates:
        return list(min(candidates)[1]), False

    # Two printed grips need a brief low-to-high roll because two stopped
    # pitches share one physical string. Keep every printed pitch.
    for strings in itertools.combinations_with_replacement(range(4), len(ordered)):
        if any(strings[index] > strings[index + 1]
               for index in range(len(strings) - 1)):
            continue
        if any(strings.count(string) > 2 for string in set(strings)):
            continue
        cost = assignment_cost(ordered, strings, last_pitch, last_voice_string)
        if math.isfinite(cost):
            repeats = len(strings) - len(set(strings))
            candidates.append((cost + 1000.0 * repeats, strings))
    if not candidates:
        raise ValueError(f"unplayable chord at tick {group[0].start}")
    return list(min(candidates)[1]), True


def measure_at(beat: float) -> int:
    if beat < 2.0:
        return 1
    return 2 + int((beat - 2.0) // 3.0)


def beat_for_measure(measure: int) -> float:
    return 0.0 if measure == 1 else float(3 * measure - 4)


def dynamic_at(beat: float) -> float:
    points = [(beat_for_measure(measure), value)
              for measure, value in DYNAMIC_ANCHORS]
    for index in range(len(points) - 1):
        left_beat, left_value = points[index]
        right_beat, right_value = points[index + 1]
        if beat <= right_beat:
            width = max(0.000001, right_beat - left_beat)
            phase = min(1.0, max(0.0, (beat - left_beat) / width))
            value = left_value + phase * (right_value - left_value)
            local = beat if beat < 2.0 else (beat - 2.0) % 3.0
            if local < 0.03:
                value += 0.045
            elif abs(local - 1.0) < 0.03:
                value += 0.018
            return min(0.92, max(0.24, value))
    return points[-1][1]


def build_score(notes: list[SourceNote]) -> list[ScoreNote]:
    groups: dict[int, list[SourceNote]] = defaultdict(list)
    for note in notes:
        groups[note.start].append(note)

    score: list[ScoreNote] = []
    last_pitch: list[int | None] = [None] * 4
    last_voice_string: list[int | None] = [None] * len(VOICE_NAMES)
    for tick, group in sorted(groups.items()):
        ordered = sorted(group, key=lambda note: (note.pitch, note.voice, note.end))
        strings, rolled = choose_strings(ordered, last_pitch, last_voice_string)
        lead_voice = min(note.voice for note in ordered)
        lead_note = max(
            (note for note in ordered if note.voice == lead_voice),
            key=lambda note: (note.pitch, note.end),
        )
        repeated_seen: Counter[int] = Counter()
        for order, (note, string) in enumerate(zip(ordered, strings)):
            roll_offset = repeated_seen[string] * ROLL_TICKS if rolled else 0
            repeated_seen[string] += 1
            start = note.start + roll_offset
            end = max(start + 1, note.end)
            score.append(ScoreNote(start, end, note.pitch, string + 1,
                                   rolled=int(roll_offset != 0),
                                   chord_size=len(group),
                                   voice=note.voice,
                                   lead=int(note is lead_note),
                                   chord_rank=len(group) - order - 1,
                                   source_slur=note.slur_from_previous,
                                   dotted_short=int(note.dotted_short)))
            last_pitch[string] = note.pitch
            last_voice_string[note.voice] = string

    # Bach closes with two D4s of different colour: stopped on G, then open D.
    final_ds = [note for note in score if note.pitch == 62
                and note.start == 767 * DIVISION]
    if len(final_ds) != 2:
        raise ValueError("unexpected final D pair")
    final_ds[0].string = 1
    final_ds[1].string = 2

    # A string cannot keep an older written value after a new finger lands.
    by_string: dict[int, list[ScoreNote]] = defaultdict(list)
    for note in score:
        by_string[note.string].append(note)
    for string_notes in by_string.values():
        string_notes.sort(key=lambda note: (note.start, note.pitch, note.end))
        for index in range(len(string_notes) - 1):
            current = string_notes[index]
            following = string_notes[index + 1]
            current.end = min(current.end, following.start)
            if current.end <= current.start:
                current.end = current.start + 1

    onsets: dict[int, list[ScoreNote]] = defaultdict(list)
    for note in score:
        written_start = note.start - (ROLL_TICKS if note.rolled else 0)
        onsets[written_start].append(note)
    direction = -1
    gesture = 0
    for tick, group in sorted(onsets.items()):
        beat = tick / DIVISION
        if not any(note.source_slur for note in group):
            direction *= -1
            gesture += 1
        for note in sorted(group, key=lambda item: (item.start, item.string, item.pitch)):
            note.direction = direction
            note.bow_group = gesture
            note.dynamic = min(
                0.92,
                dynamic_at(beat) + (0.055 if note.dotted_short else 0.0),
            )
            note.legato = int(note.source_slur or note.rolled != 0)
            duration = (note.end - note.start) / DIVISION
            open_pitch = OPEN_PITCHES[note.string - 1]
            if (note.pitch != open_pitch
                    and not note.dotted_short
                    and duration >= 0.25
                    and (note.chord_size == 1 or note.lead != 0)):
                if note.chord_size == 1 and duration >= 0.50:
                    depth = 11.0 + 15.5 * note.dynamic
                else:
                    depth = 7.5 + 11.5 * note.dynamic
                position = min(1.0, (note.pitch - open_pitch) / 12.0)
                note.vibrato_depth = max(
                    7.0,
                    min(26.0, depth * (
                        1.0 + 0.12 * performance_variation(note, "depth")
                    )),
                )
                note.vibrato_rate = max(
                    5.1,
                    min(
                        6.5,
                        5.25 + 0.45 * note.dynamic + 0.38 * position
                        + 0.28 * performance_variation(note, "rate"),
                    ),
                )

    score.sort(key=lambda note: (note.start, note.string, note.pitch, note.end))
    for gesture_id, note in enumerate(score, 1):
        note.gesture = gesture_id
    return score


def format_number(value: float) -> str:
    text = f"{value:.9f}".rstrip("0").rstrip(".")
    return text if text else "0"


def performance_variation(note: ScoreNote, name: str) -> float:
    payload = (
        f"{note.start}:{note.end}:{note.pitch}:{note.string}:"
        f"{note.voice}:{name}"
    ).encode("ascii")
    value = int.from_bytes(hashlib.sha256(payload).digest()[:8], "big")
    return 2.0 * value / (2**64 - 1) - 1.0


def render_score(score: list[ScoreNote]) -> str:
    stroke_starts: dict[int, tuple[int, int, int]] = {}
    for note in score:
        start, direction, chord_size = stroke_starts.get(
            note.bow_group, (note.start, note.direction, note.chord_size))
        if note.start < start:
            start = note.start
            chord_size = note.chord_size
        elif note.start == start:
            chord_size = max(chord_size, note.chord_size)
        stroke_starts[note.bow_group] = (start, direction, chord_size)
    ordered_strokes = sorted(
        (start, stroke_id, direction, chord_size)
        for stroke_id, (start, direction, chord_size) in stroke_starts.items()
    )
    strokes_at: dict[int, tuple[float, float, int, int, int]] = {}
    for index, (start, stroke_id, direction, chord_size) in enumerate(
            ordered_strokes):
        event_start = max(0.0, start / DIVISION - STROKE_LEAD_BEATS)
        event_end = (max(0.0, ordered_strokes[index + 1][0] / DIVISION
                         - STROKE_LEAD_BEATS)
                     if index + 1 < len(ordered_strokes)
                     else EXPECTED_BEATS)
        if event_end <= event_start:
            raise ValueError("bow stroke has no duration")
        strokes_at[start] = (
            event_start, event_end, direction, stroke_id, chord_size)

    lines = [
        "; Generated Bach Chaconne performance events. Do not edit by hand.",
        f"; written_notes={EXPECTED_NOTES} beats={format_number(EXPECTED_BEATS)} division={DIVISION}",
        "; BachStroke p4 bow +down/-up, p5 stroke ID, p6 opening chord size.",
        "; BachBar p4 written bar number.",
        "; p4 pitch, p5 string G/D/A/E=1/2/3/4, p6 bow +down/-up,",
        "; p7 legato, p8 dynamic, p9 vibrato cents, p10 vibrato Hz,",
        "; p11 gesture, p12 rolled, p13 written onset size,",
        "; p14 source voice 0..3, p15 written lead flag,",
        "; p16 chord rank from high to low, starting at zero,",
        "; p17 true for the short note after a written dotted note.",
        "",
    ]
    mark_index = 0
    current_measure = 0
    for note in score:
        beat = note.start / DIVISION
        while mark_index < len(MARKS) and MARKS[mark_index][0] <= beat + 1e-9:
            mark_beat, section = MARKS[mark_index]
            lines.append(f'i "BachMark" {format_number(mark_beat)} 0.001 {section}')
            mark_index += 1
        measure = measure_at(beat)
        if measure != current_measure:
            lines.append("")
            lines.append(f"; measure {measure}")
            lines.append(
                'i "BachBar" '
                f"{format_number(beat_for_measure(measure))} 0.001 {measure}"
            )
            current_measure = measure
        if note.start in strokes_at:
            stroke_start, stroke_end, direction, stroke_id, chord_size = \
                strokes_at.pop(note.start)
            lines.append(
                'i "BachStroke" '
                f"{format_number(stroke_start)} "
                f"{format_number(stroke_end - stroke_start)} "
                f"{direction} {stroke_id} {chord_size}"
            )
        duration = (note.end - note.start) / DIVISION
        lines.append(
            'i "BachNote" '
            f"{format_number(beat)} {format_number(duration)} "
            f"{note.pitch} {note.string} {note.direction} {note.legato} "
            f"{format_number(note.dynamic)} "
            f"{format_number(note.vibrato_depth)} "
            f"{format_number(note.vibrato_rate)} "
            f"{note.gesture} {note.rolled} {note.chord_size} "
            f"{note.voice} {note.lead} {note.chord_rank} "
            f"{note.dotted_short}"
        )
    while mark_index < len(MARKS):
        mark_beat, section = MARKS[mark_index]
        lines.append(f'i "BachMark" {format_number(mark_beat)} 0.001 {section}')
        mark_index += 1
    lines.append("")
    note_text = "\n".join(line for line in lines
                          if line.startswith('i "BachNote"')) + "\n"
    stroke_text = "\n".join(line for line in lines
                            if line.startswith('i "BachStroke"')) + "\n"
    digest = hashlib.sha256(note_text.encode("utf-8")).hexdigest()
    stroke_digest = hashlib.sha256(stroke_text.encode("utf-8")).hexdigest()
    lines.insert(2, f"; note_rows_sha256={digest}")
    lines.insert(3, f"; stroke_rows_sha256={stroke_digest}")
    return "\n".join(lines)


def parse_generated(path: Path) -> list[list[float]]:
    rows: list[list[float]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        match = NOTE_PATTERN.match(line)
        if not match:
            continue
        fields = match.group(1).split()
        if len(fields) != 16:
            raise ValueError(f"{path}:{line_number}: expected 16 note fields")
        try:
            rows.append([float(field) for field in fields])
        except ValueError as error:
            raise ValueError(f"{path}:{line_number}: invalid number") from error
    return rows


def check_generated(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    note_text = "\n".join(line for line in text.splitlines()
                          if line.startswith('i "BachNote"')) + "\n"
    stroke_text = "\n".join(line for line in text.splitlines()
                            if line.startswith('i "BachStroke"')) + "\n"
    digest = hashlib.sha256(note_text.encode("utf-8")).hexdigest()
    stroke_digest = hashlib.sha256(stroke_text.encode("utf-8")).hexdigest()
    if digest != EXPECTED_EVENT_DIGEST:
        raise ValueError("generated performance rows changed")
    if stroke_digest != EXPECTED_STROKE_DIGEST:
        raise ValueError("generated bow stroke rows changed")
    if f"; note_rows_sha256={digest}" not in text:
        raise ValueError("generated note digest header changed")
    if f"; stroke_rows_sha256={stroke_digest}" not in text:
        raise ValueError("generated stroke digest header changed")
    rows = parse_generated(path)
    if len(rows) != EXPECTED_NOTES:
        raise ValueError(f"expected {EXPECTED_NOTES} note rows, found {len(rows)}")
    pitches = [int(row[2]) for row in rows]
    strings = [int(row[3]) for row in rows]
    directions = [int(row[4]) for row in rows]
    voices = [int(row[12]) for row in rows]
    leads = [int(row[13]) for row in rows]
    chord_ranks = [int(row[14]) for row in rows]
    dotted_shorts = [int(row[15]) for row in rows]
    if min(pitches) != 55 or max(pitches) != 91:
        raise ValueError("generated pitch range changed")
    if any(string not in (1, 2, 3, 4) for string in strings):
        raise ValueError("a note lacks an exact violin string")
    if any(pitch < OPEN_PITCHES[string - 1]
           for pitch, string in zip(pitches, strings)):
        raise ValueError("a note is below its assigned open string")
    if set(strings) != {1, 2, 3, 4}:
        raise ValueError("the score must use all four strings")
    if any(voice not in (0, 1, 2, 3) for voice in voices):
        raise ValueError("a note lacks its LilyPond source voice")
    if any(lead not in (0, 1) for lead in leads):
        raise ValueError("a note has an invalid lead flag")
    if any(rank < 0 or rank >= int(row[11])
           for rank, row in zip(chord_ranks, rows)):
        raise ValueError("a note has an invalid chord rank")
    if any(value not in (0, 1) for value in dotted_shorts):
        raise ValueError("a note has an invalid dotted-short flag")
    if sum(dotted_shorts) != EXPECTED_DOTTED_SHORTS:
        raise ValueError("generated dotted-short accents changed")
    if any(int(row[15]) != 0 and (row[7] != 0.0 or row[8] != 0.0)
           for row in rows):
        raise ValueError("a dotted short note has vibrato")
    for row in rows:
        eligible = (
            int(row[2]) != OPEN_PITCHES[int(row[3]) - 1]
            and int(row[15]) == 0
            and row[1] >= 0.25
            and (int(row[11]) == 1 or int(row[13]) != 0)
        )
        if (row[7] > 0.0) != eligible:
            raise ValueError("a note has the wrong vibrato eligibility")
    for string in range(1, 5):
        string_rows = sorted((row for row in rows if int(row[3]) == string),
                             key=lambda row: (row[0], row[2]))
        for previous, current in zip(string_rows, string_rows[1:]):
            if previous[0] + previous[1] > current[0] + 1e-8:
                raise ValueError(f"overlapping notes claim string {string}")
    if set(directions) != {-1, 1}:
        raise ValueError("both bow directions must occur")
    onset_directions: dict[float, set[int]] = defaultdict(set)
    for row in rows:
        onset_directions[row[0]].add(int(row[4]))
    if any(len(values) != 1 for values in onset_directions.values()):
        raise ValueError("one written onset has conflicting bow directions")
    onset_leads: dict[float, int] = defaultdict(int)
    onset_sizes: Counter[float] = Counter()
    for row in rows:
        written_onset = row[0] - (
            ROLL_TICKS / DIVISION if int(row[10]) != 0 else 0.0)
        onset_leads[written_onset] += int(row[13])
        onset_sizes[written_onset] += 1
    if any(count != 1 for count in onset_leads.values()):
        raise ValueError("each written onset must have one lead note")
    if sum(size > 1 for size in onset_sizes.values()) != EXPECTED_CHORD_ONSETS:
        raise ValueError("written chord onset count changed")
    strokes = []
    for line_number, line in enumerate(text.splitlines(), 1):
        match = STROKE_PATTERN.match(line)
        if not match:
            continue
        fields = match.group(1).split()
        if len(fields) != 5:
            raise ValueError(
                f"{path}:{line_number}: expected 5 stroke fields")
        strokes.append([float(field) for field in fields])
    if len(strokes) != EXPECTED_STROKES:
        raise ValueError(
            f"expected {EXPECTED_STROKES} bow strokes, found {len(strokes)}")
    for index, row in enumerate(strokes):
        start, duration, direction, stroke_id, chord_size = row
        if int(stroke_id) != index + 1:
            raise ValueError("bow stroke IDs are not contiguous")
        if int(direction) != (1 if index % 2 == 0 else -1):
            raise ValueError("bow strokes do not alternate direction")
        if int(chord_size) not in (1, 2, 3, 4) or duration <= 0:
            raise ValueError("bow stroke has invalid score facts")
        if index and abs(strokes[index - 1][0] +
                         strokes[index - 1][1] - start) > 1e-8:
            raise ValueError("bow strokes leave a gap or overlap")
    if strokes[0][0] != 0 or abs(
            strokes[-1][0] + strokes[-1][1] - EXPECTED_BEATS) > 1e-8:
        raise ValueError("bow strokes do not cover the full score")
    bars = []
    for line_number, line in enumerate(text.splitlines(), 1):
        match = BAR_PATTERN.match(line)
        if not match:
            continue
        fields = match.group(1).split()
        if len(fields) != 3:
            raise ValueError(
                f"{path}:{line_number}: expected 3 bar fields")
        bars.append([float(field) for field in fields])
    if len(bars) != EXPECTED_BARS:
        raise ValueError(
            f"expected {EXPECTED_BARS} bar rows, found {len(bars)}")
    for index, (start, duration, bar) in enumerate(bars, 1):
        if (int(bar) != index
                or abs(start - beat_for_measure(index)) > 1e-8
                or abs(duration - 0.001) > 1e-12):
            raise ValueError("bar markers do not match the written score")
    opening = [row for row in rows if row[0] < 2.0]
    if (len(opening) != 4
            or [(row[0], row[1], int(row[2]), int(row[4])) for row in opening]
            != [(0.0, 2.0, 62, 1), (0.0, 2.0, 65, 1),
                (0.0, 1.5, 69, 1), (1.5, 0.5, 69, -1)]):
        raise ValueError("opening chord re-attack changed")
    if [int(row[15]) for row in opening] != [0, 0, 0, 1]:
        raise ValueError("opening dotted-short accent changed")
    if sum(int(row[5]) for row in rows) != 641:
        raise ValueError("written slur and rolled-note links changed")
    if sum(row[7] > 0.0 for row in rows) != EXPECTED_VIBRATO_NOTES:
        raise ValueError("generated vibrato coverage changed")
    if sum(int(row[10]) for row in rows) != 2:
        raise ValueError("the two required rolled notes changed")
    if any(not 0.20 <= row[6] <= 0.95 for row in rows):
        raise ValueError("dynamic value is out of range")
    if any(row[7] < 0.0 or row[7] > 26.0 for row in rows):
        raise ValueError("vibrato depth is out of range")
    if any(row[7] > 0.0 and not 5.1 <= row[8] <= 6.5 for row in rows):
        raise ValueError("vibrato rate is out of range")
    vibrato_depths = {round(row[7], 6) for row in rows if row[7] > 0.0}
    vibrato_rates = {round(row[8], 6) for row in rows if row[7] > 0.0}
    if len(vibrato_depths) < 1000 or len(vibrato_rates) < 1000:
        raise ValueError("generated vibrato variation collapsed")
    if max(row[0] + row[1] for row in rows) != EXPECTED_BEATS:
        raise ValueError("generated score length changed")
    final = [row for row in rows if int(row[2]) == 62 and row[0] == 767.0]
    if len(final) != 2 or [int(row[3]) for row in final] != [1, 2]:
        raise ValueError("final D4 pair must move from G to open D")
    csd_path = path.with_name("bach_chaconne.csd")
    if csd_path.exists():
        csd = csd_path.read_text(encoding="utf-8")
        flat_csd = " ".join(csd.replace("\\\n", " ").split())
        bar_block = csd.split("instr BachBar", 1)[-1].split("endin", 1)[0]
        stroke_block = csd.split("instr BachStroke", 1)[-1].split(
            "endin", 1
        )[0]
        note_block = csd.split("instr BachNote", 1)[-1].split("endin", 1)[0]
        if ("instr BachStroke" not in csd
                or "instr BachBar" not in csd
                or '#include "bach_chaconne_stroke.inc"' not in csd
                or '#include "violin_distance.inc"' not in csd
                or ("HlolBachStrokeShape kPhase, iChordSize"
                    not in flat_csd)
                or ("kBaseFrequency HlolBachPitchTransition "
                    "gkFrequency[iString]"
                    not in flat_csd)
                or "if $SHOW_BARS != 0 then" not in bar_block
                or 'printf_i "BAR %d\\n", 1, iBar' not in csd
                or "if iStrokeId >= gkStrokeId then" not in stroke_block
                or "gkBowDirection = iDirection" not in stroke_block
                or "gkBowDirection = iDirection" in note_block
                or csd.count("gkBowDirection = iDirection") != 1
                or "gkVoice[kScan] < kLeadVoice" not in csd
                or "gkLead[kScan] > kLeadMarked" not in csd
                or "gkGestureId[kScan] > kLeadGesture" not in csd
                or "gkStrokeGate = kContact" not in flat_csd
                or "kAttach" in stroke_block
                or "kSpeed * gkStrokeSpeed * kVoiceSpeed" not in flat_csd
                or "kForce * gkStrokeForce * kVoiceForce" not in flat_csd
                or ("kStrokeTrigger = gkTrigger[iString] * gkStrokeGate * "
                    "gkChordContact[iString]") not in flat_csd
                or ("kChordContact HlolBachChordContact p3, iChordSize, "
                    "iChordRank, iLead") not in flat_csd
                or "iChordFloor" in note_block
                or "kVoiceForce = 1.08" not in csd
                or "kVoiceSpeed = 1.04" not in csd
                or "kVoiceForce = 1.00" not in csd
                or "kVoiceSpeed = 1.00" not in csd
                or "kVoiceForce = 0.94" not in csd
                or "kVoiceSpeed = 0.96" not in csd
                or "kVoiceForce = 0.88" not in csd
                or "kVoiceSpeed = 0.93" not in csd
                or "iDottedShort = int(p17)" not in note_block
                or "gkTrigger[iString] = iTriggerLevel" not in note_block
                or "kGate" in note_block
                or "gkDottedShort[iString] = iDottedShort" not in note_block
                or "kForce * 1.10" not in csd
                or "kSpeed * 1.08" not in csd
                or "iVibratoDepth = p9 * $VIBRATO_LEVEL" not in note_block
                or "iDelay = min(0.42" not in note_block
                or "iRise = min(0.25" not in note_block
                or "HlolBachHumanVibrato" not in csd
                or "rspline" not in csd
                or "aRoomLeft, aRoomRight ftconv" not in flat_csd
                or "HlolViolinDistance" not in csd
                or "$VIOLIN_DISTANCE_METERS" not in csd
                or 'alwayson "Listener"' not in csd
                or 'alwayson "Room"' not in csd
                or csd.count("alwayson giStringControllerInstr + 0.0") != 4
                or 'alwayson "StringController"' in csd
                or "gaAudible += 1" not in csd
                or "gaAudible * tanh" not in flat_csd
                or "kSpeed = -(0.27 + 0.43 * kDynamic)" not in csd):
            raise ValueError("the shared physical bow-direction path changed")
    print(
        f"PASS: {len(rows)} notes, {sum(int(row[5]) for row in rows)} legato links, "
        f"{sum(row[7] > 0.0 for row in rows)} vibrato notes, "
        f"{sum(int(row[15]) for row in rows)} dotted shorts, exact strings"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--lilypond", type=Path, help="input LilyPond score")
    group.add_argument("--check", type=Path, help="check a generated include")
    parser.add_argument("--output", type=Path, help="output Csound include")
    args = parser.parse_args()
    try:
        if args.check is not None:
            if args.output is not None:
                parser.error("--output cannot be used with --check")
            check_generated(args.check)
            return 0
        if args.output is None:
            parser.error("--output is required with --lilypond")
        score = build_score(parse_lilypond(args.lilypond))
        args.output.write_text(render_score(score), encoding="utf-8")
        check_generated(args.output)
        return 0
    except (OSError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
