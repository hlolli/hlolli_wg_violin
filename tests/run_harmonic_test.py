#!/usr/bin/env python3
"""Check natural and artificial harmonic stopping."""

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
OPEN_FREQUENCIES = (
    195.99771799087463,
    293.66476791740757,
    440.0,
    659.2551138257398,
)
HARMONIC_FIELDS = (
    "requested_order", "active_order", "filter_order", "valid", "natural",
    "sounding_frequency", "fundamental_frequency", "stop_position",
    "touch_position", "touch_target", "touch_pressure", "touch_period",
    "projection_input", "projection_output", "transitions", "rejections",
    "touch_samples", "history_index", "finite",
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
        timeout=60,
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
            raise ValueError("unexpected harmonic-test WAV format")
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
    harmonic_tags: Sequence[int] = (),
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
    harmonics = read_tagged(
        completed.stdout, "WG_HARMONIC", len(HARMONIC_FIELDS))
    waves = read_tagged(completed.stdout, "WG_WAVE", len(WAVE_FIELDS))
    strings = read_tagged(completed.stdout, "WG_STRING", len(STRING_FIELDS))
    bodies = read_tagged(
        completed.stdout, "WG_HARMONIC_BODY", len(BODY_FIELDS))
    missing = (
        [tag for tag in harmonic_tags if tag not in harmonics],
        [tag for tag in wave_tags if tag not in waves],
        [tag for tag in string_tags if tag not in strings],
        [tag for tag in body_tags if tag not in bodies],
    )
    if any(missing):
        failures.append(
            "{} missed harmonic {}, wave {}, string {}, or body {} tags:\n{}".
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
    return harmonics, waves, strings, bodies, rendered


def check_harmonic_common(
    failures: List[str], label: str, state: State,
) -> None:
    if len(state) != len(HARMONIC_FIELDS):
        failures.append("{} returned the wrong harmonic state size".format(label))
        return
    if not all(math.isfinite(item) for item in state):
        failures.append("{} returned non-finite harmonic state".format(label))
        return
    if value(state, HARMONIC_FIELDS, "finite") != 1.0:
        failures.append("{} reported invalid harmonic state".format(label))
    for field in ("valid", "natural"):
        if value(state, HARMONIC_FIELDS, field) not in (0.0, 1.0):
            failures.append("{} returned non-Boolean {}".format(label, field))
    filter_order = value(state, HARMONIC_FIELDS, "filter_order")
    if filter_order != 0.0 and not 2.0 <= filter_order <= 8.0:
        failures.append("{} returned invalid filter order".format(label))
    for field in ("stop_position", "touch_position", "touch_target",
                  "touch_pressure"):
        found = value(state, HARMONIC_FIELDS, field)
        if not 0.0 <= found <= 1.0:
            failures.append("{} {} left [0, 1]: {:.17g}".format(
                label, field, found))
    if value(state, HARMONIC_FIELDS, "history_index") < 0.0:
        failures.append("{} returned a negative history index".format(label))


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


def partial_power(samples: Sequence[float], frequency: float) -> float:
    if len(samples) < 2 or frequency <= 0.0:
        return 0.0
    mean = sum(samples) / len(samples)
    real = 0.0
    imaginary = 0.0
    for index, sample in enumerate(samples):
        window = 0.5 - 0.5 * math.cos(
            2.0 * math.pi * index / (len(samples) - 1))
        angle = 2.0 * math.pi * frequency * index / SAMPLE_RATE
        centered = (sample - mean) * window
        real += centered * math.cos(angle)
        imaginary -= centered * math.sin(angle)
    return real * real + imaginary * imaginary


def period_metrics(
    samples: Sequence[float], wanted: float,
) -> Tuple[float, float]:
    mean = sum(samples) / len(samples)
    centered = [sample - mean for sample in samples]
    center = SAMPLE_RATE / wanted
    low = max(2, int(math.floor(0.82 * center)))
    high = int(math.ceil(1.18 * center))
    correlations: List[float] = []
    for lag in range(low, high + 1):
        left = centered[:-lag]
        right = centered[lag:]
        denominator = math.sqrt(
            sum(item * item for item in left) *
            sum(item * item for item in right))
        cross = sum(a * b for a, b in zip(left, right))
        correlations.append(cross / denominator if denominator else 0.0)
    peak = max(range(len(correlations)), key=correlations.__getitem__)
    fraction = 0.0
    if 0 < peak < len(correlations) - 1:
        before, middle, after = correlations[peak - 1:peak + 2]
        curvature = before - 2.0 * middle + after
        if curvature:
            fraction = 0.5 * (before - after) / curvature
    return SAMPLE_RATE / (low + peak + fraction), correlations[peak]


def check_harmonic_audio(
    failures: List[str],
    label: str,
    rendered: Audio,
    fundamental: float,
    order: int,
    sounding: float,
) -> None:
    samples = stereo_window(rendered[1], 0.30, 0.47)
    level = rms(samples)
    if level < 2.0:
        failures.append("{} had quiet steady audio: {:.9g}".format(label, level))
        return
    if max(abs(sample) for sample in samples) >= 32767.0:
        failures.append("{} saturated its PCM".format(label))
    measured, periodicity = period_metrics(samples, sounding)
    cents = 1200.0 * math.log2(measured / sounding)
    if abs(cents) > 45.0 or periodicity < 0.08:
        failures.append(
            "{} missed sounding pitch by {:.9g} cents at correlation {:.9g}".
            format(label, cents, periodicity))
    selected = partial_power(samples, sounding)
    neighbors = [
        partial_power(samples, harmonic * fundamental)
        for harmonic in (order - 1, order + 1)
        if harmonic > 0 and harmonic * fundamental < 0.48 * SAMPLE_RATE
    ]
    if selected <= 0.0:
        failures.append("{} had no selected harmonic energy".format(label))
    elif neighbors and selected < 0.5 * max(neighbors):
        failures.append(
            "{} did not notch adjacent modes around order {}".format(
                label, order))


def check_steady_state(
    failures: List[str],
    label: str,
    state: State,
    wave_state: State,
    string_state: State,
    order: int,
    sounding: float,
    fundamental: float,
    stop: float,
    touch: float,
    natural: bool,
) -> None:
    check_harmonic_common(failures, label, state)
    check_wave_common(failures, label, wave_state)
    expected = (
        ("requested_order", float(order)),
        ("active_order", float(order)),
        ("filter_order", float(order)),
        ("valid", 1.0),
        ("natural", 1.0 if natural else 0.0),
    )
    for field, wanted in expected:
        found = value(state, HARMONIC_FIELDS, field)
        if found != wanted:
            failures.append(
                "{} {} was {:.17g}, wanted {:.17g}".format(
                    label, field, found, wanted))
    for field, wanted in (
        ("sounding_frequency", sounding),
        ("fundamental_frequency", fundamental),
        ("stop_position", stop),
        ("touch_position", touch),
        ("touch_period", SAMPLE_RATE / sounding),
    ):
        found = value(state, HARMONIC_FIELDS, field)
        if not close(found, wanted, 2.0e-9):
            failures.append(
                "{} {} was {:.17g}, wanted {:.17g}".format(
                    label, field, found, wanted))
    if value(state, HARMONIC_FIELDS, "touch_target") < 0.9:
        failures.append("{} had no firm touch target".format(label))
    if value(state, HARMONIC_FIELDS, "touch_pressure") < 0.85:
        failures.append("{} touch did not settle".format(label))
    if value(state, HARMONIC_FIELDS, "touch_samples") <= 0.0:
        failures.append("{} recorded no touch samples".format(label))
    if value(state, HARMONIC_FIELDS, "rejections") != 0.0:
        failures.append("{} rejected a valid harmonic".format(label))
    if not close(
            value(wave_state, WAVE_FIELDS, "target_frequency"),
            fundamental, 2.0e-9):
        failures.append("{} waveguide kept the wrong fundamental".format(label))
    if value(wave_state, WAVE_FIELDS, "excitation_count") != 1.0:
        failures.append("{} had the wrong attack count".format(label))
    if not close(
            value(string_state, STRING_FIELDS, "frequency"),
            sounding, 2.0e-9):
        failures.append("{} lost its requested sounding pitch".format(label))


def check_orders(
    failures: List[str], csound: Path, module: Path, csd: Path,
) -> None:
    with tempfile.TemporaryDirectory(prefix="hlolli-harmonic-orders-") as folder:
        temporary = Path(folder)
        for order in range(2, 9):
            sounding = OPEN_FREQUENCIES[0] * order
            label = "natural order {}".format(order)
            result = run_case(
                failures, label, csound, module, csd,
                {"TEST_CASE": 1, "TEST_ORDER": order,
                 "TEST_FREQUENCY": "{:.17g}".format(sounding)},
                (1,), (1,), (1,), output=temporary / "natural-{}.wav".format(order))
            if 1 in result[0] and 1 in result[1] and 1 in result[2] and result[4]:
                check_steady_state(
                    failures, label, result[0][1], result[1][1], result[2][1],
                    order, sounding, OPEN_FREQUENCIES[0], 0.0, 1.0 / order,
                    True)
                check_harmonic_audio(
                    failures, label, result[4], OPEN_FREQUENCIES[0],
                    order, sounding)

        sounding = 1760.0
        deterministic: Tuple[State, State, bytes] | None = None
        for order in range(2, 9):
            fundamental = sounding / order
            stop = 1.0 - OPEN_FREQUENCIES[0] / fundamental
            touch = stop + (OPEN_FREQUENCIES[0] / fundamental) / order
            label = "artificial order {}".format(order)
            result = run_case(
                failures, label, csound, module, csd,
                {"TEST_CASE": 1, "TEST_ORDER": order,
                 "TEST_FREQUENCY": sounding},
                (1,), (1,), (1,),
                output=temporary / "artificial-{}.wav".format(order))
            if 1 in result[0] and 1 in result[1] and 1 in result[2] and result[4]:
                check_steady_state(
                    failures, label, result[0][1], result[1][1], result[2][1],
                    order, sounding, fundamental, stop, touch, False)
                check_harmonic_audio(
                    failures, label, result[4], fundamental, order, sounding)
                if order == 4:
                    deterministic = (result[0][1], result[1][1], result[4][0])

        repeated = run_case(
            failures, "artificial deterministic repeat", csound, module, csd,
            {"TEST_CASE": 1, "TEST_ORDER": 4, "TEST_FREQUENCY": sounding},
            (1,), (1,), (1,), output=temporary / "artificial-repeat.wav")
        if deterministic is not None and 1 in repeated[0] and 1 in repeated[1] and repeated[4]:
            if deterministic[0] != repeated[0][1]:
                failures.append("artificial harmonic changed deterministic state")
            if deterministic[1] != repeated[1][1]:
                failures.append("artificial harmonic changed deterministic rail state")
            if deterministic[2] != repeated[4][0]:
                failures.append("artificial harmonic changed deterministic PCM")


def transition_step_ok(samples: Sequence[float], boundary: float) -> bool:
    center = int(boundary * SAMPLE_RATE)
    first = max(1, center - 512)
    last = min(len(samples), center + 512)
    differences = [
        abs(samples[index] - samples[index - 1])
        for index in range(first, last)
    ]
    background = sorted(differences[:max(1, min(400, center - first))])
    reference = background[int(0.99 * (len(background) - 1))]
    boundary_step = max(
        abs(samples[index] - samples[index - 1])
        for index in range(max(1, center - 2), min(len(samples), center + 3))
    )
    return boundary_step <= max(1200.0, 12.0 * reference)


def check_pressure_path(
    failures: List[str], csound: Path, module: Path, csd: Path,
) -> None:
    with tempfile.TemporaryDirectory(prefix="hlolli-harmonic-pressure-") as folder:
        result = run_case(
            failures, "harmonic touch pressure", csound, module, csd,
            {"TEST_CASE": 2, "TEST_ORDER": 4, "TEST_FREQUENCY": 1760,
             "TEST_END": 0.35},
            tuple(range(1, 10)), tuple(range(1, 10)), tuple(range(1, 10)),
            output=Path(folder) / "pressure.wav")
    if any(tag not in result[0] or tag not in result[1]
           for tag in range(1, 10)) or result[4] is None:
        return
    for tag in range(1, 10):
        check_harmonic_common(
            failures, "touch pressure snapshot {}".format(tag), result[0][tag])
        check_wave_common(
            failures, "touch pressure snapshot {}".format(tag), result[1][tag])
        if value(result[1][tag], WAVE_FIELDS, "excitation_count") != 1.0:
            failures.append("touch pressure snapshot {} retriggered".format(tag))
    pressures = [
        value(result[0][tag], HARMONIC_FIELDS, "touch_pressure")
        for tag in range(1, 10)
    ]
    if pressures[0] > 0.05:
        failures.append("normal stopping began with harmonic pressure")
    if not pressures[0] < pressures[1] < pressures[2] < pressures[3]:
        failures.append("harmonic touch did not rise smoothly: {}".format(pressures[:4]))
    if pressures[3] < 0.75:
        failures.append("harmonic touch did not speak")
    if not pressures[3] > pressures[4] > pressures[5] > pressures[6]:
        failures.append("harmonic touch did not release smoothly: {}".format(pressures[3:7]))
    if pressures[6] > 0.15:
        failures.append("failed harmonic touch did not lift")
    if not pressures[6] < pressures[7] < pressures[8] or pressures[8] < 0.75:
        failures.append("harmonic touch did not return: {}".format(pressures[6:]))
    transitions = [
        value(result[0][tag], HARMONIC_FIELDS, "transitions")
        for tag in range(1, 10)
    ]
    if any(right < left for left, right in zip(transitions, transitions[1:])):
        failures.append("harmonic transition count went backwards")
    if transitions[-1] < 3.0:
        failures.append("harmonic touch did not count all three transitions")
    mono = stereo_window(result[4][1], 0.0, 0.34)
    for boundary in (0.08, 0.16, 0.24):
        if not transition_step_ok(mono, boundary):
            failures.append(
                "harmonic touch made a sharp step at {:.3f} seconds".format(boundary))


def check_rapid_order_changes(
    failures: List[str], csound: Path, module: Path, csd: Path,
) -> None:
    with tempfile.TemporaryDirectory(prefix="hlolli-harmonic-rapid-") as folder:
        result = run_case(
            failures, "rapid harmonic orders", csound, module, csd,
            {"TEST_CASE": 9, "TEST_END": 0.36},
            tuple(range(1, 8)), tuple(range(1, 8)), tuple(range(1, 8)),
            output=Path(folder) / "rapid.wav")
    if any(tag not in result[0] or tag not in result[1]
           for tag in range(1, 8)) or result[4] is None:
        return

    transitions = []
    touch_samples = []
    for tag, order in enumerate(range(2, 9), 1):
        label = "rapid order {}".format(order)
        harmonic = result[0][tag]
        wave_state = result[1][tag]
        check_harmonic_common(failures, label, harmonic)
        check_wave_common(failures, label, wave_state)
        for field, wanted in (
            ("requested_order", float(order)),
            ("active_order", float(order)),
            ("filter_order", float(order)),
            ("valid", 1.0),
            ("natural", 1.0),
            ("sounding_frequency", OPEN_FREQUENCIES[0] * order),
            ("fundamental_frequency", OPEN_FREQUENCIES[0]),
            ("touch_position", 1.0 / order),
            ("touch_period", SAMPLE_RATE / (OPEN_FREQUENCIES[0] * order)),
        ):
            found = value(harmonic, HARMONIC_FIELDS, field)
            if not close(found, wanted, 2.0e-9):
                failures.append(
                    "{} {} was {:.17g}, wanted {:.17g}".format(
                        label, field, found, wanted))
        if value(harmonic, HARMONIC_FIELDS, "touch_target") < 0.9:
            failures.append("{} had not selected its new projection".format(label))
        if value(harmonic, HARMONIC_FIELDS, "touch_pressure") < 0.85:
            failures.append("{} lost touch pressure during its short note".format(label))
        if value(wave_state, WAVE_FIELDS, "excitation_count") != 1.0:
            failures.append("{} retriggered the rail".format(label))
        if not close(
                value(wave_state, WAVE_FIELDS, "target_frequency"),
                OPEN_FREQUENCIES[0], 2.0e-9):
            failures.append("{} changed the internal fundamental".format(label))
        transitions.append(value(harmonic, HARMONIC_FIELDS, "transitions"))
        touch_samples.append(value(harmonic, HARMONIC_FIELDS, "touch_samples"))

    if transitions != [float(item) for item in range(7)]:
        failures.append("rapid harmonic transition counts were {}".format(transitions))
    if any(right <= left for left, right in zip(touch_samples, touch_samples[1:])):
        failures.append("rapid harmonic touch sample count did not advance")

    channels = result[4][1]
    whole = stereo_window(channels, 0.0, 0.35)
    for index, order in enumerate(range(2, 9)):
        start = index * 0.048 + 0.026
        stop = index * 0.048 + 0.045
        samples = stereo_window(channels, start, stop)
        label = "rapid order {} audio".format(order)
        if rms(samples) < 2.0:
            failures.append("{} was quiet".format(label))
            continue
        sounding = OPEN_FREQUENCIES[0] * order
        selected = partial_power(samples, sounding)
        neighbors = [
            partial_power(samples, OPEN_FREQUENCIES[0] * neighbor)
            for neighbor in (order - 1, order + 1)
            if neighbor > 0
        ]
        if selected <= 0.0 or selected < 0.5 * max(neighbors):
            failures.append("{} did not reach its selected projection".format(label))
        measured, periodicity = period_metrics(samples, sounding)
        cents = 1200.0 * math.log2(measured / sounding)
        if abs(cents) > 80.0 or periodicity < 0.02:
            failures.append(
                "{} missed by {:.9g} cents at correlation {:.9g}".format(
                    label, cents, periodicity))
    for boundary in (0.048, 0.096, 0.144, 0.192, 0.240, 0.288):
        if not transition_step_ok(whole, boundary):
            failures.append(
                "rapid harmonic change clicked at {:.3f} seconds".format(boundary))
    if max(abs(sample) for channel in channels for sample in channel) >= 32767:
        failures.append("rapid harmonic changes saturated PCM")


def check_harmonic_pitch_change(
    failures: List[str], csound: Path, module: Path, csd: Path,
) -> None:
    with tempfile.TemporaryDirectory(prefix="hlolli-harmonic-pitch-") as folder:
        result = run_case(
            failures, "held fourth-harmonic pitch change",
            csound, module, csd,
            {"TEST_CASE": 10, "TEST_END": 0.225},
            (1, 2, 3, 4), (1, 2, 3, 4), (1, 2, 3, 4),
            output=Path(folder) / "pitch-change.wav")
    if any(tag not in result[0] or tag not in result[1]
           for tag in range(1, 5)) or result[4] is None:
        return

    for tag in range(1, 5):
        harmonic = result[0][tag]
        wave_state = result[1][tag]
        label = "fourth-harmonic pitch snapshot {}".format(tag)
        check_harmonic_common(failures, label, harmonic)
        check_wave_common(failures, label, wave_state)
        for field, wanted in (
            ("requested_order", 4.0),
            ("active_order", 4.0),
            ("filter_order", 4.0),
            ("valid", 1.0),
        ):
            if value(harmonic, HARMONIC_FIELDS, field) != wanted:
                failures.append("{} had the wrong {}".format(label, field))
        if value(harmonic, HARMONIC_FIELDS, "touch_target") < 0.9:
            failures.append("{} lifted its harmonic touch".format(label))
        if value(harmonic, HARMONIC_FIELDS, "touch_pressure") < 0.85:
            failures.append("{} lost harmonic pressure".format(label))
        if value(wave_state, WAVE_FIELDS, "excitation_count") != 1.0:
            failures.append("{} retriggered the rail".format(label))

    first = result[0][1]
    if value(first, HARMONIC_FIELDS, "natural") != 1.0:
        failures.append("fourth-harmonic pitch change did not start natural")
    for tag in (2, 3, 4):
        state = result[0][tag]
        if value(state, HARMONIC_FIELDS, "natural") != 0.0:
            failures.append("pitch snapshot {} did not become artificial".format(tag))
        for field, wanted in (
            ("sounding_frequency", 1760.0),
            ("fundamental_frequency", 440.0),
        ):
            if not close(value(state, HARMONIC_FIELDS, field), wanted, 2.0e-9):
                failures.append("pitch snapshot {} missed {}".format(tag, field))

    periods = [
        value(result[0][tag], HARMONIC_FIELDS, "touch_period")
        for tag in range(1, 5)
    ]
    old_period = SAMPLE_RATE / (4.0 * OPEN_FREQUENCIES[0])
    new_period = SAMPLE_RATE / 1760.0
    if not close(periods[0], old_period, 2.0e-9):
        failures.append("fourth-harmonic pitch change began with the wrong period")
    if not periods[0] > periods[1] > periods[2] >= new_period - 1.0e-9:
        failures.append(
            "fourth-harmonic period did not follow its rail smoothly: {}".
            format(periods))
    if not close(periods[3], new_period, 2.0e-9):
        failures.append("fourth-harmonic period did not reach its new pitch")

    energies = [
        value(result[1][tag], WAVE_FIELDS, "toward_nut_energy") +
        value(result[1][tag], WAVE_FIELDS, "toward_bridge_energy")
        for tag in range(1, 5)
    ]
    if min(energies) <= 0.0:
        failures.append("fourth-harmonic pitch change lost its rail energy")
    elif min(energies[1:]) < 1.0e-3 * energies[0]:
        failures.append(
            "fourth-harmonic pitch change collapsed rail energy: {}".
            format(energies))

    channels = result[4][1]
    samples = stereo_window(channels, 0.150, 0.190)
    selected = partial_power(samples, 1760.0)
    neighbors = [partial_power(samples, frequency) for frequency in (1320.0, 2200.0)]
    if rms(samples) < 2.0 or selected <= 0.0 or selected < 0.5 * max(neighbors):
        failures.append("moved fourth harmonic did not reach its sounding mode")
    measured, periodicity = period_metrics(samples, 1760.0)
    cents = 1200.0 * math.log2(measured / 1760.0)
    if abs(cents) > 80.0 or periodicity < 0.02:
        failures.append(
            "moved fourth harmonic missed by {:.9g} cents at correlation {:.9g}".
            format(cents, periodicity))
    whole = stereo_window(channels, 0.0, 0.22)
    if not transition_step_ok(whole, 0.096):
        failures.append("held fourth-harmonic pitch change clicked")


def check_exact_pair(
    failures: List[str],
    label: str,
    case: int,
    split_time: float,
    csound: Path,
    module: Path,
    csd: Path,
    folder: Path,
) -> None:
    common = {
        "TEST_CASE": case, "TEST_ORDER": 4, "TEST_FREQUENCY": 1760,
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
    for name, index in (("harmonic", 0), ("wave", 1), ("string", 2)):
        if 1 in reference[index] and 1 in split[index]:
            left = reference[index][1]
            right = split[index][1]
            same = left == right
            if name == "string":
                same = all(close(a, b, 2.0e-12) for a, b in zip(left, right))
            if not same:
                failures.append("{} changed {} state".format(label, name))
    if 1 in split[1]:
        check_wave_common(failures, label, split[1][1])
        if value(split[1][1], WAVE_FIELDS, "excitation_count") != 1.0:
            failures.append("{} added an attack".format(label))


def check_handoffs(
    failures: List[str], csound: Path, module: Path, csd: Path,
) -> None:
    with tempfile.TemporaryDirectory(prefix="hlolli-harmonic-handoff-") as folder:
        temporary = Path(folder)
        check_exact_pair(
            failures, "harmonic block handoff", 3, 0.016,
            csound, module, csd, temporary)
        check_exact_pair(
            failures, "harmonic mid-block handoff", 3, 0.016125,
            csound, module, csd, temporary)
        check_exact_pair(
            failures, "normal-to-harmonic handoff", 4, 0.016,
            csound, module, csd, temporary)


def check_invalid_and_choice(
    failures: List[str], csound: Path, module: Path, csd: Path,
) -> None:
    sounding = 1318.51022765148
    with tempfile.TemporaryDirectory(prefix="hlolli-harmonic-invalid-") as folder:
        temporary = Path(folder)
        baseline = run_case(
            failures, "normal E-string baseline", csound, module, csd,
            {"TEST_CASE": 5, "TEST_ORDER": 0, "TEST_STRING": 4,
             "TEST_FREQUENCY": "{:.17g}".format(sounding)},
            (1,), (1,), (1,), output=temporary / "baseline.wav")
        for index, order in enumerate((-1, 1, 1.5, 9)):
            label = "invalid harmonic order {}".format(order)
            result = run_case(
                failures, label, csound, module, csd,
                {"TEST_CASE": 5, "TEST_ORDER": order, "TEST_STRING": 4,
                 "TEST_FREQUENCY": "{:.17g}".format(sounding)},
                (1,), (1,), (1,), output=temporary / "invalid-{}.wav".format(index))
            if 1 not in result[0] or 1 not in result[1] or result[4] is None:
                continue
            check_harmonic_common(failures, label, result[0][1])
            check_wave_common(failures, label, result[1][1])
            if value(
                    result[0][1], HARMONIC_FIELDS,
                    "requested_order") != float(order):
                failures.append("{} lost its raw request".format(label))
            for field in ("active_order", "filter_order", "valid", "natural",
                          "touch_target", "touch_pressure"):
                if value(result[0][1], HARMONIC_FIELDS, field) != 0.0:
                    failures.append("{} kept nonzero {}".format(label, field))
            if value(result[0][1], HARMONIC_FIELDS, "rejections") < 1.0:
                failures.append("{} was not counted as rejected".format(label))
            if baseline[4] and result[4][0] != baseline[4][0]:
                failures.append("{} changed normal-stopping PCM".format(label))

        unsafe = run_case(
            failures, "unsafe E-string fourth harmonic", csound, module, csd,
            {"TEST_CASE": 5, "TEST_ORDER": 4, "TEST_STRING": 4,
             "TEST_FREQUENCY": "{:.17g}".format(sounding)},
            (1,), (1,), (1,), output=temporary / "unsafe.wav")
        if 1 in unsafe[0] and 1 in unsafe[1] and unsafe[4]:
            state = unsafe[0][1]
            check_harmonic_common(failures, "unsafe E-string fourth harmonic", state)
            check_wave_common(failures, "unsafe E-string fourth harmonic", unsafe[1][1])
            if value(state, HARMONIC_FIELDS, "requested_order") != 4.0:
                failures.append("unsafe harmonic lost its requested order")
            for field in ("active_order", "filter_order", "valid", "natural",
                          "touch_target", "touch_pressure"):
                if value(state, HARMONIC_FIELDS, field) != 0.0:
                    failures.append("unsafe harmonic kept nonzero {}".format(field))
            if value(state, HARMONIC_FIELDS, "rejections") < 1.0:
                failures.append("unsafe harmonic was not rejected")
            if not close(
                    value(unsafe[1][1], WAVE_FIELDS, "target_frequency"),
                    sounding, 2.0e-9):
                failures.append("unsafe harmonic did not fall back to sounding pitch")
            if baseline[4] and unsafe[4][0] != baseline[4][0]:
                failures.append("unsafe harmonic changed normal-stopping PCM")

        automatic = run_case(
            failures, "automatic artificial fourth harmonic", csound, module, csd,
            {"TEST_CASE": 8, "TEST_ORDER": 4,
             "TEST_FREQUENCY": "{:.17g}".format(sounding)},
            (1, 2, 3, 4), (1, 2, 3, 4), (1, 2, 3, 4))
        if all(tag in automatic[0] and tag in automatic[2] for tag in range(1, 5)):
            active = [
                tag for tag in range(1, 5)
                if value(automatic[2][tag], STRING_FIELDS, "owner") == 1.0
            ]
            if active != [2]:
                failures.append(
                    "automatic fourth harmonic chose strings {}, wanted D".format(active))
            else:
                state = automatic[0][2]
                if (value(state, HARMONIC_FIELDS, "active_order") != 4.0 or
                        value(state, HARMONIC_FIELDS, "valid") != 1.0):
                    failures.append("automatic fourth harmonic was not active")

        first_k = run_case(
            failures, "first-pass k-rate fourth harmonic", csound, module, csd,
            {"TEST_CASE": 11},
            (1, 2, 3, 4), (1, 2, 3, 4), (1, 2, 3, 4))
        if all(tag in first_k[0] and tag in first_k[2] for tag in range(1, 5)):
            active = [
                tag for tag in range(1, 5)
                if value(first_k[2][tag], STRING_FIELDS, "owner") == 1.0
            ]
            if active != [3]:
                failures.append(
                    "first-pass fourth harmonic chose {}, wanted A".format(active))
            else:
                state = first_k[0][3]
                if (value(state, HARMONIC_FIELDS, "active_order") != 4.0 or
                        value(state, HARMONIC_FIELDS, "valid") != 1.0 or
                        not close(value(
                            state, HARMONIC_FIELDS,
                            "fundamental_frequency"), 440.0, 2.0e-9)):
                    failures.append(
                        "first-pass fourth harmonic did not bind to 440 Hz on A")

        up = OPEN_FREQUENCIES[0] * 8.0 * math.pow(2.0, 2.0 / 1200.0)
        boundary = run_case(
            failures, "above-natural boundary", csound, module, csd,
            {"TEST_CASE": 1, "TEST_ORDER": 8,
             "TEST_FREQUENCY": "{:.17g}".format(up)},
            (1,), (1,), (1,))
        if 1 in boundary[0]:
            state = boundary[0][1]
            if (value(state, HARMONIC_FIELDS, "valid") != 1.0 or
                    value(state, HARMONIC_FIELDS, "natural") != 0.0):
                failures.append("above-natural boundary did not become artificial")

        low_baseline = run_case(
            failures, "automatic low normal baseline", csound, module, csd,
            {"TEST_CASE": 8, "TEST_ORDER": 0, "TEST_FREQUENCY": 1000},
            (1, 2, 3, 4), (1, 2, 3, 4), (1, 2, 3, 4),
            output=temporary / "auto-low-baseline.wav")
        low = run_case(
            failures, "automatic harmonic below G", csound, module, csd,
            {"TEST_CASE": 8, "TEST_ORDER": 8, "TEST_FREQUENCY": 1000},
            (1, 2, 3, 4), (1, 2, 3, 4), (1, 2, 3, 4),
            output=temporary / "auto-low.wav")
        if all(tag in low[0] and tag in low[2] for tag in range(1, 5)):
            active = [
                tag for tag in range(1, 5)
                if value(low[2][tag], STRING_FIELDS, "owner") == 1.0
            ]
            if active != [4]:
                failures.append(
                    "rejected automatic harmonic chose {}, wanted E".format(active))
            else:
                state = low[0][4]
                if value(state, HARMONIC_FIELDS, "requested_order") != 8.0:
                    failures.append("rejected automatic harmonic lost its request")
                for field in ("active_order", "filter_order", "valid", "natural",
                              "touch_target", "touch_pressure"):
                    if value(state, HARMONIC_FIELDS, field) != 0.0:
                        failures.append(
                            "rejected automatic harmonic kept nonzero {}".
                            format(field))
                if value(state, HARMONIC_FIELDS, "rejections") < 1.0:
                    failures.append("automatic harmonic below G was not rejected")
        if low_baseline[4] and low[4] and low_baseline[4][0] != low[4][0]:
            failures.append("automatic harmonic below G changed fallback PCM")


def check_four_strings_and_body(
    failures: List[str], csound: Path, module: Path, csd: Path,
) -> None:
    with tempfile.TemporaryDirectory(prefix="hlolli-harmonic-four-") as folder:
        result = run_case(
            failures, "four harmonic strings", csound, module, csd,
            {"TEST_CASE": 6}, (1, 2, 3, 4), (1, 2, 3, 4),
            (1, 2, 3, 4), (1,), output=Path(folder) / "four.wav")
    if any(tag not in result[0] or tag not in result[1]
           for tag in range(1, 5)) or 1 not in result[3] or result[4] is None:
        return
    signatures = []
    for tag, order in enumerate((2, 3, 4, 5), 1):
        harmonic = result[0][tag]
        wave_state = result[1][tag]
        check_harmonic_common(failures, "four-string harmonic {}".format(tag), harmonic)
        check_wave_common(failures, "four-string wave {}".format(tag), wave_state)
        if (value(harmonic, HARMONIC_FIELDS, "active_order") != float(order) or
                value(harmonic, HARMONIC_FIELDS, "natural") != 1.0):
            failures.append("four-string harmonic {} had the wrong mode".format(tag))
        signatures.append((
            value(wave_state, WAVE_FIELDS, "toward_nut_signature"),
            value(wave_state, WAVE_FIELDS, "toward_bridge_signature"),
        ))
    if len(set(signatures)) != 4:
        failures.append("four harmonic strings shared rail state")
    body = result[3][1]
    if not all(math.isfinite(item) for item in body) or value(
            body, BODY_FIELDS, "finite") != 1.0:
        failures.append("harmonic body reported invalid state")
    for lane in range(1, 5):
        if value(body, BODY_FIELDS, "send_energy_{}".format(lane)) <= 0.0:
            failures.append("body lane {} received no harmonic energy".format(lane))
    for field in ("drive_energy", "output_energy_left", "output_energy_right"):
        if value(body, BODY_FIELDS, field) <= 0.0:
            failures.append("harmonic body had no {}".format(field))
    for field in ("reset_count", "clip_count"):
        if value(body, BODY_FIELDS, field) != 0.0:
            failures.append("harmonic body had nonzero {}".format(field))
    frames = result[4][0]
    if not frames.strip(b"\x00") or max(abs(sample) for channel in result[4][1]
                                        for sample in channel) >= 32767:
        failures.append("four harmonic strings were silent or saturated")


def check_stress(
    failures: List[str], csound: Path, module: Path, csd: Path,
) -> None:
    with tempfile.TemporaryDirectory(prefix="hlolli-harmonic-stress-") as folder:
        result = run_case(
            failures, "harmonic stress", csound, module, csd,
            {"TEST_CASE": 7, "TEST_END": 10.01},
            (1, 2, 3, 4), (1, 2, 3, 4), (1, 2, 3, 4), (1,),
            output=Path(folder) / "stress.wav")
    if any(tag not in result[0] or tag not in result[1]
           for tag in range(1, 5)) or 1 not in result[3] or result[4] is None:
        return
    for tag in range(1, 5):
        harmonic = result[0][tag]
        wave_state = result[1][tag]
        check_harmonic_common(failures, "harmonic stress {}".format(tag), harmonic)
        check_wave_common(failures, "harmonic stress {}".format(tag), wave_state)
        if value(harmonic, HARMONIC_FIELDS, "valid") != 1.0:
            failures.append("harmonic stress {} ended invalid".format(tag))
        if value(harmonic, HARMONIC_FIELDS, "filter_order") != value(
                harmonic, HARMONIC_FIELDS, "active_order"):
            failures.append("harmonic stress {} left an old projection".format(tag))
        if (value(harmonic, HARMONIC_FIELDS, "touch_target") < 0.9 or
                value(harmonic, HARMONIC_FIELDS, "touch_pressure") < 0.85):
            failures.append("harmonic stress {} ended with its touch lifted".format(tag))
        if value(harmonic, HARMONIC_FIELDS, "transitions") < 2.0:
            failures.append("harmonic stress {} made too few transitions".format(tag))
        if value(harmonic, HARMONIC_FIELDS, "touch_samples") <= 0.0:
            failures.append("harmonic stress {} made no touch samples".format(tag))
        if value(wave_state, WAVE_FIELDS, "wave_samples") < 479000.0:
            failures.append("harmonic stress {} skipped rail samples".format(tag))
    body = result[3][1]
    if (not all(math.isfinite(item) for item in body) or
            value(body, BODY_FIELDS, "finite") != 1.0 or
            value(body, BODY_FIELDS, "reset_count") != 0.0 or
            value(body, BODY_FIELDS, "clip_count") != 0.0):
        failures.append("harmonic stress body left finite bounds")
    peak = max(abs(sample) for channel in result[4][1] for sample in channel)
    if peak == 0 or peak >= 32767:
        failures.append("harmonic stress PCM was silent or saturated")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--csound", required=True, type=Path)
    parser.add_argument("--module", required=True, type=Path)
    parser.add_argument("--csd", required=True, type=Path)
    arguments = parser.parse_args()
    failures: List[str] = []

    check_orders(failures, arguments.csound, arguments.module, arguments.csd)
    check_pressure_path(failures, arguments.csound, arguments.module, arguments.csd)
    check_rapid_order_changes(
        failures, arguments.csound, arguments.module, arguments.csd)
    check_harmonic_pitch_change(
        failures, arguments.csound, arguments.module, arguments.csd)
    check_handoffs(failures, arguments.csound, arguments.module, arguments.csd)
    check_invalid_and_choice(
        failures, arguments.csound, arguments.module, arguments.csd)
    check_four_strings_and_body(
        failures, arguments.csound, arguments.module, arguments.csd)
    check_stress(failures, arguments.csound, arguments.module, arguments.csd)

    if failures:
        for failure in failures:
            print("FAIL: {}".format(failure), file=sys.stderr)
        return 1
    print("natural and artificial harmonic checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
