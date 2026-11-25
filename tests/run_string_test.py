#!/usr/bin/env python3
"""Check tuning, phase retention, decay, range, and string isolation."""

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


WaveState = Tuple[float, ...]

SAMPLE_RATE = 48000.0
WAVE_LIMIT = 4.0
WAVE_FIELDS = (
    "capacity",
    "read_delay",
    "target_delay",
    "target_frequency",
    "loop_phase_samples",
    "toward_nut_energy",
    "toward_bridge_energy",
    "toward_nut_signature",
    "toward_bridge_signature",
    "nut_pole",
    "nut_gain",
    "nut_state",
    "bridge_pole",
    "bridge_gain",
    "bridge_state",
    "write_index",
    "wave_samples",
    "excitation_count",
    "clear_count",
    "reset_count",
    "clip_count",
    "bridge_dynamic_input",
    "bridge_dynamic_output",
    "last_bridge_output",
    "finite",
)
FIELD = {name: index for index, name in enumerate(WAVE_FIELDS)}


def run_csound(
    csound: Path,
    module: Path,
    csd: Path,
    definitions: Mapping[str, object],
    timeout: int = 20,
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
        "-n",
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


def read_wave_states(output: str) -> Dict[int, WaveState]:
    states: Dict[int, WaveState] = {}
    for line in output.splitlines():
        start = line.find("WG_WAVE ")
        if start < 0:
            continue
        words = line[start:].split()
        if len(words) < len(WAVE_FIELDS) + 2:
            continue
        tag = int(float(words[1]))
        states[tag] = tuple(
            float(value) for value in words[2:2 + len(WAVE_FIELDS)])
    return states


def run_case(
    failures: List[str],
    label: str,
    csound: Path,
    module: Path,
    csd: Path,
    definitions: Mapping[str, object],
    tags: Sequence[int],
    timeout: int = 20,
) -> Dict[int, WaveState]:
    completed = run_csound(
        csound, module, csd, definitions, timeout=timeout)
    if completed.returncode != 0:
        failures.append(
            "{} failed with status {}:\n{}".format(
                label, completed.returncode, completed.stdout.rstrip()))
        return {}
    states = read_wave_states(completed.stdout)
    missing = [tag for tag in tags if tag not in states]
    if missing:
        failures.append(
            "{} printed no wave state for tags {}:\n{}".format(
                label, missing, completed.stdout.rstrip()))
    return states


def close(left: float, right: float, tolerance: float = 2.0e-12) -> bool:
    return math.isclose(left, right, rel_tol=tolerance, abs_tol=tolerance)


def value(state: WaveState, name: str) -> float:
    return state[FIELD[name]]


def energy(state: WaveState) -> float:
    return value(state, "toward_nut_energy") + value(
        state, "toward_bridge_energy")


def check_common(
    failures: List[str], label: str, state: WaveState,
) -> bool:
    if len(state) != len(WAVE_FIELDS):
        failures.append("{} returned the wrong state size".format(label))
        return False
    if not all(math.isfinite(item) for item in state):
        failures.append("{} returned a non-finite value".format(label))
        return False
    if value(state, "finite") != 1.0:
        failures.append("{} reported invalid waveguide state".format(label))
    capacity = value(state, "capacity")
    write_index = value(state, "write_index")
    read_delay = value(state, "read_delay")
    target_delay = value(state, "target_delay")
    if capacity < 1208.0 or capacity != math.floor(capacity):
        failures.append(
            "{} returned invalid capacity {:.17g}".format(label, capacity))
    if (write_index < 0.0 or write_index >= capacity or
            write_index != math.floor(write_index)):
        failures.append(
            "{} returned invalid write index {:.17g}".format(
                label, write_index))
    for name, delay in (("read", read_delay), ("target", target_delay)):
        if delay < 2.0 or delay > capacity - 2.0:
            failures.append(
                "{} {} delay {:.17g} exceeded its rail".format(
                    label, name, delay))
    for name in ("toward_nut_energy", "toward_bridge_energy"):
        if value(state, name) < 0.0:
            failures.append(
                "{} returned negative {}".format(label, name))
    for name in ("nut_pole", "bridge_pole"):
        coefficient = value(state, name)
        if coefficient < 0.0 or coefficient >= 1.0:
            failures.append(
                "{} returned unstable {} {:.17g}".format(
                    label, name, coefficient))
    for name in ("nut_gain", "bridge_gain"):
        coefficient = value(state, name)
        if coefficient <= 0.0 or coefficient >= 1.0:
            failures.append(
                "{} returned invalid {} {:.17g}".format(
                    label, name, coefficient))
    if abs(value(state, "last_bridge_output")) > WAVE_LIMIT + 1.0e-12:
        failures.append("{} exceeded the wave limit".format(label))
    if value(state, "clip_count") != 0.0:
        failures.append("{} used the safety clamp".format(label))
    return True


def check_tuning(
    failures: List[str], csound: Path, module: Path, csd: Path,
) -> None:
    frequencies = (
        20.0,
        195.997717990875,
        440.0,
        2793.82585146403,
        5000.0,
    )
    for frequency in frequencies:
        label = "{:.9g} Hz tuning".format(frequency)
        states = run_case(
            failures,
            label,
            csound,
            module,
            csd,
            {
                "TEST_CASE": 1,
                "TEST_FREQUENCY": "{:.17g}".format(frequency),
                "TEST_DURATION": 0.08,
                "TEST_END": 0.09,
            },
            (1,),
        )
        if 1 not in states:
            continue
        state = states[1]
        if not check_common(failures, label, state):
            continue
        target_frequency = value(state, "target_frequency")
        loop_phase = value(state, "loop_phase_samples")
        if not close(target_frequency, frequency, 2.0e-11):
            failures.append(
                "{} kept target {:.17g}".format(label, target_frequency))
        if not loop_phase > 0.0:
            failures.append("{} returned no loop phase".format(label))
        else:
            measured_frequency = SAMPLE_RATE / loop_phase
            cents = 1200.0 * math.log2(measured_frequency / frequency)
            if abs(cents) > 0.01:
                failures.append(
                    "{} missed by {:.9g} cents".format(label, cents))
        if energy(state) <= 1.0e-15:
            failures.append("{} stored no excitation energy".format(label))
        checks = (
            ("wave samples", value(state, "wave_samples"), 3840.0),
            ("excitation count", value(state, "excitation_count"), 1.0),
            ("clear count", value(state, "clear_count"), 0.0),
            ("reset count", value(state, "reset_count"), 0.0),
        )
        for name, found, wanted in checks:
            if found != wanted:
                failures.append(
                    "{} {} was {:.17g}, wanted {:.17g}".format(
                        label, name, found, wanted))


def render_audio(
    csound: Path, module: Path, csd: Path, frequency: float,
    string: int, duration: float, output: Path, test_case: int = 1,
    bridge_scale: float = 1.0, position: float = 0.12,
) -> subprocess.CompletedProcess[str]:
    command = [
        str(csound),
        "--opcode-lib={}".format(module),
        "--sample-accurate",
        "--num-threads=1",
        "--omacro:TEST_CASE={}".format(test_case),
        "--omacro:TEST_FREQUENCY={:.17g}".format(frequency),
        "--omacro:TEST_STRING={}".format(string),
        "--omacro:TEST_DURATION={:.17g}".format(duration),
        "--omacro:TEST_END={:.17g}".format(duration + 0.01),
        "--omacro:TEST_BRIDGE_SCALE={:.17g}".format(bridge_scale),
        "--omacro:TEST_POSITION={:.17g}".format(position),
        "-W",
        "-s",
        "-o",
        str(output),
        "-d",
        "-m128",
        str(csd),
    ]
    return subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        timeout=20,
        check=False,
    )


def high_band_share(
    samples: Sequence[float], start: float, stop: float,
) -> float:
    pole = math.exp(-2.0 * math.pi * 3500.0 / SAMPLE_RATE)
    first = max(0, int(start * SAMPLE_RATE))
    last = min(len(samples), int(stop * SAMPLE_RATE))
    low = 0.0
    high_energy = 0.0
    full_energy = 0.0
    for index, sample in enumerate(samples):
        low = (1.0 - pole) * sample + pole * low
        if first <= index < last:
            high = sample - low
            high_energy += high * high
            full_energy += sample * sample
        if index >= last:
            break
    return high_energy / full_energy if full_energy > 0.0 else 0.0


def partial_decay(samples: Sequence[float], frequency: float) -> float:
    length = round(0.04 * SAMPLE_RATE)
    omega = 2.0 * math.pi * frequency / SAMPLE_RATE
    basis = [
        (0.5 - 0.5 * math.cos(2.0 * math.pi * index / (length - 1))) *
        complex(math.cos(index * omega), math.sin(index * omega))
        for index in range(length)
    ]

    def level(start: float) -> float:
        first = round(start * SAMPLE_RATE)
        return abs(sum(sample * weight for sample, weight in
                       zip(samples[first:first + length], basis)))

    early = level(0.020)
    return level(0.090) / early if early > 0.0 else 0.0


def cubic_delay_magnitude(delay: float, omega: float) -> float:
    whole = math.floor(delay)
    fraction = delay - whole
    if whole < 2.0:
        return math.sqrt(
            (1.0 - fraction) ** 2 + fraction ** 2 +
            2.0 * fraction * (1.0 - fraction) * math.cos(omega)
        )
    offset = 1.0 + fraction
    coefficients = (
        -(offset - 1.0) * (offset - 2.0) *
        (offset - 3.0) / 6.0,
        offset * (offset - 2.0) * (offset - 3.0) / 2.0,
        -offset * (offset - 1.0) * (offset - 3.0) / 2.0,
        offset * (offset - 1.0) * (offset - 2.0) / 6.0,
    )
    real = sum(
        coefficient * math.cos(omega * index)
        for index, coefficient in enumerate(coefficients)
    )
    imaginary = sum(
        coefficient * math.sin(omega * index)
        for index, coefficient in enumerate(coefficients)
    )
    return math.hypot(real, imaginary)


def estimate_period_frequency(
    samples: Sequence[float], sample_rate: float, wanted: float,
) -> float:
    if len(samples) < 3:
        raise ValueError("pitch window is too short")
    weighted = [
        sample * (0.5 - 0.5 * math.cos(
            2.0 * math.pi * index / (len(samples) - 1)))
        for index, sample in enumerate(samples)
    ]

    def score(frequency: float) -> float:
        angle = -2.0 * math.pi * frequency / sample_rate
        advance = complex(math.cos(angle), math.sin(angle))
        phase = 1.0 + 0.0j
        projection = 0.0 + 0.0j
        for sample in weighted:
            projection += sample * phase
            phase *= advance
        return abs(projection)

    span = 0.02 * wanted
    coarse_step = 2.0 * span / 160.0
    coarse = [
        wanted - span + coarse_step * index for index in range(161)
    ]
    center = max(coarse, key=score)
    fine_step = coarse_step / 50.0
    fine = [
        center - coarse_step + fine_step * index for index in range(101)
    ]
    return max(fine, key=score)


def check_rendered_tuning(
    failures: List[str], csound: Path, module: Path, csd: Path,
) -> None:
    cases = (
        (195.997717990875, 1, 0.55, 0.04, 0.42),
        (440.0, 3, 0.40, 0.02, 0.28),
        (2637.02045530296, 4, 0.25, 0.002, 0.03),
    )
    with tempfile.TemporaryDirectory(prefix="hlolli-wg-violin-") as folder:
        for index, (frequency, string, duration, start, end) in enumerate(cases):
            output = Path(folder) / "pitch-{}.wav".format(index)
            completed = render_audio(
                csound, module, csd, frequency, string, duration, output)
            label = "{:.9g} Hz rendered tuning".format(frequency)
            if completed.returncode != 0 or not output.exists():
                failures.append(
                    "{} failed:\n{}".format(
                        label, completed.stdout.rstrip()))
                continue
            with wave.open(str(output), "rb") as audio:
                if (audio.getframerate() != int(SAMPLE_RATE) or
                        audio.getnchannels() != 2 or
                        audio.getsampwidth() != 2):
                    failures.append("{} returned an unexpected WAV".format(label))
                    continue
                frames = audio.readframes(audio.getnframes())
            left = [
                pair[0] / 32768.0
                for pair in struct.iter_unpack("<hh", frames)
            ]
            window = left[
                int(start * SAMPLE_RATE):int(end * SAMPLE_RATE)]
            measured = estimate_period_frequency(
                window, SAMPLE_RATE, frequency)
            cents = 1200.0 * math.log2(measured / frequency)
            if abs(cents) > 2.0:
                failures.append(
                    "{} missed by {:.9g} cents".format(label, cents))


def check_intrinsic_loss_spectrum(
    failures: List[str], csound: Path, module: Path, csd: Path,
) -> None:
    cases = (
        ("G", 195.997717990875, 1),
        ("D", 293.664767917408, 2),
        ("A", 440.0, 3),
        ("E", 659.255113825740, 4),
    )
    with tempfile.TemporaryDirectory(
            prefix="hlolli-string-spectrum-") as folder:
        temporary = Path(folder)
        normal_a_frames = b""
        normal_a_share = 0.0
        normal_a_samples: list[float] = []
        for name, frequency, string in cases:
            output = temporary / "{}.wav".format(name)
            completed = render_audio(
                csound, module, csd, frequency, string, 0.20, output,
                test_case=11)
            label = "{} intrinsic string spectrum".format(name)
            if completed.returncode != 0 or not output.exists():
                failures.append(
                    "{} failed:\n{}".format(label, completed.stdout.rstrip()))
                continue
            states = read_wave_states(completed.stdout)
            if 1 not in states or not check_common(failures, label, states[1]):
                continue
            state = states[1]
            if value(state, "excitation_count") != 1.0:
                failures.append("{} did not use one fixed impulse".format(label))
            endpoint = []
            total = []
            delay = value(state, "target_delay")
            bridge_delay = 0.12 * delay
            nut_delay = delay - bridge_delay
            for harmonic in (1.0, 2.0, 4.0, min(8.0, 8000.0 / frequency)):
                omega = 2.0 * math.pi * harmonic * frequency / SAMPLE_RATE
                endpoint_gain = (
                    one_pole_magnitude(
                        value(state, "nut_pole"),
                        value(state, "nut_gain"), omega) *
                    one_pole_magnitude(
                        value(state, "bridge_pole"),
                        value(state, "bridge_gain"), omega))
                interpolation_gain = 1.0
                for branch in (bridge_delay, nut_delay):
                    interpolation_gain *= cubic_delay_magnitude(
                        branch, omega)
                endpoint.append(endpoint_gain)
                total.append(endpoint_gain * interpolation_gain)
            if not all(
                    0.0 < later < earlier < 1.0
                    for earlier, later in zip(endpoint, endpoint[1:])):
                failures.append(
                    "{} endpoint loss was not contractive and darker at "
                    "higher harmonics: {}".format(label, endpoint))
            if not all(0.0 < item < 1.0 for item in total):
                failures.append(
                    "{} endpoint and interpolation loop was not "
                    "contractive: {}".format(label, total))
            loop_gain = value(state, "nut_gain") * value(
                state, "bridge_gain")
            if 0.0 < loop_gain < 1.0:
                loss_seconds = -1.0 / (frequency * math.log(loop_gain))
                maximum_loop_gain = math.exp(
                    -1.0 / (5000.0 * loss_seconds))
                for step in range(1, 257):
                    omega = math.pi * step / 256.0
                    maximum_delay_gain = max(
                        cubic_delay_magnitude(
                            2.0 + index / 64.0, omega)
                        for index in range(65)
                    )
                    endpoint_gain = maximum_loop_gain
                    for pole_name in ("nut_pole", "bridge_pole"):
                        pole = value(state, pole_name)
                        endpoint_gain *= (1.0 - pole) / math.sqrt(
                            1.0 + pole * pole -
                            2.0 * pole * math.cos(omega))
                    if endpoint_gain * maximum_delay_gain ** 2 >= 1.0:
                        failures.append(
                            "{} cubic delay could overpower endpoint loss "
                            "at {:.9g} radians".format(label, omega))
                        break
            with wave.open(str(output), "rb") as audio:
                if (audio.getframerate() != int(SAMPLE_RATE) or
                        audio.getnchannels() != 2 or
                        audio.getsampwidth() != 2):
                    failures.append("{} returned an unexpected WAV".format(label))
                    continue
                frames = audio.readframes(audio.getnframes())
            samples = [
                (left + right) / 65536.0
                for left, right in struct.iter_unpack("<hh", frames)
            ]
            early = high_band_share(samples, 0.005, 0.030)
            late = high_band_share(samples, 0.080, 0.160)
            if early <= 0.0 or late >= 0.5 * early:
                failures.append(
                    "{} did not darken its fixed impulse: {:.9g} -> "
                    "{:.9g}".format(label, early, late))
            if name == "A":
                normal_a_frames = frames
                normal_a_share = early
                normal_a_samples = samples

        if not normal_a_frames:
            return

        def render_a(
            tag: str, scale: float, position: float = 0.12,
        ) -> Tuple[bytes, List[float]]:
            output = temporary / "A-{}.wav".format(tag)
            completed = render_audio(
                csound, module, csd, 440.0, 3, 0.20, output,
                test_case=11, bridge_scale=scale, position=position)
            label = "A intrinsic string {}".format(tag)
            if completed.returncode != 0 or not output.exists():
                failures.append(
                    "{} failed:\n{}".format(label, completed.stdout.rstrip()))
                return b"", []
            with wave.open(str(output), "rb") as audio:
                if (audio.getframerate() != int(SAMPLE_RATE) or
                        audio.getnchannels() != 2 or
                        audio.getsampwidth() != 2):
                    failures.append("{} returned an unexpected WAV".format(label))
                    return b"", []
                frames = audio.readframes(audio.getnframes())
            samples = [
                (left + right) / 65536.0
                for left, right in struct.iter_unpack("<hh", frames)
            ]
            return frames, samples

        dark_frames, dark_samples = render_a("dark", 0.5)
        bright_frames, bright_samples = render_a("bright", 2.0)
        repeat_frames, _ = render_a("repeat", 1.0)
        if dark_frames and bright_frames:
            dark_share = high_band_share(dark_samples, 0.005, 0.030)
            bright_share = high_band_share(bright_samples, 0.005, 0.030)
            if not 0.0 < dark_share < normal_a_share < bright_share:
                failures.append(
                    "A bridge cutoff did not order dark, normal, bright: "
                    "{:.9g}, {:.9g}, {:.9g}".format(
                        dark_share, normal_a_share, bright_share))
        if repeat_frames and repeat_frames != normal_a_frames:
            failures.append("A intrinsic string repeat changed PCM")

        position_renders = [(0.12, normal_a_samples)]
        for tag, position in (("near", 0.05), ("far", 0.24),
                              ("farthest", 0.40)):
            _, samples = render_a(tag, 1.0, position)
            position_renders.append((position, samples))
        # Compare the same mode over time so the bridge tap's gain cancels.
        for frequency in (880.0, 1320.0):
            decays = [(position, partial_decay(samples, frequency))
                      for position, samples in position_renders]
            values = [decay for _, decay in decays]
            if min(values) <= 0.0 or max(values) > 1.05 * min(values):
                failures.append(
                    f"A passive {frequency:g} Hz decay changed with the "
                    f"inactive junction: {decays}")


def check_retune(
    failures: List[str], csound: Path, module: Path, csd: Path,
) -> None:
    states = run_case(
        failures,
        "retune",
        csound,
        module,
        csd,
        {"TEST_CASE": 2, "TEST_END": 0.052},
        (1, 2, 3, 4),
    )
    if any(tag not in states for tag in (1, 2, 3, 4)):
        return
    for tag, state in states.items():
        check_common(failures, "retune snapshot {}".format(tag), state)
        if value(state, "excitation_count") != 1.0:
            failures.append(
                "retune snapshot {} retriggered the exciter".format(tag))
        if value(state, "clear_count") != 0.0:
            failures.append(
                "retune snapshot {} cleared the rail".format(tag))
        if value(state, "reset_count") != 0.0:
            failures.append(
                "retune snapshot {} reset after invalid state".format(tag))
        if energy(state) <= 1.0e-15:
            failures.append(
                "retune snapshot {} lost the rail".format(tag))

    before = states[1]
    after = [states[tag] for tag in (2, 3, 4)]
    if not close(value(before, "target_frequency"), 220.0, 2.0e-11):
        failures.append("retune did not begin at 220 Hz")
    for tag, state in zip((2, 3, 4), after):
        if not close(value(state, "target_frequency"), 880.0, 2.0e-11):
            failures.append(
                "retune snapshot {} did not target 880 Hz".format(tag))

    old_delay = value(before, "target_delay")
    new_delay = value(after[-1], "target_delay")
    low, high = sorted((old_delay, new_delay))
    errors: List[float] = []
    for tag, state in zip((2, 3, 4), after):
        delay = value(state, "read_delay")
        if delay < low - 1.0e-10 or delay > high + 1.0e-10:
            failures.append(
                "retune snapshot {} jumped outside its endpoints".format(tag))
        errors.append(abs(delay - new_delay))
    if any(
        later > earlier + 1.0e-10
        for earlier, later in zip(errors, errors[1:])
    ):
        failures.append("retune delay did not approach its target")
    if value(after[-1], "wave_samples") != 2304.0:
        failures.append("retune processed the wrong sample count")


def compare_wave_states(
    failures: List[str], label: str, reference: WaveState, actual: WaveState,
) -> None:
    for name, wanted, found in zip(WAVE_FIELDS, reference, actual):
        if not close(wanted, found):
            failures.append(
                "{} changed {}: {:.17g} != {:.17g}".format(
                    label, name, found, wanted))


def check_phase_equivalence(
    failures: List[str], csound: Path, module: Path, csd: Path,
) -> None:
    common = {"TEST_CASE": 7, "TEST_END": 0.052}
    reference_states = run_case(
        failures,
        "continuous wave reference",
        csound,
        module,
        csd,
        common,
        (1,),
    )
    if 1 not in reference_states:
        return
    reference = reference_states[1]
    check_common(failures, "continuous wave reference", reference)
    for name, split_time in (("block", 0.016), ("mid-block", 0.016125)):
        definitions = dict(common)
        definitions.update({
            "TEST_SPLIT": 1,
            "TEST_SPLIT_TIME": split_time,
        })
        states = run_case(
            failures,
            "{} wave handoff".format(name),
            csound,
            module,
            csd,
            definitions,
            (1,),
        )
        if 1 not in states:
            continue
        check_common(failures, "{} wave handoff".format(name), states[1])
        compare_wave_states(
            failures,
            "{} wave handoff".format(name),
            reference,
            states[1],
        )

    for string in (1, 3):
        label = "string {}".format(string)
        gap_reference_states = run_case(
            failures,
            "{} continuous release reference".format(label),
            csound,
            module,
            csd,
            {"TEST_CASE": 8, "TEST_GAP": 0, "TEST_STRING": string,
             "TEST_END": 0.052},
            (1,),
        )
        gap_states = run_case(
            failures,
            "{} owner gap".format(label),
            csound,
            module,
            csd,
            {"TEST_CASE": 8, "TEST_GAP": 1, "TEST_STRING": string,
             "TEST_END": 0.052},
            (1,),
        )
        if 1 in gap_reference_states and 1 in gap_states:
            check_common(
                failures, "{} continuous release reference".format(label),
                gap_reference_states[1])
            check_common(
                failures, "{} owner gap".format(label), gap_states[1])
            compare_wave_states(
                failures,
                "{} owner gap".format(label),
                gap_reference_states[1],
                gap_states[1],
            )


def one_pole_magnitude(pole: float, gain: float, omega: float) -> float:
    denominator = math.sqrt(
        1.0 + pole * pole - 2.0 * pole * math.cos(omega))
    return gain * (1.0 - pole) / denominator


def check_decay(
    failures: List[str], csound: Path, module: Path, csd: Path,
) -> None:
    states = run_case(
        failures,
        "decay",
        csound,
        module,
        csd,
        {"TEST_CASE": 3, "TEST_END": 1.028},
        (1, 2, 3, 4),
    )
    if any(tag not in states for tag in (1, 2, 3, 4)):
        return
    energies: List[float] = []
    for tag in (1, 2, 3, 4):
        state = states[tag]
        check_common(failures, "decay snapshot {}".format(tag), state)
        energies.append(energy(state))
        if value(state, "excitation_count") != 1.0:
            failures.append(
                "decay snapshot {} had the wrong excitation count".format(tag))
        if value(state, "clear_count") != 0.0:
            failures.append(
                "decay snapshot {} cleared before the gap limit".format(tag))
        if value(state, "reset_count") != 0.0:
            failures.append(
                "decay snapshot {} reset after invalid state".format(tag))
    if energies[0] <= 1.0e-15:
        failures.append("decay test stored no initial energy")
    if any(
        later > earlier * (1.0 + 1.0e-8) + 1.0e-15
        for earlier, later in zip(energies, energies[1:])
    ):
        failures.append(
            "decay energy was not monotone: {}".format(energies))
    if energies[-1] >= 0.05 * energies[0]:
        failures.append(
            "decay retained too much energy: {}".format(energies))

    state = states[4]
    nut_pole = value(state, "nut_pole")
    nut_gain = value(state, "nut_gain")
    bridge_pole = value(state, "bridge_pole")
    bridge_gain = value(state, "bridge_gain")
    magnitudes = []
    for frequency in (0.0, 500.0, 10000.0):
        omega = 2.0 * math.pi * frequency / SAMPLE_RATE
        magnitudes.append(
            one_pole_magnitude(nut_pole, nut_gain, omega) *
            one_pole_magnitude(bridge_pole, bridge_gain, omega))
    if not (magnitudes[2] < magnitudes[1] < magnitudes[0] < 1.0):
        failures.append(
            "reflection loss was not contractive and frequency dependent: "
            "{}".format(magnitudes))


def check_four_strings(
    failures: List[str], csound: Path, module: Path, csd: Path,
) -> None:
    frequencies = (
        195.997717990875,
        293.664767917408,
        440.0,
        659.25511382574,
    )
    states = run_case(
        failures,
        "four strings",
        csound,
        module,
        csd,
        {"TEST_CASE": 4, "TEST_END": 0.052},
        (1, 2, 3, 4),
    )
    if any(tag not in states for tag in (1, 2, 3, 4)):
        return
    target_delays = []
    for tag, frequency in enumerate(frequencies, 1):
        state = states[tag]
        label = "string {}".format(tag)
        check_common(failures, label, state)
        if not close(value(state, "target_frequency"), frequency, 2.0e-11):
            failures.append("{} kept the wrong pitch".format(label))
        loop_phase = value(state, "loop_phase_samples")
        if loop_phase <= 0.0:
            failures.append("{} returned no loop phase".format(label))
        else:
            cents = 1200.0 * math.log2(
                SAMPLE_RATE / loop_phase / frequency)
            if abs(cents) > 0.01:
                failures.append(
                    "{} analytic tuning missed by {:.9g} cents".format(
                        label, cents))
        if value(state, "wave_samples") != 2304.0:
            failures.append("{} processed the wrong sample count".format(label))
        if value(state, "excitation_count") != 1.0:
            failures.append("{} was not excited once".format(label))
        if value(state, "clear_count") != 0.0:
            failures.append("{} cleared its rail".format(label))
        if value(state, "reset_count") != 0.0:
            failures.append("{} reset after invalid state".format(label))
        if energy(state) <= 1.0e-15:
            failures.append("{} stored no wave energy".format(label))
        target_delays.append(value(state, "target_delay"))
    if any(
        later >= earlier
        for earlier, later in zip(target_delays, target_delays[1:])
    ):
        failures.append("open-string delays did not fall with pitch")

    isolated = run_case(
        failures,
        "string isolation",
        csound,
        module,
        csd,
        {"TEST_CASE": 5, "TEST_END": 0.020},
        (1, 2, 3, 4),
    )
    if any(tag not in isolated for tag in (1, 2, 3, 4)):
        return
    for tag in (1, 2, 3, 4):
        state = isolated[tag]
        check_common(failures, "isolated string {}".format(tag), state)
        if value(state, "wave_samples") != 768.0:
            failures.append(
                "isolated string {} processed the wrong sample count".format(tag))
        if tag == 2:
            if value(state, "excitation_count") != 1.0 or energy(state) <= 0.0:
                failures.append("isolated string 2 did not retain its seed")
        elif value(state, "excitation_count") != 0.0 or energy(state) != 0.0:
            failures.append(
                "isolated string {} received string 2 state".format(tag))


def check_long_run(
    failures: List[str], csound: Path, module: Path, csd: Path,
) -> None:
    states = run_case(
        failures,
        "long sweep",
        csound,
        module,
        csd,
        {"TEST_CASE": 6, "TEST_END": 30.005},
        (1, 2, 3, 4),
        timeout=60,
    )
    if any(tag not in states for tag in (1, 2, 3, 4)):
        return
    for tag in (1, 2, 3, 4):
        state = states[tag]
        label = "long sweep string {}".format(tag)
        check_common(failures, label, state)
        if value(state, "wave_samples") != 1440000.0:
            failures.append("{} processed the wrong sample count".format(label))
        if value(state, "excitation_count") != 1.0:
            failures.append("{} did not keep one passive seed".format(label))
        if value(state, "clear_count") != 0.0:
            failures.append("{} recovered from invalid state".format(label))
        if value(state, "reset_count") != 0.0:
            failures.append("{} reset after invalid state".format(label))
        if not 20.0 <= value(state, "target_frequency") <= 5000.0:
            failures.append("{} left the test pitch range".format(label))
        maximum_energy = 2.0 * WAVE_LIMIT ** 2
        if energy(state) > maximum_energy * (1.0 + 1.0e-12):
            failures.append("{} exceeded its energy bound".format(label))


def check_long_gap(
    failures: List[str], csound: Path, module: Path, csd: Path,
) -> None:
    states = run_case(
        failures,
        "long owner gap",
        csound,
        module,
        csd,
        {"TEST_CASE": 9, "TEST_END": 6.052},
        (1,),
    )
    if 1 not in states:
        return
    state = states[1]
    check_common(failures, "long owner gap", state)
    checks = (
        ("wave samples", value(state, "wave_samples"), 290304.0),
        ("excitation count", value(state, "excitation_count"), 1.0),
        ("clear count", value(state, "clear_count"), 1.0),
        ("reset count", value(state, "reset_count"), 0.0),
    )
    for name, found, wanted in checks:
        if found != wanted:
            failures.append(
                "long owner gap {} was {:.17g}, wanted {:.17g}".format(
                    name, found, wanted))
    if energy(state) != 0.0:
        failures.append("long owner gap kept audible rail energy")

    for string in (1, 3):
        label = "medium owner gap string {}".format(string)
        medium_states = run_case(
            failures,
            label,
            csound,
            module,
            csd,
            {"TEST_CASE": 10, "TEST_STRING": string, "TEST_END": 0.536},
            (1,),
        )
        if 1 not in medium_states:
            continue
        medium = medium_states[1]
        check_common(failures, label, medium)
        checks = (
            ("wave samples", value(medium, "wave_samples"), 25536.0),
            ("excitation count", value(medium, "excitation_count"), 1.0),
            ("clear count", value(medium, "clear_count"), 0.0),
            ("reset count", value(medium, "reset_count"), 0.0),
        )
        for name, found, wanted in checks:
            if found != wanted:
                failures.append(
                    "{} {} was {:.17g}, wanted {:.17g}".format(
                        label, name, found, wanted))
        if energy(medium) <= 0.0:
            failures.append("{} lost all rail state".format(label))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csound", required=True, type=Path)
    parser.add_argument("--module", required=True, type=Path)
    parser.add_argument("--csd", required=True, type=Path)
    arguments = parser.parse_args()

    failures: List[str] = []
    try:
        check_tuning(failures, arguments.csound, arguments.module, arguments.csd)
        check_rendered_tuning(
            failures, arguments.csound, arguments.module, arguments.csd)
        check_intrinsic_loss_spectrum(
            failures, arguments.csound, arguments.module, arguments.csd)
        check_retune(failures, arguments.csound, arguments.module, arguments.csd)
        check_phase_equivalence(
            failures, arguments.csound, arguments.module, arguments.csd)
        check_decay(failures, arguments.csound, arguments.module, arguments.csd)
        check_four_strings(
            failures, arguments.csound, arguments.module, arguments.csd)
        check_long_gap(
            failures, arguments.csound, arguments.module, arguments.csd)
        check_long_run(failures, arguments.csound, arguments.module, arguments.csd)
    except (OSError, subprocess.TimeoutExpired, ValueError,
            wave.Error) as error:
        print("string test failed: {}".format(error), file=sys.stderr)
        return 2

    if failures:
        for failure in failures:
            print("failure: {}".format(failure), file=sys.stderr)
        return 1
    print("violin string checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
