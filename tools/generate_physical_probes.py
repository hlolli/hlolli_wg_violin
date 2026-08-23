#!/usr/bin/env python3
"""Render the explicit WAVE bindings used by the analyzer."""

from __future__ import annotations

import argparse
import hashlib
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tempfile


CASES = (
    ("element-d-a4.wav", 1, 32),
    ("element-a-a4.wav", 2, 32),
    ("double-d.wav", 3, 32),
    ("double-a.wav", 4, 32),
    ("double-joint.wav", 5, 32),
    ("body-impulse.wav", 6, 32),
    ("render-base.wav", 7, 32),
    ("render-variant.wav", 7, 16),
)


def path_entry_exists(path: Path) -> bool:
    """Return true for any directory entry, including a broken symlink."""
    try:
        path.lstat()
    except FileNotFoundError:
        return False
    return True


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--csound", required=True, type=Path)
    parser.add_argument("--opcode-lib", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument(
        "--library-path",
        type=Path,
        help="Optional dynamic-library directory for the Csound process.",
    )
    parser.add_argument(
        "--csd",
        type=Path,
        default=Path(__file__).resolve().parents[1]
        / "examples"
        / "physical_probes.csd",
    )
    return parser.parse_args()


def run(arguments: argparse.Namespace) -> None:
    for path in (arguments.csound, arguments.opcode_lib, arguments.csd):
        if not path.is_file():
            raise ValueError(f"missing regular file: {path}")
    output_dir = arguments.output_dir.absolute()
    output_parent = output_dir.parent
    if path_entry_exists(output_dir):
        raise ValueError(f"output path already exists: {output_dir}")
    if not output_parent.is_dir():
        raise ValueError(f"missing output parent directory: {output_parent}")
    child_environment = os.environ.copy()
    if arguments.library_path is not None:
        if not arguments.library_path.is_dir():
            raise ValueError(
                f"missing library directory: {arguments.library_path}"
            )
        if sys.platform == "darwin":
            library_variable = "DYLD_LIBRARY_PATH"
        elif sys.platform.startswith("win"):
            library_variable = "PATH"
        else:
            library_variable = "LD_LIBRARY_PATH"
        previous_library_path = child_environment.get(library_variable)
        child_environment[library_variable] = str(arguments.library_path)
        if previous_library_path:
            child_environment[library_variable] += (
                os.pathsep + previous_library_path
            )

    temporary_dir = Path(
        tempfile.mkdtemp(
            prefix=f".{output_dir.name}.hwa-tmp-", dir=output_parent
        )
    )
    try:
        rendered_hashes: dict[str, str] = {}
        for filename, probe_case, ksmps in CASES:
            output = temporary_dir / filename
            command = [
                str(arguments.csound),
                f"--opcode-lib={arguments.opcode_lib}",
                f"--omacro:PROBE_CASE={probe_case}",
                f"--omacro:PROBE_KSMPS={ksmps}",
                "-W",
                "-f",
                "-K",
                "-o",
                str(output),
                str(arguments.csd),
            ]
            completed = subprocess.run(
                command,
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                env=child_environment,
            )
            if completed.returncode != 0:
                raise RuntimeError(
                    f"probe render failed for {filename}:\n{completed.stdout}"
                )
            if not output.is_file() or output.stat().st_size <= 44:
                raise RuntimeError(
                    f"probe render did not create audio: {output}"
                )
            digest = hashlib.sha256(output.read_bytes()).hexdigest()
            if digest in rendered_hashes:
                raise RuntimeError(
                    "probe renders are byte-identical: "
                    f"{rendered_hashes[digest]} and {filename}"
                )
            rendered_hashes[digest] = filename

        bindings = temporary_dir / "bindings.txt"
        bindings.write_text(
            "\n".join(
                (
                    "--bind model:scan:element-d="
                    + shlex.quote(str(output_dir / "element-d-a4.wav")),
                    "--bind model:scan:element-a="
                    + shlex.quote(str(output_dir / "element-a-a4.wav")),
                    "--bind model:isolated-a:double-stop="
                    + shlex.quote(str(output_dir / "double-d.wav")),
                    "--bind model:isolated-b:double-stop="
                    + shlex.quote(str(output_dir / "double-a.wav")),
                    "--bind model:joint:double-stop="
                    + shlex.quote(str(output_dir / "double-joint.wav")),
                    "--bind model:body:bridge="
                    + shlex.quote(str(output_dir / "body-impulse.wav")),
                    "--bind model:render-baseline:block-size="
                    + shlex.quote(str(output_dir / "render-base.wav")),
                    "--bind model:render-variant:block-size="
                    + shlex.quote(str(output_dir / "render-variant.wav")),
                )
            )
            + "\n",
            encoding="utf-8",
        )
        if path_entry_exists(output_dir):
            raise ValueError(f"output path already exists: {output_dir}")
        temporary_dir.rename(output_dir)
    except BaseException:
        shutil.rmtree(temporary_dir, ignore_errors=True)
        raise


def main() -> int:
    try:
        run(parse_args())
    except (OSError, ValueError, RuntimeError) as error:
        print(f"generate_physical_probes.py: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
