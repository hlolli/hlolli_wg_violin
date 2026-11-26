# Continuous bow phrasing

7 September 2026. Development checks from the first continuous-bow pass.
That pass used the existing runtime and profile.

## Phrase rules

The public `examples/infinite_bow.csd` joins adjacent arco notes on the same
physical string through the existing ownership handoff. Its four phrases include
repeated pitches and real rests. No public opcode or constructor changed.

The Chaconne enables its optional phrase map by default. The generator marks
256 phrases containing 1,073 notes and 817 joins in selected melodic variations.
The exact passages and rules are in `examples/bach_chaconne.md`. The written
note rows, stroke rows, tempo, accents, string map, and slurs stay unchanged.

The score uses one persistent controller per string. A phrase holds its own bow
direction and bypasses shared stroke envelopes. Direct arco applies from its
first note. Continuations keep vibrato phase and do not replay the depth ramp.
Dynamics use a 10 ms half-time. Phrase starts and ends lower the gate for one
control block; joined boundaries keep it positive. The existing guarded note-off
event runs one block after the note ends so it cannot briefly release a joined
note before its successor updates the controller.

Phrase release keeps the stopped pitch and the body tail. The old open-string
retuning remains in the unmarked path. `INFINITE_BOW=0` restores that path for
the whole score. Bars 73–76 with this switch off produce byte-identical 16-bit
PCM to the score saved before the change.

## Checks

All 40 configured CTest checks pass. The profile/body-data checks, prepared
native source target, and whitespace check also pass.

- Sixty joined/held voice pairs cover all four strings at 44.1, 48, and 96 kHz
  with block sizes 1, 8, 16, 32, and 64. They match PCM and state, including a
  repeated-pitch handoff inside a control block.
- Tests check attacks, direction changes, mechanical events, contact bounds,
  finite state, and the absence of clears, resets, clips, and recoveries.
  They also cover rests, separate attacks, string changes, double stops, and
  a second handle that must not affect the first.
- Chaconne tests check live gate, direction, and vibrato across joined notes
  in bars 37–40 and 73–76. They reject phrase maps that cut a written slur and
  check that enabling the feature leaves the unmarked opening byte-identical.
- The seven-second public phrase passes actual browser/native float64 PCM
  comparison: maximum error `1.9130530493072229e-14`, RMS error
  `1.1685784837700806e-16`, 672,000 interleaved samples. The limits remain
  `1e-12` maximum and `1e-13` RMS, taken from the sibling instrument's PCM gate.
  The original browser smoke also passes.

The longer Chaconne browser audition could not compile: the configured browser
Csound build lacks `alwayson`, which the existing score uses. This is a concrete
limit on testing that score in this host. The passing public phrase test does
not establish browser parity for the full Chaconne. No tolerance was relaxed.

## Listening files

The comparison script writes audio, scores, logs, and state snapshots to its
output directory. The measurements below describe the original development run.

`four-way.wav` has one second of silence between variants:

| Time | Variant | Attacks | Mechanical events | Injected bow-noise energy |
|---|---|---:|---:|---:|
| 0–7 s | Conventional, full bursts | 16 | 16 | 0.0413914310 |
| 8–15 s | Conventional, bursts off | 16 | 16 | 0.0041379313 |
| 16–23 s | Infinite bow, full bursts | 4 | 4 | 0.0136160013 |
| 24–31 s | Infinite bow, bursts off | 4 | 4 | 0.0044160689 |

`bach-73-80-comparison.wav` plays conventional phrasing at 0–28.444 s, then
infinite phrasing at 29.444–57.888 s. Both retain full mechanical bursts, the
same body/sympathy settings, the same room, and the 2.5 m listener distance.

`bach-full-infinite.wav` contains all 257 bars: 853.929 seconds at 48 kHz,
stereo, 24 bit. Csound reports zero errors and zero out-of-range samples;
its left/right peaks are 0.04448 and 0.04102. The WAVE frame count and format
were checked after the render.

| Bach phrasing | Attacks | Direction changes | Mechanical events | Injected bow-noise energy |
|---|---:|---:|---:|---:|
| Conventional | 45 | 144 | 165 | 0.4002264268 |
| Infinite | 46 | 38 | 76 | 0.1697636978 |

The main event-count change here comes from fewer bow reversals. Explicit
phrase starts account for the extra attack. Noise energy includes ongoing
friction noise and is an internal measure, not output loudness or musical
quality. Removing bursts can also change later string vibration.

All audition files are non-silent and unclipped at the same gain. State probes
report finite values and no contact failures, rail resets, clips, or recoveries.
Each full-burst diagnostic render matches its release-module render exactly.
Only the private diagnostic module can suppress bursts in these comparisons;
the shipped examples keep them. Finger, board, and friction-noise gains stay at
one. The comparisons use no normalization or added EQ.

## Reproduce

Use the Csound and module paths from the configured build:

```sh
python3 -B tools/generate_bach_phrases.py --check
cmake --build build
ctest --test-dir build -R 'ownership|legato|gesture|physics|release_native|bach_|infinite_bow' --output-on-failure
cmake --build build --target hlolli_wg_violin_check_profiles
cmake --build build --target hlolli_wg_violin_check_wasm
cmake --build build --target hlolli_wg_violin_check_infinite_bow_wasm
ctest --test-dir build --output-on-failure
python3 -B tools/render_infinite_bow_comparison.py \
  --csound /path/to/csound/build/csound \
  --module build/libhlolli_wg_violin.dylib \
  --test-module build/libhlolli_wg_violin_test.dylib \
  --output-dir /tmp/violin-infinite-bow
cmake -DSTART_BAR=73 -DINFINITE_BOW=1 -P build/play_bach_chaconne.cmake
```

The phrase generator owns the map; the listening script owns the temporary
comparison scores. Tests reuse the existing private probes. The WASM runner
can now export float64 PCM for the new comparison gate. Example docs, API notes,
playback arguments, CMake checks, and the changelog describe the public behavior.
