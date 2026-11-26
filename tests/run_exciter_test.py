#!/usr/bin/env python3
"""Check pizzicato and wood exciters."""

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

SAMPLE_RATE = 48000
EXCITER_LIMIT = 1.25
EXCITER_FIELDS = (
    "articulation", "mode", "armed", "active", "age",
    "total_samples", "pulse_samples", "notch_delay", "position",
    "contact_target", "contact", "speed_target", "speed", "last_output",
    "energy", "peak", "rng", "pending_impact",
    "normal_pizzicato_attacks", "left_hand_pizzicato_attacks",
    "bartok_pizzicato_attacks", "fingerboard_impacts", "wood_strikes",
    "wood_tratto_attacks", "wood_tratto_samples", "collision_samples",
    "collision_compression", "collision_force", "exciter_samples",
    "recoveries", "finite",
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
    "body", "sympathetic", "mute", "mode_count", "send_samples_1",
    "send_samples_2", "send_samples_3", "send_samples_4", "send_energy_1",
    "send_energy_2", "send_energy_3", "send_energy_4", "last_drive",
    "drive_energy", "modal_energy", "state_signature", "last_left",
    "last_right", "output_energy_left", "output_energy_right", "peak_left",
    "peak_right", "processed_samples", "fast_forward_samples", "reset_count",
    "clip_count", "finite",
)


def value(state: State, fields: Sequence[str], name: str) -> float:
    return state[fields.index(name)]


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
        timeout=30,
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


def read_exciter_states(output: str) -> Dict[int, State]:
    first = read_tagged(output, "WG_EXCITER_A", 16)
    second = read_tagged(output, "WG_EXCITER_B", 15)
    return {
        tag: first[tag] + second[tag]
        for tag in first.keys() & second.keys()
    }


def read_body_states(output: str) -> Dict[int, State]:
    first = read_tagged(output, "WG_BODY_A", 14)
    second = read_tagged(output, "WG_BODY_B", 13)
    return {
        tag: first[tag] + second[tag]
        for tag in first.keys() & second.keys()
    }


def read_wav(path: Path) -> Tuple[bytes, Tuple[List[int], List[int]]]:
    with wave.open(str(path), "rb") as audio:
        if (audio.getframerate() != SAMPLE_RATE or
                audio.getnchannels() != 2 or audio.getsampwidth() != 2):
            raise ValueError("unexpected exciter-test WAV format")
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
    exciter_tags: Sequence[int],
    wave_tags: Sequence[int] = (),
    string_tags: Sequence[int] = (),
    body_tags: Sequence[int] = (),
    output: Path | None = None,
) -> Tuple[Dict[int, State], Dict[int, State], Dict[int, State],
           Dict[int, State], Dict[int, float],
           Tuple[bytes, Tuple[List[int], List[int]]] | None]:
    completed = run_csound(csound, module, csd, definitions, output)
    if completed.returncode != 0:
        failures.append(
            "{} failed with status {}:\n{}".format(
                label, completed.returncode, completed.stdout.rstrip()))
        return {}, {}, {}, {}, {}, None
    exciters = read_exciter_states(completed.stdout)
    waves = read_tagged(completed.stdout, "WG_WAVE", len(WAVE_FIELDS))
    strings = read_tagged(completed.stdout, "WG_STRING", len(STRING_FIELDS))
    bodies = read_body_states(completed.stdout)
    faults = {
        tag: state[0]
        for tag, state in read_tagged(
            completed.stdout, "WG_EXCITER_FAULT", 1).items()
    }
    missing = (
        [tag for tag in exciter_tags if tag not in exciters],
        [tag for tag in wave_tags if tag not in waves],
        [tag for tag in string_tags if tag not in strings],
        [tag for tag in body_tags if tag not in bodies],
    )
    if any(missing):
        failures.append(
            "{} missed exciter {}, wave {}, string {}, or body {} tags:\n{}".
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
    return exciters, waves, strings, bodies, faults, rendered


def check_exciter_common(
    failures: List[str], label: str, state: State,
) -> None:
    if len(state) != len(EXCITER_FIELDS):
        failures.append("{} returned the wrong exciter state size".format(label))
        return
    if not all(math.isfinite(item) for item in state):
        failures.append("{} returned a non-finite exciter value".format(label))
        return
    if value(state, EXCITER_FIELDS, "finite") != 1.0:
        failures.append("{} reported invalid exciter state".format(label))
    peak = value(state, EXCITER_FIELDS, "peak")
    if peak < 0.0 or peak > EXCITER_LIMIT + 1.0e-12:
        failures.append("{} peak was {:.17g}".format(label, peak))
    if value(state, EXCITER_FIELDS, "rng") == 0.0:
        failures.append("{} returned a zero random state".format(label))


def check_wave_common(failures: List[str], label: str, state: State) -> None:
    if len(state) != len(WAVE_FIELDS):
        failures.append("{} returned the wrong wave state size".format(label))
        return
    if not all(math.isfinite(item) for item in state):
        failures.append("{} returned a non-finite wave value".format(label))
        return
    if value(state, WAVE_FIELDS, "finite") != 1.0:
        failures.append("{} reported invalid wave state".format(label))
    for field in ("clear_count", "reset_count", "clip_count"):
        if value(state, WAVE_FIELDS, field) != 0.0:
            failures.append("{} had nonzero {}".format(label, field))


def is_silent(frames: bytes) -> bool:
    return not frames.strip(b"\x00")


def rail_energy(state: State) -> float:
    return (
        value(state, WAVE_FIELDS, "toward_nut_energy") +
        value(state, WAVE_FIELDS, "toward_bridge_energy")
    )


def stereo_rms(
    channels: Tuple[List[int], List[int]], start: float, stop: float,
) -> float:
    first = max(0, int(start * SAMPLE_RATE))
    last = min(len(channels[0]), int(stop * SAMPLE_RATE))
    if last <= first:
        return 0.0
    total = 0.0
    for channel in channels:
        total += sum(float(sample) * float(sample)
                     for sample in channel[first:last])
    return math.sqrt(total / (2.0 * (last - first)))


def partial_power(samples: Sequence[int], frequency: float) -> float:
    start = int(0.006 * SAMPLE_RATE)
    stop = min(len(samples), int(0.076 * SAMPLE_RATE))
    section = samples[start:stop]
    if len(section) < 2:
        return 0.0
    real = 0.0
    imaginary = 0.0
    count = len(section)
    for index, sample in enumerate(section):
        window = 0.5 - 0.5 * math.cos(
            2.0 * math.pi * index / (count - 1))
        angle = 2.0 * math.pi * frequency * (start + index) / SAMPLE_RATE
        scaled = float(sample) * window
        real += scaled * math.cos(angle)
        imaginary -= scaled * math.sin(angle)
    return real * real + imaginary * imaginary


def check_simple_modes(
    failures: List[str], csound: Path, module: Path, csd: Path,
) -> None:
    settings = {
        "normal pizzicato": (5, 0.70, (1, 0, 0, 0, 0, 0)),
        "left-hand pizzicato": (5, -0.70, (0, 1, 0, 0, 0, 0)),
        "Bartok pizzicato": (6, 0.74, (0, 0, 1, 1, 0, 0)),
        "col legno battuto": (7, 0.72, (0, 0, 0, 0, 1, 0)),
        "col legno tratto": (8, -0.55, (0, 0, 0, 0, 0, 1)),
    }
    results: Dict[str, Tuple[State, State, bytes, List[int]]] = {}
    counter_fields = (
        "normal_pizzicato_attacks", "left_hand_pizzicato_attacks",
        "bartok_pizzicato_attacks", "fingerboard_impacts", "wood_strikes",
        "wood_tratto_attacks",
    )
    with tempfile.TemporaryDirectory(prefix="hlolli-exciters-") as folder:
        temporary = Path(folder)
        for label, (mode, speed, counters) in settings.items():
            runs = []
            for repeat in range(2):
                runs.append(run_case(
                    failures, "{} run {}".format(label, repeat + 1),
                    csound, module, csd,
                    {"TEST_CASE": 1, "TEST_MODE": mode,
                     "TEST_SPEED": speed, "TEST_POSITION": 0.25},
                    (1,), (1,),
                    output=temporary / "{}-{}.wav".format(
                        label.replace(" ", "-"), repeat)))
            if any(1 not in run[0] or 1 not in run[1] or run[5] is None
                   for run in runs):
                continue
            exciter = runs[0][0][1]
            wave_state = runs[0][1][1]
            rendered = runs[0][5]
            assert rendered is not None
            check_exciter_common(failures, label, exciter)
            check_wave_common(failures, label, wave_state)
            if runs[0][0][1] != runs[1][0][1]:
                failures.append("{} changed deterministic exciter state".format(label))
            if runs[0][1][1] != runs[1][1][1]:
                failures.append("{} changed deterministic rail state".format(label))
            if runs[0][5][0] != runs[1][5][0]:
                failures.append("{} changed deterministic PCM".format(label))
            if value(exciter, EXCITER_FIELDS, "articulation") != float(mode):
                failures.append("{} stored the wrong articulation".format(label))
            if value(exciter, EXCITER_FIELDS, "mode") != float(mode):
                failures.append("{} stored the wrong exciter mode".format(label))
            if value(exciter, EXCITER_FIELDS, "armed") != 0.0:
                failures.append("{} rearmed while its trigger stayed high".format(label))
            if not math.isclose(
                    value(exciter, EXCITER_FIELDS, "position"), 0.25,
                    rel_tol=2.0e-12, abs_tol=2.0e-12):
                failures.append("{} stored the wrong position".format(label))
            if value(exciter, EXCITER_FIELDS, "notch_delay") != 27.0:
                failures.append("{} stored the wrong notch delay".format(label))
            found_counters = tuple(
                int(value(exciter, EXCITER_FIELDS, field))
                for field in counter_fields)
            if found_counters != counters:
                failures.append(
                    "{} counters were {}, wanted {}".format(
                        label, found_counters, counters))
            if mode == 8:
                if value(exciter, EXCITER_FIELDS, "active") != 1.0:
                    failures.append("tratto contact was not active")
                if value(exciter, EXCITER_FIELDS, "wood_tratto_samples") <= 0.0:
                    failures.append("tratto recorded no contact samples")
                if value(exciter, EXCITER_FIELDS, "contact_target") != 1.0:
                    failures.append("tratto had the wrong contact target")
                wanted_speed = 0.55 * speed
                if not math.isclose(
                        value(exciter, EXCITER_FIELDS, "speed_target"),
                        wanted_speed, rel_tol=2.0e-12, abs_tol=2.0e-12):
                    failures.append("tratto had the wrong speed target")
            else:
                if value(exciter, EXCITER_FIELDS, "active") != 0.0:
                    failures.append("{} one-shot remained active".format(label))
                if (value(exciter, EXCITER_FIELDS, "age") !=
                        value(exciter, EXCITER_FIELDS, "total_samples")):
                    failures.append("{} pulse did not finish".format(label))
                if value(exciter, EXCITER_FIELDS, "total_samples") <= 0.0:
                    failures.append("{} had no pulse length".format(label))
            if mode == 7:
                collision = value(exciter, EXCITER_FIELDS, "collision_samples")
                if not 0.0 < collision <= 144.0:
                    failures.append(
                        "battuto collision samples were {:.17g}".format(collision))
                if (value(exciter, EXCITER_FIELDS, "collision_compression") != 0.0 or
                        value(exciter, EXCITER_FIELDS, "collision_force") != 0.0):
                    failures.append("battuto collision did not settle")
            if value(exciter, EXCITER_FIELDS, "energy") <= 0.0:
                failures.append("{} had no exciter energy".format(label))
            if value(exciter, EXCITER_FIELDS, "exciter_samples") <= 0.0:
                failures.append("{} emitted no exciter samples".format(label))
            if value(wave_state, WAVE_FIELDS, "excitation_count") != 1.0:
                failures.append("{} had the wrong rail attack count".format(label))
            if (value(wave_state, WAVE_FIELDS, "toward_nut_energy") <= 0.0 or
                    value(wave_state, WAVE_FIELDS, "toward_bridge_energy") <= 0.0):
                failures.append("{} left no rail energy".format(label))
            if is_silent(rendered[0]):
                failures.append("{} produced silent PCM".format(label))
            results[label] = (exciter, wave_state, rendered[0], rendered[1][0])

        position_runs = []
        for repeat in range(2):
            position_runs.append(run_case(
                failures, "one-fifth pluck run {}".format(repeat + 1),
                csound, module, csd,
                {"TEST_CASE": 1, "TEST_MODE": 5, "TEST_SPEED": 0.70,
                 "TEST_POSITION": 0.20},
                (1,), (1,),
                output=temporary / "one-fifth-{}.wav".format(repeat)))
        if all(1 in run[0] and run[5] is not None for run in position_runs):
            fifth_exciter = position_runs[0][0][1]
            fifth_render = position_runs[0][5]
            assert fifth_render is not None
            if value(fifth_exciter, EXCITER_FIELDS, "notch_delay") != 22.0:
                failures.append("one-fifth pluck stored the wrong notch delay")
            if position_runs[0][0][1] != position_runs[1][0][1]:
                failures.append("one-fifth pluck changed deterministic state")
            if position_runs[0][5][0] != position_runs[1][5][0]:
                failures.append("one-fifth pluck changed deterministic PCM")
            if "normal pizzicato" in results:
                quarter_samples = results["normal pizzicato"][3]
                fifth_samples = fifth_render[1][0]
                if results["normal pizzicato"][2] == fifth_render[0]:
                    failures.append("pluck position did not change PCM")
                quarter = [partial_power(quarter_samples, 440.0 * order)
                           for order in (3, 4, 5)]
                fifth = [partial_power(fifth_samples, 440.0 * order)
                         for order in (4, 5, 6)]
                quarter_ratio = quarter[1] / max(
                    1.0, 0.5 * (quarter[0] + quarter[2]))
                fifth_ratio = fifth[1] / max(
                    1.0, 0.5 * (fifth[0] + fifth[2]))
                if quarter_ratio >= 0.35:
                    failures.append(
                        "quarter-position fourth-partial ratio was {:.6g}".
                        format(quarter_ratio))
                if fifth_ratio >= 0.35:
                    failures.append(
                        "fifth-position fifth-partial ratio was {:.6g}".
                        format(fifth_ratio))

    if "normal pizzicato" in results and "left-hand pizzicato" in results:
        normal_energy = value(
            results["normal pizzicato"][0], EXCITER_FIELDS, "energy")
        left_energy = value(
            results["left-hand pizzicato"][0], EXCITER_FIELDS, "energy")
        if left_energy >= normal_energy:
            failures.append("left-hand pizzicato was not weaker than normal pizzicato")
    if "normal pizzicato" in results and "Bartok pizzicato" in results:
        normal_energy = value(
            results["normal pizzicato"][0], EXCITER_FIELDS, "energy")
        bartok_energy = value(
            results["Bartok pizzicato"][0], EXCITER_FIELDS, "energy")
        if bartok_energy <= normal_energy:
            failures.append("Bartok pizzicato did not exceed normal pluck energy")


def check_latch(
    failures: List[str], csound: Path, module: Path, csd: Path,
) -> None:
    exciters, waves, _, _, _, _ = run_case(
        failures, "one-shot gate latch", csound, module, csd,
        {"TEST_CASE": 2}, (1, 2, 3), (3,))
    if any(tag not in exciters for tag in (1, 2, 3)) or 3 not in waves:
        return
    for tag in (1, 2, 3):
        check_exciter_common(failures, "gate snapshot {}".format(tag), exciters[tag])
    attacks = [
        value(exciters[tag], EXCITER_FIELDS, "normal_pizzicato_attacks")
        for tag in (1, 2, 3)
    ]
    armed = [value(exciters[tag], EXCITER_FIELDS, "armed")
             for tag in (1, 2, 3)]
    if attacks != [1.0, 1.0, 2.0]:
        failures.append("held/rearmed pizzicato attacks were {}".format(attacks))
    if armed != [0.0, 1.0, 0.0]:
        failures.append("held/rearmed pizzicato latch was {}".format(armed))
    check_wave_common(failures, "one-shot gate latch", waves[3])
    if value(waves[3], WAVE_FIELDS, "excitation_count") != 2.0:
        failures.append("rearmed pizzicato did not count two rail attacks")


def check_held_mode_change_latch(
    failures: List[str], csound: Path, module: Path, csd: Path,
) -> None:
    exciters, waves, _, _, _, _ = run_case(
        failures, "held one-shot mode changes", csound, module, csd,
        {"TEST_CASE": 10, "TEST_END": 0.05}, (1, 2, 3), (1,))
    if any(tag not in exciters for tag in (1, 2, 3)) or 1 not in waves:
        return
    for tag in (1, 2, 3):
        check_exciter_common(
            failures, "held mode snapshot {}".format(tag), exciters[tag])
    articulations = [
        value(exciters[tag], EXCITER_FIELDS, "articulation")
        for tag in (1, 2, 3)
    ]
    if articulations != [5.0, 6.0, 7.0]:
        failures.append(
            "held one-shot articulations were {}".format(articulations))
    for tag in (1, 2, 3):
        state = exciters[tag]
        for field, wanted in (
                ("mode", 5.0),
                ("armed", 0.0),
                ("normal_pizzicato_attacks", 1.0),
                ("left_hand_pizzicato_attacks", 0.0),
                ("bartok_pizzicato_attacks", 0.0),
                ("fingerboard_impacts", 0.0),
                ("wood_strikes", 0.0)):
            if value(state, EXCITER_FIELDS, field) != wanted:
                failures.append(
                    "held mode snapshot {} had {} {}, wanted {}".format(
                        tag, field, value(state, EXCITER_FIELDS, field),
                        wanted))
    check_wave_common(failures, "held one-shot mode changes", waves[1])
    if value(waves[1], WAVE_FIELDS, "excitation_count") != 1.0:
        failures.append("held one-shot mode changes added a rail attack")


def check_handoffs(
    failures: List[str], csound: Path, module: Path, csd: Path,
) -> None:
    with tempfile.TemporaryDirectory(prefix="hlolli-exciter-handoff-") as folder:
        temporary = Path(folder)
        reference = run_case(
            failures, "continuous tratto", csound, module, csd,
            {"TEST_CASE": 3, "TEST_MODE": 8, "TEST_SPEED": -0.55},
            (1,), (1,), output=temporary / "tratto-continuous.wav")
        if 1 in reference[0] and 1 in reference[1] and reference[5] is not None:
            for name, split_time in (("block", 0.016),
                                     ("mid-block", 0.016125)):
                split = run_case(
                    failures, "{} tratto handoff".format(name),
                    csound, module, csd,
                    {"TEST_CASE": 3, "TEST_MODE": 8, "TEST_SPEED": -0.55,
                     "TEST_SPLIT": 1, "TEST_SPLIT_TIME": split_time},
                    (1,), (1,),
                    output=temporary / "tratto-{}.wav".format(name))
                if 1 not in split[0] or 1 not in split[1] or split[5] is None:
                    continue
                if split[0][1] != reference[0][1]:
                    failures.append("{} tratto handoff changed exciter state".format(name))
                if split[1][1] != reference[1][1]:
                    failures.append("{} tratto handoff changed rail state".format(name))
                if split[5][0] != reference[5][0]:
                    failures.append("{} tratto handoff changed PCM".format(name))

        continuous = run_case(
            failures, "continuous one-shot", csound, module, csd,
            {"TEST_CASE": 3, "TEST_MODE": 5, "TEST_SPEED": 0.70},
            (1,), (1,), output=temporary / "pizz-continuous.wav")
        split = run_case(
            failures, "exact one-shot reattack", csound, module, csd,
            {"TEST_CASE": 3, "TEST_MODE": 5, "TEST_SPEED": 0.70,
             "TEST_SPLIT": 1, "TEST_SPLIT_TIME": 0.016125},
            (1,), (1,), output=temporary / "pizz-split.wav")
        if (1 in continuous[0] and 1 in continuous[1] and
                1 in split[0] and 1 in split[1] and
                continuous[5] is not None and split[5] is not None):
            if value(
                    continuous[0][1], EXCITER_FIELDS,
                    "normal_pizzicato_attacks") != 1.0:
                failures.append("continuous pizzicato had the wrong attack count")
            if value(
                    split[0][1], EXCITER_FIELDS,
                    "normal_pizzicato_attacks") != 2.0:
                failures.append("exact positive pizzicato edge did not reattack")
            if value(split[1][1], WAVE_FIELDS, "excitation_count") != 2.0:
                failures.append("exact positive pizzicato edge missed a rail attack")
            check_wave_common(failures, "exact one-shot reattack", split[1][1])
            if continuous[5][0] == split[5][0]:
                failures.append("exact positive pizzicato reattack did not change PCM")


def check_four_strings_and_body(
    failures: List[str], csound: Path, module: Path, csd: Path,
) -> None:
    with tempfile.TemporaryDirectory(prefix="hlolli-exciter-four-") as folder:
        result = run_case(
            failures, "four exciter strings", csound, module, csd,
            {"TEST_CASE": 4}, (1, 2, 3, 4), (1, 2, 3, 4),
            (1, 2, 3, 4), (1,), output=Path(folder) / "four.wav")
    exciters, waves, strings, bodies, _, rendered = result
    if any(tag not in exciters or tag not in waves or tag not in strings
           for tag in (1, 2, 3, 4)) or 1 not in bodies or rendered is None:
        return
    wanted_modes = (5.0, 6.0, 7.0, 8.0)
    rng_states = []
    rail_signatures = []
    for tag, mode in zip((1, 2, 3, 4), wanted_modes):
        check_exciter_common(failures, "four-string exciter {}".format(tag),
                             exciters[tag])
        check_wave_common(failures, "four-string rail {}".format(tag), waves[tag])
        if value(exciters[tag], EXCITER_FIELDS, "mode") != mode:
            failures.append("string {} stored the wrong mode".format(tag))
        if (value(strings[tag], STRING_FIELDS, "owner") != 0.0 or
                value(strings[tag], STRING_FIELDS, "successor") != 0.0):
            failures.append("string {} kept an owner after release".format(tag))
        rng_states.append(value(exciters[tag], EXCITER_FIELDS, "rng"))
        rail_signatures.append((
            value(waves[tag], WAVE_FIELDS, "toward_nut_signature"),
            value(waves[tag], WAVE_FIELDS, "toward_bridge_signature"),
        ))
    if len(set(rng_states)) != 4:
        failures.append("four exciters shared random state")
    if len(set(rail_signatures)) != 4:
        failures.append("four exciters shared rail state")
    body = bodies[1]
    if value(body, BODY_FIELDS, "finite") != 1.0:
        failures.append("four-string body reported invalid state")
    for lane in range(1, 5):
        if value(body, BODY_FIELDS, "send_energy_{}".format(lane)) <= 0.0:
            failures.append("body lane {} received no exciter energy".format(lane))
    if (value(body, BODY_FIELDS, "drive_energy") <= 0.0 or
            value(body, BODY_FIELDS, "output_energy_left") <= 0.0 or
            value(body, BODY_FIELDS, "output_energy_right") <= 0.0):
        failures.append("four exciters produced no wet body energy")
    if (value(body, BODY_FIELDS, "reset_count") != 0.0 or
            value(body, BODY_FIELDS, "clip_count") != 0.0):
        failures.append("four exciters tripped body recovery")
    if is_silent(rendered[0]):
        failures.append("four exciters produced silent PCM")


def check_silence(
    failures: List[str], csound: Path, module: Path, csd: Path,
) -> None:
    with tempfile.TemporaryDirectory(prefix="hlolli-exciter-silence-") as folder:
        for label, mode, trigger in (
            ("reserved articulation", 9, 1),
            ("zero-trigger pizzicato", 5, 0),
        ):
            result = run_case(
                failures, label, csound, module, csd,
                {"TEST_CASE": 5, "TEST_MODE": mode,
                 "TEST_TRIGGER": trigger},
                (1,), (1,), output=Path(folder) / "{}.wav".format(mode))
            if 1 not in result[0] or 1 not in result[1] or result[5] is None:
                continue
            exciter = result[0][1]
            wave_state = result[1][1]
            check_exciter_common(failures, label, exciter)
            check_wave_common(failures, label, wave_state)
            for field in (
                "normal_pizzicato_attacks", "left_hand_pizzicato_attacks",
                "bartok_pizzicato_attacks", "fingerboard_impacts",
                "wood_strikes", "wood_tratto_attacks", "exciter_samples",
                "energy", "peak",
            ):
                if value(exciter, EXCITER_FIELDS, field) != 0.0:
                    failures.append("{} had nonzero {}".format(label, field))
            if value(wave_state, WAVE_FIELDS, "excitation_count") != 0.0:
                failures.append("{} excited its rail".format(label))
            if not is_silent(result[5][0]):
                failures.append("{} produced nonzero PCM".format(label))

        for control, definitions in (
            ("zero force", {"TEST_FORCE": 0}),
            ("zero speed", {"TEST_SPEED": 0}),
        ):
            for mode in range(5, 9):
                label = "{} articulation {}".format(control, mode)
                output = Path(folder) / "{}-{}.wav".format(
                    control.replace(" ", "-"), mode)
                result = run_case(
                    failures, label, csound, module, csd,
                    {"TEST_CASE": 5, "TEST_MODE": mode, **definitions},
                    (1,), (1,), output=output)
                if (1 not in result[0] or 1 not in result[1] or
                        result[5] is None):
                    continue
                exciter = result[0][1]
                wave_state = result[1][1]
                check_exciter_common(failures, label, exciter)
                check_wave_common(failures, label, wave_state)
                for field in ("exciter_samples", "energy", "peak"):
                    if value(exciter, EXCITER_FIELDS, field) != 0.0:
                        failures.append(
                            "{} had nonzero {}".format(label, field))
                for field in ("toward_nut_energy", "toward_bridge_energy"):
                    if value(wave_state, WAVE_FIELDS, field) != 0.0:
                        failures.append(
                            "{} had nonzero {}".format(label, field))
                if not is_silent(result[5][0]):
                    failures.append("{} produced nonzero PCM".format(label))


def check_fault_recovery(
    failures: List[str], csound: Path, module: Path, csd: Path,
) -> None:
    for fault in (1, 2, 3):
        label = "exciter fault {}".format(fault)
        result = run_case(
            failures, label, csound, module, csd,
            {"TEST_CASE": 6, "TEST_FAULT": fault}, (1,), (1,))
        if 1 not in result[0] or 1 not in result[1]:
            continue
        if result[4].get(1) != 1.0:
            failures.append("{} helper did not run".format(label))
        check_exciter_common(failures, label, result[0][1])
        check_wave_common(failures, label, result[1][1])
        if value(result[0][1], EXCITER_FIELDS, "recoveries") != 1.0:
            failures.append("{} did not recover exactly once".format(label))
        counter = {
            1: "normal_pizzicato_attacks",
            2: "wood_strikes",
            3: "wood_tratto_attacks",
        }[fault]
        if value(result[0][1], EXCITER_FIELDS, counter) != 1.0:
            failures.append("{} reattacked its held gate".format(label))
        if value(result[1][1], WAVE_FIELDS, "excitation_count") != 1.0:
            failures.append("{} added a rail attack during recovery".format(
                label))


def check_handle_isolation(
    failures: List[str], csound: Path, module: Path, csd: Path,
) -> None:
    alone = run_case(
        failures, "handle B alone", csound, module, csd,
        {"TEST_CASE": 7, "TEST_TRIGGER": 0}, (1,), (1,))
    together = run_case(
        failures, "handle B beside A", csound, module, csd,
        {"TEST_CASE": 7, "TEST_TRIGGER": 1}, (1,), (1,))
    if (1 in alone[0] and 1 in alone[1] and
            1 in together[0] and 1 in together[1]):
        if alone[0][1] != together[0][1]:
            failures.append("handle A changed handle B exciter state")
        if alone[1][1] != together[1][1]:
            failures.append("handle A changed handle B rail state")


def check_release_decay(
    failures: List[str], csound: Path, module: Path, csd: Path,
) -> None:
    note_off = 0.12
    offsets = (0.050, 0.100, 0.250, 0.500)
    settings = (
        ("arco", 0, 0.55, 0.42),
        ("detache", 1, 0.55, 0.38),
        ("martele", 2, 0.55, 0.13),
        ("spiccato", 3, 0.55, 0.09),
        ("tremolo", 4, 0.55, 0.18),
        ("normal pizzicato", 5, 0.70, 0.72),
        ("left-hand pizzicato", 5, -0.70, 0.32),
        ("Bartok pizzicato", 6, 0.74, 0.38),
        ("col legno battuto", 7, 0.72, 0.16),
        ("col legno tratto", 8, -0.55, 0.22),
    )
    energy_ratios: Dict[str, Tuple[float, ...]] = {}

    with tempfile.TemporaryDirectory(prefix="hlolli-release-decay-") as folder:
        temporary = Path(folder)
        for label, mode, speed, time_to_60_db in settings:
            frequency = 440.0 * 2.0 ** (1.0 / 12.0) if mode in (0, 1) else 440.0
            result = run_case(
                failures, label + " release", csound, module, csd,
                {"TEST_CASE": 8, "TEST_MODE": mode, "TEST_SPEED": speed,
                 "TEST_NOTE_OFF": note_off, "TEST_END": 0.64,
                 "TEST_ATTACK_FREQUENCY": frequency,
                 "TEST_RELEASE_FREQUENCY": frequency},
                (1,), (1, 2, 3, 4, 5),
                output=temporary / (label.replace(" ", "-") + ".wav"))
            exciters, waves, _, _, _, rendered = result
            if (1 not in exciters or
                    any(tag not in waves for tag in (1, 2, 3, 4, 5)) or
                    rendered is None):
                continue
            check_exciter_common(failures, label + " release", exciters[1])
            for tag in (1, 2, 3, 4, 5):
                check_wave_common(
                    failures, "{} release snapshot {}".format(label, tag),
                    waves[tag])

            reference_energy = rail_energy(waves[1])
            reference_audio = stereo_rms(
                rendered[1], note_off - 0.030, note_off - 0.010)
            if reference_energy <= 1.0e-16:
                failures.append("{} had no rail energy at note-off".format(label))
                continue
            if reference_audio <= 0.0:
                failures.append("{} had no dry audio at note-off".format(label))
                continue

            found_energy = tuple(
                rail_energy(waves[tag]) / reference_energy
                for tag in (2, 3, 4, 5))
            found_audio = tuple(
                stereo_rms(
                    rendered[1], note_off + offset - 0.010,
                    note_off + offset + 0.010) / reference_audio
                for offset in offsets)
            energy_ratios[label] = found_energy

            for index, offset in enumerate(offsets):
                predicted_energy = 10.0 ** (
                    -6.0 * offset / time_to_60_db)
                predicted_audio = 10.0 ** (
                    -3.0 * offset / time_to_60_db)
                energy_factor = (256.0, 160.0, 8.0, 16.0)[index]
                energy_ceiling = (0.65, 0.30, 0.08, 0.005)[index]
                audio_ceiling = (0.90, 0.75, 0.30, 0.08)[index]
                energy_limit = min(
                    energy_ceiling,
                    max(1.0e-8, energy_factor * predicted_energy))
                audio_limit = min(
                    audio_ceiling,
                    max(1.0e-4, 2.5 * predicted_audio))
                # The 16-bit WAV reaches its measurement floor before the
                # quickest rails reach their double-precision floor.
                audio_limit = max(audio_limit, 4.0 / reference_audio)
                if found_energy[index] > energy_limit:
                    failures.append(
                        "{} rail ratio at {} ms was {:.6g}, limit {:.6g}".
                        format(label, int(offset * 1000),
                               found_energy[index], energy_limit))
                if found_audio[index] > audio_limit:
                    failures.append(
                        "{} audio ratio at {} ms was {:.6g}, limit {:.6g}".
                        format(label, int(offset * 1000),
                               found_audio[index], audio_limit))
                if index > 0 and found_energy[index] > found_energy[index - 1]:
                    failures.append(
                        "{} rail energy rose between {} and {} ms".format(
                            label, int(offsets[index - 1] * 1000),
                            int(offset * 1000)))

    at_100_ms = {
        label: ratios[1] for label, ratios in energy_ratios.items()
    }
    ordered = (
        ("martele", "detache", 0.35),
        ("spiccato", "detache", 0.35),
        ("tremolo", "detache", 0.35),
        ("left-hand pizzicato", "normal pizzicato", 0.40),
        ("Bartok pizzicato", "normal pizzicato", 0.40),
        ("col legno battuto", "Bartok pizzicato", 0.10),
        ("col legno tratto", "normal pizzicato", 0.20),
    )
    for shorter, longer, maximum_ratio in ordered:
        if shorter not in at_100_ms or longer not in at_100_ms:
            continue
        ratio = at_100_ms[shorter] / at_100_ms[longer]
        if ratio >= maximum_ratio:
            failures.append(
                "{} to {} rail ratio at 100 ms was {:.6g}, limit {:.6g}".
                format(shorter, longer, ratio, maximum_ratio))
    if "detache" in energy_ratios and "arco" in energy_ratios:
        ratio = energy_ratios["detache"][3] / energy_ratios["arco"][3]
        if ratio >= 0.80:
            failures.append(
                "detache to arco rail ratio at 500 ms was {:.6g}, "
                "limit 0.8".format(ratio))


def release_energy_ratios(waves: Mapping[int, State]) -> Tuple[float, ...]:
    reference = rail_energy(waves[1])
    if reference <= 0.0:
        return ()
    return tuple(rail_energy(waves[tag]) / reference
                 for tag in (2, 3, 4, 5))


def check_open_bow_release(
    failures: List[str], csound: Path, module: Path, csd: Path,
) -> None:
    tags = (1, 2, 3, 4, 5)
    for label, mode in (("open arco", 0), ("open detache", 1)):
        _, waves, _, _, _, _ = run_case(
            failures, label, csound, module, csd,
            {"TEST_CASE": 8, "TEST_MODE": mode, "TEST_SPEED": 0.55,
             "TEST_NOTE_OFF": 0.12, "TEST_END": 0.64},
            (1,), tags)
        if any(tag not in waves for tag in tags):
            continue
        for tag in tags:
            check_wave_common(failures, f"{label} release snapshot {tag}", waves[tag])
        ratios = release_energy_ratios(waves)
        if not ratios or not (0.02 < ratios[2] < 0.10 and
                              0.0 < ratios[3] < 0.01):
            failures.append(f"{label} had unexpected release energy ratios {ratios}")
        if any(newer >= older for older, newer in zip(ratios, ratios[1:])):
            failures.append(f"{label} release energy did not fall steadily")


def check_release_pitch_and_profile(
    failures: List[str], csound: Path, module: Path, csd: Path,
) -> None:
    base = {
        "TEST_CASE": 8,
        "TEST_MODE": 5,
        "TEST_SPEED": 0.70,
        "TEST_NOTE_OFF": 0.12,
        "TEST_END": 0.64,
    }
    runs = {
        "stable low pitch": {
            "TEST_ATTACK_FREQUENCY": 220,
            "TEST_RELEASE_FREQUENCY": 220,
        },
        "pitch change at release": {
            "TEST_ATTACK_FREQUENCY": 440,
            "TEST_RELEASE_FREQUENCY": 220,
        },
        "pitch change during release": {
            "TEST_ATTACK_FREQUENCY": 440,
            "TEST_RELEASE_FREQUENCY": 440,
            "TEST_RELEASE_CHANGE": 0.22,
            "TEST_RELEASE_FREQUENCY_2": 220,
        },
        "stable release controls": {},
        "changed release speed": {"TEST_RELEASE_SPEED": -0.70},
        "changed release articulation": {"TEST_RELEASE_MODE": 6},
    }
    results: Dict[str, Tuple[Dict[int, State], Dict[int, State]]] = {}

    for label, extra in runs.items():
        result = run_case(
            failures, label, csound, module, csd,
            {**base, **extra}, (1,), (1, 2, 3, 4, 5))
        exciters, waves = result[0], result[1]
        if 1 not in exciters or any(tag not in waves
                                    for tag in (1, 2, 3, 4, 5)):
            continue
        check_exciter_common(failures, label, exciters[1])
        for tag in (1, 2, 3, 4, 5):
            check_wave_common(
                failures, "{} snapshot {}".format(label, tag), waves[tag])
        results[label] = (exciters, waves)

    pitch_labels = (
        "stable low pitch",
        "pitch change at release",
        "pitch change during release",
    )
    expected = tuple(10.0 ** (-6.0 * offset / 0.72)
                     for offset in (0.050, 0.100, 0.250, 0.500))
    stable_ratios: Tuple[float, ...] = ()
    if "stable low pitch" in results:
        stable_ratios = release_energy_ratios(
            results["stable low pitch"][1])
    for label in pitch_labels:
        if label not in results:
            continue
        waves = results[label][1]
        ratios = release_energy_ratios(waves)
        if not ratios:
            failures.append("{} had no rail energy at note-off".format(label))
            continue
        if abs(value(waves[5], WAVE_FIELDS, "target_frequency") - 220.0) > 1.0e-9:
            failures.append("{} did not finish at 220 Hz".format(label))
        for offset, found, wanted in zip(
                (0.050, 0.100, 0.250, 0.500), ratios, expected):
            if found < 0.25 * wanted or found > 2.0 * wanted:
                failures.append(
                    "{} rail ratio at {} ms was {:.6g}, target {:.6g}".
                    format(label, int(offset * 1000), found, wanted))
        if stable_ratios and label != "stable low pitch":
            for offset, found, stable in zip(
                    (0.050, 0.100, 0.250, 0.500), ratios, stable_ratios):
                if found < 0.45 * stable or found > 2.2 * stable:
                    failures.append(
                        "{} changed the {} ms tail ratio from {:.6g} to {:.6g}".
                        format(label, int(offset * 1000), stable, found))

    if "stable release controls" in results:
        stable_exciter, stable_waves = results["stable release controls"]
        stable_energy = tuple(rail_energy(stable_waves[tag])
                              for tag in (1, 2, 3, 4, 5))
        for label in (
                "changed release speed", "changed release articulation"):
            if label not in results:
                continue
            exciter, waves = results[label]
            found_energy = tuple(rail_energy(waves[tag])
                                 for tag in (1, 2, 3, 4, 5))
            for tag, stable, found in zip(
                    (1, 2, 3, 4, 5), stable_energy, found_energy):
                if not math.isclose(
                        found, stable, rel_tol=1.0e-12, abs_tol=1.0e-18):
                    failures.append(
                        "{} changed attack-time tail energy at snapshot {}".
                        format(label, tag))
            for field, wanted in (
                    ("mode", 5.0),
                    ("normal_pizzicato_attacks", 1.0),
                    ("left_hand_pizzicato_attacks", 0.0),
                    ("bartok_pizzicato_attacks", 0.0)):
                if value(exciter[1], EXCITER_FIELDS, field) != wanted:
                    failures.append(
                        "{} stored the wrong {}".format(label, field))
        if value(
                stable_exciter[1], EXCITER_FIELDS,
                "normal_pizzicato_attacks") != 1.0:
            failures.append("stable release controls lost its attack")


def check_early_one_shot_release(
    failures: List[str], csound: Path, module: Path, csd: Path,
) -> None:
    note_off_samples = 4.0
    note_off = note_off_samples / SAMPLE_RATE
    settings = (
        ("early pizzicato release", 5, 0.70),
        ("early Bartok release", 6, 0.74),
    )
    for label, mode, speed in settings:
        result = run_case(
            failures, label, csound, module, csd,
            {"TEST_CASE": 9, "TEST_MODE": mode, "TEST_SPEED": speed,
             "TEST_NOTE_OFF": note_off, "TEST_END": 0.40},
            (1, 2), (1, 2, 3, 4))
        exciters, waves = result[0], result[1]
        if (any(tag not in exciters for tag in (1, 2)) or
                any(tag not in waves for tag in (1, 2, 3, 4))):
            continue
        for tag in (1, 2):
            check_exciter_common(
                failures, "{} exciter {}".format(label, tag), exciters[tag])
        for tag in (1, 2, 3, 4):
            check_wave_common(
                failures, "{} rail {}".format(label, tag), waves[tag])

        total = value(exciters[2], EXCITER_FIELDS, "total_samples")
        if total <= note_off_samples:
            failures.append("{} ended after its transient".format(label))
        if value(exciters[2], EXCITER_FIELDS, "age") != total:
            failures.append("{} did not finish its stored transient".format(label))
        if value(exciters[2], EXCITER_FIELDS, "active") != 0.0:
            failures.append("{} stayed active after its transient".format(label))

        if mode == 5:
            if value(
                    exciters[2], EXCITER_FIELDS,
                    "normal_pizzicato_attacks") != 1.0:
                failures.append("early pizzicato release lost its attack")
        else:
            if value(exciters[1], EXCITER_FIELDS, "pending_impact") != 1.0:
                failures.append("early Bartok release dropped its pending impact")
            if value(
                    exciters[2], EXCITER_FIELDS,
                    "fingerboard_impacts") != 1.0:
                failures.append("early Bartok release missed its delayed impact")

        energies = tuple(rail_energy(waves[tag]) for tag in (1, 2, 3, 4))
        if min(energies) <= 0.0:
            failures.append("{} left an empty rail".format(label))
            continue
        if not (energies[3] < energies[2] < energies[1]):
            failures.append("{} rails did not decay after the transient".format(label))
        if energies[3] >= 0.01 * energies[1]:
            failures.append("{} rail tail stayed too loud".format(label))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--csound", required=True, type=Path)
    parser.add_argument("--module", required=True, type=Path)
    parser.add_argument("--csd", required=True, type=Path)
    arguments = parser.parse_args()
    failures: List[str] = []

    check_simple_modes(
        failures, arguments.csound, arguments.module, arguments.csd)
    check_latch(failures, arguments.csound, arguments.module, arguments.csd)
    check_held_mode_change_latch(
        failures, arguments.csound, arguments.module, arguments.csd)
    check_handoffs(failures, arguments.csound, arguments.module, arguments.csd)
    check_four_strings_and_body(
        failures, arguments.csound, arguments.module, arguments.csd)
    check_silence(failures, arguments.csound, arguments.module, arguments.csd)
    check_fault_recovery(
        failures, arguments.csound, arguments.module, arguments.csd)
    check_handle_isolation(
        failures, arguments.csound, arguments.module, arguments.csd)
    check_release_decay(
        failures, arguments.csound, arguments.module, arguments.csd)
    check_open_bow_release(
        failures, arguments.csound, arguments.module, arguments.csd)
    check_release_pitch_and_profile(
        failures, arguments.csound, arguments.module, arguments.csd)
    check_early_one_shot_release(
        failures, arguments.csound, arguments.module, arguments.csd)

    if failures:
        for failure in failures:
            print("FAIL: {}".format(failure), file=sys.stderr)
        return 1
    print("pizzicato and wood exciter checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
