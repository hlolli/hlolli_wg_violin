# Changelog

## Unreleased

- License the plug-in under GPL-3.0-only.
- Move the model source to `src/`, group research under `docs/`, and move
  test-only scripts into `tests/`. Replace the completed plan with short API,
  model, build, and fitting guides.
- Rename numbered test and benchmark files by what they check. Add strict C
  warnings, remove dead stores, and name all public articulation codes in C.
- Split GitHub Actions into quick source checks, native tests, and a browser
  WASM check.
- Use the fixed built-in model directly in all public scores and docs. The old
  named constructors remain for source compatibility.
- Add an optional i-rate A4 reference to violin creation. It retunes all four
  open strings, finger geometry, harmonics, automatic choice, and sympathy.
- Lower bow rosin noise by 20 percent so it stands out less at note attacks.
- Keep the quiet direct string tap near the radiated body level so ordinary
  bowed attacks do not expose the raw bridge spectrum.
- Add a smooth 0.10-sample delay correction for plain bowed contact far from
  the bridge so the solver does not lock to the audio sample grid. Passive,
  plucked, and natural-harmonic tuning stays unchanged.
- Use four-point fractional-delay reads in both string rails. Passive string
  decay now stays steady when the inactive bow junction moves, and the pitch
  solver includes the new delay phase.
- Set the detache release tail to 0.38 seconds. A clean held-note recording now
  passes the release-level and darkening checks, while the resonant body stays
  louder and decays more slowly than the direct string in the tail. The body
  resonance check now measures each mode against its nearby bands instead of
  selecting a direct-path spectral null.
- Fit the G, D, A, and E bridge loss cutoffs at 5.387, 4.964, 7.086, and
  6.025 kHz. Against separate fit and held-out recordings, this lowers
  body-shape error from 9.09 to 6.63 dB and from 8.50 to 6.52 dB without
  output tone EQ.
- Keep body-mode widths within 90 to 100 percent of their measured values
  across the full `kBody` range.
- Keep the negative `kStrange` limit weak and airy after the body fix.
- Add a full Bach Chaconne demo read from all four LilyPond voices, with fixed
  strings, written slurs, score-linked shared bow strokes, physical voice and
  chord balance, and delayed Csound vibrato.
- Extend delayed Chaconne vibrato from 126 to 1,280 stopped single and
  written chord-lead notes, then raise it to a clear 12 to 24 cent range with
  a faster onset. Open strings and dotted short notes stay clean.
- Replace the Chaconne's near-fixed vibrato with note-specific mean values,
  slow cubic spline drift, a shaped rise, and a small late rate lift.
- Give Chaconne chords a curved bow path and a small mid-stroke push. Keep
  enough contact, force, and speed through the full stroke that bars 111--112
  lose at most 1.43 dB inside a bowed beat instead of 8.54 dB. Single-note
  strokes now keep even bow input instead of adding a false rising envelope.
- Break all 487 written Chaconne chord onsets across the lower and upper
  two-string bow planes. Contact time scales with note length. Non-lead notes
  then ring from stored motion while only the marked upper voice stays bowed.
- Lower body level and modal Q during three- and four-note Chaconne grips so
  the sparse mode bank does not build into metal-like chord resonances.
- Keep held upper Chaconne voices in charge of the shared bow, accent the 143
  written dotted-rhythm short notes, and add a quiet 0.20-second neutral room.
- Keep string contact and stored motion alive between joined Chaconne notes.
  Dotted short notes now speak through extra bow speed and force, while a real
  rest remains the only score event that releases the string.
- Add bar-start playback and optional 24-bit WAVE output for the Chaconne.
- Add a reusable 1-to-50-metre listener-distance Module. The Chaconne now
  defaults to 2.5 metres, with travel time, direct loss, mild high-frequency
  loss, and distance-independent diffuse room energy kept behind one parameter.
- Shorten the Chaconne's plain-slur pitch half-time from 22 ms to 3 ms so
  quick runs stay connected without sounding like glissando.
- Emit one stopped-finger event burst at the start of a continuous move,
  while per-sample movement noise follows the rest of the move.
- Match the first four Chaconne bar spans to the reference phrase and use a
  darker opening contact point. The 250 Hz--8 kHz shape error falls from 3.28
  to 2.93 dB RMS without output EQ.
- Add a four-string hold and spectrum check. It records the usable reference
  hold, held-level drift, model tail, band shape, slope, and spectral centre,
  and flags source clips that contain no useful release tail.
- Extend the real-note transient check to measure the attack curve, attack
  spectral change, and held-level direction. Direct-string and body-only
  renders now show which part causes a failed build-up or release.

## 1.0.0 - 2026-08-13

- Add four persistent waveguide strings, nonlinear bow contact, legato,
  harmonics, pizzicato, col legno, open-string sympathy, and a modal body.
- Add one fixed violin profile and offline fit checks.
- Add native, worker, browser WASM, stress, recovery, and performance gates.
- Add a solo technique tour, four-player section, and full Paganini Caprice
  No. 24 demo.
- Keep the runtime sample-free.
