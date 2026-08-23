<CsoundSynthesizer>
<CsOptions>
-n -d -m128
</CsOptions>
<CsInstruments>

#ifndef BENCH_CASE
#define BENCH_CASE #1#
#endif
#ifndef BENCH_SECONDS
#define BENCH_SECONDS #20#
#endif

sr = 48000
ksmps = 32
nchnls = 2
0dbfs = 1

giViolin hlolli_wg_violin_create

instr Bow
  iIndex = p5
  kPhase phasor 0.29 + 0.013 * iIndex, 0.11 * iIndex
  kTriangle = 1 - abs(2 * kPhase - 1)
  kForce = 0.28 + 0.34 * kTriangle
  kSpeed = (0.34 + 0.28 * (1 - kTriangle)) * \
      (kPhase < 0.5 ? 1 : -1)
  kPosition = 0.08 + 0.08 * kTriangle
  kFrequency = p6 * exp(0.18 * log(2) * kTriangle)
  aLeft, aRight hlolli_wg_violin \
      1, kFrequency, kForce, kSpeed, kPosition, \
      12, 5.1, 0, 0, p7, p5, p4
  outs aLeft, aRight
endin

instr Renderer
  aLeft, aRight hlolli_wg_violin_resonance \
      p4, 0.72, p5, 0.12
  outs aLeft, aRight
endin

instr Silent
  aSilence init 0
  outs aSilence, aSilence
endin

instr ScheduleBenchmark
  event_i "i", "Silent", 0, $BENCH_SECONDS
  if $BENCH_CASE == 1 then
    ; One neutral bowed string and wet body, with sympathetic drive off.
    event_i "i", "Bow", 0, $BENCH_SECONDS, \
        giViolin, 1, 293.664767917408, 0
    event_i "i", "Renderer", 0, $BENCH_SECONDS, giViolin, 0
  elseif $BENCH_CASE == 2 then
    ; The same source drives the three unowned open strings.
    event_i "i", "Bow", 0, $BENCH_SECONDS, \
        giViolin, 1, 293.664767917408, 0
    event_i "i", "Renderer", 0, $BENCH_SECONDS, giViolin, 1
  elseif $BENCH_CASE == 3 then
    ; Four neutral, owned strings plus the wet body.
    event_i "i", "Bow", 0, $BENCH_SECONDS, \
        giViolin, 1, 246.941650628062, 0
    event_i "i", "Bow", 0, $BENCH_SECONDS, \
        giViolin, 2, 369.994422711634, 0
    event_i "i", "Bow", 0, $BENCH_SECONDS, \
        giViolin, 3, 554.365261953744, 0
    event_i "i", "Bow", 0, $BENCH_SECONDS, \
        giViolin, 4, 830.609395159890, 0
    event_i "i", "Renderer", 0, $BENCH_SECONDS, giViolin, 1
  elseif $BENCH_CASE == 4 || $BENCH_CASE == 5 then
    ; Full four-string kStrange limits with sympathetic drive enabled.
    iStrange = $BENCH_CASE == 4 ? -1 : 1
    event_i "i", "Bow", 0, $BENCH_SECONDS, \
        giViolin, 1, 246.941650628062, iStrange
    event_i "i", "Bow", 0, $BENCH_SECONDS, \
        giViolin, 2, 369.994422711634, iStrange
    event_i "i", "Bow", 0, $BENCH_SECONDS, \
        giViolin, 3, 554.365261953744, iStrange
    event_i "i", "Bow", 0, $BENCH_SECONDS, \
        giViolin, 4, 830.609395159890, iStrange
    event_i "i", "Renderer", 0, $BENCH_SECONDS, giViolin, 1
  endif
endin

</CsInstruments>
<CsScore>
i "ScheduleBenchmark" 0 0.001
e
</CsScore>
</CsoundSynthesizer>
