#!/usr/bin/env python3
"""Install the public examples and compile them outside the source tree."""

from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import tempfile


EXAMPLES = (
    "basic.csd", "solo_techniques.csd", "string_section.csd",
    "wasm_smoke.csd", "bach_chaconne.csd", "infinite_bow.csd",
    "paganini_caprice_24.csd",
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cmake", required=True, type=Path)
    parser.add_argument("--build-dir", required=True, type=Path)
    parser.add_argument("--data-dir", required=True, type=Path)
    parser.add_argument("--config", default="")
    parser.add_argument("--csound", required=True, type=Path)
    parser.add_argument("--module", required=True, type=Path)
    options = parser.parse_args()
    if options.data_dir.is_absolute() or ".." in options.data_dir.parts:
        parser.error("data-dir must stay within the install prefix")

    with tempfile.TemporaryDirectory(prefix="violin-installed-examples-") as folder:
        command = [
            str(options.cmake), "--install", str(options.build_dir),
            "--prefix", folder, "--component", "Documentation",
        ]
        if options.config:
            command.extend(("--config", options.config))
        subprocess.run(command, check=True, timeout=30)
        examples = Path(folder) / options.data_dir / "hlolli_wg_violin/examples"
        for name in EXAMPLES:
            subprocess.run([
                str(options.csound), f"--opcode-lib={options.module}",
                "--syntax-check-only", "--sample-accurate", "--num-threads=1",
                "-n", "-d", "-m128", str(examples / name),
            ], cwd=examples, check=True, timeout=30)
    print("PASS: all installed public examples compile")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
