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

giViolin1 hlolli_wg_violin_create
giViolin2 hlolli_wg_violin_create
giViolin3 hlolli_wg_violin_create
giViolin4 hlolli_wg_violin_create

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
      12, 5.1, 0, 0, 0, p5, p4
  outs aLeft, aRight
endin

instr Silent
  aSilence init 0
  outs aSilence, aSilence
endin

instr ScheduleBenchmark
  event_i "i", "Silent", 0, $BENCH_SECONDS
  if $BENCH_CASE == 1 then
    event_i "i", "Bow", 0, $BENCH_SECONDS, \
        giViolin1, 3, 440
  elseif $BENCH_CASE == 2 then
    event_i "i", "Bow", 0, $BENCH_SECONDS, \
        giViolin1, 1, 246.941650628062
    event_i "i", "Bow", 0, $BENCH_SECONDS, \
        giViolin1, 2, 369.994422711634
    event_i "i", "Bow", 0, $BENCH_SECONDS, \
        giViolin1, 3, 554.365261953744
    event_i "i", "Bow", 0, $BENCH_SECONDS, \
        giViolin1, 4, 830.609395159890
  elseif $BENCH_CASE == 3 then
    event_i "i", "Bow", 0, $BENCH_SECONDS, \
        giViolin1, 3, 440
    event_i "i", "Bow", 0, $BENCH_SECONDS, \
        giViolin2, 3, 440
    event_i "i", "Bow", 0, $BENCH_SECONDS, \
        giViolin3, 3, 440
    event_i "i", "Bow", 0, $BENCH_SECONDS, \
        giViolin4, 3, 440
  endif
endin

</CsInstruments>
<CsScore>
i "ScheduleBenchmark" 0 0.001
e
</CsScore>
</CsoundSynthesizer>
