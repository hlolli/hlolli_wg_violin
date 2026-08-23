# Tools

These scripts run offline. None is part of the audio thread.

| Script | Job |
|---|---|
| `generate_profiles.py` | Check JSON and update the generated C model table |
| `fit_body_modes.py` | Check the five published low body modes |
| `prepare_wasm_source.py` | Make the bounded browser source |
| `run_wasm_workbench_test.ts` | Compile and play the WASM opcode |
| `generate_caprice_24_demo.py` | Check or rebuild the Caprice event list |
| `generate_bach_chaconne_demo.py` | Check or rebuild the Chaconne event lists |
| `play_bach_chaconne.py` | Start the Chaconne at a bar or render a file |
| `generate_physical_probes.py` | Render fixed probe cases for an analyzer |
| `render_realism_diagnostics.py` | Render component splits for local checks |
| `violin_fit_adapter.py` | Connect fixed violin renders to the analyzer fit tool |

Run model checks:

```sh
python3 -B tools/fit_body_modes.py --check
python3 -B tools/generate_profiles.py --check
```

Run generator self-tests:

```sh
python3 -B tools/fit_body_modes.py --self-test
python3 -B tools/generate_profiles.py --self-test
```

Read [docs/FITTING.md](../docs/FITTING.md) before using private recordings or
changing fitted values. Reusable audio analysis belongs in
`hlolli_wg_analyzer`. Keep only the thin renderer link and chosen model data in
this repo.
