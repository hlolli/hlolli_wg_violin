#!/usr/bin/env python3
"""Render and measure private realism diagnostics for the violin model."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile
import wave


COMPONENT_CASES = (
    ("baseline", (1.0, 1.0, 1.0, 1.0)),
    ("no-finger", (0.0, 1.0, 1.0, 1.0)),
    ("no-fingerboard", (1.0, 0.0, 1.0, 1.0)),
    ("no-rosin", (1.0, 1.0, 0.0, 1.0)),
    ("no-mechanical", (1.0, 1.0, 1.0, 0.0)),
    ("no-secondary-noise", (0.0, 0.0, 0.0, 0.0)),
)

OPEN_STRINGS = (
    ("g3", 1, 195.997717990875),
    ("d4", 2, 293.664767917408),
    ("a4", 3, 440.0),
    ("e5", 4, 659.255113825740),
)


def entry_exists(path: Path) -> bool:
    try:
        path.lstat()
    except FileNotFoundError:
        return False
    return True


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while True:
            block = stream.read(1024 * 1024)
            if not block:
                break
            digest.update(block)
    return digest.hexdigest()


def run_checked(command: list[str], environment: dict[str, str]) -> str:
    completed = subprocess.run(
        command,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        env=environment,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            "command failed ({}):\n{}".format(
                " ".join(command), completed.stdout
            )
        )
    return completed.stdout


def render(
    csound: Path,
    module: Path,
    csd: Path,
    output: Path,
    macros: dict[str, str],
    environment: dict[str, str],
) -> None:
    command = [
        str(csound),
        f"--opcode-lib={module}",
        "--sample-accurate",
        "--num-threads=1",
        "-W",
        "-s",
        "--nopeaks",
        "-o",
        str(output),
    ]
    command.extend(f"--omacro:{key}={value}" for key, value in macros.items())
    command.append(str(csd))
    run_checked(command, environment)
    if not output.is_file() or output.stat().st_size <= 44:
        raise RuntimeError(f"render did not create WAVE audio: {output}")


def inspect(analyzer: Path, path: Path, environment: dict[str, str]) -> dict:
    output = run_checked(
        [str(analyzer), "--json", "inspect", str(path)], environment
    )
    try:
        report = json.loads(output)
    except json.JSONDecodeError as error:
        raise RuntimeError(f"analyzer returned invalid JSON for {path}") from error
    return report["file"]


def spectrum_value(report: dict, name: str) -> float:
    for row in report["spectrum"]["band_power"]:
        if row["name"] == name:
            return float(row["value"])
    raise RuntimeError(f"analyzer omitted spectrum band: {name}")


def report_metrics(report: dict) -> dict[str, float]:
    channels = report["channels"]
    rms = math.sqrt(
        sum(float(channel["rms"]) ** 2 for channel in channels)
        / len(channels)
    )
    return {
        "rms": rms,
        "integrated_lufs": float(report["loudness"]["integrated_lufs"]),
        "centroid_hz": float(report["spectrum"]["centroid_hz"]),
        "rolloff_85_hz": float(report["spectrum"]["rolloff_85_hz"]),
        "flatness": float(report["spectrum"]["flatness"]),
        "mean_flux": float(report["spectrum"]["mean_flux"]),
        "power_4_8khz": spectrum_value(report, "4-8 kHz"),
        "power_8_16khz": spectrum_value(report, "8-16 kHz"),
    }


def pcm16_difference(reference: Path, candidate: Path) -> tuple[float, float]:
    with wave.open(str(reference), "rb") as first, wave.open(
        str(candidate), "rb"
    ) as second:
        facts = (
            first.getnchannels(),
            first.getsampwidth(),
            first.getframerate(),
            first.getnframes(),
        )
        other_facts = (
            second.getnchannels(),
            second.getsampwidth(),
            second.getframerate(),
            second.getnframes(),
        )
        if facts != other_facts or facts[1] != 2:
            raise RuntimeError("diagnostic renders do not share PCM16 facts")
        square_sum = 0.0
        peak = 0
        sample_count = 0
        while True:
            left = first.readframes(4096)
            right = second.readframes(4096)
            if not left and not right:
                break
            if len(left) != len(right) or len(left) % 2 != 0:
                raise RuntimeError("diagnostic renders have unequal sample data")
            count = len(left) // 2
            left_values = struct.unpack(f"<{count}h", left)
            right_values = struct.unpack(f"<{count}h", right)
            for left_value, right_value in zip(left_values, right_values):
                difference = left_value - right_value
                square_sum += difference * difference
                peak = max(peak, abs(difference))
            sample_count += count
    if sample_count == 0:
        raise RuntimeError("diagnostic render is empty")
    return math.sqrt(square_sum / sample_count) / 32768.0, peak / 32768.0


def write_pcm16_excerpt(
    source: Path,
    destination: Path,
    duration_seconds: float,
    start_seconds: float | None,
) -> None:
    with wave.open(str(source), "rb") as input_stream:
        channels = input_stream.getnchannels()
        sample_width = input_stream.getsampwidth()
        sample_rate = input_stream.getframerate()
        frame_count = input_stream.getnframes()
        if sample_width != 2 or channels < 1 or sample_rate < 1:
            raise RuntimeError(f"expected PCM16 WAVE input: {source}")
        excerpt_frames = round(duration_seconds * sample_rate)
        if start_seconds is None:
            start_frame = (frame_count - excerpt_frames) // 2
        else:
            start_frame = round(start_seconds * sample_rate)
        if (
            excerpt_frames < 1
            or start_frame < 0
            or start_frame + excerpt_frames > frame_count
        ):
            raise RuntimeError(f"excerpt lies outside WAVE input: {source}")
        input_stream.setpos(start_frame)
        audio = input_stream.readframes(excerpt_frames)
        if len(audio) != excerpt_frames * channels * sample_width:
            raise RuntimeError(f"short WAVE excerpt read: {source}")
        parameters = input_stream.getparams()
    with wave.open(str(destination), "wb") as output_stream:
        output_stream.setparams(parameters)
        output_stream.setnframes(excerpt_frames)
        output_stream.writeframes(audio)


def parse_args() -> argparse.Namespace:
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser()
    parser.add_argument("--csound", required=True, type=Path)
    parser.add_argument("--module", required=True, type=Path)
    parser.add_argument("--analyzer", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    for name, _, _ in OPEN_STRINGS:
        parser.add_argument(f"--reference-{name}", required=True, type=Path)
    parser.add_argument(
        "--csd", type=Path, default=root / "examples" / "realism_diagnostic.csd"
    )
    parser.add_argument(
        "--caprice-csd",
        type=Path,
        default=root / "examples" / "paganini_caprice_24.csd",
    )
    parser.add_argument("--library-path", type=Path)
    return parser.parse_args()


def run(arguments: argparse.Namespace) -> None:
    required_files = (
        arguments.csound,
        arguments.module,
        arguments.analyzer,
        arguments.csd,
        arguments.caprice_csd,
        *(getattr(arguments, f"reference_{name}") for name, _, _ in OPEN_STRINGS),
    )
    for path in required_files:
        if not path.is_file():
            raise ValueError(f"missing regular file: {path}")
    output_dir = arguments.output_dir.absolute()
    if entry_exists(output_dir):
        raise ValueError(f"output path already exists: {output_dir}")
    if not output_dir.parent.is_dir():
        raise ValueError(f"missing output parent: {output_dir.parent}")

    environment = os.environ.copy()
    if arguments.library_path is not None:
        if not arguments.library_path.is_dir():
            raise ValueError(
                f"missing library directory: {arguments.library_path}"
            )
        if sys.platform == "darwin":
            variable = "DYLD_LIBRARY_PATH"
        elif sys.platform.startswith("win"):
            variable = "PATH"
        else:
            variable = "LD_LIBRARY_PATH"
        old_value = environment.get(variable)
        environment[variable] = str(arguments.library_path)
        if old_value:
            environment[variable] += os.pathsep + old_value

    temporary = Path(
        tempfile.mkdtemp(prefix=f".{output_dir.name}.tmp-", dir=output_dir.parent)
    )
    try:
        phrase_dir = temporary / "phrase"
        caprice_dir = temporary / "caprice"
        open_dir = temporary / "open-strings"
        phrase_dir.mkdir()
        caprice_dir.mkdir()
        open_dir.mkdir()
        phrase_reports: dict[str, dict] = {}
        phrase_paths: dict[str, Path] = {}
        for name, gains in COMPONENT_CASES:
            path = phrase_dir / f"{name}.wav"
            macros = {
                "DIAG_MODE": "phrase",
                "DIAG_STRING": "3",
                "DIAG_FINGER_GAIN": str(gains[0]),
                "DIAG_BOARD_GAIN": str(gains[1]),
                "DIAG_ROSIN_GAIN": str(gains[2]),
                "DIAG_MECHANICAL_GAIN": str(gains[3]),
                "DIAG_NUT_CUTOFF_SCALE": "1",
                "DIAG_BRIDGE_CUTOFF_SCALE": "1",
            }
            render(
                arguments.csound,
                arguments.module,
                arguments.csd,
                path,
                macros,
                environment,
            )
            phrase_paths[name] = path
            phrase_reports[name] = inspect(arguments.analyzer, path, environment)

        repeat_path = phrase_dir / ".baseline-repeat.wav"
        render(
            arguments.csound,
            arguments.module,
            arguments.csd,
            repeat_path,
            {
                "DIAG_MODE": "phrase",
                "DIAG_STRING": "3",
                "DIAG_FINGER_GAIN": "1",
                "DIAG_BOARD_GAIN": "1",
                "DIAG_ROSIN_GAIN": "1",
                "DIAG_MECHANICAL_GAIN": "1",
                "DIAG_NUT_CUTOFF_SCALE": "1",
                "DIAG_BRIDGE_CUTOFF_SCALE": "1",
            },
            environment,
        )
        if sha256(repeat_path) != sha256(phrase_paths["baseline"]):
            raise RuntimeError("baseline diagnostic render is not deterministic")
        repeat_path.unlink()

        baseline_metrics = report_metrics(phrase_reports["baseline"])
        component_rows = []
        for name, _ in COMPONENT_CASES:
            metrics = report_metrics(phrase_reports[name])
            difference_rms, difference_peak = pcm16_difference(
                phrase_paths["baseline"], phrase_paths[name]
            )
            row: dict[str, object] = {
                "case": name,
                **metrics,
                "difference_rms": difference_rms,
                "difference_peak": difference_peak,
                "centroid_change_hz": (
                    metrics["centroid_hz"] - baseline_metrics["centroid_hz"]
                ),
                "flatness_ratio": (
                    metrics["flatness"] / baseline_metrics["flatness"]
                ),
                "flux_ratio": metrics["mean_flux"]
                / baseline_metrics["mean_flux"],
                "power_4_8khz_ratio": metrics["power_4_8khz"]
                / baseline_metrics["power_4_8khz"],
            }
            component_rows.append(row)

        caprice_reports: dict[str, dict] = {}
        caprice_paths: dict[str, Path] = {}
        for name, gains in COMPONENT_CASES:
            path = caprice_dir / f"{name}.wav"
            render(
                arguments.csound,
                arguments.module,
                arguments.caprice_csd,
                path,
                {
                    "REALISM_DIAGNOSTIC": "1",
                    "DIAG_FINGER_GAIN": str(gains[0]),
                    "DIAG_BOARD_GAIN": str(gains[1]),
                    "DIAG_ROSIN_GAIN": str(gains[2]),
                    "DIAG_MECHANICAL_GAIN": str(gains[3]),
                    "DIAG_LOSS_CUTOFF_SCALE": "1",
                    "GUIDE_LEVEL": "0",
                    "SHOW_MARKS": "0",
                },
                environment,
            )
            caprice_paths[name] = path
            caprice_reports[name] = inspect(arguments.analyzer, path, environment)

        caprice_baseline = report_metrics(caprice_reports["baseline"])
        caprice_rows = []
        for name, _ in COMPONENT_CASES:
            metrics = report_metrics(caprice_reports[name])
            difference_rms, difference_peak = pcm16_difference(
                caprice_paths["baseline"], caprice_paths[name]
            )
            caprice_rows.append(
                {
                    "case": name,
                    **metrics,
                    "difference_rms": difference_rms,
                    "difference_peak": difference_peak,
                    "centroid_change_hz": metrics["centroid_hz"]
                    - caprice_baseline["centroid_hz"],
                    "flatness_ratio": metrics["flatness"]
                    / caprice_baseline["flatness"],
                    "flux_ratio": metrics["mean_flux"]
                    / caprice_baseline["mean_flux"],
                    "power_4_8khz_ratio": metrics["power_4_8khz"]
                    / caprice_baseline["power_4_8khz"],
                }
            )

        open_rows = []
        for name, string, frequency in OPEN_STRINGS:
            model_path = open_dir / f"model-{name}.wav"
            render(
                arguments.csound,
                arguments.module,
                arguments.csd,
                model_path,
                {
                    "DIAG_MODE": "open",
                    "DIAG_STRING": str(string),
                    "DIAG_FREQUENCY": str(frequency),
                },
                environment,
            )
            reference_path = getattr(arguments, f"reference_{name}")
            model_held_path = open_dir / f"model-held-{name}.wav"
            reference_held_path = open_dir / f"reference-held-{name}.wav"
            write_pcm16_excerpt(model_path, model_held_path, 1.5, 1.0)
            write_pcm16_excerpt(
                reference_path, reference_held_path, 1.5, None
            )
            model_report = inspect(
                arguments.analyzer, model_held_path, environment
            )
            reference_report = inspect(
                arguments.analyzer, reference_held_path, environment
            )
            model_metrics = report_metrics(model_report)
            reference_metrics = report_metrics(reference_report)
            centroid_ratio = (
                model_metrics["centroid_hz"]
                / reference_metrics["centroid_hz"]
            )
            rolloff_ratio = (
                model_metrics["rolloff_85_hz"]
                / reference_metrics["rolloff_85_hz"]
            )
            flatness_ratio = (
                model_metrics["flatness"] / reference_metrics["flatness"]
            )
            shape_score = (
                abs(math.log2(centroid_ratio))
                + abs(math.log2(rolloff_ratio))
                + 0.5 * abs(math.log2(flatness_ratio))
            )
            shape_pass = (
                0.60 <= centroid_ratio <= 1.67
                and 0.60 <= rolloff_ratio <= 1.67
                and 0.20 <= flatness_ratio <= 5.0
            )
            open_rows.append(
                {
                    "string": name,
                    "frequency_hz": frequency,
                    "reference_path": str(reference_path.absolute()),
                    "reference_sha256": sha256(reference_path),
                    "model": model_metrics,
                    "reference": reference_metrics,
                    "centroid_change_hz": model_metrics["centroid_hz"]
                    - reference_metrics["centroid_hz"],
                    "rolloff_change_hz": model_metrics["rolloff_85_hz"]
                    - reference_metrics["rolloff_85_hz"],
                    "flatness_ratio": model_metrics["flatness"]
                    / reference_metrics["flatness"],
                    "centroid_ratio": centroid_ratio,
                    "rolloff_85_ratio": rolloff_ratio,
                    "shape_score": shape_score,
                    "shape_pass": shape_pass,
                    "power_4_8khz_ratio": model_metrics["power_4_8khz"]
                    / reference_metrics["power_4_8khz"],
                }
            )

        report = {
            "schema_version": 1,
            "method": "realism-diagnostic-1",
            "component_rows": component_rows,
            "caprice_component_rows": caprice_rows,
            "open_string_rows": open_rows,
        }
        (temporary / "report.json").write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        with (temporary / "component-summary.csv").open(
            "w", newline="", encoding="utf-8"
        ) as stream:
            writer = csv.DictWriter(stream, fieldnames=list(component_rows[0]))
            writer.writeheader()
            writer.writerows(component_rows)
        with (temporary / "caprice-component-summary.csv").open(
            "w", newline="", encoding="utf-8"
        ) as stream:
            writer = csv.DictWriter(stream, fieldnames=list(caprice_rows[0]))
            writer.writeheader()
            writer.writerows(caprice_rows)
        temporary.rename(output_dir)
    except BaseException:
        shutil.rmtree(temporary, ignore_errors=True)
        raise


def main() -> int:
    try:
        run(parse_args())
    except (OSError, ValueError, RuntimeError) as error:
        print(f"render_realism_diagnostics.py: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
