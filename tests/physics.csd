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
#ifndef TEST_FAULT
#define TEST_FAULT #1#
#endif
#ifndef TEST_SYMPATHETIC
#define TEST_SYMPATHETIC #0#
#endif
#ifndef TEST_KSMPS
#define TEST_KSMPS #32#
#endif

sr = 48000
ksmps = $TEST_KSMPS
nchnls = 2
0dbfs = 1

giViolinA hlolli_wg_violin_create
giViolinB hlolli_wg_violin_create

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

instr HistoryVoice
  kTime timeinsts
  kSpeed = $TEST_VARIANT == 0 ? 0.68 : -0.68
  if kTime >= 0.18 then
    kSpeed = 0.26
  endif
  aLeft, aRight hlolli_wg_violin \
      1, 440, 0.56, kSpeed, 0.12, \
      0, 0, 0, 0, 0, 3, p4
  outs aLeft, aRight
endin

instr ThermalVoice
  kTime timeinsts
  kTrigger = kTime < 0.62 ? 1 : 0
  aLeft, aRight hlolli_wg_violin \
      kTrigger, 440, 0.72, 0.78, 0.10, \
      0, 0, 0, 0, 0, 3, p4
  outs aLeft, aRight
endin

instr HairVoice
  kTime timeinsts
  kSpeed = 0.18
  if kTime >= 0.16 && kTime < 0.32 then
    kSpeed = 0.88
  elseif kTime >= 0.32 then
    kSpeed = -0.64
  endif
  aLeft, aRight hlolli_wg_violin \
      1, 440, 0.54, kSpeed, 0.12, \
      0, 0, 0, 0, 0, 3, p4
  outs aLeft, aRight
endin

instr MechanicalVoice
  iTrigger = 1
  iForce = 1
  iSpeed = 0.92
  iFrequency = 880
  if $TEST_VARIANT == 1 then
    iTrigger = 0
    iFrequency = 440
  elseif $TEST_VARIANT == 2 then
    iForce = 0
    iFrequency = 440
  elseif $TEST_VARIANT == 3 then
    iSpeed = 0
    iFrequency = 440
  elseif $TEST_VARIANT == 4 then
    iFrequency = 440
    iForce = 0.48
    iSpeed = 0.58
  endif
  aLeft, aRight hlolli_wg_violin \
      iTrigger, iFrequency, iForce, iSpeed, 0.18, \
      0, 0, 0, 0, 0, 3, p4
  outs aLeft, aRight
endin

instr StressVoice
  iIndex = p5
  kPhase phasor 0.41 + 0.023 * iIndex, 0.17 * iIndex
  kTriangle = 1 - abs(2 * kPhase - 1)
  kGatePhase phasor 1 + 0.07 * iIndex, 0
  kTrigger = kGatePhase < 0.75 ? 1 : 0
  kForce = 0.3 + 0.2 * \
      sin(6.283185307179586 * (0.31 + 0.017 * iIndex) * timeinsts())
  kSpeed = 0.5 * \
      sin(6.283185307179586 * (0.43 + 0.019 * iIndex) * timeinsts())
  kPosition = 0.12 + 0.08 * \
      sin(6.283185307179586 * (0.19 + 0.013 * iIndex) * timeinsts())
  kFrequency = p6 * exp(0.5 * log(2) * kTriangle)

  aLeft, aRight hlolli_wg_violin \
      kTrigger, kFrequency, kForce, kSpeed, kPosition, \
      10 * kTriangle, 4.2 + 1.8 * kTriangle, \
      0, 0, 0, p5, p4
  outs aLeft, aRight
endin

instr Renderer
  aLeft, aRight hlolli_wg_violin_resonance \
      p4, 0.72, $TEST_SYMPATHETIC, 0.12
  outs aLeft, aRight
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
      "WG_PHYSICS_A %d %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g\n", \
      1, p6, iContactMemory, iContactMemoryVelocity, iContactAdhesion, \
      iContactSteadyDisplacement, iContactForce, iContactIterations, \
      iContactFailures, iTemperature, iThermalScale, iThermalWork, \
      iHairDisplacement, iHairVelocity, iHairEffectiveSpeed, \
      iBoardDisplacement, iBoardCompression, iBoardForce
  printf_i \
      "WG_PHYSICS_B %d %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g\n", \
      1, p6, iBoardEnergy, iBoardImpacts, iNoiseLast, iNoiseEnergy, \
      iNoisePeak, iNoiseSamples, iMechanicalEvents, iCouplingInput, \
      iCouplingEnergy, iCouplingPeak, iCouplingSamples, \
      iCouplingSourceMask, iRecoveries, iSecondPolarization, iFinite
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
      "WG_PHYSICS_WAVE %d %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g\n", \
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
      "WG_PHYSICS_STRING %d %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g\n", \
      1, p6, iPhase, iVibratoPhase, iFrequency, iTrigger, iForce, \
      iSpeed, iActivity, iLastSample, iGapSamples, iOwner, iSuccessor
endin

instr PhysicsFault
  iOk hlolli_wg_violin_test_physics_fault p4, p5, p6
  printf_i "WG_PHYSICS_FAULT %d %.17g\n", 1, p7, iOk
endin

instr BowFault
  iOk hlolli_wg_violin_test_bow_fault p4, p5, p6
  printf_i "WG_PHYSICS_BOW_FAULT %d %.17g\n", 1, p7, iOk
endin

instr ProbeOne
  event_i "i", "PhysicsProbe", 0, 0.001, p4, p5, p6
  event_i "i", "WaveProbe", 0, 0.001, p4, p5, p6
  event_i "i", "StringProbe", 0, 0.001, p4, p5, p6
endin

instr KeepAlive
  aSilence init 0
  outs aSilence, aSilence
endin

instr ScheduleTest
  event_i "i", "KeepAlive", 0, $TEST_END

  if $TEST_CASE == 1 then
    ; Opposite bow histories reach the same live controls after 180 ms.
    event_i "i", "HistoryVoice", 0, 0.46, giViolinA
    event_i "i", "ProbeOne", 0.170, 0.001, giViolinA, 3, 1
    event_i "i", "ProbeOne", 0.181, 0.001, giViolinA, 3, 2
    event_i "i", "ProbeOne", 0.195, 0.001, giViolinA, 3, 3
    event_i "i", "ProbeOne", 0.420, 0.001, giViolinA, 3, 4
  elseif $TEST_CASE == 2 then
    ; Sliding heats the small work state; a released hold lets it cool.
    event_i "i", "ThermalVoice", 0, 1.20, giViolinA
    event_i "i", "ProbeOne", 0.020, 0.001, giViolinA, 3, 1
    event_i "i", "ProbeOne", 0.300, 0.001, giViolinA, 3, 2
    event_i "i", "ProbeOne", 0.600, 0.001, giViolinA, 3, 3
    event_i "i", "ProbeOne", 0.820, 0.001, giViolinA, 3, 4
    event_i "i", "ProbeOne", 1.150, 0.001, giViolinA, 3, 5
  elseif $TEST_CASE == 3 then
    ; A speed step and reversal exercise hair lag and stored contact.
    event_i "i", "HairVoice", 0, 0.52, giViolinA
    event_i "i", "ProbeOne", 0.150, 0.001, giViolinA, 3, 1
    event_i "i", "ProbeOne", 0.161, 0.001, giViolinA, 3, 2
    event_i "i", "ProbeOne", 0.180, 0.001, giViolinA, 3, 3
    event_i "i", "ProbeOne", 0.300, 0.001, giViolinA, 3, 4
    event_i "i", "ProbeOne", 0.321, 0.001, giViolinA, 3, 5
    event_i "i", "ProbeOne", 0.380, 0.001, giViolinA, 3, 6
    event_i "i", "ProbeOne", 0.500, 0.001, giViolinA, 3, 7
  elseif $TEST_CASE == 4 then
    ; Strong stopped bow, three silent controls, or an open-string control.
    event_i "i", "MechanicalVoice", 0, 0.62, giViolinA
    event_i "i", "ProbeOne", 0.060, 0.001, giViolinA, 3, 2
    event_i "i", "ProbeOne", 0.580, 0.001, giViolinA, 3, 1
  elseif $TEST_CASE == 5 then
    ; A stopped G drives an open D on the same handle, never another handle.
    iTargetHandle = $TEST_VARIANT == 0 ? giViolinA : giViolinB
    event_i "i", "Voice", 0, 0.58, \
        giViolinA, 1, 293.664767917408, 1, 0.62, 0.64, 0.10, 0
    event_i "i", "Voice", 0, 0.58, \
        iTargetHandle, 2, 293.664767917408, 1, 0, 0, 0.12, 0
    event_i "i", "Renderer", 0, 0.62, giViolinA
    event_i "i", "ProbeOne", 0.540, 0.001, iTargetHandle, 2, 1
    event_i "i", "ProbeOne", 0.540, 0.001, giViolinA, 1, 2
  elseif $TEST_CASE == 6 then
    ; Exact arco handoff, at a block edge or within one block.
    if $TEST_SPLIT == 0 then
      event_i "i", "Voice", 0, 0.056, \
          giViolinA, 3, 440, 1, 0.56, 0.62, 0.12, 0
    else
      event_i "i", "Voice", 0, $TEST_SPLIT_TIME, \
          giViolinA, 3, 440, 1, 0.56, 0.62, 0.12, 0
      event_i "i", "Voice", $TEST_SPLIT_TIME, \
          0.056 - $TEST_SPLIT_TIME, \
          giViolinA, 3, 440, 1, 0.56, 0.62, 0.12, 0
    endif
    event_i "i", "ProbeOne", 0.052, 0.001, giViolinA, 3, 1
  elseif $TEST_CASE == 7 then
    ; A real four-millisecond owner gap advances and keeps the stored rail.
    event_i "i", "Voice", 0, 0.016, \
        giViolinA, 3, 440, 1, 0.56, 0.62, 0.12, 0
    event_i "i", "ProbeOne", 0.018, 0.001, giViolinA, 3, 1
    event_i "i", "Voice", 0.020, 0.036, \
        giViolinA, 3, 440, 1, 0.56, 0.62, 0.12, 0
    event_i "i", "ProbeOne", 0.052, 0.001, giViolinA, 3, 2
  elseif $TEST_CASE == 8 then
    ; One active target also receives bridge return while a bad field lands.
    event_i "i", "Voice", 0, 0.44, \
        giViolinA, 1, 293.664767917408, 1, 0.56, 0.62, 0.10, 0
    event_i "i", "Voice", 0, 0.44, \
        giViolinA, 3, 880, 1, 0.82, 0.72, 0.16, 0
    event_i "i", "ProbeOne", 0.198, 0.001, giViolinA, 3, 1
    event_i "i", "PhysicsFault", 0.200, 0.001, \
        giViolinA, 3, $TEST_FAULT, 1
    event_i "i", "ProbeOne", 0.204, 0.001, giViolinA, 3, 2
    event_i "i", "ProbeOne", 0.360, 0.001, giViolinA, 3, 3
  elseif $TEST_CASE == 9 then
    ; Four strings sweep force, speed, point, gate, and stopped pitch.
    event_i "i", "StressVoice", 0, 6, \
        giViolinA, 1, 195.997717990875
    event_i "i", "StressVoice", 0, 6, \
        giViolinA, 2, 293.664767917408
    event_i "i", "StressVoice", 0, 6, \
        giViolinA, 3, 440
    event_i "i", "StressVoice", 0, 6, \
        giViolinA, 4, 659.255113825740
    event_i "i", "Renderer", 0, 6.04, giViolinA
    event_i "i", "ProbeOne", 6.001, 0.001, giViolinA, 1, 1
    event_i "i", "ProbeOne", 6.001, 0.001, giViolinA, 2, 2
    event_i "i", "ProbeOne", 6.001, 0.001, giViolinA, 3, 3
    event_i "i", "ProbeOne", 6.001, 0.001, giViolinA, 4, 4
  elseif $TEST_CASE == 10 then
    ; Skip a medium owner gap after heating a stopped, coupled string.
    event_i "i", "Voice", 0, 0.30, \
        giViolinA, 1, 293.664767917408, 1, 0.62, 0.64, 0.10, 0
    event_i "i", "MechanicalVoice", 0, 0.30, giViolinA
    event_i "i", "ProbeOne", 0.280, 0.001, giViolinA, 3, 1
    event_i "i", "Voice", 0.800, 0.016, \
        giViolinA, 3, 880, 0, 0, 0, 0.18, 0
    event_i "i", "ProbeOne", 0.812, 0.001, giViolinA, 3, 2
    event_i "i", "MechanicalVoice", 0.816, 0.12, giViolinA
    event_i "i", "ProbeOne", 0.900, 0.001, giViolinA, 3, 3
  elseif $TEST_CASE == 11 then
    ; Probe the first processed sample after an invalid bow state lands.
    iFaultTime = 0.250
    iSampleTime = 1 / sr
    event_i "i", "Voice", 0, 0.60, \
        giViolinA, 3, 440, 1, 0.56, 0.62, 0.12, 0
    event_i "i", "ProbeOne", 0.200, 0.001, giViolinA, 3, 1
    event_i "i", "BowFault", iFaultTime, 0.001, giViolinA, 3, 3, 1
    event_i "i", "ProbeOne", iFaultTime + iSampleTime, \
        0.001, giViolinA, 3, 2
    event_i "i", "ProbeOne", 0.350, 0.001, giViolinA, 3, 3
  endif
endin

</CsInstruments>
<CsScore>
i "ScheduleTest" 0 0.001
e
</CsScore>
</CsoundSynthesizer>
