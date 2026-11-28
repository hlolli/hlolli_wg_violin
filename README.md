# hlolli_wg_violin

`hlolli_wg_violin` is a sample-free violin for Csound 7. It runs as a native
plug-in and as a browser WASM opcode. One handle owns four strings, one body,
and all the state that carries between notes.

The plug-in reads no audio or JSON while it plays. Its fixed violin data is
generated into the same C file used by native and WASM builds.

## Hear it

Build the plug-in, then play the short technique demo:

```sh
cmake --build build --target play_solo_techniques
```

Play the Bach Chaconne:

```sh
cmake --build build --target play_bach_chaconne
```

Start at a bar or write a 24-bit WAVE file:

```sh
cmake -DSTART_BAR=93 -P build/play_bach_chaconne.cmake
cmake -DSTART_BAR=93 \
  -DOUTPUT=/absolute/path/chaconne-93.wav \
  -P build/play_bach_chaconne.cmake
```

The default is live sound. The Chaconne adds its own small room and a 2.5 m
listener distance outside the plug-in.

## Use it

Create one handle for each player. Pass an optional A4 pitch when the group
tunes above or below 440 Hz.

```csound
giViolin hlolli_wg_violin_create
giViolin442 hlolli_wg_violin_create 442

aDryL, aDryR hlolli_wg_violin \
    kTrigger, kFrequency, kForce, kSpeed, kPosition, \
    kVibratoDepth, kVibratoRate, kArticulation, \
    kHarmonic, kStrange, iString, giViolin

aBodyL, aBodyR hlolli_wg_violin_resonance \
    giViolin, kBody, kSympathetic, kMute
```

`iString` is `0` for automatic choice or `1` to `4` for G, D, A, and E.
Use one voice opcode for each note in a double stop. Keep the resonance opcode
alive after the last note if you want to hear the body tail.

See [docs/API.md](docs/API.md) for every input and articulation code.

## Build

You need CMake, a C compiler, Ninja, and Csound 7 headers.

```sh
cmake -S . -B build -G Ninja \
  -DHLOLLI_CSOUND_BUILD_DIR=/path/to/csound/build \
  -DHLOLLI_CSOUND_SOURCE_DIR=/path/to/csound \
  -DCSOUND_EXECUTABLE=/path/to/csound/build/csound
cmake --build build
ctest --test-dir build --output-on-failure
```

Copy `Custom.cmake.example` to `Custom.cmake` if you want to keep local paths
out of the command line.

The output is:

| System | File |
|---|---|
| macOS | `build/libhlolli_wg_violin.dylib` |
| Linux | `build/libhlolli_wg_violin.so` |
| Windows | `build/hlolli_wg_violin.dll` |

See [docs/BUILD.md](docs/BUILD.md) for install, Csound-tree, WASM, and test
commands.

## What is in the model

- Four phase-preserving waveguide strings.
- A nonlinear bow with contact memory, heat, and hair motion.
- Détaché, martelé, spiccato, tremolo, pizzicato, and col legno.
- Natural and artificial harmonics.
- Smooth pitch changes and same-string legato.
- Open-string sympathy through the bridge.
- A seventeen-mode violin body with a stereo return.
- Per-handle state, so two players do not share phase or noise.
- Finite-state checks and bounded recovery paths.

The plug-in adds no room and no output tone EQ. Scores may add distance and
room effects after the dry and body signals are mixed.

Read [docs/MODEL.md](docs/MODEL.md) for the state and signal rules. Read
[docs/FITTING.md](docs/FITTING.md) before changing fitted values.

## Examples

| File | Use |
|---|---|
| `examples/basic.csd` | Small API and articulation tour |
| `examples/solo_techniques.csd` | Focused solo techniques |
| `examples/string_section.csd` | Four separate violin handles |
| `examples/bach_chaconne.csd` | Full Chaconne with bar-start playback |
| `examples/infinite_bow.csd` | Four strings with continuous same-string phrases |
| `examples/paganini_caprice_24.csd` | Full Caprice No. 24 |
| `examples/wasm_smoke.csd` | Browser build smoke test |

## Analysis and fitting

The [checked analyzer adapter](tools/analyzer_adapter/README.md) builds private
fit bundles and tests them through the shared analyzer. Its tools path is
explicit, so the two checkouts need not sit next to each other.

## License

GPL-3.0-only. See [LICENSE](LICENSE). The checked analyzer adapter and
`tests/test_analyzer_adapter.py` retain their
[MIT license](tools/analyzer_adapter/LICENSE).
