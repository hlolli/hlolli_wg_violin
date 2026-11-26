#!/usr/bin/env python3
"""Check the static bow junction, controls, handoff, and bounded recovery."""

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

SAMPLE_RATE = 48000.0
WAVE_LIMIT = 4.0
DRY_LIMIT = 0.12 * WAVE_LIMIT

BOW_FIELDS = (
    "state", "requested_force", "effective_force", "bow_speed",
    "contact", "target_position", "effective_position", "bridge_delay",
    "nut_delay", "impedance", "free_velocity", "string_velocity",
    "relative_velocity", "friction_force", "junction_increment",
    "min_force", "max_force", "residual", "bracket_width", "root_count",
    "iterations_last", "iterations_max", "solver_calls", "solver_failures",
    "solver_fallbacks", "stick_samples", "slip_samples", "scratch_samples",
    "no_motion_samples", "state_transitions", "direction_changes", "attacks",
    "recoveries", "scratch_score", "max_abs_relative", "finite",
)
BOW_FIELD = {name: index for index, name in enumerate(BOW_FIELDS)}

WAVE_FIELDS = (
    "capacity", "read_delay", "target_delay", "target_frequency",
    "loop_phase_samples", "toward_nut_energy", "toward_bridge_energy",
    "toward_nut_signature", "toward_bridge_signature", "nut_pole",
    "nut_gain", "nut_state", "bridge_pole", "bridge_gain", "bridge_state",
    "write_index", "wave_samples", "excitation_count", "clear_count",
    "reset_count", "clip_count", "bridge_dynamic_input",
    "bridge_dynamic_output", "last_bridge_output", "finite",
)
WAVE_FIELD = {name: index for index, name in enumerate(WAVE_FIELDS)}

COUNTER_FIELDS = (
    "root_count", "iterations_last", "iterations_max", "solver_calls",
    "solver_failures", "solver_fallbacks", "stick_samples", "slip_samples",
    "scratch_samples", "no_motion_samples", "state_transitions",
    "direction_changes", "attacks", "recoveries",
)


def run_csound(
    csound: Path,
    module: Path,
    csd: Path,
    definitions: Mapping[str, object],
    timeout: int = 30,
    output: Path | None = None,
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


def read_states(
    output: str, marker: str, fields: Sequence[str],
) -> Dict[int, State]:
    states: Dict[int, State] = {}
    prefix = marker + " "
    for line in output.splitlines():
        start = line.find(prefix)
        if start < 0:
            continue
        words = line[start:].split()
        if len(words) < len(fields) + 2:
            continue
        tag = int(float(words[1]))
        states[tag] = tuple(
            float(item) for item in words[2:2 + len(fields)])
    return states


def run_case(
    failures: List[str],
    label: str,
    csound: Path,
    module: Path,
    csd: Path,
    definitions: Mapping[str, object],
    bow_tags: Sequence[int],
    wave_tags: Sequence[int],
    timeout: int = 30,
) -> Tuple[Dict[int, State], Dict[int, State]]:
    completed = run_csound(
        csound, module, csd, definitions, timeout=timeout)
    if completed.returncode != 0:
        failures.append(
            "{} failed with status {}:\n{}".format(
                label, completed.returncode, completed.stdout.rstrip()))
        return {}, {}
    bow_first = read_states(completed.stdout, "WG_BOW_A", BOW_FIELDS[:18])
    bow_second = read_states(completed.stdout, "WG_BOW_B", BOW_FIELDS[18:])
    bow = {
        tag: bow_first[tag] + bow_second[tag]
        for tag in bow_first.keys() & bow_second.keys()
    }
    rail = read_states(completed.stdout, "WG_WAVE", WAVE_FIELDS)
    missing_bow = [tag for tag in bow_tags if tag not in bow]
    missing_wave = [tag for tag in wave_tags if tag not in rail]
    if missing_bow or missing_wave:
        failures.append(
            "{} missed bow tags {} or wave tags {}:\n{}".format(
                label, missing_bow, missing_wave,
                completed.stdout.rstrip()))
    return bow, rail


def close(left: float, right: float, tolerance: float = 2.0e-12) -> bool:
    return math.isclose(left, right, rel_tol=tolerance, abs_tol=tolerance)


def bow_value(state: State, name: str) -> float:
    return state[BOW_FIELD[name]]


def wave_value(state: State, name: str) -> float:
    return state[WAVE_FIELD[name]]


def rail_energy(state: State) -> float:
    return wave_value(state, "toward_nut_energy") + wave_value(
        state, "toward_bridge_energy")


def check_bow_common(
    failures: List[str], label: str, state: State,
) -> bool:
    if len(state) != len(BOW_FIELDS):
        failures.append("{} returned the wrong bow state size".format(label))
        return False
    if not all(math.isfinite(item) for item in state):
        failures.append("{} returned a non-finite bow value".format(label))
        return False
    if bow_value(state, "finite") != 1.0:
        failures.append("{} reported invalid bow state".format(label))
    if bow_value(state, "impedance") <= 0.0:
        failures.append("{} returned no string impedance".format(label))
    minimum_force = bow_value(state, "min_force")
    maximum_force = bow_value(state, "max_force")
    if minimum_force < 0.0 or maximum_force < minimum_force:
        failures.append("{} returned invalid force bounds".format(label))
    if (bow_value(state, "contact") > 1.0e-7 and
            bow_value(state, "requested_force") > 0.0 and
            maximum_force <= minimum_force):
        failures.append("{} returned no playable force interval".format(label))
    if bow_value(state, "bracket_width") < 0.0:
        failures.append("{} returned a negative solver bracket".format(label))
    for name in COUNTER_FIELDS:
        found = bow_value(state, name)
        if found < 0.0 or found != math.floor(found):
            failures.append(
                "{} returned invalid {} {:.17g}".format(label, name, found))
    for name in ("iterations_last", "iterations_max"):
        if bow_value(state, name) > 12.0:
            failures.append("{} exceeded the solver limit".format(label))
    iterations = int(bow_value(state, "iterations_last"))
    free_relative = abs(
        bow_value(state, "bow_speed") - bow_value(state, "free_velocity"))
    residual_limit = 1.0e-5 * (1.0 + free_relative)
    width_limit = 1.0e-3 * (1.0 + free_relative)
    if iterations > 0:
        if bow_value(state, "residual") > residual_limit:
            failures.append("{} exceeded the solver residual".format(label))
        if bow_value(state, "bracket_width") > width_limit:
            failures.append("{} exceeded the solver bracket".format(label))
    total_delay = bow_value(state, "bridge_delay") + bow_value(
        state, "nut_delay")
    if total_delay <= 2.0:
        failures.append("{} returned no contact return path".format(label))
    else:
        expected_position = bow_value(state, "bridge_delay") / total_delay
        if not close(
            bow_value(state, "effective_position"),
            expected_position,
            2.0e-10,
        ):
            failures.append("{} returned wrong effective position".format(label))
    impedance = bow_value(state, "impedance")
    expected_increment = bow_value(state, "friction_force") / (
        2.0 * impedance)
    if not close(
        bow_value(state, "junction_increment"),
        expected_increment,
        2.0e-10,
    ):
        failures.append("{} violated its junction force relation".format(label))
    expected_velocity = bow_value(state, "free_velocity") + bow_value(
        state, "junction_increment")
    if not close(
        bow_value(state, "string_velocity"), expected_velocity, 2.0e-10,
    ):
        failures.append("{} violated its junction velocity relation".format(label))
    expected_relative = bow_value(state, "bow_speed") - bow_value(
        state, "string_velocity")
    if not close(
        bow_value(state, "relative_velocity"), expected_relative, 2.0e-10,
    ):
        failures.append("{} returned wrong relative velocity".format(label))
    opposition = bow_value(state, "friction_force") * bow_value(
        state, "relative_velocity")
    if opposition < -1.0e-8:
        failures.append("{} friction opposed string motion".format(label))
    return True


def check_wave_common(
    failures: List[str], label: str, state: State,
) -> bool:
    if len(state) != len(WAVE_FIELDS):
        failures.append("{} returned the wrong rail state size".format(label))
        return False
    if not all(math.isfinite(item) for item in state):
        failures.append("{} returned a non-finite rail value".format(label))
        return False
    if wave_value(state, "finite") != 1.0:
        failures.append("{} reported invalid rail state".format(label))
    if wave_value(state, "reset_count") != 0.0:
        failures.append("{} reset its rails".format(label))
    if wave_value(state, "clip_count") != 0.0:
        failures.append("{} used the rail safety clamp".format(label))
    energy = rail_energy(state)
    if energy < 0.0 or energy > 2.0 * WAVE_LIMIT ** 2 + 1.0e-12:
        failures.append("{} exceeded the rail energy bound".format(label))
    if abs(wave_value(state, "last_bridge_output")) > WAVE_LIMIT + 1.0e-12:
        failures.append("{} exceeded the bridge-output bound".format(label))
    return True


def compare_states(
    failures: List[str], label: str, fields: Sequence[str],
    reference: State, actual: State,
) -> None:
    for name, wanted, found in zip(fields, reference, actual):
        if not close(wanted, found):
            failures.append(
                "{} changed {}: {:.17g} != {:.17g}".format(
                    label, name, found, wanted))


def read_wav(path: Path) -> Tuple[List[float], bytes]:
    with wave.open(str(path), "rb") as audio:
        if (audio.getframerate() != int(SAMPLE_RATE) or
                audio.getnchannels() != 2 or audio.getsampwidth() != 2):
            raise ValueError("unexpected bow-test WAV format")
        frames = audio.readframes(audio.getnframes())
    left = [pair[0] / 32768.0 for pair in struct.iter_unpack("<hh", frames)]
    return left, frames


def render(
    failures: List[str], label: str, csound: Path, module: Path, csd: Path,
    definitions: Mapping[str, object], output: Path,
) -> Tuple[List[float], bytes] | None:
    completed = run_csound(
        csound, module, csd, definitions, output=output)
    if completed.returncode != 0 or not output.exists():
        failures.append(
            "{} render failed:\n{}".format(label, completed.stdout.rstrip()))
        return None
    try:
        return read_wav(output)
    except (ValueError, wave.Error) as error:
        failures.append("{}: {}".format(label, error))
        return None


def rms(samples: Sequence[float]) -> float:
    if not samples:
        return 0.0
    return math.sqrt(sum(item * item for item in samples) / len(samples))


def period_metrics(
    samples: Sequence[float], wanted: float,
) -> Tuple[float, float]:
    if len(samples) < 16:
        raise ValueError("audio window was too short")
    mean = sum(samples) / len(samples)
    centered = [item - mean for item in samples]
    center = SAMPLE_RATE / wanted
    low = max(2, int(math.floor(center * 0.85)))
    high = int(math.ceil(center * 1.15))
    correlations: List[float] = []
    for lag in range(low, high + 1):
        left = centered[:-lag]
        right = centered[lag:]
        cross = sum(a * b for a, b in zip(left, right))
        denominator = math.sqrt(
            sum(item * item for item in left) *
            sum(item * item for item in right))
        correlations.append(cross / denominator if denominator > 0.0 else 0.0)
    peak = max(range(len(correlations)), key=correlations.__getitem__)
    fraction = 0.0
    if 0 < peak < len(correlations) - 1:
        before, middle, after = correlations[peak - 1:peak + 2]
        curvature = before - 2.0 * middle + after
        if curvature != 0.0:
            fraction = 0.5 * (before - after) / curvature
    lag = low + peak + fraction
    return SAMPLE_RATE / lag, correlations[peak]


def harmonic_powers(
    samples: Sequence[float], fundamental: float, count: int = 12,
) -> List[float]:
    if not samples:
        return [0.0] * count
    mean = sum(samples) / len(samples)
    powers: List[float] = []
    for harmonic in range(1, count + 1):
        frequency = harmonic * fundamental
        if frequency >= 0.48 * SAMPLE_RATE:
            powers.append(0.0)
            continue
        real = 0.0
        imaginary = 0.0
        for index, item in enumerate(samples):
            window = 0.5 - 0.5 * math.cos(
                2.0 * math.pi * index / max(1, len(samples) - 1))
            angle = 2.0 * math.pi * frequency * index / SAMPLE_RATE
            centered = item - mean
            real += window * centered * math.cos(angle)
            imaginary -= window * centered * math.sin(angle)
        powers.append(real * real + imaginary * imaginary)
    return powers


def harmonic_centroid(powers: Sequence[float], fundamental: float) -> float:
    total = sum(powers)
    if total <= 0.0:
        return 0.0
    return sum(
        (index + 1) * fundamental * power
        for index, power in enumerate(powers)
    ) / total


def check_no_motion(
    failures: List[str], csound: Path, module: Path, csd: Path,
) -> None:
    with tempfile.TemporaryDirectory(prefix="hlolli-bow-zero-") as folder:
        for variant in range(3):
            label = "no-motion case {}".format(variant)
            definitions = {
                "TEST_CASE": 1, "TEST_VARIANT": variant, "TEST_END": 0.084}
            bow, rail = run_case(
                failures, label, csound, module, csd, definitions, (1,), (1,))
            if 1 not in bow or 1 not in rail:
                continue
            check_bow_common(failures, label, bow[1])
            check_wave_common(failures, label, rail[1])
            if variant == 2:
                if bow_value(bow[1], "no_motion_samples") < 0.98 * 3840.0:
                    failures.append("{} did not remain in no-motion".format(label))
            elif bow_value(bow[1], "state") != 0.0:
                failures.append("{} did not remain off".format(label))
            for name in ("stick_samples", "slip_samples", "scratch_samples"):
                if bow_value(bow[1], name) != 0.0:
                    failures.append("{} recorded {}".format(label, name))
            if bow_value(bow[1], "solver_calls") != 0.0:
                failures.append("{} called the slip solver".format(label))
            if rail_energy(rail[1]) > 1.0e-14:
                failures.append("{} injected rail energy".format(label))
            rendered = render(
                failures, label, csound, module, csd, definitions,
                Path(folder) / "zero-{}.wav".format(variant))
            if rendered is not None and max(map(abs, rendered[0]), default=0.0) > (
                    1.0 / 32768.0):
                failures.append("{} rendered audible output".format(label))


def check_default_motion(
    failures: List[str], csound: Path, module: Path, csd: Path,
) -> Tuple[float, float]:
    definitions = {"TEST_CASE": 2, "TEST_END": 0.61}
    bow, rail = run_case(
        failures, "default bow", csound, module, csd, definitions,
        (1, 2, 3, 4), (1,))
    if any(tag not in bow for tag in (1, 2, 3, 4)) or 1 not in rail:
        return 0.0, 0.0
    for tag, state in bow.items():
        check_bow_common(failures, "default bow snapshot {}".format(tag), state)
    check_wave_common(failures, "default bow", rail[1])
    final = bow[4]
    if bow_value(final, "stick_samples") <= 0.0:
        failures.append("default bow never stuck")
    if bow_value(final, "slip_samples") <= 0.0:
        failures.append("default bow never slipped")
    if bow_value(final, "state_transitions") <= 0.0:
        failures.append("default bow had no stick-slip transitions")
    if bow_value(final, "attacks") != 1.0:
        failures.append("default bow did not record one attack")
    for name in ("solver_failures", "solver_fallbacks", "recoveries"):
        if bow_value(final, name) != 0.0:
            failures.append("default bow recorded {}".format(name))
    active = bow[3]
    if not bow_value(active, "min_force") < bow_value(
            active, "effective_force") < bow_value(active, "max_force"):
        failures.append("default force missed the playable range")
    if bow_value(active, "state") not in (2.0, 3.0):
        failures.append("default bow did not sustain stick-slip motion")
    if bow_value(active, "scratch_score") > 0.05:
        failures.append("default bow retained scratch after its attack")

    with tempfile.TemporaryDirectory(prefix="hlolli-bow-default-") as folder:
        rendered = render(
            failures, "default bow", csound, module, csd, definitions,
            Path(folder) / "default.wav")
        if rendered is None:
            return 0.0, 0.0
        samples = rendered[0]
        steady = samples[int(0.30 * SAMPLE_RATE):int(0.55 * SAMPLE_RATE)]
        measured, periodicity = period_metrics(steady, 440.0)
        cents = 1200.0 * math.log2(measured / 440.0)
        steady_rms = rms(steady)
        if steady_rms < 1.0e-6:
            failures.append("default bow rendered no sustained motion")
        if periodicity < 0.65:
            failures.append(
                "default bow periodicity was {:.9g}".format(periodicity))
        if abs(cents) > 10.0:
            failures.append("default bow missed pitch by {:.9g} cents".format(cents))
        earlier = rms(samples[
            int(0.20 * SAMPLE_RATE):int(0.30 * SAMPLE_RATE)])
        later = rms(samples[
            int(0.45 * SAMPLE_RATE):int(0.55 * SAMPLE_RATE)])
        ratio = later / earlier if earlier > 0.0 else math.inf
        if not 0.5 <= ratio <= 2.0:
            failures.append("default bow sustain ratio was {:.9g}".format(ratio))
        period = max(1, int(round(SAMPLE_RATE / 440.0)))
        threshold = 0.1 * steady_rms
        onset = None
        for cycle in range(20):
            start = cycle * period
            if rms(samples[start:start + period]) >= threshold:
                onset = cycle
                break
        if onset is None:
            failures.append("default bow did not start within 20 periods")
        return periodicity, steady_rms


def check_reversal(
    failures: List[str], csound: Path, module: Path, csd: Path,
) -> None:
    jump_db: List[float] = []
    sustain_ratio: List[float] = []
    with tempfile.TemporaryDirectory(prefix="hlolli-bow-reverse-") as folder:
        for variant, polarity in ((0, 1.0), (1, -1.0)):
            label = "bow reversal {}".format(
                "forward-return" if variant == 0 else "return-forward")
            definitions = {
                "TEST_CASE": 3, "TEST_VARIANT": variant,
                "TEST_END": 0.61,
            }
            bow, rail = run_case(
                failures, label, csound, module, csd, definitions,
                (1, 2, 3), (1,))
            if 3 not in bow or 1 not in rail:
                continue
            for tag, state in bow.items():
                check_bow_common(
                    failures, "{} snapshot {}".format(label, tag), state)
            check_wave_common(failures, label, rail[1])
            if polarity * bow_value(bow[1], "bow_speed") <= 0.0:
                failures.append("{} had no first stroke".format(label))
            if polarity * bow_value(bow[2], "bow_speed") >= 0.0:
                failures.append("{} had no return stroke".format(label))
            final = bow[3]
            if bow_value(final, "direction_changes") != 1.0:
                failures.append(
                    "{} did not record one direction change".format(label))
            if bow_value(final, "attacks") != 1.0:
                failures.append("{} caused another attack".format(label))
            if bow_value(final, "recoveries") != 0.0:
                failures.append("{} used finite recovery".format(label))

            rendered = render(
                failures, label, csound, module, csd, definitions,
                Path(folder) / "reverse-{}.wav".format(variant))
            if rendered is None:
                continue
            samples = rendered[0]
            before = samples[
                int(0.15 * SAMPLE_RATE):int(0.23 * SAMPLE_RATE)]
            attack = samples[
                int(0.25 * SAMPLE_RATE):int(0.31 * SAMPLE_RATE)]
            after = samples[
                int(0.40 * SAMPLE_RATE):int(0.55 * SAMPLE_RATE)]
            before_rms = rms(before)
            attack_rms = rms(attack)
            after_rms = rms(after)
            ratio = (
                after_rms / before_rms if before_rms > 0.0 else math.inf)
            sustain_ratio.append(ratio)
            jump_db.append(
                20.0 * math.log10(attack_rms / before_rms)
                if attack_rms > 0.0 and before_rms > 0.0 else math.inf)
            if not 0.25 <= ratio <= 4.0:
                failures.append(
                    "{} RMS ratio was {:.9g}".format(label, ratio))
            measured, periodicity = period_metrics(after, 440.0)
            cents = 1200.0 * math.log2(measured / 440.0)
            if periodicity < 0.5:
                failures.append(
                    "{} did not regain periodic motion".format(label))
            if abs(cents) > 15.0:
                failures.append(
                    "{} missed pitch by {:.9g} cents".format(label, cents))

    if len(jump_db) == 2 and abs(jump_db[0] - jump_db[1]) > 0.55:
        failures.append(
            "mirrored bow-reversal jumps differed by {:.9g} dB".format(
                abs(jump_db[0] - jump_db[1])))
    if (len(sustain_ratio) == 2 and
            max(sustain_ratio) > 1.1 * min(sustain_ratio)):
        failures.append(
            "mirrored bow-reversal sustain ratios differed: {}".format(
                sustain_ratio))


def check_extremes(
    failures: List[str], csound: Path, module: Path, csd: Path,
    default_periodicity: float,
) -> None:
    scratch_evidence = False
    range_departure = False
    with tempfile.TemporaryDirectory(prefix="hlolli-bow-extreme-") as folder:
        for variant in range(3):
            label = "bow extreme {}".format(variant)
            definitions = {
                "TEST_CASE": 4, "TEST_VARIANT": variant, "TEST_END": 0.41}
            bow, rail = run_case(
                failures, label, csound, module, csd, definitions, (1,), (1,))
            if 1 not in bow or 1 not in rail:
                continue
            check_bow_common(failures, label, bow[1])
            check_wave_common(failures, label, rail[1])
            if bow_value(bow[1], "solver_failures") != 0.0:
                failures.append("{} had a solver failure".format(label))
            if bow_value(bow[1], "solver_fallbacks") > 1.0:
                failures.append("{} used repeated solver fallback".format(label))
            scratch_evidence = scratch_evidence or (
                bow_value(bow[1], "scratch_samples") > 0.0 or
                bow_value(bow[1], "scratch_score") >= 0.25)
            force = bow_value(bow[1], "effective_force")
            range_departure = range_departure or (
                force < bow_value(bow[1], "min_force") or
                force > bow_value(bow[1], "max_force"))
            rendered = render(
                failures, label, csound, module, csd, definitions,
                Path(folder) / "extreme-{}.wav".format(variant))
            if rendered is None:
                continue
            samples = rendered[0]
            if max(map(abs, samples), default=0.0) > DRY_LIMIT + 2.0 / 32768.0:
                failures.append("{} exceeded dry output bound".format(label))
            window = samples[
                int(0.20 * SAMPLE_RATE):int(0.38 * SAMPLE_RATE)]
            if rms(window) > 1.0e-6:
                _, periodicity = period_metrics(window, 440.0)
                if periodicity < max(0.4, default_periodicity - 0.05):
                    scratch_evidence = True
    if not scratch_evidence:
        failures.append("control extremes produced no scratch departure")
    if not range_departure:
        failures.append("control extremes never left the playable force range")


def check_positions(
    failures: List[str], csound: Path, module: Path, csd: Path,
) -> None:
    centroids: List[float] = []
    normal_forces: List[float] = []
    spectra: List[List[float]] = []
    settings = (
        ("0.05", 0, 0.05, {}),
        ("0.125", 1, 0.125, {}),
        ("0.24", 0, 0.24, {
            "TEST_BOW_POSITION": 0.24,
            "TEST_BOW_FORCE": 0.85184032185544689,
        }),
        ("0.25", 2, 0.25, {}),
    )
    with tempfile.TemporaryDirectory(prefix="hlolli-bow-position-") as folder:
        for name, variant, wanted, overrides in settings:
            label = "bow position {}".format(name)
            definitions = {
                "TEST_CASE": 5, "TEST_VARIANT": variant, "TEST_END": 0.51,
                **overrides,
            }
            bow, rail = run_case(
                failures, label, csound, module, csd, definitions, (1,), (1,))
            if 1 not in bow or 1 not in rail:
                return
            check_bow_common(failures, label, bow[1])
            check_wave_common(failures, label, rail[1])
            if not close(bow_value(bow[1], "target_position"), wanted):
                failures.append("{} changed its target position".format(label))
            if not close(
                bow_value(bow[1], "effective_position"), wanted, 2.0e-8,
            ):
                failures.append("{} missed its contact geometry".format(label))
            if bow_value(bow[1], "state") not in (2.0, 3.0):
                failures.append("{} left the matched stick-slip regime".format(label))
            if bow_value(bow[1], "scratch_score") > 0.05:
                failures.append("{} retained scratch in the comparison".format(label))
            for name in ("solver_failures", "solver_fallbacks", "recoveries"):
                if bow_value(bow[1], name) != 0.0:
                    failures.append("{} recorded {}".format(label, name))
            normal_forces.append(bow_value(bow[1], "effective_force"))
            rendered = render(
                failures, label, csound, module, csd, definitions,
                Path(folder) / "position-{}.wav".format(name))
            if rendered is None:
                return
            steady = rendered[0][
                int(0.25 * SAMPLE_RATE):int(0.45 * SAMPLE_RATE)]
            measured, periodicity = period_metrics(steady, 440.0)
            cents = 1200.0 * math.log2(measured / 440.0)
            if abs(cents) > 15.0 or periodicity < 0.5:
                failures.append(
                    "{} lost stable pitch: {:.2f} cents, {:.3f} periodicity"
                    .format(label, cents, periodicity))
            powers = harmonic_powers(steady, measured)
            spectra.append(powers)
            centroids.append(harmonic_centroid(powers, measured))
    if max(normal_forces) - min(normal_forces) > 0.02 * max(normal_forces):
        failures.append("position comparison used unmatched normal force")
    if max(centroids) <= 1.02 * min(centroids):
        failures.append("contact position did not move the harmonic centroid")
    totals = [sum(spectrum) for spectrum in spectra]
    if min(totals[0], totals[-1]) > 0.0:
        normalized_a = [item / totals[0] for item in spectra[0]]
        normalized_b = [item / totals[-1] for item in spectra[-1]]
        difference = sum(
            abs(left - right)
            for left, right in zip(normalized_a, normalized_b))
        if difference < 0.02:
            failures.append("contact position did not change dry harmonics")


def check_high_frequency(
    failures: List[str], csound: Path, module: Path, csd: Path,
) -> None:
    definitions = {"TEST_CASE": 9, "TEST_END": 0.61}
    bow, rail = run_case(
        failures, "high-frequency near-bridge bow", csound, module, csd,
        definitions, (1, 2), (1,))
    if any(tag not in bow for tag in (1, 2)) or 1 not in rail:
        return
    for tag, state in bow.items():
        check_bow_common(
            failures, "high-frequency bow snapshot {}".format(tag), state)
    check_wave_common(failures, "high-frequency near-bridge bow", rail[1])
    active = bow[2]
    if bow_value(active, "state") not in (2.0, 3.0):
        failures.append("high-frequency bow left stick-slip motion")
    if bow_value(active, "scratch_score") > 0.05:
        failures.append("high-frequency bow retained scratch")
    if not close(bow_value(active, "target_position"), 0.01):
        failures.append("high-frequency bow changed its target position")
    if not close(bow_value(active, "bridge_delay"), 1.0, 2.0e-10):
        failures.append("high-frequency bow missed the minimum branch")
    if not bow_value(active, "min_force") < bow_value(
            active, "effective_force") < bow_value(active, "max_force"):
        failures.append("high-frequency bow missed its playable force range")
    for name in ("solver_failures", "solver_fallbacks", "recoveries"):
        if bow_value(active, name) != 0.0:
            failures.append("high-frequency bow recorded {}".format(name))
    for name in ("stick_samples", "slip_samples", "solver_calls"):
        if bow_value(active, name) <= 0.0:
            failures.append("high-frequency bow recorded no {}".format(name))
    if bow_value(active, "attacks") != 1.0:
        failures.append("high-frequency bow did not record one attack")
    if not close(wave_value(rail[1], "target_frequency"), 5000.0, 2.0e-11):
        failures.append("high-frequency bow changed its target frequency")
    if wave_value(rail[1], "wave_samples") != 28320.0:
        failures.append("high-frequency bow processed the wrong sample count")
    if rail_energy(rail[1]) <= 1.0e-8:
        failures.append("high-frequency bow stored no rail energy")

    with tempfile.TemporaryDirectory(prefix="hlolli-bow-high-") as folder:
        rendered = render(
            failures, "high-frequency near-bridge bow", csound, module, csd,
            definitions, Path(folder) / "high.wav")
        if rendered is None:
            return
        samples = rendered[0]
        steady = samples[
            int(0.25 * SAMPLE_RATE):int(0.55 * SAMPLE_RATE)]
        if rms(steady) < 1.0e-6:
            failures.append("high-frequency bow rendered no sustained motion")
        if max(map(abs, samples), default=0.0) > (
                DRY_LIMIT + 2.0 / 32768.0):
            failures.append("high-frequency bow exceeded dry output bound")


def check_release(
    failures: List[str], csound: Path, module: Path, csd: Path,
) -> None:
    bow, rail = run_case(
        failures, "bow release", csound, module, csd,
        {"TEST_CASE": 10, "TEST_END": 0.46}, (1, 2, 3, 4), (1,))
    if any(tag not in bow for tag in (1, 2, 3, 4)) or 1 not in rail:
        return
    for tag, state in bow.items():
        check_bow_common(failures, "release snapshot {}".format(tag), state)
    check_wave_common(failures, "bow release", rail[1])
    before = bow[1]
    early = bow[2]
    late = bow[4]
    if bow_value(before, "contact") < 0.99:
        failures.append("bow release started without full contact")
    if not 0.1 < bow_value(early, "contact") < bow_value(before, "contact"):
        failures.append("bow release did not keep a decaying contact tail")
    expected_contact = bow_value(early, "contact") * math.exp(-0.004 / 0.002)
    if not math.isclose(bow_value(bow[3], "contact"), expected_contact,
                        abs_tol=1.0e-6):
        failures.append("bow lift did not use the 2 ms contact time constant")
    if bow_value(early, "requested_force") <= 0.0:
        failures.append("bow release cut force at the trigger edge")
    if bow_value(early, "state") == 0.0:
        failures.append("bow release entered off state at the trigger edge")
    if bow_value(late, "contact") > 1.0e-7:
        failures.append("bow release did not finish its contact decay")
    if bow_value(late, "state") != 0.0:
        failures.append("bow release did not reach off state")
    if bow_value(late, "requested_force") != 0.0:
        failures.append("bow release retained force after contact ended")
    if bow_value(late, "attacks") != 1.0:
        failures.append("bow release changed the attack count")
    for name in ("solver_failures", "solver_fallbacks", "recoveries"):
        if bow_value(late, name) != 0.0:
            failures.append("bow release recorded {}".format(name))


def check_recovery(
    failures: List[str], csound: Path, module: Path, csd: Path,
) -> None:
    definitions = {"TEST_CASE": 6, "TEST_END": 0.61}
    bow, rail = run_case(
        failures, "bow fault recovery", csound, module, csd, definitions,
        (1, 2, 3, 4), (1,))
    if any(tag not in bow for tag in (1, 2, 3, 4)) or 1 not in rail:
        return
    for tag, state in bow.items():
        check_bow_common(failures, "recovery snapshot {}".format(tag), state)
    check_wave_common(failures, "bow fault recovery", rail[1])
    for name in ("solver_failures", "solver_fallbacks", "recoveries"):
        before = bow_value(bow[1], name)
        if before != 0.0:
            failures.append("bow recorded {} before fault injection".format(name))
        for tag in (2, 3, 4):
            if bow_value(bow[tag], name) != before + 1.0:
                failures.append(
                    "recovery snapshot {} had wrong {} delta".format(
                        tag, name))
    for name in ("friction_force", "junction_increment"):
        if bow_value(bow[2], name) != 0.0:
            failures.append(
                "bow recovery leaked {} {}".format(
                    name, bow_value(bow[2], name)))
    if bow_value(bow[2], "string_velocity") != bow_value(
            bow[2], "free_velocity"):
        failures.append("bow recovery changed the string junction velocity")
    with tempfile.TemporaryDirectory(prefix="hlolli-bow-recovery-") as folder:
        rendered = render(
            failures, "bow fault recovery", csound, module, csd, definitions,
            Path(folder) / "recovery.wav")
        if rendered is None:
            return
        after = rendered[0][
            int(0.40 * SAMPLE_RATE):int(0.55 * SAMPLE_RATE)]
        measured, periodicity = period_metrics(after, 440.0)
        cents = 1200.0 * math.log2(measured / 440.0)
        if rms(after) < 1.0e-6 or periodicity < 0.5 or abs(cents) > 15.0:
            failures.append("bow did not regain stable motion after recovery")


def check_handoff(
    failures: List[str], csound: Path, module: Path, csd: Path,
) -> None:
    common = {"TEST_CASE": 7, "TEST_END": 0.51}
    reference_bow, reference_wave = run_case(
        failures, "continuous bow", csound, module, csd, common, (1,), (1,))
    if 1 not in reference_bow or 1 not in reference_wave:
        return
    check_bow_common(failures, "continuous bow", reference_bow[1])
    check_wave_common(failures, "continuous bow", reference_wave[1])
    split_cases = (("block", 0.25), ("mid-block", 0.250125))
    for name, split_time in split_cases:
        definitions = dict(common)
        definitions.update({"TEST_SPLIT": 1, "TEST_SPLIT_TIME": split_time})
        bow, rail = run_case(
            failures, "{} bow handoff".format(name), csound, module, csd,
            definitions, (1,), (1,))
        if 1 not in bow or 1 not in rail:
            continue
        compare_states(
            failures, "{} bow handoff".format(name), BOW_FIELDS,
            reference_bow[1], bow[1])
        compare_states(
            failures, "{} rail handoff".format(name), WAVE_FIELDS,
            reference_wave[1], rail[1])

    with tempfile.TemporaryDirectory(prefix="hlolli-bow-handoff-") as folder:
        rendered = render(
            failures, "continuous bow", csound, module, csd, common,
            Path(folder) / "continuous.wav")
        if rendered is None:
            return
        reference_frames = rendered[1]
        for name, split_time in split_cases:
            definitions = dict(common)
            definitions.update({
                "TEST_SPLIT": 1,
                "TEST_SPLIT_TIME": split_time,
            })
            split = render(
                failures, "{} bow handoff".format(name), csound, module, csd,
                definitions, Path(folder) / "{}.wav".format(name))
            if split is not None and split[1] != reference_frames:
                failures.append("{} bow handoff changed rendered samples".format(name))


def check_stress(
    failures: List[str], csound: Path, module: Path, csd: Path,
) -> None:
    bow, rail = run_case(
        failures, "bow stress", csound, module, csd,
        {"TEST_CASE": 8, "TEST_END": 10.01},
        (1, 2, 3, 4), (1, 2, 3, 4), timeout=60)
    if any(tag not in bow or tag not in rail for tag in (1, 2, 3, 4)):
        return
    for tag in (1, 2, 3, 4):
        label = "bow stress string {}".format(tag)
        check_bow_common(failures, label, bow[tag])
        check_wave_common(failures, label, rail[tag])
        if wave_value(rail[tag], "wave_samples") != 480000.0:
            failures.append("{} processed the wrong sample count".format(label))
        if bow_value(bow[tag], "direction_changes") < 5.0:
            failures.append("{} had too few bow reversals".format(label))
        if bow_value(bow[tag], "attacks") < 5.0:
            failures.append("{} had too few gated attacks".format(label))
        if bow_value(bow[tag], "stick_samples") <= 0.0:
            failures.append("{} never stuck".format(label))
        if bow_value(bow[tag], "slip_samples") <= 0.0:
            failures.append("{} never slipped".format(label))
        if bow_value(bow[tag], "solver_failures") != 0.0:
            failures.append("{} had solver failures".format(label))
        calls = bow_value(bow[tag], "solver_calls")
        if bow_value(bow[tag], "solver_fallbacks") > max(1.0, 0.001 * calls):
            failures.append("{} used too many solver fallbacks".format(label))
        if bow_value(bow[tag], "recoveries") != 0.0:
            failures.append("{} used finite recovery".format(label))
        if bow_value(bow[tag], "max_abs_relative") > 10.0:
            failures.append("{} exceeded relative-velocity bound".format(label))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csound", required=True, type=Path)
    parser.add_argument("--module", required=True, type=Path)
    parser.add_argument("--csd", required=True, type=Path)
    arguments = parser.parse_args()

    failures: List[str] = []
    try:
        check_no_motion(
            failures, arguments.csound, arguments.module, arguments.csd)
        default_periodicity, _ = check_default_motion(
            failures, arguments.csound, arguments.module, arguments.csd)
        check_reversal(
            failures, arguments.csound, arguments.module, arguments.csd)
        check_extremes(
            failures, arguments.csound, arguments.module, arguments.csd,
            default_periodicity)
        check_positions(
            failures, arguments.csound, arguments.module, arguments.csd)
        check_high_frequency(
            failures, arguments.csound, arguments.module, arguments.csd)
        check_release(
            failures, arguments.csound, arguments.module, arguments.csd)
        check_recovery(
            failures, arguments.csound, arguments.module, arguments.csd)
        check_handoff(
            failures, arguments.csound, arguments.module, arguments.csd)
        check_stress(
            failures, arguments.csound, arguments.module, arguments.csd)
    except (OSError, subprocess.TimeoutExpired, ValueError, wave.Error) as error:
        print("bow test failed: {}".format(error), file=sys.stderr)
        return 2

    if failures:
        for failure in failures:
            print("failure: {}".format(failure), file=sys.stderr)
        return 1
    print("violin bow checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
