# Violin physics review

25 November 2026

## Reproduced defects

### Pitch reversals bypass the delay slew limit

The delay update takes the full remaining step when the smoothed velocity
still points away from the new target. That can happen when the pitch
reverses before a glide has settled. At 48 kHz and `ksmps=8`, a held A
string commanded to 440 Hz, then 660 Hz for 80 samples, then back to 440 Hz
jumped from 94.811665 to 108.175886 delay samples in one audio sample.
The step was 13.364221 samples. The intended limit is 0.25. An abrupt change
in the read position can recirculate a discontinuity as an extra attack
during a slur. Add an in-flight reversal case to the legato tests and check
both the delay step and the waveform around the turn.
[Delay update](../../src/hlolli_wg_violin.c#L5548-L5560),
[Jaffe and Smith, section 2.2](https://www.davidajaffe.com/writings/performance-expression-in-commuted-waveguide-synthesis-of-bo.html).

### The bridge output uses the return trip

The bow junction needs the round-trip delay to pick up the reflection. The
bridge force tap uses the same delayed sample. Physical force at the bridge
uses the waves at the termination, reached after one leg from the contact
point. The tap supplies both the direct output and the body drive. At
48 kHz, an open-G pizzicato render showed the following first nonzero direct
samples, using a threshold of 1e-10.

| Contact distance as a fraction of string length | Measured sample | Ideal one-way travel in samples |
| ---: | ---: | ---: |
| 0.12 | 28 | 14.7 |
| 0.24 | 57 | 29.4 |
| 0.40 | 96 | 49.0 |

The ideal column is `position * sample_rate / (2 * fundamental)`.
Interpolation and the loop phase correction account for small offsets. The
slope across positions shows the factor of two. A bridge tap at the physical
termination would preserve the round-trip delay used by the bow while
correcting the timing of the radiation drive. After that change, recheck
attack timing and the phase between strings in double stops.
[Delay split](../../src/hlolli_wg_violin.c#L2116-L2125),
[Bridge read](../../src/hlolli_wg_violin.c#L5628-L5657),
[Force tap](../../src/hlolli_wg_violin.c#L5715-L5725),
[Pakarinen, Fig. 2 and Eq. 8](https://www.ee.bilkent.edu.tr/~signal/defevent/papers/cr1264.pdf).

### The audio block sets the phase of sympathetic feedback

The renderer and string coupling both read the previous engine block. The
renderer delay is a known output latency. The coupling delay sits inside
the instrument, so its phase is part of the synthesized response. The
coupling also uses a fixed matrix and skips the source string itself. The
body's resonators radiate sound but do not provide the frequency-dependent
bridge admittance that the bow sees. The minimum-force map has the expected
inverse-square dependence on position before its clamps. It uses a fitted
divisor in place of the bridge resistance in the simple Schelleng model.
It cannot reproduce the pitch-dependent changes in bowing limits that
Mansour and colleagues traced to bridge motion.

In a steady bowed open D at 48 kHz, with fixed controls and sympathy off,
direct PCM matched at block sizes 8, 32, and 128 over the measured window.
With sympathy on, I
removed the renderer's one-block offset and subtracted each sympathy-off
wet render from its matching sympathy-on render. The difference signal
sat about 34.5 dB below the wet output. Its RMS difference between blocks
8 and 32 was 1.64 times its RMS at block size 8. This confirms a change in
the phase and waveform of the added response. The effect on the full wet
signal was small in this probe. A physical bridge model needs a sample-rate
or fixed internal substep with measured admittance, while the host output
can still account for block scheduling.
[String coupling](../../src/hlolli_wg_violin.c#L4898-L4976),
[Force map](../../src/hlolli_wg_violin.c#L4990-L5044),
[Body input](../../src/hlolli_wg_violin.c#L7427-L7456),
[Mansour, Woodhouse and Scavone, sections 2–4](https://dael.euracoustics.org/bin/EAA/aaua_dl?document_id=52343).

## Sound limits

- **Harmonics use a comb in the string loop.** The code computes the
  harmonic touch coordinate, then exposes it through the diagnostic opcode.
  The audio path averages delayed copies of the nut reflection based on
  harmonic order and period. This suppresses unwanted partials but cannot
  represent scattering or damping at the finger, or its relation to bow
  position. The existing test checks the reported coordinate and the
  resulting spectrum. A test for a spatial damper would compare how
  individual partials decay when the touch moves on and off a node.
  [Touch calculation](../../src/hlolli_wg_violin.c#L2654-L2691),
  [Comb](../../src/hlolli_wg_violin.c#L3585-L3666),
  [Harmonic test](../../tests/run_harmonic_test.py#L313),
  [Pakarinen, sections 2–3](https://www.ee.bilkent.edu.tr/~signal/defevent/papers/cr1264.pdf).
- **Point bow omits the contact width.** The model includes contact
  memory, a heat state, and one hair motion state. The single junction
  cannot reproduce one edge slipping while the other edge sticks.
  Schoonderwaldt and colleagues measured changes of 3–6 dB above partial
  20 when they narrowed the hair. That makes bow width a candidate for
  held-tone brightness and attack texture. The recordings cited by the
  existing project diagnosis lack matched bow controls, so they cannot
  establish the size of this effect in the plug-in. A two-edge
  experiment would give a more direct comparison than changing string
  loss again.
  [Bow junction](../../src/hlolli_wg_violin.c#L5665-L5689),
  [Earlier spectrum check](open-string-spectrum-diagnosis.md),
  [Schoonderwaldt, Guettler and Askenfelt](https://knutsacoustics.com/files/bow-width-smac03-.pdf),
  [Serafin and Smith](https://www.dafx.de/paper-archive/2000/pdf/Serafin_Stefania_paper.pdf).
- **The Chaconne changes the body with chord size.** The score moves
  `kBody` from 0.78 to 0.18 or 0.14 when three or four strings play.
  This cuts the wet gain target by about 13 or 15 dB, respectively, and
  changes modal gain and decay. A linear body model keeps the transfer
  function fixed as the string forces add. The score also mixes the
  current direct output with wet output delayed by one block. The
  block offset changes their relative phase by 180 degrees at 750 Hz
  at 48 kHz and `ksmps=32`, before the body's own phase. The score
  gain and the timing can be tested separately with fixed body settings
  and a delay on the summed direct bus.
  [Chaconne body and mix](../../examples/bach_chaconne.csd#L441-L469),
  [Body coefficients](../../src/hlolli_wg_violin.c#L4117-L4151),
  [Holm and Välimäki, sections 3 and 5](https://eurasip.org/Proceedings/Eusipco/Eusipco2000/SESSIONS/FRIPM/SS1/CR1706.PDF).

Holm and Välimäki's Table 1 frequencies and bandwidths match the first
five profile modes. Their relative levels match after conversion from dB
and normalization to the largest peak. The complex pole formula uses the
correct bandwidth-to-decay relation. The radiating body and the admittance
needed for string feedback are separate measurements. The table supplies
the former.
[Measurements](../../profiles/measurements/holm_valimaki_2000_table1.json),
[Holm and Välimäki, Table 1 and section 4](https://eurasip.org/Proceedings/Eusipco/Eusipco2000/SESSIONS/FRIPM/SS1/CR1706.PDF).

The adapted bow laws also warrant a transient test. The base slip root is
solved with a velocity curve scaled by the current heat state. The memory
update then changes the force, and heat advances from that result. The
recorded root residual therefore describes the first solve. The useful
targets are final force, slip timing, and pre-Helmholtz periods across
matched attacks. The papers use richer contact and hair dynamics.
[Bow solve and memory update](../../src/hlolli_wg_violin.c#L5389-L5496),
[Galluzzo, Woodhouse and Mansour](https://www.repository.cam.ac.uk/items/872131e9-6e51-4d90-a5ee-dde02409ebe3),
[Serafin, Avanzini and Rocchesso](https://avanzini.di.unimi.it/downloads/publications/serafin_smac03.pdf),
[Maestre, Spa and Smith](https://zenodo.org/records/850848).

## CPU cost

**The delay solver repeats the same trigonometry at every bisection step.**
A change in pitch or position reruns a 48-step solve. The sine and cosine
values depend on the target pitch, which stays fixed during that solve.
I tested a temporary build that moved those calculations out of the
iterations. With the release benchmark's bow position moving from 0.12
to 0.22, the median CPU time fell from 106 to 98 ms for one stopped
string and from 1,292 to 1,237 ms for eight players. Each case used seven
five-second runs on this arm64 Mac. These are about 7.5% and 4.2% gains
for the two loads. Float32 PCM matched byte for byte on both loads.
The held-note reflection path also calls two
`pow` functions with a base of one per sample. A temporary bypass
showed no consistent speedup across both stock benchmark loads.
[Phase solver](../../src/hlolli_wg_violin.c#L2127-L2235),
[Reflection path](../../src/hlolli_wg_violin.c#L5600-L5658),
[Benchmark score](../../benchmarks/release_loads.csd).

## Scope and test setup

I reviewed the current working tree and built the C source outside the
checkout with Apple Clang at `-O3`. The native probes used Csound 7 commit
`8047075e6`, `--sample-accurate`, and `--num-threads=1`. The pitch reversal
used a temporary trace of the delay step. It used force 0.46, speed 0.52,
position 0.15, direct arco and no vibrato. The sympathy render used the same
controls, `kBody=0.72`, `kMute=0`, and measured samples 24,000 through
45,999 after delay alignment. The pizzicato used force 0.55, speed 0.60,
articulation 5, and `ksmps=32`.

Of the 43 registered tests, 41 passed, including the native comparison
between the canonical and browser-prepared source. Both browser renders
stopped at the workbench check for the pinned Csound entry. The separate
profile data and generator checks passed. Audibility against matched
acoustic recordings and browser performance remain open.
