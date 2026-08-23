#!/usr/bin/env python3
"""Check measured violin profiles, registry ownership, and neutral sound."""

from __future__ import annotations

import argparse
import math
import re
import struct
import subprocess
import sys
import tempfile
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Mapping, Optional, Sequence, Tuple


State = Tuple[float, ...]
ModeKey = Tuple[int, int]
Channels = Tuple[List[int], List[int]]

PROFILE_FIELDS = (
    "registry_index", "schema_version", "profile_count",
    "validation_count", "mu_zero", "mu_point_one", "bridge_coupling",
    "static_mu", "static_mu_matches_profile", "finite",
)
BODY_FIELDS = (
    "modal_energy", "output_energy_left", "output_energy_right",
    "processed_samples", "finite",
)
MODE_FIELDS = ("frequency", "bandwidth", "gain", "pan", "finite")
MODE_COUNT = 12


@dataclass
class CaseResult:
    completed: subprocess.CompletedProcess[str]
    profiles: Dict[int, State]
    bodies: Dict[int, State]
    modes: Dict[ModeKey, State]
    frames: Optional[bytes]
    channels: Optional[Channels]


def value(state: State, fields: Sequence[str], name: str) -> float:
    return state[fields.index(name)]


def run_csound(
    csound: Path,
    module: Path,
    csd: Path,
    definitions: Mapping[str, object],
    output: Optional[Path] = None,
    timeout: int = 30,
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


def read_modes(output: str) -> Dict[ModeKey, State]:
    modes: Dict[ModeKey, State] = {}
    prefix = "WG_PROFILE_MODE "
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


def read_handles(output: str) -> Optional[Tuple[int, int]]:
    for line in output.splitlines():
        start = line.find("WG_PROFILE_HANDLES ")
        if start < 0:
            continue
        words = line[start:].split()
        if len(words) >= 3:
            return int(float(words[1])), int(float(words[2]))
    return None


def read_tunings(output: str) -> Dict[int, Tuple[float, float]]:
    tunings: Dict[int, Tuple[float, float]] = {}
    prefix = "WG_PROFILE_TUNING "
    for line in output.splitlines():
        start = line.find(prefix)
        if start < 0:
            continue
        words = line[start:].split()
        if len(words) >= 4:
            string = int(float(words[1]))
            tunings[string] = float(words[2]), float(words[3])
    return tunings


def read_owners(output: str) -> Dict[int, int]:
    owners: Dict[int, int] = {}
    prefix = "WG_PROFILE_OWNER "
    for line in output.splitlines():
        start = line.find(prefix)
        if start < 0:
            continue
        words = line[start:].split()
        if len(words) >= 3:
            owners[int(float(words[1]))] = int(float(words[2]))
    return owners


def read_wav(path: Path, sample_rate: int) -> Tuple[bytes, Channels]:
    with wave.open(str(path), "rb") as audio:
        if (audio.getframerate() != sample_rate or
                audio.getnchannels() != 2 or audio.getsampwidth() != 2):
            raise ValueError("unexpected profile-test WAV format")
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
    output: Optional[Path] = None,
    expect_failure: bool = False,
) -> CaseResult:
    completed = run_csound(
        csound, module, csd, definitions, output=output)
    if expect_failure:
        if completed.returncode == 0:
            failures.append("{} was accepted".format(label))
    elif completed.returncode != 0:
        failures.append(
            "{} failed with status {}:\n{}".format(
                label, completed.returncode, completed.stdout.rstrip()))

    ranges = read_out_of_range(completed.stdout)
    if not ranges:
        failures.append("{} did not report output bounds".format(label))
    elif any(ranges):
        failures.append(
            "{} had out-of-range samples {}".format(label, ranges))

    frames = None
    channels = None
    if output is not None and completed.returncode == 0:
        if not output.exists():
            failures.append("{} produced no WAV".format(label))
        else:
            try:
                frames, channels = read_wav(
                    output, int(definitions["TEST_SR"]))
            except (ValueError, wave.Error) as error:
                failures.append("{}: {}".format(label, error))

    return CaseResult(
        completed=completed,
        profiles=read_tagged(
            completed.stdout, "WG_PROFILE", len(PROFILE_FIELDS)),
        bodies=read_tagged(
            completed.stdout, "WG_PROFILE_BODY", len(BODY_FIELDS)),
        modes=read_modes(completed.stdout),
        frames=frames,
        channels=channels,
    )


def close(left: float, right: float, tolerance: float = 2.0e-12) -> bool:
    return math.isclose(left, right, rel_tol=tolerance, abs_tol=tolerance)


def check_profile_state(
    failures: List[str], label: str, state: State,
) -> None:
    if len(state) != len(PROFILE_FIELDS) or not all(map(math.isfinite, state)):
        failures.append("{} returned invalid profile state".format(label))
        return
    if value(state, PROFILE_FIELDS, "schema_version") != 1.0:
        failures.append("{} did not use profile schema 1".format(label))
    if value(state, PROFILE_FIELDS, "profile_count") != 1.0:
        failures.append("{} did not expose the generic profile".format(label))
    if value(state, PROFILE_FIELDS, "validation_count") != 1.0:
        failures.append("{} did not validate the registry once".format(label))
    if value(state, PROFILE_FIELDS, "finite") != 1.0:
        failures.append("{} reported invalid embedded data".format(label))
    mu_zero = value(state, PROFILE_FIELDS, "mu_zero")
    mu_point_one = value(state, PROFILE_FIELDS, "mu_point_one")
    coupling = value(state, PROFILE_FIELDS, "bridge_coupling")
    static_mu = value(state, PROFILE_FIELDS, "static_mu")
    if not (0.0 < mu_point_one < mu_zero <= 2.0):
        failures.append("{} exposed an invalid friction curve".format(label))
    if not (0.0 < coupling < 0.1):
        failures.append("{} exposed an invalid bridge coupling".format(label))
    if not (0.0 < static_mu <= 2.5):
        failures.append("{} exposed an invalid static friction".format(label))


def check_static_mu_binding(
    failures: List[str], label: str, state: Optional[State],
) -> None:
    if state is None or len(state) != len(PROFILE_FIELDS):
        return
    found = value(state, PROFILE_FIELDS, "static_mu_matches_profile")
    if found != 1.0:
        failures.append(
            "{} does not match the fixed model static friction".format(label))


def check_body_state(failures: List[str], label: str, state: State) -> None:
    if len(state) != len(BODY_FIELDS) or not all(map(math.isfinite, state)):
        failures.append("{} returned invalid body state".format(label))
        return
    if value(state, BODY_FIELDS, "finite") != 1.0:
        failures.append("{} reported a non-finite body".format(label))
    if value(state, BODY_FIELDS, "processed_samples") <= 0.0:
        failures.append("{} did not run the body".format(label))


def check_modes(
    failures: List[str], label: str, modes: Mapping[ModeKey, State], tag: int,
) -> None:
    for mode_number in range(1, MODE_COUNT + 1):
        state = modes.get((tag, mode_number))
        if state is None:
            failures.append("{} missed body mode {}".format(label, mode_number))
            continue
        if len(state) != len(MODE_FIELDS) or not all(map(math.isfinite, state)):
            failures.append("{} mode {} was not finite".format(
                label, mode_number))
            continue
        frequency = value(state, MODE_FIELDS, "frequency")
        bandwidth = value(state, MODE_FIELDS, "bandwidth")
        gain = value(state, MODE_FIELDS, "gain")
        pan = value(state, MODE_FIELDS, "pan")
        finite = value(state, MODE_FIELDS, "finite")
        if not (20.0 <= frequency < 20000.0 and bandwidth > 0.0 and
                gain >= 0.0 and abs(pan) <= 1.0 and finite == 1.0):
            failures.append("{} mode {} was out of range".format(
                label, mode_number))


def check_render(
    failures: List[str], label: str, result: CaseResult,
) -> None:
    if result.completed.returncode != 0:
        return
    if 1 not in result.profiles:
        failures.append("{} printed no profile state".format(label))
    else:
        check_profile_state(failures, label, result.profiles[1])
    if 1 not in result.bodies:
        failures.append("{} printed no body state".format(label))
    else:
        check_body_state(failures, label, result.bodies[1])
        energy = (
            value(result.bodies[1], BODY_FIELDS, "output_energy_left") +
            value(result.bodies[1], BODY_FIELDS, "output_energy_right"))
        if energy <= 1.0e-12:
            failures.append("{} made no wet body output".format(label))
    check_modes(failures, label, result.modes, 1)
    if result.frames is None or result.channels is None:
        failures.append("{} had no readable audio".format(label))
    elif not result.frames or max(
            max(abs(item) for item in result.channels[0]),
            max(abs(item) for item in result.channels[1])) < 4:
        failures.append("{} rendered silence".format(label))


def compare_exact(
    failures: List[str], label: str,
    reference: CaseResult, actual: CaseResult,
) -> None:
    if reference.frames != actual.frames:
        failures.append("{} changed PCM".format(label))
    if reference.profiles != actual.profiles:
        failures.append("{} changed profile probe state".format(label))
    if reference.bodies != actual.bodies:
        failures.append("{} changed body probe state".format(label))
    if reference.modes != actual.modes:
        failures.append("{} changed modal probe state".format(label))


def check_isolation(
    failures: List[str], label: str, result: CaseResult, driven_tag: int,
) -> None:
    if result.completed.returncode != 0:
        return
    if set(result.profiles) != {1, 2}:
        failures.append("{} missed a profile probe".format(label))
        return
    for tag, state in result.profiles.items():
        check_profile_state(failures, "{} handle {}".format(label, tag), state)
    check_static_mu_binding(
        failures, "{} generic handle".format(label), result.profiles.get(1))
    for tag in (1, 2):
        check_modes(failures, "{} handle {}".format(label, tag), result.modes, tag)
        if tag not in result.bodies:
            failures.append("{} missed body {}".format(label, tag))
            continue
        check_body_state(
            failures, "{} handle {}".format(label, tag), result.bodies[tag])
    if set(result.bodies) != {1, 2}:
        return
    quiet_tag = 2 if driven_tag == 1 else 1
    driven_energy = (
        value(result.bodies[driven_tag], BODY_FIELDS, "output_energy_left") +
        value(result.bodies[driven_tag], BODY_FIELDS, "output_energy_right"))
    quiet_energy = (
        value(result.bodies[quiet_tag], BODY_FIELDS, "output_energy_left") +
        value(result.bodies[quiet_tag], BODY_FIELDS, "output_energy_right"))
    if driven_energy <= 1.0e-12:
        failures.append("{} did not excite its driven handle".format(label))
    if abs(quiet_energy) > 1.0e-18:
        failures.append("{} leaked {:.17g} into the quiet handle".format(
            label, quiet_energy))


def check_invalid_ids(
    failures: List[str], csound: Path, module: Path, csd: Path,
) -> None:
    for label, profile_id in (
        ("unknown profile", "missing_violin"),
        ("empty profile", ""),
        ("wrong-case profile", "Generic_Violin"),
    ):
        result = run_case(
            failures,
            label,
            csound,
            module,
            csd,
            {
                "TEST_CASE": 3,
                "TEST_INVALID": 1,
                "TEST_BAD_PROFILE": profile_id,
                "TEST_SR": 48000,
                "TEST_KSMPS": 32,
            },
            expect_failure=True,
        )
        wanted = 'unknown profile "{}"'.format(profile_id)
        if wanted not in result.completed.stdout:
            failures.append("{} lacked {!r}".format(label, wanted))
        handles = read_handles(result.completed.stdout)
        if handles != (1, 2):
            failures.append(
                "{} consumed a handle: found {!r}".format(label, handles))
        if set(result.profiles) != {1, 2}:
            failures.append("{} did not probe both valid handles".format(label))
        else:
            for tag, state in result.profiles.items():
                check_profile_state(
                    failures, "{} valid handle {}".format(label, tag), state)
                check_static_mu_binding(
                    failures,
                    "{} valid generic handle {}".format(label, tag),
                    state,
                )
            if result.profiles[1] != result.profiles[2]:
                failures.append(
                    "{} changed the generic profile around the failure".format(
                        label))


def check_tuned_result(
    failures: List[str], label: str, result: CaseResult,
    reference_pitch_hz: float,
) -> None:
    if result.completed.returncode != 0:
        return
    base = (
        195.99771799087463,
        293.66476791740757,
        440.0,
        659.2551138257398,
    )
    tunings = read_tunings(result.completed.stdout)
    if set(tunings) != {1, 2, 3, 4}:
        failures.append("{} missed tuned open strings".format(label))
    else:
        for string, a440 in enumerate(base, 1):
            frequency, finite = tunings[string]
            wanted = a440 * reference_pitch_hz / 440.0
            if not close(frequency, wanted, 2.0e-14):
                failures.append(
                    "{} string {} used {:.17g}, wanted {:.17g}".format(
                        label, string, frequency, wanted))
            if finite != 1.0:
                failures.append(
                    "{} string {} reported invalid tuning".format(
                        label, string))
    owners = read_owners(result.completed.stdout)
    if set(owners) != {1, 2, 3, 4}:
        failures.append("{} missed automatic-string ownership".format(label))
    elif not (owners[3] > 0 and owners[1] == 0 and
              owners[2] == 0 and owners[4] == 0):
        failures.append(
            "{} chose wrong tuned string owners {!r}".format(label, owners))
    if result.frames is None or result.channels is None:
        failures.append("{} returned no tuned audio".format(label))
    elif not result.frames or max(
            max(abs(item) for item in result.channels[0]),
            max(abs(item) for item in result.channels[1])) < 4:
        failures.append("{} rendered tuned silence".format(label))


def check_invalid_references(
    failures: List[str], csound: Path, module: Path, csd: Path,
) -> None:
    for reference in (0.0, 379.999, 480.001):
        label = "invalid reference {:.17g}".format(reference)
        result = run_case(
            failures,
            label,
            csound,
            module,
            csd,
            {
                "TEST_CASE": 5,
                "TEST_INVALID": 1,
                "TEST_REFERENCE_PITCH": "{:.17g}".format(reference),
                "TEST_SR": 48000,
                "TEST_KSMPS": 32,
            },
            expect_failure=True,
        )
        if "reference pitch must be from 380 to 480 Hz" not in (
                result.completed.stdout):
            failures.append("{} lacked its range error".format(label))
        handles = read_handles(result.completed.stdout)
        if handles != (1, 2):
            failures.append(
                "{} consumed a handle: found {!r}".format(label, handles))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csound", required=True, type=Path)
    parser.add_argument("--module", required=True, type=Path)
    parser.add_argument("--csd", required=True, type=Path)
    args = parser.parse_args()

    failures: List[str] = []
    configurations = ((48000, 32), (44100, 16))
    with tempfile.TemporaryDirectory(prefix="hlolli-wg-violin-profile-") as tmp:
        temp = Path(tmp)
        primary_generic: Optional[CaseResult] = None
        for sample_rate, ksmps in configurations:
            common = {
                "TEST_CASE": 1,
                "TEST_SR": sample_rate,
                "TEST_KSMPS": ksmps,
            }
            default = run_case(
                failures,
                "default at {}/{}".format(sample_rate, ksmps),
                args.csound,
                args.module,
                args.csd,
                {**common, "TEST_DEFAULT": 1},
                output=temp / "default-{}-{}.wav".format(sample_rate, ksmps),
            )
            generic = run_case(
                failures,
                "named generic at {}/{}".format(sample_rate, ksmps),
                args.csound,
                args.module,
                args.csd,
                {**common, "TEST_PROFILE": "generic_violin"},
                output=temp / "generic-{}-{}.wav".format(sample_rate, ksmps),
            )
            for label, result in (
                ("default at {}/{}".format(sample_rate, ksmps), default),
                ("named generic at {}/{}".format(sample_rate, ksmps), generic),
            ):
                check_render(failures, label, result)
            check_static_mu_binding(
                failures,
                "default at {}/{}".format(sample_rate, ksmps),
                default.profiles.get(1),
            )
            check_static_mu_binding(
                failures,
                "named generic at {}/{}".format(sample_rate, ksmps),
                generic.profiles.get(1),
            )
            compare_exact(
                failures,
                "default versus named generic at {}/{}".format(
                    sample_rate, ksmps),
                default,
                generic,
            )
            if sample_rate == 48000 and ksmps == 32:
                primary_generic = generic

        if primary_generic is not None:
            repeat_common = {
                "TEST_CASE": 1,
                "TEST_SR": 48000,
                "TEST_KSMPS": 32,
            }
            repeat_generic = run_case(
                failures,
                "generic repeat",
                args.csound,
                args.module,
                args.csd,
                {**repeat_common, "TEST_PROFILE": "generic_violin"},
                output=temp / "generic-repeat.wav",
            )
            check_render(failures, "generic repeat", repeat_generic)
            check_static_mu_binding(
                failures, "generic repeat", repeat_generic.profiles.get(1))
            compare_exact(
                failures, "generic repeat", primary_generic, repeat_generic)

        isolation_results: List[CaseResult] = []
        for variant, driven_tag in ((0, 1), (1, 2)):
            result = run_case(
                failures,
                "dual-handle isolation {}".format(driven_tag),
                args.csound,
                args.module,
                args.csd,
                {
                    "TEST_CASE": 2,
                    "TEST_DUAL": 1,
                    "TEST_VARIANT": variant,
                    "TEST_SR": 48000,
                    "TEST_KSMPS": 32,
                },
            )
            check_isolation(
                failures,
                "dual-handle isolation {}".format(driven_tag),
                result,
                driven_tag,
            )
            isolation_results.append(result)
        if len(isolation_results) == 2:
            if isolation_results[0].profiles != isolation_results[1].profiles:
                failures.append("driving a handle changed the profile registry state")
            if isolation_results[0].modes != isolation_results[1].modes:
                failures.append("driving a handle changed its profile mode table")

        check_invalid_ids(failures, args.csound, args.module, args.csd)
        check_invalid_references(failures, args.csound, args.module, args.csd)

        for variant, note in ((0, "open"), (1, "harmonic")):
            tuned_results: List[CaseResult] = []
            for constructor in ("default", "named"):
                definitions = {
                    "TEST_CASE": 4,
                    "TEST_VARIANT": variant,
                    "TEST_REFERENCE_PITCH": 442,
                    "TEST_SR": 48000,
                    "TEST_KSMPS": 32,
                }
                if constructor == "default":
                    definitions["TEST_TUNED_DEFAULT"] = 1
                else:
                    definitions["TEST_TUNED_NAMED"] = 1
                    definitions["TEST_PROFILE"] = "generic_violin"
                label = "{} tuned {} constructor".format(note, constructor)
                result = run_case(
                    failures,
                    label,
                    args.csound,
                    args.module,
                    args.csd,
                    definitions,
                    output=temp / "tuned-{}-{}.wav".format(
                        note, constructor),
                )
                check_tuned_result(failures, label, result, 442.0)
                tuned_results.append(result)
            if len(tuned_results) == 2:
                compare_exact(
                    failures,
                    "{} tuned default versus named".format(note),
                    tuned_results[0],
                    tuned_results[1],
                )

    if failures:
        for failure in failures:
            print("FAIL: {}".format(failure), file=sys.stderr)
        return 1
    print(
        "profile checks passed: IDs, generated data, neutral generic, "
        "repeatability, isolation, and registry life")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
