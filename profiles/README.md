# Fixed violin data

The plug-in ships one built-in violin. Callers do not choose a profile file.

`generic_violin.json` holds the checked source data. Its string order is G, D,
A, E. `manifest.json` names the fixed default. The schema rejects unknown
fields and values outside the safe ranges.

The runtime reads no JSON. `tools/generate_profiles.py` writes a C table into
`src/hlolli_wg_violin.c` and stores the source hash with it. Do not edit that
table by hand.

```sh
python3 -B tools/fit_body_modes.py --check
python3 -B tools/fit_body_modes.py --self-test
python3 -B tools/generate_profiles.py --check
python3 -B tools/generate_profiles.py --self-test
```

The five lowest body modes come from
`measurements/holm_valimaki_2000_table1.json`. A schema change needs a new
schema version and matching C code.
