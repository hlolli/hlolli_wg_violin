<CsoundSynthesizer>
<CsOptions>
-n -d -m128
</CsOptions>
<CsInstruments>

#ifndef TEST_CASE
#define TEST_CASE #1#
#endif
#ifndef TEST_ORDER
#define TEST_ORDER #2#
#endif
#ifndef TEST_FREQUENCY
#define TEST_FREQUENCY #391.99543598175#
#endif
#ifndef TEST_STRING
#define TEST_STRING #1#
#endif
#ifndef TEST_SPLIT
#define TEST_SPLIT #0#
#endif
#ifndef TEST_SPLIT_TIME
#define TEST_SPLIT_TIME #0.016125#
#endif
#ifndef TEST_END
#define TEST_END #0.56#
#endif

sr = 48000
ksmps = 32
nchnls = 2
0dbfs = 1

giViolin hlolli_wg_violin_create

instr Voice
  kTrigger init p7
  kFrequency init p6
  kHarmonic init p12

  aLeft, aRight hlolli_wg_violin \
      kTrigger, kFrequency, p8, p9, p10, \
      0, 0, p11, kHarmonic, 0, p5, p4
  outs aLeft, aRight
endin

instr KAssignmentVoice
  kTrigger = p7
  kFrequency = p6
  kHarmonic = p12

  aLeft, aRight hlolli_wg_violin \
      kTrigger, kFrequency, p8, p9, p10, \
      0, 0, p11, kHarmonic, 0, p5, p4
  outs aLeft, aRight
endin

instr SwitchVoice
  kHarmonic init p7
  if timeinstk() >= 25 then
    kHarmonic = p8
  endif

  aLeft, aRight hlolli_wg_violin \
      1, p6, 0.48, 0.54, 0.113, \
      0, 0, 0, kHarmonic, 0, p5, p4
  outs aLeft, aRight
endin

instr PressureVoice
  kTime timeinsts
  kHarmonic = 0
  if kTime >= 0.08 && kTime < 0.16 then
    kHarmonic = p7
  elseif kTime >= 0.24 then
    kHarmonic = p7
  endif

  aLeft, aRight hlolli_wg_violin \
      1, p6, 0.48, 0.54, 0.113, \
      0, 0, 0, kHarmonic, 0, p5, p4
  outs aLeft, aRight
endin

instr RapidOrderVoice
  kTime timeinsts
  kOrder init 2
  kFrequency init 391.995435981749
  kOrder = min(8, 2 + int(kTime / 0.048))
  kFrequency = 195.997717990875 * kOrder

  aLeft, aRight hlolli_wg_violin \
      1, kFrequency, 0.48, 0.54, 0.113, \
      0, 0, 0, kOrder, 0, 1, p4
  outs aLeft, aRight
endin

instr HarmonicPitchVoice
  kTime timeinsts
  kFrequency init 783.990871963499
  if kTime >= 0.096 then
    kFrequency = 1760
  endif

  aLeft, aRight hlolli_wg_violin \
      1, kFrequency, 0.48, 0.54, 0.113, \
      0, 0, 0, 4, 0, 1, p4
  outs aLeft, aRight
endin

instr SweepVoice
  iOpen = p6
  iOrderCount = p7
  kPhase phasor p8, p9
  kOrder = 2 + int(kPhase * iOrderCount)
  kTriangle = 1 - abs(2 * kPhase - 1)
  kFrequency = iOpen * kOrder
  kForce = 0.28 + 0.44 * kTriangle
  kSpeed = (0.30 + 0.48 * (1 - kTriangle)) * \
      (kPhase < 0.5 ? 1 : -1)
  kPosition = 0.05 + 0.36 * kTriangle

  aLeft, aRight hlolli_wg_violin \
      1, kFrequency, kForce, kSpeed, kPosition, \
      18 * kTriangle, 4.7 + kTriangle, 0, kOrder, 0, p5, p4
  outs aLeft, aRight
endin

instr Renderer
  aLeft, aRight hlolli_wg_violin_resonance \
      p4, 0.72, 0, 0.18
  outs aLeft, aRight
endin

instr HarmonicProbe
  iRequestedOrder, iActiveOrder, iFilterOrder, iValid, iNatural, \
      iSoundingFrequency, iFundamentalFrequency, iStopPosition, \
      iTouchPosition, iTouchTarget, iTouchPressure, iTouchPeriod, \
      iProjectionInput, iProjectionOutput, iTransitions, iRejections, \
      iTouchSamples, iHistoryIndex, iFinite \
      hlolli_wg_violin_test_harmonic p4, p5
  printf_i \
      "WG_HARMONIC %d %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g\n", \
      1, p6, iRequestedOrder, iActiveOrder, iFilterOrder, iValid, iNatural, \
      iSoundingFrequency, iFundamentalFrequency, iStopPosition, \
      iTouchPosition, iTouchTarget, iTouchPressure, iTouchPeriod, \
      iProjectionInput, iProjectionOutput, iTransitions, iRejections, \
      iTouchSamples, iHistoryIndex, iFinite
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

instr StringProbe
  iPhase, iVibratoPhase, iFrequency, iTrigger, iForce, iSpeed, \
      iActivity, iLastSample, iGapSamples, iOwner, iSuccessor \
      hlolli_wg_violin_test_string p4, p5
  printf_i \
      "WG_STRING %d %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g\n", \
      1, p6, iPhase, iVibratoPhase, iFrequency, iTrigger, iForce, \
      iSpeed, iActivity, iLastSample, iGapSamples, iOwner, iSuccessor
endin

instr BodyProbe
  iBody, iSympathetic, iMute, iModeCount, \
      iSendSamples1, iSendSamples2, iSendSamples3, iSendSamples4, \
      iSendEnergy1, iSendEnergy2, iSendEnergy3, iSendEnergy4, \
      iLastDrive, iDriveEnergy, iModalEnergy, iStateSignature, \
      iLastLeft, iLastRight, iOutputEnergyLeft, iOutputEnergyRight, \
      iPeakLeft, iPeakRight, iProcessedSamples, iFastForwardSamples, \
      iResetCount, iClipCount, iFinite \
      hlolli_wg_violin_test_body p4
  printf_i \
      "WG_HARMONIC_BODY %d %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g\n", \
      1, p5, iSendEnergy1, iSendEnergy2, iSendEnergy3, iSendEnergy4, \
      iDriveEnergy, iOutputEnergyLeft, iOutputEnergyRight, \
      iResetCount, iClipCount, iFinite
endin

instr ProbeOne
  event_i "i", "HarmonicProbe", 0, 0.001, giViolin, p4, p5
  event_i "i", "WaveProbe", 0, 0.001, giViolin, p4, p5
  event_i "i", "StringProbe", 0, 0.001, giViolin, p4, p5
endin

instr ProbeFour
  event_i "i", "ProbeOne", 0, 0.001, 1, p4
  event_i "i", "ProbeOne", 0, 0.001, 2, p4 + 1
  event_i "i", "ProbeOne", 0, 0.001, 3, p4 + 2
  event_i "i", "ProbeOne", 0, 0.001, 4, p4 + 3
endin

instr KeepAlive
  aSilence init 0
  outs aSilence, aSilence
endin

instr ScheduleTest
  event_i "i", "KeepAlive", 0, $TEST_END

  if $TEST_CASE == 1 then
    ; One steady natural or artificial harmonic.
    event_i "i", "Voice", 0, 0.52, \
        giViolin, $TEST_STRING, $TEST_FREQUENCY, 1, \
        0.48, 0.54, 0.113, 0, $TEST_ORDER
    event_i "i", "ProbeOne", 0.48, 0.001, $TEST_STRING, 1
  elseif $TEST_CASE == 2 then
    ; Let touch pressure rise, fail to zero, and return on one rail.
    event_i "i", "PressureVoice", 0, 0.34, \
        giViolin, 1, $TEST_FREQUENCY, $TEST_ORDER
    event_i "i", "ProbeOne", 0.075, 0.001, 1, 1
    event_i "i", "ProbeOne", 0.082, 0.001, 1, 2
    event_i "i", "ProbeOne", 0.090, 0.001, 1, 3
    event_i "i", "ProbeOne", 0.125, 0.001, 1, 4
    event_i "i", "ProbeOne", 0.162, 0.001, 1, 5
    event_i "i", "ProbeOne", 0.185, 0.001, 1, 6
    event_i "i", "ProbeOne", 0.235, 0.001, 1, 7
    event_i "i", "ProbeOne", 0.250, 0.001, 1, 8
    event_i "i", "ProbeOne", 0.285, 0.001, 1, 9
  elseif $TEST_CASE == 3 then
    ; Constant harmonic across an exact positive handoff.
    if $TEST_SPLIT == 0 then
      event_i "i", "Voice", 0, 0.056, \
          giViolin, 1, $TEST_FREQUENCY, 1, \
          0.48, 0.54, 0.113, 0, $TEST_ORDER
    else
      event_i "i", "Voice", 0, $TEST_SPLIT_TIME, \
          giViolin, 1, $TEST_FREQUENCY, 1, \
          0.48, 0.54, 0.113, 0, $TEST_ORDER
      event_i "i", "Voice", $TEST_SPLIT_TIME, \
          0.056 - $TEST_SPLIT_TIME, \
          giViolin, 1, $TEST_FREQUENCY, 1, \
          0.48, 0.54, 0.113, 0, $TEST_ORDER
    endif
    event_i "i", "ProbeOne", 0.052, 0.001, 1, 1
  elseif $TEST_CASE == 4 then
    ; Normal-to-harmonic change in one owner or at an exact handoff.
    if $TEST_SPLIT == 0 then
      event_i "i", "SwitchVoice", 0, 0.056, \
          giViolin, 1, $TEST_FREQUENCY, 0, $TEST_ORDER
    else
      event_i "i", "Voice", 0, 0.016, \
          giViolin, 1, $TEST_FREQUENCY, 1, \
          0.48, 0.54, 0.113, 0, 0
      event_i "i", "Voice", 0.016, 0.040, \
          giViolin, 1, $TEST_FREQUENCY, 1, \
          0.48, 0.54, 0.113, 0, $TEST_ORDER
    endif
    event_i "i", "ProbeOne", 0.052, 0.001, 1, 1
  elseif $TEST_CASE == 5 then
    ; Invalid order or pitch/string combination on an explicit string.
    event_i "i", "Voice", 0, 0.52, \
        giViolin, $TEST_STRING, $TEST_FREQUENCY, 1, \
        0.48, 0.54, 0.113, 0, $TEST_ORDER
    event_i "i", "ProbeOne", 0.48, 0.001, $TEST_STRING, 1
  elseif $TEST_CASE == 6 then
    ; Four natural harmonics feed four body lanes.
    event_i "i", "Voice", 0, 0.52, \
        giViolin, 1, 391.99543598175, 1, 0.42, 0.48, 0.13, 0, 2
    event_i "i", "Voice", 0, 0.52, \
        giViolin, 2, 880.994303752223, 1, 0.48, -0.52, 0.17, 0, 3
    event_i "i", "Voice", 0, 0.52, \
        giViolin, 3, 1760, 1, 0.54, 0.58, 0.21, 0, 4
    event_i "i", "Voice", 0, 0.52, \
        giViolin, 4, 3296.2755691287, 1, 0.60, -0.62, 0.25, 0, 5
    event_i "i", "Renderer", 0, 0.55, giViolin
    event_i "i", "ProbeFour", 0.48, 0.001, 1
    event_i "i", "BodyProbe", 0.53, 0.001, giViolin, 1
  elseif $TEST_CASE == 7 then
    ; Ten-second, four-string order and control sweep.
    event_i "i", "SweepVoice", 0, 10, \
        giViolin, 1, 195.997717990875, 7, 0.43, 0.00
    event_i "i", "SweepVoice", 0, 10, \
        giViolin, 2, 293.664767917408, 7, 0.47, 0.19
    event_i "i", "SweepVoice", 0, 10, \
        giViolin, 3, 440, 7, 0.53, 0.41
    event_i "i", "SweepVoice", 0, 10, \
        giViolin, 4, 659.25511382574, 6, 0.59, 0.67
    event_i "i", "Renderer", 0, 10.01, giViolin
    event_i "i", "ProbeFour", 10.001, 0.001, 1
    event_i "i", "BodyProbe", 10.003, 0.001, giViolin, 1
  elseif $TEST_CASE == 8 then
    ; Automatic choice must use the internal harmonic fundamental.
    event_i "i", "Voice", 0, 0.52, \
        giViolin, 0, $TEST_FREQUENCY, 1, \
        0.48, 0.54, 0.113, 0, $TEST_ORDER
    event_i "i", "ProbeFour", 0.48, 0.001, 1
  elseif $TEST_CASE == 9 then
    ; Each held harmonic order lasts 48 ms, including its crossfade.
    event_i "i", "RapidOrderVoice", 0, 0.35, giViolin
    event_i "i", "ProbeOne", 0.030, 0.001, 1, 1
    event_i "i", "ProbeOne", 0.078, 0.001, 1, 2
    event_i "i", "ProbeOne", 0.126, 0.001, 1, 3
    event_i "i", "ProbeOne", 0.174, 0.001, 1, 4
    event_i "i", "ProbeOne", 0.222, 0.001, 1, 5
    event_i "i", "ProbeOne", 0.270, 0.001, 1, 6
    event_i "i", "ProbeOne", 0.318, 0.001, 1, 7
  elseif $TEST_CASE == 10 then
    ; Keep order 4 while its stopped and sounding pitches move.
    event_i "i", "HarmonicPitchVoice", 0, 0.22, giViolin
    event_i "i", "ProbeOne", 0.090, 0.001, 1, 1
    event_i "i", "ProbeOne", 0.098, 0.001, 1, 2
    event_i "i", "ProbeOne", 0.114, 0.001, 1, 3
    event_i "i", "ProbeOne", 0.180, 0.001, 1, 4
  elseif $TEST_CASE == 11 then
    ; Auto choice must wait for plain k-rate pitch and harmonic assignments.
    event_i "i", "KAssignmentVoice", 0, 0.52, \
        giViolin, 0, 1760, 1, 0.48, 0.54, 0.113, 0, 4
    event_i "i", "ProbeFour", 0.48, 0.001, 1
  endif
endin

</CsInstruments>
<CsScore>
i "ScheduleTest" 0 0.001
e
</CsScore>
</CsoundSynthesizer>
