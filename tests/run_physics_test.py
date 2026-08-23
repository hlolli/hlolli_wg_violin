#!/usr/bin/env python3
"""Check bow mechanics contact memory, small mechanics, and bridge return."""

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
Channels = Tuple[List[int], List[int]]
Audio = Tuple[bytes, Channels]

SAMPLE_RATE = 48000
PHYSICS_FIELDS = (
    "contact_memory", "contact_memory_velocity", "contact_adhesion",
    "contact_steady_displacement", "contact_force", "contact_iterations",
    "contact_failures", "temperature", "thermal_scale", "thermal_work",
    "hair_displacement", "hair_velocity", "hair_effective_speed",
    "board_displacement", "board_compression", "board_force",
    "board_energy", "board_impacts", "noise_last", "noise_energy",
    "noise_peak", "noise_samples", "mechanical_events", "coupling_input",
    "coupling_energy", "coupling_peak", "coupling_samples",
    "coupling_source_mask", "recoveries", "second_polarization", "finite",
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
    timeout: int = 75,
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
        timeout=timeout,
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
            raise ValueError("unexpected physics-test WAV format")
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
    physics_tags: Sequence[int] = (),
    wave_tags: Sequence[int] = (),
    string_tags: Sequence[int] = (),
    output: Path | None = None,
    timeout: int = 75,
) -> Tuple[Dict[int, State], Dict[int, State], Dict[int, State], Audio | None]:
    completed = run_csound(
        csound, module, csd, definitions, output=output, timeout=timeout)
    if completed.returncode != 0:
        failures.append(
            "{} failed with status {}:\n{}".format(
                label, completed.returncode, completed.stdout.rstrip()))
        return {}, {}, {}, None
    first = read_tagged(completed.stdout, "WG_PHYSICS_A", 16)
    second = read_tagged(completed.stdout, "WG_PHYSICS_B", 15)
    physics = {
        tag: first[tag] + second[tag]
        for tag in first.keys() & second.keys()
    }
    waves = read_tagged(
        completed.stdout, "WG_PHYSICS_WAVE", len(WAVE_FIELDS))
    strings = read_tagged(
        completed.stdout, "WG_PHYSICS_STRING", len(STRING_FIELDS))
    missing = (
        [tag for tag in physics_tags if tag not in physics],
        [tag for tag in wave_tags if tag not in waves],
        [tag for tag in string_tags if tag not in strings],
    )
    if any(missing):
        failures.append(
            "{} missed physics {}, wave {}, or string {} tags:\n{}".format(
                label, *missing, completed.stdout.rstrip()))
    rendered = None
    if output is not None:
        if not output.exists():
            failures.append("{} produced no WAV".format(label))
        else:
            try:
                rendered = read_wav(output)
            except (ValueError, wave.Error) as error:
                failures.append("{}: {}".format(label, error))
    return physics, waves, strings, rendered


def check_physics_common(
    failures: List[str], label: str, state: State,
) -> bool:
    if len(state) != len(PHYSICS_FIELDS):
        failures.append("{} returned the wrong physics state size".format(label))
        return False
    if not all(math.isfinite(item) for item in state):
        failures.append("{} returned non-finite physics state".format(label))
        return False
    if value(state, PHYSICS_FIELDS, "finite") != 1.0:
        failures.append("{} reported invalid physics state".format(label))
    adhesion = value(state, PHYSICS_FIELDS, "contact_adhesion")
    steady = value(state, PHYSICS_FIELDS, "contact_steady_displacement")
    if not 0.0 <= adhesion <= 1.0:
        failures.append("{} returned invalid contact adhesion".format(label))
    if abs(value(state, PHYSICS_FIELDS, "contact_memory")) > 0.002000000001:
        failures.append("{} let contact memory leave its bound".format(label))
    if abs(steady) > 0.002000000001:
        failures.append("{} let steady displacement leave its bound".format(label))
    temperature = value(state, PHYSICS_FIELDS, "temperature")
    thermal_scale = value(state, PHYSICS_FIELDS, "thermal_scale")
    if not 0.0 <= temperature <= 1.0:
        failures.append("{} returned invalid temperature".format(label))
    if not 0.91 <= thermal_scale <= 1.0:
        failures.append("{} returned invalid thermal scale".format(label))
    if abs(value(
            state, PHYSICS_FIELDS, "hair_displacement")) > 0.001500000001:
        failures.append("{} let hair displacement leave its bound".format(label))
    if abs(value(state, PHYSICS_FIELDS, "hair_velocity")) > 0.120000000001:
        failures.append("{} let hair velocity leave its bound".format(label))
    if abs(value(
            state, PHYSICS_FIELDS, "board_displacement")) > 0.004000000001:
        failures.append("{} let board displacement leave its bound".format(label))
    for field in (
            "thermal_work", "board_compression", "board_energy",
            "noise_energy", "noise_peak", "coupling_energy",
            "coupling_peak"):
        if value(state, PHYSICS_FIELDS, field) < 0.0:
            failures.append("{} returned negative {}".format(label, field))
    if abs(value(state, PHYSICS_FIELDS, "noise_last")) > value(
            state, PHYSICS_FIELDS, "noise_peak") + 1.0e-12:
        failures.append("{} noise peak missed its last sample".format(label))
    for field in (
            "contact_iterations", "contact_failures", "board_impacts",
            "noise_samples", "mechanical_events", "coupling_samples",
            "coupling_source_mask", "recoveries"):
        found = value(state, PHYSICS_FIELDS, field)
        if found < 0.0 or found != math.floor(found):
            failures.append("{} returned invalid {}".format(label, field))
    source_mask = value(state, PHYSICS_FIELDS, "coupling_source_mask")
    if source_mask > 15.0:
        failures.append("{} returned an invalid coupling source mask".format(label))
    if value(state, PHYSICS_FIELDS, "second_polarization") != 0.0:
        failures.append("{} enabled the deferred second polarization".format(label))
    return True


def check_wave_common(failures: List[str], label: str, state: State) -> bool:
    if len(state) != len(WAVE_FIELDS):
        failures.append("{} returned the wrong wave state size".format(label))
        return False
    if not all(math.isfinite(item) for item in state):
        failures.append("{} returned non-finite wave state".format(label))
        return False
    if value(state, WAVE_FIELDS, "finite") != 1.0:
        failures.append("{} reported invalid wave state".format(label))
    for field in ("clear_count", "reset_count", "clip_count"):
        if value(state, WAVE_FIELDS, field) != 0.0:
            failures.append("{} had nonzero {}".format(label, field))
    return True


def mono(channels: Channels, start: float = 0.0, stop: float | None = None) -> List[float]:
    first = max(0, int(start * SAMPLE_RATE))
    last = len(channels[0]) if stop is None else min(
        len(channels[0]), int(stop * SAMPLE_RATE))
    return [
        0.5 * (channels[0][index] + channels[1][index])
        for index in range(first, last)
    ]


def rms(samples: Sequence[float]) -> float:
    if not samples:
        return 0.0
    return math.sqrt(sum(sample * sample for sample in samples) / len(samples))


def harmonic_powers(
    samples: Sequence[float], fundamental: float, count: int = 16,
) -> List[float]:
    if not samples:
        return [0.0] * count
    mean = sum(samples) / len(samples)
    result: List[float] = []
    for harmonic in range(1, count + 1):
        frequency = harmonic * fundamental
        if frequency >= 0.48 * SAMPLE_RATE:
            result.append(0.0)
            continue
        real = 0.0
        imaginary = 0.0
        for index, sample in enumerate(samples):
            window = 0.5 - 0.5 * math.cos(
                2.0 * math.pi * index / max(1, len(samples) - 1))
            angle = 2.0 * math.pi * frequency * index / SAMPLE_RATE
            centered = sample - mean
            real += window * centered * math.cos(angle)
            imaginary -= window * centered * math.sin(angle)
        result.append(real * real + imaginary * imaginary)
    return result


def spectral_distance(left: Sequence[float], right: Sequence[float]) -> float:
    left_total = sum(left)
    right_total = sum(right)
    if left_total <= 0.0 or right_total <= 0.0:
        return 0.0
    return sum(abs(a / left_total - b / right_total)
               for a, b in zip(left, right))


def difference_ratio(samples: Sequence[float]) -> float:
    energy = sum(sample * sample for sample in samples)
    if energy <= 0.0:
        return 0.0
    differences = [
        samples[index] - samples[index - 1]
        for index in range(1, len(samples))
    ]
    return sum(sample * sample for sample in differences) / energy


def transition_step_ok(samples: Sequence[float], boundary: float) -> bool:
    center = int(boundary * SAMPLE_RATE)
    first = max(1, center - 512)
    last = min(len(samples), center + 512)
    differences = [
        abs(samples[index] - samples[index - 1])
        for index in range(first, last)
    ]
    if not differences:
        return True
    before = differences[:max(1, min(400, center - first))]
    reference = sorted(before)[int(0.99 * (len(before) - 1))]
    boundary_step = max(
        abs(samples[index] - samples[index - 1])
        for index in range(max(1, center - 2), min(len(samples), center + 3))
    )
    return boundary_step <= max(1400.0, 14.0 * reference)


def check_pcm(failures: List[str], label: str, rendered: Audio) -> None:
    peak = max(abs(sample) for channel in rendered[1] for sample in channel)
    if peak >= 32767:
        failures.append("{} saturated PCM".format(label))


def check_contact_history(
    failures: List[str], csound: Path, module: Path, csd: Path,
) -> None:
    with tempfile.TemporaryDirectory(prefix="hlolli-physics-memory-") as folder:
        temporary = Path(folder)
        results = []
        for variant, name in enumerate(("forward", "reverse")):
            result = run_case(
                failures, name + " contact history", csound, module, csd,
                {"TEST_CASE": 1, "TEST_VARIANT": variant, "TEST_END": 0.48},
                (1, 2, 3, 4), (1, 2, 3, 4), (1, 2, 3, 4),
                output=temporary / (name + ".wav"))
            results.append(result)
            if any(tag not in result[0] or tag not in result[1]
                   for tag in range(1, 5)) or result[3] is None:
                continue
            for tag in range(1, 5):
                check_physics_common(
                    failures, "{} history {}".format(name, tag), result[0][tag])
                check_wave_common(
                    failures, "{} history {}".format(name, tag), result[1][tag])
            final = result[0][4]
            if value(final, PHYSICS_FIELDS, "contact_iterations") <= 0.0:
                failures.append("{} history did no contact work".format(name))
            if value(final, PHYSICS_FIELDS, "contact_failures") != 0.0:
                failures.append("{} history had contact failures".format(name))
            if value(final, PHYSICS_FIELDS, "thermal_work") <= 0.0:
                failures.append("{} history stored no friction work".format(name))
            if value(final, PHYSICS_FIELDS, "noise_energy") <= 0.0:
                failures.append("{} history made no bow noise".format(name))
            check_pcm(failures, name + " contact history", result[3])
        if all(all(tag in result[0] for tag in range(1, 5))
               for result in results):
            forward = results[0][0]
            reverse = results[1][0]
            before_product = value(
                forward[1], PHYSICS_FIELDS, "contact_memory") * value(
                reverse[1], PHYSICS_FIELDS, "contact_memory")
            if before_product >= 0.0:
                failures.append("opposite strokes did not store opposite contact memory")
            same_control_fields = (
                "contact_memory", "contact_force", "hair_displacement")
            if all(close(value(forward[2], PHYSICS_FIELDS, field), value(
                    reverse[2], PHYSICS_FIELDS, field), 1.0e-8)
                   for field in same_control_fields):
                failures.append("contact history vanished at equal live controls")
        if results[0][3] and results[1][3]:
            if results[0][3][0] == results[1][3][0]:
                failures.append("opposite contact histories rendered identical PCM")


def check_thermal(
    failures: List[str], csound: Path, module: Path, csd: Path,
    neutral_module: Path | None,
) -> None:
    with tempfile.TemporaryDirectory(prefix="hlolli-physics-thermal-") as folder:
        temporary = Path(folder)
        result = run_case(
            failures, "thermal work", csound, module, csd,
            {"TEST_CASE": 2, "TEST_END": 1.22}, tuple(range(1, 6)),
            tuple(range(1, 6)), tuple(range(1, 6)),
            output=temporary / "thermal.wav")
        neutral = None
        if neutral_module is not None:
            neutral = run_case(
                failures, "zero-drop thermal comparison", csound,
                neutral_module, csd, {"TEST_CASE": 2, "TEST_END": 1.22},
                tuple(range(1, 6)), tuple(range(1, 6)), tuple(range(1, 6)),
                output=temporary / "thermal-neutral.wav")
    physics, waves, _, rendered = result
    if any(tag not in physics or tag not in waves for tag in range(1, 6)):
        return
    for tag in range(1, 6):
        check_physics_common(
            failures, "thermal snapshot {}".format(tag), physics[tag])
        check_wave_common(failures, "thermal snapshot {}".format(tag), waves[tag])
    temperatures = [value(physics[tag], PHYSICS_FIELDS, "temperature")
                    for tag in range(1, 6)]
    warm = max(temperatures[1:3])
    if warm <= temperatures[0] + 1.0e-10:
        failures.append("sliding did not warm the contact")
    if temperatures[-1] >= warm:
        failures.append("released contact did not cool")
    if close(value(physics[1], PHYSICS_FIELDS, "thermal_scale"), value(
            physics[3], PHYSICS_FIELDS, "thermal_scale"), 1.0e-10):
        failures.append("temperature did not change friction scale")
    works = [value(physics[tag], PHYSICS_FIELDS, "thermal_work")
             for tag in range(1, 6)]
    if any(after + 1.0e-12 < before for before, after in zip(works, works[1:])):
        failures.append("thermal work counter went backwards")
    if rendered is not None:
        check_pcm(failures, "thermal work", rendered)
        samples = mono(rendered[1])
        early = harmonic_powers(
            samples[int(0.08 * SAMPLE_RATE):int(0.22 * SAMPLE_RATE)], 440.0)
        warm_spectrum = harmonic_powers(
            samples[int(0.42 * SAMPLE_RATE):int(0.58 * SAMPLE_RATE)], 440.0)
        if spectral_distance(early, warm_spectrum) <= 1.0e-5:
            failures.append("cold and warm contact had no spectral difference")
    if neutral is not None and rendered is not None and neutral[3] is not None:
        if any(tag not in neutral[0] for tag in range(1, 6)):
            return
        if rendered[0] == neutral[3][0]:
            failures.append("thermal drop made no PCM difference")
            return
        current_samples = mono(rendered[1], 0.08, 0.60)
        neutral_samples = mono(neutral[3][1], 0.08, 0.60)
        difference = [a - b for a, b in zip(current_samples, neutral_samples)]
        relative = rms(difference) / max(1.0e-30, rms(neutral_samples))
        current_spectrum = harmonic_powers(current_samples, 440.0)
        neutral_spectrum = harmonic_powers(neutral_samples, 440.0)
        distance = spectral_distance(current_spectrum, neutral_spectrum)
        print("thermal A/B: relative difference {:.9g}, spectral distance {:.9g}".
              format(relative, distance))
        if relative < 0.001 or distance < 0.001:
            failures.append(
                "thermal drop did not clear its audible-difference floor")
        if value(neutral[0][3], PHYSICS_FIELDS, "thermal_scale") != 1.0:
            failures.append("zero-drop build changed its thermal scale")


def check_hair_and_reversal(
    failures: List[str], csound: Path, module: Path, csd: Path,
) -> None:
    with tempfile.TemporaryDirectory(prefix="hlolli-physics-hair-") as folder:
        result = run_case(
            failures, "hair step and reversal", csound, module, csd,
            {"TEST_CASE": 3, "TEST_END": 0.54}, tuple(range(1, 8)),
            tuple(range(1, 8)), tuple(range(1, 8)),
            output=Path(folder) / "hair.wav")
    physics, waves, _, rendered = result
    if any(tag not in physics or tag not in waves for tag in range(1, 8)):
        return
    for tag in range(1, 8):
        check_physics_common(
            failures, "hair snapshot {}".format(tag), physics[tag])
        check_wave_common(failures, "hair snapshot {}".format(tag), waves[tag])
    effective = [value(physics[tag], PHYSICS_FIELDS, "hair_effective_speed")
                 for tag in range(1, 8)]
    displacement = [value(physics[tag], PHYSICS_FIELDS, "hair_displacement")
                    for tag in range(1, 8)]
    if close(effective[1], effective[3], 1.0e-8):
        failures.append("hair speed step had no compliance lag")
    if abs(effective[2] - effective[3]) >= abs(effective[1] - effective[3]):
        failures.append("hair speed did not settle after its step")
    if max(abs(item) for item in displacement[1:4]) <= abs(displacement[0]):
        failures.append("speed step stored no extra hair displacement")
    if effective[5] >= 0.0 or effective[6] >= 0.0:
        failures.append("hair state did not follow the bow reversal")
    if value(waves[7], WAVE_FIELDS, "excitation_count") != 1.0:
        failures.append("hair step or reversal retriggered the rail")
    if rendered is not None:
        check_pcm(failures, "hair step and reversal", rendered)
        samples = mono(rendered[1])
        for boundary in (0.16, 0.32):
            if not transition_step_ok(samples, boundary):
                failures.append(
                    "hair control clicked at {:.3f} seconds".format(boundary))


def check_mechanics_and_noise(
    failures: List[str], csound: Path, module: Path, csd: Path,
) -> None:
    with tempfile.TemporaryDirectory(prefix="hlolli-physics-mechanics-") as folder:
        temporary = Path(folder)
        results = []
        for variant, name in enumerate(
                ("stopped", "gate zero", "force zero", "speed zero", "open")):
            physics_tags = (1, 2) if variant == 0 else (1,)
            result = run_case(
                failures, name + " mechanics", csound, module, csd,
                {"TEST_CASE": 4, "TEST_VARIANT": variant, "TEST_END": 0.64},
                physics_tags, (1,), (1,),
                output=temporary / "{}.wav".format(variant))
            results.append(result)
            if 1 in result[0]:
                check_physics_common(failures, name + " mechanics", result[0][1])
            if 1 in result[1]:
                check_wave_common(failures, name + " mechanics", result[1][1])
            if result[3] is not None:
                check_pcm(failures, name + " mechanics", result[3])
        active = results[0]
        opened = results[4]
        if 2 in active[0]:
            attack = active[0][2]
            check_physics_common(failures, "stopped bow attack", attack)
            if value(attack, PHYSICS_FIELDS, "noise_energy") > 0.0075:
                failures.append("bow attack rosin energy exceeded its bound")
            if value(attack, PHYSICS_FIELDS, "noise_peak") > 0.0070:
                failures.append("bow attack rosin peak exceeded its bound")
        if 1 in active[0]:
            state = active[0][1]
            for field in ("board_energy", "board_impacts", "noise_energy",
                          "noise_peak", "mechanical_events"):
                if value(state, PHYSICS_FIELDS, field) <= 0.0:
                    failures.append("stopped bow had no {}".format(field))
        if 1 in opened[0]:
            state = opened[0][1]
            if value(state, PHYSICS_FIELDS, "board_impacts") != 0.0:
                failures.append("open string struck the fingerboard")
            if value(state, PHYSICS_FIELDS, "noise_energy") <= 0.0:
                failures.append("open bowed string made no rosin noise")
        for index, name in enumerate(("gate zero", "force zero"), 1):
            result = results[index]
            if 1 in result[0]:
                state = result[0][1]
                for field in ("board_energy", "board_impacts", "noise_energy",
                              "noise_peak", "mechanical_events"):
                    if value(state, PHYSICS_FIELDS, field) != 0.0:
                        failures.append("{} leaked {}".format(name, field))
            if result[3] is not None and any(
                    sample != 0 for channel in result[3][1] for sample in channel):
                failures.append("{} produced free hiss".format(name))
        if 1 in results[3][0] and 1 in opened[0]:
            stopped_motion = results[3][0][1]
            if value(stopped_motion, PHYSICS_FIELDS, "noise_last") != 0.0:
                failures.append("motionless contact kept making bow noise")
            if value(stopped_motion, PHYSICS_FIELDS, "noise_samples") >= value(
                    opened[0][1], PHYSICS_FIELDS, "noise_samples"):
                failures.append("motionless contact behaved like sliding hiss")
        repeat = run_case(
            failures, "deterministic stopped mechanics", csound, module, csd,
            {"TEST_CASE": 4, "TEST_VARIANT": 0, "TEST_END": 0.64},
            (1,), (1,), (1,), output=temporary / "repeat.wav")
        if active[3] and repeat[3]:
            if active[3][0] != repeat[3][0]:
                failures.append("mechanical noise changed on repeat render")
            if 1 in active[0] and 1 in repeat[0] and active[0][1] != repeat[0][1]:
                failures.append("mechanical state changed on repeat render")
            active_samples = mono(active[3][1], 0.08, 0.56)
            if rms(active_samples) <= 1.0 or difference_ratio(active_samples) <= 0.0:
                failures.append("mechanical path gave no audible high-band output")


def check_coupling_and_sympathetic(
    failures: List[str], csound: Path, module: Path, csd: Path,
) -> None:
    with tempfile.TemporaryDirectory(prefix="hlolli-physics-coupling-") as folder:
        temporary = Path(folder)
        same = run_case(
            failures, "same-handle bridge return", csound, module, csd,
            {"TEST_CASE": 5, "TEST_VARIANT": 0, "TEST_SYMPATHETIC": 0,
             "TEST_END": 0.64}, (1, 2), (1, 2), (1, 2),
            output=temporary / "same.wav")
        separate = run_case(
            failures, "cross-handle bridge isolation", csound, module, csd,
            {"TEST_CASE": 5, "TEST_VARIANT": 1, "TEST_SYMPATHETIC": 0,
             "TEST_END": 0.64}, (1, 2), (1, 2), (1, 2),
            output=temporary / "separate.wav")
        sympathetic = run_case(
            failures, "open-string sympathetic coupling", csound, module, csd,
            {"TEST_CASE": 5, "TEST_VARIANT": 0, "TEST_SYMPATHETIC": 1,
             "TEST_END": 0.64}, (1, 2), (1, 2), (1, 2),
            output=temporary / "sympathetic.wav")
    for label, result in (("same handle", same), ("separate handle", separate),
                          ("sympathetic", sympathetic)):
        for tag in (1, 2):
            if tag in result[0]:
                check_physics_common(
                    failures, "{} coupling {}".format(label, tag), result[0][tag])
            if tag in result[1]:
                check_wave_common(
                    failures, "{} coupling {}".format(label, tag), result[1][tag])
        if result[3] is not None:
            check_pcm(failures, label + " coupling", result[3])
    if 1 in same[0] and 1 in same[1]:
        target = same[0][1]
        if value(target, PHYSICS_FIELDS, "coupling_energy") <= 0.0:
            failures.append("same-handle target received no bridge return")
        if value(target, PHYSICS_FIELDS, "coupling_source_mask") == 0.0:
            failures.append("same-handle target recorded no coupling source")
        target_energy = value(same[1][1], WAVE_FIELDS, "toward_nut_energy") + \
            value(same[1][1], WAVE_FIELDS, "toward_bridge_energy")
        if target_energy <= 0.0:
            failures.append("same-handle bridge return did not enter target rails")
        if value(same[1][1], WAVE_FIELDS, "excitation_count") != 0.0:
            failures.append("bridge return counted as a target attack")
    if 1 in separate[0] and 1 in separate[1]:
        target = separate[0][1]
        for field in ("coupling_input", "coupling_energy", "coupling_peak",
                      "coupling_samples", "coupling_source_mask"):
            if value(target, PHYSICS_FIELDS, field) != 0.0:
                failures.append("another handle leaked {}".format(field))
        target_energy = value(
            separate[1][1], WAVE_FIELDS, "toward_nut_energy") + value(
            separate[1][1], WAVE_FIELDS, "toward_bridge_energy")
        if target_energy != 0.0:
            failures.append("another handle drove the silent target rails")
    if same[3] and separate[3] and same[3][0] == separate[3][0]:
        failures.append("bridge return made no rendered difference")
    if same[3] and sympathetic[3] and same[3][0] == sympathetic[3][0]:
        failures.append("kSympathetic did not change open-string audio")
    if (all(tag in same[0] for tag in (1, 2)) and
            all(tag in sympathetic[0] for tag in (1, 2)) and
            same[0] == sympathetic[0]):
        failures.append("kSympathetic did not change open-string physics")
    if 1 in same[0] and 1 in sympathetic[0]:
        base_energy = value(
            same[0][1], PHYSICS_FIELDS, "coupling_energy")
        sympathetic_energy = value(
            sympathetic[0][1], PHYSICS_FIELDS, "coupling_energy")
        if sympathetic_energy <= base_energy:
            failures.append("kSympathetic did not raise open-string coupling")


def check_handoff(
    failures: List[str], csound: Path, module: Path, csd: Path,
) -> None:
    with tempfile.TemporaryDirectory(prefix="hlolli-physics-handoff-") as folder:
        temporary = Path(folder)
        for name, split_time in (("block", 0.016), ("mid-block", 0.016125)):
            common = {"TEST_CASE": 6, "TEST_END": 0.060}
            reference = run_case(
                failures, name + " handoff reference", csound, module, csd,
                common, (1,), (1,), (1,),
                output=temporary / (name + "-reference.wav"))
            split_defs = dict(common)
            split_defs.update({"TEST_SPLIT": 1, "TEST_SPLIT_TIME": split_time})
            split = run_case(
                failures, name + " physics handoff", csound, module, csd,
                split_defs, (1,), (1,), (1,),
                output=temporary / (name + "-split.wav"))
            if reference[3] and split[3] and reference[3][0] != split[3][0]:
                failures.append("{} physics handoff changed PCM".format(name))
            for label, index in (("physics", 0), ("wave", 1), ("string", 2)):
                if 1 in reference[index] and 1 in split[index]:
                    same = reference[index][1] == split[index][1]
                    if label == "string":
                        same = all(close(a, b, 2.0e-12) for a, b in zip(
                            reference[index][1], split[index][1]))
                    if not same:
                        failures.append(
                            "{} handoff changed {} state".format(name, label))
            if 1 in split[0]:
                check_physics_common(failures, name + " handoff", split[0][1])
            if 1 in split[1]:
                check_wave_common(failures, name + " handoff", split[1][1])
                if value(split[1][1], WAVE_FIELDS, "excitation_count") != 1.0:
                    failures.append("{} handoff added an attack".format(name))


def check_gap(
    failures: List[str], csound: Path, module: Path, csd: Path,
) -> None:
    with tempfile.TemporaryDirectory(prefix="hlolli-physics-gap-") as folder:
        temporary = Path(folder)
        definitions = {"TEST_CASE": 7, "TEST_END": 0.060}
        first = run_case(
            failures, "physics owner gap", csound, module, csd, definitions,
            (1, 2), (1, 2), (1, 2), output=temporary / "gap.wav")
        repeat = run_case(
            failures, "physics owner gap repeat", csound, module, csd,
            definitions, (1, 2), (1, 2), (1, 2),
            output=temporary / "gap-repeat.wav")
    for tag in (1, 2):
        if tag in first[0]:
            check_physics_common(
                failures, "gap snapshot {}".format(tag), first[0][tag])
        if tag in first[1]:
            check_wave_common(failures, "gap snapshot {}".format(tag), first[1][tag])
    if first[3] and repeat[3] and first[3][0] != repeat[3][0]:
        failures.append("owner-gap audio was not deterministic")
    for index, label in ((0, "physics"), (1, "wave"), (2, "string")):
        if first[index] != repeat[index]:
            failures.append("owner-gap {} state was not exact".format(label))
    if 2 in first[2]:
        if value(first[2][2], STRING_FIELDS, "gap_samples") != 192.0:
            failures.append("four-millisecond gap advanced the wrong sample count")
    if 2 in first[1]:
        wave = first[1][2]
        if value(wave, WAVE_FIELDS, "excitation_count") != 2.0:
            failures.append("post-gap bow did not make one new attack")
        energy = value(wave, WAVE_FIELDS, "toward_nut_energy") + value(
            wave, WAVE_FIELDS, "toward_bridge_energy")
        if energy <= 0.0:
            failures.append("owner gap lost the stored rail")


def check_medium_gap(
    failures: List[str], csound: Path, module: Path, csd: Path,
) -> None:
    with tempfile.TemporaryDirectory(
            prefix="hlolli-physics-medium-gap-") as folder:
        temporary = Path(folder)
        definitions = {"TEST_CASE": 10, "TEST_END": 0.95}
        first = run_case(
            failures, "physics medium gap", csound, module, csd,
            definitions, (1, 2, 3), (1, 2, 3), (1, 2, 3),
            output=temporary / "gap.wav")
        repeat = run_case(
            failures, "physics medium gap repeat", csound, module, csd,
            definitions, (1, 2, 3), (1, 2, 3), (1, 2, 3),
            output=temporary / "gap-repeat.wav")
    if any(tag not in first[index] for index in range(3)
           for tag in (1, 2, 3)):
        return
    for tag in (1, 2, 3):
        check_physics_common(
            failures, "medium-gap snapshot {}".format(tag), first[0][tag])
        check_wave_common(
            failures, "medium-gap snapshot {}".format(tag), first[1][tag])
    if first[3] and repeat[3] and first[3][0] != repeat[3][0]:
        failures.append("medium-gap audio was not deterministic")
    for index, label in ((0, "physics"), (1, "wave"), (2, "string")):
        if first[index] != repeat[index]:
            failures.append("medium-gap {} state was not exact".format(label))

    hot = first[0][1]
    cooled = first[0][2]
    seeded_fields = (
        "contact_memory", "temperature", "hair_displacement",
        "board_displacement", "noise_last", "coupling_input",
    )
    for field in seeded_fields:
        if abs(value(hot, PHYSICS_FIELDS, field)) <= 1.0e-12:
            failures.append("medium gap did not seed {}".format(field))
    for field in ("contact_memory", "hair_displacement",
                  "board_displacement"):
        if abs(value(cooled, PHYSICS_FIELDS, field)) >= 0.01 * abs(
                value(hot, PHYSICS_FIELDS, field)):
            failures.append("medium gap did not decay {}".format(field))
    if value(cooled, PHYSICS_FIELDS, "temperature") >= 0.1 * value(
            hot, PHYSICS_FIELDS, "temperature"):
        failures.append("medium gap did not cool contact")
    if value(cooled, PHYSICS_FIELDS, "thermal_scale") <= value(
            hot, PHYSICS_FIELDS, "thermal_scale"):
        failures.append("medium gap did not restore thermal friction")
    for field in (
            "contact_force", "contact_steady_displacement",
            "hair_velocity", "hair_effective_speed", "board_compression",
            "board_force", "noise_last", "coupling_input",
            "coupling_source_mask"):
        if abs(value(cooled, PHYSICS_FIELDS, field)) > 1.0e-12:
            failures.append("medium gap kept live {}".format(field))
    for field in (
            "thermal_work", "board_energy", "board_impacts", "noise_energy",
            "noise_peak", "noise_samples", "mechanical_events",
            "coupling_energy", "coupling_peak", "coupling_samples"):
        if value(cooled, PHYSICS_FIELDS, field) < value(
                hot, PHYSICS_FIELDS, field):
            failures.append("medium gap reset cumulative {}".format(field))

    hot_wave = first[1][1]
    cooled_wave = first[1][2]
    resumed_wave = first[1][3]
    gap_samples = value(first[2][2], STRING_FIELDS, "gap_samples")
    capacity = value(cooled_wave, WAVE_FIELDS, "capacity")
    if gap_samples != 24000.0:
        failures.append("medium gap advanced the wrong sample count")
    if gap_samples <= 2.0 * capacity or gap_samples >= 6.0 * SAMPLE_RATE:
        failures.append("medium gap did not exercise bounded fast-forward")
    if value(cooled_wave, WAVE_FIELDS, "wave_samples") - value(
            hot_wave, WAVE_FIELDS, "wave_samples") != 25536.0:
        failures.append("medium gap lost waveguide time")
    hot_energy = value(hot_wave, WAVE_FIELDS, "toward_nut_energy") + value(
        hot_wave, WAVE_FIELDS, "toward_bridge_energy")
    cooled_energy = value(
        cooled_wave, WAVE_FIELDS, "toward_nut_energy") + value(
            cooled_wave, WAVE_FIELDS, "toward_bridge_energy")
    if not 0.0 < cooled_energy < hot_energy:
        failures.append("medium gap did not keep a bounded decaying rail")
    attacks = tuple(value(first[1][tag], WAVE_FIELDS, "excitation_count")
                    for tag in (1, 2, 3))
    if attacks != (1.0, 1.0, 2.0):
        failures.append("medium-gap attacks were {}, wanted (1, 1, 2)".format(
            attacks))
    if value(first[2][3], STRING_FIELDS, "gap_samples") != 24000.0:
        failures.append("medium-gap resume changed the gap counter")
    if value(resumed_wave, WAVE_FIELDS, "wave_samples") <= value(
            cooled_wave, WAVE_FIELDS, "wave_samples"):
        failures.append("medium-gap resume did not advance the rail")
    if first[3] is not None:
        check_pcm(failures, "physics medium gap", first[3])
        if rms(mono(first[3][1], 0.84, 0.92)) <= 1.0:
            failures.append("medium-gap bow did not resume audio")


def check_faults(
    failures: List[str], csound: Path, module: Path, csd: Path,
) -> None:
    with tempfile.TemporaryDirectory(prefix="hlolli-physics-fault-") as folder:
        temporary = Path(folder)
        names = ("contact", "thermal", "hair", "board", "noise", "coupling")
        for fault, name in enumerate(names, 1):
            label = name + " physics fault"
            result = run_case(
                failures, label, csound, module, csd,
                {"TEST_CASE": 8, "TEST_FAULT": fault, "TEST_END": 0.46},
                (1, 2, 3), (1, 2, 3), (1, 2, 3),
                output=temporary / "fault-{}.wav".format(fault))
            physics, waves, _, rendered = result
            if any(tag not in physics or tag not in waves for tag in (1, 2, 3)):
                continue
            for tag in (1, 2, 3):
                check_physics_common(
                    failures, "{} snapshot {}".format(label, tag), physics[tag])
                check_wave_common(
                    failures, "{} snapshot {}".format(label, tag), waves[tag])
                if value(waves[tag], WAVE_FIELDS, "excitation_count") != 1.0:
                    failures.append("{} retriggered a rail".format(label))
            if value(physics[1], PHYSICS_FIELDS, "recoveries") != 0.0:
                failures.append("{} began with recovery".format(label))
            for tag in (2, 3):
                if value(physics[tag], PHYSICS_FIELDS, "recoveries") != 1.0:
                    failures.append("{} did not recover once".format(label))
            before_energy = value(waves[1], WAVE_FIELDS, "toward_nut_energy") + \
                value(waves[1], WAVE_FIELDS, "toward_bridge_energy")
            after_energy = value(waves[2], WAVE_FIELDS, "toward_nut_energy") + \
                value(waves[2], WAVE_FIELDS, "toward_bridge_energy")
            if before_energy <= 0.0 or after_energy <= 0.0:
                failures.append("{} lost its stored rail".format(label))
            if rendered is not None:
                check_pcm(failures, label, rendered)
                if rms(mono(rendered[1], 0.26, 0.40)) <= 1.0:
                    failures.append("{} did not resume audio".format(label))


def check_bow_recovery_contact_isolation(
    failures: List[str], csound: Path, module: Path, csd: Path,
) -> None:
    physics, waves, _, _ = run_case(
        failures,
        "bow recovery contact isolation",
        csound,
        module,
        csd,
        {"TEST_CASE": 11, "TEST_END": 0.61, "TEST_KSMPS": 1},
        (1, 2, 3),
        (1, 2, 3),
        (1, 2, 3),
    )
    if any(tag not in physics or tag not in waves for tag in (1, 2, 3)):
        return
    for tag in (1, 2, 3):
        check_physics_common(
            failures, "bow recovery snapshot {}".format(tag), physics[tag])
        check_wave_common(
            failures, "bow recovery snapshot {}".format(tag), waves[tag])
    before_force = value(physics[1], PHYSICS_FIELDS, "contact_force")
    recovery_force = value(physics[2], PHYSICS_FIELDS, "contact_force")
    resumed_force = value(physics[3], PHYSICS_FIELDS, "contact_force")
    if abs(before_force) <= 1.0e-9:
        failures.append("bow recovery test began without stored-contact force")
    if recovery_force != 0.0:
        failures.append(
            "bow recovery leaked stored-contact force {}".format(
                recovery_force))
    if value(physics[2], PHYSICS_FIELDS, "contact_iterations") != 0.0:
        failures.append("bow recovery ran the stored-contact solver")
    if value(physics[2], PHYSICS_FIELDS, "contact_adhesion") != 0.0:
        failures.append("bow recovery retained contact adhesion")
    if value(
            physics[2], PHYSICS_FIELDS,
            "contact_steady_displacement") != 0.0:
        failures.append("bow recovery retained steady contact displacement")
    if abs(resumed_force) <= 1.0e-9:
        failures.append("stored-contact force did not resume after bow recovery")
    for tag in (1, 2, 3):
        if value(physics[tag], PHYSICS_FIELDS, "recoveries") != 0.0:
            failures.append("bow recovery reset secondary physics")


def check_stress(
    failures: List[str], csound: Path, module: Path, csd: Path,
) -> None:
    with tempfile.TemporaryDirectory(prefix="hlolli-physics-stress-") as folder:
        result = run_case(
            failures, "physics stress", csound, module, csd,
            {"TEST_CASE": 9, "TEST_END": 6.05}, (1, 2, 3, 4),
            (1, 2, 3, 4), (1, 2, 3, 4),
            output=Path(folder) / "stress.wav", timeout=90)
    physics, waves, _, rendered = result
    if any(tag not in physics or tag not in waves for tag in (1, 2, 3, 4)):
        return
    signatures = []
    for tag in (1, 2, 3, 4):
        label = "physics stress string {}".format(tag)
        check_physics_common(failures, label, physics[tag])
        check_wave_common(failures, label, waves[tag])
        for field in ("contact_failures", "recoveries"):
            if value(physics[tag], PHYSICS_FIELDS, field) != 0.0:
                failures.append("{} had nonzero {}".format(label, field))
        for field in ("thermal_work", "noise_energy", "coupling_energy",
                      "coupling_samples"):
            if value(physics[tag], PHYSICS_FIELDS, field) <= 0.0:
                failures.append("{} had no {}".format(label, field))
        if value(waves[tag], WAVE_FIELDS, "wave_samples") < 287000.0:
            failures.append("{} skipped wave samples".format(label))
        signatures.append(tuple(round(value(
            physics[tag], PHYSICS_FIELDS, field), 12) for field in (
                "thermal_work", "noise_energy", "coupling_energy")))
    if len(set(signatures)) != 4:
        failures.append("four strings shared bow mechanics physics state")
    if rendered is not None:
        check_pcm(failures, "physics stress", rendered)
        if rms(mono(rendered[1], 0.1, 5.9)) <= 1.0:
            failures.append("physics stress rendered silence")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csound", required=True, type=Path)
    parser.add_argument("--module", required=True, type=Path)
    parser.add_argument("--csd", required=True, type=Path)
    parser.add_argument("--thermal-neutral-module", type=Path)
    arguments = parser.parse_args()
    failures: List[str] = []

    check_contact_history(
        failures, arguments.csound, arguments.module, arguments.csd)
    check_thermal(
        failures, arguments.csound, arguments.module, arguments.csd,
        arguments.thermal_neutral_module)
    check_hair_and_reversal(
        failures, arguments.csound, arguments.module, arguments.csd)
    check_mechanics_and_noise(
        failures, arguments.csound, arguments.module, arguments.csd)
    check_coupling_and_sympathetic(
        failures, arguments.csound, arguments.module, arguments.csd)
    check_handoff(failures, arguments.csound, arguments.module, arguments.csd)
    check_gap(failures, arguments.csound, arguments.module, arguments.csd)
    check_medium_gap(
        failures, arguments.csound, arguments.module, arguments.csd)
    check_faults(failures, arguments.csound, arguments.module, arguments.csd)
    check_bow_recovery_contact_isolation(
        failures, arguments.csound, arguments.module, arguments.csd)
    check_stress(failures, arguments.csound, arguments.module, arguments.csd)

    if failures:
        for failure in failures:
            print("FAIL: {}".format(failure), file=sys.stderr)
        return 1
    print("contact and secondary-physics checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
