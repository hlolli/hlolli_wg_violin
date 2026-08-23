<CsoundSynthesizer>
<CsOptions>
-n -d -m128
</CsOptions>
<CsInstruments>

#ifndef TEST_SR
#define TEST_SR #48000#
#endif
#ifndef TEST_KSMPS
#define TEST_KSMPS #32#
#endif
#ifndef TEST_SECONDS
#define TEST_SECONDS #2#
#endif
#ifndef TEST_CASE
#define TEST_CASE #1#
#endif

sr = $TEST_SR
ksmps = $TEST_KSMPS
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

instr Voice
  iHandle = p4
  iString = int(p5)
  iFrequency = p6
  iMotion = p7
  if $TEST_CASE == 2 then
    kRapidPhase phasor 83, 0.13 * iMotion
    kRapidStep = int(kRapidPhase * 8)
    if kRapidStep == 0 then
      kFrequency = 0.985 * iFrequency
      kForce = 0.24
      kSpeed = 0.62
      kPosition = 0.08
    elseif kRapidStep == 1 then
      kFrequency = 1.012 * iFrequency
      kForce = 0.68
      kSpeed = -0.58
      kPosition = 0.19
    elseif kRapidStep == 2 then
      kFrequency = 0.972 * iFrequency
      kForce = 0.36
      kSpeed = 0.41
      kPosition = 0.12
    elseif kRapidStep == 3 then
      kFrequency = 1.026 * iFrequency
      kForce = 0.57
      kSpeed = -0.33
      kPosition = 0.23
    elseif kRapidStep == 4 then
      kFrequency = 0.994 * iFrequency
      kForce = 0.29
      kSpeed = -0.64
      kPosition = 0.10
    elseif kRapidStep == 5 then
      kFrequency = 1.018 * iFrequency
      kForce = 0.63
      kSpeed = 0.55
      kPosition = 0.17
    elseif kRapidStep == 6 then
      kFrequency = 0.978 * iFrequency
      kForce = 0.42
      kSpeed = -0.46
      kPosition = 0.14
    else
      kFrequency = 1.031 * iFrequency
      kForce = 0.52
      kSpeed = 0.37
      kPosition = 0.21
    endif
  else
    kPhase phasor 0.37 + 0.071 * iMotion, 0.13 * iMotion
    kTriangle = 1 - abs(2 * kPhase - 1)
    kFrequency = iFrequency * exp(log(2) * 0.08 * (kTriangle - 0.5))
    kForce = 0.31 + 0.28 * kTriangle
    kSpeed = (0.33 + 0.25 * (1 - kTriangle)) * \
        (kPhase < 0.5 ? 1 : -1)
    kPosition = 0.09 + 0.08 * kTriangle
  endif
  aLeft, aRight hlolli_wg_violin \
      1, kFrequency, kForce, kSpeed, kPosition, \
      12, 5.1, 0, 0, 0, iString, iHandle
  outs 0.34 * aLeft, 0.34 * aRight
endin

instr Body
  iHandle = p4
  kSympathetic init p5
  aLeft, aRight hlolli_wg_violin_resonance \
      iHandle, 0.72, kSympathetic, 0.08
  outs 0.55 * aLeft, 0.55 * aRight
endin

instr Schedule
  if $TEST_CASE == 1 then
    event_i "i", "Voice", 0, $TEST_SECONDS, giPlayer1, 2, 293.664768, 1
    event_i "i", "Body", 0, $TEST_SECONDS, giPlayer1, 0.45
  elseif $TEST_CASE == 2 then
    event_i "i", "Voice", 0, $TEST_SECONDS, giPlayer1, 3, 440, 7
    event_i "i", "Body", 0, $TEST_SECONDS, giPlayer1, 0.5
  elseif $TEST_CASE == 3 then
    event_i "i", "Voice", 0, $TEST_SECONDS, giPlayer1, 1, 196, 1
    event_i "i", "Voice", 0, $TEST_SECONDS, giPlayer1, 2, 293.664768, 2
    event_i "i", "Voice", 0, $TEST_SECONDS, giPlayer1, 3, 440, 3
    event_i "i", "Voice", 0, $TEST_SECONDS, giPlayer1, 4, 659.255114, 4
    event_i "i", "Body", 0, $TEST_SECONDS, giPlayer1, 0.5
  else
    event_i "i", "Voice", 0, $TEST_SECONDS, giPlayer1, 1, 196, 1
    event_i "i", "Voice", 0, $TEST_SECONDS, giPlayer2, 2, 293.664768, 2
    event_i "i", "Voice", 0, $TEST_SECONDS, giPlayer3, 3, 440, 3
    event_i "i", "Voice", 0, $TEST_SECONDS, giPlayer4, 4, 659.255114, 4
    event_i "i", "Voice", 0, $TEST_SECONDS, giPlayer5, 1, 246.941651, 5
    event_i "i", "Voice", 0, $TEST_SECONDS, giPlayer6, 2, 369.994423, 6
    event_i "i", "Voice", 0, $TEST_SECONDS, giPlayer7, 3, 554.365262, 7
    event_i "i", "Voice", 0, $TEST_SECONDS, giPlayer8, 4, 830.609395, 8
    event_i "i", "Body", 0, $TEST_SECONDS, giPlayer1, 0.35
    event_i "i", "Body", 0, $TEST_SECONDS, giPlayer2, 0.35
    event_i "i", "Body", 0, $TEST_SECONDS, giPlayer3, 0.35
    event_i "i", "Body", 0, $TEST_SECONDS, giPlayer4, 0.35
    event_i "i", "Body", 0, $TEST_SECONDS, giPlayer5, 0.35
    event_i "i", "Body", 0, $TEST_SECONDS, giPlayer6, 0.35
    event_i "i", "Body", 0, $TEST_SECONDS, giPlayer7, 0.35
    event_i "i", "Body", 0, $TEST_SECONDS, giPlayer8, 0.35
  endif
endin

</CsInstruments>
<CsScore>
i "Schedule" 0 0.001
e
</CsScore>
</CsoundSynthesizer>
