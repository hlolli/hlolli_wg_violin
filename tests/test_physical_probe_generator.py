#!/usr/bin/env python3
"""Test the physical-probe exporter."""

from __future__ import annotations

import argparse
import importlib.util
import os
from pathlib import Path
import shlex
import subprocess
import tempfile
import unittest
from unittest import mock


SCRIPT = Path(__file__).resolve().parents[1] / "tools" / "generate_physical_probes.py"


def load_generator():
    spec = importlib.util.spec_from_file_location("physical_probe_generator", SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load physical probe generator")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class PhysicalProbeGeneratorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.csound = self.root / "csound"
        self.opcode = self.root / "opcode.dylib"
        self.csd = self.root / "probe.csd"
        self.library = self.root / "lib"
        self.output = self.root / "probes"
        self.csound.write_bytes(b"fake")
        self.opcode.write_bytes(b"fake")
        self.csd.write_text("fake", encoding="utf-8")
        self.library.mkdir()

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def arguments(self) -> argparse.Namespace:
        return argparse.Namespace(
            csound=self.csound,
            opcode_lib=self.opcode,
            output_dir=self.output,
            library_path=self.library,
            csd=self.csd,
        )

    @staticmethod
    def successful_render(command, **_kwargs):
        output = Path(command[command.index("-o") + 1])
        output.write_bytes(b"RIFF" + output.name.encode("utf-8") + bytes(64))
        return subprocess.CompletedProcess(command, 0, stdout="")

    def test_publishes_one_complete_new_directory(self) -> None:
        generator = load_generator()
        with mock.patch.object(
            generator.subprocess, "run", side_effect=self.successful_render
        ) as run:
            generator.run(self.arguments())
        self.assertEqual(run.call_count, len(generator.CASES))
        self.assertTrue(
            all("-K" in call.args[0] for call in run.call_args_list)
        )
        self.assertEqual(
            sorted(path.name for path in self.output.iterdir()),
            sorted([case[0] for case in generator.CASES] + ["bindings.txt"]),
        )
        bindings = (self.output / "bindings.txt").read_text(encoding="utf-8")
        self.assertIn(str(self.output / "body-impulse.wav"), bindings)
        self.assertNotIn(".hwa-tmp-", bindings)

    def test_existing_output_is_unchanged(self) -> None:
        generator = load_generator()
        self.output.mkdir()
        sentinel = self.output / "keep"
        sentinel.write_bytes(b"unchanged")
        with self.assertRaisesRegex(ValueError, "already exists"):
            generator.run(self.arguments())
        self.assertEqual(sentinel.read_bytes(), b"unchanged")

    def test_broken_output_symlink_is_unchanged(self) -> None:
        generator = load_generator()
        self.output.symlink_to(self.root / "missing-target", target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "already exists"):
            generator.run(self.arguments())
        self.assertTrue(self.output.is_symlink())
        self.assertFalse(self.output.exists())

    def test_output_created_during_render_is_unchanged(self) -> None:
        generator = load_generator()
        calls = 0

        def create_target_after_last_render(command, **kwargs):
            nonlocal calls
            calls += 1
            completed = self.successful_render(command, **kwargs)
            if calls == len(generator.CASES):
                self.output.mkdir()
                (self.output / "keep").write_bytes(b"unchanged")
            return completed

        with mock.patch.object(
            generator.subprocess,
            "run",
            side_effect=create_target_after_last_render,
        ):
            with self.assertRaisesRegex(ValueError, "already exists"):
                generator.run(self.arguments())
        self.assertEqual((self.output / "keep").read_bytes(), b"unchanged")
        self.assertEqual(
            list(self.root.glob(f".{self.output.name}.hwa-tmp-*")), []
        )

    def test_bindings_quote_paths_with_spaces(self) -> None:
        generator = load_generator()
        self.output = self.root / "probe set"
        with mock.patch.object(
            generator.subprocess, "run", side_effect=self.successful_render
        ):
            generator.run(self.arguments())
        bindings = (self.output / "bindings.txt").read_text(encoding="utf-8")
        expected_path = shlex.quote(str(self.output / "body-impulse.wav"))
        self.assertIn(f"--bind model:body:bridge={expected_path}\n", bindings)

    def test_windows_library_directory_is_added_to_path(self) -> None:
        generator = load_generator()
        with mock.patch.object(generator.sys, "platform", "win32"):
            with mock.patch.object(
                generator.os, "environ", {"PATH": "old-path"}
            ):
                with mock.patch.object(
                    generator.subprocess,
                    "run",
                    side_effect=self.successful_render,
                ) as run:
                    generator.run(self.arguments())
        expected = f"{self.library}{os.pathsep}old-path"
        for call in run.call_args_list:
            self.assertEqual(call.kwargs["env"]["PATH"], expected)
            self.assertNotIn("LD_LIBRARY_PATH", call.kwargs["env"])

    def test_failed_render_publishes_nothing(self) -> None:
        generator = load_generator()
        calls = 0

        def fail_fifth(command, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 5:
                return subprocess.CompletedProcess(command, 1, stdout="failed")
            return self.successful_render(command, **kwargs)

        with mock.patch.object(generator.subprocess, "run", side_effect=fail_fifth):
            with self.assertRaisesRegex(RuntimeError, "probe render failed"):
                generator.run(self.arguments())
        self.assertFalse(self.output.exists())
        self.assertEqual(
            list(self.root.glob(f".{self.output.name}.hwa-tmp-*")), []
        )

    def test_duplicate_render_publishes_nothing(self) -> None:
        generator = load_generator()

        def duplicate_render(command, **_kwargs):
            output = Path(command[command.index("-o") + 1])
            output.write_bytes(b"RIFF" + bytes(64))
            return subprocess.CompletedProcess(command, 0, stdout="")

        with mock.patch.object(
            generator.subprocess, "run", side_effect=duplicate_render
        ):
            with self.assertRaisesRegex(RuntimeError, "byte-identical"):
                generator.run(self.arguments())
        self.assertFalse(self.output.exists())
        self.assertEqual(
            list(self.root.glob(f".{self.output.name}.hwa-tmp-*")), []
        )


if __name__ == "__main__":
    unittest.main()
