#!/usr/bin/env python3
"""Check private realism mutes without changing the normal opcode API."""

from __future__ import annotations

import argparse
import hashlib
import math
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import wave


CASES = {
    "baseline": (1, 1, 1, 1),
    "no-finger": (0, 1, 1, 1),
    "no-fingerboard": (1, 0, 1, 1),
    "no-rosin": (1, 1, 0, 1),
    "no-mechanical": (1, 1, 1, 0),
    "no-secondary-noise": (0, 0, 0, 0),
}


def render(
    csound: Path,
    module: Path,
    csd: Path,
    output: Path,
    gains: tuple[float, float, float, float],
    *,
    mode: str = "phrase",
    direct_gain: float = 1,
    body_gain: float = 1,
    body: float = 0.72,
) -> subprocess.CompletedProcess[str]:
    macros = {
        "DIAG_MODE": mode,
        "DIAG_STRING": "3",
        "DIAG_FINGER_GAIN": gains[0],
        "DIAG_BOARD_GAIN": gains[1],
        "DIAG_ROSIN_GAIN": gains[2],
        "DIAG_MECHANICAL_GAIN": gains[3],
        "DIAG_NUT_CUTOFF_SCALE": 1,
        "DIAG_BRIDGE_CUTOFF_SCALE": 1,
        "DIAG_DIRECT_GAIN": direct_gain,
        "DIAG_BODY_GAIN": body_gain,
        "DIAG_BODY": body,
    }
    command = [
        str(csound),
        "--opcode-lib={}".format(module),
        "--sample-accurate",
        "--num-threads=1",
        "-W",
        "-s",
        "--nopeaks",
        "-o",
        str(output),
    ]
    command.extend(
        "--omacro:{}={}".format(name, value)
        for name, value in macros.items()
    )
    command.append(str(csd))
    return subprocess.run(
        command,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        timeout=45,
    )


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def wav_facts(path: Path) -> tuple[int, int, int, int]:
    with wave.open(str(path), "rb") as stream:
        return (
            stream.getnchannels(),
            stream.getsampwidth(),
            stream.getframerate(),
            stream.getnframes(),
        )


def steady_dc_ratio(path: Path, start: float, end: float) -> float:
    with wave.open(str(path), "rb") as stream:
        if stream.getsampwidth() != 2:
            raise ValueError("dynamic-force probe is not PCM16")
        first = round(start * stream.getframerate())
        count = round((end - start) * stream.getframerate())
        stream.setpos(first)
        data = stream.readframes(count)
        samples = struct.unpack("<{}h".format(len(data) // 2), data)
    scaled = [sample / 32768.0 for sample in samples]
    mean = sum(scaled) / len(scaled)
    rms = math.sqrt(sum(sample * sample for sample in scaled) / len(scaled))
    return abs(mean) / max(rms, 1.0e-12)


def window_rms(path: Path, start: float, end: float) -> float:
    with wave.open(str(path), "rb") as stream:
        if stream.getsampwidth() != 2 or stream.getnchannels() != 2:
            raise ValueError("release probe is not stereo PCM16")
        first = round(start * stream.getframerate())
        count = round((end - start) * stream.getframerate())
        stream.setpos(first)
        data = stream.readframes(count)
    samples = struct.unpack("<{}h".format(len(data) // 2), data)
    mono = [0.5 * (samples[index] + samples[index + 1]) / 32768.0
            for index in range(0, len(samples), 2)]
    return math.sqrt(sum(sample * sample for sample in mono) / len(mono))


def window_brightness(path: Path, start: float, end: float) -> float:
    with wave.open(str(path), "rb") as stream:
        if stream.getsampwidth() != 2 or stream.getnchannels() != 2:
            raise ValueError("release probe is not stereo PCM16")
        first = round(start * stream.getframerate())
        count = round((end - start) * stream.getframerate())
        stream.setpos(first)
        data = stream.readframes(count)
    samples = struct.unpack("<{}h".format(len(data) // 2), data)
    mono = [0.5 * (samples[index] + samples[index + 1]) / 32768.0
            for index in range(0, len(samples), 2)]
    signal_rms = math.sqrt(
        sum(sample * sample for sample in mono) / len(mono))
    difference_rms = math.sqrt(
        sum((mono[index] - mono[index - 1]) ** 2
            for index in range(1, len(mono))) / (len(mono) - 1))
    return difference_rms / max(signal_rms, 1.0e-12)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--csound", required=True, type=Path)
    parser.add_argument("--module", required=True, type=Path)
    parser.add_argument("--csd", required=True, type=Path)
    return parser.parse_args()


def main() -> int:
    arguments = parse_args()
    failures: list[str] = []
    with tempfile.TemporaryDirectory(prefix="hwa-realism-diagnostic-") as name:
        directory = Path(name)
        outputs: dict[str, Path] = {}
        for label, gains in CASES.items():
            output = directory / "{}.wav".format(label)
            completed = render(
                arguments.csound,
                arguments.module,
                arguments.csd,
                output,
                gains,
            )
            if completed.returncode != 0:
                failures.append(
                    "{} failed:\n{}".format(label, completed.stdout.rstrip())
                )
                continue
            outputs[label] = output

        if "baseline" in outputs:
            expected_facts = (2, 2, 44100, 176416)
            for label, output in outputs.items():
                try:
                    facts = wav_facts(output)
                except (OSError, wave.Error) as error:
                    failures.append("{} WAV failed: {}".format(label, error))
                    continue
                if facts != expected_facts:
                    failures.append(
                        "{} returned WAV facts {}, expected {}".format(
                            label, facts, expected_facts
                        )
                    )

            repeat = directory / "baseline-repeat.wav"
            completed = render(
                arguments.csound,
                arguments.module,
                arguments.csd,
                repeat,
                CASES["baseline"],
            )
            if completed.returncode != 0:
                failures.append("baseline repeat failed")
            elif digest(repeat) != digest(outputs["baseline"]):
                failures.append("baseline render was not byte-exact")

            baseline_digest = digest(outputs["baseline"])
            for label in (
                "no-finger",
                "no-rosin",
                "no-mechanical",
                "no-secondary-noise",
            ):
                if label in outputs and digest(outputs[label]) == baseline_digest:
                    failures.append("{} did not change the audio".format(label))

        dynamic_probe = directory / "dynamic-force-probe.wav"
        completed = render(
            arguments.csound,
            arguments.module,
            arguments.csd,
            dynamic_probe,
            CASES["baseline"],
            mode="open",
            direct_gain=1,
            body_gain=0,
        )
        if completed.returncode != 0:
            failures.append("dynamic bridge-force probe failed")
        else:
            ratio = steady_dc_ratio(dynamic_probe, 0.50, 2.70)
            if ratio >= 0.01:
                failures.append(
                    "steady dynamic-force DC/RMS ratio {:.6f} exceeded "
                    "0.01".format(ratio)
                )

        release_direct = directory / "release-direct.wav"
        release_direct_bright = directory / "release-direct-bright.wav"
        release_body = directory / "release-body.wav"
        direct_completed = render(
            arguments.csound,
            arguments.module,
            arguments.csd,
            release_direct,
            CASES["baseline"],
            mode="open",
            direct_gain=1,
            body_gain=0,
        )
        bright_completed = render(
            arguments.csound,
            arguments.module,
            arguments.csd,
            release_direct_bright,
            CASES["baseline"],
            mode="open",
            direct_gain=15,
            body_gain=0,
        )
        body_completed = render(
            arguments.csound,
            arguments.module,
            arguments.csd,
            release_body,
            CASES["baseline"],
            mode="open",
            direct_gain=0,
            body_gain=1,
        )
        if (direct_completed.returncode != 0 or
                bright_completed.returncode != 0 or
                body_completed.returncode != 0):
            failures.append("release balance probe failed")
        else:
            direct_held = window_rms(release_direct, 2.50, 2.75)
            body_held = window_rms(release_body, 2.50, 2.75)
            if direct_held < 0.5 * body_held:
                failures.append(
                    "direct string RMS {:.6f} fell below 50 percent of body "
                    "RMS {:.6f}".format(direct_held, body_held)
                )
            if direct_held > 1.5 * body_held:
                failures.append(
                    "direct string RMS {:.6f} exceeded 150 percent of body "
                    "RMS {:.6f}".format(direct_held, body_held)
                )
            bright_held = window_rms(
                release_direct_bright, 2.50, 2.75)
            if bright_held < 1.0e-4:
                failures.append("direct brightness probe was silent")
            else:
                held_brightness = window_brightness(
                    release_direct_bright, 2.50, 2.75)
                later_brightness = window_brightness(
                    release_direct_bright, 3.12, 3.22)
                if later_brightness > 0.45 * held_brightness:
                    failures.append(
                        "release brightness fell only from {:.6f} to "
                        "{:.6f}".format(held_brightness, later_brightness)
                    )
            if window_rms(release_body, 3.50, 3.75) < 5.0e-6:
                failures.append("body release tail fell below the noise floor")

        invalid = render(
            arguments.csound,
            arguments.module,
            arguments.csd,
            directory / "invalid.wav",
            (-0.01, 1, 1, 1),
        )
        if invalid.returncode == 0:
            failures.append("an invalid diagnostic gain was accepted")

    if failures:
        print("FAIL: realism diagnostic", file=sys.stderr)
        for failure in failures:
            print("- {}".format(failure), file=sys.stderr)
        return 1
    print("PASS: private realism component mutes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
