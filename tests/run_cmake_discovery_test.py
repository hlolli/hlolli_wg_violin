#!/usr/bin/env python3
"""Check Csound discovery with empty cached paths in a fresh build."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import subprocess
import tempfile


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cmake", required=True, type=Path)
    parser.add_argument("--source-dir", required=True, type=Path)
    parser.add_argument("--generator", required=True)
    parser.add_argument("--make-program", required=True)
    parser.add_argument("--compiler", required=True)
    options = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="violin-cmake-discovery-") as folder:
        root = Path(folder)
        headers = root / "headers"
        headers.mkdir()
        (headers / "csdl.h").write_text("/* configure-only fixture */\n")
        (headers / "version.h").write_text("#define CS_VERSION 7\n#define CS_SUBVER 0\n")
        (headers / "float-version.h").write_text("/* configure-only fixture */\n")
        binary_dir = root / "bin"
        binary_dir.mkdir()
        executable = binary_dir / ("csound.exe" if os.name == "nt" else "csound")
        executable.write_text("configure-only fixture\n")
        executable.chmod(0o755)
        environment = dict(os.environ)
        environment["CSOUND_INCLUDE_DIR"] = str(headers)
        environment["PATH"] = str(binary_dir) + os.pathsep + environment.get("PATH", "")
        build = root / "build"
        subprocess.run([
            str(options.cmake), "-S", str(options.source_dir), "-B", str(build),
            "-G", options.generator,
            f"-DCMAKE_MAKE_PROGRAM={options.make_program}",
            f"-DCMAKE_C_COMPILER={options.compiler}",
            "-DHLOLLI_WG_VIOLIN_CUSTOM_CMAKE=",
            "-DHLOLLI_WG_VIOLIN_BUILD_TESTS=OFF",
            "-DHLOLLI_CSOUND_BUILD_DIR=", "-DHLOLLI_CSOUND_SOURCE_DIR=",
            "-DHLOLLI_CSOUND_INCLUDE_DIR=", "-DCSOUND_EXECUTABLE=",
            "-DCMAKE_DISABLE_FIND_PACKAGE_Csound=ON",
            "-DCMAKE_FIND_FRAMEWORK=LAST",
        ], env=environment, check=True, timeout=30)
        cache = {}
        for line in (build / "CMakeCache.txt").read_text().splitlines():
            if not line or line.startswith(("#", "//")):
                continue
            key, value = line.split("=", 1)
            cache[key.split(":", 1)[0]] = value
        for name, expected in (("HLOLLI_CSOUND_INCLUDE_DIR", headers),
                               ("CSOUND_EXECUTABLE", executable)):
            actual = Path(cache.get(name, ""))
            if actual.resolve() != expected.resolve():
                raise RuntimeError(f"{name}: expected {expected}, found {actual}")
    print("PASS: Csound headers and executable found with empty cached paths")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
