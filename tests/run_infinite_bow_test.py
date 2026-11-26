#!/usr/bin/env python3
"""Compare joined score notes with one continuously controlled violin voice."""

from __future__ import annotations

import argparse
import math
import re
import struct
import subprocess
import tempfile
import wave
from pathlib import Path

import run_legato_test as legato


ROOT = Path(__file__).resolve().parents[1]


def instrument(text: str, name: str) -> str:
    return "instr " + name + text.split("instr " + name, 1)[1].split("endin", 1)[0] + "endin\n"


def probes() -> str:
    source = (ROOT / "tests/legato.csd").read_text()
    result = "\n".join(instrument(source, name) for name in
                       ("StringProbe", "FingerProbe", "WaveProbe", "BowProbe"))
    return result + instrument((ROOT / "tests/physics.csd").read_text(), "PhysicsProbe")


def render(csound: Path, module: Path, text: str, root: Path, name: str,
           definitions: tuple[str, ...] = ()) -> tuple[bytes, str]:
    csd = root / (name + ".csd")
    output = root / (name + ".wav")
    csd.write_text(text)
    result = subprocess.run([
        str(csound), f"--opcode-lib={module}", "--sample-accurate",
        "--num-threads=1", "-W", "-s", "--nopeaks", "-d", "-m128",
        "-o", str(output), *["--omacro:" + value for value in definitions], str(csd),
    ], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
        cwd=ROOT / "examples", timeout=60)
    (root / (name + ".log")).write_text(result.stdout)
    if result.returncode:
        raise RuntimeError(result.stdout)
    with wave.open(str(output), "rb") as stream:
        pcm = stream.readframes(stream.getnframes())
        if stream.getnchannels() != 2 or stream.getsampwidth() != 2:
            raise AssertionError("wrong PCM format")
    peak = max(abs(sample[0]) for sample in struct.iter_unpack("<h", pcm))
    if not 0 < peak < 32767:
        raise AssertionError(f"{name}: silent or clipped PCM")
    return pcm, result.stdout


def states(log: str) -> dict[str, dict[int, tuple[float, ...]]]:
    result = {marker: legato.read_states(log, marker) for marker in legato.FIELDS}
    for marker in ("WG_PHYSICS_A", "WG_PHYSICS_B"):
        result[marker] = {}
        for line in log.splitlines():
            match = re.search(r"\b" + marker + r" (\d+) (.*)", line)
            if match:
                result[marker][int(match[1])] = tuple(map(float, match[2].split()))
    return result


def check_state(log: str, attacks: int = 1, directions: int = 0) -> None:
    snapshot = states(log)
    assert all(snapshot.values()), "missing state probes"
    assert all(math.isfinite(value) for tags in snapshot.values()
               for values in tags.values() for value in values), "non-finite state"
    for tag, bow in snapshot["WG_BOW"].items():
        get = lambda field: legato.value(bow, "WG_BOW", field)
        assert get("attacks") == attacks, (tag, "attacks", get("attacks"), attacks)
        assert get("direction_changes") == directions, (tag, "direction", get("direction_changes"))
        assert 0 <= get("contact") <= 1
        assert get("recoveries") == 0 and get("finite") == 1
        wave_state = snapshot["WG_WAVE"][tag]
        for field in ("clear_count", "reset_count", "clip_count"):
            assert legato.value(wave_state, "WG_WAVE", field) == 0, field
        assert legato.value(wave_state, "WG_WAVE", "finite") == 1
        assert snapshot["WG_PHYSICS_A"][tag][6] == 0, "contact failure"
        assert snapshot["WG_PHYSICS_B"][tag][12] == 0, "mechanics recovery"
        assert snapshot["WG_PHYSICS_B"][tag][-1] == 1
        assert snapshot["WG_PHYSICS_B"][tag][6] == attacks + directions, "mechanical events"


def phrase_score(rate: int, block: int, string: int, split: bool,
                 gap: bool = False) -> str:
    source = (ROOT / "examples/infinite_bow.csd").read_text()
    orchestra = source.split("<CsInstruments>")[1].split("</CsInstruments>")[0]
    orchestra = orchestra.replace("sr = 48000", f"sr = {rate}")
    orchestra = orchestra.replace("ksmps = 32", f"ksmps = {block}")
    step = max(8, int(rate * 0.12) // block) * block
    base = (220, 330, 494, 740)[string - 1]
    second = base * 2 ** (2 / 12)
    last = base * 2 ** (3 / 12)
    held = instrument(orchestra, "BowedNote").replace("instr BowedNote", "instr HeldPhrase")
    held = held.replace("kFrequency = p4", f"""kFrequency = p4
  if timeinstk() > {step // block} then
    kFrequency = {second:.17g}
  endif
  if timeinstk() > {2 * step // block} then
    kFrequency = {last:.17g}
  endif""")
    orchestra += held + probes()
    # The repeated pitch also hands off inside a control block.
    middle = step + (step // (2 * block)) * block + (1 if block > 1 else 0)
    endpoints = (0, step, middle, 2 * step, 3 * step)
    seconds = lambda samples: format((samples + 0.01) / rate, ".17g")
    score = [f'i "Body" 0 {seconds(3 * step + 8 * block)}']
    if split:
        for index, pitch in enumerate((base, second, second, last)):
            start, end = endpoints[index:index + 2]
            if gap and index == 3:
                start += 4 * block
            score.append(f'i "BowedNote" {seconds(start)} {seconds(end - start)} '
                         f'{pitch:.17g} {string} {1 if index % 2 == 0 else -1}')
    else:
        score.append(f'i "HeldPhrase" 0 {seconds(3 * step)} {base} {string} 1')
    for name in ("StringProbe", "FingerProbe", "WaveProbe", "BowProbe", "PhysicsProbe"):
        score.append(f'i "{name}" {seconds(3 * step - 2 * block)} 0.001 '
                     f'1 {string} 1')
    score.append("e")
    return ("<CsoundSynthesizer>\n<CsOptions>\n-d -m128\n</CsOptions>\n"
            "<CsInstruments>\n" + orchestra + "</CsInstruments>\n<CsScore>\n" +
            "\n".join(score) + "\n</CsScore>\n</CsoundSynthesizer>\n")


def run(csound: Path, module: Path, root: Path) -> None:
    for rate in (44100, 48000, 96000):
        for block in (1, 8, 16, 32, 64):
            for string in range(1, 5):
                name = f"{rate}-{block}-{string}"
                reference, reference_log = render(
                    csound, module, phrase_score(rate, block, string, False), root, name + "-held")
                joined, joined_log = render(
                    csound, module, phrase_score(rate, block, string, True), root, name + "-joined")
                assert reference == joined, f"{name}: PCM differs at a joined boundary"
                left, right = states(reference_log), states(joined_log)
                for marker in left:
                    for tag in left[marker]:
                        assert all(math.isclose(a, b, rel_tol=2e-12, abs_tol=2e-12)
                                   for a, b in zip(left[marker][tag], right[marker][tag])), (name, marker)
                check_state(joined_log)
    text = phrase_score(48000, 32, 2, True)
    _, ordinary_log = render(csound, module, text, root, "ordinary", ("CONTINUOUS=0",))
    check_state(ordinary_log, attacks=4)
    assert states(ordinary_log)["WG_BOW"][1][1] < 0, "ordinary bow lost its direction"
    _, gap_log = render(csound, module, phrase_score(48000, 32, 2, True, gap=True), root, "rest")
    check_state(gap_log, attacks=2)
    baseline, _ = render(csound, module, text, root, "one-handle")
    other = text.replace("giViolin hlolli_wg_violin_create", "giViolin hlolli_wg_violin_create\ngiOther hlolli_wg_violin_create")
    other_voice = instrument(other, "BowedNote").replace("instr BowedNote", "instr OtherVoice")
    other_voice = other_voice.replace("giViolin", "giOther").replace("outs aLeft, aRight", "")
    other = other.replace("</CsInstruments>", other_voice + "</CsInstruments>")
    other = other.replace("<CsScore>", '<CsScore>\ni "OtherVoice" 0 0.3 880 2 1')
    isolated, _ = render(csound, module, other, root, "two-handles")
    assert baseline == isolated, "another handle changed the phrase"
    for start, label in ((0.125, "string-change"), (0, "double-stop")):
        events = [f'i "Body" 0 0.5', 'i "BowedNote" 0 0.125 330 2 1',
                  f'i "BowedNote" {start} 0.125 494 3 1']
        for string in (2, 3):
            for name in ("StringProbe", "FingerProbe", "WaveProbe", "BowProbe", "PhysicsProbe"):
                events.append(f'i "{name}" 0.3 0.001 1 {string} {string}')
        combined = re.sub(r'<CsScore>.*?</CsScore>',
                          '<CsScore>\n' + '\n'.join(events) + '\ne\n</CsScore>', text, flags=re.S)
        _, log = render(csound, module, combined, root, label)
        check_state(log)
    print("PASS: 60 multi-note/held pairs, repeated pitch, rests, ordinary attacks, and handle isolation")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csound", required=True, type=Path)
    parser.add_argument("--module", required=True, type=Path)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="violin-infinite-test-") as folder:
        run(args.csound.resolve(), args.module.resolve(), Path(folder))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
