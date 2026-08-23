#!/usr/bin/env python3
"""Build and check the Csound event list for Paganini's Caprice No. 24.

The Mutopia MIDI supplies most note timing, but its assembly omits Variation V
and treats all of Variation IX as pizzicato. This script restores Variation V
from the LilyPond notation and applies left-hand pizzicato only to notes marked
with a circle in Variation IX.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import math
import os
import re
import shutil
import sys
import tempfile
import unicodedata
from collections import Counter, defaultdict, deque
from dataclasses import dataclass
from pathlib import Path
from typing import Deque, Dict, Iterable, List, Optional, Sequence, Tuple


MIDI_SHA256 = "b74930766d3c2735e58ec568b727ac574a098fa880ea27353eb0546ebd10b662"
EXPECTED_DIVISION = 384
EXPECTED_MIDI_NOTES = 1593
EXPECTED_SAME_STRING_SLUR_LINKS = 180
EXPECTED_VARIATION_IX_BOWED = 48
EXPECTED_LEFT_HAND_PIZZICATO = 75
EXPECTED_SAME_STRING_PIZZICATO_REATTACKS = 25
EXPECTED_HARMONIC_PRACTICE_NOTES = 88
EXPECTED_HARMONIC_PRACTICE_ORDERS = {2: 6, 3: 7, 4: 75}
EXPECTED_HARMONIC_PRACTICE_STRINGS = {1: 24, 2: 33, 3: 28, 4: 3}
EXPECTED_HARMONIC_PRACTICE_NATURALS = 24
HARMONIC_NATURAL_TOLERANCE_SEMITONES = 0.01
HARMONIC_PLAYABLE_EPSILON_SEMITONES = 1.0e-9
SOFT_BOW_TEST_VELOCITY = 35
MINIMUM_SOFT_BOW_CONTACT = 0.40
INSERT_BEAT = 160.0
INSERT_LENGTH = 32.0
END_BEAT = 441.4375

STACCATO = 1
ACCENT = 2
SLUR = 4
GRACE = 8
CHORD = 16
LEFT_HAND_PIZZICATO = 32
TRILL = 64
HARMONIC_OPTION = 256

STRING_OPEN_MIDI = {1: 55, 2: 62, 3: 69, 4: 76}
SECTION_STARTS = (
    (0.0, 0, "TEMA"),
    (32.0, 1, "VAR. I"),
    (64.0, 2, "VAR. II"),
    (96.0, 3, "VAR. III"),
    (128.0, 4, "VAR. IV"),
    (160.0, 5, "VAR. V"),
    (192.0, 6, "VAR. VI"),
    (224.0, 7, "VAR. VII"),
    (272.0, 8, "VAR. VIII"),
    (319.0, 9, "VAR. IX"),
    (351.0, 10, "VAR. X"),
    (383.0, 11, "VAR. XI"),
    (413.0, 12, "FINALE"),
)

EXPECTED_MARK_BEATS = {
    **{section: beat for beat, section, _ in SECTION_STARTS},
    1: 31.0 + 362.0 / EXPECTED_DIVISION,
    13: 429.0,
    14: END_BEAT,
}

SOURCE_ACCENT_BEATS = {
    0: (6.0, 14.0, 30.0),
    1: (32.0, 34.0, 36.0, 38.0, 40.0, 42.0, 44.0, 46.0, 62.0),
    3: (
        98.0, 102.0, 102.5, 103.0, 103.5,
        106.0, 110.0, 110.5, 111.0, 111.5,
        114.0, 114.5, 115.0, 115.5,
        118.0, 118.5, 119.0, 119.5,
    ),
    7: (225.0, 231.0, 237.0, 243.0, 249.0, 255.0, 261.0, 264.0),
}

SOURCE_STACCATO_BEATS = {
    0: (0.0, 0.75, 8.0, 8.75),
    3: (99.0, 107.0),
    4: (135.5, 143.5),
}

EXPECTED_SECTION_FLAG_COUNTS = {
    (0, STACCATO): 4,
    (0, ACCENT): 3,
    (0, SLUR): 56,
    (1, STACCATO): 36,
    (1, ACCENT): 9,
    (1, SLUR): 47,
    (2, ACCENT): 0,
    (2, SLUR): 40,
    (3, STACCATO): 4,
    (3, ACCENT): 36,
    (4, STACCATO): 2,
    (5, ACCENT): 12,
    (5, SLUR): 90,
    (7, ACCENT): 8,
    (7, SLUR): 81,
    (9, STACCATO): 0,
    (9, ACCENT): 0,
    (9, SLUR): 0,
    (9, LEFT_HAND_PIZZICATO): EXPECTED_LEFT_HAND_PIZZICATO,
    (10, HARMONIC_OPTION): EXPECTED_HARMONIC_PRACTICE_NOTES,
    (12, STACCATO): 0,
    (12, ACCENT): 0,
    (12, SLUR): 156,
}


@dataclass
class Note:
    start: int
    duration: int
    pitch: int
    velocity: int
    order: int
    section: int = -1
    flags: int = 0
    string: int = 0

    @property
    def end(self) -> int:
        return self.start + self.duration


def read_vlq(data: bytes, offset: int) -> Tuple[int, int]:
    value = 0
    while True:
        if offset >= len(data):
            raise ValueError("truncated MIDI variable-length value")
        byte = data[offset]
        offset += 1
        value = (value << 7) | (byte & 0x7F)
        if byte < 0x80:
            return value, offset


def parse_midi(path: Path) -> Tuple[int, List[Note]]:
    data = path.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    if digest != MIDI_SHA256:
        raise ValueError(
            "unexpected MIDI file; use Mutopia Caprice_24.mid "
            f"with SHA-256 {MIDI_SHA256}")
    if data[:4] != b"MThd" or len(data) < 14:
        raise ValueError("not a Standard MIDI file")
    header_size = int.from_bytes(data[4:8], "big")
    track_count = int.from_bytes(data[10:12], "big")
    division = int.from_bytes(data[12:14], "big")
    if division != EXPECTED_DIVISION:
        raise ValueError(f"unexpected MIDI division {division}")

    offset = 8 + header_size
    midi_events: List[Tuple[int, int, int, bytes, int]] = []
    event_order = 0
    for _ in range(track_count):
        if data[offset:offset + 4] != b"MTrk":
            raise ValueError("missing MIDI track header")
        size = int.from_bytes(data[offset + 4:offset + 8], "big")
        track = data[offset + 8:offset + 8 + size]
        offset += 8 + size
        position = 0
        tick = 0
        running_status = None
        while position < len(track):
            delta, position = read_vlq(track, position)
            tick += delta
            status = track[position]
            if status < 0x80:
                if running_status is None:
                    raise ValueError("MIDI running status without a status byte")
                status = running_status
            else:
                position += 1
                if status < 0xF0:
                    running_status = status
            if status == 0xFF:
                position += 1
                length, position = read_vlq(track, position)
                position += length
            elif status in (0xF0, 0xF7):
                length, position = read_vlq(track, position)
                position += length
            else:
                kind = status & 0xF0
                channel = status & 0x0F
                count = 1 if kind in (0xC0, 0xD0) else 2
                payload = track[position:position + count]
                position += count
                midi_events.append((tick, kind, channel, payload, event_order))
                event_order += 1

    active: Dict[Tuple[int, int], Deque[Tuple[int, int, int]]] = defaultdict(deque)
    notes: List[Note] = []
    for tick, kind, channel, payload, order in midi_events:
        if kind == 0x90 and payload[1] != 0:
            active[(channel, payload[0])].append((tick, payload[1], order))
        elif kind == 0x80 or (kind == 0x90 and payload[1] == 0):
            key = (channel, payload[0])
            if not active[key]:
                raise ValueError(f"unmatched note-off at tick {tick}")
            start, velocity, note_order = active[key].popleft()
            notes.append(Note(
                start=start,
                duration=tick - start,
                pitch=payload[0],
                velocity=velocity,
                order=note_order,
            ))
    if any(queue for queue in active.values()):
        raise ValueError("MIDI contains notes without note-off events")
    if len(notes) != EXPECTED_MIDI_NOTES:
        raise ValueError(
            f"MIDI contained {len(notes)} notes, expected {EXPECTED_MIDI_NOTES}")
    return division, notes


VARIATION_V_BARS: Sequence[Tuple[Sequence[int], Sequence[int]]] = (
    ((57, 77, 65, 76, 64, 57),
     (ACCENT, SLUR, SLUR, SLUR, SLUR, ACCENT | SLUR)),
    ((56, 87, 74, 88, 76, 56),
     (SLUR, SLUR, SLUR, SLUR, SLUR, ACCENT | SLUR)),
    ((57, 77, 65, 76, 64, 57),
     (SLUR, SLUR, SLUR, SLUR, SLUR, ACCENT | SLUR)),
    ((56, 87, 74, 88, 76), (SLUR, SLUR, SLUR, SLUR, SLUR)),
    ((61, 94, 83, 93, 81, 61),
     (0, SLUR, SLUR, SLUR, SLUR, ACCENT | SLUR)),
    ((62, 76, 64, 77, 65, 60),
     (SLUR, SLUR, SLUR, SLUR, SLUR, ACCENT | SLUR)),
    ((59, 92, 81, 91, 79, 59),
     (SLUR, SLUR, SLUR, SLUR, SLUR, ACCENT | SLUR)),
    ((60, 75, 62, 76, 64, 61),
     (SLUR, SLUR, SLUR, SLUR, SLUR, ACCENT | SLUR)),
    ((62, 83, 71, 82, 71, 62), (SLUR,) * 6),
    ((64, 80, 67, 81, 69, 65), (SLUR,) * 6),
    ((62, 89, 77, 88, 76, 64), (SLUR,) * 6),
    ((57, 84, 72, 81, 69), (SLUR,) * 5),
)


def variation_v_notes(division: int, first_order: int) -> List[Note]:
    eighth = division // 2
    sixteenth = division // 4
    bar_ticks = division * 2
    expanded = list(VARIATION_V_BARS[:4]) * 2 + list(VARIATION_V_BARS[4:])
    notes: List[Note] = []
    order = first_order
    start_tick = int(INSERT_BEAT * division)
    for bar_index, (pitches, source_flags) in enumerate(expanded):
        onsets = [0, eighth, eighth + sixteenth,
                  eighth + 2 * sixteenth, eighth + 3 * sixteenth]
        durations = [eighth, sixteenth, sixteenth, sixteenth, sixteenth]
        if len(pitches) == 6:
            onsets.append(eighth + 4 * sixteenth)
            durations.append(eighth)
        for pitch, onset, duration, flags in zip(
                pitches, onsets, durations, source_flags):
            notes.append(Note(
                start=start_tick + bar_index * bar_ticks + onset,
                duration=duration,
                pitch=pitch,
                velocity=81,
                order=order,
                section=5,
                flags=flags,
            ))
            order += 1
    if len(notes) != 93:
        raise AssertionError(f"Variation V has {len(notes)} notes, expected 93")
    return notes


def section_for_beat(beat: float) -> int:
    section = 0
    for start, candidate, _ in SECTION_STARTS:
        if beat < start:
            break
        section = candidate
    return section


VARIATION_IX_PIZZICATO = tuple(
    value
    for bar in (
        (0, 1, 1, 0, 1, 0, 1, 1),
        (0, 1, 1, 0, 1, 1, 0, 1),
        (0, 1, 1, 0, 1, 0, 1, 1),
        (0, 1, 1, 1, 1, 0, 1),
    ) * 2 + (
        (0, 1, 1, 0, 0, 1, 0, 1),
        (0, 1, 0, 1, 0, 1, 0, 1),
        (0, 1, 1, 1, 0, 1, 0, 1),
        (0, 1, 0, 1, 0, 1, 0, 1),
        (0, 1, 1, 0, 1, 0, 1, 1),
        (1, 0, 1, 1, 1, 0, 1, 1),
        (0, 1, 0, 1, 0, 1, 0, 1),
        (0, 1, 0, 1, 1),
    )
    for value in bar
)


def restore_complete_score(division: int, midi_notes: List[Note]) -> List[Note]:
    insert_tick = int(INSERT_BEAT * division)
    shift = int(INSERT_LENGTH * division)
    for note in midi_notes:
        if note.start >= insert_tick:
            note.start += shift
        beat = note.start / division
        note.section = section_for_beat(beat)
        for section_start, candidate, _ in SECTION_STARTS[1:]:
            if (0 < section_start - beat <= 0.125 and
                    note.duration <= division // 16):
                note.section = candidate
                break
    first_order = max(note.order for note in midi_notes) + 1
    notes = midi_notes + variation_v_notes(division, first_order)
    return sorted(notes, key=lambda note: (note.start, note.order, note.pitch))


def annotate(notes: List[Note], division: int) -> None:
    onset_counts = Counter(note.start for note in notes)
    for note in notes:
        if note.section == 9:
            # The printed score carries forte from Variation VIII. Mutopia's
            # separate MIDI expression falls back to its default velocity.
            note.velocity = 101
    for note in notes:
        if onset_counts[note.start] > 1:
            note.flags |= CHORD
        if note.duration <= division // 16:
            note.flags |= GRACE
        beat = note.start / division
        if any(
                abs(beat - marked) < 1.0e-8
                for marked in SOURCE_ACCENT_BEATS.get(note.section, ())):
            note.flags |= ACCENT
        if any(
                abs(beat - marked) < 1.0e-8
                for marked in SOURCE_STACCATO_BEATS.get(note.section, ())):
            note.flags |= STACCATO
        if (note.section == 1 and note.duration > division // 16 and (
                32.0 <= beat < 38.0 or 40.0 <= beat < 46.0)):
            # The first three repeated triplet bars carry printed dots.
            note.flags |= STACCATO
        if note.section == 10:
            note.flags |= HARMONIC_OPTION
        if (note.section == 12 and 437.0 <= beat < 441.0 and
                note.pitch in (57, 59)):
            note.flags |= TRILL

    pizzicato_notes = [note for note in notes if note.section == 9]
    pizzicato_notes.sort(key=lambda note: (note.start, note.order))
    if len(pizzicato_notes) != len(VARIATION_IX_PIZZICATO):
        raise ValueError(
            "Variation IX note count did not match the printed circle mask: "
            f"{len(pizzicato_notes)} != {len(VARIATION_IX_PIZZICATO)}")
    for note, marked in zip(pizzicato_notes, VARIATION_IX_PIZZICATO):
        if marked:
            note.flags |= LEFT_HAND_PIZZICATO
    annotate_source_slurs(notes, division)


def annotate_source_slurs(notes: List[Note], division: int) -> None:
    def beat_of(note: Note) -> float:
        return note.start / division

    def at(left: float, right: float) -> bool:
        return abs(left - right) < 1.0e-8

    theme_beats = set()
    for base in (0.0, 8.0):
        for offset in (1.0, 3.0, 5.0):
            theme_beats.update(
                base + offset + step for step in (0.0, 0.25, 0.5, 0.75))
        theme_beats.update((base + 6.0, base + 7.0))
    for base in (16.0, 18.0, 20.0, 22.0, 24.0, 26.0, 28.0):
        theme_beats.update(
            base + 1.0 + step for step in (0.0, 0.25, 0.5, 0.75))
    for note in notes:
        beat = beat_of(note)
        if note.section == 0 and any(at(beat, marked) for marked in theme_beats):
            note.flags |= SLUR

    variation_one = sorted(
        (note for note in notes if note.section == 1),
        key=lambda note: (note.start, note.order, note.pitch),
    )
    bar_counts = [8, 8, 8, 2, 8, 8, 8, 2] + [8] * 7 + [2]
    slur_indices = [
        set(range(8)), {0, 1}, {0, 1}, {0, 1},
        set(range(8)), {0, 1}, {0, 1}, {0, 1},
        {0, 1}, {0, 1}, {0, 1}, {0, 1}, {0, 1}, {0, 1},
        {0, 1, 2, 3, 4}, {0, 1},
    ]
    if sum(bar_counts) != len(variation_one):
        raise ValueError(
            f"Variation I has {len(variation_one)} notes, expected 110")
    offset = 0
    for count, marked_indices in zip(bar_counts, slur_indices):
        for index, note in enumerate(variation_one[offset:offset + count]):
            if index in marked_indices:
                note.flags |= SLUR
        offset += count

    for note in notes:
        beat = beat_of(note)
        if note.section == 2 and (
                64.0 <= beat < 68.0 or 72.0 <= beat < 76.0 or
                any(at(beat, marked) for marked in (94.0, 94.25, 94.5, 94.75))):
            note.flags |= SLUR

        if note.section == 7:
            marked = False
            for base in (224.0, 236.0):
                for phrase in (base, base + 6.0):
                    for triplet in (phrase, phrase + 2.0):
                        if any(at(beat, triplet + step)
                               for step in (0.0, 1.0 / 3.0, 2.0 / 3.0)):
                            marked = True
                    if phrase + 3.0 <= beat <= phrase + 5.25:
                        marked = True
            if any(at(beat, 248.0 + step) for step in (
                    0.0, 1.0 / 3.0, 2.0 / 3.0,
                    2.0, 2.0 + 1.0 / 3.0, 2.0 + 2.0 / 3.0)):
                marked = True
            if 251.0 <= beat < 254.0:
                marked = True
            if any(at(beat, 270.0 + step)
                   for step in (0.0, 1.0 / 3.0, 2.0 / 3.0)):
                marked = True
            if marked:
                note.flags |= SLUR

        if note.section == 12 and (
                413.0 <= beat < 418.0 or 421.0 <= beat < 426.0 or
                429.0 <= beat < 441.0 or at(beat, 441.0)):
            note.flags |= SLUR


def preferred_string(pitch: int) -> int:
    if pitch >= STRING_OPEN_MIDI[4]:
        return 4
    if pitch >= STRING_OPEN_MIDI[3]:
        return 3
    if pitch >= STRING_OPEN_MIDI[2]:
        return 2
    return 1


def practice_harmonic_assignment(
    pitch: int,
) -> Optional[Tuple[int, int, float]]:
    """Return the highest valid order up to four and its highest string."""
    for order in range(4, 1, -1):
        fundamental = pitch - 12.0 * math.log2(order)
        playable = [
            string for string, open_pitch in STRING_OPEN_MIDI.items()
            if fundamental >= (
                open_pitch - HARMONIC_PLAYABLE_EPSILON_SEMITONES)
        ]
        if playable:
            return order, max(playable), fundamental
    return None


def validate_harmonic_practice(
    events: Sequence[Tuple[float, float, int]],
) -> Tuple[Counter[int], Counter[int], int]:
    if len(events) != EXPECTED_HARMONIC_PRACTICE_NOTES:
        raise ValueError(
            f"harmonic practice has {len(events)} notes, expected "
            f"{EXPECTED_HARMONIC_PRACTICE_NOTES}")
    ordered = sorted(events)
    for left, right in zip(ordered, ordered[1:]):
        if left[1] > right[0] + 1.0e-8:
            raise ValueError("harmonic practice notes are not monophonic")

    order_counts: Counter[int] = Counter()
    string_counts: Counter[int] = Counter()
    natural_count = 0
    for _, _, pitch in events:
        assignment = practice_harmonic_assignment(pitch)
        if assignment is None:
            raise ValueError(
                f"harmonic practice pitch {pitch} has no valid order or string")
        order, string, fundamental = assignment
        if order < 2 or order > 4:
            raise ValueError(f"harmonic practice selected order {order}")
        open_pitch = STRING_OPEN_MIDI[string]
        if fundamental < (
            open_pitch - HARMONIC_PLAYABLE_EPSILON_SEMITONES
        ):
            raise ValueError(
                f"harmonic practice pitch {pitch}, order {order} is below "
                f"string {string}")
        order_counts[order] += 1
        string_counts[string] += 1
        if (fundamental >=
                open_pitch - HARMONIC_PLAYABLE_EPSILON_SEMITONES and
                fundamental - open_pitch <=
                HARMONIC_NATURAL_TOLERANCE_SEMITONES):
            natural_count += 1

    if dict(order_counts) != EXPECTED_HARMONIC_PRACTICE_ORDERS:
        raise ValueError(
            f"harmonic practice order map changed: {dict(order_counts)}")
    if dict(string_counts) != EXPECTED_HARMONIC_PRACTICE_STRINGS:
        raise ValueError(
            f"harmonic practice string map changed: {dict(string_counts)}")
    if natural_count != EXPECTED_HARMONIC_PRACTICE_NATURALS:
        raise ValueError(
            f"harmonic practice has {natural_count} natural harmonics")
    return order_counts, string_counts, natural_count


def onset_assignments(
    group: Sequence[Note], occupied: Iterable[int], force_low_pair: bool,
) -> List[Tuple[int, ...]]:
    unavailable = set(occupied)
    candidates: Dict[int, List[int]] = {}
    for index, note in enumerate(group):
        allowed = [
            string for string, open_pitch in STRING_OPEN_MIDI.items()
            if string not in unavailable and note.pitch >= open_pitch
        ]
        if force_low_pair:
            allowed = [string for string in allowed if string in (1, 2)]
        preference = preferred_string(note.pitch)
        allowed.sort(key=lambda string: (abs(string - preference), -string))
        candidates[index] = allowed

    order = sorted(
        range(len(group)),
        key=lambda index: (len(candidates[index]), group[index].pitch),
    )
    result: Dict[int, int] = {}
    results: List[Tuple[int, ...]] = []

    def search(position: int, used: set[int]) -> None:
        if position == len(order):
            results.append(tuple(result[index] for index in range(len(group))))
            return
        index = order[position]
        for string in candidates[index]:
            if string in used:
                continue
            result[index] = string
            search(position + 1, used | {string})
            result.pop(index, None)
    search(0, set(unavailable))
    return results


def assign_strings(notes: List[Note]) -> None:
    by_start: Dict[int, List[Note]] = defaultdict(list)
    for note in notes:
        by_start[note.start].append(note)
    groups = [
        sorted(by_start[start], key=lambda note: (note.pitch, note.order))
        for start in sorted(by_start)
    ]
    note_index = {id(note): index for index, note in enumerate(notes)}
    choices: Dict[Tuple[int, Tuple[Tuple[int, int], ...]], Tuple[int, ...]] = {}
    failed: set[Tuple[int, Tuple[Tuple[int, int], ...]]] = set()
    sys.setrecursionlimit(max(5000, len(groups) + 100))

    def solve(
        group_index: int, active_state: Tuple[Tuple[int, int], ...],
    ) -> bool:
        if group_index == len(groups):
            return True
        start = groups[group_index][0].start
        active = tuple(
            (index, string) for index, string in active_state
            if notes[index].end > start
        )
        key = (group_index, active)
        if key in failed:
            return False
        occupied = {string for _, string in active}
        group = groups[group_index]
        assignments = onset_assignments(
            group, occupied, force_low_pair=group[0].section == 3)
        for assignment in assignments:
            added = tuple(
                (note_index[id(note)], string)
                for note, string in zip(group, assignment)
            )
            next_state = tuple(sorted(active + added))
            if solve(group_index + 1, next_state):
                choices[key] = assignment
                return True
        failed.add(key)
        return False

    if not solve(0, ()):
        raise ValueError("the complete score cannot fit on four violin strings")

    active_state: Tuple[Tuple[int, int], ...] = ()
    for group_index, group in enumerate(groups):
        start = group[0].start
        active = tuple(
            (index, string) for index, string in active_state
            if notes[index].end > start
        )
        key = (group_index, active)
        assignment = choices[key]
        added = []
        for note, string in zip(group, assignment):
            note.string = string
            added.append((note_index[id(note)], string))
        active_state = tuple(sorted(active + tuple(added)))


def validate_notes(notes: Sequence[Note], division: int) -> None:
    if len(notes) != EXPECTED_MIDI_NOTES + 93:
        raise ValueError(f"complete score has {len(notes)} notes")
    sections = Counter(note.section for note in notes)
    if set(sections) != set(range(13)) or sections[5] != 93:
        raise ValueError(f"incomplete section coverage: {dict(sections)}")
    if max(note.start for note in notes) / division >= END_BEAT:
        raise ValueError("note starts at or beyond the expected ending")
    final = {
        note.pitch for note in notes
        if note.start == int(441.0 * division)
    }
    if final != {57, 64, 73, 81}:
        raise ValueError(f"wrong final A-major chord: {sorted(final)}")
    for string in range(1, 5):
        string_notes = sorted(
            (note for note in notes if note.string == string),
            key=lambda note: (note.start, note.end),
        )
        for left, right in zip(string_notes, string_notes[1:]):
            if left.end > right.start:
                raise ValueError(
                    f"string {string} overlaps at ticks {left.start} and {right.start}")
    legato_links = 0
    pizzicato_reattacks = 0
    for string in range(1, 5):
        sequence = sorted(
            (note for note in notes if note.string == string),
            key=lambda note: (note.start, note.end),
        )
        legato_links += sum(
            left.end == right.start and
            bool(left.flags & SLUR) and bool(right.flags & SLUR)
            for left, right in zip(sequence, sequence[1:])
        )
        pizzicato_reattacks += sum(
            left.end == right.start and
            bool(left.flags & LEFT_HAND_PIZZICATO) and
            bool(right.flags & LEFT_HAND_PIZZICATO)
            for left, right in zip(sequence, sequence[1:])
        )
    if legato_links != EXPECTED_SAME_STRING_SLUR_LINKS:
        raise ValueError(
            f"score has {legato_links} same-string slur links, "
            f"expected {EXPECTED_SAME_STRING_SLUR_LINKS}")
    for note in notes:
        if note.pitch < STRING_OPEN_MIDI[note.string]:
            raise ValueError(
                f"MIDI note {note.pitch} is below string {note.string}")
    pizzicato_notes = [
        note for note in notes if note.flags & LEFT_HAND_PIZZICATO]
    if any(note.section != 9 for note in pizzicato_notes):
        raise ValueError("left-hand pizzicato appears outside Variation IX")
    pizzicato_count = len(pizzicato_notes)
    if pizzicato_count != EXPECTED_LEFT_HAND_PIZZICATO:
        raise ValueError(
            f"marked {pizzicato_count} left-hand pizzicato notes, expected "
            f"{EXPECTED_LEFT_HAND_PIZZICATO}")
    variation_nine_bowed = sum(
        not bool(note.flags & LEFT_HAND_PIZZICATO)
        for note in notes if note.section == 9)
    if variation_nine_bowed != EXPECTED_VARIATION_IX_BOWED:
        raise ValueError(
            f"Variation IX has {variation_nine_bowed} bowed notes, expected "
            f"{EXPECTED_VARIATION_IX_BOWED}")
    if pizzicato_reattacks != EXPECTED_SAME_STRING_PIZZICATO_REATTACKS:
        raise ValueError(
            f"score has {pizzicato_reattacks} exact same-string pizzicato "
            f"reattacks, expected {EXPECTED_SAME_STRING_PIZZICATO_REATTACKS}")
    required_flags = (
        STACCATO, ACCENT, SLUR, GRACE, CHORD, LEFT_HAND_PIZZICATO,
        TRILL, HARMONIC_OPTION,
    )
    for flag in required_flags:
        if not any(note.flags & flag for note in notes):
            raise ValueError(f"score does not use effect flag {flag}")
    for (section, flag), expected in EXPECTED_SECTION_FLAG_COUNTS.items():
        actual = sum(
            bool(note.flags & flag) for note in notes
            if note.section == section)
        if actual != expected:
            raise ValueError(
                f"section {section} has {actual} uses of flag {flag}, "
                f"expected {expected}")
    if any(
            note.flags & TRILL for note in notes
            if note.start == int(441.0 * division)):
        raise ValueError("the final chord still carries a trill marker")
    if any(
            note.section != 10 for note in notes
            if note.flags & HARMONIC_OPTION):
        raise ValueError("harmonic practice appears outside Variation X")
    validate_harmonic_practice([
        (float(note.start), float(note.end), note.pitch)
        for note in notes if note.flags & HARMONIC_OPTION
    ])


def format_beat(ticks: int, division: int) -> str:
    text = f"{ticks / division:.9f}".rstrip("0").rstrip(".")
    return text if "." in text else text + ".0"


def render_score(notes: Sequence[Note], division: int) -> str:
    lines = [
        "; Generated by tools/generate_caprice_24_demo.py.",
        "; Note source: Samuel Rummel's Mutopia setting,",
        "; Mutopia-2015/03/25-2000, based on Ricordi (1836).",
        "; Changes: restore Variation V; restore carried forte and mixed",
        "; bowed/left-hand pizzicato in Variation IX; expand repeats;",
        "; assign four strings;",
        "; retain dynamics and explicit score marks as event data.",
        "; Slur flags cover the theme, Variations I, II, V, VII, and finale.",
        ";",
        "; p4 MIDI, p5 velocity, p6 string (1=G, 2=D, 3=A, 4=E),",
        "; p7 section, p8 flags, p9 event id.",
        "; flags: 1 staccato, 2 accent, 4 slur, 8 grace, 16 chord,",
        ";        32 left-hand pizzicato, 64 trill,",
        ";        256 optional harmonic practice.",
        "; The final-rest fermata uses its own CapriceMark event.",
        "",
    ]
    section_names = {section: name for _, section, name in SECTION_STARTS}
    current_section = None
    event_id = 1
    for note in sorted(notes, key=lambda item: (item.start, item.order, item.pitch)):
        if note.section != current_section:
            current_section = note.section
            lines.extend((
                f"; {section_names[current_section]}",
                f'i "CapriceMark" {format_beat(note.start, division)} '
                f'0.001 {current_section}',
            ))
        lines.append(
            'i "CapriceNote" '
            f"{format_beat(note.start, division)} "
            f"{format_beat(note.duration, division)} "
            f"{note.pitch} {note.velocity} {note.string} "
            f"{note.section} {note.flags} {event_id}")
        event_id += 1
    lines.extend((
        "",
        "; A-MAJOR CLOSE",
        'i "CapriceMark" 429 0.001 13',
        "",
        "; FINAL FERMATA",
        f'i "CapriceMark" {END_BEAT:.4f} 0.001 14',
    ))
    lines.append("")
    return "\n".join(lines)


NOTE_LINE = re.compile(
    r'^i "CapriceNote" ([0-9.]+) ([0-9.]+) '
    r'(\d+) (\d+) (\d+) (\d+) (\d+) (\d+)$')
MARK_LINE = re.compile(r'^i "CapriceMark" ([0-9.]+) 0\.001 (\d+)$')

RenderedNote = Tuple[float, float, int, int, int, int, int, int]


def read_rendered(path: Path) -> Tuple[List[RenderedNote], Dict[int, float]]:
    notes: List[RenderedNote] = []
    marks: Dict[int, float] = {}
    for line_number, line in enumerate(path.read_text().splitlines(), 1):
        note_match = NOTE_LINE.match(line)
        if note_match:
            start, duration = map(float, note_match.group(1, 2))
            pitch, velocity, string, section, flags, event_id = map(
                int, note_match.group(3, 4, 5, 6, 7, 8))
            notes.append((start, duration, pitch, velocity, string,
                          section, flags, event_id))
            continue
        mark_match = MARK_LINE.match(line)
        if mark_match:
            section = int(mark_match.group(2))
            if section in marks:
                raise ValueError(f"duplicate score mark {section}")
            marks[section] = float(mark_match.group(1))
        elif line.startswith('i "'):
            raise ValueError(f"unreadable score line {line_number}: {line}")
    return notes, marks


def check_rendered(path: Path) -> None:
    notes, marks = read_rendered(path)
    if len(notes) != EXPECTED_MIDI_NOTES + 93:
        raise ValueError(f"rendered score has {len(notes)} notes")
    if set(marks) != set(EXPECTED_MARK_BEATS):
        raise ValueError(f"rendered score marks sections {sorted(marks)}")
    for section, expected in EXPECTED_MARK_BEATS.items():
        if abs(marks[section] - expected) > 1.0e-8:
            raise ValueError(
                f"score mark {section} starts at {marks[section]}, "
                f"expected {expected}")
    if len({note[7] for note in notes}) != len(notes):
        raise ValueError("event ids are not unique")
    if {note[5] for note in notes} != set(range(13)):
        raise ValueError("rendered score does not contain every section")
    if Counter(note[5] for note in notes)[5] != 93:
        raise ValueError("rendered score does not contain all of Variation V")
    for note in notes:
        if note[4] not in STRING_OPEN_MIDI:
            raise ValueError(f"rendered score uses string {note[4]}")
        if note[2] < STRING_OPEN_MIDI[note[4]]:
            raise ValueError(
                f"rendered MIDI note {note[2]} is below string {note[4]}")
    for string in range(1, 5):
        sequence = sorted(
            (note for note in notes if note[4] == string),
            key=lambda note: note[0],
        )
        for left, right in zip(sequence, sequence[1:]):
            if left[0] + left[1] > right[0] + 1.0e-8:
                raise ValueError(f"rendered string {string} overlaps")
    legato_links = 0
    pizzicato_reattacks = 0
    for string in range(1, 5):
        sequence = sorted(
            (note for note in notes if note[4] == string),
            key=lambda note: note[0],
        )
        legato_links += sum(
            abs(left[0] + left[1] - right[0]) <= 1.0e-8 and
            bool(left[6] & SLUR) and bool(right[6] & SLUR)
            for left, right in zip(sequence, sequence[1:])
        )
        pizzicato_reattacks += sum(
            abs(left[0] + left[1] - right[0]) <= 1.0e-8 and
            bool(left[6] & LEFT_HAND_PIZZICATO) and
            bool(right[6] & LEFT_HAND_PIZZICATO)
            for left, right in zip(sequence, sequence[1:])
        )
    if legato_links != EXPECTED_SAME_STRING_SLUR_LINKS:
        raise ValueError(
            f"rendered score has {legato_links} same-string slur links")
    final = {note[2] for note in notes if abs(note[0] - 441.0) < 1.0e-8}
    if final != {57, 64, 73, 81}:
        raise ValueError(f"rendered final chord is {sorted(final)}")
    if any(
        note[6] & TRILL for note in notes
        if abs(note[0] - 441.0) < 1.0e-8
    ):
        raise ValueError("the final chord still carries a trill marker")
    if any(
        note[5] != 10 for note in notes
        if note[6] & HARMONIC_OPTION
    ):
        raise ValueError(
            "rendered harmonic practice appears outside Variation X")
    pizzicato_notes = [
        note for note in notes if note[6] & LEFT_HAND_PIZZICATO]
    if any(note[5] != 9 for note in pizzicato_notes):
        raise ValueError(
            "rendered left-hand pizzicato appears outside Variation IX")
    pizzicato_count = len(pizzicato_notes)
    if pizzicato_count != EXPECTED_LEFT_HAND_PIZZICATO:
        raise ValueError(
            f"rendered score has {pizzicato_count} left-hand pizzicato notes")
    variation_nine_bowed = sum(
        not bool(note[6] & LEFT_HAND_PIZZICATO)
        for note in notes if note[5] == 9)
    if variation_nine_bowed != EXPECTED_VARIATION_IX_BOWED:
        raise ValueError(
            f"rendered Variation IX has {variation_nine_bowed} bowed notes")
    if pizzicato_reattacks != EXPECTED_SAME_STRING_PIZZICATO_REATTACKS:
        raise ValueError(
            f"rendered score has {pizzicato_reattacks} exact same-string "
            "pizzicato reattacks")
    for flag in (
            STACCATO, ACCENT, SLUR, GRACE, CHORD, LEFT_HAND_PIZZICATO,
            TRILL, HARMONIC_OPTION):
        if not any(note[6] & flag for note in notes):
            raise ValueError(f"rendered score does not use effect flag {flag}")
    for (section, flag), expected in EXPECTED_SECTION_FLAG_COUNTS.items():
        actual = sum(
            bool(note[6] & flag) for note in notes
            if note[5] == section)
        if actual != expected:
            raise ValueError(
                f"rendered section {section} has {actual} uses of flag {flag}, "
                f"expected {expected}")
    harmonic_orders, harmonic_strings, natural_harmonics = (
        validate_harmonic_practice([
            (note[0], note[0] + note[1], note[2])
            for note in notes if note[6] & HARMONIC_OPTION
        ])
    )
    print(
        f"Caprice score OK: {len(notes)} notes, 13 sections, "
        f"{pizzicato_count} left-hand pizzicato notes, "
        f"{pizzicato_reattacks} exact pizzicato reattacks, "
        f"{legato_links} same-string slur links, "
        f"{sum(harmonic_orders.values())} harmonic practice notes "
        f"({natural_harmonics} natural), strings "
        f"{dict(sorted(harmonic_strings.items()))}")


def read_tempo_curve(path: Path) -> List[Tuple[float, float]]:
    lines = path.read_text().splitlines()
    tokens: List[str] = []
    for index, line in enumerate(lines):
        stripped = line.strip()
        if not stripped.startswith("t "):
            continue
        first_line = True
        while True:
            continued = stripped.endswith("\\")
            if continued:
                stripped = stripped[:-1].rstrip()
            parts = stripped.split()
            tokens.extend(parts[1:] if first_line else parts)
            first_line = False
            if not continued:
                break
            index += 1
            if index == len(lines):
                raise ValueError("unterminated Csound tempo statement")
            stripped = lines[index].strip()
        break
    if not tokens or len(tokens) % 2 != 0:
        raise ValueError(f"cannot read the tempo curve from {path}")
    values = [float(token) for token in tokens]
    curve = list(zip(values[0::2], values[1::2]))
    if (any(not math.isfinite(beat) or not math.isfinite(bpm) or
            beat < 0.0 or bpm <= 0.0 for beat, bpm in curve) or
            curve[0][0] != 0.0 or any(
                right[0] <= left[0]
                for left, right in zip(curve, curve[1:]))):
        raise ValueError("the Csound tempo curve is not positive and ordered")
    if curve[-1][0] < END_BEAT:
        raise ValueError("the Csound tempo curve ends before the score")
    return curve


def tempo_at(curve: Sequence[Tuple[float, float]], beat: float) -> float:
    for left, right in zip(curve, curve[1:]):
        if beat <= right[0]:
            fraction = (beat - left[0]) / (right[0] - left[0])
            return left[1] + fraction * (right[1] - left[1])
    return curve[-1][1]


def interval_tempo(curve: Sequence[Tuple[float, float]],
                   start: float, end: float) -> float:
    start_bpm = tempo_at(curve, start)
    end_bpm = tempo_at(curve, end)
    if math.isclose(start_bpm, end_bpm, rel_tol=0.0, abs_tol=1.0e-12):
        return start_bpm
    return (end_bpm - start_bpm) / math.log(end_bpm / start_bpm)


def short_float(value: float) -> str:
    return f"{value:.12f}".rstrip("0").rstrip(".")


def midi_pitch_name(pitch: int) -> str:
    names = ("C", "C#", "D", "D#", "E", "F",
             "F#", "G", "G#", "A", "A#", "B")
    return f"{names[pitch % 12]}{pitch // 12 - 1}"


def dynamic_name(velocity: int) -> str:
    if velocity <= 40:
        return "pp"
    if velocity <= 55:
        return "p"
    if velocity <= 70:
        return "mp"
    if velocity <= 85:
        return "mf"
    if velocity <= 105:
        return "f"
    return "ff"


def analyzer_rows(
    notes: Sequence[RenderedNote],
    curve: Sequence[Tuple[float, float]],
) -> Tuple[List[List[str]], List[List[str]]]:
    section_names = {section: name for _, section, name in SECTION_STARTS}
    string_names = {1: "violin-string-G", 2: "violin-string-D",
                    3: "violin-string-A", 4: "violin-string-E"}
    last_note_beat = max(start + duration for start, duration, *_ in notes)
    breaks = {0.0, last_note_beat}
    breaks.update(beat for beat, _ in curve if beat <= last_note_beat)
    breaks.update(start for start, *_ in notes)
    breaks.update(start + duration for start, duration, *_ in notes)
    last_beat = max(breaks)
    eighth_count = int(math.ceil(last_beat * 8.0))
    breaks.update(
        step / 8.0 for step in range(eighth_count + 1)
        if step / 8.0 <= last_beat)
    ordered_breaks = sorted(breaks)

    rows_by_beat: Dict[float, List[List[str]]] = defaultdict(list)
    for index, beat in enumerate(ordered_breaks):
        bpm = (interval_tempo(curve, beat, ordered_breaks[index + 1])
               if index + 1 < len(ordered_breaks) else tempo_at(curve, beat))
        rows_by_beat[beat].append([
            f"tempo-{index + 1:05d}", "tempo", short_float(beat), "", "",
            "", "", "", "", "", "", short_float(bpm),
        ])

    label_rows: List[List[str]] = []
    prior_on_string: Dict[int, RenderedNote] = {}
    for note in sorted(notes, key=lambda item: (item[0], item[7])):
        (start, duration, pitch, velocity, string,
         section, flags, event_number) = note
        event_id = f"caprice-{event_number:04d}"
        kind = "ornament" if flags & GRACE else "note"
        dynamic = dynamic_name(velocity)
        articulation_parts = []
        if flags & STACCATO:
            articulation_parts.append("staccato")
        if flags & ACCENT:
            articulation_parts.append("accent")
        articulation = "+".join(articulation_parts)
        technique_parts = []
        if flags & LEFT_HAND_PIZZICATO:
            technique_parts.append("left-hand-pizzicato")
        if flags & HARMONIC_OPTION:
            technique_parts.append("harmonic")
        if flags & TRILL:
            technique_parts.append("trill")
        technique = "+".join(technique_parts)
        prior = prior_on_string.get(string)
        transition = ""
        if (prior is not None and abs(prior[0] + prior[1] - start) <= 1.0e-8
                and prior[6] & SLUR and flags & SLUR):
            transition = "slur"
        prior_on_string[string] = note
        section_name = section_names[section]
        rows_by_beat[start].append([
            event_id, kind, short_float(start), short_float(duration),
            str(pitch), str(velocity), "solo-violin", "none", dynamic, "",
            section_name, "",
        ])
        gesture_parts = []
        # The score kind already creates the ornament item.
        # Keep this cell for extra gestures so one mark cannot make two items.
        if flags & TRILL:
            gesture_parts.append("trill")
        label_rows.append([
            event_id, midi_pitch_name(pitch), f"octave-{pitch // 12 - 1}",
            dynamic, articulation, "solo-violin", string_names[string],
            "left-hand-finger" if flags & LEFT_HAND_PIZZICATO else "bow",
            technique, section_name, transition, "+".join(gesture_parts),
        ])
    score_rows = [
        row for beat in sorted(rows_by_beat) for row in rows_by_beat[beat]
    ]
    return score_rows, label_rows


def casefolded_resolved_parts(path: Path) -> Tuple[str, ...]:
    return tuple(
        unicodedata.normalize("NFC", part).casefold()
        for part in path.resolve(strict=False).parts
    )


def paths_alias(left: Path, right: Path) -> bool:
    try:
        if left.samefile(right):
            return True
    except (FileNotFoundError, OSError):
        pass
    # Keep absent paths safe on case-insensitive file systems. This is
    # conservative on case-sensitive systems so a checked export behaves the
    # same on every supported host.
    return (casefolded_resolved_parts(left) ==
            casefolded_resolved_parts(right))


def preflight_output_paths(outputs: Sequence[Path],
                           protected_paths: Sequence[Path]) -> None:
    folded_outputs = [casefolded_resolved_parts(path) for path in outputs]
    for index, output in enumerate(outputs):
        for other_index in range(index):
            other = outputs[other_index]
            if paths_alias(output, other):
                raise ValueError(
                    f"output paths must differ: {other} and {output}")
            other_parts = folded_outputs[other_index]
            output_parts = folded_outputs[index]
            if (other_parts == output_parts[:len(other_parts)] or
                    output_parts == other_parts[:len(output_parts)]):
                raise ValueError(
                    f"output paths may not contain each other: "
                    f"{other} and {output}")
        if output.is_symlink():
            raise ValueError(f"output may not be a symlink: {output}")
        if output.exists() and not output.is_file():
            raise ValueError(f"output must be a regular file: {output}")
        for protected in protected_paths:
            if paths_alias(output, protected):
                raise ValueError(f"output aliases an input: {output}")


def write_csv_temporary(destination: Path,
                        header: Sequence[str],
                        rows: Sequence[Sequence[str]]) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary: Optional[Path] = None
    try:
        with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", newline="",
                dir=destination.parent,
                prefix=f".{destination.name}.", suffix=".tmp",
                delete=False) as stream:
            temporary = Path(stream.name)
            writer = csv.writer(stream, lineterminator="\n")
            writer.writerow(header)
            writer.writerows(rows)
            stream.flush()
            os.fsync(stream.fileno())
        return temporary
    except BaseException:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
        raise


def backup_analyzer_output(destination: Path) -> Optional[Path]:
    if not destination.exists():
        return None
    descriptor, name = tempfile.mkstemp(
        dir=destination.parent,
        prefix=f".{destination.name}.", suffix=".backup")
    os.close(descriptor)
    backup = Path(name)
    try:
        shutil.copy2(destination, backup)
        with backup.open("rb") as stream:
            os.fsync(stream.fileno())
        return backup
    except BaseException:
        backup.unlink(missing_ok=True)
        raise


def write_analyzer_inputs(score_path: Path,
                          labels_path: Path,
                          notes: Sequence[RenderedNote],
                          tempo_source: Path,
                          protected_paths: Sequence[Path],
                          tempo_curve: Optional[
                              Sequence[Tuple[float, float]]
                          ] = None) -> None:
    outputs = (score_path, labels_path)
    preflight_output_paths(outputs, protected_paths)
    curve = (read_tempo_curve(tempo_source)
             if tempo_curve is None else tempo_curve)
    score_rows, label_rows = analyzer_rows(notes, curve)
    score_header = (
            "event_id", "kind", "start_beats", "duration_beats", "midi_note",
            "velocity", "voice", "tie", "dynamic", "mark", "score_position",
            "tempo_bpm",
    )
    label_header = (
            "event_id", "pitch", "register", "dynamic", "articulation", "part",
            "physical_element", "controller", "technique", "score_section",
            "transition", "gesture",
    )
    score_temporary: Optional[Path] = None
    labels_temporary: Optional[Path] = None
    backups: List[Optional[Path]] = [None, None]
    committed = [False, False]
    preserved_backups: set[Path] = set()
    try:
        score_temporary = write_csv_temporary(
            score_path, score_header, score_rows)
        labels_temporary = write_csv_temporary(
            labels_path, label_header, label_rows)
        backups[0] = backup_analyzer_output(score_path)
        backups[1] = backup_analyzer_output(labels_path)
        if backups[0] is not None:
            shutil.copymode(score_path, score_temporary)
        if backups[1] is not None:
            shutil.copymode(labels_path, labels_temporary)
        os.replace(score_temporary, score_path)
        score_temporary = None
        committed[0] = True
        os.replace(labels_temporary, labels_path)
        labels_temporary = None
        committed[1] = True
    except BaseException as commit_error:
        rollback_errors: List[OSError] = []
        for index, destination in reversed(tuple(enumerate(outputs))):
            if not committed[index]:
                continue
            try:
                if backups[index] is not None:
                    os.replace(backups[index], destination)
                    backups[index] = None
                else:
                    destination.unlink(missing_ok=True)
            except OSError as rollback_error:
                rollback_errors.append(rollback_error)
                if backups[index] is not None:
                    preserved_backups.add(backups[index])
        if rollback_errors:
            kept = ", ".join(str(path) for path in preserved_backups)
            suffix = f"; backups kept at {kept}" if kept else ""
            raise RuntimeError(
                f"cannot restore analyzer outputs after a write fault{suffix}"
            ) from commit_error
        raise
    finally:
        if score_temporary is not None:
            score_temporary.unlink(missing_ok=True)
        if labels_temporary is not None:
            labels_temporary.unlink(missing_ok=True)
        for backup in backups:
            if backup is not None and backup not in preserved_backups:
                backup.unlink(missing_ok=True)
    print(f"wrote {len(score_rows)} analyzer score rows to {score_path}")
    print(f"wrote {len(label_rows)} typed label rows to {labels_path}")


def check_demo_gate(path: Path) -> None:
    source = path.read_text()
    note_match = re.search(
        r"^instr CapriceNote\n(?P<body>.*?)^endin$", source,
        re.MULTILINE | re.DOTALL)
    off_match = re.search(
        r"^instr CapriceOff\n(?P<body>.*?)^endin$", source,
        re.MULTILINE | re.DOTALL)
    if note_match is None or off_match is None:
        raise ValueError("demo lacks CapriceNote or CapriceOff")
    note_body = note_match.group("body")
    off_body = off_match.group("body")
    delayed_off = re.search(
        r'event_i\s+"i",\s*"CapriceOff",\s*'
        r'p3\s*\+\s*ksmps\s*/\s*sr\s*,',
        note_body)
    if delayed_off is None:
        raise ValueError(
            "CapriceOff must run one control block after note end")
    if "gkTrigger[iString] = 0" not in off_body:
        raise ValueError("CapriceOff does not lower the string trigger")
    if re.search(r"^\s*turnoff\s*$", off_body, re.MULTILINE):
        raise ValueError(
            "CapriceOff turns off before its k-rate trigger write")
    flat_note_body = note_body.replace("\\\n", " ")
    dynamic_match = re.search(
        r"iDynamic\s*=\s*\(iVelocity\s*/\s*127\)\s*\^\s*([0-9.]+)",
        flat_note_body)
    contact_match = re.search(
        r"if\s+iArticulation\s*<=\s*4\s+then\s+"
        r".*?iTriggerLevel\s*=\s*([0-9.]+)\s*\+\s*"
        r"([0-9.]+)\s*\*\s*iDynamic\s+endif",
        flat_note_body, re.DOTALL)
    exciter_match = re.search(
        r"iTriggerLevel\s*=\s*([0-9.]+)\s*\+\s*"
        r"([0-9.]+)\s*\*\s*iDynamic\s+"
        r"if\s+iArticulation\s*<=\s*4\s+then",
        flat_note_body)
    if (dynamic_match is None or contact_match is None or
            exciter_match is None):
        raise ValueError("demo lacks the checked bow-contact map")
    exponent = float(dynamic_match.group(1))
    contact_floor = float(contact_match.group(1))
    contact_range = float(contact_match.group(2))
    soft_dynamic = (SOFT_BOW_TEST_VELOCITY / 127.0) ** exponent
    soft_contact = contact_floor + contact_range * soft_dynamic
    if soft_contact < MINIMUM_SOFT_BOW_CONTACT:
        raise ValueError(
            f"soft bow contact {soft_contact:.3f} falls below the stable "
            f"floor {MINIMUM_SOFT_BOW_CONTACT:.3f}")
    if not math.isclose(contact_floor + contact_range, 1.0,
                        rel_tol=0.0, abs_tol=1.0e-9):
        raise ValueError("bow-contact map must reach 1 at full dynamic")
    exciter_floor = float(exciter_match.group(1))
    exciter_range = float(exciter_match.group(2))
    if (not math.isclose(exciter_floor, 0.16, rel_tol=0.0,
                         abs_tol=1.0e-9) or
            not math.isclose(exciter_range, 0.88, rel_tol=0.0,
                             abs_tol=1.0e-9)):
        raise ValueError("bow-contact fix changed the exciter strength map")
    print(
        "Caprice gate OK: delayed off runs at k-rate after unclaimed note "
        f"ends; soft contact {soft_contact:.3f}")


def check_demo_harmonics(path: Path) -> None:
    source = path.read_text()
    required = (
        "opcode CapricePracticeHarmonic, ii, ii",
        "iFundamentalMidi = iMidi - 12 * log(iOrder) / log(2)",
        "iHarmonic, iString CapricePracticeHarmonic iMidi, iString",
        "iOrder = 0",
    )
    for text in required:
        if text not in source:
            raise ValueError(f"demo harmonic mapping lacks: {text}")
    mapping = source.index(
        "iHarmonic, iString CapricePracticeHarmonic iMidi, iString")
    slur_state = source.index("iStartsSlurLink = 0")
    if mapping >= slur_state:
        raise ValueError(
            "demo must choose its practice string before reading slur state")
    for name in (
        "gkGestureId", "gkTrigger", "gkFrequency", "gkForce", "gkSpeed",
        "gkPosition", "gkVibratoDepth", "gkVibratoRate",
        "gkArticulation", "gkHarmonic",
    ):
        if f"{name}[] init 5" not in source:
            raise ValueError(f"demo lacks safe four-string array {name}")
    print(
        "Caprice harmonics OK: practice mapping precedes fixed-string state")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--midi", type=Path,
                        help="Mutopia Caprice_24.mid used to generate data")
    parser.add_argument("--output", type=Path,
                        default=Path("examples/paganini_caprice_24_score.inc"))
    parser.add_argument("--check", type=Path,
                        help="check an existing generated score and exit")
    parser.add_argument("--analyzer-score", type=Path,
                        help="write a note manifest")
    parser.add_argument("--analyzer-labels", type=Path,
                        help="write matching typed labels")
    parser.add_argument("--tempo-source", type=Path,
                        help="Csound file that owns the editorial tempo curve")
    arguments = parser.parse_args()

    if (arguments.analyzer_score is None) != (arguments.analyzer_labels is None):
        parser.error(
            "--analyzer-score and --analyzer-labels must be used together")

    if arguments.check is not None:
        check_rendered(arguments.check)
        demo = arguments.check.with_name("paganini_caprice_24.csd")
        if demo.exists():
            check_demo_gate(demo)
            check_demo_harmonics(demo)
        if arguments.analyzer_score is not None:
            tempo_source = arguments.tempo_source or demo
            if not tempo_source.exists():
                parser.error(
                    "--tempo-source is needed when the demo is not beside "
                    "--check")
            notes, _ = read_rendered(arguments.check)
            protected_paths = [arguments.check, tempo_source]
            if demo.exists():
                protected_paths.append(demo)
            write_analyzer_inputs(arguments.analyzer_score,
                                  arguments.analyzer_labels,
                                  notes, tempo_source,
                                  protected_paths)
        return 0
    if arguments.midi is None:
        parser.error("--midi is required unless --check is used")

    tempo_curve: Optional[Sequence[Tuple[float, float]]] = None
    outputs = [arguments.output]
    protected_paths = [arguments.midi]
    if arguments.analyzer_score is not None:
        tempo_source = arguments.tempo_source
        if tempo_source is None:
            parser.error("--tempo-source is required with analyzer exports")
        outputs.extend((arguments.analyzer_score, arguments.analyzer_labels))
        protected_paths.append(tempo_source)
    preflight_output_paths(outputs, protected_paths)
    if arguments.analyzer_score is not None:
        tempo_curve = read_tempo_curve(arguments.tempo_source)

    division, midi_notes = parse_midi(arguments.midi)
    notes = restore_complete_score(division, midi_notes)
    annotate(notes, division)
    assign_strings(notes)
    validate_notes(notes, division)
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(render_score(notes, division))
    print(f"wrote {len(notes)} notes to {arguments.output}")
    if arguments.analyzer_score is not None:
        rendered_notes, _ = read_rendered(arguments.output)
        write_analyzer_inputs(arguments.analyzer_score,
                              arguments.analyzer_labels,
                              rendered_notes, arguments.tempo_source,
                              (arguments.midi, arguments.output,
                               arguments.tempo_source),
                              tempo_curve)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
