# AGENTS.md

This repo builds a sample-free violin opcode for Csound 7. Native and WASM
builds use the same C file.

Read [README.md](README.md), [docs/API.md](docs/API.md), and
[docs/MODEL.md](docs/MODEL.md) before changing the model.

## Main files

- `src/hlolli_wg_violin.c` is the only model source.
- `profiles/generic_violin.json` is the fixed build-time model data.
- `CMakeLists.txt` builds the release and private test modules.
- `tests/` holds Csound scores and Python test runners.
- `examples/` holds scores meant for listening.
- `tools/` holds generators and offline plug-in adapters.
- `docs/research/` holds reports. It is not runtime input.

## Build

```sh
cmake -S . -B build -G Ninja \
  -DHLOLLI_CSOUND_BUILD_DIR=/path/to/csound/build \
  -DHLOLLI_CSOUND_SOURCE_DIR=/path/to/csound \
  -DCSOUND_EXECUTABLE=/path/to/csound/build/csound
cmake --build build
ctest --test-dir build --output-on-failure
```

Csound 7 headers are required. A sibling `../csound` checkout is found by
default. Copy `Custom.cmake.example` to the ignored `Custom.cmake` file for
local paths.

## Before you edit C

- Keep C11 with no compiler extensions.
- Keep one source file for native and WASM.
- Do not split test and release DSP into two copies.
- Do not add runtime audio, JSON, files, or heap work in the audio loop.
- Do not add output tone EQ. Put fitted loss inside the physical path.
- Do not round fitted constants because they look untidy.
- Add a comment only when it explains a rule the code cannot state.
- Run the matching focused test before the full suite.

The generated block between `BEGIN GENERATED VIOLIN PROFILE DATA` and its end
marker must not be edited by hand.

## Model-data changes

Change the JSON, then regenerate the C table:

```sh
python3 -B tools/generate_profiles.py
python3 -B tools/generate_profiles.py --check
python3 -B tools/generate_profiles.py --self-test
```

Also run the body-mode check when its source values move:

```sh
python3 -B tools/fit_body_modes.py --check
python3 -B tools/fit_body_modes.py --self-test
```

The schema checks shape and simple bounds. The generator checks rules between
fields, such as matrix symmetry and ordered body modes.

## State rules that must stay true

- One handle owns one violin and four physical strings.
- One voice owns one string at a time.
- State lives on the handle, not on a score note.
- A trigger release damps contact. It does not erase the rail.
- A true legato handoff keeps rail, bow, finger, vibrato, and noise state.
- A new attack may keep the rail while it rearms bow contact.
- No two opcode instances may overlap ownership of one string.
- Short gaps step state. Medium gaps use bounded decay. Long gaps clear it.
- One renderer owns one handle's body.
- The renderer reads prior-block bridge sends, so run order does not matter.
- Separate handles share no phase, state, or random history.
- Automatic string choice never goes below an open string.
- Harmonic choice uses the derived internal string pitch.
- `kStrange = 0` is the neutral path.

Most hard bugs in this repo break one of these rules.

## Tests

All exact renders use `--sample-accurate --num-threads=1`. Keep those flags.
The worker test also runs eight handles with two workers.

Run one test by name:

```sh
ctest --test-dir build -R hlolli_wg_violin.string --output-on-failure
```

After a model change, run:

```sh
cmake --build build --target hlolli_wg_violin_check_profiles
cmake --build build --target hlolli_wg_violin_wasm_source_check
ctest --test-dir build --output-on-failure
```

Run `hlolli_wg_violin_check_wasm` when Bun and the browser workbench are ready.

The private `hlolli_wg_violin_test_*` opcodes exist only in builds compiled
with `HLOLLI_WG_VIOLIN_TEST_API=1`. Never register them in the release build.

## Private recordings

Do not commit reference audio, analyzer databases, fit output, or local clips.
The ignored `hlolli/` folder may hold private files on one machine. The shared
analyzer owns reusable audio measurement and fit code. This repo owns the
renderer adapter and the chosen fixed model data.

## Finish a change

- Run `git diff --check`.
- Run the narrow test first, then the full suite.
- Check the generated model data.
- Check native and WASM source equality after a C change.
- Update the `Unreleased` part of [CHANGELOG.md](CHANGELOG.md).
- Keep public text short and literal.
