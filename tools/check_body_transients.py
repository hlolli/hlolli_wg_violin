#!/usr/bin/env python3
"""Compare violin note and chord transients with a private real performance."""

from __future__ import annotations

import argparse
from array import array
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import wave


REFERENCE_SHA256 = "8a296a1041d43f9ed35da45f4cd84ef66bf929d16c5ca0a9767b7133bc122a16"
RATE = 48000
ATTACK_ENVELOPE_LIMIT_DB = 4.0
ATTACK_SPECTRAL_CHANGE_LIMIT_DB = 5.0
HELD_TRAJECTORY_LIMIT_DB = 2.0
TAIL_BODY_DOMINANCE_MIN_DB = 6.0
REFERENCE_SEGMENTS = {
    "note": (round(152.21405065251951 * RATE),
             round(1.11094934748049 * RATE)),
    "chord": (round(74.053820996071283 * RATE),
              round(2.003983204445473 * RATE)),
}
WINDOWS = {
    "note": {
        "attack": (0.20, 0.32),
        "held": (0.34, 0.56),
        "late": (0.56, 0.70),
        "tail": (0.74, 1.05),
    },
    "chord": {
        "attack": (0.20, 0.35),
        "held": (0.45, 0.85),
        "late": (1.00, 1.35),
        "tail": (1.46, 1.92),
    },
}


class TransientError(ValueError):
    pass


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_pcm16(path: Path, start: int = 0,
               count: int | None = None) -> tuple[int, list[float]]:
    with wave.open(str(path), "rb") as stream:
        if (stream.getframerate() != RATE or stream.getsampwidth() != 2
                or stream.getnchannels() not in (1, 2)):
            raise TransientError(f"unsupported WAVE shape: {path}")
        channels = stream.getnchannels()
        if start < 0 or start >= stream.getnframes():
            raise TransientError(f"segment starts outside WAVE: {path}")
        stream.setpos(start)
        frames = stream.readframes(
            stream.getnframes() - start if count is None else count)
    samples = array("h")
    samples.frombytes(frames)
    if sys.byteorder != "little":
        samples.byteswap()
    frame_count = len(samples) // channels
    if count is not None and frame_count != count:
        raise TransientError(f"short WAVE segment: {path}")
    mono = [sum(samples[index:index + channels]) / (32768.0 * channels)
            for index in range(0, len(samples), channels)]
    return RATE, mono


def window_metrics(samples: list[float], start: float,
                   end: float) -> dict[str, float]:
    first = round(start * RATE)
    last = round(end * RATE)
    values = samples[first:last]
    if len(values) < 2:
        raise TransientError("transient window is empty")
    rms = math.sqrt(sum(value * value for value in values) / len(values))
    motion = math.sqrt(sum(
        (values[index] - values[index - 1]) ** 2
        for index in range(1, len(values))) / (len(values) - 1))
    if rms <= 0:
        raise TransientError("transient window is silent")
    return {"rms": rms, "normalized_first_difference": motion / rms}


def db_ratio(actual: float, required: float) -> float:
    if actual <= 0 or required <= 0:
        raise TransientError("transient ratio is not positive")
    return 20.0 * math.log10(actual / required)


def trajectory(rows: dict[str, dict[str, float]]) -> dict[str, float]:
    return {
        "attack_to_held_db": db_ratio(
            rows["held"]["rms"], rows["attack"]["rms"]),
        "held_to_late_db": db_ratio(
            rows["late"]["rms"], rows["held"]["rms"]),
        "late_to_tail_db": db_ratio(
            rows["tail"]["rms"], rows["late"]["rms"]),
    }


def attack_envelope(samples: list[float], held_rms: float,
                    first: float, last: float) -> list[float]:
    size = round(0.010 * RATE)
    hop = round(0.002 * RATE)
    begin = round(first * RATE)
    end = round(last * RATE)
    result = []
    for offset in range(begin, end - size + 1, hop):
        values = samples[offset:offset + size]
        rms = math.sqrt(sum(value * value for value in values) / len(values))
        result.append(20.0 * math.log10(max(rms / held_rms, 1.0e-5)))
    if not result:
        raise TransientError("attack envelope is empty")
    return result


def attack_envelope_error(model: list[float], reference: list[float],
                          case: str,
                          model_rows: dict[str, dict[str, float]],
                          reference_rows: dict[str, dict[str, float]]) -> float:
    first = WINDOWS[case]["attack"][0]
    last = WINDOWS[case]["held"][0]
    model_curve = attack_envelope(
        model, model_rows["held"]["rms"], first, last)
    reference_curve = attack_envelope(
        reference, reference_rows["held"]["rms"], first, last)
    if len(model_curve) != len(reference_curve):
        raise TransientError("attack envelopes have unequal lengths")
    return math.sqrt(sum(
        (actual - wanted) ** 2
        for actual, wanted in zip(model_curve, reference_curve)
    ) / len(model_curve))


def render(csound: Path, module: Path, csd: Path,
           case_number: int, output: Path,
           direct_level: float = 1.0, body_level: float = 1.0,
           room_level: float = 0.075) -> None:
    command = [
        str(csound), f"--opcode-lib={module}", "--sample-accurate",
        "--num-threads=1", "-W", "-s", "--nopeaks", "-o", str(output),
        f"--omacro:TRANSIENT_CASE={case_number}",
        f"--omacro:TRANSIENT_DIRECT_LEVEL={direct_level}",
        f"--omacro:TRANSIENT_BODY_LEVEL={body_level}",
        f"--omacro:TRANSIENT_ROOM_LEVEL={room_level}", str(csd),
    ]
    environment = os.environ.copy()
    environment.update({"LC_ALL": "C", "LANG": "C", "TZ": "UTC"})
    completed = subprocess.run(
        command, check=False, env=environment,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    if completed.returncode != 0 or not output.is_file():
        raise TransientError("Csound transient render failed\n" + completed.stdout)


def analyze(csound: Path, module: Path, csd: Path,
            reference: Path) -> dict:
    if sha256(reference) != REFERENCE_SHA256:
        raise TransientError("private real-performance recording changed")
    result = {
        "schema": "hlolli-wg-violin-body-transients",
        "schema_version": 4,
        "bindings": {
            "reference_sha256": REFERENCE_SHA256,
            "module_sha256": sha256(module),
            "csd_sha256": sha256(csd),
        },
        "cases": {},
        "diagnostics": {},
    }
    with tempfile.TemporaryDirectory(prefix="hlolli-body-transients-") as folder:
        root = Path(folder)
        for case_number, case in enumerate(("note", "chord"), 1):
            model_path = root / f"{case}.wav"
            render(csound, module, csd, case_number, model_path)
            _, model = read_pcm16(model_path)
            start, count = REFERENCE_SEGMENTS[case]
            _, wanted = read_pcm16(reference, start, count)
            rows = {}
            for name, bounds in WINDOWS[case].items():
                reference_row = window_metrics(wanted, *bounds)
                model_row = window_metrics(model, *bounds)
                rows[name] = {
                    "reference": reference_row,
                    "model": model_row,
                    "spectral_error_db": db_ratio(
                        model_row["normalized_first_difference"],
                        reference_row["normalized_first_difference"]),
                }
            result["cases"][case] = rows
            model_rows = {name: row["model"] for name, row in rows.items()}
            reference_rows = {
                name: row["reference"] for name, row in rows.items()
            }
            model_trajectory = trajectory(model_rows)
            reference_trajectory = trajectory(reference_rows)
            component_rows = {}
            for component, direct_level, body_level in (
                    ("direct", 1.0, 0.0), ("body", 0.0, 1.0)):
                component_path = root / f"{case}-{component}.wav"
                render(csound, module, csd, case_number, component_path,
                       direct_level, body_level, 0.0)
                _, component_samples = read_pcm16(component_path)
                metrics = {
                    name: window_metrics(component_samples, *bounds)
                    for name, bounds in WINDOWS[case].items()
                }
                component_rows[component] = {
                    "windows": metrics,
                    "trajectory": trajectory(metrics),
                }
            result["diagnostics"][case] = {
                "attack_envelope_shape_error_db": attack_envelope_error(
                    model, wanted, case, model_rows, reference_rows),
                "model_trajectory": model_trajectory,
                "reference_trajectory": reference_trajectory,
                "trajectory_error_db": {
                    name: model_trajectory[name] - reference_trajectory[name]
                    for name in model_trajectory
                },
                "components": component_rows,
            }
    note = result["cases"]["note"]
    chord = result["cases"]["chord"]
    note_components = result["diagnostics"]["note"]["components"]
    checks = [
        {
            "id": "note-attack-envelope-shape",
            "value_db": result["diagnostics"]["note"]
                ["attack_envelope_shape_error_db"],
            "limit_db": ATTACK_ENVELOPE_LIMIT_DB,
        },
        {
            "id": "chord-attack-envelope-shape",
            "value_db": result["diagnostics"]["chord"]
                ["attack_envelope_shape_error_db"],
            "limit_db": ATTACK_ENVELOPE_LIMIT_DB,
        },
        {
            "id": "note-attack-spectral-change",
            "value_db": abs(note["attack"]["spectral_error_db"] -
                            note["held"]["spectral_error_db"]),
            "limit_db": ATTACK_SPECTRAL_CHANGE_LIMIT_DB,
        },
        {
            "id": "chord-attack-spectral-change",
            "value_db": abs(chord["attack"]["spectral_error_db"] -
                            chord["held"]["spectral_error_db"]),
            "limit_db": ATTACK_SPECTRAL_CHANGE_LIMIT_DB,
        },
        {
            "id": "note-held-level-shape",
            "value_db": abs(result["diagnostics"]["note"]
                            ["trajectory_error_db"]["held_to_late_db"]),
            "limit_db": HELD_TRAJECTORY_LIMIT_DB,
        },
        {
            "id": "chord-held-level-shape",
            "value_db": abs(result["diagnostics"]["chord"]
                            ["trajectory_error_db"]["held_to_late_db"]),
            "limit_db": HELD_TRAJECTORY_LIMIT_DB,
        },
        {
            "id": "note-held-spectrum",
            "value_db": abs(note["held"]["spectral_error_db"]),
            "limit_db": 3.0,
        },
        {
            "id": "chord-held-spectrum",
            "value_db": abs(chord["held"]["spectral_error_db"]),
            "limit_db": 3.0,
        },
        {
            "id": "note-tail-level",
            "value_db": abs(db_ratio(
                note["tail"]["model"]["rms"] /
                note["late"]["model"]["rms"],
                note["tail"]["reference"]["rms"] /
                note["late"]["reference"]["rms"])),
            "limit_db": 4.0,
        },
        {
            "id": "note-tail-spectral-change",
            "value_db": abs(db_ratio(
                note["tail"]["model"]["normalized_first_difference"] /
                note["late"]["model"]["normalized_first_difference"],
                note["tail"]["reference"]["normalized_first_difference"] /
                note["late"]["reference"]["normalized_first_difference"])),
            "limit_db": 4.0,
        },
        {
            "id": "note-tail-darkening",
            "value_db": db_ratio(
                note["tail"]["model"]["normalized_first_difference"],
                note["late"]["model"]["normalized_first_difference"]),
            "limit_db": 0.0,
        },
        {
            "id": "note-tail-body-dominance",
            "value_db": db_ratio(
                note_components["body"]["windows"]["tail"]["rms"],
                note_components["direct"]["windows"]["tail"]["rms"]),
            "minimum_db": TAIL_BODY_DOMINANCE_MIN_DB,
        },
        {
            "id": "note-tail-body-decay-advantage",
            "value_db": note_components["body"]["trajectory"]
                ["late_to_tail_db"] - note_components["direct"]["trajectory"]
                ["late_to_tail_db"],
            "minimum_db": 0.0,
        },
    ]
    for row in checks:
        if "minimum_db" in row:
            row["pass"] = row["value_db"] >= row["minimum_db"]
        else:
            row["pass"] = row["value_db"] <= row["limit_db"]
    result["reported_only"] = [
        {
            "id": "chord-tail-level",
            "reason": "reference window contains the following note",
            "signed_error_db": db_ratio(
                chord["tail"]["model"]["rms"] /
                chord["late"]["model"]["rms"],
                chord["tail"]["reference"]["rms"] /
                chord["late"]["reference"]["rms"]),
        },
        {
            "id": "chord-tail-spectral-change",
            "reason": "reference window contains the following note",
            "signed_error_db": db_ratio(
                chord["tail"]["model"]["normalized_first_difference"] /
                chord["late"]["model"]["normalized_first_difference"],
                chord["tail"]["reference"]["normalized_first_difference"] /
                chord["late"]["reference"]["normalized_first_difference"]),
        },
    ]
    result["checks"] = checks
    result["pass"] = all(row["pass"] for row in checks)
    return result


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csound", required=True, type=Path)
    parser.add_argument("--module", required=True, type=Path)
    parser.add_argument("--reference-recording", required=True, type=Path)
    parser.add_argument("--csd", type=Path,
                        default=root / "examples/body_transient_probe.csd")
    parser.add_argument("--report", type=Path)
    options = parser.parse_args()
    try:
        paths = (options.csound, options.module,
                 options.csd, options.reference_recording)
        if any(not path.is_file() for path in paths):
            raise TransientError("a transient input file is missing")
        result = analyze(*(path.resolve() for path in paths))
        text = json.dumps(result, indent=2, sort_keys=True) + "\n"
        if options.report is not None:
            options.report.write_text(text, encoding="utf-8")
        for row in result["checks"]:
            status = "PASS" if row["pass"] else "FAIL"
            bound = (f"minimum {row['minimum_db']:.3f} dB"
                     if "minimum_db" in row
                     else f"limit {row['limit_db']:.3f} dB")
            print(f"{status}: {row['id']} {row['value_db']:.3f} dB "
                  f"({bound})")
        for row in result["reported_only"]:
            print(f"INFO: {row['id']} {row['signed_error_db']:+.3f} dB "
                  f"({row['reason']})")
        return 0 if result["pass"] else 1
    except (OSError, TransientError, ValueError, wave.Error) as error:
        print(f"check_body_transients.py: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
