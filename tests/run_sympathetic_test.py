#!/usr/bin/env python3
"""Check sympathetic strings and the bipolar kStrange control."""

from __future__ import annotations

import argparse
import math
import re
import struct
import subprocess
import sys
import tempfile
import wave
from pathlib import Path
from typing import Dict, List, Mapping, Optional, Sequence, Tuple


State = Tuple[float, ...]
Channels = Tuple[List[int], List[int]]
Audio = Tuple[bytes, Channels]
Result = Tuple[
    Dict[int, State], Dict[int, State], Dict[int, State],
    Dict[int, State], Optional[Audio], str, Dict[int, State],
]

SAMPLE_RATE = 48000
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
BODY_FIELDS = (
    "body", "sympathetic", "mute", "mode_count", "send_samples_1",
    "send_samples_2", "send_samples_3", "send_samples_4", "send_energy_1",
    "send_energy_2", "send_energy_3", "send_energy_4", "last_drive",
    "drive_energy", "modal_energy", "state_signature", "last_left",
    "last_right", "output_energy_left", "output_energy_right", "peak_left",
    "peak_right", "processed_samples", "fast_forward_samples", "reset_count",
    "clip_count", "finite",
)
STRANGE_FIELDS = (
    "strange", "sympathetic", "sympathetic_applied", "air_state",
    "dispersion_input", "dispersion_output", "subharmonic_phase",
    "subharmonic_envelope", "squeal_state", "squeal_frequency",
    "coupling_mix", "last_output", "energy", "peak", "samples",
    "recoveries", "passive_active",
    "passive_level", "passive_energy", "passive_peak", "passive_samples",
    "finite",
)


def value(state: State, fields: Sequence[str], name: str) -> float:
    return state[fields.index(name)]


def run_csound(
    csound: Path,
    module: Path,
    csd: Path,
    definitions: Mapping[str, object],
    output: Path | None = None,
    timeout: int = 90,
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
            raise ValueError("unexpected sympathetic-test WAV format")
        frames = audio.readframes(audio.getnframes())
    pairs = list(struct.iter_unpack("<hh", frames))
    return frames, ([pair[0] for pair in pairs], [pair[1] for pair in pairs])


def read_out_of_range(output: str) -> Tuple[int, ...]:
    match = re.search(
        r"overall samples out of range:\s+([0-9]+)(?:\s+([0-9]+))?",
        output,
    )
    if match is None:
        return ()
    return tuple(int(item) for item in match.groups() if item is not None)


def run_case(
    failures: List[str],
    label: str,
    csound: Path,
    module: Path,
    csd: Path,
    definitions: Mapping[str, object],
    wave_tags: Sequence[int] = (),
    string_tags: Sequence[int] = (),
    physics_tags: Sequence[int] = (),
    body_tags: Sequence[int] = (),
    output: Path | None = None,
    timeout: int = 90,
    strange_tags: Sequence[int] = (),
) -> Result:
    completed = run_csound(
        csound, module, csd, definitions, output=output, timeout=timeout)
    if completed.returncode != 0:
        failures.append(
            "{} failed with status {}:\n{}".format(
                label, completed.returncode, completed.stdout.rstrip()))
        return {}, {}, {}, {}, None, completed.stdout, {}
    waves = read_tagged(completed.stdout, "WG_SYMP_WAVE", len(WAVE_FIELDS))
    strings = read_tagged(
        completed.stdout, "WG_SYMP_STRING", len(STRING_FIELDS))
    first = read_tagged(
        completed.stdout, "WG_SYMP_PHYSICS_A", 16)
    second = read_tagged(
        completed.stdout, "WG_SYMP_PHYSICS_B", 15)
    physics = {
        tag: first[tag] + second[tag]
        for tag in first.keys() & second.keys()
    }
    bodies = read_tagged(completed.stdout, "WG_SYMP_BODY", len(BODY_FIELDS))
    strange = read_tagged(
        completed.stdout, "WG_SYMP_STRANGE", len(STRANGE_FIELDS))
    expected_strange_tags = strange_tags if strange_tags else wave_tags
    for states, tags, name in (
            (waves, wave_tags, "wave"),
            (strings, string_tags, "string"),
            (physics, physics_tags, "physics"),
            (bodies, body_tags, "body"),
            (strange, expected_strange_tags, "sympathetic-string")):
        missing = [tag for tag in tags if tag not in states]
        if missing:
            failures.append("{} missed {} tags {}".format(label, name, missing))
    ranges = read_out_of_range(completed.stdout)
    if not ranges:
        failures.append("{} did not report output bounds".format(label))
    elif any(ranges):
        failures.append("{} had out-of-range samples {}".format(label, ranges))
    rendered = None
    if output is not None:
        if not output.exists():
            failures.append("{} produced no WAV".format(label))
        else:
            try:
                rendered = read_wav(output)
            except (ValueError, wave.Error) as error:
                failures.append("{}: {}".format(label, error))
    return waves, strings, physics, bodies, rendered, completed.stdout, strange


def mono(channels: Channels, start: float, stop: float) -> List[float]:
    first = max(0, int(start * SAMPLE_RATE))
    last = min(len(channels[0]), int(stop * SAMPLE_RATE))
    return [0.5 * (left + right) for left, right in zip(
        channels[0][first:last], channels[1][first:last])]


def rms(samples: Sequence[float]) -> float:
    if not samples:
        return 0.0
    return math.sqrt(sum(sample * sample for sample in samples) / len(samples))


def high_band_share(samples: Sequence[float]) -> float:
    """Return a stable high-band proxy based on a 3.5 kHz one-pole split."""
    if not samples:
        return 0.0
    pole = math.exp(-2.0 * math.pi * 3500.0 / SAMPLE_RATE)
    low = 0.0
    high_energy = 0.0
    full_energy = 0.0
    for sample in samples:
        low = (1.0 - pole) * sample + pole * low
        high = sample - low
        high_energy += high * high
        full_energy += sample * sample
    return high_energy / full_energy if full_energy > 0.0 else 0.0


def tone_amplitude(samples: Sequence[float], frequency: float) -> float:
    if not samples:
        return 0.0
    angular = 2.0 * math.pi * frequency / SAMPLE_RATE
    real = 0.0
    imaginary = 0.0
    count = len(samples)
    for index, sample in enumerate(samples):
        window = 0.5 - 0.5 * math.cos(
            2.0 * math.pi * index / max(1, count - 1))
        real += sample * window * math.cos(angular * index)
        imaginary -= sample * window * math.sin(angular * index)
    return math.hypot(real, imaginary) / max(1, count)


def rail_energy(state: State) -> float:
    return (value(state, WAVE_FIELDS, "toward_nut_energy") +
            value(state, WAVE_FIELDS, "toward_bridge_energy"))


def check_common(
    failures: List[str], label: str, waves: Mapping[int, State],
    physics: Mapping[int, State], bodies: Mapping[int, State],
    strange: Optional[Mapping[int, State]] = None,
) -> None:
    for tag, state in waves.items():
        if len(state) != len(WAVE_FIELDS) or not all(map(math.isfinite, state)):
            failures.append("{} wave {} was not finite".format(label, tag))
            continue
        if value(state, WAVE_FIELDS, "finite") != 1.0:
            failures.append("{} wave {} reported invalid state".format(
                label, tag))
        if value(state, WAVE_FIELDS, "clip_count") != 0.0:
            failures.append("{} wave {} used a safety clip".format(label, tag))
        if rail_energy(state) < 0.0:
            failures.append("{} wave {} had negative energy".format(label, tag))
    for tag, state in physics.items():
        if (len(state) != len(PHYSICS_FIELDS) or
                not all(map(math.isfinite, state)) or
                value(state, PHYSICS_FIELDS, "finite") != 1.0):
            failures.append("{} physics {} was not finite".format(label, tag))
    for tag, state in bodies.items():
        if (len(state) != len(BODY_FIELDS) or
                not all(map(math.isfinite, state)) or
                value(state, BODY_FIELDS, "finite") != 1.0):
            failures.append("{} body {} was not finite".format(label, tag))
            continue
        if value(state, BODY_FIELDS, "clip_count") != 0.0:
            failures.append("{} body {} used a safety clip".format(label, tag))
    if strange is None:
        return
    for tag, state in strange.items():
        item_label = "{} kStrange string {}".format(label, tag)
        if len(state) != len(STRANGE_FIELDS) or not all(map(math.isfinite, state)):
            failures.append("{} was not finite".format(item_label))
            continue
        if value(state, STRANGE_FIELDS, "finite") != 1.0:
            failures.append("{} reported invalid state".format(item_label))
        for field in ("strange",):
            if abs(value(state, STRANGE_FIELDS, field)) > 1.000000000001:
                failures.append("{} had invalid {}".format(item_label, field))
        for field in ("sympathetic", "sympathetic_applied", "coupling_mix"):
            found = value(state, STRANGE_FIELDS, field)
            if not 0.0 <= found <= 1.0:
                failures.append("{} had invalid {}".format(item_label, field))
        if abs(value(state, STRANGE_FIELDS, "air_state")) > 1.000000000001:
            failures.append("{} let air state leave its bound".format(item_label))
        phase = value(state, STRANGE_FIELDS, "subharmonic_phase")
        if not 0.0 <= phase < 1.0:
            failures.append("{} had invalid subharmonic phase".format(item_label))
        for field, limit in (
                ("dispersion_input", 4.0), ("dispersion_output", 4.0),
                ("subharmonic_envelope", 0.006000000001),
                ("squeal_state", 0.008000000001),
                ("last_output", 0.018000000001),
                ("peak", 0.018000000001),
                ("passive_level", 4.000000000001),
                ("passive_peak", 4.000000000001)):
            if abs(value(state, STRANGE_FIELDS, field)) > limit:
                failures.append("{} let {} leave its bound".format(
                    item_label, field))
        squeal_frequency = value(
            state, STRANGE_FIELDS, "squeal_frequency")
        if not 0.0 < squeal_frequency <= 7800.0:
            failures.append("{} had invalid squeal frequency".format(
                item_label))
        for field in ("energy", "passive_energy"):
            if value(state, STRANGE_FIELDS, field) < 0.0:
                failures.append("{} had negative {}".format(item_label, field))
        for field in ("samples", "recoveries", "passive_active",
                      "passive_samples"):
            found = value(state, STRANGE_FIELDS, field)
            if found < 0.0 or found != math.floor(found):
                failures.append("{} had invalid {}".format(item_label, field))
        if value(state, STRANGE_FIELDS, "passive_active") > 1.0:
            failures.append("{} had invalid passive flag".format(item_label))


def check_neutral_baseline(
    failures: List[str], csound: Path, module: Path, baseline: Path | None,
    neutral_csd: Path | None,
) -> None:
    if baseline is None or neutral_csd is None:
        return
    with tempfile.TemporaryDirectory(prefix="hlolli-sympathetic-neutral-") as folder:
        temporary = Path(folder)
        current_path = temporary / "current.wav"
        baseline_path = temporary / "baseline.wav"
        definitions = {"BENCH_CASE": 1, "BENCH_SECONDS": 0.6}
        current = run_csound(
            csound, module, neutral_csd, definitions, current_path)
        old = run_csound(
            csound, baseline, neutral_csd, definitions, baseline_path)
        for label, completed in (("neutral current", current),
                                 ("neutral baseline", old)):
            if completed.returncode != 0:
                failures.append("{} failed:\n{}".format(
                    label, completed.stdout.rstrip()))
            elif any(read_out_of_range(completed.stdout)):
                failures.append("{} exceeded output bounds".format(label))
        if current.returncode != 0 or old.returncode != 0:
            return
        try:
            current_audio = read_wav(current_path)
            old_audio = read_wav(baseline_path)
        except (ValueError, wave.Error, FileNotFoundError) as error:
            failures.append("neutral baseline A/B: {}".format(error))
            return
    if current_audio[0] != old_audio[0]:
        failures.append("kStrange 0 and kSympathetic 0 changed neutral PCM")


def check_sympathetic_response(
    failures: List[str], csound: Path, module: Path, csd: Path,
) -> None:
    with tempfile.TemporaryDirectory(prefix="hlolli-sympathetic-") as folder:
        temporary = Path(folder)
        levels: Dict[float, Result] = {}
        for level in (0.0, 0.25, 0.6, 1.0):
            levels[level] = run_case(
                failures, "unowned sympathy {:.2g}".format(level),
                csound, module, csd,
                {"TEST_CASE": 1, "TEST_VARIANT": 0,
                 "TEST_SYMPATHETIC": level, "TEST_END": 0.62},
                (1, 2, 3, 4), (1, 2, 3, 4), (1, 2, 3, 4), (1,),
                temporary / "unowned-{}.wav".format(level))
        for order in (0, 1):
            run = run_case(
                failures, "owned sympathy order {}".format(order),
                csound, module, csd,
                {"TEST_CASE": 1, "TEST_VARIANT": 1,
                 "TEST_SYMPATHETIC": 1, "TEST_ORDER": order,
                 "TEST_END": 0.62},
                (1, 2, 3, 4), (1, 2, 3, 4), (1, 2, 3, 4), (1,),
                temporary / "owned-order-{}.wav".format(order))
            levels[2.0 + order] = run

    for level, result in levels.items():
        check_common(
            failures, "sympathy {:.2g}".format(level),
            result[0], result[2], result[3], result[6])
    if any(tag not in levels[0.0][0] for tag in (2, 3, 4)):
        return
    for tag in (2, 3, 4):
        if rail_energy(levels[0.0][0][tag]) != 0.0:
            failures.append("zero sympathy moved free string {}".format(tag))
        if value(levels[0.0][0][tag], WAVE_FIELDS, "wave_samples") != 0.0:
            failures.append("zero sympathy stepped free string {}".format(tag))
        neutral_state = levels[0.0][6].get(tag)
        if neutral_state is not None:
            if value(neutral_state, STRANGE_FIELDS, "passive_samples") != 0.0:
                failures.append(
                    "zero sympathy counted passive string {}".format(tag))
            if value(
                    neutral_state, STRANGE_FIELDS,
                    "sympathetic_applied") != 0.0:
                failures.append(
                    "zero sympathy left an applied control on string {}".format(
                        tag))

    target_energy = []
    for level in (0.25, 0.6, 1.0):
        waves = levels[level][0]
        if any(tag not in waves for tag in (2, 3, 4)):
            return
        target_energy.append(rail_energy(waves[2]))
        if rail_energy(waves[2]) <= 0.0:
            failures.append("sympathy {} did not excite open D".format(level))
        if value(waves[2], WAVE_FIELDS, "wave_samples") < 26000.0:
            failures.append("sympathy {} did not step open D".format(level))
        if rail_energy(waves[2]) <= max(
                rail_energy(waves[3]), rail_energy(waves[4])):
            failures.append(
                "sympathy {} lost open-pitch selectivity".format(level))
        target = levels[level][6].get(2)
        if target is not None:
            if not math.isclose(
                    value(target, STRANGE_FIELDS, "sympathetic_applied"),
                    level, rel_tol=1.0e-12, abs_tol=1.0e-12):
                failures.append(
                    "sympathy {} applied the wrong control".format(level))
            if value(target, STRANGE_FIELDS, "passive_active") != 1.0:
                failures.append(
                    "sympathy {} did not mark open D passive".format(level))
            if value(target, STRANGE_FIELDS, "passive_energy") <= 0.0:
                failures.append(
                    "sympathy {} recorded no passive energy".format(level))
            if value(target, STRANGE_FIELDS, "passive_samples") < 26000.0:
                failures.append(
                    "sympathy {} missed passive samples".format(level))
    if not target_energy[0] < target_energy[1] < target_energy[2]:
        failures.append(
            "sympathetic amount did not raise open-D energy: {}".format(
                target_energy))

    early = levels[2.0]
    late = levels[3.0]
    if early[0] and late[0] and early[0] != late[0]:
        failures.append("renderer/voice order changed sympathetic rail state")
    if early[2] and late[2] and early[2] != late[2]:
        failures.append("renderer/voice order changed secondary state")
    if early[6] and late[6] and early[6] != late[6]:
        failures.append("renderer/voice order changed sympathetic-string state")
    if (early[4] is not None and late[4] is not None and
            early[4][0] != late[4][0]):
        failures.append("renderer/voice order changed sympathetic PCM")
    for label, result in (("early", early), ("late", late)):
        if 2 in result[0]:
            samples = value(result[0][2], WAVE_FIELDS, "wave_samples")
            if not 26000.0 <= samples <= 27000.0:
                failures.append(
                    "{} owned open target stepped {} samples".format(
                        label, samples))


def check_target_rules(
    failures: List[str], csound: Path, module: Path, csd: Path,
) -> None:
    results: Dict[Tuple[int, int], Result] = {}
    with tempfile.TemporaryDirectory(prefix="hlolli-sympathetic-target-") as folder:
        temporary = Path(folder)
        for variant in (0, 1, 2):
            for enabled in (0, 1):
                results[(variant, enabled)] = run_case(
                    failures,
                    "sympathetic target {} level {}".format(variant, enabled),
                    csound, module, csd,
                    {"TEST_CASE": 2, "TEST_VARIANT": variant,
                     "TEST_SYMPATHETIC": enabled, "TEST_END": 0.62},
                    (1,), (1,), (1,), (1,),
                    temporary / "target-{}-{}.wav".format(variant, enabled))
    for key, result in results.items():
        check_common(failures, "target {}".format(key), result[0],
                     result[2], result[3], result[6])
    open_off = results[(0, 0)][0].get(1)
    open_on = results[(0, 1)][0].get(1)
    stopped_off = results[(1, 0)][0].get(1)
    stopped_on = results[(1, 1)][0].get(1)
    other_on = results[(2, 1)][0].get(1)
    if open_off and open_on and rail_energy(open_on) <= rail_energy(open_off):
        failures.append("sympathy did not add energy to an owned open string")
    if stopped_off and stopped_on and stopped_on != stopped_off:
        failures.append("sympathy changed a stopped target")
    if other_on and rail_energy(other_on) != 0.0:
        failures.append("sympathetic energy leaked across handles")


def check_reserved_articulation_coupling(
    failures: List[str], csound: Path, module: Path, csd: Path,
) -> None:
    for sympathetic in (0, 1):
        result = run_case(
            failures,
            "reserved coupling at sympathy {}".format(sympathetic),
            csound, module, csd,
            {"TEST_CASE": 9, "TEST_SYMPATHETIC": sympathetic,
             "TEST_END": 0.34},
            (1,), (1,), (1,), ())
        check_common(
            failures, "reserved coupling", result[0], result[2],
            result[3], result[6])
        wave = result[0].get(1)
        physics = result[2].get(1)
        if wave is None or physics is None:
            continue
        if rail_energy(wave) != 0.0:
            failures.append(
                "reserved articulation accepted bridge energy at sympathy {}".
                format(sympathetic))
        for field in (
                "coupling_input", "coupling_energy", "coupling_peak",
                "coupling_samples", "coupling_source_mask"):
            if value(physics, PHYSICS_FIELDS, field) != 0.0:
                failures.append(
                    "reserved articulation had nonzero {} at sympathy {}".
                    format(field, sympathetic))


def check_low_rate_squeal_bounds(
    failures: List[str], csound: Path, module: Path, csd: Path,
) -> None:
    for sample_rate in (8000, 9600, 12000):
        result = run_case(
            failures, "low-rate squeal {}".format(sample_rate),
            csound, module, csd,
            {"TEST_CASE": 10, "TEST_SR": sample_rate,
             "TEST_STRANGE": 1, "TEST_END": 0.24},
            strange_tags=(1,))
        state = result[6].get(1)
        if state is None:
            continue
        found = value(state, STRANGE_FIELDS, "squeal_frequency")
        wanted = min(4200.0, 0.40 * sample_rate)
        if not math.isclose(found, wanted, rel_tol=1.0e-12, abs_tol=1.0e-12):
            failures.append(
                "{} Hz squeal was {:.17g}, wanted {:.17g}".format(
                    sample_rate, found, wanted))
        if found > 0.40 * sample_rate:
            failures.append(
                "{} Hz squeal exceeded its low-rate ceiling".format(
                    sample_rate))


def check_strange_audio(
    failures: List[str], csound: Path, module: Path, csd: Path,
) -> None:
    values = (-1.0, -0.05, 0.0, 0.05, 1.0)
    results: Dict[float, Result] = {}
    repeats: Dict[float, Result] = {}
    with tempfile.TemporaryDirectory(prefix="hlolli-strange-") as folder:
        temporary = Path(folder)
        for strange in values:
            definitions = {
                "TEST_CASE": 3, "TEST_STRANGE": strange,
                "TEST_SYMPATHETIC": 1, "TEST_END": 0.62,
            }
            results[strange] = run_case(
                failures, "strange {}".format(strange), csound, module, csd,
                definitions, (1, 2, 3, 4), (1, 2, 3, 4),
                (1, 2, 3, 4), (1,),
                temporary / "strange-{}.wav".format(strange))
            if abs(strange) == 1.0:
                repeats[strange] = run_case(
                    failures, "strange {} repeat".format(strange),
                    csound, module, csd, definitions,
                    (1, 2, 3, 4), (1, 2, 3, 4),
                    (1, 2, 3, 4), (1,),
                    temporary / "strange-{}-repeat.wav".format(strange))
        for strange in (-1.0, 1.0):
            for variant in (1, 2, 3):
                run = run_case(
                    failures,
                    "strange {} silent control {}".format(strange, variant),
                    csound, module, csd,
                    {"TEST_CASE": 3, "TEST_VARIANT": variant,
                     "TEST_STRANGE": strange, "TEST_SYMPATHETIC": 1,
                     "TEST_END": 0.62},
                    (1,), (1,), (1,), (1,),
                    temporary / "silent-{}-{}.wav".format(strange, variant))
                check_common(
                    failures, "strange silent", run[0], run[2], run[3],
                    run[6])
                if run[4] is not None and rms(mono(run[4][1], 0.08, 0.54)) > 1.0:
                    failures.append(
                        "strange {} made a free oscillator for control {}".format(
                            strange, variant))
                source_state = run[6].get(3)
                if source_state is not None and (
                        value(source_state, STRANGE_FIELDS, "samples") != 0.0 or
                        value(source_state, STRANGE_FIELDS, "energy") != 0.0):
                    failures.append(
                        "strange {} kept state for silent control {}".format(
                            strange, variant))
        low_force = run_case(
            failures, "positive strange low force", csound, module, csd,
            {"TEST_CASE": 3, "TEST_VARIANT": 4,
             "TEST_STRANGE": 1, "TEST_SYMPATHETIC": 1,
             "TEST_END": 0.62},
            (3,), (3,), (3,), (1,),
            temporary / "positive-low-force.wav")
        check_common(
            failures, "positive strange low force", low_force[0],
            low_force[2], low_force[3], low_force[6])
        low_force_state = low_force[6].get(3)
        if low_force_state is not None and (
                abs(value(low_force_state, STRANGE_FIELDS,
                          "subharmonic_envelope")) > 1.0e-12 or
                abs(value(low_force_state, STRANGE_FIELDS,
                          "squeal_state")) > 1.0e-12):
            failures.append(
                "positive kStrange made an anomaly at negligible force")

    metrics: Dict[float, Tuple[float, float, float, float]] = {}
    for strange, result in results.items():
        check_common(
            failures, "strange {}".format(strange),
            result[0], result[2], result[3], result[6])
        if result[4] is None:
            continue
        samples = mono(result[4][1], 0.12, 0.54)
        fundamental = tone_amplitude(samples, 440.0)
        sub = tone_amplitude(samples, 220.0)
        metrics[strange] = (
            rms(samples), high_band_share(samples),
            sub / max(fundamental, 1.0e-12),
            tone_amplitude(samples, 13.0 * 440.0),
        )
    if all(item in metrics for item in values):
        negative = metrics[-1.0]
        neutral = metrics[0.0]
        positive = metrics[1.0]
        if negative[0] >= 0.98 * neutral[0]:
            failures.append("negative kStrange was not weaker than neutral")
        if negative[1] <= neutral[1]:
            failures.append(
                "negative kStrange high-band share {:.9g} did not exceed "
                "neutral {:.9g}".format(negative[1], neutral[1]))
        for strange in (-0.05, 0.05):
            ratio = metrics[strange][0] / max(neutral[0], 1.0e-12)
            if not 0.75 <= ratio <= 1.25:
                failures.append(
                    "kStrange {} left the near-neutral level range".format(
                        strange))
        if positive[2] <= 1.10 * neutral[2]:
            failures.append(
                "positive kStrange sub-octave ratio {:.9g} did not exceed "
                "neutral {:.9g} by 10 percent".format(
                    positive[2], neutral[2]))
        if positive[3] <= 2.0 * neutral[3]:
            failures.append(
                "positive kStrange squeal {:.9g} did not exceed neutral "
                "{:.9g} by 2x".format(positive[3], neutral[3]))
        neutral_targets = sum(
            rail_energy(results[0.0][0][tag]) for tag in (1, 2, 4))
        positive_targets = sum(
            rail_energy(results[1.0][0][tag]) for tag in (1, 2, 4))
        if positive_targets <= 1.10 * neutral_targets:
            failures.append(
                "positive kStrange did not raise same-handle coupling")
        negative_state = results[-1.0][6].get(3)
        neutral_state = results[0.0][6].get(3)
        positive_state = results[1.0][6].get(3)
        if negative_state is not None:
            if (value(negative_state, STRANGE_FIELDS, "samples") <= 0.0 or
                    value(negative_state, STRANGE_FIELDS, "energy") <= 0.0 or
                    abs(value(
                        negative_state, STRANGE_FIELDS, "air_state")) <= 1.0e-12):
                failures.append("negative kStrange did not run its air state")
        if neutral_state is not None:
            for field in ("last_output", "energy", "peak", "samples"):
                if value(neutral_state, STRANGE_FIELDS, field) != 0.0:
                    failures.append(
                        "neutral kStrange changed {}".format(field))
        if positive_state is not None:
            for field in ("subharmonic_envelope", "coupling_mix", "energy",
                          "samples"):
                if value(positive_state, STRANGE_FIELDS, field) <= 0.0:
                    failures.append(
                        "positive kStrange did not run {}".format(field))
    for strange, repeat in repeats.items():
        first = results[strange]
        if first[0] != repeat[0] or first[2] != repeat[2]:
            failures.append("kStrange {} state was not deterministic".format(
                strange))
        if (first[4] is not None and repeat[4] is not None and
                first[4][0] != repeat[4][0]):
            failures.append("kStrange {} PCM was not deterministic".format(
                strange))


def check_handoffs(
    failures: List[str], csound: Path, module: Path, csd: Path,
) -> None:
    settings = ((0.8, 0.7), (0.65, -0.7))
    splits = (0.016, 0.016125)
    with tempfile.TemporaryDirectory(prefix="hlolli-sympathetic-handoff-") as folder:
        temporary = Path(folder)
        for sympathetic, strange in settings:
            base = {
                "TEST_CASE": 4, "TEST_END": 0.06,
                "TEST_SYMPATHETIC": sympathetic, "TEST_STRANGE": strange,
                "TEST_SPLIT": 0,
            }
            held = run_case(
                failures, "sympathetic-string held", csound, module, csd, base,
                (1, 2), (1, 2), (1, 2), (1,),
                temporary / "held-{}-{}.wav".format(sympathetic, strange))
            for split in splits:
                definitions = dict(base)
                definitions.update({"TEST_SPLIT": 1, "TEST_SPLIT_TIME": split})
                divided = run_case(
                    failures, "sympathetic-string split {}".format(split),
                    csound, module, csd, definitions,
                    (1, 2), (1, 2), (1, 2), (1,),
                    temporary / "split-{}-{}-{}.wav".format(
                        sympathetic, strange, split))
                if held[:4] != divided[:4]:
                    failures.append(
                        "sympathetic-string split {} changed exact state".format(split))
                if held[6] != divided[6]:
                    failures.append(
                        "sympathetic-string split {} changed exact new state".format(
                            split))
                if (held[4] is not None and divided[4] is not None and
                        held[4][0] != divided[4][0]):
                    failures.append(
                        "sympathetic-string split {} changed exact PCM".format(split))


def check_gap(
    failures: List[str], csound: Path, module: Path, csd: Path,
) -> None:
    with tempfile.TemporaryDirectory(prefix="hlolli-sympathetic-gap-") as folder:
        result = run_case(
            failures, "sympathetic-string renderer gap", csound, module, csd,
            {"TEST_CASE": 5, "TEST_END": 0.90,
             "TEST_SYMPATHETIC": 1},
            (1, 2, 3), (1, 2, 3), (1, 2, 3), (1,),
            Path(folder) / "gap.wav")
    check_common(
        failures, "sympathetic-string gap", result[0], result[2], result[3], result[6])
    if any(tag not in result[0] for tag in (1, 2, 3)):
        return
    hot, resumed, later = (result[0][tag] for tag in (1, 2, 3))
    if rail_energy(hot) <= 0.0:
        failures.append("renderer gap did not seed a passive rail")
    if not 0.0 <= rail_energy(resumed) < rail_energy(hot):
        failures.append("renderer gap did not decay the passive rail")
    if value(resumed, WAVE_FIELDS, "wave_samples") <= value(
            hot, WAVE_FIELDS, "wave_samples"):
        failures.append("renderer gap did not advance passive rail time")
    if value(later, WAVE_FIELDS, "wave_samples") <= value(
            resumed, WAVE_FIELDS, "wave_samples"):
        failures.append("renderer gap did not resume passive processing")
    if all(tag in result[6] for tag in (1, 2, 3)):
        hot_new, resumed_new, later_new = (
            result[6][tag] for tag in (1, 2, 3))
        if value(resumed_new, STRANGE_FIELDS, "passive_level") >= value(
                hot_new, STRANGE_FIELDS, "passive_level"):
            failures.append("renderer gap did not decay passive level")
        for newer, older in ((resumed_new, hot_new), (later_new, resumed_new)):
            for field in ("passive_energy", "passive_peak", "passive_samples"):
                if value(newer, STRANGE_FIELDS, field) < value(
                        older, STRANGE_FIELDS, field):
                    failures.append(
                        "renderer gap reset cumulative {}".format(field))


def check_stopped_release(
    failures: List[str], csound: Path, module: Path, csd: Path,
) -> None:
    with tempfile.TemporaryDirectory(prefix="hlolli-sympathetic-release-") as folder:
        result = run_case(
            failures, "sympathetic-string stopped release", csound, module, csd,
            {"TEST_CASE": 8, "TEST_END": 0.62,
             "TEST_SYMPATHETIC": 1},
            (1,), (1,), (1,), (1,),
            Path(folder) / "stopped-release.wav")
    check_common(
        failures, "sympathetic-string stopped release", result[0], result[2],
        result[3], result[6])
    wave = result[0].get(1)
    string = result[1].get(1)
    strange = result[6].get(1)
    if wave is None or string is None or strange is None:
        return
    if value(string, STRING_FIELDS, "owner") != 0.0:
        failures.append("released stopped string kept its owner")
    if value(strange, STRANGE_FIELDS, "passive_active") != 1.0:
        failures.append("released stopped string did not become passive")
    if value(wave, WAVE_FIELDS, "wave_samples") < 26800.0:
        failures.append("released stopped string skipped passive time")
    if rail_energy(wave) >= 0.01:
        failures.append("stopped-note energy survived the open retune")
    if abs(value(wave, WAVE_FIELDS, "last_bridge_output")) >= 0.05:
        failures.append("stopped-note bridge tail survived the open retune")


def check_faults(
    failures: List[str], csound: Path, module: Path, csd: Path,
) -> None:
    names = (
        "air", "dispersion", "subharmonic", "squeal", "coupling",
        "energy", "passive",
    )
    with tempfile.TemporaryDirectory(prefix="hlolli-sympathetic-fault-") as folder:
        temporary = Path(folder)
        for mode, name in enumerate(names, 1):
            strange = -1 if mode == 1 else 1
            result = run_case(
                failures, "sympathetic-string {} fault".format(name),
                csound, module, csd,
                {"TEST_CASE": 6, "TEST_FAULT": mode,
                 "TEST_STRANGE": strange, "TEST_END": 0.49},
                (1, 2, 3), (1, 2, 3), (1, 2, 3), (),
                temporary / "fault-{}.wav".format(mode))
            check_common(
                failures, "sympathetic-string {} fault".format(name),
                result[0], result[2], result[3], result[6])
            if any(tag not in result[0] or tag not in result[6]
                   for tag in (1, 2, 3)):
                continue
            before, after, later = (result[6][tag] for tag in (1, 2, 3))
            if value(before, STRANGE_FIELDS, "recoveries") != 0.0:
                failures.append("{} fault began with recovery".format(name))
            for label, state in (("after", after), ("later", later)):
                if value(state, STRANGE_FIELDS, "recoveries") != 1.0:
                    failures.append(
                        "{} fault {} snapshot did not recover once".format(
                            name, label))
            before_wave, after_wave, later_wave = (
                result[0][tag] for tag in (1, 2, 3))
            if value(after_wave, WAVE_FIELDS, "reset_count") != value(
                    before_wave, WAVE_FIELDS, "reset_count"):
                failures.append("{} fault reset the physical rail".format(name))
            if value(later_wave, WAVE_FIELDS, "wave_samples") <= value(
                    after_wave, WAVE_FIELDS, "wave_samples"):
                failures.append("{} fault did not resume the rail".format(name))
            if rail_energy(before_wave) <= 0.0 or rail_energy(after_wave) <= 0.0:
                failures.append("{} fault cleared the physical rail".format(name))
            if result[4] is not None and rms(
                    mono(result[4][1], 0.24, 0.44)) <= 1.0:
                failures.append("{} fault did not resume audio".format(name))


def check_stress(
    failures: List[str], csound: Path, module: Path, csd: Path,
) -> None:
    with tempfile.TemporaryDirectory(prefix="hlolli-sympathetic-stress-") as folder:
        result = run_case(
            failures, "sympathetic-string stress", csound, module, csd,
            {"TEST_CASE": 7, "TEST_END": 6.04},
            (1, 2, 3, 4), (1, 2, 3, 4), (1, 2, 3, 4), (1,),
            Path(folder) / "stress.wav", timeout=120)
    check_common(
        failures, "sympathetic-string stress", result[0], result[2], result[3],
        result[6])
    if len(result[0]) < 4:
        return
    signatures = []
    for tag in (1, 2, 3, 4):
        state = result[0][tag]
        if value(state, WAVE_FIELDS, "wave_samples") < 287000.0:
            failures.append("sympathetic-string stress string {} skipped time".format(tag))
        if rail_energy(state) <= 0.0:
            failures.append("sympathetic-string stress string {} had no rail energy".format(
                tag))
        signatures.append((
            round(value(state, WAVE_FIELDS, "toward_nut_signature"), 12),
            round(value(state, WAVE_FIELDS, "toward_bridge_signature"), 12),
        ))
        sympathetic = result[6].get(tag)
        if sympathetic is not None:
            if value(sympathetic, STRANGE_FIELDS, "recoveries") != 0.0:
                failures.append(
                    "sympathetic-string stress string {} recovered".format(tag))
            if value(sympathetic, STRANGE_FIELDS, "samples") <= 0.0:
                failures.append(
                    "sympathetic-string stress string {} skipped kStrange".format(tag))
    if len(set(signatures)) != 4:
        failures.append("sympathetic-string stress strings shared rail state")
    if result[4] is not None and rms(mono(result[4][1], 0.1, 5.9)) <= 1.0:
        failures.append("sympathetic-string stress rendered silence")


def check_block_size(
    failures: List[str], csound: Path, module: Path, csd: Path,
) -> None:
    cases = {}
    with tempfile.TemporaryDirectory(prefix="violin-feedback-blocks-") as folder:
        for block, sympathetic in ((8, 0), (8, 1), (32, 1), (48, 1), (128, 1)):
            path = Path(folder) / f"feedback-{block}-{sympathetic}.wav"
            result = run_csound(csound, module, csd, {
                "TEST_CASE": 11, "TEST_KSMPS": block,
                "TEST_SYMPATHETIC": sympathetic,
            }, path)
            if result.returncode != 0:
                failures.append(result.stdout)
                return
            _, (dry, wet) = read_wav(path)
            cases[block, sympathetic] = (
                dry[24000:46000], wet[24000 + block:46000 + block])
    if cases[8, 0][1] == cases[8, 1][1]:
        failures.append("sympathetic feedback added no wet signal")
    for block in (32, 48, 128):
        if cases[block, 1] != cases[8, 1]:
            failures.append(f"aligned sympathetic PCM changed at ksmps={block}")


def main(arguments: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csound", required=True, type=Path)
    parser.add_argument("--module", required=True, type=Path)
    parser.add_argument("--csd", required=True, type=Path)
    parser.add_argument("--neutral-module", type=Path)
    parser.add_argument("--neutral-csd", type=Path)
    options = parser.parse_args(arguments)
    failures: List[str] = []

    for path, label in ((options.csound, "Csound"),
                        (options.module, "module"),
                        (options.csd, "CSD")):
        if not path.exists():
            parser.error("{} does not exist: {}".format(label, path))
    if options.neutral_module is not None and not options.neutral_module.exists():
        parser.error("neutral module does not exist: {}".format(
            options.neutral_module))
    if options.neutral_csd is not None and not options.neutral_csd.exists():
        parser.error("neutral CSD does not exist: {}".format(
            options.neutral_csd))

    check_neutral_baseline(
        failures, options.csound, options.module,
        options.neutral_module, options.neutral_csd)
    check_sympathetic_response(
        failures, options.csound, options.module, options.csd)
    check_block_size(failures, options.csound, options.module, options.csd)
    check_target_rules(failures, options.csound, options.module, options.csd)
    check_reserved_articulation_coupling(
        failures, options.csound, options.module, options.csd)
    check_strange_audio(failures, options.csound, options.module, options.csd)
    check_low_rate_squeal_bounds(
        failures, options.csound, options.module, options.csd)
    check_handoffs(failures, options.csound, options.module, options.csd)
    check_gap(failures, options.csound, options.module, options.csd)
    check_stopped_release(
        failures, options.csound, options.module, options.csd)
    check_faults(failures, options.csound, options.module, options.csd)
    check_stress(failures, options.csound, options.module, options.csd)

    if failures:
        for failure in failures:
            print("FAIL: {}".format(failure), file=sys.stderr)
        return 1
    print("sympathetic-string and kStrange checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
