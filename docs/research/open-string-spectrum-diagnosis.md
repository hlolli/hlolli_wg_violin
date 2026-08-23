# Open-string spectrum diagnosis

Date: 2026-08-23

## Result

The current passive string loss is not the cause of the held-tone mismatch.
The seeded, bow-free string test passes tuning, loss, high-frequency darkening,
repeat output, and bow-position stability. Nut and bridge cutoff changes move
the bowed string between different stick-slip cycles, so they do not act like
a smooth tone control.

The private recordings do not state bow force, speed, position, or microphone
phase. They also leave only 6--8 ms after the held sound, which is too short to
fit passive decay.

## Measurement repair

The old check wrote the model as 16-bit PCM. Quiet upper bins then reached the
file's rounding floor and moved the whole-FFT slope. The check now writes
24-bit PCM. A common tenfold output gain leaves the new band shape and centre
unchanged.

The whole-FFT slope stays in the report, but it no longer decides pass or fail.
The hard held-tone checks use normalized band-shape error, spectral-centre
ratio, and early-to-late level drift.

## Bounded control check

Each reference shape is inside the model's normal public bow-control range:

| String | Force | Speed | Position | Shape error | Centre ratio |
| --- | ---: | ---: | ---: | ---: | ---: |
| G3 | 0.46 | 0.62 | 0.15 | 3.27 dB | 0.885 |
| D4 | 0.38 | 0.42 | 0.11 | 3.62 dB | 1.197 |
| A4 | 0.46 | 0.62 | 0.15 | 2.48 dB | 0.979 |
| E5 | 0.46 | 0.52 | 0.16 | 2.44 dB | 0.758 |

The limits are 4 dB for shape and 0.75--1.33 for centre ratio. All four held
level drift checks also pass.

## Dry and body timing

The voice writes direct sound and bridge force from the same string sample.
The body reads that force one engine block later to stay independent of opcode
order. Their unaligned sum therefore has a scheduler-dependent phase pattern.
A 32-sample dry delay at 44.1 kHz improves D and A but makes G and E worse
against these four recordings. It is useful as a cause split, not as a string
loss fit.

Any score that needs a time-aligned dry-plus-body mix should delay the summed
dry bus by one engine block in its always-running violin output handler. The
voice opcode should stay undelayed for direct-only use.

## Next physical change

A point bow can bias high partials. Published tests show that bow-hair width,
force, and speed can each move upper partials by several decibels. Do not add an
output low-pass filter. If matched recordings across several force and speed
settings still show a source error, test a finite-width bow contact as a new
physical model step.

Sources: [Schoonderwaldt, Guettler, and Askenfelt, 2003][bow-width] and
[Serafin and Smith, 2000][two-edge].

[bow-width]: https://knutsacoustics.com/files/bow-width-smac03-.pdf
[two-edge]: https://www.dafx.de/paper-archive/2000/pdf/Serafin_Stefania_paper.pdf
