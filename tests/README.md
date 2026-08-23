# Tests

CTest runs the whole suite:

```sh
ctest --test-dir build --output-on-failure
```

Run one area while editing:

```sh
ctest --test-dir build -R hlolli_wg_violin.bow --output-on-failure
```

Each Python runner calls Csound with a small CSD and checks fixed text, state,
or PCM facts. Exact renders use `--sample-accurate --num-threads=1`. The
release worker gate also uses two workers.

| Area | Main files |
|---|---|
| API and ownership | `smoke.csd`, `ownership.csd`, `handoff.csd` |
| String and bow | `string.csd`, `bow.csd` |
| Body and sympathy | `body.csd`, `sympathetic.csd` |
| Legato and harmonics | `legato.csd`, `harmonics.csd` |
| Plucks and wood | `exciters.csd` |
| Bow gestures | `gesture.csd` |
| Contact and recovery | `physics.csd` |
| Fixed model data | `profiles.csd` |
| Native and worker release gate | `release_gate.csd`, `run_release_gate.py` |
| Chaconne | `run_chaconne_*_test.py`, `bach_stroke_shape.csd` |
| Distance | `violin_distance.csd` |

The release module exposes only the three public opcode names. CMake builds a
private test module from the same source with diagnostic opcodes enabled.

When a test prints fixed fields, its runner owns that output format. Change the
CSD and runner together.
