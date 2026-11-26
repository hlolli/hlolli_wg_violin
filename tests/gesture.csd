<CsoundSynthesizer>
<CsOptions>
-n -d -m128
</CsOptions>
<CsInstruments>

#ifndef TEST_CASE
#define TEST_CASE #1#
#endif
#ifndef TEST_ARTICULATION
#define TEST_ARTICULATION #1#
#endif
#ifndef TEST_SPLIT
#define TEST_SPLIT #0#
#endif
#ifndef TEST_SPLIT_TIME
#define TEST_SPLIT_TIME #0.016125#
#endif
#ifndef TEST_END
#define TEST_END #0.66#
#endif
#ifndef TEST_FAULT
#define TEST_FAULT #1#
#endif
#ifndef TEST_MOVE_AT_LIFT
#define TEST_MOVE_AT_LIFT #0#
#endif

sr = 48000
ksmps = 32
nchnls = 2
0dbfs = 1

giViolin hlolli_wg_violin_create

instr Voice
  kTrigger init p7
  kFrequency init p6
  kForce init p8
  kSpeed init p9
  kPosition init p10
  kArticulation init p11

  aLeft, aRight hlolli_wg_violin \
      kTrigger, kFrequency, kForce, kSpeed, kPosition, \
      0, 0, kArticulation, 0, 0, p5, p4
  outs aLeft, aRight
endin

instr DirectControlVoice
  kTime timeinsts
  kForce = 0.24
  kSpeed = 0.34
  kPosition = 0.11
  if kTime >= 0.16 then
    kForce = 0.82
    kSpeed = -0.72
    kPosition = 0.23
  endif

  aLeft, aRight hlolli_wg_violin \
      1, 440, kForce, kSpeed, kPosition, \
      0, 0, 1, 0, 0, 3, p4
  outs aLeft, aRight
endin

instr BowChangeVoice
  kTime timeinsts
  kSpeed = 0.58
  if kTime >= 0.18 && kTime < 0.36 then
    kSpeed = -0.58
  elseif kTime >= 0.36 then
    kSpeed = 0.52
  endif

  aLeft, aRight hlolli_wg_violin \
      1, 440, 0.48, kSpeed, 0.12, \
      0, 0, 0, 0, 0, 3, p4
  outs aLeft, aRight
endin

instr BowLiftVoice
  kTime timeinsts
  kGate = kTime < 0.20 || kTime >= 0.32 ? 1 : 0
  kMoveBow = kTime >= 0.32 || (kTime >= 0.20 && $TEST_MOVE_AT_LIFT != 0) ? 1 : 0
  kSpeed = kMoveBow == 0 ? 0.58 : -0.72
  kForce = kMoveBow == 0 ? 0.52 : 0.81

  aLeft, aRight hlolli_wg_violin \
      kGate, 493.883301256124, kForce, kSpeed, 0.12, \
      0, 0, $TEST_ARTICULATION, 0, 0, 3, p4
  outs aLeft, aRight
endin

instr ModeChangeVoice
  kTime timeinsts
  kArticulation = 1
  if kTime >= 0.16 && kTime < 0.32 then
    kArticulation = 4
  elseif kTime >= 0.32 then
    kArticulation = 0
  endif

  aLeft, aRight hlolli_wg_violin \
      1, 440, 0.52, 0.58, 0.12, \
      0, 0, kArticulation, 0, 0, 3, p4
  outs aLeft, aRight
endin

instr StressVoice
  iIndex = p5
  kPhase phasor 0.37 + 0.017 * iIndex, 0.19 * iIndex
  kTriangle = 1 - abs(2 * kPhase - 1)
  kArticulation = 1 + int(4 * min(kPhase, 0.999999))
  kForce = 0.04 + 0.92 * kTriangle
  kSpeed = (0.12 + 0.82 * (1 - kTriangle)) * \
      (kPhase < 0.5 ? 1 : -1)
  kPosition = 0.015 + 0.46 * kTriangle
  kGatePhase phasor 1.13 + 0.03 * iIndex, 0.11 * iIndex
  kTrigger = kGatePhase < 0.88 ? 1 : 0
  kFrequency = p6 * exp(0.42 * log(2) * kTriangle)

  aLeft, aRight hlolli_wg_violin \
      kTrigger, kFrequency, kForce, kSpeed, kPosition, \
      16 * kTriangle, 4.2 + 1.7 * kTriangle, \
      kArticulation, 0, 0, p5, p4
  outs aLeft, aRight
endin

instr Renderer
  aLeft, aRight hlolli_wg_violin_resonance \
      p4, 0.74, 0, 0.14
  outs aLeft, aRight
endin

instr GestureProbe
  iArticulation, iActive, iPhase, iForceTarget, iSpeedTarget, \
      iForceOutput, iSpeedOutput, iContactOutput, iOnsetSamples, \
      iStrokeSamples, iStrokes, iBowChanges, iPresetChanges, \
      iDirectOverrides, iRecoveries, iReleaseArticulation, \
      iReleaseGainTarget, iFinite \
      hlolli_wg_violin_test_gesture p4, p5
  printf_i \
      "WG_GESTURE %d %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g\n", \
      1, p6, iArticulation, iActive, iPhase, iForceTarget, iSpeedTarget, \
      iForceOutput, iSpeedOutput, iContactOutput, iOnsetSamples, \
      iStrokeSamples, iStrokes, iBowChanges, iPresetChanges, \
      iDirectOverrides, iRecoveries, iReleaseArticulation, \
      iReleaseGainTarget, iFinite
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
      "WG_GESTURE_WAVE %d %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g\n", \
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
      "WG_GESTURE_STRING %d %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g\n", \
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
      "WG_GESTURE_BODY %d %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g\n", \
      1, p5, iSendEnergy1, iSendEnergy2, iSendEnergy3, iSendEnergy4, \
      iDriveEnergy, iOutputEnergyLeft, iOutputEnergyRight, \
      iResetCount, iClipCount, iFinite
endin

instr GestureFault
  iOk hlolli_wg_violin_test_gesture_fault p4, p5, p6
  printf_i "WG_GESTURE_FAULT %d %.17g\n", 1, p7, iOk
endin

instr ProbeOne
  event_i "i", "GestureProbe", 0, 0.001, giViolin, p4, p5
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
    ; One held preset, sampled through onset and sustain.
    event_i "i", "Voice", 0, 0.60, \
        giViolin, 3, 440, 1, 0.56, 0.62, 0.12, $TEST_ARTICULATION
    event_i "i", "ProbeOne", 0.004, 0.001, 3, 1
    event_i "i", "ProbeOne", 0.012, 0.001, 3, 2
    event_i "i", "ProbeOne", 0.030, 0.001, 3, 3
    event_i "i", "ProbeOne", 0.080, 0.001, 3, 4
    event_i "i", "ProbeOne", 0.180, 0.001, 3, 5
    event_i "i", "ProbeOne", 0.340, 0.001, 3, 6
    event_i "i", "ProbeOne", 0.560, 0.001, 3, 7
  elseif $TEST_CASE == 2 then
    ; Direct k-rate changes during a held detache gesture.
    event_i "i", "DirectControlVoice", 0, 0.44, giViolin
    event_i "i", "ProbeOne", 0.140, 0.001, 3, 1
    event_i "i", "ProbeOne", 0.162, 0.001, 3, 2
    event_i "i", "ProbeOne", 0.185, 0.001, 3, 3
    event_i "i", "ProbeOne", 0.300, 0.001, 3, 4
    event_i "i", "ProbeOne", 0.420, 0.001, 3, 5
  elseif $TEST_CASE == 3 then
    ; Two direct bow changes on one held rail.
    event_i "i", "BowChangeVoice", 0, 0.54, giViolin
    event_i "i", "ProbeOne", 0.160, 0.001, 3, 1
    event_i "i", "ProbeOne", 0.182, 0.001, 3, 2
    event_i "i", "ProbeOne", 0.220, 0.001, 3, 3
    event_i "i", "ProbeOne", 0.362, 0.001, 3, 4
    event_i "i", "ProbeOne", 0.410, 0.001, 3, 5
    event_i "i", "ProbeOne", 0.520, 0.001, 3, 6
  elseif $TEST_CASE == 4 then
    ; Smooth held change from detache to tremolo to direct arco.
    event_i "i", "ModeChangeVoice", 0, 0.48, giViolin
    event_i "i", "ProbeOne", 0.140, 0.001, 3, 1
    event_i "i", "ProbeOne", 0.162, 0.001, 3, 2
    event_i "i", "ProbeOne", 0.210, 0.001, 3, 3
    event_i "i", "ProbeOne", 0.322, 0.001, 3, 4
    event_i "i", "ProbeOne", 0.390, 0.001, 3, 5
    event_i "i", "ProbeOne", 0.460, 0.001, 3, 6
  elseif $TEST_CASE == 5 then
    ; Exact score-event handoff. Codes 0 and 4 continue; 1--3 reattack.
    if $TEST_SPLIT == 0 then
      event_i "i", "Voice", 0, 0.056, \
          giViolin, 3, 440, 1, 0.56, 0.62, 0.12, $TEST_ARTICULATION
    else
      event_i "i", "Voice", 0, $TEST_SPLIT_TIME, \
          giViolin, 3, 440, 1, 0.56, 0.62, 0.12, $TEST_ARTICULATION
      event_i "i", "Voice", $TEST_SPLIT_TIME, \
          0.056 - $TEST_SPLIT_TIME, \
          giViolin, 3, 440, 1, 0.56, 0.62, 0.12, $TEST_ARTICULATION
    endif
    event_i "i", "ProbeOne", 0.052, 0.001, 3, 1
  elseif $TEST_CASE == 6 then
    ; Four gesture presets feed four string and body lanes.
    event_i "i", "Voice", 0, 0.60, \
        giViolin, 1, 293.664767917408, 1, 0.46, 0.52, 0.10, 1
    event_i "i", "Voice", 0, 0.60, \
        giViolin, 2, 440, 1, 0.60, -0.58, 0.14, 2
    event_i "i", "Voice", 0, 0.60, \
        giViolin, 3, 659.255113825740, 1, 0.52, 0.66, 0.18, 3
    event_i "i", "Voice", 0, 0.60, \
        giViolin, 4, 987.766602512248, 1, 0.42, -0.72, 0.22, 4
    event_i "i", "Renderer", 0, 0.64, giViolin
    event_i "i", "ProbeFour", 0.56, 0.001, 1
    event_i "i", "BodyProbe", 0.62, 0.001, giViolin, 1
  elseif $TEST_CASE == 7 then
    ; Four-string control, mode, gate, and pitch stress.
    event_i "i", "StressVoice", 0, 8, \
        giViolin, 1, 195.997717990875
    event_i "i", "StressVoice", 0, 8, \
        giViolin, 2, 293.664767917408
    event_i "i", "StressVoice", 0, 8, \
        giViolin, 3, 440
    event_i "i", "StressVoice", 0, 8, \
        giViolin, 4, 659.255113825740
    event_i "i", "Renderer", 0, 8.04, giViolin
    event_i "i", "ProbeFour", 8.001, 0.001, 1
    event_i "i", "BodyProbe", 8.02, 0.001, giViolin, 1
  elseif $TEST_CASE == 8 then
    ; A bad gesture value recovers without clearing the stored rail.
    event_i "i", "Voice", 0, 0.42, \
        giViolin, 3, 440, 1, 0.56, 0.62, 0.12, 1
    event_i "i", "ProbeOne", 0.198, 0.001, 3, 1
    event_i "i", "GestureFault", 0.200, 0.001, \
        giViolin, 3, $TEST_FAULT, 1
    event_i "i", "ProbeOne", 0.204, 0.001, 3, 2
    event_i "i", "ProbeOne", 0.300, 0.001, 3, 3
  elseif $TEST_CASE == 9 then
    event_i "i", "BowLiftVoice", 0, 0.45, giViolin
    event_i "i", "ProbeOne", 0.190, 0.001, 3, 1
    event_i "i", "ProbeOne", 0.205, 0.001, 3, 2
    event_i "i", "ProbeOne", 0.380, 0.001, 3, 3
  endif
endin

</CsInstruments>
<CsScore>
i "ScheduleTest" 0 0.001
e
</CsScore>
</CsoundSynthesizer>
