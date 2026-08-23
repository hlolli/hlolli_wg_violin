<CsoundSynthesizer>
<CsOptions>
-n -d -m128
</CsOptions>
<CsInstruments>

#ifndef BENCH_CASE
#define BENCH_CASE #1#
#endif
#ifndef BENCH_SECONDS
#define BENCH_SECONDS #10#
#endif

sr = 48000
ksmps = 32
nchnls = 2
0dbfs = 1

giPlayer1 hlolli_wg_violin_create
giPlayer2 hlolli_wg_violin_create
giPlayer3 hlolli_wg_violin_create
giPlayer4 hlolli_wg_violin_create
giPlayer5 hlolli_wg_violin_create
giPlayer6 hlolli_wg_violin_create
giPlayer7 hlolli_wg_violin_create
giPlayer8 hlolli_wg_violin_create

instr Bow
  iHandle = p4
  iString = p5
  iFrequency = p6
  iIndex = p7
  kPhase phasor 0.29 + 0.011 * iIndex, 0.09 * iIndex
  kTriangle = 1 - abs(2 * kPhase - 1)
  kForce = 0.30 + 0.29 * kTriangle
  kSpeed = (0.35 + 0.22 * (1 - kTriangle)) * \
      (kPhase < 0.5 ? 1 : -1)
  aLeft, aRight hlolli_wg_violin \
      1, iFrequency, kForce, kSpeed, 0.12, \
      10, 5.1, 0, 0, 0, iString, iHandle
  outs aLeft, aRight
endin

instr Body
  aLeft, aRight hlolli_wg_violin_resonance \
      p4, 0.72, p5, 0.08
  outs aLeft, aRight
endin

instr Silent
  aSilence init 0
  outs aSilence, aSilence
endin

instr Schedule
  event_i "i", "Silent", 0, $BENCH_SECONDS
  if $BENCH_CASE == 1 then
    event_i "i", "Bow", 0, $BENCH_SECONDS, \
        giPlayer1, 2, 369.994423, 1
    event_i "i", "Body", 0, $BENCH_SECONDS, giPlayer1, 0
  elseif $BENCH_CASE == 2 then
    event_i "i", "Bow", 0, $BENCH_SECONDS, \
        giPlayer1, 2, 293.664768, 1
    event_i "i", "Body", 0, $BENCH_SECONDS, giPlayer1, 1
  elseif $BENCH_CASE == 3 then
    event_i "i", "Bow", 0, $BENCH_SECONDS, \
        giPlayer1, 2, 369.994423, 1
    event_i "i", "Bow", 0, $BENCH_SECONDS, \
        giPlayer1, 3, 554.365262, 2
    event_i "i", "Body", 0, $BENCH_SECONDS, giPlayer1, 0.5
  elseif $BENCH_CASE == 4 then
    event_i "i", "Bow", 0, $BENCH_SECONDS, giPlayer1, 1, 196, 1
    event_i "i", "Bow", 0, $BENCH_SECONDS, giPlayer2, 2, 293.664768, 2
    event_i "i", "Bow", 0, $BENCH_SECONDS, giPlayer3, 3, 440, 3
    event_i "i", "Bow", 0, $BENCH_SECONDS, giPlayer4, 4, 659.255114, 4
    event_i "i", "Bow", 0, $BENCH_SECONDS, giPlayer5, 1, 246.941651, 5
    event_i "i", "Bow", 0, $BENCH_SECONDS, giPlayer6, 2, 369.994423, 6
    event_i "i", "Bow", 0, $BENCH_SECONDS, giPlayer7, 3, 554.365262, 7
    event_i "i", "Bow", 0, $BENCH_SECONDS, giPlayer8, 4, 830.609395, 8
    event_i "i", "Body", 0, $BENCH_SECONDS, giPlayer1, 0.35
    event_i "i", "Body", 0, $BENCH_SECONDS, giPlayer2, 0.35
    event_i "i", "Body", 0, $BENCH_SECONDS, giPlayer3, 0.35
    event_i "i", "Body", 0, $BENCH_SECONDS, giPlayer4, 0.35
    event_i "i", "Body", 0, $BENCH_SECONDS, giPlayer5, 0.35
    event_i "i", "Body", 0, $BENCH_SECONDS, giPlayer6, 0.35
    event_i "i", "Body", 0, $BENCH_SECONDS, giPlayer7, 0.35
    event_i "i", "Body", 0, $BENCH_SECONDS, giPlayer8, 0.35
  endif
endin

</CsInstruments>
<CsScore>
i "Schedule" 0 0.001
e
</CsScore>
</CsoundSynthesizer>
