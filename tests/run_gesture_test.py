#!/usr/bin/env python3
"""Check bowed gesture presets, live overrides, and phase retention."""

from __future__ import annotations

import argparse
import math
import struct
import subprocess
import sys
import tempfile
import wave
from pathlib import Path
from typing import Dict, List, Mapping, Sequence, Tuple


State = Tuple[float, ...]
Audio = Tuple[bytes, Tuple[List[int], List[int]]]

SAMPLE_RATE = 48000
GESTURE_FIELDS = (
    "articulation", "active", "phase", "force_target", "speed_target",
    "force_output", "speed_output", "contact_output", "onset_samples",
    "stroke_samples", "strokes", "bow_changes", "preset_changes",
    "direct_overrides", "recoveries", "release_articulation",
    "release_gain_target", "finite",
)
WAVE_FIELDS = (
    "capacity", "read_delay", "target_delay", "target_frequency",
    "loop_phase", "toward_nut_energy", "toward_bridge_energy",
    "toward_nut_signature", "toward_bridge_signature", "nut_pole",
    "nut_gain", "nut_state", "bridge_pole", "bridge_gain", "bridge_state",
    "write_index", "wave_samples", "excitation_count", "clear_count",
    "reset_count", "clip_count", "bridge_dynamic_input",
    "bridge_dynamic_output", "last_bridge_output", "finite",
)
STRING_FIELDS = (
    "phase", "vibrato_phase", "frequency", "trigger", "force", "speed",
    "activity", "last_sample", "gap_samples", "owner", "successor",
)
BODY_FIELDS = (
    "send_energy_1", "send_energy_2", "send_energy_3", "send_energy_4",
    "drive_energy", "output_energy_left", "output_energy_right",
    "reset_count", "clip_count", "finite",
)


def value(state: State, fields: Sequence[str], name: str) -> float:
    return state[fields.index(name)]


def close(left: float, right: float, tolerance: float = 2.0e-10) -> bool:
    return math.isclose(left, right, rel_tol=tolerance, abs_tol=tolerance)


def run_csound(
    csound: Path,
    module: Path,
    csd: Path,
    definitions: Mapping[str, object],
    output: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    command = [
        str(csound),
        "--opcode-lib={}".format(module),
        "--sample-accurate",
        "--num-threads=1",
        *[
            "--omacro:{}={}".format(name, setting)
            for name, setting in definitions.items()
        ],
    ]
    if output is None:
        command.extend(("-n", "-d", "-m128"))
    else:
        command.extend(("-W", "-s", "-o", str(output), "-d", "-m128"))
    command.append(str(csd))
    return subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        timeout=75,
        check=False,
    )


def read_tagged(output: str, marker: str, count: int) -> Dict[int, State]:
    states: Dict[int, State] = {}
    prefix = marker + " "
    for line in output.splitlines():
        start = line.find(prefix)
        if start < 0:
            continue
        words = line[start:].split()
        if len(words) < count + 2:
            continue
        tag = int(float(words[1]))
        states[tag] = tuple(float(item) for item in words[2:2 + count])
    return states


def read_wav(path: Path) -> Audio:
    with wave.open(str(path), "rb") as audio:
        if (audio.getframerate() != SAMPLE_RATE or
                audio.getnchannels() != 2 or audio.getsampwidth() != 2):
            raise ValueError("unexpected gesture-test WAV format")
        frames = audio.readframes(audio.getnframes())
    pairs = list(struct.iter_unpack("<hh", frames))
    return frames, ([pair[0] for pair in pairs], [pair[1] for pair in pairs])


def run_case(
    failures: List[str],
    label: str,
    csound: Path,
    module: Path,
    csd: Path,
    definitions: Mapping[str, object],
    gesture_tags: Sequence[int] = (),
    wave_tags: Sequence[int] = (),
    string_tags: Sequence[int] = (),
    body_tags: Sequence[int] = (),
    output: Path | None = None,
) -> Tuple[Dict[int, State], Dict[int, State], Dict[int, State],
           Dict[int, State], Audio | None]:
    completed = run_csound(csound, module, csd, definitions, output)
    if completed.returncode != 0:
        failures.append(
            "{} failed with status {}:\n{}".format(
                label, completed.returncode, completed.stdout.rstrip()))
        return {}, {}, {}, {}, None
    gestures = read_tagged(
        completed.stdout, "WG_GESTURE", len(GESTURE_FIELDS))
    waves = read_tagged(
        completed.stdout, "WG_GESTURE_WAVE", len(WAVE_FIELDS))
    strings = read_tagged(
        completed.stdout, "WG_GESTURE_STRING", len(STRING_FIELDS))
    bodies = read_tagged(
        completed.stdout, "WG_GESTURE_BODY", len(BODY_FIELDS))
    missing = (
        [tag for tag in gesture_tags if tag not in gestures],
        [tag for tag in wave_tags if tag not in waves],
        [tag for tag in string_tags if tag not in strings],
        [tag for tag in body_tags if tag not in bodies],
    )
    if any(missing):
        failures.append(
            "{} missed gesture {}, wave {}, string {}, or body {} tags:\n{}".
            format(label, *missing, completed.stdout.rstrip()))
    rendered = None
    if output is not None:
        if not output.exists():
            failures.append("{} produced no WAV".format(label))
        else:
            try:
                rendered = read_wav(output)
            except (ValueError, wave.Error) as error:
                failures.append("{}: {}".format(label, error))
    return gestures, waves, strings, bodies, rendered


def check_gesture_common(
    failures: List[str], label: str, state: State,
) -> None:
    if len(state) != len(GESTURE_FIELDS):
        failures.append("{} returned the wrong gesture state size".format(label))
        return
    if not all(math.isfinite(item) for item in state):
        failures.append("{} returned non-finite gesture state".format(label))
        return
    if value(state, GESTURE_FIELDS, "finite") != 1.0:
        failures.append("{} reported invalid gesture state".format(label))
    if value(state, GESTURE_FIELDS, "active") not in (0.0, 1.0):
        failures.append("{} returned a non-Boolean active flag".format(label))
    if not 0.0 <= value(state, GESTURE_FIELDS, "articulation") <= 4.0:
        failures.append("{} returned an invalid bowed articulation".format(label))
    if not 0.0 <= value(state, GESTURE_FIELDS, "phase") < 1.0 + 1.0e-12:
        failures.append("{} returned an invalid gesture phase".format(label))
    for field in ("force_target", "force_output", "contact_output"):
        found = value(state, GESTURE_FIELDS, field)
        if not 0.0 <= found <= 1.0:
            failures.append("{} {} left [0, 1]: {:.17g}".format(
                label, field, found))
    for field in ("speed_target", "speed_output"):
        found = value(state, GESTURE_FIELDS, field)
        if not -1.0 <= found <= 1.0:
            failures.append("{} {} left [-1, 1]: {:.17g}".format(
                label, field, found))
    for field in (
            "onset_samples", "stroke_samples", "strokes", "bow_changes",
            "preset_changes", "direct_overrides", "recoveries"):
        found = value(state, GESTURE_FIELDS, field)
        if found < 0.0 or found != math.floor(found):
            failures.append("{} returned an invalid {}".format(label, field))
    release_articulation = value(
        state, GESTURE_FIELDS, "release_articulation")
    if not 0.0 <= release_articulation <= 15.0 or \
            release_articulation != math.floor(release_articulation):
        failures.append("{} returned an invalid release articulation".format(
            label))
    release_gain = value(state, GESTURE_FIELDS, "release_gain_target")
    if not 0.05 <= release_gain <= 1.0:
        failures.append("{} returned an invalid release gain".format(label))


def check_wave_common(failures: List[str], label: str, state: State) -> None:
    if len(state) != len(WAVE_FIELDS):
        failures.append("{} returned the wrong wave state size".format(label))
        return
    if not all(math.isfinite(item) for item in state):
        failures.append("{} returned non-finite wave state".format(label))
        return
    if value(state, WAVE_FIELDS, "finite") != 1.0:
        failures.append("{} reported invalid wave state".format(label))
    for field in ("clear_count", "reset_count", "clip_count"):
        if value(state, WAVE_FIELDS, field) != 0.0:
            failures.append("{} had nonzero {}".format(label, field))


def stereo_window(
    channels: Tuple[List[int], List[int]], start: float, stop: float,
) -> List[float]:
    first = max(0, int(start * SAMPLE_RATE))
    last = min(len(channels[0]), int(stop * SAMPLE_RATE))
    return [
        0.5 * (channels[0][index] + channels[1][index])
        for index in range(first, last)
    ]


def rms(samples: Sequence[float]) -> float:
    if not samples:
        return 0.0
    return math.sqrt(sum(sample * sample for sample in samples) / len(samples))


def transition_step_ok(samples: Sequence[float], boundary: float) -> bool:
    center = int(boundary * SAMPLE_RATE)
    first = max(1, center - 512)
    last = min(len(samples), center + 512)
    differences = [
        abs(samples[index] - samples[index - 1])
        for index in range(first, last)
    ]
    before = differences[:max(1, min(400, center - first))]
    reference = sorted(before)[int(0.99 * (len(before) - 1))]
    boundary_step = max(
        abs(samples[index] - samples[index - 1])
        for index in range(max(1, center - 2), min(len(samples), center + 3))
    )
    return boundary_step <= max(1400.0, 14.0 * reference)


def check_profiles(
    failures: List[str], csound: Path, module: Path, csd: Path,
) -> None:
    with tempfile.TemporaryDirectory(prefix="hlolli-gesture-profile-") as folder:
        temporary = Path(folder)
        results = {}
        for articulation, name in enumerate(
                ("detache", "martele", "spiccato", "tremolo"), 1):
            label = "{} gesture".format(name)
            results[articulation] = run_case(
                failures, label, csound, module, csd,
                {"TEST_CASE": 1, "TEST_ARTICULATION": articulation},
                tuple(range(1, 8)), tuple(range(1, 8)),
                tuple(range(1, 8)),
                output=temporary / "{}.wav".format(name))

        signatures = []
        for articulation, name in enumerate(
                ("detache", "martele", "spiccato", "tremolo"), 1):
            gestures, waves, _, _, rendered = results[articulation]
            if any(tag not in gestures or tag not in waves
                   for tag in range(1, 8)) or rendered is None:
                continue
            for tag in range(1, 8):
                label = "{} snapshot {}".format(name, tag)
                check_gesture_common(failures, label, gestures[tag])
                check_wave_common(failures, label, waves[tag])
                if value(gestures[tag], GESTURE_FIELDS, "articulation") != \
                        float(articulation):
                    failures.append("{} stored the wrong articulation".format(label))
                if value(gestures[tag], GESTURE_FIELDS, "recoveries") != 0.0:
                    failures.append("{} recovered during a normal gesture".format(label))
            final = gestures[7]
            if value(final, GESTURE_FIELDS, "onset_samples") <= 0.0:
                failures.append("{} recorded no onset path".format(name))
            if value(final, GESTURE_FIELDS, "stroke_samples") <= 0.0:
                failures.append("{} recorded no stroke path".format(name))
            if value(final, GESTURE_FIELDS, "strokes") < 1.0:
                failures.append("{} recorded no stroke".format(name))
            if value(waves[7], WAVE_FIELDS, "excitation_count") != 1.0:
                failures.append("{} had the wrong rail attack count".format(name))
            path = tuple(
                round(value(gestures[tag], GESTURE_FIELDS, field), 7)
                for tag in range(1, 8)
                for field in ("force_output", "speed_output", "contact_output")
            )
            signatures.append(path)
            samples = stereo_window(rendered[1], 0.01, 0.58)
            if rms(samples) < 1.0:
                failures.append("{} rendered quiet audio".format(name))
            if max(abs(sample) for channel in rendered[1] for sample in channel) \
                    >= 32767:
                failures.append("{} saturated PCM".format(name))
        if len(signatures) == 4 and len(set(signatures)) != 4:
            failures.append("bowed presets did not produce four distinct paths")

        if all(articulation in results and 7 in results[articulation][0]
               for articulation in range(1, 5)):
            detache = results[1][0]
            martele = results[2][0]
            spiccato = results[3][0]
            tremolo = results[4][0]
            if value(martele[1], GESTURE_FIELDS, "force_output") <= value(
                    detache[1], GESTURE_FIELDS, "force_output"):
                failures.append("martele did not build more early bow force")
            contacts = [
                value(spiccato[tag], GESTURE_FIELDS, "contact_output")
                for tag in range(1, 8)
            ]
            if max(contacts) < 0.35 or contacts[-1] > 0.20:
                failures.append("spiccato did not make and release contact")
            if value(tremolo[7], GESTURE_FIELDS, "strokes") < 3.0:
                failures.append("tremolo did not repeat its stroke")
            if value(tremolo[7], GESTURE_FIELDS, "bow_changes") < 2.0:
                failures.append("tremolo did not change bow direction")

        first = results.get(4)
        repeat = run_case(
            failures, "tremolo deterministic repeat", csound, module, csd,
            {"TEST_CASE": 1, "TEST_ARTICULATION": 4},
            tuple(range(1, 8)), tuple(range(1, 8)), tuple(range(1, 8)),
            output=temporary / "tremolo-repeat.wav")
        if first and first[4] and repeat[4]:
            if first[0] != repeat[0]:
                failures.append("tremolo changed deterministic gesture state")
            if first[1] != repeat[1]:
                failures.append("tremolo changed deterministic rail state")
            if first[4][0] != repeat[4][0]:
                failures.append("tremolo changed deterministic PCM")


def check_direct_controls(
    failures: List[str], csound: Path, module: Path, csd: Path,
) -> None:
    with tempfile.TemporaryDirectory(prefix="hlolli-gesture-direct-") as folder:
        result = run_case(
            failures, "direct gesture controls", csound, module, csd,
            {"TEST_CASE": 2, "TEST_END": 0.46}, tuple(range(1, 6)),
            tuple(range(1, 6)), tuple(range(1, 6)),
            output=Path(folder) / "direct.wav")
    gestures, waves, _, _, rendered = result
    if any(tag not in gestures or tag not in waves
           for tag in range(1, 6)) or rendered is None:
        return
    for tag in range(1, 6):
        check_gesture_common(
            failures, "direct control snapshot {}".format(tag), gestures[tag])
        check_wave_common(
            failures, "direct control snapshot {}".format(tag), waves[tag])
    for field, before, after in (
            ("force_target", 0.24, 0.82),
            ("speed_target", 0.34, -0.72)):
        if not close(value(gestures[1], GESTURE_FIELDS, field), before):
            failures.append("direct controls began with the wrong {}".format(field))
        for tag in range(2, 6):
            if not close(value(gestures[tag], GESTURE_FIELDS, field), after):
                failures.append(
                    "direct controls snapshot {} missed {}".format(tag, field))
    if value(gestures[5], GESTURE_FIELDS, "force_output") <= value(
            gestures[1], GESTURE_FIELDS, "force_output"):
        failures.append("direct force override did not reach the shaped path")
    if value(gestures[5], GESTURE_FIELDS, "speed_output") >= -0.05:
        failures.append("direct speed override did not reverse the shaped path")
    if value(gestures[5], GESTURE_FIELDS, "direct_overrides") <= value(
            gestures[1], GESTURE_FIELDS, "direct_overrides"):
        failures.append("direct k-rate changes were not counted")
    if any(value(waves[tag], WAVE_FIELDS, "excitation_count") != 1.0
           for tag in range(1, 6)):
        failures.append("direct controls retriggered the rail")
    mono = stereo_window(rendered[1], 0.0, 0.44)
    if not transition_step_ok(mono, 0.16):
        failures.append("direct k-rate override made a sharp output step")


def check_bow_changes_and_mode_changes(
    failures: List[str], csound: Path, module: Path, csd: Path,
) -> None:
    with tempfile.TemporaryDirectory(prefix="hlolli-gesture-change-") as folder:
        temporary = Path(folder)
        bow = run_case(
            failures, "bow changes", csound, module, csd,
            {"TEST_CASE": 3, "TEST_END": 0.56}, tuple(range(1, 7)),
            tuple(range(1, 7)), tuple(range(1, 7)),
            output=temporary / "bow-changes.wav")
        mode = run_case(
            failures, "held preset changes", csound, module, csd,
            {"TEST_CASE": 4, "TEST_END": 0.50}, tuple(range(1, 7)),
            tuple(range(1, 7)), tuple(range(1, 7)),
            output=temporary / "mode-changes.wav")
    if all(tag in bow[0] and tag in bow[1] for tag in range(1, 7)) and bow[4]:
        for tag in range(1, 7):
            check_gesture_common(
                failures, "bow change snapshot {}".format(tag), bow[0][tag])
            check_wave_common(
                failures, "bow change snapshot {}".format(tag), bow[1][tag])
        if value(bow[0][1], GESTURE_FIELDS, "speed_target") <= 0.0:
            failures.append("bow change did not begin down-bow")
        if value(bow[0][3], GESTURE_FIELDS, "speed_target") >= 0.0:
            failures.append("first bow change missed its up-bow target")
        if value(bow[0][5], GESTURE_FIELDS, "speed_target") <= 0.0:
            failures.append("second bow change missed its down-bow target")
        if value(bow[0][6], GESTURE_FIELDS, "bow_changes") < 2.0:
            failures.append("two bow changes were not counted")
        if value(bow[1][6], WAVE_FIELDS, "excitation_count") != 1.0:
            failures.append("bow changes retriggered the rail")
        mono = stereo_window(bow[4][1], 0.0, 0.54)
        for boundary in (0.18, 0.36):
            if not transition_step_ok(mono, boundary):
                failures.append(
                    "bow change clicked at {:.3f} seconds".format(boundary))

    if all(tag in mode[0] and tag in mode[1] for tag in range(1, 7)) and mode[4]:
        wanted = (1.0, 4.0, 4.0, 0.0, 0.0, 0.0)
        for tag, articulation in enumerate(wanted, 1):
            check_gesture_common(
                failures, "mode change snapshot {}".format(tag), mode[0][tag])
            check_wave_common(
                failures, "mode change snapshot {}".format(tag), mode[1][tag])
            if value(mode[0][tag], GESTURE_FIELDS, "articulation") != articulation:
                failures.append(
                    "mode change snapshot {} kept the wrong preset".format(tag))
            if value(
                    mode[0][tag], GESTURE_FIELDS,
                    "release_articulation") != articulation:
                failures.append(
                    "mode change snapshot {} kept the old release profile".
                    format(tag))
            if value(mode[1][tag], WAVE_FIELDS, "excitation_count") != 1.0:
                failures.append("held mode change retriggered the rail")
        if value(mode[0][6], GESTURE_FIELDS, "preset_changes") < 2.0:
            failures.append("held mode changes were not all counted")
        mono = stereo_window(mode[4][1], 0.0, 0.48)
        for boundary in (0.16, 0.32):
            if not transition_step_ok(mono, boundary):
                failures.append(
                    "held mode change clicked at {:.3f} seconds".format(boundary))


def check_continuous_handoff(
    failures: List[str],
    label: str,
    articulation: int,
    split_time: float,
    csound: Path,
    module: Path,
    csd: Path,
    folder: Path,
) -> None:
    common = {
        "TEST_CASE": 5, "TEST_ARTICULATION": articulation,
        "TEST_END": 0.060,
    }
    reference = run_case(
        failures, label + " reference", csound, module, csd, common,
        (1,), (1,), (1,), output=folder / (label + "-reference.wav"))
    split_defs = dict(common)
    split_defs.update({"TEST_SPLIT": 1, "TEST_SPLIT_TIME": split_time})
    split = run_case(
        failures, label + " split", csound, module, csd, split_defs,
        (1,), (1,), (1,), output=folder / (label + "-split.wav"))
    if reference[4] is None or split[4] is None:
        return
    if reference[4][0] != split[4][0]:
        first = next(
            (index for index, pair in enumerate(zip(reference[4][0], split[4][0]))
             if pair[0] != pair[1]),
            min(len(reference[4][0]), len(split[4][0])),
        )
        failures.append("{} PCM differs first at byte {}".format(label, first))
    for name, index in (("gesture", 0), ("wave", 1), ("string", 2)):
        if 1 in reference[index] and 1 in split[index]:
            same = reference[index][1] == split[index][1]
            if name == "string":
                same = all(close(left, right, 2.0e-12) for left, right in zip(
                    reference[index][1], split[index][1]))
            if not same:
                failures.append("{} changed {} state".format(label, name))
    if 1 in split[1]:
        check_wave_common(failures, label, split[1][1])
        if value(split[1][1], WAVE_FIELDS, "excitation_count") != 1.0:
            failures.append("{} added an attack".format(label))


def check_handoffs(
    failures: List[str], csound: Path, module: Path, csd: Path,
) -> None:
    with tempfile.TemporaryDirectory(prefix="hlolli-gesture-handoff-") as folder:
        temporary = Path(folder)
        check_continuous_handoff(
            failures, "arco block handoff", 0, 0.016,
            csound, module, csd, temporary)
        check_continuous_handoff(
            failures, "arco mid-block handoff", 0, 0.016125,
            csound, module, csd, temporary)
        check_continuous_handoff(
            failures, "tremolo block handoff", 4, 0.016,
            csound, module, csd, temporary)
        check_continuous_handoff(
            failures, "tremolo mid-block handoff", 4, 0.016125,
            csound, module, csd, temporary)

        for articulation in range(1, 4):
            label = "articulation {} reattack handoff".format(articulation)
            result = run_case(
                failures, label, csound, module, csd,
                {"TEST_CASE": 5, "TEST_ARTICULATION": articulation,
                 "TEST_SPLIT": 1, "TEST_SPLIT_TIME": 0.016125,
                 "TEST_END": 0.060},
                (1,), (1,), (1,), output=temporary / "reattack-{}.wav".format(
                    articulation))
            if 1 not in result[0] or 1 not in result[1]:
                continue
            check_gesture_common(failures, label, result[0][1])
            check_wave_common(failures, label, result[1][1])
            if value(result[1][1], WAVE_FIELDS, "excitation_count") != 2.0:
                failures.append("{} did not restart contact".format(label))
            if value(result[0][1], GESTURE_FIELDS, "strokes") < 2.0:
                failures.append("{} did not count the new stroke".format(label))
            energy = value(result[1][1], WAVE_FIELDS, "toward_nut_energy") + \
                value(result[1][1], WAVE_FIELDS, "toward_bridge_energy")
            if energy <= 0.0:
                failures.append("{} lost its stored rail".format(label))


def check_four_strings_and_body(
    failures: List[str], csound: Path, module: Path, csd: Path,
) -> None:
    with tempfile.TemporaryDirectory(prefix="hlolli-gesture-four-") as folder:
        result = run_case(
            failures, "four gesture strings", csound, module, csd,
            {"TEST_CASE": 6}, (1, 2, 3, 4), (1, 2, 3, 4),
            (1, 2, 3, 4), (1,), output=Path(folder) / "four.wav")
    if any(tag not in result[0] or tag not in result[1]
           for tag in range(1, 5)) or 1 not in result[3] or result[4] is None:
        return
    signatures = []
    for tag in range(1, 5):
        gesture = result[0][tag]
        wave_state = result[1][tag]
        check_gesture_common(
            failures, "four-string gesture {}".format(tag), gesture)
        check_wave_common(failures, "four-string wave {}".format(tag), wave_state)
        if value(gesture, GESTURE_FIELDS, "articulation") != float(tag):
            failures.append("four-string gesture {} had the wrong mode".format(tag))
        if value(gesture, GESTURE_FIELDS, "strokes") < 1.0:
            failures.append("four-string gesture {} made no stroke".format(tag))
        signatures.append((
            value(wave_state, WAVE_FIELDS, "toward_nut_signature"),
            value(wave_state, WAVE_FIELDS, "toward_bridge_signature"),
        ))
    if len(set(signatures)) != 4:
        failures.append("four gesture strings shared rail state")
    body = result[3][1]
    if not all(math.isfinite(item) for item in body) or value(
            body, BODY_FIELDS, "finite") != 1.0:
        failures.append("gesture body reported invalid state")
    for lane in range(1, 5):
        if value(body, BODY_FIELDS, "send_energy_{}".format(lane)) <= 0.0:
            failures.append("body lane {} received no gesture energy".format(lane))
    for field in ("drive_energy", "output_energy_left", "output_energy_right"):
        if value(body, BODY_FIELDS, field) <= 0.0:
            failures.append("gesture body had no {}".format(field))
    for field in ("reset_count", "clip_count"):
        if value(body, BODY_FIELDS, field) != 0.0:
            failures.append("gesture body had nonzero {}".format(field))
    peak = max(abs(sample) for channel in result[4][1] for sample in channel)
    if peak == 0 or peak >= 32767:
        failures.append("four gesture strings were silent or saturated")


def check_stress(
    failures: List[str], csound: Path, module: Path, csd: Path,
) -> None:
    with tempfile.TemporaryDirectory(prefix="hlolli-gesture-stress-") as folder:
        result = run_case(
            failures, "gesture stress", csound, module, csd,
            {"TEST_CASE": 7, "TEST_END": 8.05},
            (1, 2, 3, 4), (1, 2, 3, 4), (1, 2, 3, 4), (1,),
            output=Path(folder) / "stress.wav")
    if any(tag not in result[0] or tag not in result[1]
           for tag in range(1, 5)) or 1 not in result[3] or result[4] is None:
        return
    for tag in range(1, 5):
        gesture = result[0][tag]
        wave_state = result[1][tag]
        label = "gesture stress string {}".format(tag)
        check_gesture_common(failures, label, gesture)
        check_wave_common(failures, label, wave_state)
        for field in ("strokes", "bow_changes", "preset_changes",
                      "direct_overrides"):
            if value(gesture, GESTURE_FIELDS, field) < 2.0:
                failures.append("{} made too few {}".format(label, field))
        if value(gesture, GESTURE_FIELDS, "recoveries") != 0.0:
            failures.append("{} needed gesture recovery".format(label))
        if value(wave_state, WAVE_FIELDS, "wave_samples") < 383000.0:
            failures.append("{} skipped rail samples".format(label))
    body = result[3][1]
    if (not all(math.isfinite(item) for item in body) or
            value(body, BODY_FIELDS, "finite") != 1.0 or
            value(body, BODY_FIELDS, "reset_count") != 0.0 or
            value(body, BODY_FIELDS, "clip_count") != 0.0):
        failures.append("gesture stress body left finite bounds")
    peak = max(abs(sample) for channel in result[4][1] for sample in channel)
    if peak == 0 or peak >= 32767:
        failures.append("gesture stress PCM was silent or saturated")


def check_fault_recovery(
    failures: List[str], csound: Path, module: Path, csd: Path,
) -> None:
    with tempfile.TemporaryDirectory(prefix="hlolli-gesture-fault-") as folder:
        temporary = Path(folder)
        for fault, name in enumerate(
                ("phase", "transition", "shaped force"), 1):
            label = "gesture {} fault".format(name)
            result = run_case(
                failures, label, csound, module, csd,
                {"TEST_CASE": 8, "TEST_FAULT": fault, "TEST_END": 0.44},
                (1, 2, 3), (1, 2, 3), (1, 2, 3),
                output=temporary / "fault-{}.wav".format(fault))
            gestures, waves, _, _, rendered = result
            if any(tag not in gestures or tag not in waves
                   for tag in range(1, 4)) or rendered is None:
                continue
            for tag in range(1, 4):
                check_gesture_common(
                    failures, "{} snapshot {}".format(label, tag),
                    gestures[tag])
                check_wave_common(
                    failures, "{} snapshot {}".format(label, tag),
                    waves[tag])
                if value(waves[tag], WAVE_FIELDS, "excitation_count") != 1.0:
                    failures.append("{} retriggered the rail".format(label))
            if value(gestures[1], GESTURE_FIELDS, "recoveries") != 0.0:
                failures.append("{} began with a recovery".format(label))
            for tag in (2, 3):
                if value(gestures[tag], GESTURE_FIELDS, "recoveries") != 1.0:
                    failures.append("{} was not recovered once".format(label))
                if value(gestures[tag], GESTURE_FIELDS, "active") != 1.0:
                    failures.append("{} did not resume the held gesture".format(label))
            before_energy = value(
                waves[1], WAVE_FIELDS, "toward_nut_energy") + value(
                    waves[1], WAVE_FIELDS, "toward_bridge_energy")
            after_energy = value(
                waves[2], WAVE_FIELDS, "toward_nut_energy") + value(
                    waves[2], WAVE_FIELDS, "toward_bridge_energy")
            if before_energy <= 0.0 or after_energy <= 0.0:
                failures.append("{} lost its stored rail".format(label))
            samples = stereo_window(rendered[1], 0.25, 0.40)
            if rms(samples) < 1.0:
                failures.append("{} did not recover audible output".format(label))
            if max(abs(sample) for channel in rendered[1] for sample in channel) \
                    >= 32767:
                failures.append("{} saturated PCM".format(label))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--csound", required=True, type=Path)
    parser.add_argument("--module", required=True, type=Path)
    parser.add_argument("--csd", required=True, type=Path)
    arguments = parser.parse_args()
    failures: List[str] = []

    check_profiles(failures, arguments.csound, arguments.module, arguments.csd)
    check_direct_controls(
        failures, arguments.csound, arguments.module, arguments.csd)
    check_bow_changes_and_mode_changes(
        failures, arguments.csound, arguments.module, arguments.csd)
    check_handoffs(failures, arguments.csound, arguments.module, arguments.csd)
    check_four_strings_and_body(
        failures, arguments.csound, arguments.module, arguments.csd)
    check_stress(failures, arguments.csound, arguments.module, arguments.csd)
    check_fault_recovery(
        failures, arguments.csound, arguments.module, arguments.csd)

    if failures:
        for failure in failures:
            print("FAIL: {}".format(failure), file=sys.stderr)
        return 1
    print("gesture and articulation checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
