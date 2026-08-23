<CsoundSynthesizer>
<CsOptions>
-n -d -m128
</CsOptions>
<CsInstruments>

#ifndef TEST_CASE
#define TEST_CASE #1#
#endif
#ifndef TEST_VARIANT
#define TEST_VARIANT #0#
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
#ifndef TEST_SYMPATHETIC
#define TEST_SYMPATHETIC #1#
#endif
#ifndef TEST_STRANGE
#define TEST_STRANGE #0#
#endif
#ifndef TEST_ORDER
#define TEST_ORDER #0#
#endif
#ifndef TEST_FAULT
#define TEST_FAULT #1#
#endif
#ifndef TEST_SR
#define TEST_SR #48000#
#endif

sr = $TEST_SR
ksmps = 32
nchnls = 2
0dbfs = 1

giViolinA hlolli_wg_violin_create
giViolinB hlolli_wg_violin_create

; Instrument number order lets one case run the renderer before the voices.
instr RenderEarly
  aLeft, aRight hlolli_wg_violin_resonance \
      p4, 0.72, p5, 0.12
  outs aLeft, aRight
endin

instr Voice
  kTrigger init p7
  kFrequency init p6
  kForce init p8
  kSpeed init p9
  kPosition init p10
  kStrange init p11
  kArticulation init p12
  aLeft, aRight hlolli_wg_violin \
      kTrigger, kFrequency, kForce, kSpeed, kPosition, \
      0, 0, kArticulation, 0, kStrange, p5, p4
  outs aLeft, aRight
endin

instr StrangeVoice
  kTrigger = p7
  kForce = p8
  kSpeed = p9
  if $TEST_VARIANT == 1 then
    kSpeed = 0
  elseif $TEST_VARIANT == 2 then
    kForce = 0
  elseif $TEST_VARIANT == 3 then
    kTrigger = 0
  elseif $TEST_VARIANT == 4 then
    kForce = 0.001
  endif
  aLeft, aRight hlolli_wg_violin \
      kTrigger, p6, kForce, kSpeed, 0.11, \
      0, 0, 0, 0, $TEST_STRANGE, p5, p4
  outs aLeft, aRight
endin

instr StressVoice
  iIndex = p5
  kTime timeinsts
  kPhase phasor 0.37 + 0.019 * iIndex, 0.13 * iIndex
  kTriangle = 1 - abs(2 * kPhase - 1)
  kGatePhase phasor 0.91 + 0.043 * iIndex, 0.07 * iIndex
  kTrigger = kGatePhase < 0.78 ? 1 : 0
  kForce = 0.28 + 0.24 * \
      sin(6.283185307179586 * (0.29 + 0.017 * iIndex) * kTime)
  kSpeed = 0.48 * \
      sin(6.283185307179586 * (0.41 + 0.021 * iIndex) * kTime)
  kPosition = 0.12 + 0.07 * \
      sin(6.283185307179586 * (0.17 + 0.011 * iIndex) * kTime)
  kFrequency = p6 * exp(0.42 * log(2) * kTriangle)
  kStrange = sin(6.283185307179586 * \
      (0.071 + 0.009 * iIndex) * kTime + 0.4 * iIndex)
  aLeft, aRight hlolli_wg_violin \
      kTrigger, kFrequency, kForce, kSpeed, kPosition, \
      9 * kTriangle, 4.4 + 1.5 * kTriangle, \
      0, 0, kStrange, p5, p4
  outs aLeft, aRight
endin

instr RenderLate
  aLeft, aRight hlolli_wg_violin_resonance \
      p4, 0.72, p5, 0.12
  outs aLeft, aRight
endin

instr StressRenderer
  kSympathetic = 0.5 + 0.5 * \
      sin(6.283185307179586 * 0.083 * timeinsts())
  aLeft, aRight hlolli_wg_violin_resonance \
      p4, 0.72, kSympathetic, 0.12
  outs aLeft, aRight
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
      "WG_SYMP_WAVE %d %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g\n", \
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
      "WG_SYMP_STRING %d %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g\n", \
      1, p6, iPhase, iVibratoPhase, iFrequency, iTrigger, iForce, \
      iSpeed, iActivity, iLastSample, iGapSamples, iOwner, iSuccessor
endin

instr PhysicsProbe
  iContactMemory, iContactMemoryVelocity, iContactAdhesion, \
      iContactSteadyDisplacement, iContactForce, iContactIterations, \
      iContactFailures, iTemperature, iThermalScale, iThermalWork, \
      iHairDisplacement, iHairVelocity, iHairEffectiveSpeed, \
      iBoardDisplacement, iBoardCompression, iBoardForce, iBoardEnergy, \
      iBoardImpacts, iNoiseLast, iNoiseEnergy, iNoisePeak, iNoiseSamples, \
      iMechanicalEvents, iCouplingInput, iCouplingEnergy, iCouplingPeak, \
      iCouplingSamples, iCouplingSourceMask, iRecoveries, \
      iSecondPolarization, iFinite \
      hlolli_wg_violin_test_physics p4, p5
  printf_i \
      "WG_SYMP_PHYSICS_A %d %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g\n", \
      1, p6, iContactMemory, iContactMemoryVelocity, iContactAdhesion, \
      iContactSteadyDisplacement, iContactForce, iContactIterations, \
      iContactFailures, iTemperature, iThermalScale, iThermalWork, \
      iHairDisplacement, iHairVelocity, iHairEffectiveSpeed, \
      iBoardDisplacement, iBoardCompression, iBoardForce
  printf_i \
      "WG_SYMP_PHYSICS_B %d %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g\n", \
      1, p6, iBoardEnergy, iBoardImpacts, iNoiseLast, iNoiseEnergy, \
      iNoisePeak, iNoiseSamples, iMechanicalEvents, iCouplingInput, \
      iCouplingEnergy, iCouplingPeak, iCouplingSamples, \
      iCouplingSourceMask, iRecoveries, iSecondPolarization, iFinite
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
      "WG_SYMP_BODY %d %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g\n", \
      1, p5, iBody, iSympathetic, iMute, iModeCount, \
      iSendSamples1, iSendSamples2, iSendSamples3, iSendSamples4, \
      iSendEnergy1, iSendEnergy2, iSendEnergy3, iSendEnergy4, \
      iLastDrive, iDriveEnergy, iModalEnergy, iStateSignature, \
      iLastLeft, iLastRight, iOutputEnergyLeft, iOutputEnergyRight, \
      iPeakLeft, iPeakRight, iProcessedSamples, iFastForwardSamples, \
      iResetCount, iClipCount, iFinite
endin

instr StrangeProbe
  iStrange, iSympathetic, iSympatheticApplied, iAirState, \
      iDispersionInput, iDispersionOutput, iSubharmonicPhase, \
      iSubharmonicEnvelope, iSquealState, iSquealFrequency, \
      iCouplingMix, iLastOutput, iEnergy, iPeak, iSamples, iRecoveries, \
      iPassiveActive, \
      iPassiveLevel, iPassiveEnergy, iPassivePeak, iPassiveSamples, iFinite \
      hlolli_wg_violin_test_strange p4, p5
  printf_i \
      "WG_SYMP_STRANGE %d %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g\n", \
      1, p6, iStrange, iSympathetic, iSympatheticApplied, iAirState, \
      iDispersionInput, iDispersionOutput, iSubharmonicPhase, \
      iSubharmonicEnvelope, iSquealState, iSquealFrequency, \
      iCouplingMix, iLastOutput, iEnergy, iPeak, iSamples, iRecoveries, \
      iPassiveActive, \
      iPassiveLevel, iPassiveEnergy, iPassivePeak, iPassiveSamples, iFinite
endin

instr StrangeFault
  iOk hlolli_wg_violin_test_strange_fault p4, p5, p6
  printf_i "WG_SYMP_FAULT %d %.17g\n", 1, p7, iOk
endin

instr ProbeOne
  event_i "i", "WaveProbe", 0, 0.001, p4, p5, p6
  event_i "i", "StringProbe", 0, 0.001, p4, p5, p6
  event_i "i", "PhysicsProbe", 0, 0.001, p4, p5, p6
  event_i "i", "StrangeProbe", 0, 0.001, p4, p5, p6
endin

instr KeepAlive
  aSilence init 0
  outs aSilence, aSilence
endin

instr ScheduleTest
  event_i "i", "KeepAlive", 0, $TEST_END
  if $TEST_CASE == 1 then
    ; A stopped G string matches the open D target.
    event_i "i", "Voice", 0, 0.58, \
        giViolinA, 1, 293.664767917408, 1, 0.60, 0.62, 0.10, 0
    if $TEST_VARIANT == 1 then
      ; A trigger-zero open target must not be stepped twice.
      event_i "i", "Voice", 0, 0.58, \
          giViolinA, 2, 293.664767917408, 0, 0, 0, 0.12, 0
    endif
    if $TEST_ORDER == 0 then
      event_i "i", "RenderEarly", 0, 0.60, \
          giViolinA, $TEST_SYMPATHETIC
    else
      event_i "i", "RenderLate", 0, 0.60, \
          giViolinA, $TEST_SYMPATHETIC
    endif
    event_i "i", "ProbeOne", 0.560, 0.001, giViolinA, 1, 1
    event_i "i", "ProbeOne", 0.560, 0.001, giViolinA, 2, 2
    event_i "i", "ProbeOne", 0.560, 0.001, giViolinA, 3, 3
    event_i "i", "ProbeOne", 0.560, 0.001, giViolinA, 4, 4
    event_i "i", "BodyProbe", 0.560, 0.001, giViolinA, 1
  elseif $TEST_CASE == 2 then
    ; Owned open, stopped, or other-handle targets.
    iTargetHandle = $TEST_VARIANT == 2 ? giViolinB : giViolinA
    iTargetFrequency = $TEST_VARIANT == 1 ? 330 : 293.664767917408
    event_i "i", "Voice", 0, 0.58, \
        giViolinA, 1, 293.664767917408, 1, 0.60, 0.62, 0.10, 0
    event_i "i", "Voice", 0, 0.58, \
        iTargetHandle, 2, iTargetFrequency, 0, 0, 0, 0.12, 0
    if $TEST_ORDER == 0 then
      event_i "i", "RenderEarly", 0, 0.60, \
          iTargetHandle, $TEST_SYMPATHETIC
    else
      event_i "i", "RenderLate", 0, 0.60, \
          iTargetHandle, $TEST_SYMPATHETIC
    endif
    event_i "i", "ProbeOne", 0.560, 0.001, iTargetHandle, 2, 1
    event_i "i", "BodyProbe", 0.560, 0.001, iTargetHandle, 1
  elseif $TEST_CASE == 3 then
    ; A fixed held bow exposes the three kStrange paths.
    event_i "i", "StrangeVoice", 0, 0.58, \
        giViolinA, 3, 440, 1, 0.58, 0.61
    if $TEST_ORDER == 0 then
      event_i "i", "RenderEarly", 0, 0.60, \
          giViolinA, $TEST_SYMPATHETIC
    else
      event_i "i", "RenderLate", 0, 0.60, \
          giViolinA, $TEST_SYMPATHETIC
    endif
    event_i "i", "ProbeOne", 0.560, 0.001, giViolinA, 1, 1
    event_i "i", "ProbeOne", 0.560, 0.001, giViolinA, 2, 2
    event_i "i", "ProbeOne", 0.560, 0.001, giViolinA, 3, 3
    event_i "i", "ProbeOne", 0.560, 0.001, giViolinA, 4, 4
    event_i "i", "BodyProbe", 0.560, 0.001, giViolinA, 1
  elseif $TEST_CASE == 4 then
    ; Held control and exact split handoffs must match.
    if $TEST_SPLIT == 0 then
      event_i "i", "Voice", 0, 0.056, \
          giViolinA, 1, 293.664767917408, 1, 0.60, 0.62, 0.10, \
          $TEST_STRANGE
      event_i "i", "RenderEarly", 0, 0.056, \
          giViolinA, $TEST_SYMPATHETIC
    else
      event_i "i", "Voice", 0, $TEST_SPLIT_TIME, \
          giViolinA, 1, 293.664767917408, 1, 0.60, 0.62, 0.10, \
          $TEST_STRANGE
      event_i "i", "Voice", $TEST_SPLIT_TIME, \
          0.056 - $TEST_SPLIT_TIME, \
          giViolinA, 1, 293.664767917408, 1, 0.60, 0.62, 0.10, \
          $TEST_STRANGE
      event_i "i", "RenderEarly", 0, $TEST_SPLIT_TIME, \
          giViolinA, $TEST_SYMPATHETIC
      event_i "i", "RenderEarly", $TEST_SPLIT_TIME, \
          0.056 - $TEST_SPLIT_TIME, giViolinA, $TEST_SYMPATHETIC
    endif
    event_i "i", "ProbeOne", 0.052, 0.001, giViolinA, 1, 1
    event_i "i", "ProbeOne", 0.052, 0.001, giViolinA, 2, 2
    event_i "i", "BodyProbe", 0.052, 0.001, giViolinA, 1
  elseif $TEST_CASE == 5 then
    ; A 500 ms renderer gap must decay passive rails before a safe resume.
    event_i "i", "Voice", 0, 0.30, \
        giViolinA, 1, 293.664767917408, 1, 0.60, 0.62, 0.10, 0
    event_i "i", "RenderEarly", 0, 0.30, \
        giViolinA, $TEST_SYMPATHETIC
    event_i "i", "ProbeOne", 0.280, 0.001, giViolinA, 2, 1
    event_i "i", "RenderEarly", 0.800, 0.08, \
        giViolinA, $TEST_SYMPATHETIC
    event_i "i", "ProbeOne", 0.804, 0.001, giViolinA, 2, 2
    event_i "i", "ProbeOne", 0.860, 0.001, giViolinA, 2, 3
    event_i "i", "BodyProbe", 0.860, 0.001, giViolinA, 1
  elseif $TEST_CASE == 6 then
    ; Each bad sympathetic-string field recovers without clearing its physical rail.
    if $TEST_FAULT == 7 then
      event_i "i", "Voice", 0, 0.46, \
          giViolinA, 1, 293.664767917408, 1, 0.60, 0.62, 0.10, 0
      event_i "i", "RenderEarly", 0, 0.48, giViolinA, 1
      event_i "i", "ProbeOne", 0.198, 0.001, giViolinA, 2, 1
      event_i "i", "StrangeFault", 0.200, 0.001, \
          giViolinA, 2, $TEST_FAULT, 1
      event_i "i", "ProbeOne", 0.204, 0.001, giViolinA, 2, 2
      event_i "i", "ProbeOne", 0.420, 0.001, giViolinA, 2, 3
    else
      event_i "i", "StrangeVoice", 0, 0.46, \
          giViolinA, 3, 440, 1, 0.66, 0.72
      event_i "i", "RenderEarly", 0, 0.48, giViolinA, 1
      event_i "i", "ProbeOne", 0.198, 0.001, giViolinA, 3, 1
      event_i "i", "StrangeFault", 0.200, 0.001, \
          giViolinA, 3, $TEST_FAULT, 1
      event_i "i", "ProbeOne", 0.204, 0.001, giViolinA, 3, 2
      event_i "i", "ProbeOne", 0.420, 0.001, giViolinA, 3, 3
    endif
  elseif $TEST_CASE == 7 then
    ; Four strings sweep the whole kStrange and kSympathetic ranges.
    event_i "i", "StressVoice", 0, 6, \
        giViolinA, 1, 195.997717990875
    event_i "i", "StressVoice", 0, 6, \
        giViolinA, 2, 293.664767917408
    event_i "i", "StressVoice", 0, 6, \
        giViolinA, 3, 440
    event_i "i", "StressVoice", 0, 6, \
        giViolinA, 4, 659.255113825740
    event_i "i", "StressRenderer", 0, 6.02, giViolinA
    event_i "i", "ProbeOne", 6.001, 0.001, giViolinA, 1, 1
    event_i "i", "ProbeOne", 6.001, 0.001, giViolinA, 2, 2
    event_i "i", "ProbeOne", 6.001, 0.001, giViolinA, 3, 3
    event_i "i", "ProbeOne", 6.001, 0.001, giViolinA, 4, 4
    event_i "i", "BodyProbe", 6.001, 0.001, giViolinA, 1
  elseif $TEST_CASE == 8 then
    ; A stopped note must damp before its unowned rail retunes open.
    event_i "i", "Voice", 0, 0.30, \
        giViolinA, 1, 293.664767917408, 1, 0.60, 0.62, 0.10, 0
    event_i "i", "RenderEarly", 0, 0.60, \
        giViolinA, $TEST_SYMPATHETIC
    event_i "i", "ProbeOne", 0.560, 0.001, giViolinA, 1, 1
    event_i "i", "BodyProbe", 0.560, 0.001, giViolinA, 1
  elseif $TEST_CASE == 9 then
    ; A reserved owned target must reject both fixed and sympathetic drive.
    event_i "i", "Voice", 0, 0.30, \
        giViolinA, 1, 293.664767917408, 1, 0.60, 0.62, 0.10, 0, 0
    event_i "i", "Voice", 0, 0.30, \
        giViolinA, 2, 293.664767917408, 1, 0.60, 0.62, 0.12, 0, 9
    event_i "i", "RenderEarly", 0, 0.32, \
        giViolinA, $TEST_SYMPATHETIC
    event_i "i", "ProbeOne", 0.280, 0.001, giViolinA, 2, 1
  elseif $TEST_CASE == 10 then
    ; Probe the squeal band where its 4.2 kHz floor meets low Nyquist rates.
    event_i "i", "StrangeVoice", 0, 0.22, \
        giViolinA, 1, 195.997717990875, 1, 0.66, 0.72
    event_i "i", "StrangeProbe", 0.200, 0.001, giViolinA, 1, 1
  endif
endin

</CsInstruments>
<CsScore>
i "ScheduleTest" 0 0.001
e
</CsScore>
</CsoundSynthesizer>
