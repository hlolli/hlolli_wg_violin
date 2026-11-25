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
#ifndef TEST_SPLIT
#define TEST_SPLIT #0#
#endif
#ifndef TEST_SPLIT_TIME
#define TEST_SPLIT_TIME #0.016125#
#endif
#ifndef TEST_END
#define TEST_END #0.072#
#endif
#ifndef TEST_KSMPS
#define TEST_KSMPS #32#
#endif

sr = 48000
ksmps = $TEST_KSMPS
nchnls = 2
0dbfs = 1

giViolin hlolli_wg_violin_create

instr Voice
  kFrequency init p6
  if p13 == 1 && timeinstk() >= 25 then
    kFrequency = p14
  endif
  kTrigger init p7
  kForce init p8
  kSpeed init p9
  kDepth init p10
  kRate init p11

  aLeft, aRight hlolli_wg_violin \
      kTrigger, kFrequency, kForce, kSpeed, 0.12, \
      kDepth, kRate, p12, 0, 0, p5, p4
  outs aLeft, aRight
endin

instr KAssignmentVoice
  kTrigger = p7
  kFrequency = p6
  kForce = p8
  kSpeed = p9
  kDepth = p10
  kRate = p11
  kArticulation = p12
  kHarmonic = p13

  aLeft, aRight hlolli_wg_violin \
      kTrigger, kFrequency, kForce, kSpeed, 0.12, \
      kDepth, kRate, kArticulation, kHarmonic, 0, p5, p4
  outs aLeft, aRight
endin

instr Portamento
  kTime timeinsts
  kFrequency = 195.997717990875
  if kTime >= 0.012 then
    kFrequency = 330
  endif
  if kTime >= 0.028 then
    kFrequency = 392
  endif
  if kTime >= 0.044 then
    kFrequency = 195.997717990875
  endif

  aLeft, aRight hlolli_wg_violin \
      1, kFrequency, 0.45, 0.55, 0.12, \
      0, 0, 0, 0, 0, 1, giViolin
  outs aLeft, aRight
endin

instr ReverseGlide
  kBlock timeinstk
  kFrequency = kBlock >= 1200 && kBlock < 1210 ? 660 : 440
  aLeft, aRight hlolli_wg_violin \
      1, kFrequency, 0.46, 0.52, 0.15, 0, 0, 0, 0, 0, 3, giViolin
  outs aLeft, aRight
endin

instr BridgePluck
  aLeft, aRight hlolli_wg_violin \
      1, 195.997717990875, 0.55, 0.60, 0.40, 0, 0, 5, 0, 0, 1, giViolin
  outs aLeft, aRight
endin

instr GateReattack
  iNoteOff = 0.12
  iGap = 32 / sr
  kTime timeinsts
  kTrigger = 1
  if kTime >= iNoteOff && kTime < iNoteOff + iGap then
    kTrigger = 0
  endif

  aLeft, aRight hlolli_wg_violin \
      kTrigger, 440, 0.45, 0.55, 0.12, \
      0, 0, 1, 0, 0, 1, giViolin
  outs aLeft, aRight
endin

instr SmoothFingerShift
  kFrequency linseg 330, 0.05, 330, 0.20, 349.228231, \
      0.15, 349.228231
  aLeft, aRight hlolli_wg_violin \
      1, kFrequency, 0, 0, 0.12, \
      0, 0, 0, 0, 0, 1, giViolin
  outs aLeft, aRight
endin

instr SmoothFingerArrival
  kFrequency linseg 195.997718, 0.05, 195.997718, 0.20, 220, \
      0.15, 220
  aLeft, aRight hlolli_wg_violin \
      1, kFrequency, 0, 0, 0.12, \
      0, 0, 0, 0, 0, 1, giViolin
  outs aLeft, aRight
endin

instr StringProbe
  iPhase, iVibratoPhase, iFrequency, iTrigger, iForce, iSpeed, \
      iActivity, iLastSample, iGapSamples, iOwner, iSuccessor \
      hlolli_wg_violin_test_string p4, p5
  printf_i \
      "WG_STRING %d %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g\n", \
      1, p6, iPhase, iVibratoPhase, iFrequency, iTrigger, iForce, \
      iSpeed, iActivity, iLastSample, iGapSamples, iOwner, iSuccessor
endin

instr FingerProbe
  iOpenFrequency, iTargetPosition, iPosition, iTargetPressure, \
      iPressure, iVelocity, iDelayVelocity, iEffectiveFrequency, \
      iLastNoise, iNoiseEnergy, iNoisePeak, iNoiseState, iArrivals, \
      iReleases, iShifts, iMovementSamples, iNoiseSamples, iFinite \
      hlolli_wg_violin_test_finger p4, p5
  printf_i \
      "WG_FINGER %d %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g\n", \
      1, p6, iOpenFrequency, iTargetPosition, iPosition, \
      iTargetPressure, iPressure, iVelocity, iDelayVelocity, \
      iEffectiveFrequency, iLastNoise, iNoiseEnergy, iNoisePeak, \
      iNoiseState, iArrivals, iReleases, iShifts, iMovementSamples, \
      iNoiseSamples, iFinite
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
      "WG_BOW %d %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g\n", \
      1, p6, iState, iBowSpeed, iContact, iFreeVelocity, \
      iRelativeVelocity, iFrictionForce, iJunctionIncrement, \
      iStateTransitions, iDirectionChanges, iAttacks, iRecoveries, iFinite
endin

instr ProbeOne
  event_i "i", "StringProbe", 0, 0.001, giViolin, p4, p5
  event_i "i", "FingerProbe", 0, 0.001, giViolin, p4, p5
  event_i "i", "WaveProbe", 0, 0.001, giViolin, p4, p5
  event_i "i", "BowProbe", 0, 0.001, giViolin, p4, p5
endin

instr ProbeFour
  event_i "i", "ProbeOne", 0, 0.001, 1, 1
  event_i "i", "ProbeOne", 0, 0.001, 2, 2
  event_i "i", "ProbeOne", 0, 0.001, 3, 3
  event_i "i", "ProbeOne", 0, 0.001, 4, 4
endin

instr KeepAlive
  aZero init 0
  outs aZero, aZero
endin

instr ScheduleTest
  event_i "i", "KeepAlive", 0, $TEST_END

  if $TEST_CASE == 1 then
    event_i "i", "Voice", 0, 0.04, \
        giViolin, 0, $TEST_FREQUENCY, 1, 0.45, 0.55, 0, 0
    event_i "i", "ProbeFour", 0.03, 0.001
  elseif $TEST_CASE == 2 then
    event_i "i", "Voice", 0, 0.04, \
        giViolin, 0, 190, 1, 0.45, 0.55, 0, 0
  elseif $TEST_CASE == 3 then
    event_i "i", "Voice", 0, 0.04, \
        giViolin, 1, 250, 1, 0.45, 0.55, 0, 0
    event_i "i", "Voice", 0, 0.04, \
        giViolin, 0, 250, 1, 0.45, 0.55, 0, 0
  elseif $TEST_CASE == 4 then
    event_i "i", "Voice", 0, 0.016, \
        giViolin, 0, 435, 1, 0.45, 0.55, 0, 0
    event_i "i", "Voice", 0.016, 0.032, \
        giViolin, 0, 445, 1, 0.45, 0.55, 0, 0
    event_i "i", "ProbeFour", 0.04, 0.001
  elseif $TEST_CASE == 5 then
    event_i "i", "Voice", 0, 0.016, \
        giViolin, 0, 700, 1, 0.45, 0.55, 0, 0
    event_i "i", "Voice", 0.016, 0.032, \
        giViolin, 0, 500, 1, 0.45, 0.55, 0, 0
    event_i "i", "ProbeFour", 0.04, 0.001
  elseif $TEST_CASE == 6 then
    event_i "i", "Portamento", 0, 0.064
    event_i "i", "ProbeOne", 0.06, 0.001, 1, 1
  elseif $TEST_CASE == 7 then
    if $TEST_SPLIT == 0 then
      event_i "i", "Voice", 0, 0.056, \
          giViolin, 1, 445, 1, 0.45, 0.55, 35, 6.25
    else
      event_i "i", "Voice", 0, $TEST_SPLIT_TIME, \
          giViolin, 1, 445, 1, 0.45, 0.55, 35, 6.25
      event_i "i", "Voice", $TEST_SPLIT_TIME, \
          0.056 - $TEST_SPLIT_TIME, \
          giViolin, 1, 445, 1, 0.45, 0.55, 35, 6.25
    endif
    event_i "i", "ProbeOne", 0.052, 0.001, 1, 1
  elseif $TEST_CASE == 8 then
    if $TEST_SPLIT == 0 then
      event_i "i", "Voice", 0, 0.056, \
          giViolin, 1, 330, 1, 0.45, 0.55, 0, 0
    else
      event_i "i", "Voice", 0, $TEST_SPLIT_TIME, \
          giViolin, 1, 330, 1, 0.45, 0.55, 0, 0
      event_i "i", "Voice", $TEST_SPLIT_TIME, \
          0.056 - $TEST_SPLIT_TIME, \
          giViolin, 1, 330, 1, 0.45, 0.55, 0, 0
    endif
    event_i "i", "ProbeOne", 0.052, 0.001, 1, 1
  elseif $TEST_CASE == 9 then
    if $TEST_SPLIT == 0 then
      event_i "i", "Voice", 0, 0.056, \
          giViolin, 1, 330, 1, 0.45, 0.55, 0, 0, 0, 1, 440
    else
      event_i "i", "Voice", 0, 0.016, \
          giViolin, 1, 330, 1, 0.45, 0.55, 0, 0
      event_i "i", "Voice", 0.016, 0.04, \
          giViolin, 1, 440, 1, 0.45, 0.55, 0, 0
    endif
    event_i "i", "ProbeOne", 0.052, 0.001, 1, 1
  elseif $TEST_CASE == 10 then
    event_i "i", "Voice", 0, 0.056, \
        giViolin, 2, 350, 1, 0.38, 0.42, 0, 0
    event_i "i", "Voice", 0, 0.056, \
        giViolin, 3, 560, 1, 0.62, -0.47, 0, 0
    event_i "i", "ProbeFour", 0.052, 0.001
  elseif $TEST_CASE == 11 then
    event_i "i", "Voice", 0, 0.056, \
        giViolin, 1, 247, 1, 0.31, 0.37, 0, 0
    event_i "i", "Voice", 0, 0.056, \
        giViolin, 2, 370, 1, 0.43, -0.44, 0, 0
    event_i "i", "Voice", 0, 0.056, \
        giViolin, 3, 554, 1, 0.57, 0.51, 0, 0
    event_i "i", "Voice", 0, 0.056, \
        giViolin, 4, 740, 1, 0.69, -0.58, 0, 0
    event_i "i", "ProbeFour", 0.052, 0.001
  elseif $TEST_CASE == 12 then
    event_i "i", "Voice", 0, 0.016, \
        giViolin, 1, 330, 1, 0.45, 0.55, 0, 0, 0
    event_i "i", "Voice", 0.016, 0.04, \
        giViolin, 1, 440, 1, 0.45, 0.55, 0, 0, 1
    event_i "i", "ProbeOne", 0.052, 0.001, 1, 1
  elseif $TEST_CASE == 13 then
    ; One zero control block releases contact without erasing bow motion.
    iNoteOff = 0.12
    iGap = 32 / sr
    event_i "i", "GateReattack", 0, 0.24
    event_i "i", "ProbeOne", iNoteOff - 0.001, 0.001, 1, 1
    event_i "i", "ProbeOne", iNoteOff + 0.0005, 0.001, 1, 2
    event_i "i", "ProbeOne", iNoteOff + iGap + 0.0015, 0.001, 1, 3
    event_i "i", "ProbeOne", iNoteOff + 0.020, 0.001, 1, 4
  elseif $TEST_CASE == 14 then
    ; Plain k assignments have their first values only at the first k-pass.
    event_i "i", "KAssignmentVoice", 0, 0.04, \
        giViolin, 0, 440, 1, 0.45, 0.55, 0, 0, 0, 0
    event_i "i", "ProbeFour", 0.03, 0.001
  elseif $TEST_CASE == 15 then
    ; Exact tremolo handoff with plain k-rate gate, pitch, and mode inputs.
    if $TEST_SPLIT == 0 then
      event_i "i", "KAssignmentVoice", 0, 0.056, \
          giViolin, 1, 445, 1, 0.45, 0.55, 18, 5.2, 4, 0
    else
      event_i "i", "KAssignmentVoice", 0, $TEST_SPLIT_TIME, \
          giViolin, 1, 445, 1, 0.45, 0.55, 18, 5.2, 4, 0
      event_i "i", "KAssignmentVoice", $TEST_SPLIT_TIME, \
          0.056 - $TEST_SPLIT_TIME, \
          giViolin, 1, 445, 1, 0.45, 0.55, 18, 5.2, 4, 0
    endif
    event_i "i", "ProbeOne", 0.052, 0.001, 1, 1
  elseif $TEST_CASE == 16 then
    ; One physical finger shift must not gain noise when ksmps gets smaller.
    event_i "i", "SmoothFingerShift", 0, 0.40
    event_i "i", "ProbeOne", 0.399, 0.001, 1, 1
  elseif $TEST_CASE == 17 then
    ; An open-string arrival is one arrival, not an arrival plus a shift.
    event_i "i", "SmoothFingerArrival", 0, 0.40
    event_i "i", "ProbeOne", 0.399, 0.001, 1, 1
  elseif $TEST_CASE == 18 then
    event_i "i", "ReverseGlide", 0, 0.22
    event_i "i", "ProbeOne", 9672 / sr, ksmps / sr, 3, 1
    event_i "i", "ProbeOne", 9680 / sr, ksmps / sr, 3, 2
  elseif $TEST_CASE == 19 then
    event_i "i", "BridgePluck", 0, 0.02
  endif
endin

</CsInstruments>
<CsScore>
i "ScheduleTest" 0 0.001
e
</CsScore>
</CsoundSynthesizer>
