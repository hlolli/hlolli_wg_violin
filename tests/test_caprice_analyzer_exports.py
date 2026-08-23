#!/usr/bin/env python3
"""Focused output-safety tests for the Caprice analyzer exports."""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import generate_caprice_24_demo as caprice


class AnalyzerExportSafetyTest(unittest.TestCase):
    def setUp(self) -> None:
        self.workspace = tempfile.TemporaryDirectory(
            prefix="caprice-analyzer-export-")
        self.root = Path(self.workspace.name)
        self.tempo = (Path(__file__).parent.parent / "examples" /
                      "paganini_caprice_24.csd")
        self.notes = [(0.0, 0.25, 69, 81, 3, 0, 0, 1)]

    def tearDown(self) -> None:
        self.workspace.cleanup()

    def test_rejects_same_and_nested_outputs(self) -> None:
        same = self.root / "same.csv"
        with self.assertRaises(ValueError):
            caprice.write_analyzer_inputs(
                same, same, self.notes, self.tempo, (self.tempo,))

        parent = self.root / "nested"
        child = parent / "score.csv"
        with self.assertRaises(ValueError):
            caprice.write_analyzer_inputs(
                child, parent, self.notes, self.tempo, (self.tempo,))
        self.assertFalse(parent.exists())

    def test_rejects_absent_outputs_that_differ_only_by_case(self) -> None:
        score = self.root / "Score.csv"
        labels = self.root / "score.csv"
        with self.assertRaises(ValueError):
            caprice.write_analyzer_inputs(
                score, labels, self.notes, self.tempo, (self.tempo,))
        self.assertFalse(score.exists())
        self.assertFalse(labels.exists())

    def test_rejects_absent_outputs_with_case_only_parent_difference(
            self) -> None:
        score = self.root / "Foo" / "out.csv"
        labels = self.root / "foo" / "out.csv"
        sentinel = self.root / "keep.txt"
        sentinel.write_bytes(b"keep")
        with self.assertRaises(ValueError):
            caprice.write_analyzer_inputs(
                score, labels, self.notes, self.tempo, (self.tempo,))
        self.assertEqual(sentinel.read_bytes(), b"keep")
        self.assertFalse(score.exists())
        self.assertFalse(labels.exists())

    def test_rejects_casefolded_output_ancestor(self) -> None:
        parent = self.root / "Foo"
        child = self.root / "foo" / "child.csv"
        sentinel = self.root / "keep.txt"
        sentinel.write_bytes(b"keep")
        with self.assertRaises(ValueError):
            caprice.write_analyzer_inputs(
                parent, child, self.notes, self.tempo, (self.tempo,))
        self.assertEqual(sentinel.read_bytes(), b"keep")
        self.assertFalse(parent.exists())
        self.assertFalse(child.exists())

    def test_rejects_unicode_normalized_output_alias(self) -> None:
        composed = self.root / "\u00e9.csv"
        decomposed = self.root / "e\u0301.csv"
        sentinel = self.root / "keep.txt"
        sentinel.write_bytes(b"keep")
        with self.assertRaises(ValueError):
            caprice.write_analyzer_inputs(
                composed, decomposed, self.notes, self.tempo, (self.tempo,))
        self.assertEqual(sentinel.read_bytes(), b"keep")
        self.assertFalse(composed.exists())
        self.assertFalse(decomposed.exists())

    def test_rejects_hard_link_to_input(self) -> None:
        source = self.root / "source.inc"
        alias = self.root / "score.csv"
        source.write_text("source", encoding="utf-8")
        try:
            os.link(source, alias)
        except OSError as error:
            self.skipTest(f"hard links are unavailable: {error}")
        with self.assertRaises(ValueError):
            caprice.write_analyzer_inputs(
                alias, self.root / "labels.csv", self.notes, self.tempo,
                (source, self.tempo))
        self.assertEqual(source.read_text(encoding="utf-8"), "source")

    def test_rejects_nonfinite_tempo_values(self) -> None:
        for name, curve in (
                ("nan-bpm.csd", "t 0 nan 442 120\n"),
                ("infinite-beat.csd", "t 0 120 inf 120\n")):
            with self.subTest(name=name):
                path = self.root / name
                path.write_text(curve, encoding="utf-8")
                with self.assertRaises(ValueError):
                    caprice.read_tempo_curve(path)

    def test_check_mode_protects_the_demo_it_reads(self) -> None:
        examples = Path(__file__).parent.parent / "examples"
        score = self.root / "paganini_caprice_24_score.inc"
        demo = self.root / "paganini_caprice_24.csd"
        alternate_tempo = self.root / "alternate-tempo.csd"
        labels = self.root / "labels.csv"
        shutil.copy2(examples / score.name, score)
        shutil.copy2(examples / demo.name, demo)
        shutil.copy2(examples / demo.name, alternate_tempo)
        before = demo.read_bytes()
        arguments = [
            "generate_caprice_24_demo.py", "--check", str(score),
            "--tempo-source", str(alternate_tempo),
            "--analyzer-score", str(demo),
            "--analyzer-labels", str(labels),
        ]
        with mock.patch.object(sys, "argv", arguments):
            with self.assertRaises(ValueError):
                caprice.main()
        self.assertEqual(demo.read_bytes(), before)
        self.assertFalse(labels.exists())

    def test_midi_mode_requires_tempo_before_writing(self) -> None:
        midi = self.root / "source.mid"
        output = self.root / "score.inc"
        score = self.root / "score.csv"
        labels = self.root / "labels.csv"
        midi.write_bytes(b"midi input")
        output.write_bytes(b"old score")
        score.write_bytes(b"old analyzer score")
        labels.write_bytes(b"old labels")
        arguments = [
            "generate_caprice_24_demo.py", "--midi", str(midi),
            "--output", str(output), "--analyzer-score", str(score),
            "--analyzer-labels", str(labels),
        ]
        with mock.patch.object(sys, "argv", arguments):
            with self.assertRaises(SystemExit):
                caprice.main()
        self.assertEqual(midi.read_bytes(), b"midi input")
        self.assertEqual(output.read_bytes(), b"old score")
        self.assertEqual(score.read_bytes(), b"old analyzer score")
        self.assertEqual(labels.read_bytes(), b"old labels")

    def test_midi_mode_rejects_output_tempo_alias_before_writing(self) -> None:
        midi = self.root / "source.mid"
        tempo_and_output = self.root / "tempo.csd"
        score = self.root / "score.csv"
        labels = self.root / "labels.csv"
        midi.write_bytes(b"midi input")
        tempo_and_output.write_text("t 0 120 442 120\n", encoding="utf-8")
        before = tempo_and_output.read_bytes()
        arguments = [
            "generate_caprice_24_demo.py", "--midi", str(midi),
            "--output", str(tempo_and_output),
            "--analyzer-score", str(score),
            "--analyzer-labels", str(labels),
            "--tempo-source", str(tempo_and_output),
        ]
        with mock.patch.object(sys, "argv", arguments):
            with self.assertRaises(ValueError):
                caprice.main()
        self.assertEqual(midi.read_bytes(), b"midi input")
        self.assertEqual(tempo_and_output.read_bytes(), before)
        self.assertFalse(score.exists())
        self.assertFalse(labels.exists())

    def test_midi_mode_validates_tempo_before_writing(self) -> None:
        midi = self.root / "source.mid"
        output = self.root / "score.inc"
        tempo = self.root / "tempo.csd"
        score = self.root / "score.csv"
        labels = self.root / "labels.csv"
        midi.write_bytes(b"midi input")
        output.write_bytes(b"old score")
        tempo.write_text("t 0 nan 442 120\n", encoding="utf-8")
        score.write_bytes(b"old analyzer score")
        labels.write_bytes(b"old labels")
        arguments = [
            "generate_caprice_24_demo.py", "--midi", str(midi),
            "--output", str(output), "--analyzer-score", str(score),
            "--analyzer-labels", str(labels),
            "--tempo-source", str(tempo),
        ]
        with mock.patch.object(sys, "argv", arguments):
            with self.assertRaises(ValueError):
                caprice.main()
        self.assertEqual(midi.read_bytes(), b"midi input")
        self.assertEqual(output.read_bytes(), b"old score")
        self.assertEqual(tempo.read_text(encoding="utf-8"),
                         "t 0 nan 442 120\n")
        self.assertEqual(score.read_bytes(), b"old analyzer score")
        self.assertEqual(labels.read_bytes(), b"old labels")

    def test_midi_mode_rejects_analyzer_input_alias_before_writing(self) -> None:
        midi = self.root / "source.mid"
        output = self.root / "score.inc"
        tempo = self.root / "tempo.csd"
        score = self.root / "score.csv"
        midi.write_bytes(b"midi input")
        output.write_bytes(b"old score")
        tempo.write_text("t 0 120 442 120\n", encoding="utf-8")
        score.write_bytes(b"old analyzer score")
        arguments = [
            "generate_caprice_24_demo.py", "--midi", str(midi),
            "--output", str(output), "--analyzer-score", str(score),
            "--analyzer-labels", str(midi),
            "--tempo-source", str(tempo),
        ]
        with mock.patch.object(sys, "argv", arguments):
            with self.assertRaises(ValueError):
                caprice.main()
        self.assertEqual(midi.read_bytes(), b"midi input")
        self.assertEqual(output.read_bytes(), b"old score")
        self.assertEqual(tempo.read_text(encoding="utf-8"),
                         "t 0 120 442 120\n")
        self.assertEqual(score.read_bytes(), b"old analyzer score")

    def test_second_commit_failure_restores_both_outputs(self) -> None:
        score = self.root / "score.csv"
        labels = self.root / "labels.csv"
        score.write_text("old score\n", encoding="utf-8")
        labels.write_text("old labels\n", encoding="utf-8")
        real_replace = os.replace
        call_count = 0

        def fail_second_replace(source: Path, destination: Path) -> None:
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                raise OSError("injected second commit failure")
            real_replace(source, destination)

        with mock.patch.object(
                caprice.os, "replace", side_effect=fail_second_replace):
            with self.assertRaises(OSError):
                caprice.write_analyzer_inputs(
                    score, labels, self.notes, self.tempo, (self.tempo,))
        self.assertEqual(score.read_text(encoding="utf-8"), "old score\n")
        self.assertEqual(labels.read_text(encoding="utf-8"), "old labels\n")
        self.assertEqual(
            sorted(path.name for path in self.root.iterdir()),
            ["labels.csv", "score.csv"])

    def test_failed_restore_keeps_backup(self) -> None:
        score = self.root / "score.csv"
        labels = self.root / "labels.csv"
        score.write_text("old score\n", encoding="utf-8")
        labels.write_text("old labels\n", encoding="utf-8")
        real_replace = os.replace
        call_count = 0

        def fail_commit_and_restore(source: Path, destination: Path) -> None:
            nonlocal call_count
            call_count += 1
            if call_count in (2, 3):
                raise OSError("injected commit or restore failure")
            real_replace(source, destination)

        with mock.patch.object(
                caprice.os, "replace", side_effect=fail_commit_and_restore):
            with self.assertRaisesRegex(RuntimeError, "backups kept at"):
                caprice.write_analyzer_inputs(
                    score, labels, self.notes, self.tempo, (self.tempo,))
        backups = list(self.root.glob(".score.csv.*.backup"))
        self.assertEqual(len(backups), 1)
        self.assertEqual(backups[0].read_text(encoding="utf-8"),
                         "old score\n")
        self.assertEqual(labels.read_text(encoding="utf-8"), "old labels\n")


if __name__ == "__main__":
    unittest.main()
