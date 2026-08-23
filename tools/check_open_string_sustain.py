#!/usr/bin/env python3
"""Compare held open-string length and spectrum with private recordings."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import statistics
import struct
import subprocess
import tempfile
import wave


STRINGS = (
    ("g3", 1, 195.997717990875),
    ("d4", 2, 293.664767917408),
    ("a4", 3, 440.0),
    ("e5", 4, 659.255113825740),
)
BANDS = ("250-500 Hz", "500-1000 Hz", "1-2 kHz", "2-4 kHz", "4-8 kHz")
MAX_SHAPE_RMS_DB = 4.0
MAX_HOLD_DRIFT_GAP_DB = 4.0


def mono(path: Path) -> tuple[int, list[float]]:
    with wave.open(str(path), "rb") as stream:
        channels = stream.getnchannels()
        width = stream.getsampwidth()
        rate = stream.getframerate()
        data = stream.readframes(stream.getnframes())
    if width == 2:
        values = struct.unpack(f"<{len(data) // 2}h", data)
        scale = 32768.0
    elif width == 3:
        values = tuple(int.from_bytes(data[index:index + 3], "little", signed=True)
                       for index in range(0, len(data), 3))
        scale = 8388608.0
    else:
        raise ValueError(f"expected PCM16 or PCM24 WAVE: {path}")
    if channels < 1:
        raise ValueError(f"WAVE has no channels: {path}")
    samples = [sum(values[index:index + channels]) / (channels * scale)
               for index in range(0, len(values), channels)]
    return rate, samples


def envelope(path: Path) -> tuple[list[float], list[float]]:
    rate, samples = mono(path)
    size = round(0.020 * rate)
    hop = round(0.010 * rate)
    times = []
    levels = []
    for first in range(0, len(samples) - size + 1, hop):
        rms = math.sqrt(sum(value * value for value in samples[first:first + size]) / size)
        times.append(first / rate)
        levels.append(20.0 * math.log10(max(rms, 1.0e-15)))
    if not levels:
        raise ValueError(f"WAVE is too short: {path}")
    return times, levels


def reference_hold(path: Path) -> tuple[float, float]:
    times, levels = envelope(path)
    threshold = max(levels) - 20.0
    kept = [time for time, level in zip(times, levels) if level >= threshold]
    if not kept:
        raise ValueError(f"reference has no held sound: {path}")
    with wave.open(str(path), "rb") as stream:
        duration = stream.getnframes() / stream.getframerate()
    return kept[-1] + 0.020 - kept[0], duration - (kept[-1] + 0.020)


def interval_level(path: Path, first: float, last: float) -> float:
    times, levels = envelope(path)
    selected = [level for time, level in zip(times, levels)
                if first <= time < last]
    if not selected:
        raise ValueError(f"empty level interval: {path}")
    powers = [10.0 ** (level / 10.0) for level in selected]
    return 10.0 * math.log10(sum(powers) / len(powers))


def model_tail(path: Path, release: float) -> float:
    times, levels = envelope(path)
    held = [level for time, level in zip(times, levels)
            if release - 0.70 <= time < release - 0.20]
    if not held:
        raise ValueError(f"model has no held tail reference: {path}")
    threshold = statistics.median(held) - 20.0
    for index in range(len(times) - 2):
        if (times[index] >= release
                and max(levels[index:index + 3]) <= threshold):
            return times[index] - release
    return times[-1] - release + 0.020


def excerpt(source: Path, output: Path, first: float, duration: float) -> None:
    with wave.open(str(source), "rb") as input_stream:
        rate = input_stream.getframerate()
        count = round(duration * rate)
        input_stream.setpos(round(first * rate))
        data = input_stream.readframes(count)
        parameters = input_stream.getparams()
    if len(data) != count * parameters.nchannels * parameters.sampwidth:
        raise ValueError(f"short excerpt: {source}")
    with wave.open(str(output), "wb") as output_stream:
        output_stream.setparams(parameters)
        output_stream.writeframes(data)


def command_output(command: tuple[str, ...]) -> str:
    completed = subprocess.run(command, check=False, stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT, text=True, timeout=30)
    if completed.returncode != 0:
        raise ValueError(completed.stdout)
    return completed.stdout


def inspect(analyzer: Path, path: Path) -> dict:
    return json.loads(command_output((str(analyzer), "--mixdown", "--json",
                                      "inspect", str(path))))["file"]


def normalized_bands(report: dict) -> dict[str, float]:
    rows = report["spectrum"]["band_power"]
    total = sum(float(row["value"]) for row in rows)
    if total <= 0:
        raise ValueError("analyzer returned no spectral power")
    return {row["name"]: float(row["value"]) / total for row in rows}


def render(csound: Path, module: Path, csd: Path, output: Path,
           string: int, frequency: float, hold: float,
           force: float, speed: float, position: float,
           direct_level: float, body_level: float,
           nut_scale: float, bridge_scale: float,
           secondary_scale: float, direct_delay_samples: int) -> None:
    total = 0.20 + hold + 1.20
    command_output((
        str(csound), f"--opcode-lib={module}", "--sample-accurate",
        "--num-threads=1", "-W", "-3", "--nopeaks", "-o", str(output),
        "--omacro:DIAG_MODE=open", f"--omacro:DIAG_STRING={string}",
        f"--omacro:DIAG_FREQUENCY={frequency:.15g}",
        f"--omacro:DIAG_FORCE={force:.9f}",
        f"--omacro:DIAG_SPEED={speed:.9f}",
        f"--omacro:DIAG_POSITION={position:.9f}",
        f"--omacro:DIAG_OPEN_HOLD_SECONDS={hold:.9f}",
        f"--omacro:DIAG_TOTAL_SECONDS={total:.9f}",
        f"--omacro:DIAG_DIRECT_GAIN={direct_level:.9g}",
        f"--omacro:DIAG_BODY_GAIN={body_level:.9g}",
        f"--omacro:DIAG_NUT_CUTOFF_SCALE={nut_scale:.9g}",
        f"--omacro:DIAG_BRIDGE_CUTOFF_SCALE={bridge_scale:.9g}",
        f"--omacro:DIAG_FINGER_GAIN={secondary_scale:.9g}",
        f"--omacro:DIAG_BOARD_GAIN={secondary_scale:.9g}",
        f"--omacro:DIAG_ROSIN_GAIN={secondary_scale:.9g}",
        f"--omacro:DIAG_MECHANICAL_GAIN={secondary_scale:.9g}",
        f"--omacro:DIAG_DIRECT_DELAY_SAMPLES={direct_delay_samples}",
        str(csd),
    ))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csound", required=True, type=Path)
    parser.add_argument("--module", required=True, type=Path)
    parser.add_argument("--analyzer", required=True, type=Path)
    parser.add_argument("--csd", required=True, type=Path)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--only-string", choices=("g3", "d4", "a4", "e5"))
    parser.add_argument("--force", type=float, default=0.46)
    parser.add_argument("--speed", type=float, default=0.52)
    parser.add_argument("--position", type=float, default=0.15)
    parser.add_argument("--direct-level", type=float, default=1.0)
    parser.add_argument("--body-level", type=float, default=1.0)
    parser.add_argument("--nut-scale", type=float, default=1.0)
    parser.add_argument("--bridge-scale", type=float, default=1.0)
    parser.add_argument("--secondary-scale", type=float, default=1.0)
    parser.add_argument("--direct-delay-samples", type=int, default=0)
    for name, _, _ in STRINGS:
        parser.add_argument(f"--reference-{name}", required=True, type=Path)
    return parser.parse_args()


def run(options: argparse.Namespace) -> int:
    inputs = (options.csound, options.module, options.analyzer, options.csd,
              *(getattr(options, f"reference_{name}") for name, _, _ in STRINGS))
    if any(not path.is_file() for path in inputs):
        raise ValueError("an open-string input is missing")
    if not math.isfinite(options.force) or not 0.0 <= options.force <= 1.0:
        raise ValueError("force must be 0..1")
    if not math.isfinite(options.speed) or not -1.0 <= options.speed <= 1.0:
        raise ValueError("speed must be -1..1")
    if not math.isfinite(options.position) or not 0.01 <= options.position <= 0.49:
        raise ValueError("position must be 0.01..0.49")
    scales = (options.direct_level, options.body_level, options.nut_scale,
              options.bridge_scale, options.secondary_scale)
    if any(not math.isfinite(value) or value < 0.0 for value in scales):
        raise ValueError("diagnostic levels and scales must be finite and nonnegative")
    if not 0 <= options.direct_delay_samples <= 4096:
        raise ValueError("direct delay must be 0..4096 samples")
    failures = []
    rows = []
    with tempfile.TemporaryDirectory(prefix="hlolli-open-sustain-") as folder:
        root = Path(folder)
        selected_strings = tuple(
            row for row in STRINGS
            if options.only_string is None or row[0] == options.only_string)
        for name, string, frequency in selected_strings:
            reference = getattr(options, f"reference_{name}")
            hold, reference_tail = reference_hold(reference)
            model = root / f"model-{name}.wav"
            render(options.csound, options.module, options.csd, model,
                   string, frequency, hold, options.force, options.speed,
                   options.position,
                   options.direct_level, options.body_level,
                   options.nut_scale, options.bridge_scale,
                   options.secondary_scale, options.direct_delay_samples)
            model_held = root / f"model-held-{name}.wav"
            reference_held = root / f"reference-held-{name}.wav"
            excerpt(model, model_held, 0.20 + (hold - 1.50) / 2.0, 1.50)
            with wave.open(str(reference), "rb") as stream:
                reference_duration = stream.getnframes() / stream.getframerate()
            excerpt(reference, reference_held,
                    (reference_duration - 1.50) / 2.0, 1.50)
            model_report = inspect(options.analyzer, model_held)
            reference_report = inspect(options.analyzer, reference_held)
            model_bands = normalized_bands(model_report)
            reference_bands = normalized_bands(reference_report)
            gaps = {band: 10.0 * math.log10(
                model_bands[band] / reference_bands[band]) for band in BANDS}
            shape_rms = math.sqrt(sum(value * value for value in gaps.values())
                                  / len(gaps))
            slope_gap = (model_report["spectrum"]["slope_db_per_octave"]
                         - reference_report["spectrum"]["slope_db_per_octave"])
            model_early = interval_level(model, 0.20 + 0.20 * hold,
                                         0.20 + 0.35 * hold)
            model_late = interval_level(model, 0.20 + 0.65 * hold,
                                        0.20 + 0.80 * hold)
            reference_early = interval_level(reference, 0.20 * hold,
                                             0.35 * hold)
            reference_late = interval_level(reference, 0.65 * hold,
                                            0.80 * hold)
            drift_gap = ((model_late - model_early)
                         - (reference_late - reference_early))
            tail = model_tail(model, 0.20 + hold)
            row = {
                "string": name,
                "reference_hold_seconds": hold,
                "reference_tail_available_seconds": reference_tail,
                "model_tail_t20_seconds": tail,
                "model_hold_drift_db": model_late - model_early,
                "reference_hold_drift_db": reference_late - reference_early,
                "hold_drift_gap_db": drift_gap,
                "shape_rms_db": shape_rms,
                "slope_gap_db_per_octave": slope_gap,
                "centroid_ratio": (model_report["spectrum"]["centroid_hz"]
                                   / reference_report["spectrum"]["centroid_hz"]),
                "band_shape_gap_db": gaps,
            }
            rows.append(row)
            print(f"{name}: reference hold {hold:.2f} s; "
                  f"reference tail {reference_tail * 1000:.0f} ms; "
                  f"model T20 tail {tail:.2f} s; "
                  f"hold drift gap {drift_gap:+.2f} dB; shape RMS {shape_rms:.2f} dB; "
                  f"slope gap {slope_gap:+.2f} dB/oct")
            if abs(drift_gap) > MAX_HOLD_DRIFT_GAP_DB:
                failures.append(f"{name} held level shape differs")
            if shape_rms > MAX_SHAPE_RMS_DB:
                failures.append(f"{name} spectral shape differs")
            if not 0.75 <= row["centroid_ratio"] <= 1.33:
                failures.append(f"{name} spectral centre differs")
    result = {"schema_version": 1, "method": "open-string-sustain-2",
              "bow_force": options.force,
              "bow_speed": options.speed,
              "bow_position": options.position,
              "only_string": options.only_string,
              "diagnostic": {"direct_level": options.direct_level,
                             "body_level": options.body_level,
                             "nut_scale": options.nut_scale,
                             "bridge_scale": options.bridge_scale,
                             "secondary_scale": options.secondary_scale,
                             "direct_delay_samples":
                                 options.direct_delay_samples},
              "limits": {"shape_rms_db": MAX_SHAPE_RMS_DB,
                         "hold_drift_gap_db": MAX_HOLD_DRIFT_GAP_DB},
              "reported_only": ["slope_gap_db_per_octave",
                                  "model_tail_t20_seconds"],
              "rows": rows, "failures": failures}
    if options.report is not None:
        options.report.write_text(json.dumps(result, indent=2) + "\n",
                                  encoding="utf-8")
    if failures:
        for failure in failures:
            print(f"FAIL: {failure}")
        return 1
    print("Open-string sustain and spectrum passed")
    return 0


def main() -> int:
    try:
        return run(parse_args())
    except (OSError, ValueError, wave.Error, json.JSONDecodeError) as error:
        print(f"check_open_string_sustain.py: {error}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
