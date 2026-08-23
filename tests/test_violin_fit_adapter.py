#!/usr/bin/env python3

import importlib.util
import json
from pathlib import Path
import struct
import tempfile
import types
import unittest
import wave


ROOT = Path(__file__).resolve().parents[1]
ADAPTER = ROOT / "tools" / "violin_fit_adapter.py"
SPEC = importlib.util.spec_from_file_location("violin_fit_adapter", ADAPTER)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def silent_wave(path: Path, rate: int = 44100) -> None:
    with wave.open(str(path), "wb") as stream:
        stream.setnchannels(1)
        stream.setsampwidth(2)
        stream.setframerate(rate)
        stream.writeframes(b"\0\0" * 4410)


class ViolinFitAdapterTests(unittest.TestCase):
    def test_pcm16_resampler(self):
        source = struct.pack("<hhhh", 0, 1000, 2000, 3000)
        output = MODULE.resample_pcm16(source, 2, 2, 4)
        self.assertEqual(struct.unpack("<hhhhhhhh", output),
                         (0, 1000, 1000, 2000, 2000, 3000, 2000, 3000))

    def test_profile_and_experiment_contract(self):
        MODULE.validate_profile(ROOT / "profiles" / "generic_violin.json")
        with tempfile.TemporaryDirectory() as text:
            root = Path(text)
            references = {}
            for name in (
                "reference_g3", "reference_d4", "reference_a4", "reference_e5",
                "reference_body_fit", "reference_body_check",
            ):
                path = root / f"{name}.wav"
                silent_wave(path)
                references[name] = path
            experiment = MODULE.build_experiment(references, 3)
        self.assertEqual(experiment["schema"], "hwa-experiment")
        self.assertEqual(experiment["plan"]["sample_count"], 3)
        self.assertEqual([row["id"] for row in experiment["parameters"]],
                         sorted(row["id"] for row in experiment["parameters"]))
        self.assertEqual({row["split"] for row in experiment["cases"]},
                         {"fit", "check"})

    def test_every_fit_parameter_maps_to_one_profile_value(self):
        manifest = json.loads((ROOT / "fit" / "violin_fit_v1.json").read_text())
        profile = json.loads((ROOT / "profiles" / "generic_violin.json").read_text())
        for row in manifest["parameters"]:
            self.assertEqual(len(row["profile_paths"]), 1)
            value = profile
            for part in row["profile_paths"][0]:
                value = value[part]
            self.assertEqual(float(value), float(row["baseline"]))

    def test_bundle_lists_published_paths(self):
        with tempfile.TemporaryDirectory() as text:
            root = Path(text)
            files = {}
            for name in ("g3", "d4", "a4", "e5", "body_fit", "body_check"):
                path = root / f"{name}.wav"
                silent_wave(path, 48000 if name.startswith("body") else 44100)
                files[name] = path
            csound = root / "csound"
            module = root / "module"
            csound.write_bytes(b"csound")
            module.write_bytes(b"hlolli_wg_violin_test_diagnostic_gains")
            output = root / "bundle"
            arguments = types.SimpleNamespace(
                output_dir=output, csound=csound, module=module,
                library_path=None, reference_g3=files["g3"],
                reference_d4=files["d4"], reference_a4=files["a4"],
                reference_e5=files["e5"],
                reference_body_fit=files["body_fit"],
                reference_body_check=files["body_check"], sample_count=1,
                body_reference_seconds=5,
            )
            MODULE.build(arguments)
            bindings = json.loads((output / "bindings.json").read_text())
            paths = [Path(row["path"]) for row in bindings["bindings"]]
            paths.extend(Path(row["excerpt_path"])
                         for row in bindings["body_reference_excerpts"])
            self.assertTrue(all(path.is_file() for path in paths))


if __name__ == "__main__":
    unittest.main()
