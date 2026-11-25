#!/usr/bin/env python3
"""Check legato pitch control, string choice, and double stops."""

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

STRING_FIELDS = (
    "phase", "vibrato_phase", "frequency", "trigger", "force", "speed",
    "activity", "last_sample", "gap_samples", "owner", "successor",
)
FINGER_FIELDS = (
    "open_frequency", "target_position", "position", "target_pressure",
    "pressure", "velocity", "delay_velocity", "effective_frequency",
    "last_noise", "noise_energy", "noise_peak", "noise_state", "arrivals",
    "releases", "shifts", "movement_samples", "noise_samples", "finite",
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
BOW_FIELDS = (
    "state", "bow_speed", "contact", "free_velocity", "relative_velocity",
    "friction_force", "junction_increment", "state_transitions",
    "direction_changes", "attacks", "recoveries", "finite",
)
FIELDS = {
    "WG_STRING": STRING_FIELDS,
    "WG_FINGER": FINGER_FIELDS,
    "WG_WAVE": WAVE_FIELDS,
    "WG_BOW": BOW_FIELDS,
}


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
            "--omacro:{}={}".format(name, value)
            for name, value in definitions.items()
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
        timeout=20,
        check=False,
    )


def read_states(output: str, marker: str) -> Dict[int, State]:
    fields = FIELDS[marker]
    states: Dict[int, State] = {}
    for line in output.splitlines():
        start = line.find(marker + " ")
        if start < 0:
            continue
        words = line[start:].split()
        if len(words) < len(fields) + 2:
            continue
        tag = int(float(words[1]))
        states[tag] = tuple(float(item) for item in words[2:2 + len(fields)])
    return states


def value(state: State, marker: str, name: str) -> float:
    return state[FIELDS[marker].index(name)]


def run_success(
    failures: List[str],
    label: str,
    csound: Path,
    module: Path,
    csd: Path,
    definitions: Mapping[str, object],
    tags: Sequence[int],
) -> Dict[str, Dict[int, State]]:
    completed = run_csound(csound, module, csd, definitions)
    if completed.returncode != 0:
        failures.append(
            "{} failed with status {}:\n{}".format(
                label, completed.returncode, completed.stdout.rstrip()))
        return {}
    result: Dict[str, Dict[int, State]] = {}
    for marker in FIELDS:
        states = read_states(completed.stdout, marker)
        result[marker] = states
        missing = [tag for tag in tags if tag not in states]
        if missing:
            failures.append(
                "{} printed no {} state for tags {}:\n{}".format(
                    label, marker, missing, completed.stdout.rstrip()))
    return result


def expect_failure(
    failures: List[str],
    label: str,
    csound: Path,
    module: Path,
    csd: Path,
    definitions: Mapping[str, object],
    message: str,
) -> None:
    completed = run_csound(csound, module, csd, definitions)
    if completed.returncode == 0:
        failures.append("{} was accepted".format(label))
    elif message not in completed.stdout:
        failures.append(
            "{} lacked {!r}:\n{}".format(
                label, message, completed.stdout.rstrip()))


def check_finite(failures: List[str], label: str, states: Mapping[str, Dict[int, State]]) -> None:
    active = {
        tag for tag, state in states.get("WG_STRING", {}).items()
        if value(state, "WG_STRING", "owner") == 1.0
    }
    for marker, tagged in states.items():
        for tag, state in tagged.items():
            if not all(math.isfinite(item) for item in state):
                failures.append("{} {} {} has a non-finite value".format(label, marker, tag))
            if marker in ("WG_FINGER", "WG_WAVE", "WG_BOW"):
                if marker == "WG_BOW" and tag not in active:
                    continue
                if value(state, marker, "finite") != 1.0:
                    failures.append("{} {} {} reports invalid state".format(label, marker, tag))


def check_auto_choice(
    failures: List[str], csound: Path, module: Path, csd: Path,
) -> None:
    cases = (
        (195.997717990875, 1),
        (293.0, 1),
        (293.664767917408, 2),
        (439.0, 2),
        (440.0, 3),
        (659.0, 3),
        (659.25511382574, 4),
    )
    for frequency, wanted_string in cases:
        label = "auto {:.12g} Hz".format(frequency)
        states = run_success(
            failures,
            label,
            csound,
            module,
            csd,
            {"TEST_CASE": 1, "TEST_FREQUENCY": "{:.17g}".format(frequency)},
            (1, 2, 3, 4),
        )
        if not states:
            continue
        check_finite(failures, label, states)
        strings = states["WG_STRING"]
        active = [tag for tag, state in strings.items() if value(state, "WG_STRING", "owner") == 1.0]
        if active != [wanted_string]:
            failures.append("{} chose strings {}, wanted {}".format(label, active, wanted_string))
        found = value(strings[wanted_string], "WG_STRING", "frequency")
        if not math.isclose(found, frequency, rel_tol=2.0e-12, abs_tol=2.0e-12):
            failures.append("{} stored {:.17g}".format(label, found))

    expect_failure(
        failures,
        "pitch below G",
        csound,
        module,
        csd,
        {"TEST_CASE": 2},
        "automatic pitch is below the open G string",
    )
    expect_failure(
        failures,
        "busy G fallback",
        csound,
        module,
        csd,
        {"TEST_CASE": 3},
        "all four strings are busy",
    )


def check_first_k_inputs(
    failures: List[str], csound: Path, module: Path, csd: Path,
) -> None:
    states = run_success(
        failures, "first-pass k-rate auto choice", csound, module, csd,
        {"TEST_CASE": 14}, (1, 2, 3, 4))
    if not states:
        return
    check_finite(failures, "first-pass k-rate auto choice", states)
    strings = states["WG_STRING"]
    active = [
        tag for tag in range(1, 5)
        if value(strings[tag], "WG_STRING", "owner") == 1.0
    ]
    if active != [3]:
        failures.append(
            "first-pass 440 Hz k assignment chose {}, wanted A".format(active))
    elif value(strings[3], "WG_STRING", "frequency") != 440.0:
        failures.append("first-pass k assignment lost its 440 Hz pitch")


def check_auto_continuity(
    failures: List[str], csound: Path, module: Path, csd: Path,
) -> None:
    held = run_success(
        failures, "D-string auto handoff", csound, module, csd,
        {"TEST_CASE": 4}, (1, 2, 3, 4))
    if held:
        check_finite(failures, "D-string auto handoff", held)
        strings = held["WG_STRING"]
        if value(strings[2], "WG_STRING", "frequency") != 445.0:
            failures.append("435 to 445 Hz did not stay on D")
        if value(strings[3], "WG_STRING", "frequency") != 0.0:
            failures.append("435 to 445 Hz also claimed A")
        if value(held["WG_BOW"][2], "WG_BOW", "attacks") != 1.0:
            failures.append("D-string auto handoff added a bow attack")

    left = run_success(
        failures, "E-string range exit", csound, module, csd,
        {"TEST_CASE": 5}, (1, 2, 3, 4))
    if left:
        check_finite(failures, "E-string range exit", left)
        strings = left["WG_STRING"]
        if value(strings[4], "WG_STRING", "frequency") != 700.0:
            failures.append("E-string range exit lost the old E state")
        if value(strings[4], "WG_STRING", "owner") != 0.0:
            failures.append("500 Hz remained on the unplayable E string")
        if value(strings[3], "WG_STRING", "frequency") != 500.0:
            failures.append("500 Hz did not move to the A string")
        if value(strings[3], "WG_STRING", "owner") != 1.0:
            failures.append("A string did not own 500 Hz")


def check_portamento(
    failures: List[str], csound: Path, module: Path, csd: Path,
) -> None:
    states = run_success(
        failures, "held portamento", csound, module, csd,
        {"TEST_CASE": 6}, (1,))
    if not states:
        return
    check_finite(failures, "held portamento", states)
    finger = states["WG_FINGER"][1]
    wave_state = states["WG_WAVE"][1]
    bow = states["WG_BOW"][1]
    for name, wanted in (("arrivals", 1.0), ("releases", 1.0), ("shifts", 0.0)):
        found = value(finger, "WG_FINGER", name)
        if found != wanted:
            failures.append("held portamento {} was {}, wanted {}".format(name, found, wanted))
    if abs(value(finger, "WG_FINGER", "target_position")) > 1.0e-12:
        failures.append("held portamento did not target the open string")
    if not 0.0 <= value(finger, "WG_FINGER", "position") <= 0.98:
        failures.append("held portamento finger position left its bounds")
    if abs(value(finger, "WG_FINGER", "delay_velocity")) > 0.25 + 1.0e-12:
        failures.append("held portamento exceeded the delay slew bound")
    if value(finger, "WG_FINGER", "movement_samples") <= 0.0:
        failures.append("held portamento recorded no finger movement")
    if value(finger, "WG_FINGER", "noise_samples") <= 0.0:
        failures.append("held portamento made no finger noise")
    if value(finger, "WG_FINGER", "noise_energy") <= 0.0:
        failures.append("held portamento stored no finger noise energy")
    peak = value(finger, "WG_FINGER", "noise_peak")
    if peak <= 0.0 or peak > 0.004 + 1.0e-12:
        failures.append("held portamento noise peak was {:.17g}".format(peak))
    checks = (
        ("bow attacks", value(bow, "WG_BOW", "attacks"), 1.0),
        ("wave attacks", value(wave_state, "WG_WAVE", "excitation_count"), 1.0),
        ("rail clears", value(wave_state, "WG_WAVE", "clear_count"), 0.0),
        ("rail resets", value(wave_state, "WG_WAVE", "reset_count"), 0.0),
    )
    for name, found, wanted in checks:
        if found != wanted:
            failures.append("held portamento {} was {}, wanted {}".format(name, found, wanted))


def check_finger_shift_block_invariance(
    failures: List[str], csound: Path, module: Path, csd: Path,
) -> None:
    fingers: Dict[int, State] = {}
    for ksmps in (8, 32):
        label = "smooth finger shift ksmps={}".format(ksmps)
        definitions = {
            "TEST_CASE": 16,
            "TEST_KSMPS": ksmps,
            "TEST_END": 0.41,
        }
        first = run_success(
            failures, label, csound, module, csd, definitions, (1,))
        second = run_success(
            failures, label + " repeat", csound, module, csd,
            definitions, (1,))
        if not first or not second:
            continue
        check_finite(failures, label, first)
        if first["WG_FINGER"][1] != second["WG_FINGER"][1]:
            failures.append(label + " changed finger state on repeat")
        finger = first["WG_FINGER"][1]
        fingers[ksmps] = finger
        for name, wanted in (
                ("arrivals", 0.0), ("releases", 0.0), ("shifts", 1.0)):
            found = value(finger, "WG_FINGER", name)
            if found != wanted:
                failures.append(
                    "{} {} was {}, wanted {}".format(
                        label, name, found, wanted))
        if value(finger, "WG_FINGER", "movement_samples") <= 0.0:
            failures.append(label + " recorded no finger movement")
        if value(finger, "WG_FINGER", "noise_samples") <= 0.0:
            failures.append(label + " recorded no finger noise")
        if value(finger, "WG_FINGER", "noise_energy") >= 1.0e-6:
            failures.append(label + " accumulated repeated shift noise")
        if value(finger, "WG_FINGER", "noise_energy") <= 1.0e-8:
            failures.append(label + " made no shift event burst")
        if value(finger, "WG_FINGER", "noise_peak") >= 2.5e-4:
            failures.append(label + " made an excessive shift-noise peak")
        if value(finger, "WG_FINGER", "noise_peak") <= 5.0e-5:
            failures.append(label + " made no shift event peak")

    if set(fingers) == {8, 32}:
        for name in ("noise_energy", "noise_peak", "movement_samples"):
            left = value(fingers[8], "WG_FINGER", name)
            right = value(fingers[32], "WG_FINGER", name)
            ratio = left / right if right != 0.0 else math.inf
            low, high = ((0.98, 1.02) if name == "movement_samples"
                         else (0.80, 1.25))
            if not low <= ratio <= high:
                failures.append(
                    "smooth finger shift {} ratio was {:.9g}".format(
                        name, ratio))

    arrival = run_success(
        failures, "smooth finger arrival", csound, module, csd,
        {"TEST_CASE": 17, "TEST_END": 0.41}, (1,))
    if arrival:
        check_finite(failures, "smooth finger arrival", arrival)
        finger = arrival["WG_FINGER"][1]
        for name, wanted in (
                ("arrivals", 1.0), ("releases", 0.0), ("shifts", 0.0)):
            found = value(finger, "WG_FINGER", name)
            if found != wanted:
                failures.append(
                    "smooth finger arrival {} was {}, wanted {}".format(
                        name, found, wanted))


def check_non_legato_rearm(
    failures: List[str], csound: Path, module: Path, csd: Path,
) -> None:
    states = run_success(
        failures, "exact non-legato rearm", csound, module, csd,
        {"TEST_CASE": 12}, (1,))
    if not states:
        return
    check_finite(failures, "exact non-legato rearm", states)
    bow = states["WG_BOW"][1]
    wave_state = states["WG_WAVE"][1]
    if value(bow, "WG_BOW", "attacks") != 2.0:
        failures.append("exact non-legato handoff did not rearm the bow")
    if value(wave_state, "WG_WAVE", "excitation_count") != 2.0:
        failures.append("exact non-legato handoff did not count two attacks")
    if value(wave_state, "WG_WAVE", "clear_count") != 0.0:
        failures.append("exact non-legato handoff cleared the rail")
    if value(wave_state, "WG_WAVE", "reset_count") != 0.0:
        failures.append("exact non-legato handoff reset the rail")


def check_clean_reattack(
    failures: List[str], csound: Path, module: Path, csd: Path,
) -> None:
    states = run_success(
        failures, "zero-block bow reattack", csound, module, csd,
        {"TEST_CASE": 13, "TEST_END": 0.245}, (1, 2, 3, 4))
    if not states:
        return
    check_finite(failures, "zero-block bow reattack", states)
    bows = states["WG_BOW"]
    waves = states["WG_WAVE"]
    if any(tag not in bows or tag not in waves for tag in (1, 2, 3, 4)):
        return

    contacts = [value(bows[tag], "WG_BOW", "contact")
                for tag in (1, 2, 3, 4)]
    bow_speeds = [value(bows[tag], "WG_BOW", "bow_speed")
                  for tag in (1, 2, 3, 4)]
    attacks = [value(bows[tag], "WG_BOW", "attacks")
               for tag in (1, 2, 3, 4)]
    if contacts[0] < 0.95:
        failures.append("bow was not settled before the reattack")
    if contacts[1] >= contacts[0]:
        failures.append("zero control block did not start lifting the bow")
    if contacts[3] < 0.95:
        failures.append("bow contact did not recover after the reattack")
    if min(abs(speed) for speed in bow_speeds) < 0.90 * abs(bow_speeds[0]):
        failures.append(
            "zero-block bow reattack wiped bow motion: {}".
            format(bow_speeds))
    if attacks != [1.0, 1.0, 2.0, 2.0]:
        failures.append(
            "zero-block bow attack counts were {}".format(attacks))

    wave_attacks = [value(waves[tag], "WG_WAVE", "excitation_count")
                    for tag in (1, 2, 3, 4)]
    if wave_attacks != [1.0, 1.0, 2.0, 2.0]:
        failures.append(
            "zero-block rail attack counts were {}".format(wave_attacks))
    for tag in (1, 2, 3, 4):
        if value(waves[tag], "WG_WAVE", "clear_count") != 0.0:
            failures.append("bow reattack cleared the rail at snapshot {}".
                            format(tag))
        if value(waves[tag], "WG_WAVE", "reset_count") != 0.0:
            failures.append("bow reattack reset the rail at snapshot {}".
                            format(tag))


def render_case(
    failures: List[str], label: str, csound: Path, module: Path, csd: Path,
    definitions: Mapping[str, object], output: Path,
) -> Tuple[bytes, Dict[str, Dict[int, State]]] | None:
    completed = run_csound(csound, module, csd, definitions, output=output)
    if completed.returncode != 0 or not output.exists():
        failures.append("{} render failed:\n{}".format(label, completed.stdout.rstrip()))
        return None
    states = {marker: read_states(completed.stdout, marker) for marker in FIELDS}
    if any(1 not in tagged for tagged in states.values()):
        failures.append("{} render printed incomplete state".format(label))
        return None
    with wave.open(str(output), "rb") as audio:
        if audio.getframerate() != 48000 or audio.getnchannels() != 2 or audio.getsampwidth() != 2:
            failures.append("{} render has the wrong WAV format".format(label))
            return None
        frames = audio.readframes(audio.getnframes())
    return frames, states


def check_exact_pair(
    failures: List[str], label: str, case: int, split_time: float,
    csound: Path, module: Path, csd: Path, folder: Path,
) -> Tuple[Dict[str, Dict[int, State]], Dict[str, Dict[int, State]]] | None:
    common = {"TEST_CASE": case, "TEST_END": 0.060}
    reference = render_case(
        failures, label + " reference", csound, module, csd, common,
        folder / (label.replace(" ", "-") + "-continuous.wav"))
    split_defs = dict(common)
    split_defs.update({"TEST_SPLIT": 1, "TEST_SPLIT_TIME": split_time})
    split = render_case(
        failures, label + " split", csound, module, csd, split_defs,
        folder / (label.replace(" ", "-") + "-split.wav"))
    if reference is None or split is None:
        return None
    reference_pcm, reference_states = reference
    split_pcm, split_states = split
    if reference_pcm != split_pcm:
        first = next(
            (index for index, pair in enumerate(zip(reference_pcm, split_pcm)) if pair[0] != pair[1]),
            min(len(reference_pcm), len(split_pcm)),
        )
        failures.append("{} PCM differs first at byte {}".format(label, first))
    for marker in FIELDS:
        reference_state = reference_states[marker][1]
        split_state = split_states[marker][1]
        same = reference_state == split_state
        if marker == "WG_STRING":
            same = all(
                math.isclose(left, right, rel_tol=2.0e-12, abs_tol=2.0e-12)
                for left, right in zip(reference_state, split_state)
            )
        if not same:
            failures.append("{} changed {} state".format(label, marker))
    check_finite(failures, label + " reference", reference_states)
    check_finite(failures, label + " split", split_states)
    return reference_states, split_states


def check_handoffs(
    failures: List[str], csound: Path, module: Path, csd: Path,
) -> None:
    with tempfile.TemporaryDirectory(prefix="hlolli-wg-legato-") as temporary:
        folder = Path(temporary)
        vibrato = check_exact_pair(
            failures, "vibrato handoff", 7, 0.016125,
            csound, module, csd, folder)
        if vibrato is not None:
            state = vibrato[1]["WG_FINGER"][1]
            effective = value(state, "WG_FINGER", "effective_frequency")
            if abs(effective - 445.0) < 0.1:
                failures.append("vibrato did not move effective frequency")
            phase = value(vibrato[1]["WG_STRING"][1], "WG_STRING", "vibrato_phase")
            if not 0.0 < phase < 1.0:
                failures.append("vibrato handoff lost its phase")

        check_exact_pair(
            failures, "unchanged mid-block handoff", 8, 0.016125,
            csound, module, csd, folder)
        check_exact_pair(
            failures, "pitch step block handoff", 9, 0.016,
            csound, module, csd, folder)
        check_exact_pair(
            failures, "first-pass tremolo block handoff", 15, 0.016,
            csound, module, csd, folder)
        check_exact_pair(
            failures, "first-pass tremolo mid-block handoff", 15, 0.016125,
            csound, module, csd, folder)


def check_multiple_strings(
    failures: List[str], csound: Path, module: Path, csd: Path,
) -> None:
    for case, wanted, label in (
        (10, (2, 3), "two-string double stop"),
        (11, (1, 2, 3, 4), "four-string stop"),
    ):
        states = run_success(
            failures, label, csound, module, csd,
            {"TEST_CASE": case}, (1, 2, 3, 4))
        if not states:
            continue
        check_finite(failures, label, states)
        active = tuple(
            tag for tag, state in states["WG_STRING"].items()
            if value(state, "WG_STRING", "owner") == 1.0)
        if active != wanted:
            failures.append("{} active strings were {}, wanted {}".format(label, active, wanted))
        frequencies = [
            value(states["WG_STRING"][tag], "WG_STRING", "frequency")
            for tag in wanted
        ]
        rng_states = [
            value(states["WG_FINGER"][tag], "WG_FINGER", "noise_state")
            for tag in wanted
        ]
        signatures = [(
            value(states["WG_WAVE"][tag], "WG_WAVE", "toward_nut_signature"),
            value(states["WG_WAVE"][tag], "WG_WAVE", "toward_bridge_signature"),
        ) for tag in wanted]
        if len(set(frequencies)) != len(wanted):
            failures.append("{} shared pitch state".format(label))
        if len(set(rng_states)) != len(wanted):
            failures.append("{} shared finger noise state".format(label))
        if len(set(signatures)) != len(wanted):
            failures.append("{} shared rail state".format(label))
        for tag in wanted:
            wave_state = states["WG_WAVE"][tag]
            if value(wave_state, "WG_WAVE", "excitation_count") != 1.0:
                failures.append("{} string {} had the wrong attack count".format(label, tag))
            if value(wave_state, "WG_WAVE", "clear_count") != 0.0:
                failures.append("{} string {} cleared its rail".format(label, tag))


def check_glide_reversal(
    failures: List[str], csound: Path, module: Path, csd: Path,
) -> None:
    states = run_success(
        failures, "glide reversal", csound, module, csd,
        {"TEST_CASE": 18, "TEST_KSMPS": 8}, (1, 2))
    waves = states.get("WG_WAVE", {})
    if 1 not in waves or 2 not in waves:
        return
    before, after = (value(waves[tag], "WG_WAVE", "read_delay")
                     for tag in (1, 2))
    if abs(after - before) > 8 * 0.25 + 1e-10:
        failures.append(f"glide reversal moved {after - before:.6g} samples in one block")


def check_bridge_arrival(
    failures: List[str], csound: Path, module: Path, csd: Path,
) -> None:
    with tempfile.TemporaryDirectory(prefix="violin-bridge-arrival-") as folder:
        path = Path(folder) / "pluck.wav"
        completed = run_csound(csound, module, csd, {"TEST_CASE": 19}, path)
        if completed.returncode != 0:
            failures.append(completed.stdout)
            return
        with wave.open(str(path), "rb") as stream:
            frames = struct.iter_unpack("<hh", stream.readframes(stream.getnframes()))
            onset = next((i for i, frame in enumerate(frames)
                          if max(map(abs, frame)) > 1), None)
    if onset is None or not 45 <= onset <= 57:
        failures.append(f"bridge pluck arrived at sample {onset}, expected about 49")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--csound", required=True, type=Path)
    parser.add_argument("--module", required=True, type=Path)
    parser.add_argument("--csd", required=True, type=Path)
    arguments = parser.parse_args()
    failures: List[str] = []

    check_auto_choice(failures, arguments.csound, arguments.module, arguments.csd)
    check_first_k_inputs(
        failures, arguments.csound, arguments.module, arguments.csd)
    check_auto_continuity(failures, arguments.csound, arguments.module, arguments.csd)
    check_portamento(failures, arguments.csound, arguments.module, arguments.csd)
    check_glide_reversal(failures, arguments.csound, arguments.module, arguments.csd)
    check_bridge_arrival(failures, arguments.csound, arguments.module, arguments.csd)
    check_finger_shift_block_invariance(
        failures, arguments.csound, arguments.module, arguments.csd)
    check_non_legato_rearm(failures, arguments.csound, arguments.module, arguments.csd)
    check_clean_reattack(failures, arguments.csound, arguments.module, arguments.csd)
    check_handoffs(failures, arguments.csound, arguments.module, arguments.csd)
    check_multiple_strings(failures, arguments.csound, arguments.module, arguments.csd)

    if failures:
        for failure in failures:
            print("FAIL: {}".format(failure), file=sys.stderr)
        return 1
    print("legato, string choice, and double-stop checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
