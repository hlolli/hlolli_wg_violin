#!/usr/bin/python3
"""Build and run the analyzer's checked violin renderer adapter."""

from __future__ import annotations

import argparse
from array import array
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import wave


FROZEN_CONFIG = None
ROOT = Path(__file__).resolve().parents[1]
FIT_MANIFEST = ROOT / "fit" / "violin_fit_v1.json"
PROFILE = ROOT / "profiles" / "generic_violin.json"
CSD = ROOT / "examples" / "realism_diagnostic.csd"


class AdapterError(ValueError):
    pass


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def regular(path: Path, name: str) -> Path:
    path = path.absolute()
    if not path.is_file() or path.is_symlink():
        raise AdapterError(f"{name} must be a regular file: {path}")
    return path


def load_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if type(value) is not dict:
        raise AdapterError(f"JSON root must be an object: {path}")
    return value


def wave_facts(path: Path) -> tuple[int, int]:
    try:
        with wave.open(str(path), "rb") as stream:
            return stream.getframerate(), stream.getnchannels()
    except (wave.Error, EOFError) as error:
        raise AdapterError(f"invalid PCM WAVE: {path}: {error}") from error


def write_excerpt(source: Path, output: Path, seconds: float,
                  target_rate: int = 44100) -> dict:
    with wave.open(str(source), "rb") as input_stream:
        rate = input_stream.getframerate()
        total = input_stream.getnframes()
        count = min(total, round(seconds * rate))
        start = (total - count) // 2
        input_stream.setpos(start)
        audio = input_stream.readframes(count)
        parameters = input_stream.getparams()
    if count < 1 or len(audio) != count * parameters.nchannels * parameters.sampwidth:
        raise AdapterError(f"cannot read body reference excerpt: {source}")
    if parameters.sampwidth != 2:
        raise AdapterError("body references must use PCM16")
    if rate != target_rate:
        audio = resample_pcm16(audio, parameters.nchannels, rate, target_rate)
    output_frames = len(audio) // (parameters.nchannels * parameters.sampwidth)
    with wave.open(str(output), "wb") as output_stream:
        output_stream.setnchannels(parameters.nchannels)
        output_stream.setsampwidth(parameters.sampwidth)
        output_stream.setframerate(target_rate)
        output_stream.writeframes(audio)
    return {
        "source_path": str(source),
        "source_sha256": sha256(source),
        "excerpt_path": str(output),
        "excerpt_sha256": sha256(output),
        "start_frame": start,
        "source_frames": count,
        "excerpt_frames": output_frames,
        "excerpt_rate_hz": target_rate,
    }


def resample_pcm16(audio: bytes, channels: int,
                   source_rate: int, target_rate: int) -> bytes:
    if channels < 1 or source_rate < 1 or target_rate < 1:
        raise AdapterError("invalid resampler arguments")
    samples = array("h")
    samples.frombytes(audio)
    if sys.byteorder != "little":
        samples.byteswap()
    frames = len(samples) // channels
    if frames < 1 or frames * channels != len(samples):
        raise AdapterError("invalid PCM16 frame layout")
    output_frames = max(1, round(frames * target_rate / source_rate))
    output = array("h")
    for frame in range(output_frames):
        numerator = frame * source_rate
        left = min(numerator // target_rate, frames - 1)
        right = min(left + 1, frames - 1)
        fraction = (numerator % target_rate) / target_rate
        for channel in range(channels):
            first = samples[left * channels + channel]
            second = samples[right * channels + channel]
            value = first + (second - first) * fraction
            output.append(max(-32768, min(32767, round(value))))
    if sys.byteorder != "little":
        output.byteswap()
    return output.tobytes()


def parameter_rows(manifest: dict) -> list[dict]:
    result = []
    for row in manifest["parameters"]:
        result.append({
            "id": row["id"],
            "unit": row["unit"],
            "minimum": row["minimum"],
            "maximum": row["maximum"],
            "baseline": row["baseline"],
            "levels": [],
        })
    return sorted(result, key=lambda row: row["id"])


def stem(resource_id: str, side: str, input_id: str | None,
         output: str | None, rate: int, channels: int) -> dict:
    return {
        "id": resource_id,
        "side": side,
        "role": "final",
        "input_id": input_id,
        "output": output,
        "start_sample": 0,
        "gain_db": 0,
        "rate_hz": rate,
        "channels": channels,
    }


def build_experiment(references: dict[str, Path], sample_count: int) -> dict:
    reference_facts = {name: wave_facts(path) for name, path in references.items()}
    cases = []
    case_rows = (
        ("open-g3", "fit", "reference_g3"),
        ("open-a4", "fit", "reference_a4"),
        ("body-fit", "fit", "reference_body_fit"),
        ("open-d4", "check", "reference_d4"),
        ("open-e5", "check", "reference_e5"),
        ("body-check", "check", "reference_body_check"),
    )
    for case_id, split, binding in case_rows:
        rate, channels = reference_facts[binding]
        cases.append({
            "id": case_id,
            "split": split,
            "weight": 1,
            "stems": [
                stem("model.final", "model", None, "model.wav", 44100, 2),
                stem("reference.final", "reference", binding, None,
                     rate, channels),
            ],
            "probes": [],
            "links": [],
        })
    responses = [
        {"id": "final.rms", "role": "final", "feature": "rms_dbfs", "index": 0},
        {"id": "final.crest", "role": "final", "feature": "crest_db", "index": 0},
    ]
    band_names = (
        (4, "500-1000"), (5, "1-2k"), (6, "2-4k"),
        (7, "4-8k"), (8, "8-16k"),
    )
    responses.extend({
        "id": f"final.band.{name}", "role": "final",
        "feature": "band_level_dbfs", "index": index,
    } for index, name in band_names)
    return {
        "schema": "hwa-experiment",
        "schema_version": 1,
        "method_version": "violin-fit-v1",
        "clock_rate_hz": 44100,
        "inputs": [
            {"id": name, "sha256": sha256(path)}
            for name, path in sorted(references.items())
        ],
        "parameters": parameter_rows(load_json(FIT_MANIFEST)),
        "plan": {
            "kind": "random", "seed": 17012010,
            "sample_count": sample_count, "replicates": 1,
        },
        "cases": sorted(cases, key=lambda row: row["id"]),
        "responses": sorted(responses, key=lambda row: row["id"]),
    }


def build_renderer(csound: Path, module: Path, library_path: Path | None,
                   output: Path) -> None:
    source = Path(__file__).read_text(encoding="utf-8")
    marker = "FROZEN_CONFIG = None"
    lines = source.splitlines(keepends=True)
    matches = [index for index, line in enumerate(lines)
               if line.rstrip("\r\n") == marker]
    if len(matches) != 1:
        raise AdapterError("renderer source marker changed")
    files = {"csound": csound, "module": module, "csd": regular(CSD, "CSD")}
    parameters = load_json(FIT_MANIFEST)["parameters"]
    config = {
        "adapter_id": "hlolli-wg-violin-v1",
        "files": {
            name: {"path": str(path), "sha256": sha256(path)}
            for name, path in files.items()
        },
        "library_path": str(library_path) if library_path is not None else None,
        "baseline": {row["id"]: row["baseline"] for row in parameters},
        "parameters": parameters,
        "cases": {
            "open-g3": {"mode": "open", "string": 1, "frequency": 195.997717990875},
            "open-d4": {"mode": "open", "string": 2, "frequency": 293.664767917408},
            "open-a4": {"mode": "open", "string": 3, "frequency": 440.0},
            "open-e5": {"mode": "open", "string": 4, "frequency": 659.255113825740},
            "body-fit": {"mode": "phrase", "string": 3, "frequency": 440.0},
            "body-check": {"mode": "phrase", "string": 3, "frequency": 440.0},
        },
    }
    ending = "\n" if lines[matches[0]].endswith("\n") else ""
    lines[matches[0]] = "FROZEN_CONFIG = " + repr(config) + ending
    rendered = "".join(lines)
    output.write_text(rendered, encoding="utf-8")
    output.chmod(0o755)


def build(arguments: argparse.Namespace) -> None:
    output = arguments.output_dir.absolute()
    if output.exists() or output.is_symlink() or not output.parent.is_dir():
        raise AdapterError("output directory must be new with an existing parent")
    csound = regular(arguments.csound, "Csound")
    module = regular(arguments.module, "violin module")
    if b"hlolli_wg_violin_test_diagnostic_gains" not in module.read_bytes():
        raise AdapterError("violin fit needs the test opcode module")
    library_path = None
    if arguments.library_path is not None:
        library_path = arguments.library_path.absolute()
        if not library_path.is_dir():
            raise AdapterError("library path must be a directory")
    source_references = {
        "reference_g3": regular(arguments.reference_g3, "G3 reference"),
        "reference_d4": regular(arguments.reference_d4, "D4 reference"),
        "reference_a4": regular(arguments.reference_a4, "A4 reference"),
        "reference_e5": regular(arguments.reference_e5, "E5 reference"),
        "reference_body_fit": regular(arguments.reference_body_fit,
                                      "body fit reference"),
        "reference_body_check": regular(arguments.reference_body_check,
                                        "body check reference"),
    }
    temporary = Path(tempfile.mkdtemp(prefix=f".{output.name}.tmp-", dir=output.parent))
    try:
        references = dict(source_references)
        excerpt_rows = []
        for binding in ("reference_body_fit", "reference_body_check"):
            excerpt = temporary / f"{binding}.wav"
            excerpt_row = write_excerpt(
                source_references[binding], excerpt, arguments.body_reference_seconds
            )
            excerpt_row["excerpt_path"] = str(output / excerpt.name)
            excerpt_rows.append(excerpt_row)
            references[binding] = excerpt
        build_renderer(csound, module, library_path, temporary / "renderer")
        experiment = build_experiment(references, arguments.sample_count)
        (temporary / "experiment.json").write_text(
            json.dumps(experiment, indent=2, sort_keys=True) + "\n",
            encoding="utf-8"
        )
        shutil.copyfile(FIT_MANIFEST, temporary / "fit.json")
        bindings = {
            "schema": "hwa-fit-bindings", "schema_version": 1,
            "bindings": [
                {"id": name,
                 "path": str(output / path.name) if path.parent == temporary
                         else str(path),
                 "sha256": sha256(path)}
                for name, path in sorted(references.items())
            ],
            "body_reference_excerpts": excerpt_rows,
        }
        (temporary / "bindings.json").write_text(
            json.dumps(bindings, indent=2, sort_keys=True) + "\n",
            encoding="utf-8"
        )
        temporary.rename(output)
    except BaseException:
        shutil.rmtree(temporary, ignore_errors=True)
        raise


def checked_file(row: dict, name: str) -> Path:
    path = regular(Path(row["path"]), name)
    if sha256(path) != row["sha256"]:
        raise AdapterError(f"{name} hash changed")
    return path


def render_job(request_path: Path, output_dir: Path) -> None:
    if FROZEN_CONFIG is None:
        raise AdapterError("use a generated renderer")
    request_path = regular(request_path, "render request")
    output_dir = output_dir.absolute()
    if not output_dir.is_dir() or output_dir.is_symlink():
        raise AdapterError("output directory must be a real directory")
    request = load_json(request_path)
    if request.get("schema") != "hwa-render-job" or request.get("schema_version") != 1:
        raise AdapterError("unsupported render request")
    case = FROZEN_CONFIG["cases"].get(request.get("case_id"))
    if case is None:
        raise AdapterError("unknown violin fit case")
    outputs = request.get("outputs")
    if type(outputs) is not list or len(outputs) != 1 or outputs[0].get("id") != "model.final":
        raise AdapterError("violin renderer needs one model.final output")
    output = Path(outputs[0]["path"]).absolute()
    if output.parent != output_dir or output.exists() or output.is_symlink():
        raise AdapterError("invalid renderer output path")
    values = {row["id"]: float(row["value"]) for row in request.get("parameters", [])}
    baseline = FROZEN_CONFIG["baseline"]
    if set(values) != set(baseline):
        raise AdapterError("render parameter set changed")
    for row in FROZEN_CONFIG["parameters"]:
        value = values[row["id"]]
        if not math.isfinite(value) or value < row["minimum"] or value > row["maximum"]:
            raise AdapterError(f"render parameter is out of range: {row['id']}")
    csound = checked_file(FROZEN_CONFIG["files"]["csound"], "Csound")
    module = checked_file(FROZEN_CONFIG["files"]["module"], "module")
    csd = checked_file(FROZEN_CONFIG["files"]["csd"], "CSD")
    string = int(case["string"])
    cutoff_names = (
        "bridge_cutoff_g_hz", "bridge_cutoff_d_hz",
        "bridge_cutoff_a_hz", "bridge_cutoff_e_hz",
    )
    macros = {
        "DIAG_MODE": case["mode"],
        "DIAG_STRING": string,
        "DIAG_FREQUENCY": case["frequency"],
        "DIAG_BODY_GAIN": values["body_wet_gain"] / baseline["body_wet_gain"],
        "DIAG_BRIDGE_CUTOFF_SCALE": (
            values[cutoff_names[string - 1]] / baseline[cutoff_names[string - 1]]
        ),
    }
    command = [
        str(csound), f"--opcode-lib={module}", "--sample-accurate",
        "--num-threads=1", "-W", "-s", "--nopeaks", "-o", str(output),
    ]
    command.extend(f"--omacro:{name}={value}" for name, value in macros.items())
    command.append(str(csd))
    environment = {"LC_ALL": "C", "LANG": "C", "TZ": "UTC"}
    library_path = FROZEN_CONFIG.get("library_path")
    if library_path is not None:
        variable = "DYLD_LIBRARY_PATH" if sys.platform == "darwin" else "LD_LIBRARY_PATH"
        environment[variable] = library_path
    completed = subprocess.run(command, check=False, env=environment)
    if completed.returncode != 0 or not output.is_file() or output.is_symlink():
        raise AdapterError("Csound violin fit render failed")


def validate_profile(path: Path) -> None:
    path = regular(path, "profile")
    generator_path = ROOT / "tools" / "generate_profiles.py"
    spec = importlib.util.spec_from_file_location("violin_profile_generator", generator_path)
    if spec is None or spec.loader is None:
        raise AdapterError("cannot load violin profile validator")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    schema = module.load_json(ROOT / "profiles" / "schema" / "violin-profile-v1.schema.json")
    profile = module.load_json(path)
    module.validate_profile(profile, schema)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hwa-experiment-job", type=Path)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--validate-profile", type=Path)
    commands = parser.add_subparsers(dest="command")
    build_parser = commands.add_parser("build")
    build_parser.add_argument("--csound", required=True, type=Path)
    build_parser.add_argument("--module", required=True, type=Path)
    build_parser.add_argument("--library-path", type=Path)
    build_parser.add_argument("--reference-g3", required=True, type=Path)
    build_parser.add_argument("--reference-d4", required=True, type=Path)
    build_parser.add_argument("--reference-a4", required=True, type=Path)
    build_parser.add_argument("--reference-e5", required=True, type=Path)
    build_parser.add_argument("--reference-body-fit", required=True, type=Path)
    build_parser.add_argument("--reference-body-check", required=True, type=Path)
    build_parser.add_argument("--sample-count", type=int, default=24)
    build_parser.add_argument("--body-reference-seconds", type=float, default=30.0)
    build_parser.add_argument("--output-dir", required=True, type=Path)
    return parser.parse_args()


def main() -> int:
    try:
        arguments = parse_args()
        if arguments.hwa_experiment_job is not None:
            if arguments.output_dir is None:
                raise AdapterError("render job needs --output-dir")
            render_job(arguments.hwa_experiment_job, arguments.output_dir)
        elif arguments.validate_profile is not None:
            validate_profile(arguments.validate_profile)
        elif arguments.command == "build":
            if arguments.sample_count < 1 or arguments.sample_count > 256:
                raise AdapterError("sample count must be 1..256")
            if not math.isfinite(arguments.body_reference_seconds) or not (
                    5.0 <= arguments.body_reference_seconds <= 120.0):
                raise AdapterError("body reference seconds must be 5..120")
            build(arguments)
        else:
            raise AdapterError("choose build, render job, or profile validation")
    except (AdapterError, OSError, ValueError, json.JSONDecodeError) as error:
        print(f"violin_fit_adapter.py: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
