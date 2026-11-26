#!/usr/bin/env python3
"""Render the same-gain legato audition and a Chaconne excerpt outside the repo."""

from __future__ import annotations

import argparse
import json
import math
import struct
import sys
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
import run_infinite_bow_test as common
import run_bach_phrase_test as bach


def facts(pcm: bytes, log: str) -> dict:
    samples = [item[0] / 32768 for item in struct.iter_unpack("<h", pcm)]
    snapshot = common.states(log)
    for marker, tagged in snapshot.items():
        assert len(tagged) == 4, (marker, "missing string")
        assert all(math.isfinite(value) for values in tagged.values() for value in values)
    for values in snapshot["WG_WAVE"].values():
        for field in ("clear_count", "reset_count", "clip_count"):
            assert common.legato.value(values, "WG_WAVE", field) == 0, field
        assert values[-1] == 1
    for values in snapshot["WG_BOW"].values():
        assert 0 <= values[2] <= 1 and values[-2] == 0 and values[-1] == 1
    for values in snapshot["WG_PHYSICS_A"].values():
        assert values[6] == 0, "contact failure"
    for values in snapshot["WG_PHYSICS_B"].values():
        assert values[12] == 0 and values[-1] == 1, "mechanics recovery"
    return {
        "seconds": len(samples) / 96000,
        "peak": max(map(abs, samples)),
        "rms": math.sqrt(sum(value * value for value in samples) / len(samples)),
        "attacks": sum(value[9] for value in snapshot["WG_BOW"].values()),
        "direction_changes": sum(value[8] for value in snapshot["WG_BOW"].values()),
        "mechanical_events": sum(value[6] for value in snapshot["WG_PHYSICS_B"].values()),
        "injected_bow_noise_energy": sum(value[3] for value in snapshot["WG_PHYSICS_B"].values()),
        "state": snapshot,
    }


def concatenate(path: Path, rows: list[tuple[str, bytes]]) -> list[dict]:
    order = []
    frame = 0
    with wave.open(str(path), "wb") as out:
        out.setparams((2, 2, 48000, 0, "NONE", "not compressed"))
        for index, (label, pcm) in enumerate(rows):
            if index:
                out.writeframes(bytes(48000 * 4))
                frame += 48000
            order.append({"variant": label, "start_seconds": frame / 48000,
                          "end_seconds": (frame + len(pcm) / 4) / 48000})
            out.writeframes(pcm)
            frame += len(pcm) // 4
    return order


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csound", type=Path, required=True)
    parser.add_argument("--module", type=Path, required=True)
    parser.add_argument("--test-module", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    output = args.output_dir.resolve()
    if output == ROOT or ROOT in output.parents:
        parser.error("output-dir must be outside the repository")
    output.mkdir(parents=True, exist_ok=True)
    csound, release, diagnostic = (args.csound.resolve(), args.module.resolve(),
                                   args.test_module.resolve())
    public = (ROOT / "examples/infinite_bow.csd").read_text()
    tested = public.replace("</CsInstruments>", common.probes() + "</CsInstruments>")
    for string in range(1, 5):
        for probe in ("StringProbe", "FingerProbe", "WaveProbe", "BowProbe", "PhysicsProbe"):
            tested = tested.replace("\ne\n", f'\ni "{probe}" 6.9 0.001 1 {string} {string}\ne\n')
    report = {"variants": {}, "mechanical_suppression": "private diagnostic only"}
    audio = []
    for continuous in (0, 1):
        default_pcm, _ = common.render(csound, release, public, output,
                                      f"release-{continuous}", (f"CONTINUOUS={continuous}",))
        for gain in (1, 0):
            name = ("infinite" if continuous else "conventional") + ("-full" if gain else "-bursts-off")
            source = tested
            for string in range(1, 5):
                source = source.replace("instr BowedNote", f"giGain{string} "
                    f"hlolli_wg_violin_test_diagnostic_gains giViolin, {string}, "
                    f"1, 1, 1, {gain}, 1, 1\ninstr BowedNote")
            pcm, log = common.render(csound, diagnostic, source, output, name,
                                     (f"CONTINUOUS={continuous}",))
            if gain:
                assert default_pcm == pcm, "release/default diagnostic PCM differs"
            common.check_state(log, attacks=1 if continuous else 4)
            report["variants"][name] = facts(pcm, log)
            audio.append((name, pcm))
    report["four_way_order"] = concatenate(output / "four-way.wav", audio)
    musical = []
    for continuous in (0, 1):
        name = "bach-73-80-" + ("infinite" if continuous else "conventional")
        source = bach.window(73, 80, diagnostics=True)
        pcm, log = common.render(csound, diagnostic, source, output, name,
                                 (f"INFINITE_BOW={continuous}",))
        public_source = bach.window(73, 80)
        public_source = public_source.replace("#define INFINITE_BOW #1#",
                                              f"#define INFINITE_BOW #{continuous}#")
        release_pcm, _ = common.render(csound, release, public_source, output, name + "-release")
        assert pcm == release_pcm, "Bach release/default diagnostic PCM differs"
        report["variants"][name] = facts(pcm, log)
        musical.append((name, pcm))
    report["bach_order"] = concatenate(output / "bach-73-80-comparison.wav", musical)
    (output / "listening-results.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"four_way": report["four_way_order"], "bach": report["bach_order"],
                      "variants": {name: {key: value for key, value in row.items() if key != "state"}
                                   for name, row in report["variants"].items()}}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
