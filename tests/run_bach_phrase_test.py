#!/usr/bin/env python3
"""Check the Chaconne phrase map and the controls that reach each string."""

from __future__ import annotations

import argparse
import re
import sys
import tempfile
from pathlib import Path

import run_infinite_bow_test as common

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import generate_bach_phrases as phrasing
import generate_bach_chaconne_demo as score_data
import play_bach_chaconne as playback


def window(first_bar: int, last_bar: int, *, trace: bool = False,
           diagnostics: bool = False, mechanical_gain: int = 1,
           source: str | None = None) -> str:
    examples = ROOT / "examples"
    score = examples / "bach_chaconne_score.inc"
    bars, strokes = playback.parse_score(score)
    tempo = playback.parse_tempo(examples / "bach_chaconne_performance.inc")
    start = playback.active_stroke(strokes, bars[first_bar]).start
    end = bars[last_bar + 1] if last_bar < 257 else 770
    origin = playback.seconds_at(start, tempo)
    duration = playback.seconds_at(end, tempo) - origin
    score_lines = []
    for line in score.read_text().splitlines():
        if not line.startswith('i "'):
            continue
        fields = line.split()
        beat, length = float(fields[2]), float(fields[3])
        if beat < start - 1e-9 or beat >= end - 1e-9:
            continue
        fields[2] = playback.format_number(playback.seconds_at(beat, tempo) - origin)
        fields[3] = playback.format_number(playback.seconds_at(min(beat + length, end), tempo)
                                           - playback.seconds_at(beat, tempo))
        score_lines.append(" ".join(fields))
    audible_start = playback.seconds_at(bars[first_bar], tempo) - origin
    score_lines.append(f'i "BachAudible" {audible_start:.17g} {duration + 2 - audible_start:.17g}')
    score_lines.append(f'f 0 {duration + 2:.17g}')
    csd = source if source is not None else (examples / "bach_chaconne.csd").read_text()
    csd = re.sub(r'<CsScore>.*?</CsScore>', '<CsScore>\n' +
                 '\n'.join(score_lines) + '\ne\n</CsScore>', csd, flags=re.S)
    csd = re.sub(r'#include "([^"]+)"', lambda match:
                 (examples / match[1]).read_text(), csd)
    if trace:
        needle = '  aLeft, aRight hlolli_wg_violin \\\n'
        csd = csd.replace(needle, '''  printf "BACH_PHRASE %d %d %d %.17g %.17g %.17g\\n", timek(), \\
      iString, gkGestureId[iString], gkPhrase[iString], \\
      kStrokeTrigger, kSpeed, kDepth
''' + needle)
    if diagnostics:
        csd = csd.replace('</CsInstruments>', common.probes() + '</CsInstruments>')
        for string in range(1, 5):
            for name in ('StringProbe', 'FingerProbe', 'WaveProbe', 'BowProbe', 'PhysicsProbe'):
                csd = csd.replace('\ne\n</CsScore>',
                    f'\ni "{name}" {duration + 1:.17g} 0.001 1 {string} {string}\ne\n</CsScore>')
    if mechanical_gain != 1:
        for string in range(1, 5):
            csd = csd.replace('giOpenFrequency[] fillarray',
                f'giDiagnostic{string} hlolli_wg_violin_test_diagnostic_gains '
                f'giViolin, {string}, 1, 1, 1, {mechanical_gain}, 1, 1\ngiOpenFrequency[] fillarray')
    return csd


def check_plan() -> None:
    rows = score_data.parse_generated(ROOT / 'examples/bach_chaconne_score.inc')
    phrases = phrasing.phrase_plan(rows)
    assert phrases, 'missing phrases'
    assert {int(row[3]) for phrase in phrases for row in phrase} == {1, 2, 3, 4}
    assert any(score_data.measure_at(phrase[0][0]) != score_data.measure_at(phrase[-1][0])
               for phrase in phrases), 'no phrase crosses a barline'
    for phrase in phrases:
        assert len(phrase) >= 2
        for left, right in zip(phrase, phrase[1:]):
            assert abs(left[0] + left[1] - right[0]) < 1e-8
            assert left[3] == right[3] and left[12] == right[12]
            assert left[11] == right[11] == 1
            assert left[15] == right[15] == 0
    membership = {int(row[9]): number for number, phrase in enumerate(phrases)
                  for row in phrase}
    for string in range(1, 5):
        for voice in range(4):
            lane = [row for row in rows if row[3] == string and row[12] == voice]
            for left, right in zip(lane, lane[1:]):
                if right[5] and abs(left[0] + left[1] - right[0]) < 1e-8:
                    assert membership.get(int(left[9])) == membership.get(int(right[9])), 'written slur cut'
    # Gaps, string or voice changes, and accented notes break a phrase.
    sample = [list(row) for row in phrases[0][:2]]
    for field, delta in ((0, 0.01), (3, 1), (12, 1), (15, 1), (11, 1)):
        changed = [list(row) for row in sample]
        changed[1][field] += delta
        assert not phrasing.phrase_plan(changed), ('unwanted join', field)
    sample[1][2] = sample[0][2]
    sample[1][5] = 0
    assert not phrasing.phrase_plan(sample), 'separate repeated pitches joined'
    assert phrasing.repeated_stroke_releases(sample) == [int(sample[0][9])]
    sample[1][5] = 1
    assert len(phrasing.phrase_plan(sample)) == 1, 'written slur over a repeat cut'
    assert not phrasing.repeated_stroke_releases(sample), 'bow released within a written slur'


def read_trace(log: str) -> dict[int, list[tuple[int, int, float, float, float]]]:
    trace = {}
    for match in re.finditer(r'BACH_PHRASE (\d+) (\d+) (-?\d+) ([^\n]+)', log):
        string, gesture, phrase = map(int, match.group(1, 2, 3))
        gate, speed, depth = map(float, match[4].split())
        trace.setdefault(gesture, []).append((string, phrase, gate, speed, depth))
    return trace


def check_repeats(log: str) -> None:
    trace = read_trace(log)
    for before, after in ((993, 994), (995, 996), (1009, 1010), (1019, 1020)):
        left = [row[2] for row in trace[before]]
        right = [row[2] for row in trace[after]]
        assert any(gate > 0 for gate in left[:-6]), ('first note silent', before)
        assert left[-6:] == [0] * 6, ('bow stayed on the string', before, after)
        assert any(gate > 0 for gate in right[:4]), ('repeat missed its attack', after)


def check_trace(log: str) -> tuple[int, int]:
    rows = score_data.parse_generated(ROOT / 'examples/bach_chaconne_score.inc')
    phrases = phrasing.phrase_plan(rows)
    trace = read_trace(log)
    checked = 0
    vibrato_checked = 0
    for phrase in phrases:
        for previous, row in zip(phrase, phrase[1:]):
            left, right = trace.get(int(previous[9])), trace.get(int(row[9]))
            if not left or not right:
                continue
            assert left[-1][2] > 0 and right[0][2] > 0, ('contact restart', row[9])
            assert left[-1][1] == right[0][1] != 0, ('phrase changed', row[9])
            assert left[-1][3] * right[0][3] > 0, ('bow reversal', row[9])
            if previous[7] > 0 and row[7] > 0:
                assert abs(left[-1][4] - right[0][4]) < 1, ('vibrato restart', row[9])
                vibrato_checked += 1
            checked += 1
    assert checked > 15, ('too few rendered joins', checked)
    return checked, vibrato_checked


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--csound', type=Path, required=True)
    parser.add_argument('--module', type=Path, required=True)
    args = parser.parse_args()
    check_plan()
    with tempfile.TemporaryDirectory(prefix='violin-bach-phrase-') as folder:
        root = Path(folder)
        phrase_audio, log = common.render(
            args.csound.resolve(), args.module.resolve(),
            window(73, 76, trace=True), root, 'phrases')
        count, vibrato_count = check_trace(log)
        rows = score_data.parse_generated(ROOT / 'examples/bach_chaconne_score.inc')
        anchor = next(int(phrase[0][9]) for phrase in phrasing.phrase_plan(rows)
                      if score_data.measure_at(phrase[0][0]) == 73)
        guide = root / 'bow guide.inc'
        guide.write_text(f'giBachBowSlope[{anchor}] = 2.0\n', encoding='utf-8')
        guided_audio, guided_log = common.render(
            args.csound.resolve(), args.module.resolve(),
            window(73, 76, trace=True), root, 'guided-phrases',
            (f'BACH_BOW_GUIDE={guide}',))
        assert guided_audio != phrase_audio, 'bow guide did not change the render'
        assert check_trace(guided_log) == (count, vibrato_count)
        _, expressive_log = common.render(args.csound.resolve(), args.module.resolve(),
                                          window(37, 40, trace=True), root, 'expressive-phrases')
        extra_count, extra_vibrato = check_trace(expressive_log)
        count += extra_count
        vibrato_count += extra_vibrato
        assert vibrato_count > 5, ('too few vibrato joins', vibrato_count)
        repeat_window = window(81, 83, trace=True)
        for enabled in (0, 1):
            _, repeat_log = common.render(
                args.csound.resolve(), args.module.resolve(), repeat_window, root,
                f'repeated-notes-{enabled}', (f'INFINITE_BOW={enabled}',))
            check_repeats(repeat_log)
        normal, _ = common.render(args.csound.resolve(), args.module.resolve(),
                                  window(1, 2), root, 'opening', ('INFINITE_BOW=0',))
        unchanged, _ = common.render(args.csound.resolve(), args.module.resolve(),
                                     window(1, 2), root, 'opening-enabled')
        assert normal == unchanged, 'unmarked opening changed'
    print(f'PASS: {count} Chaconne joins, {vibrato_count} vibrato joins, unchanged opening')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
