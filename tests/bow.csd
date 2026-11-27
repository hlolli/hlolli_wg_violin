<CsoundSynthesizer>
<CsOptions>
-n -d -m128
</CsOptions>
<CsInstruments>

#ifndef TEST_CASE
#define TEST_CASE #2#
#endif
#ifndef TEST_VARIANT
#define TEST_VARIANT #0#
#endif

#ifndef TEST_BOW_POSITION
#define TEST_BOW_POSITION #-1#
#endif

#ifndef TEST_BOW_FORCE
#define TEST_BOW_FORCE #-1#
#endif

#ifndef TEST_SPLIT
#define TEST_SPLIT #0#
#endif
#ifndef TEST_SPLIT_TIME
#define TEST_SPLIT_TIME #0.25#
#endif
#ifndef TEST_END
#define TEST_END #0.62#
#endif

sr = 48000
ksmps = 32
nchnls = 2
0dbfs = 1

giViolin hlolli_wg_violin_create

instr Voice
  kFrequency init p6
  kTrigger init p7
  kForce init p8
  kSpeed init p9
  kPosition init p10

  aLeft, aRight hlolli_wg_violin \
      kTrigger, kFrequency, kForce, kSpeed, kPosition, \
      0, 0, 0, 0, 0, p5, p4
  outs aLeft, aRight
endin

instr Attack
  iRamp = p11
  kFrequency init p6
  kTrigger init p7
  kForce linseg 0, iRamp, p8, p3 - iRamp, p8
  kSpeed linseg 0, iRamp, p9, p3 - iRamp, p9
  kPosition init p10

  aLeft, aRight hlolli_wg_violin \
      kTrigger, kFrequency, kForce, kSpeed, kPosition, \
      0, 0, 0, 0, 0, p5, p4
  outs aLeft, aRight
endin

instr Reverse
  iPolarity = 1
  if $TEST_VARIANT == 1 then
    iPolarity = -1
  endif
  kFrequency init p6
  kTrigger init 1
  kForce linseg 0, 0.01, 0.45, p3 - 0.01, 0.45
  kSpeed linseg 0, 0.02, iPolarity * 0.55, 0.23, \
      iPolarity * 0.55, 0.01, -iPolarity * 0.55, \
      p3 - 0.26, -iPolarity * 0.55
  kPosition init 0.12

  aLeft, aRight hlolli_wg_violin \
      kTrigger, kFrequency, kForce, kSpeed, kPosition, \
      0, 0, 0, 0, 0, p5, p4
  outs aLeft, aRight
endin

instr Release
  kTrigger init 1
  if timeinsts() >= 0.25 then
    kTrigger = 0
  endif
  kFrequency init 440
  kForce init 0.45
  kSpeed init 0.55
  kPosition init 0.12

  aLeft, aRight hlolli_wg_violin \
      kTrigger, kFrequency, kForce, kSpeed, kPosition, \
      0, 0, 0, 0, 0, p5, p4
  outs aLeft, aRight
endin

instr Stress
  iIndex = p5
  kPitchPhase phasor 0.071 + 0.009 * iIndex, p7
  kPitchTriangle = 1 - abs(2 * kPitchPhase - 1)
  kFrequency = p6 * exp(0.5 * log(2) * kPitchTriangle)
  kForce = 0.3 + 0.2 * \
      sin(6.283185307179586 * (0.31 + 0.017 * iIndex) * timeinsts())
  kSpeed = 0.5 * \
      sin(6.283185307179586 * (0.43 + 0.019 * iIndex) * timeinsts())
  kPosition = 0.12 + 0.08 * \
      sin(6.283185307179586 * (0.19 + 0.013 * iIndex) * timeinsts())
  kGatePhase phasor 1 + 0.07 * iIndex, 0
  kTrigger = 1
  if kGatePhase >= 0.75 then
    kTrigger = 0
  endif

  aLeft, aRight hlolli_wg_violin \
      kTrigger, kFrequency, kForce, kSpeed, kPosition, \
      0, 0, 0, 0, 0, p5, p4
  outs aLeft, aRight
endin

instr BowProbe
  iState, iRequestedForce, iEffectiveForce, iBowSpeed, iContact, \
      iTargetPosition, iEffectivePosition, iBridgeDelay, iNutDelay, \
      iImpedance, iFreeVelocity, iStringVelocity, iRelativeVelocity, \
      iFrictionForce, iJunctionIncrement, iMinForce, iMaxForce, \
      iResidual, iBracketWidth, iRootCount, iIterationsLast, \
      iIterationsMax, iSolverCalls, iSolverFailures, iSolverFallbacks, \
      iStickSamples, iSlipSamples, iScratchSamples, iNoMotionSamples, \
      iStateTransitions, iDirectionChanges, iAttacks, iRecoveries, \
      iScratchScore, iMaxAbsRelative, iFinite \
      hlolli_wg_violin_test_bow p4, p5
  printf_i \
      "WG_BOW_A %d %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g\n", \
      1, p6, iState, iRequestedForce, iEffectiveForce, iBowSpeed, \
      iContact, iTargetPosition, iEffectivePosition, iBridgeDelay, \
      iNutDelay, iImpedance, iFreeVelocity, iStringVelocity, \
      iRelativeVelocity, iFrictionForce, iJunctionIncrement, iMinForce, \
      iMaxForce, iResidual
  printf_i \
      "WG_BOW_B %d %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g\n", \
      1, p6, iBracketWidth, iRootCount, iIterationsLast, \
      iIterationsMax, iSolverCalls, iSolverFailures, iSolverFallbacks, \
      iStickSamples, iSlipSamples, iScratchSamples, iNoMotionSamples, \
      iStateTransitions, iDirectionChanges, iAttacks, iRecoveries, \
      iScratchScore, iMaxAbsRelative, iFinite
endin

instr WaveProbe
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

instr Fault
  iOk hlolli_wg_violin_test_bow_fault p4, p5, p6
  printf_i "WG_FAULT %d %.17g\n", 1, p7, iOk
endin

instr KeepAlive
  aSilence init 0
  outs aSilence, aSilence
endin

instr ScheduleTest
  event_i "i", "KeepAlive", 0, $TEST_END

  if $TEST_CASE == 1 then
    iTrigger = 0
    iForce = 0.5
    iSpeed = 0.5
    if $TEST_VARIANT == 1 then
      iTrigger = 1
      iForce = 0
    elseif $TEST_VARIANT == 2 then
      iTrigger = 1
      iSpeed = 0
    endif
    event_i "i", "Voice", 0, 0.08, \
        giViolin, 1, 440, iTrigger, iForce, iSpeed, 0.12
    event_i "i", "BowProbe", 0.081, 0.001, giViolin, 1, 1
    event_i "i", "WaveProbe", 0.081, 0.001, giViolin, 1, 1
  elseif $TEST_CASE == 2 then
    event_i "i", "Attack", 0, 0.6, \
        giViolin, 1, 440, 1, 0.45, 0.55, 0.12, 0.0227272727273
    event_i "i", "BowProbe", 0.025, 0.001, giViolin, 1, 1
    event_i "i", "BowProbe", 0.05, 0.001, giViolin, 1, 2
    event_i "i", "BowProbe", 0.3, 0.001, giViolin, 1, 3
    event_i "i", "BowProbe", 0.601, 0.001, giViolin, 1, 4
    event_i "i", "WaveProbe", 0.601, 0.001, giViolin, 1, 1
  elseif $TEST_CASE == 3 then
    event_i "i", "Reverse", 0, 0.6, giViolin, 1, 440
    event_i "i", "BowProbe", 0.2, 0.001, giViolin, 1, 1
    event_i "i", "BowProbe", 0.35, 0.001, giViolin, 1, 2
    event_i "i", "BowProbe", 0.601, 0.001, giViolin, 1, 3
    event_i "i", "WaveProbe", 0.601, 0.001, giViolin, 1, 1
  elseif $TEST_CASE == 4 then
    iForce = 0.02
    iSpeed = 0.95
    iPosition = 0.4
    if $TEST_VARIANT == 1 then
      iForce = 1
      iSpeed = 0.05
      iPosition = 0.01
    elseif $TEST_VARIANT == 2 then
      iForce = 1
      iSpeed = 1
      iPosition = 0.01
    endif
    event_i "i", "Attack", 0, 0.4, \
        giViolin, 1, 440, 1, iForce, iSpeed, iPosition, 0.0227272727273
    event_i "i", "BowProbe", 0.39, 0.001, giViolin, 1, 1
    event_i "i", "WaveProbe", 0.39, 0.001, giViolin, 1, 1
  elseif $TEST_CASE == 5 then
    ; Match about 1.65 N across positions despite the position-aware map.
    iPosition = 0.05
    iForce = 0.16412267812412107
    if $TEST_VARIANT == 1 then
      iPosition = 0.125
      iForce = 0.6598560434350398
    elseif $TEST_VARIANT == 2 then
      iPosition = 0.25
      iForce = 0.8626210424620069
    endif
    if $TEST_BOW_POSITION >= 0 then
      iPosition = $TEST_BOW_POSITION
    endif
    if $TEST_BOW_FORCE >= 0 then
      iForce = $TEST_BOW_FORCE
    endif
    event_i "i", "Attack", 0, 0.5, \
        giViolin, 1, 440, 1, iForce, 0.55, iPosition, 0.0227272727273
    event_i "i", "BowProbe", 0.49, 0.001, giViolin, 1, 1
    event_i "i", "WaveProbe", 0.49, 0.001, giViolin, 1, 1
  elseif $TEST_CASE == 6 then
    event_i "i", "Attack", 0, 0.6, \
        giViolin, 1, 440, 1, 0.45, 0.55, 0.12, 0.0227272727273
    event_i "i", "BowProbe", 0.2, 0.001, giViolin, 1, 1
    event_i "i", "Fault", 0.25, 0.001, giViolin, 1, 3, 1
    event_i "i", "BowProbe", 0.251, 0.001, giViolin, 1, 2
    event_i "i", "BowProbe", 0.35, 0.001, giViolin, 1, 3
    event_i "i", "BowProbe", 0.601, 0.001, giViolin, 1, 4
    event_i "i", "WaveProbe", 0.601, 0.001, giViolin, 1, 1
  elseif $TEST_CASE == 7 then
    if $TEST_SPLIT == 0 then
      event_i "i", "Voice", 0, 0.5, \
          giViolin, 1, 440, 1, 0.45, 0.55, 0.12
    else
      event_i "i", "Voice", 0, $TEST_SPLIT_TIME, \
          giViolin, 1, 440, 1, 0.45, 0.55, 0.12
      event_i "i", "Voice", $TEST_SPLIT_TIME, \
          0.5 - $TEST_SPLIT_TIME, \
          giViolin, 1, 440, 1, 0.45, 0.55, 0.12
    endif
    event_i "i", "BowProbe", 0.49, 0.001, giViolin, 1, 1
    event_i "i", "WaveProbe", 0.49, 0.001, giViolin, 1, 1
  elseif $TEST_CASE == 8 then
    event_i "i", "Stress", 0, 10, giViolin, 1, 195.997717990875, 0
    event_i "i", "Stress", 0, 10, giViolin, 2, 293.664767917408, 0.25
    event_i "i", "Stress", 0, 10, giViolin, 3, 440, 0.5
    event_i "i", "Stress", 0, 10, giViolin, 4, 659.25511382574, 0.75
    event_i "i", "BowProbe", 10.001, 0.001, giViolin, 1, 1
    event_i "i", "BowProbe", 10.001, 0.001, giViolin, 2, 2
    event_i "i", "BowProbe", 10.001, 0.001, giViolin, 3, 3
    event_i "i", "BowProbe", 10.001, 0.001, giViolin, 4, 4
    event_i "i", "WaveProbe", 10.001, 0.001, giViolin, 1, 1
    event_i "i", "WaveProbe", 10.001, 0.001, giViolin, 2, 2
    event_i "i", "WaveProbe", 10.001, 0.001, giViolin, 3, 3
    event_i "i", "WaveProbe", 10.001, 0.001, giViolin, 4, 4
  elseif $TEST_CASE == 9 then
    event_i "i", "Attack", 0, 0.6, \
        giViolin, 4, 5000, 1, 0.45, 0.5, 0.01, 0.01
    event_i "i", "BowProbe", 0.3, 0.001, giViolin, 4, 1
    event_i "i", "BowProbe", 0.59, 0.001, giViolin, 4, 2
    event_i "i", "WaveProbe", 0.59, 0.001, giViolin, 4, 1
  elseif $TEST_CASE == 10 then
    event_i "i", "Release", 0, 0.45, giViolin, 1
    event_i "i", "BowProbe", 0.24, 0.001, giViolin, 1, 1
    event_i "i", "BowProbe", 0.251, 0.001, giViolin, 1, 2
    event_i "i", "BowProbe", 0.255, 0.001, giViolin, 1, 3
    event_i "i", "BowProbe", 0.40, 0.001, giViolin, 1, 4
    event_i "i", "WaveProbe", 0.44, 0.001, giViolin, 1, 1
  elseif $TEST_CASE == 11 then
    event_i "i", "Voice", 0, 0.24, \
        giViolin, 4, 659.25511382574, 1, 0.55, 0.61, 0.11
  endif
endin

</CsInstruments>
<CsScore>
i "ScheduleTest" 0 0.001
e
</CsScore>
</CsoundSynthesizer>
