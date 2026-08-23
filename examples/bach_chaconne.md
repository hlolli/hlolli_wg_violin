# Bach Chaconne demo

`bach_chaconne.csd` plays the full Chaconne from Partita No. 2 in D minor,
BWV 1004. It uses the violin plug-in alone, followed by a quiet, generated
0.20-second stereo room. It adds no guide voice, EQ, or audio sample.

The generator reads all four LilyPond voices. It keeps all 3,123 written notes
over 257 bars, including unison notes in separate voices. Every note names one
physical string: `1` is G, `2` is D, `3` is A, and `4` is E. The map favours
open strings and low positions, keeps chord pitches in low-to-high string
order, and keeps a slurred voice on one string when the grip allows it. The bow
breaks each three- or four-note onset across the two bow planes. The lower pair
speaks first, followed by the upper note or pair. A non-lead note then rings on
stored string and body motion. Only the marked upper voice keeps bow contact.
Two-note stops begin together. No written attack is dropped. The closing D is
a stopped-and-open unison on the G and D strings.

Positive bow speed is a down bow. Negative speed is an up bow. Each
non-slurred bow group starts one shared stroke a few milliseconds before its
written attack. Bow speed crosses through zero at the change, while string
contact and stored motion stay alive. Down and up strokes use different force,
speed, and contact points.
Chord strokes add a small push near the middle and unload without dropping the
lead voice. Single-note strokes keep even bow input. Across all 487 written
chord onsets, contact moves from the lower bow plane to the upper one over as
much as 650 ms. The span scales with the written note length. On long chords,
the lower plane remains bowed through the turn and overlaps the upper attack
before it releases. The marked lead then stays under the bow.
The highest active written voice keeps the lead even when a lower voice starts
a new note. Notes below it step down by pitch. LilyPond slurs keep the same
stroke and a positive gate. Their pitch handoff uses a 3 ms half-time, which
joins the notes without turning the written slur into a slide.

The generator marks each true 3:1 dotted figure. Its short note gets 0.055
more dynamic, 10 percent more bow force, and 8 percent more bow speed. This
affects 143 note rows and leaves ordinary short notes alone.

Stopped single notes and the written lead of chords get vibrato when they last
at least a quarter beat. Each note has its own mean depth and rate. Slow cubic
splines vary both controls over a few cycles, the cycle is a little uneven,
and longer notes get a gradual rise and a small rate lift near the end. Mean
targets span about 10 to 24 cents and 5.2 to 6.2 Hz. This gives pitch motion to
1,280 note rows. Open strings, lower chord notes, and the 143 crisp dotted
short notes stay clean. The plug-in's vibrato inputs stay at zero, so one
pitch source owns the motion. The measured ranges and style limits behind this
plan are in `../docs/research/violin-vibrato-performance.md`.

The first four bars follow the measured phrase spans of the private reference:
2.350, 4.025, 4.005, and 2.995 seconds. Their bow contact stays near 0.15 of
the string length, which cuts the excess high-band energy without output EQ.
Later sections retain their prior contact points.

Play the demo after building:

```sh
cmake --build build --target play_bach_chaconne
```

Start at a written bar with a one-shot CMake script:

```sh
cmake -DSTART_BAR=93 -P build/play_bach_chaconne.cmake
```

Add an absolute `OUTPUT` path to write a trimmed 24-bit, 48 kHz stereo WAVE
file. With no `OUTPUT`, playback uses the default audio device.

```sh
cmake -DSTART_BAR=93 -DOUTPUT=/absolute/path/chaconne-93.wav \
  -P build/play_bach_chaconne.cmake
```

The listener defaults to 2.5 metres from the violin. Set
`DISTANCE_METERS=1` for the old close position, or use a value through 50 for
a more distant player. Distance adds relative travel time, lowers direct
level, softens the directional high end, and keeps diffuse room energy steady.

```sh
cmake -DSTART_BAR=231 -DDISTANCE_METERS=1 \
  -P build/play_bach_chaconne.cmake
cmake -DSTART_BAR=231 -DDISTANCE_METERS=2.5 \
  -P build/play_bach_chaconne.cmake
```

Set `VIBRATO_LEVEL=0` for a no-vibrato comparison. Values through 2 scale the
same written vibrato plan without changing which notes receive it.

```sh
cmake -DSTART_BAR=93 -DVIBRATO_LEVEL=0 \
  -DOUTPUT=/absolute/path/chaconne-93-no-vibrato.wav \
  -P build/play_bach_chaconne.cmake
```

The player starts its hidden preparation at the active bow stroke, then opens
the output at the requested bar. This keeps the first bow change intact. It
does not rebuild the waveguide history from every earlier bar, so a bar start
is for rehearsal and listening, not a byte-identical slice of a full render.

Useful score macros are:

```sh
csound \
  --opcode-lib=build/libhlolli_wg_violin.dylib \
  -odac \
  --omacro:MODEL_LEVEL=0.75 \
  --omacro:SYMPATHETIC_LEVEL=0.35 \
  --omacro:VIOLIN_REFERENCE_PITCH=442 \
  --omacro:VIBRATO_LEVEL=1 \
  --omacro:VIOLIN_DISTANCE_METERS=2.5 \
  --omacro:ROOM_LEVEL=0.05 \
  examples/bach_chaconne.csd
```

Csound prints `BAR 1` through `BAR 257` as the movement plays. Set
`SHOW_BARS=0` to hide those numbers. `SHOW_MARKS=0` hides section text.
`VIOLIN_REFERENCE_PITCH` sets A4 for both the score and the physical violin
and defaults to 440. The
fixed event list lives in `bach_chaconne_score.inc`. `ROOM_LEVEL=0` makes the
score dry. `VIOLIN_DISTANCE_METERS` accepts 1 through 50 and defaults to 2.5.
