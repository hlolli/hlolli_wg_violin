# Chaconne opening check

## Result

The first four model bars now last 2.350, 4.025, 4.005, and 2.995 seconds. The
matched reference spans last 2.350, 4.030, 4.010, and 2.990 seconds. The score
keeps every written note and changes only the tempo line.

The opening bow now stays near a 0.15 contact position. This moves the broad
250 Hz--8 kHz shape error from 3.28 to 2.93 dB RMS. The normalized 4--8 kHz
gap falls from +5.48 to +4.08 dB, and the 8--16 kHz gap falls from +8.06 to
+5.75 dB. The spectral slope moves from -9.71 to -10.22 dB per octave; the
reference measures -14.53 dB per octave. The remaining upper-band gap still
needs work.

Absolute level differs by 11.66 LU. This does not set a model gain target: the
recording includes its own microphone, distance, room, and recording gain.
The comparison therefore uses normalized band energy for tone and relative
pitch levels for chord balance.

## String holds

The four isolated source files contain these usable holds:

| String | Hold | Audio after the last held frame | Model post-bow T20 |
|---|---:|---:|---:|
| G3 | 5.05 s | 8 ms | 0.17 s |
| D4 | 4.04 s | 6 ms | 0.12 s |
| A4 | 4.14 s | 8 ms | 0.13 s |
| E5 | 3.33 s | 8 ms | 0.15 s |

The model's held-level drift differs from the recordings by at most 1.36 dB.
The source files stop too soon to measure a natural release, so their last
column describes the model only. A later body-tail fit must use notes followed
by a recorded rest.

At a 0.15 contact position, the held 250 Hz--8 kHz shape errors are 4.40 dB
for G, 3.19 dB for D, 2.88 dB for A, and 4.18 dB for E. D, A, and E still have
too little downward spectral slope. The current bounded bridge-cutoff fit made
that direct check worse, so the profile kept its present loss values.
