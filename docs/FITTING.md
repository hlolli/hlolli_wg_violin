# Fitting the violin

The plug-in repo owns the real-time model and its chosen fixed values. The
shared analyzer owns audio reading, alignment, measurements, search, scoring,
and held-out checks.

Do not add private recordings to this repo. Keep them outside the worktree or
under an ignored local folder.

## Files in this repo

- `profiles/generic_violin.json` holds the fixed model data.
- `profiles/schema/` checks field shapes and bounds.
- `profiles/measurements/` holds small public numeric sources used by a fit.
- `fit/violin_fit_v1.json` maps search values to model fields.
- `tools/violin_fit_adapter.py` renders fixed probe cases for the analyzer.
- `tools/generate_profiles.py` checks the data and writes the C table.

The adapter is a thin plug-in link. Reusable audio analysis belongs in
`hlolli_wg_analyzer`, not here.

## Safe fit loop

1. Pick separate fit and check recordings.
2. Record exact file hashes as input identity, not as a claim that two audio
   recordings must have the same bytes.
3. Render the same notes, controls, sample rate, and channel layout.
4. Compare attack, held spectrum, pitch, body shape, and a clean release.
5. Reject a release window if the next note enters it.
6. Choose one candidate with a combined score and physical safety gates.
7. Write a new JSON file through the checked writer.
8. Regenerate the C table.
9. Run all native and WASM tests.
10. Listen to notes, chords, and a full phrase before keeping the change.

Do not tune string loss from one bowed note alone. Bow force, speed, position,
hair width, and body phase can move the same spectrum. Use passive string
tests and several played cases.

## Model data checks

```sh
python3 -B tools/fit_body_modes.py --check
python3 -B tools/fit_body_modes.py --self-test
python3 -B tools/generate_profiles.py --check
python3 -B tools/generate_profiles.py --self-test
```

Run `python3 -B tools/generate_profiles.py` only when you mean to replace the
generated block. Review the JSON and C diff together.

## Private reference rule

Never commit source recordings, trimmed clips, analyzer databases, or fit
output folders. A published fit may include the source name, license, byte
count, and hash when sharing those facts is safe. The runtime must remain
sample-free.
