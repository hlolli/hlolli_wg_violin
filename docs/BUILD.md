# Build and test

## What you need

- CMake 3.16 or newer
- a C11 compiler
- Ninja or another CMake build tool
- Python 3.8 or newer for tests and generators
- Csound 7 headers
- a Csound 7 program for render tests

The default paths expect sibling `csound` and `csound-wasm-plugin-compiler`
folders under the same parent folder as this repo.

## Stand-alone build

```sh
cmake -S . -B build -G Ninja \
  -DHLOLLI_CSOUND_BUILD_DIR=/path/to/csound/build \
  -DHLOLLI_CSOUND_SOURCE_DIR=/path/to/csound \
  -DCSOUND_EXECUTABLE=/path/to/csound/build/csound
cmake --build build
ctest --test-dir build --output-on-failure
```

If one installed folder contains `csdl.h`, `version.h`, and
`float-version.h`, use this instead:

```sh
cmake -S . -B build -G Ninja \
  -DHLOLLI_CSOUND_INCLUDE_DIR=/path/to/csound/headers
```

Copy `Custom.cmake.example` to the ignored `Custom.cmake` file to store local
paths.

## Useful checks

Run one test:

```sh
ctest --test-dir build -R hlolli_wg_violin.bow --output-on-failure
```

Check the model data and generated C:

```sh
cmake --build build --target hlolli_wg_violin_check_profiles
```

Build and play the browser version when Bun and the workbench are present:

```sh
cmake --build build --target hlolli_wg_violin_check_wasm
```

The build strips test-only code and comments to make
`build/wasm/hlolli_wg_violin.c`. A native test compiles that file and requires
the same PCM as `src/hlolli_wg_violin.c`.

Run the fixed release cost check:

```sh
cmake --build build --target benchmark_release
```

Run the two focused cost tools with:

```sh
cmake --build build --target benchmark_bow_contact
cmake --build build --target benchmark_sympathetic
```

## Build inside Csound

Add the repo after Csound defines `make_plugin()`:

```cmake
add_subdirectory(
  "/absolute/path/to/hlolli_wg_violin"
  "${CMAKE_BINARY_DIR}/hlolli_wg_violin"
)
```

The target is `hlolli_wg_violin`. Its alias is `hlolli::wg_violin`.

## Install

```sh
cmake --install build --prefix "$HOME/.local"
```

Set `HLOLLI_CSOUND_PLUGIN_DIR` if Csound uses another plug-in folder.

## Test modules

The build can make three modules from the same source:

- `hlolli_wg_violin` is the plug-in users load.
- `hlolli_wg_violin_test` adds private state probes.
- `hlolli_wg_violin_wasm_source_check` compiles the prepared browser source.

A thermal-neutral test build also exists for one physics comparison. Install
rules ship only the normal plug-in.

Every exact render uses `--sample-accurate --num-threads=1`. The worker test
also runs eight handles with two workers. Do not weaken those settings when a
change touches ownership or handoff code.

## CI

GitHub Actions uses fixed Csound and browser-workbench commits. It checks the
generators, builds with strict warnings, runs the native suite, and compiles
the WASM opcode. Keep local results on the same pins before changing a golden
audio or cost value.
