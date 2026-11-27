#!/usr/bin/env python3
"""Mark optional continuous phrases in the fixed Chaconne performance."""

from __future__ import annotations

import argparse
from bisect import bisect_right
from collections import defaultdict
from pathlib import Path

from generate_bach_chaconne_demo import DIVISION, measure_at, parse_generated
from play_bach_chaconne import Stroke, parse_score, parse_tempo, seconds_at


ROOT = Path(__file__).resolve().parents[1]
# These melodic variations can use longer bow spans. Chords retain their rolls.
PASSAGES = ((33, 56), (65, 88), (121, 124), (153, 164),
            (217, 228), (241, 248))


def phrase_plan(rows: list[list[float]]) -> list[list[list[float]]]:
    phrases = []
    chain: list[list[float]] = []
    for index, row in enumerate(rows):
        bar = measure_at(row[0])
        passage = next(((first, last) for first, last in PASSAGES
                        if first <= bar <= last), None)
        solo = row[11] == 1 and row[10] == 0 and row[15] == 0
        start, end = round(row[0] * DIVISION), round((row[0] + row[1]) * DIVISION)
        solo = solo and not any(
            other_index != index
            and round(other[0] * DIVISION) < end
            and round((other[0] + other[1]) * DIVISION) > start
            for other_index, other in enumerate(rows))
        joins = False
        if chain and passage and solo:
            previous = chain[-1]
            previous_bar = measure_at(previous[0])
            joins = (
                round((previous[0] + previous[1]) * DIVISION) == start
                and previous[3] == row[3] and previous[12] == row[12]
                and (previous[2] != row[2] or row[5] != 0)
                and passage[0] <= previous_bar <= passage[1]
                and ((bar - passage[0]) // 4 == (previous_bar - passage[0]) // 4
                     or row[5] != 0))
        if not joins:
            if len(chain) > 1:
                phrases.append(chain)
            chain = []
        if passage and solo:
            chain.append(row)
    if len(chain) > 1:
        phrases.append(chain)
    # A selected passage must not put a new attack inside a written slur.
    membership = {int(row[9]): index for index, phrase in enumerate(phrases)
                  for row in phrase}
    voices = defaultdict(list)
    for row in rows:
        voices[(row[3], row[12])].append(row)
    blocked = set()
    for voice in voices.values():
        for left, right in zip(voice, voice[1:]):
            if right[5] == 0 or round((left[0] + left[1]) * DIVISION) != round(right[0] * DIVISION):
                continue
            before, after = membership.get(int(left[9])), membership.get(int(right[9]))
            if before != after:
                blocked.update(index for index in (before, after) if index is not None)
    return [phrase for index, phrase in enumerate(phrases) if index not in blocked]


def repeated_stroke_releases(rows: list[list[float]]) -> list[int]:
    previous_by_string = {}
    releases = []
    for row in rows:
        previous = previous_by_string.get(row[3])
        if (previous is not None and previous[2] == row[2] and row[5] == 0
                and round((previous[0] + previous[1]) * DIVISION)
                == round(row[0] * DIVISION)):
            releases.append(int(previous[9]))
        previous_by_string[row[3]] = row
    return releases


def chord_support_releases(rows: list[list[float]],
                           strokes: list[Stroke]) -> dict[int, int]:
    starts = [stroke.start for stroke in strokes]
    notes_at = defaultdict(list)
    for note in rows:
        notes_at[round(note[0] * DIVISION)].append(note)

    releases = {}
    for lead in rows:
        if lead[11] < 3 or not lead[13] or lead[14] != 0:
            continue
        boundary = round((lead[0] + lead[1]) * DIVISION)
        incoming = notes_at.get(boundary, [])
        if len(incoming) != 1:
            continue
        repeat = incoming[0]
        if (repeat[11] != 1 or repeat[5] or repeat[2:4] != lead[2:4]
                or repeat[12] != lead[12] or repeat[4] == lead[4]):
            continue
        index = bisect_right(starts, repeat[0] + 1e-8) - 1
        if index < 0:
            continue
        stroke = strokes[index]
        if stroke.chord_size != 1 or not 0 <= repeat[0] - stroke.start <= .012:
            continue
        for support in notes_at[round(lead[0] * DIVISION)]:
            if (support[3] == lead[3] - 1 and support[14] == 1
                    and support[11] == lead[11]
                    and round((support[0] + support[1]) * DIVISION) >= boundary):
                releases[int(support[9])] = stroke.stroke_id
    return releases


def bow_spans(rows: list[list[float]], phrases: list[list[list[float]]],
              strokes: list[Stroke]) -> list[list[list[float]]]:
    joined = {int(row[9]): int(phrase[0][9])
              for phrase in phrases for row in phrase}
    starts = [stroke.start for stroke in strokes]
    spans = defaultdict(list)
    for row in sorted(rows, key=lambda note: (note[0], note[0] + note[1], note[9])):
        start, duration = row[:2]
        gesture, string = int(row[9]), int(row[3])
        if row[11] != 1 or row[15] != 0:
            continue
        stroke_index = bisect_right(starts, start + 1e-8) - 1
        stroke = strokes[stroke_index] if stroke_index >= 0 else None
        if gesture in joined:
            key = ("phrase", joined[gesture])
        elif stroke and stroke.chord_size == 1 and start + duration <= stroke.end + .02:
            key = ("stroke", stroke.stroke_id, string)
        else:
            key = ("note", gesture)
        spans[key].append(row)
    return list(spans.values())


def render_plan(rows: list[list[float]], strokes: list[Stroke],
                tempo: list[tuple[float, float]]) -> str:
    phrases = phrase_plan(rows)
    size = 1 + max(int(row[9]) for row in rows)
    lines = [
        "; Generated by tools/generate_bach_phrases.py. Do not edit by hand.",
        "; A signed phrase ID selects its bow direction. Join=1 holds to the next note.",
        f"giBachPhrase[] init {size}",
        f"giBachJoinNext[] init {size}",
    ]
    for number, phrase in enumerate(phrases, 1):
        direction = int(phrase[0][4])
        lines.append(f"; phrase {number}, bar {measure_at(phrase[0][0])}")
        for index, row in enumerate(phrase):
            gesture = int(row[9])
            lines.append(f"giBachPhrase[{gesture}] = {number * direction}")
            if index + 1 < len(phrase):
                lines.append(f"giBachJoinNext[{gesture}] = 1")
    lines.extend((
        "",
        "; Release the bow before a separate stroke on the same pitch.",
        f"giBachRepeatNext[] init {size}",
    ))
    for gesture in repeated_stroke_releases(rows):
        lines.append(f"giBachRepeatNext[{gesture}] = 1")
    lines.extend((
        "",
        "; Hold the upper pair of a rolled chord until the bare repeat starts.",
        f"giBachSupportUntilStroke[] init {size}",
    ))
    for gesture, stroke in chord_support_releases(rows, strokes).items():
        lines.append(f"giBachSupportUntilStroke[{gesture}] = {stroke}")
    lines.extend((
        "",
        "; Bow timing in seconds at the demo tempo. The first gesture names the span.",
        f"giBachBowSpan[] init {size}",
        f"giBachBowElapsed[] init {size}",
        f"giBachBowDuration[] init {size}",
        f"giBachBowJoined[] init {size}",
    ))
    for span in bow_spans(rows, phrases, strokes):
        start = seconds_at(span[0][0], tempo)
        end = seconds_at(max(row[0] + row[1] for row in span), tempo)
        if end - start <= .22:
            continue
        anchor = int(span[0][9])
        lines.append(f"giBachBowDuration[{anchor}] = {end - start:.9f}")
        if len(span) > 1:
            lines.append(f"giBachBowJoined[{anchor}] = 1")
        for row in span:
            gesture = int(row[9])
            lines.append(f"giBachBowSpan[{gesture}] = {anchor}")
            if row[0] > span[0][0]:
                offset = seconds_at(row[0], tempo) - start
                lines.append(f"giBachBowElapsed[{gesture}] = {offset:.9f}")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    examples = ROOT / "examples"
    score = examples / "bach_chaconne_score.inc"
    rows = parse_generated(score)
    _, strokes = parse_score(score)
    tempo = parse_tempo(examples / "bach_chaconne_performance.inc")
    output = examples / "bach_chaconne_phrases.inc"
    expected = render_plan(rows, strokes, tempo)
    if args.check:
        if not output.exists() or output.read_text() != expected:
            parser.exit(1, "Chaconne phrase data needs regeneration\n")
    else:
        output.write_text(expected)
    phrases = phrase_plan(rows)
    print(f"Chaconne: {len(phrases)} phrases, "
          f"{sum(len(phrase) - 1 for phrase in phrases)} joined boundaries")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
