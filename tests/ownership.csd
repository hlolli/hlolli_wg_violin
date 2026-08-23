<CsoundSynthesizer>
<CsOptions>
-n -d -m128
</CsOptions>
<CsInstruments>

#ifndef TEST_CASE
#define TEST_CASE #0#
#endif

sr = 48000
ksmps = 32
nchnls = 2
0dbfs = 1

giViolinA hlolli_wg_violin_create
giViolinB hlolli_wg_violin_create

instr Voice
  iHandle = p4
  iString = p5
  kFrequency init p6
  kTrigger init p7
  kForce init p8
  kSpeed init p9

  aLeft, aRight hlolli_wg_violin \
      kTrigger, kFrequency, kForce, kSpeed, 0.12, \
      13, 5.25, 0, 0, 0, iString, iHandle
  outs aLeft, aRight
endin

instr Renderer
  aLeft, aRight hlolli_wg_violin_resonance \
      p4, p5, p6, p7
  outs aLeft, aRight
endin

instr UnknownProfile
  iHandle hlolli_wg_violin_create "missing_violin"
endin

instr LocalCreate
  setksmps 16
  iHandle hlolli_wg_violin_create
endin

instr LocalVoice
  setksmps 16
  kFrequency init 330
  aLeft, aRight hlolli_wg_violin \
      0.5, kFrequency, 0.4, 0.3, 0.12, \
      13, 5.25, 0, 0, 0, 1, giViolinA
  outs aLeft, aRight
endin

instr LocalRenderer
  setksmps 16
  aLeft, aRight hlolli_wg_violin_resonance \
      giViolinA, 0.7, 0.5, 0
  outs aLeft, aRight
endin

instr ProbeCreators
  printf_i "WG_CREATOR %.17g %.17g\n", \
      1, giViolinA, giViolinB
endin

instr ProbeString
  iPhase, iVibratoPhase, iFrequency, iTrigger, iForce, iSpeed, \
      iActivity, iLastSample, iGapSamples, iOwner, iSuccessor \
      hlolli_wg_violin_test_string p4, p5
  printf_i \
      "WG_STRING %d %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g\n", \
      1, p6, iPhase, iVibratoPhase, iFrequency, iTrigger, \
      iForce, iSpeed, iActivity, iLastSample, iGapSamples, \
      iOwner, iSuccessor
endin

instr ScheduleTest
  if $TEST_CASE == 0 then
    event_i "i", "ProbeCreators", 0, 0.001
  elseif $TEST_CASE == 1 then
    event_i "i", "UnknownProfile", 0, 0.001
  elseif $TEST_CASE == 2 then
    event_i "i", "Voice", 0, 0.02, 0, 1, 330, 0.5, 0.4, 0.3
  elseif $TEST_CASE == 3 then
    event_i "i", "Voice", 0, 0.02, 1.5, 1, 330, 0.5, 0.4, 0.3
  elseif $TEST_CASE == 4 then
    event_i "i", "Voice", 0, 0.02, 999, 1, 330, 0.5, 0.4, 0.3
  elseif $TEST_CASE == 5 then
    event_i "i", "Renderer", 0, 0.02, 0, 0.7, 0.5, 0
  elseif $TEST_CASE == 6 then
    event_i "i", "Renderer", 0, 0.02, 1.5, 0.7, 0.5, 0
  elseif $TEST_CASE == 7 then
    event_i "i", "Renderer", 0, 0.02, 999, 0.7, 0.5, 0
  elseif $TEST_CASE == 8 then
    event_i "i", "LocalCreate", 0, 0.02
  elseif $TEST_CASE == 9 then
    event_i "i", "LocalVoice", 0, 0.02
  elseif $TEST_CASE == 10 then
    event_i "i", "LocalRenderer", 0, 0.02
  elseif $TEST_CASE == 11 then
    event_i "i", "Renderer", 0, 0.04, giViolinA, 0.7, 0.5, 0
    event_i "i", "Renderer", 0, 0.04, giViolinA, 0.7, 0.5, 0
  elseif $TEST_CASE == 12 then
    event_i "i", "Voice", 0, 0.04, giViolinA, 1, 330, 0.5, 0.4, 0.3
    event_i "i", "Voice", 0, 0.04, giViolinA, 1, 440, 0.6, 0.5, 0.4
  elseif $TEST_CASE == 13 then
    event_i "i", "Voice", 0, 0.04, giViolinA, 1, 196, 0.4, 0.3, -0.2
    event_i "i", "Voice", 0, 0.04, giViolinA, 2, 294, 0.5, 0.4, -0.1
    event_i "i", "Voice", 0, 0.04, giViolinA, 3, 440, 0.6, 0.5, 0.1
    event_i "i", "Voice", 0, 0.04, giViolinA, 4, 659, 0.7, 0.6, 0.2
  elseif $TEST_CASE == 14 then
    event_i "i", "Voice", 0, 0.04, giViolinA, 1, 196, 0.4, 0.3, -0.2
    event_i "i", "Voice", 0, 0.04, giViolinA, 2, 294, 0.5, 0.4, -0.1
    event_i "i", "Voice", 0, 0.04, giViolinA, 3, 440, 0.6, 0.5, 0.1
    event_i "i", "Voice", 0, 0.04, giViolinA, 4, 659, 0.7, 0.6, 0.2
    event_i "i", "Voice", 0, 0.04, giViolinA, 0, 523, 0.5, 0.4, 0.3
  elseif $TEST_CASE == 15 then
    event_i "i", "Voice", 0, 0.016, giViolinA, 1, 311, 0.35, 0.2, -0.25
    event_i "i", "Voice", 0, 0.024, giViolinB, 1, 509, 0.8, 0.9, 0.75
    event_i "i", "ProbeString", 0.034, 0.001, giViolinA, 1, 1
    event_i "i", "ProbeString", 0.034, 0.001, giViolinB, 1, 2
  endif
endin

</CsInstruments>
<CsScore>
i "ScheduleTest" 0 0.001
e 0.08
</CsScore>
</CsoundSynthesizer>
