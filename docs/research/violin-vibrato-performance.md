# Violin vibrato performance

## Scope

This note gives targets for a human vibrato controller. It uses original
measurements of violin playing, one historical violin method, and the Csound
manual and source. The studies do not measure Bach's Chaconne. Their exact
values must remain style controls, not fixed rules.

Peer-reviewed studies anchor the rate, depth, register, and slur ranges. The
exact delay, rise, and fall times come from a 2001 workshop paper based on
direct measurements and a 1998 KTH report. Those two sources did not pass the
same journal review, so use their times as first fit values and test them
against recordings.

Studies use `extent` and `width` in different ways. This project calls the
largest change from pitch centre `depth`. A reported peak-to-peak width must be
halved before use as depth.

## Measured values

| Source | Material | Rate | Depth or width | Main limit |
|---|---|---:|---:|---|
| Mellody and Wakefield, 2000 | Ten violin pitches | Mean 5.9 Hz | Mean depth 15.2 cents | Ten isolated pitches |
| Schoonderwaldt and Friberg, 2001 | Four players, Schubert *Ave Maria* | Model centre 6 Hz | Model centre 20 cents | Two professionals and two advanced students in one slow work |
| Yang, Chew, and Rajab, 2013 | Six violin recordings, 204 vibrated notes | Player means 5.82--7.33 Hz; note limits 5.13--8.23 Hz | Player means 13--16 cents; note limits 4--32 cents | A Chinese work; five recordings had backing |
| Allen, Geringer, and MacLeod, 2009 | One artist, exercises in first and fifth position | 5.7 and 6.3 Hz | Total width 40 and 108 cents | One player; the wide fifth-position result is not a general default |
| MacLeod, 2010 | Four professional soloists in recordings | Mean 6.63 Hz | Mean total width 63 cents | Four players and selected recorded passages |

Mellody and Wakefield found that a single sine fitted the pitch movement well,
but each partial also had strong level change. Their listening test found that
removing the level change altered the sound more than removing the pitch
change. A physical violin should get much of this level change as moving
partials pass through body peaks. Do not add one plain gain LFO to the whole
output. [Mellody and Wakefield, 2000](https://doi.org/10.1121/1.428326)

Yang and co-authors define depth as half the peak-to-trough pitch span. The
six players each covered a rate span of 0.90--2.38 Hz across notes. Their violin
pitch shapes had only 0.66--0.80 correlation with a matched sine, with a mean
of 0.74. Longer notes also had more humps in the depth envelope. This supports
a near-sine carrier with slow changes, not a perfect sine with fixed controls.
[Yang, Chew, and Rajab, 2013](https://luweiyang.com/wp-content/uploads/2016/05/cmmr2013_luwei_yang.pdf)

MacLeod's test of 58 student violin and viola players found that a higher
register added 0.32 Hz and about 26 cents of total width. Forte added about
four cents of total width over piano. A later study of four professional
violinists found a 6.63 Hz mean rate and a 63-cent mean total width. Thus pitch
height and loudness should shape depth, while a modern solo preset may use a
higher rate than the Chaconne preset.
[MacLeod, 2008](https://doi.org/10.1177/0022429408323070),
[MacLeod, 2010](https://doi.org/10.1177/194849921000100105)

## Time shape

The measured *Ave Maria* notes had four parts: delay, rise, sustain, and fall.
Notes under 350 ms were mostly free of vibrato. Long notes had a later start,
up to 600 ms for notes longer than 1.5 s. Measured rise and fall times were
about 350 and 300 ms. Depth could drift through the held part. Rate stayed
fairly steady within a note but often rose near its end. The paper's simple
model used a 15% rate rise over the last three cycles, linked depth to loudness
and phrase shape, and still sounded a little mechanical against measured
control curves. [Schoonderwaldt and Friberg, 2001](https://www.researchgate.net/publication/254472747_TOWARD_A_RULE-BASED_MODEL_FOR_VIOLIN_VIBRATO)

Gleiser, Friberg, and Granqvist also found that rate and depth varied both
between and within notes. Depth often rose with sound level, but the players
could vary rate, depth, and level on their own. In some notes vibrato began
only after the sound level reached its peak. [Gleiser, Friberg, and Granqvist,
1998](https://www.researchgate.net/publication/265010728_A_method_for_extracting_vibrato_parameters_applied_to_violin_performance)

In the artist case study, pitch moved both above and below its centre and each
vibrato began with a move towards the scroll, hence down in pitch. The player
stopped vibrating around slurred changes for a mean 0.33 s, mostly before the
change, then began the new note with full vibrato. One player's result should
guide a transition option, not force all slurs to act alike. [Allen, Geringer,
and MacLeod, 2009](https://doi.org/10.1177/1948499209OS-400103)

A peer-reviewed study of 40 high-school and university violin and cello
players found a break at every tested slurred change. Mean gaps were 0.42 s
for university players and 0.50 s for high-school players. This supports a
short break at finger changes, while the artist's shorter gap is the better
target for this model. [Geringer, Allen, and MacLeod,
2005](https://doi.org/10.1177/002242940505300306)

## Chords and Bach style

The modern measurement papers above give no firm phase or depth rule for each
tone of a violin chord. Do not create independent vibrato hands for chord
tones. For a two-note stopped grip, any two moving tones should share one rate
and broad phase motion. For a rolled three- or four-note chord, applying
vibrato only to the held lead is the safer first model. Open strings cannot use
left-hand pitch vibrato.

Leopold Mozart wrote in 1756 that players should not vibrate every note. He
favoured long and final notes, named slow, growing, and fast forms, and also
said that two stopped strings could vibrate together. This is direct historical
evidence, but it came 36 years after Bach dated the D-minor Partita and does
not tell us how Bach's Chaconne was played. It supports a selective Baroque
preset, not one claim of authenticity. [Leopold Mozart, *Violinschule*, chapter
11, sections 1--7](https://dme.mozarteum.at/digital-editions/violinschule/download/1756)

## Csound choices

The score already uses `vibrato`. It runs a table oscillator and varies its
amplitude and frequency with two linearly interpolated random controls. The
random values scale amplitude and rate by powers of two. `iphs` sets only the
oscillator's starting phase; it does not seed the random controls.
[Csound `vibrato` manual](https://csound.com/manual/opcodes/vibrato/),
[pinned Csound source](https://github.com/csound/csound/blob/fee3593e4c5f29a33bae6a0bab8994e5f4a3d32c/Opcodes/uggab.c#L783-L853)

`jspline` and `rspline` use cubic joins between random targets. `jspline`
returns a bipolar signal scaled by an amplitude. `rspline` maps the signal to
a stated range. Both can pass slightly outside their stated limits, so clamp
their result. Their minimum and maximum rates choose how often a new target
arrives. They suit slow drift in rate and depth. They should not replace the
5--7 Hz vibrato carrier with free random pitch motion.
[Csound `jspline` manual](https://csound.com/manual/opcodes/jspline/),
[Csound `rspline` manual](https://csound.com/manual/opcodes/rspline/),
[pinned `jspline` source](https://github.com/csound/csound/blob/fee3593e4c5f29a33bae6a0bab8994e5f4a3d32c/Opcodes/uggab.c#L1031-L1123),
[pinned `rspline` source](https://github.com/csound/csound/blob/fee3593e4c5f29a33bae6a0bab8994e5f4a3d32c/Opcodes/uggab.c#L1431-L1524)

There is no live opcode named `spline` in this Csound source. `GEN08` makes a
fixed spline table. `randomi` joins random targets with straight lines, while
`randomh` jumps between held values. Neither is a better fit here than a
clamped k-rate `jspline` or a small local spline.
[Csound `GEN08` manual](https://csound.com/manual/scoregens/gen08/),
[Csound `randomi` manual](https://csound.com/manual/opcodes/randomi/)

All these random opcodes draw from Csound's shared random state. A fixed
`seed` makes a full event schedule repeat, but a render that starts at a later
bar can consume a different part of that stream. The engine starts with a
fixed seed, but the state has no per-opcode seed or lock. If start-bar renders,
handoffs, and multi-worker tests must stay exact, derive spline knots from
stable note or gesture ids instead of call order. For a score-only first pass,
a fixed seed and a fixed schedule are enough.
[Csound `seed` manual](https://csound.com/manual/opcodes/seed/),
[pinned random-state source](https://github.com/csound/csound/blob/fee3593e4c5f29a33bae6a0bab8994e5f4a3d32c/Opcodes/uggab.h#L160-L174)

The pinned `vibrato` source swaps the amplitude-rate and frequency-rate bounds
for its first random segment. Later segments use the documented pairs. This is
another reason to use an explicit spline controller for exact tests instead of
tuning around the first segment.

## Recommended controller

Use three time scales:

1. At each note, choose whether to vibrate, its mean rate and depth, its delay,
   rise, fall, and how it acts at a slur or chord.
2. Every 0.15--0.50 s, about one to three cycles, set new rate and depth drift
   targets and join them with a cubic spline.
3. At k-rate, integrate the changing rate into phase and read a near-sine
   table. At 48 kHz and `ksmps=32`, the 1.5 kHz control rate is ample.

Good first limits for the Chaconne are:

| Control | First range |
|---|---:|
| Mean rate | 5.5--6.4 Hz |
| Per-note rate offset | about +/-0.3--0.8 Hz, clamped to 4.8--7.4 Hz |
| Slow within-note rate drift | about +/-3--8% |
| Rate lift at a shaped ending | 0--12%; reserve 15% for a clear gesture |
| Normal depth | 8--24 cents from pitch centre |
| Expressive or high-position depth | up to about 32 cents |
| Spline depth drift | about +/-10--25% of the note depth |
| Note under 0.35 s | usually no vibrato |
| Delay on a longer note | 0.10--0.60 s, rising with note length |
| Depth rise | 0.15--0.35 s |
| Depth fall | 0.10--0.30 s |

Use a light waveform change only after the envelopes sound right. A second
harmonic at roughly 5--12% of the carrier, with a slow spline change, can break
the fixed sine shape while keeping clear cycles. This is a design range, not a
measured one. The studies support a quasi-sine but do not give one reusable
harmonic coefficient.

For the Chaconne, keep open strings, fast dotted short notes, and most lower
chord tones clean. Let long stopped notes, held chord leads, cadences, and
marked upper voices carry the stronger motion. Keep a modern, more continuous
preset as a separate choice. The public violin inputs can remain mean depth
and rate; the score controller can add the human time shape without changing
the opcode API. If the same humanizer later moves into the one-file model, give
each violin handle its own small random state and spline state. Csound's random
opcodes work in a CSD and in WASM, but they do not become handle-owned model
state.
