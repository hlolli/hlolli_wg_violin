<CsoundSynthesizer>
<CsOptions>
-n -d -m128
</CsOptions>
<CsInstruments>

#ifndef TEST_CASE
#define TEST_CASE #1#
#endif
#ifndef TEST_FREQUENCY
#define TEST_FREQUENCY #440#
#endif
#ifndef TEST_DURATION
#define TEST_DURATION #0.08#
#endif
#ifndef TEST_STRING
#define TEST_STRING #1#
#endif
#ifndef TEST_END
#define TEST_END #0.09#
#endif
#ifndef TEST_SPLIT
#define TEST_SPLIT #0#
#endif
#ifndef TEST_SPLIT_TIME
#define TEST_SPLIT_TIME #0.016#
#endif
#ifndef TEST_GAP
#define TEST_GAP #0#
#endif
#ifndef TEST_BRIDGE_SCALE
#define TEST_BRIDGE_SCALE #1#
#endif
#ifndef TEST_POSITION
#define TEST_POSITION #0.12#
#endif
sr = 48000
ksmps = 32
nchnls = 2
0dbfs = 1

giViolin hlolli_wg_violin_create

instr Voice
  kFrequency init p6
  kTrigger init p7

  aLeft, aRight hlolli_wg_violin \
      kTrigger, kFrequency, 0.6, 0.5, 0.12, \
      0, 0, 0, 0, 0, p5, p4
  outs aLeft, aRight
endin

instr Sweep
  iMinimum = p6
  iMaximum = p7
  kPhase phasor p8, p9
  kTriangle = 1 - abs(2 * kPhase - 1)
  kFrequency = iMinimum * exp(log(iMaximum / iMinimum) * kTriangle)
  kTrigger init 0

  aLeft, aRight hlolli_wg_violin \
      kTrigger, kFrequency, 0.6, 0.5, 0.12, \
      0, 0, 0, 0, 0, p5, p4
  outs aLeft, aRight
endin

instr SetLoss
  iOk hlolli_wg_violin_test_diagnostic_gains \
      p4, p5, 0, 0, 0, 0, 1, p6
endin

instr PassiveVoice
  kTrigger init 1
  aLeft, aRight hlolli_wg_violin \
      kTrigger, p6, 0, 0, $TEST_POSITION, \
      0, 0, 0, 0, 0, p5, p4
  outs aLeft, aRight
endin

instr Probe
  iCapacity, iReadDelay, iTargetDelay, iTargetFrequency, iLoopPhase, \
      iTowardNutEnergy, iTowardBridgeEnergy, iTowardNutSignature, \
      iTowardBridgeSignature, iNutPole, iNutGain, iNutState, \
      iBridgePole, iBridgeGain, iBridgeState, iWriteIndex, \
      iWaveSamples, iExcitationCount, iClearCount, iResetCount, \
      iClipCount, iBridgeDynamicInput, iBridgeDynamicOutput, \
      iLastBridgeOutput, iFinite \
      hlolli_wg_violin_test_waveguide p4, p5
  printf_i \
      "WG_WAVE %d %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g\n", \
      1, p6, iCapacity, iReadDelay, iTargetDelay, iTargetFrequency, \
      iLoopPhase, iTowardNutEnergy, iTowardBridgeEnergy, \
      iTowardNutSignature, iTowardBridgeSignature, iNutPole, iNutGain, \
      iNutState, iBridgePole, iBridgeGain, iBridgeState, iWriteIndex, \
      iWaveSamples, iExcitationCount, iClearCount, iResetCount, \
      iClipCount, iBridgeDynamicInput, iBridgeDynamicOutput, \
      iLastBridgeOutput, iFinite
endin

instr Seed
  iOk hlolli_wg_violin_test_string_impulse p4, p5, p6, p7
endin

instr KeepAlive
  aSilence init 0
  outs aSilence, aSilence
endin

instr ScheduleTest
  iBlock = ksmps / sr
  event_i "i", "KeepAlive", 0, $TEST_END

  if $TEST_CASE == 1 then
    event_i "i", "Voice", 0, $TEST_DURATION, \
        giViolin, $TEST_STRING, $TEST_FREQUENCY, 0
    event_i "i", "Seed", 0, 0.001, \
        giViolin, $TEST_STRING, $TEST_FREQUENCY, 0.8
    event_i "i", "Probe", $TEST_DURATION + 0.001, 0.001, \
        giViolin, $TEST_STRING, 1
  elseif $TEST_CASE == 2 then
    ; Retune a seeded passive rail across an exact same-string handoff.
    event_i "i", "Voice", 0, 0.016, \
        giViolin, 1, 220, 0
    event_i "i", "Voice", 0.016, 0.032, \
        giViolin, 1, 880, 0
    event_i "i", "Seed", 0, 0.001, giViolin, 1, 220, 0.8
    event_i "i", "Probe", 0.012, 0.001, giViolin, 1, 1
    event_i "i", "Probe", 0.016 + iBlock, 0.001, giViolin, 1, 2
    event_i "i", "Probe", 0.020, 0.001, giViolin, 1, 3
    event_i "i", "Probe", 0.049, 0.001, giViolin, 1, 4
  elseif $TEST_CASE == 3 then
    ; Seed once and let the passive string decay.
    event_i "i", "Voice", 0, 0.016, \
        giViolin, 1, 440, 0
    event_i "i", "Voice", 0.016, 1.008, \
        giViolin, 1, 440, 0
    event_i "i", "Seed", 0, 0.001, giViolin, 1, 440, 0.8
    event_i "i", "Probe", 0.032, 0.001, giViolin, 1, 1
    event_i "i", "Probe", 0.128, 0.001, giViolin, 1, 2
    event_i "i", "Probe", 0.512, 0.001, giViolin, 1, 3
    event_i "i", "Probe", 1.025, 0.001, giViolin, 1, 4
  elseif $TEST_CASE == 4 then
    event_i "i", "Voice", 0, 0.048, \
        giViolin, 1, 195.997717990875, 0
    event_i "i", "Voice", 0, 0.048, \
        giViolin, 2, 293.664767917408, 0
    event_i "i", "Voice", 0, 0.048, \
        giViolin, 3, 440, 0
    event_i "i", "Voice", 0, 0.048, \
        giViolin, 4, 659.25511382574, 0
    event_i "i", "Seed", 0, 0.001, \
        giViolin, 1, 195.997717990875, 0.4
    event_i "i", "Seed", 0, 0.001, \
        giViolin, 2, 293.664767917408, 0.4
    event_i "i", "Seed", 0, 0.001, giViolin, 3, 440, 0.4
    event_i "i", "Seed", 0, 0.001, \
        giViolin, 4, 659.25511382574, 0.4
    event_i "i", "Probe", 0.049, 0.001, giViolin, 1, 1
    event_i "i", "Probe", 0.049, 0.001, giViolin, 2, 2
    event_i "i", "Probe", 0.049, 0.001, giViolin, 3, 3
    event_i "i", "Probe", 0.049, 0.001, giViolin, 4, 4
  elseif $TEST_CASE == 5 then
    ; All slots advance, but only the second passive rail receives a seed.
    event_i "i", "Voice", 0, 0.016, giViolin, 1, 333, 0
    event_i "i", "Voice", 0, 0.016, giViolin, 2, 333, 0
    event_i "i", "Voice", 0, 0.016, giViolin, 3, 333, 0
    event_i "i", "Voice", 0, 0.016, giViolin, 4, 333, 0
    event_i "i", "Seed", 0, 0.001, giViolin, 2, 333, 0.8
    event_i "i", "Probe", 0.017, 0.001, giViolin, 1, 1
    event_i "i", "Probe", 0.017, 0.001, giViolin, 2, 2
    event_i "i", "Probe", 0.017, 0.001, giViolin, 3, 3
    event_i "i", "Probe", 0.017, 0.001, giViolin, 4, 4
  elseif $TEST_CASE == 6 then
    event_i "i", "Sweep", 0, 30, \
        giViolin, 1, 20, 5000, 0.071, 0
    event_i "i", "Sweep", 0, 30, \
        giViolin, 2, 20, 5000, 0.083, 0.25
    event_i "i", "Sweep", 0, 30, \
        giViolin, 3, 20, 5000, 0.097, 0.5
    event_i "i", "Sweep", 0, 30, \
        giViolin, 4, 20, 5000, 0.113, 0.75
    event_i "i", "Seed", 0, 0.001, giViolin, 1, 20, 0.35
    event_i "i", "Seed", 0, 0.001, giViolin, 2, 20, 0.35
    event_i "i", "Seed", 0, 0.001, giViolin, 3, 20, 0.35
    event_i "i", "Seed", 0, 0.001, giViolin, 4, 20, 0.35
    event_i "i", "Probe", 30.001, 0.001, giViolin, 1, 1
    event_i "i", "Probe", 30.001, 0.001, giViolin, 2, 2
    event_i "i", "Probe", 30.001, 0.001, giViolin, 3, 3
    event_i "i", "Probe", 30.001, 0.001, giViolin, 4, 4
  elseif $TEST_CASE == 7 then
    if $TEST_SPLIT == 0 then
      event_i "i", "Voice", 0, 0.048, \
          giViolin, 1, 333, 0
    else
      event_i "i", "Voice", 0, $TEST_SPLIT_TIME, \
          giViolin, 1, 333, 0
      event_i "i", "Voice", $TEST_SPLIT_TIME, \
          0.048 - $TEST_SPLIT_TIME, \
          giViolin, 1, 333, 0
    endif
    event_i "i", "Seed", 0, 0.001, giViolin, 1, 333, 0.8
    event_i "i", "Probe", 0.049, 0.001, giViolin, 1, 1
  elseif $TEST_CASE == 8 then
    event_i "i", "Voice", 0, 0.016, \
        giViolin, $TEST_STRING, 333, 0
    if $TEST_GAP == 0 then
      event_i "i", "Voice", 0.016, 0.032, \
          giViolin, $TEST_STRING, 333, 0
    else
      event_i "i", "Voice", 0.032, 0.016, \
          giViolin, $TEST_STRING, 333, 0
    endif
    event_i "i", "Seed", 0, 0.001, \
        giViolin, $TEST_STRING, 333, 0.8
    event_i "i", "Probe", 0.049, 0.001, \
        giViolin, $TEST_STRING, 1
  elseif $TEST_CASE == 9 then
    ; Force the bounded long-gap clear path, then process one more block.
    event_i "i", "Voice", 0, 0.016, \
        giViolin, $TEST_STRING, 440, 0
    event_i "i", "Voice", 6.032, 0.016, \
        giViolin, $TEST_STRING, 440, 0
    event_i "i", "Seed", 0, 0.001, \
        giViolin, $TEST_STRING, 440, 0.8
    event_i "i", "Probe", 6.049, 0.001, \
        giViolin, $TEST_STRING, 1
  elseif $TEST_CASE == 10 then
    ; Exercise bounded loss and cursor catch-up below the clear threshold.
    event_i "i", "Voice", 0, 0.016, \
        giViolin, $TEST_STRING, 440, 0
    event_i "i", "Voice", 0.516, 0.016, \
        giViolin, $TEST_STRING, 440, 0
    event_i "i", "Seed", 0, 0.001, \
        giViolin, $TEST_STRING, 440, 0.8
    event_i "i", "Probe", 0.533, 0.001, \
        giViolin, $TEST_STRING, 1
  elseif $TEST_CASE == 11 then
    event_i "i", "SetLoss", 0, 0.001, \
        giViolin, $TEST_STRING, $TEST_BRIDGE_SCALE
    event_i "i", "PassiveVoice", iBlock, $TEST_DURATION, \
        giViolin, $TEST_STRING, $TEST_FREQUENCY
    event_i "i", "Seed", iBlock, 0.001, \
        giViolin, $TEST_STRING, $TEST_FREQUENCY, 0.8
    event_i "i", "Probe", iBlock + $TEST_DURATION + 0.001, 0.001, \
        giViolin, $TEST_STRING, 1
  endif
endin

</CsInstruments>
<CsScore>
i "ScheduleTest" 0 0.001
e
</CsScore>
</CsoundSynthesizer>
