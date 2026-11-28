#!/usr/bin/env python3
"""Check the bridge send, modal body, wet controls, and persistent tail."""

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
ModeKey = Tuple[int, int]

SAMPLE_RATE = 48000
MODE_COUNT = 17
OUTPUT_LIMIT = 4.0

BODY_FIELDS = (
    "body", "sympathetic", "mute", "mode_count",
    "send_samples_1", "send_samples_2", "send_samples_3", "send_samples_4",
    "send_energy_1", "send_energy_2", "send_energy_3", "send_energy_4",
    "last_drive", "drive_energy", "modal_energy", "state_signature",
    "last_left", "last_right", "output_energy_left", "output_energy_right",
    "peak_left", "peak_right", "processed_samples", "fast_forward_samples",
    "reset_count", "clip_count", "finite",
)
BODY_FIELD = {name: index for index, name in enumerate(BODY_FIELDS)}

MODE_FIELDS = (
    "frequency", "base_bandwidth", "effective_bandwidth", "radius", "gain",
    "pan", "real", "imaginary", "finite",
)
MODE_FIELD = {name: index for index, name in enumerate(MODE_FIELDS)}

WAVE_FIELDS = (
    "capacity", "read_delay", "target_delay", "target_frequency",
    "loop_phase_samples", "toward_nut_energy", "toward_bridge_energy",
    "toward_nut_signature", "toward_bridge_signature", "nut_pole",
    "nut_gain", "nut_state", "bridge_pole", "bridge_gain", "bridge_state",
    "write_index", "wave_samples", "excitation_count", "clear_count",
    "reset_count", "clip_count", "bridge_dynamic_input",
    "bridge_dynamic_output", "last_bridge_output", "finite",
)

MODE_SPECS = (
    (265.0, 15.0, 0.6310, 0.00),
    (395.0, 25.0, 0.2818, -0.10),
    (430.0, 20.0, 0.3981, 0.08),
    (550.0, 30.0, 0.7079, -0.16),
    (665.0, 30.0, 1.0000, 0.16),
    (810.0, 42.0, 0.5200, -0.22),
    (878.0, 16.0, 0.14, -0.22),
    (1033.0, 64.0, 0.4000, 0.22),
    (1078.658949, 27.420699, 0.177452, 0.18),
    (1096.887273, 4.915355, 0.051527, -0.12),
    (1320.0, 120.0, 0.3400, -0.26),
    (1710.0, 180.0, 0.3100, 0.26),
    (1968.33208694, 14.18034666, 0.16857919, -0.14),
    (1985.26973931, 8.37242926, 0.68557468, 0.20),
    (2320.0, 318.0, 1.1625, -0.30),
    (3300.0, 240.0, 1.08, 0.30),
    (4010.0, 760.0, 0.1800, -0.24),
)


def run_csound(
    csound: Path,
    module: Path,
    csd: Path,
    definitions: Mapping[str, object],
    output: Path | None = None,
    timeout: int = 30,
) -> subprocess.CompletedProcess[str]:
    audio_options = ["-n"] if output is None else [
        "-W", "-s", "-o", str(output)]
    command = [
        str(csound),
        "--opcode-lib={}".format(module),
        "--sample-accurate",
        "--num-threads=1",
        *[
            "--omacro:{}={}".format(name, value)
            for name, value in definitions.items()
        ],
        *audio_options,
        "-d",
        "-m128",
        str(csd),
    ]
    return subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        timeout=timeout,
        check=False,
    )


def read_tagged_states(
    output: str, marker: str, field_count: int,
) -> Dict[int, State]:
    states: Dict[int, State] = {}
    prefix = marker + " "
    for line in output.splitlines():
        start = line.find(prefix)
        if start < 0:
            continue
        words = line[start:].split()
        if len(words) < field_count + 2:
            continue
        tag = int(float(words[1]))
        states[tag] = tuple(
            float(item) for item in words[2:2 + field_count])
    return states


def read_body_states(output: str) -> Dict[int, State]:
    first = read_tagged_states(output, "WG_BODY_A", 14)
    second = read_tagged_states(output, "WG_BODY_B", 13)
    return {
        tag: first[tag] + second[tag]
        for tag in first.keys() & second.keys()
    }


def read_modes(output: str) -> Dict[ModeKey, State]:
    modes: Dict[ModeKey, State] = {}
    prefix = "WG_BODY_MODE "
    for line in output.splitlines():
        start = line.find(prefix)
        if start < 0:
            continue
        words = line[start:].split()
        if len(words) < len(MODE_FIELDS) + 3:
            continue
        tag = int(float(words[1]))
        mode = int(float(words[2]))
        modes[(tag, mode)] = tuple(
            float(item) for item in words[3:3 + len(MODE_FIELDS)])
    return modes


def read_results(output: str, marker: str) -> Dict[int, float]:
    return {
        tag: values[0]
        for tag, values in read_tagged_states(output, marker, 1).items()
    }


def read_wav(path: Path) -> Tuple[Tuple[List[float], List[float]], bytes]:
    with wave.open(str(path), "rb") as audio:
        if (audio.getframerate() != SAMPLE_RATE or
                audio.getnchannels() != 2 or audio.getsampwidth() != 2):
            raise ValueError("unexpected body-test WAV format")
        frames = audio.readframes(audio.getnframes())
    pairs = list(struct.iter_unpack("<hh", frames))
    left = [pair[0] / 32768.0 for pair in pairs]
    right = [pair[1] / 32768.0 for pair in pairs]
    return (left, right), frames


def run_case(
    failures: List[str],
    label: str,
    csound: Path,
    module: Path,
    csd: Path,
    definitions: Mapping[str, object],
    body_tags: Sequence[int],
    mode_keys: Sequence[ModeKey] = (),
    timeout: int = 30,
    output: Path | None = None,
) -> Tuple[Dict[int, State], Dict[ModeKey, State], Dict[int, float],
           Tuple[Tuple[List[float], List[float]], bytes] | None]:
    completed = run_csound(
        csound, module, csd, definitions, output=output, timeout=timeout)
    if completed.returncode != 0:
        failures.append(
            "{} failed with status {}:\n{}".format(
                label, completed.returncode, completed.stdout.rstrip()))
        return {}, {}, {}, None
    body = read_body_states(completed.stdout)
    modes = read_modes(completed.stdout)
    faults = read_results(completed.stdout, "WG_BODY_FAULT")
    missing_body = [tag for tag in body_tags if tag not in body]
    missing_modes = [key for key in mode_keys if key not in modes]
    if missing_body or missing_modes:
        failures.append(
            "{} missed body tags {} or modes {}:\n{}".format(
                label, missing_body, missing_modes,
                completed.stdout.rstrip()))
    rendered = None
    if output is not None:
        if not output.exists():
            failures.append("{} produced no WAV".format(label))
        else:
            try:
                rendered = read_wav(output)
            except (ValueError, wave.Error) as error:
                failures.append("{}: {}".format(label, error))
    return body, modes, faults, rendered


def close(left: float, right: float, tolerance: float = 2.0e-12) -> bool:
    return math.isclose(left, right, rel_tol=tolerance, abs_tol=tolerance)


def body_value(state: State, name: str) -> float:
    return state[BODY_FIELD[name]]


def mode_value(state: State, name: str) -> float:
    return state[MODE_FIELD[name]]


def rms(samples: Sequence[float]) -> float:
    if not samples:
        return 0.0
    return math.sqrt(sum(item * item for item in samples) / len(samples))


def check_body_common(
    failures: List[str], label: str, state: State,
) -> bool:
    if len(state) != len(BODY_FIELDS):
        failures.append("{} returned the wrong body state size".format(label))
        return False
    if not all(math.isfinite(item) for item in state):
        failures.append("{} returned a non-finite body value".format(label))
        return False
    if body_value(state, "finite") != 1.0:
        failures.append("{} reported invalid body state".format(label))
    if body_value(state, "mode_count") != MODE_COUNT:
        failures.append("{} returned the wrong mode count".format(label))
    for name in (
        "send_samples_1", "send_samples_2", "send_samples_3",
        "send_samples_4", "send_energy_1", "send_energy_2",
        "send_energy_3", "send_energy_4", "drive_energy", "modal_energy",
        "output_energy_left", "output_energy_right", "peak_left",
        "peak_right", "processed_samples", "fast_forward_samples",
        "reset_count", "clip_count",
    ):
        if body_value(state, name) < 0.0:
            failures.append("{} returned negative {}".format(label, name))
    if (body_value(state, "peak_left") > OUTPUT_LIMIT + 1.0e-12 or
            body_value(state, "peak_right") > OUTPUT_LIMIT + 1.0e-12):
        failures.append("{} exceeded the wet-output bound".format(label))
    return True


def check_mode_common(
    failures: List[str], label: str, state: State,
) -> bool:
    if len(state) != len(MODE_FIELDS):
        failures.append("{} returned the wrong mode state size".format(label))
        return False
    if not all(math.isfinite(item) for item in state):
        failures.append("{} returned a non-finite mode value".format(label))
        return False
    if mode_value(state, "finite") != 1.0:
        failures.append("{} reported an invalid mode".format(label))
    if not 0.0 <= mode_value(state, "radius") < 1.0:
        failures.append("{} returned an unstable radius".format(label))
    if mode_value(state, "effective_bandwidth") <= 0.0:
        failures.append("{} returned no mode bandwidth".format(label))
    if mode_value(state, "gain") < 0.0:
        failures.append("{} returned negative mode gain".format(label))
    if not -1.0 <= mode_value(state, "pan") <= 1.0:
        failures.append("{} returned invalid pan".format(label))
    return True


def compare_states(
    failures: List[str], label: str, fields: Sequence[str],
    reference: State, actual: State, skip: Sequence[str] = (),
) -> None:
    skipped = set(skip)
    for name, wanted, found in zip(fields, reference, actual):
        if name not in skipped and not close(wanted, found):
            failures.append(
                "{} changed {}: {:.17g} != {:.17g}".format(
                    label, name, found, wanted))


def check_silence_and_table(
    failures: List[str], csound: Path, module: Path, csd: Path,
) -> None:
    keys = tuple((1, mode) for mode in range(1, MODE_COUNT + 1))
    body, modes, _, _ = run_case(
        failures, "silent body", csound, module, csd,
        {"TEST_CASE": 1, "TEST_END": 0.083}, (1,), keys)
    if 1 not in body or any(key not in modes for key in keys):
        return
    state = body[1]
    check_body_common(failures, "silent body", state)
    if body_value(state, "processed_samples") != 3776.0:
        failures.append("silent body processed the wrong sample count")
    for name in (
        "send_samples_1", "send_samples_2", "send_samples_3",
        "send_samples_4", "send_energy_1", "send_energy_2",
        "send_energy_3", "send_energy_4", "drive_energy", "modal_energy",
        "last_left", "last_right", "output_energy_left",
        "output_energy_right", "peak_left", "peak_right",
        "fast_forward_samples", "reset_count", "clip_count",
    ):
        if body_value(state, name) != 0.0:
            failures.append("silent body had nonzero {}".format(name))

    decay_scale = 1.00 - 0.10 * 0.72
    for mode_index, spec in enumerate(MODE_SPECS, 1):
        mode = modes[(1, mode_index)]
        label = "body mode {}".format(mode_index)
        check_mode_common(failures, label, mode)
        frequency, bandwidth, _, pan = spec
        expected_bandwidth = bandwidth * decay_scale
        expected_radius = math.exp(
            -math.pi * expected_bandwidth / SAMPLE_RATE)
        checks = (
            ("frequency", mode_value(mode, "frequency"), frequency),
            ("base bandwidth", mode_value(mode, "base_bandwidth"), bandwidth),
            ("effective bandwidth", mode_value(mode, "effective_bandwidth"),
             expected_bandwidth),
            ("radius", mode_value(mode, "radius"), expected_radius),
            ("pan", mode_value(mode, "pan"), pan),
            ("real state", mode_value(mode, "real"), 0.0),
            ("imaginary state", mode_value(mode, "imaginary"), 0.0),
        )
        for name, found, wanted in checks:
            if not close(found, wanted, 2.0e-11):
                failures.append(
                    "{} {} was {:.17g}, wanted {:.17g}".format(
                        label, name, found, wanted))


def check_impulse_and_stereo(
    failures: List[str], csound: Path, module: Path, csd: Path,
) -> None:
    with tempfile.TemporaryDirectory(prefix="hlolli-body-impulse-") as folder:
        temporary = Path(folder)
        rendered_runs = {}
        state_runs = {}
        for lane in (1, 4):
            body, _, _, rendered = run_case(
                failures, "string {} bridge impulse".format(lane),
                csound, module, csd,
                {"TEST_CASE": 2, "TEST_VARIANT": lane, "TEST_END": 0.51},
                (1, 2, 3), output=temporary / "lane{}.wav".format(lane))
            if any(tag not in body for tag in (1, 2, 3)) or rendered is None:
                continue
            state_runs[lane] = body
            rendered_runs[lane] = rendered
            for tag in (1, 2, 3):
                check_body_common(
                    failures, "lane {} snapshot {}".format(lane, tag),
                    body[tag])
            early, middle, late = body[1], body[2], body[3]
            samples = [body_value(early, "send_samples_{}".format(i))
                       for i in range(1, 5)]
            energies = [body_value(early, "send_energy_{}".format(i))
                        for i in range(1, 5)]
            wanted_samples = [0.0] * 4
            wanted_energies = [0.0] * 4
            wanted_samples[lane - 1] = 1.0
            wanted_energies[lane - 1] = 16.0
            if samples != wanted_samples or energies != wanted_energies:
                failures.append(
                    "lane {} impulse entered the wrong send: {} {}".format(
                        lane, samples, energies))
            if not close(body_value(early, "drive_energy"), 1.0):
                failures.append("lane {} had wrong aggregate drive".format(lane))
            modal = [body_value(item, "modal_energy")
                     for item in (early, middle, late)]
            if modal[0] <= 0.0 or not (modal[2] < modal[1] < modal[0]):
                failures.append(
                    "lane {} modal tail did not decay: {}".format(lane, modal))
            if (body_value(late, "output_energy_left") <= 0.0 or
                    body_value(late, "output_energy_right") <= 0.0):
                failures.append("lane {} produced no stereo wet output".format(lane))
            left, right = rendered[0]
            first_block_end = int(0.25 * SAMPLE_RATE)
            if any(left[:first_block_end]) or any(right[:first_block_end]):
                failures.append("lane {} wet output arrived before its send".format(lane))
            window = slice(first_block_end, int(0.40 * SAMPLE_RATE))
            if rms(left[window]) <= 1.0e-7 or rms(right[window]) <= 1.0e-7:
                failures.append("lane {} impulse was inaudible".format(lane))
            if left[window] == right[window]:
                failures.append("lane {} wet output was mono".format(lane))
        if 1 in rendered_runs and 4 in rendered_runs:
            if rendered_runs[1][1] == rendered_runs[4][1]:
                failures.append("G and E bridge lanes produced identical wet audio")
            ratios = []
            for lane in (1, 4):
                state = state_runs[lane][3]
                ratios.append(
                    body_value(state, "output_energy_left") /
                    max(1.0e-30, body_value(state, "output_energy_right")))
            if close(ratios[0], ratios[1], 1.0e-8):
                failures.append("bridge lane identity did not change stereo energy")


def check_controls(
    failures: List[str], csound: Path, module: Path, csd: Path,
) -> None:
    settings = {
        "body_low": {"TEST_BODY": 0.0, "TEST_MUTE": 0.0,
                     "TEST_SYMPATHETIC": 0.55},
        "body_high": {"TEST_BODY": 1.0, "TEST_MUTE": 0.0,
                      "TEST_SYMPATHETIC": 0.55},
        "mute_low": {"TEST_BODY": 0.72, "TEST_MUTE": 0.0,
                     "TEST_SYMPATHETIC": 0.55},
        "mute_high": {"TEST_BODY": 0.72, "TEST_MUTE": 1.0,
                      "TEST_SYMPATHETIC": 0.55},
        "sympathetic_off": {"TEST_BODY": 0.72, "TEST_MUTE": 0.0,
                            "TEST_SYMPATHETIC": 0.0},
        "sympathetic_on": {"TEST_BODY": 0.72, "TEST_MUTE": 0.0,
                           "TEST_SYMPATHETIC": 1.0},
    }
    states = {}
    modes = {}
    frames = {}
    highest_mode = (1, MODE_COUNT)
    with tempfile.TemporaryDirectory(prefix="hlolli-body-controls-") as folder:
        temporary = Path(folder)
        for label, controls in settings.items():
            definitions = {"TEST_CASE": 2, "TEST_VARIANT": 2,
                           "TEST_END": 0.51, **controls}
            body, run_modes, _, rendered = run_case(
                failures, label, csound, module, csd, definitions,
                (1, 2, 3), (highest_mode,),
                output=temporary / "{}.wav".format(label))
            if 3 not in body or highest_mode not in run_modes or rendered is None:
                continue
            check_body_common(failures, label, body[3])
            check_mode_common(failures, f"{label} mode {MODE_COUNT}", run_modes[highest_mode])
            states[label] = body[3]
            modes[label] = run_modes[highest_mode]
            frames[label] = rendered[1]

    if "body_low" in states and "body_high" in states:
        low_energy = body_value(states["body_low"], "output_energy_left") + \
            body_value(states["body_low"], "output_energy_right")
        high_energy = body_value(states["body_high"], "output_energy_left") + \
            body_value(states["body_high"], "output_energy_right")
        if high_energy <= 10.0 * max(1.0e-30, low_energy):
            failures.append("kBody did not raise wet output level")
        if mode_value(modes["body_high"], "radius") <= \
                mode_value(modes["body_low"], "radius"):
            failures.append("kBody did not lengthen modal decay")
        if mode_value(modes["body_high"], "gain") <= \
                mode_value(modes["body_low"], "gain"):
            failures.append("kBody did not brighten the upper modes")
        if frames["body_low"].strip(b"\x00"):
            failures.append("kBody=0 did not hard-mute wet audio")
        if body_value(states["body_low"], "modal_energy") <= 0.0:
            failures.append("kBody=0 stopped modal state instead of wet output")

    if "mute_low" in states and "mute_high" in states:
        open_energy = body_value(states["mute_low"], "output_energy_left") + \
            body_value(states["mute_low"], "output_energy_right")
        muted_energy = body_value(states["mute_high"], "output_energy_left") + \
            body_value(states["mute_high"], "output_energy_right")
        if muted_energy >= 0.75 * open_energy:
            failures.append("kMute did not lower wet output")
        if mode_value(modes["mute_high"], "radius") >= \
                mode_value(modes["mute_low"], "radius"):
            failures.append("kMute did not shorten modal decay")
        if mode_value(modes["mute_high"], "gain") >= \
                mode_value(modes["mute_low"], "gain"):
            failures.append("kMute did not darken the upper modes")

    if "sympathetic_off" in states and "sympathetic_on" in states:
        if frames["sympathetic_off"] == frames["sympathetic_on"]:
            failures.append("kSympathetic did not change open-string wet audio")
        if states["sympathetic_off"] == states["sympathetic_on"]:
            failures.append("kSympathetic did not change body state")
        if modes["sympathetic_off"] == modes["sympathetic_on"]:
            failures.append("kSympathetic did not reach the body modes")


def check_handoff(
    failures: List[str], csound: Path, module: Path, csd: Path,
) -> None:
    mode_keys = tuple((1, mode) for mode in range(1, MODE_COUNT + 1))
    common = {"TEST_CASE": 3, "TEST_END": 0.51}
    with tempfile.TemporaryDirectory(prefix="hlolli-body-handoff-") as folder:
        temporary = Path(folder)
        body, modes, _, rendered = run_case(
            failures, "continuous wet renderer", csound, module, csd,
            common, (1,), mode_keys, output=temporary / "continuous.wav")
        if 1 not in body or any(key not in modes for key in mode_keys) or \
                rendered is None:
            return
        reference_state = body[1]
        reference_modes = modes
        reference_frames = rendered[1]
        for name, split_time in (("block", 0.25), ("mid-block", 0.250125)):
            definitions = dict(common)
            definitions.update({"TEST_SPLIT": 1,
                                "TEST_SPLIT_TIME": split_time})
            split_body, split_modes, _, split_rendered = run_case(
                failures, "{} wet handoff".format(name), csound, module, csd,
                definitions, (1,), mode_keys,
                output=temporary / "{}.wav".format(name))
            if 1 not in split_body or any(
                    key not in split_modes for key in mode_keys) or \
                    split_rendered is None:
                continue
            compare_states(
                failures, "{} wet handoff".format(name), BODY_FIELDS,
                reference_state, split_body[1])
            for key in mode_keys:
                compare_states(
                    failures, "{} wet handoff mode {}".format(name, key[1]),
                    MODE_FIELDS, reference_modes[key], split_modes[key])
            if split_rendered[1] != reference_frames:
                failures.append("{} wet handoff changed rendered samples".format(name))


def check_gaps(
    failures: List[str], csound: Path, module: Path, csd: Path,
) -> None:
    mode_keys = tuple((1, mode) for mode in range(1, MODE_COUNT + 1))
    common = {"TEST_CASE": 4, "TEST_END": 0.555}
    with tempfile.TemporaryDirectory(prefix="hlolli-body-gap-") as folder:
        temporary = Path(folder)
        reference_body, reference_modes, _, reference_rendered = run_case(
            failures, "continuous body tail", csound, module, csd,
            common, (1,), mode_keys, output=temporary / "continuous.wav")
        gap_definitions = dict(common)
        gap_definitions["TEST_GAP"] = 1
        gap_body, gap_modes, _, gap_rendered = run_case(
            failures, "renderer gap", csound, module, csd,
            gap_definitions, (1,), mode_keys, output=temporary / "gap.wav")
        if (1 in reference_body and 1 in gap_body and
                all(key in reference_modes and key in gap_modes
                    for key in mode_keys)):
            compare_states(
                failures, "short renderer gap", BODY_FIELDS,
                reference_body[1], gap_body[1],
                skip=("output_energy_left", "output_energy_right",
                      "fast_forward_samples"))
            for key in mode_keys:
                compare_states(
                    failures, "short renderer gap mode {}".format(key[1]),
                    MODE_FIELDS, reference_modes[key], gap_modes[key])
            if body_value(gap_body[1], "processed_samples") != 24000.0:
                failures.append("short renderer gap lost body time")
            if body_value(gap_body[1], "fast_forward_samples") != 768.0:
                failures.append("short renderer gap used the wrong skip")
        if reference_rendered is not None and gap_rendered is not None:
            reference_channels = reference_rendered[0]
            gap_channels = gap_rendered[0]
            before = slice(0, int(0.25 * SAMPLE_RATE))
            after = slice(int(0.266 * SAMPLE_RATE), int(0.50 * SAMPLE_RATE))
            for channel, (wanted, found) in enumerate(
                    zip(reference_channels, gap_channels), 1):
                if wanted[before] != found[before] or wanted[after] != found[after]:
                    failures.append(
                        "renderer gap changed active channel {} samples".format(
                            channel))
            middle = slice(int(0.25 * SAMPLE_RATE), int(0.266 * SAMPLE_RATE))
            if any(sample != 0.0 for channel in gap_channels
                   for sample in channel[middle]):
                failures.append("renderer gap emitted wet audio while unowned")

    long_body, long_modes, _, _ = run_case(
        failures, "long renderer gap", csound, module, csd,
        {"TEST_CASE": 4, "TEST_GAP": 2, "TEST_END": 0.555},
        (1,), mode_keys)
    if 1 in long_body:
        state = long_body[1]
        check_body_common(failures, "long renderer gap", state)
        if body_value(state, "processed_samples") != 26432.0:
            failures.append("long renderer gap lost body time")
        if body_value(state, "fast_forward_samples") != 12000.0:
            failures.append("long renderer gap used the wrong closed-form skip")
        for key in mode_keys:
            if key in long_modes:
                check_mode_common(
                    failures, "long-gap mode {}".format(key[1]),
                    long_modes[key])


def check_lanes_and_isolation(
    failures: List[str], csound: Path, module: Path, csd: Path,
) -> None:
    body, _, _, _ = run_case(
        failures, "four bridge lanes", csound, module, csd,
        {"TEST_CASE": 5, "TEST_VARIANT": 0, "TEST_END": 0.425}, (1,))
    if 1 in body:
        state = body[1]
        check_body_common(failures, "four bridge lanes", state)
        samples = [body_value(state, "send_samples_{}".format(i))
                   for i in range(1, 5)]
        energies = [body_value(state, "send_energy_{}".format(i))
                    for i in range(1, 5)]
        if samples != [1.0, 1.0, 1.0, 1.0]:
            failures.append("four-lane test lost a bridge send: {}".format(samples))
        if energies != [1.0, 4.0, 9.0, 16.0]:
            failures.append("four-lane test mixed lane energy: {}".format(energies))
        if body_value(state, "drive_energy") <= 0.0:
            failures.append("four bridge lanes did not drive the body")

    mode_keys = tuple((2, mode) for mode in range(1, MODE_COUNT + 1))
    isolated, modes, _, _ = run_case(
        failures, "two-handle body isolation", csound, module, csd,
        {"TEST_CASE": 8, "TEST_END": 0.425}, (1, 2), mode_keys)
    if 1 not in isolated or 2 not in isolated:
        return
    active = isolated[1]
    silent = isolated[2]
    check_body_common(failures, "active violin body", active)
    check_body_common(failures, "silent violin body", silent)
    if body_value(active, "drive_energy") <= 0.0:
        failures.append("excited violin had no body drive")
    for name in (
        "send_samples_1", "send_samples_2", "send_samples_3",
        "send_samples_4", "send_energy_1", "send_energy_2",
        "send_energy_3", "send_energy_4", "drive_energy", "modal_energy",
        "output_energy_left", "output_energy_right", "peak_left", "peak_right",
        "reset_count", "clip_count",
    ):
        if body_value(silent, name) != 0.0:
            failures.append("silent violin shared {}".format(name))
    for key in mode_keys:
        if key not in modes:
            continue
        mode = modes[key]
        check_mode_common(failures, "silent violin mode {}".format(key[1]), mode)
        if mode_value(mode, "real") != 0.0 or \
                mode_value(mode, "imaginary") != 0.0:
                failures.append("silent violin mode {} received state".format(key[1]))


def check_released_string_drive(
    failures: List[str], csound: Path, module: Path, csd: Path,
) -> None:
    body, _, _, _ = run_case(
        failures, "released string body drive", csound, module, csd,
        {"TEST_CASE": 9, "TEST_END": 0.505}, (1, 2, 3))
    if any(tag not in body for tag in (1, 2, 3)):
        return
    for tag in (1, 2, 3):
        check_body_common(
            failures, "released string snapshot {}".format(tag), body[tag])
    drive = [body_value(body[tag], "drive_energy") for tag in (1, 2, 3)]
    sends = [body_value(body[tag], "send_energy_3") for tag in (1, 2, 3)]
    if not (drive[2] > drive[1] > drive[0] > 0.0):
        failures.append(
            "released string stopped fresh body drive: {}".format(drive))
    if not (sends[2] > sends[1] > sends[0] > 0.0):
        failures.append(
            "released string stopped bridge sends: {}".format(sends))


def check_fault_recovery(
    failures: List[str], csound: Path, module: Path, csd: Path,
) -> None:
    mode_keys = tuple((1, mode) for mode in range(1, MODE_COUNT + 1))
    waves: Dict[int, State] = {}
    with tempfile.TemporaryDirectory(prefix="hlolli-body-fault-") as folder:
        output = Path(folder) / "recovery.wav"
        completed = run_csound(
            csound, module, csd, {"TEST_CASE": 6, "TEST_END": 0.61},
            output=output)
        if completed.returncode != 0:
            failures.append(
                "body fault recovery failed with status {}:\n{}".format(
                    completed.returncode, completed.stdout.rstrip()))
            return
        body = read_body_states(completed.stdout)
        modes = read_modes(completed.stdout)
        faults = read_results(completed.stdout, "WG_BODY_FAULT")
        waves = read_tagged_states(
            completed.stdout, "WG_BODY_WAVE", len(WAVE_FIELDS))
        try:
            rendered = read_wav(output)
        except (ValueError, wave.Error) as error:
            failures.append("body fault recovery: {}".format(error))
            rendered = None
    if any(tag not in body for tag in (1, 2, 3)):
        return
    for tag in (1, 2, 3):
        check_body_common(failures, "fault snapshot {}".format(tag), body[tag])
    if faults.get(1) != 1.0:
        failures.append("body fault injection did not run")
    if body_value(body[1], "reset_count") != 0.0:
        failures.append("body reset before fault injection")
    if (body_value(body[2], "reset_count") != 1.0 or
            body_value(body[3], "reset_count") != 1.0):
        failures.append("body fault did not cause one bounded reset")
    if body_value(body[3], "send_samples_2") != 2.0 or \
            body_value(body[3], "send_energy_2") != 32.0:
        failures.append("body did not accept a fresh send after recovery")
    if body_value(body[3], "output_energy_left") <= \
            body_value(body[2], "output_energy_left"):
        failures.append("body did not produce output after recovery")
    if 1 not in waves or 2 not in waves:
        failures.append("body fault recovery missed passive rail snapshots")
    else:
        compare_states(
            failures, "body fault passive rail", WAVE_FIELDS,
            waves[1], waves[2])
    for key in mode_keys:
        if key in modes:
            check_mode_common(
                failures, "recovered mode {}".format(key[1]), modes[key])
    if rendered is not None:
        left, right = rendered[0]
        window = slice(int(0.301 * SAMPLE_RATE), int(0.42 * SAMPLE_RATE))
        if rms(left[window]) <= 1.0e-7 or rms(right[window]) <= 1.0e-7:
            failures.append("body recovery left the wet output silent")


def check_stress(
    failures: List[str], csound: Path, module: Path, csd: Path,
) -> None:
    mode_keys = tuple((1, mode) for mode in range(1, MODE_COUNT + 1))
    with tempfile.TemporaryDirectory(prefix="hlolli-body-stress-") as folder:
        body, modes, _, rendered = run_case(
            failures, "body stress", csound, module, csd,
            {"TEST_CASE": 7, "TEST_END": 10.005}, (1,), mode_keys,
            timeout=60, output=Path(folder) / "stress.wav")
    if 1 not in body:
        return
    state = body[1]
    check_body_common(failures, "body stress", state)
    if body_value(state, "processed_samples") != 480000.0:
        failures.append("body stress processed the wrong sample count")
    for index in range(1, 5):
        if body_value(state, "send_samples_{}".format(index)) != 480000.0:
            failures.append("stress string {} lost send samples".format(index))
        if body_value(state, "send_energy_{}".format(index)) <= 0.0:
            failures.append("stress string {} produced no bridge energy".format(index))
    if body_value(state, "drive_energy") <= 0.0:
        failures.append("body stress had no shared drive")
    if body_value(state, "reset_count") != 0.0:
        failures.append("body stress used finite recovery")
    if body_value(state, "clip_count") != 0.0:
        failures.append("body stress reached the wet safety clamp")
    for key in mode_keys:
        if key in modes:
            check_mode_common(failures, "stress mode {}".format(key[1]), modes[key])
    if rendered is not None:
        left, right = rendered[0]
        if rms(left) <= 1.0e-6 or rms(right) <= 1.0e-6:
            failures.append("body stress produced no audible wet signal")
        if left == right:
            failures.append("body stress wet signal was mono")
        if max((abs(item) for item in left + right), default=0.0) >= 1.0:
            failures.append("body stress clipped the PCM output")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csound", required=True, type=Path)
    parser.add_argument("--module", required=True, type=Path)
    parser.add_argument("--csd", required=True, type=Path)
    arguments = parser.parse_args()

    failures: List[str] = []
    try:
        check_silence_and_table(
            failures, arguments.csound, arguments.module, arguments.csd)
        check_impulse_and_stereo(
            failures, arguments.csound, arguments.module, arguments.csd)
        check_controls(
            failures, arguments.csound, arguments.module, arguments.csd)
        check_handoff(
            failures, arguments.csound, arguments.module, arguments.csd)
        check_gaps(
            failures, arguments.csound, arguments.module, arguments.csd)
        check_lanes_and_isolation(
            failures, arguments.csound, arguments.module, arguments.csd)
        check_released_string_drive(
            failures, arguments.csound, arguments.module, arguments.csd)
        check_fault_recovery(
            failures, arguments.csound, arguments.module, arguments.csd)
        check_stress(
            failures, arguments.csound, arguments.module, arguments.csd)
    except (OSError, subprocess.TimeoutExpired, ValueError, wave.Error) as error:
        print("body test failed: {}".format(error), file=sys.stderr)
        return 2

    if failures:
        for failure in failures:
            print("failure: {}".format(failure), file=sys.stderr)
        return 1
    print("violin bridge and body checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
