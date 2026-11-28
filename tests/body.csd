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
#ifndef TEST_BODY
#define TEST_BODY #0.72#
#endif
#ifndef TEST_SYMPATHETIC
#define TEST_SYMPATHETIC #0#
#endif
#ifndef TEST_MUTE
#define TEST_MUTE #0#
#endif
#ifndef TEST_SPLIT
#define TEST_SPLIT #0#
#endif
#ifndef TEST_SPLIT_TIME
#define TEST_SPLIT_TIME #0.25#
#endif
#ifndef TEST_GAP
#define TEST_GAP #0#
#endif
#ifndef TEST_END
#define TEST_END #0.62#
#endif

sr = 48000
ksmps = 32
nchnls = 2
0dbfs = 1

giViolinA hlolli_wg_violin_create
giViolinB hlolli_wg_violin_create

instr Renderer
  aLeft, aRight hlolli_wg_violin_resonance \
      p4, p5, p6, p7
  outs aLeft, aRight
endin

instr QuietRenderer
  aLeft, aRight hlolli_wg_violin_resonance \
      p4, p5, p6, p7
endin

instr MovingRenderer
  kPhase phasor 0.071, 0
  kTriangle = 1 - abs(2 * kPhase - 1)
  kBody = 0.05 + 0.95 * kTriangle
  kSympathetic = 0.5 + 0.5 * \
      sin(6.283185307179586 * 0.113 * timeinsts())
  kMute = 0.5 + 0.5 * \
      sin(6.283185307179586 * 0.089 * timeinsts() + 0.7)
  aLeft, aRight hlolli_wg_violin_resonance \
      p4, kBody, kSympathetic, kMute
  outs aLeft, aRight
endin

instr StressVoice
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
  kGate phasor 1 + 0.07 * iIndex, 0
  kTrigger = (kGate < 0.75 ? 1 : 0)
  aLeft, aRight hlolli_wg_violin \
      kTrigger, kFrequency, kForce, kSpeed, kPosition, \
      0, 0, 0, 0, 0, iIndex, p4
endin

instr ReleaseVoice
  kTrigger = timeinsts() < p5 ? 1 : 0
  aLeft, aRight hlolli_wg_violin \
      kTrigger, 440, 0.58, 0.61, 0.11, \
      0, 0, 0, 0, 0, 3, p4
endin

instr BridgeImpulse
  iOk hlolli_wg_violin_test_bridge_impulse p4, p5, p6
  printf_i "WG_BODY_IMPULSE %d %.17g\n", 1, p7, iOk
endin

instr BodyFault
  iOk hlolli_wg_violin_test_body_fault p4, p5
  printf_i "WG_BODY_FAULT %d %.17g\n", 1, p6, iOk
endin

instr StringSeed
  iOk hlolli_wg_violin_test_string_impulse p4, p5, p6, p7
  printf_i "WG_BODY_SEED %d %.17g\n", 1, p8, iOk
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
      "WG_BODY_A %d %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g\n", \
      1, p5, iBody, iSympathetic, iMute, iModeCount, \
      iSendSamples1, iSendSamples2, iSendSamples3, iSendSamples4, \
      iSendEnergy1, iSendEnergy2, iSendEnergy3, iSendEnergy4, \
      iLastDrive, iDriveEnergy
  printf_i \
      "WG_BODY_B %d %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g\n", \
      1, p5, iModalEnergy, iStateSignature, iLastLeft, iLastRight, \
      iOutputEnergyLeft, iOutputEnergyRight, iPeakLeft, iPeakRight, \
      iProcessedSamples, iFastForwardSamples, iResetCount, iClipCount, \
      iFinite
endin

instr ModeProbe
  iFrequency, iBaseBandwidth, iEffectiveBandwidth, iRadius, iGain, \
      iPan, iReal, iImaginary, iFinite \
      hlolli_wg_violin_test_body_mode p4, p5
  printf_i \
      "WG_BODY_MODE %d %d %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g\n", \
      1, p6, p5, iFrequency, iBaseBandwidth, iEffectiveBandwidth, \
      iRadius, iGain, iPan, iReal, iImaginary, iFinite
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
      "WG_BODY_WAVE %d %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g\n", \
      1, p6, iCapacity, iReadDelay, iTargetDelay, iTargetFrequency, \
      iLoopPhase, iTowardNutEnergy, iTowardBridgeEnergy, \
      iTowardNutSignature, iTowardBridgeSignature, iNutPole, iNutGain, \
      iNutState, iBridgePole, iBridgeGain, iBridgeState, iWriteIndex, \
      iWaveSamples, iExcitationCount, iClearCount, iResetCount, \
      iClipCount, iBridgeDynamicInput, iBridgeDynamicOutput, \
      iLastBridgeOutput, iFinite
endin

instr KeepAlive
  aSilence init 0
  outs aSilence, aSilence
endin

instr ScheduleModes
  iMode = 1
  while iMode <= 17 do
    event_i "i", "ModeProbe", p4, 0.001, p5, iMode, p6
    iMode += 1
  od
endin

instr ScheduleTest
  event_i "i", "KeepAlive", 0, $TEST_END

  if $TEST_CASE == 1 then
    event_i "i", "Renderer", 0, 0.08, \
        giViolinA, $TEST_BODY, $TEST_SYMPATHETIC, $TEST_MUTE
    event_i "i", "BodyProbe", 0.079, 0.001, giViolinA, 1
    event_i "i", "ScheduleModes", 0.079, 0.001, 0, giViolinA, 1
  elseif $TEST_CASE == 2 then
    event_i "i", "Renderer", 0, 0.50, \
        giViolinA, $TEST_BODY, $TEST_SYMPATHETIC, $TEST_MUTE
    event_i "i", "BridgeImpulse", 0.25, 0.001, \
        giViolinA, max(1, $TEST_VARIANT), 4, 1
    event_i "i", "BodyProbe", 0.27, 0.001, giViolinA, 1
    event_i "i", "BodyProbe", 0.36, 0.001, giViolinA, 2
    event_i "i", "BodyProbe", 0.49, 0.001, giViolinA, 3
    event_i "i", "ScheduleModes", 0.36, 0.001, 0, giViolinA, 1
  elseif $TEST_CASE == 3 then
    if $TEST_SPLIT == 0 then
      event_i "i", "Renderer", 0, 0.50, \
          giViolinA, $TEST_BODY, $TEST_SYMPATHETIC, $TEST_MUTE
    else
      event_i "i", "Renderer", 0, $TEST_SPLIT_TIME, \
          giViolinA, $TEST_BODY, $TEST_SYMPATHETIC, $TEST_MUTE
      event_i "i", "Renderer", $TEST_SPLIT_TIME, \
          0.50 - $TEST_SPLIT_TIME, \
          giViolinA, $TEST_BODY, $TEST_SYMPATHETIC, $TEST_MUTE
    endif
    event_i "i", "BridgeImpulse", 0.05, 0.001, giViolinA, 2, 4, 1
    event_i "i", "BodyProbe", 0.49, 0.001, giViolinA, 1
    event_i "i", "ScheduleModes", 0.49, 0.001, 0, giViolinA, 1
  elseif $TEST_CASE == 4 then
    if $TEST_GAP == 0 then
      event_i "i", "Renderer", 0, 0.50, \
          giViolinA, $TEST_BODY, $TEST_SYMPATHETIC, $TEST_MUTE
    elseif $TEST_GAP == 1 then
      event_i "i", "Renderer", 0, 0.25, \
          giViolinA, $TEST_BODY, $TEST_SYMPATHETIC, $TEST_MUTE
      event_i "i", "Renderer", 0.266, 0.234, \
          giViolinA, $TEST_BODY, $TEST_SYMPATHETIC, $TEST_MUTE
    else
      event_i "i", "Renderer", 0, 0.25, \
          giViolinA, $TEST_BODY, $TEST_SYMPATHETIC, $TEST_MUTE
      event_i "i", "Renderer", 0.50, 0.05, \
          giViolinA, $TEST_BODY, $TEST_SYMPATHETIC, $TEST_MUTE
    endif
    event_i "i", "BridgeImpulse", 0.22, 0.001, giViolinA, 3, 4, 1
    if $TEST_GAP < 2 then
      event_i "i", "BodyProbe", 0.501, 0.001, giViolinA, 1
      event_i "i", "ScheduleModes", 0.501, 0.001, 0, giViolinA, 1
    else
      event_i "i", "BodyProbe", 0.551, 0.001, giViolinA, 1
      event_i "i", "ScheduleModes", 0.551, 0.001, 0, giViolinA, 1
    endif
  elseif $TEST_CASE == 5 then
    event_i "i", "Renderer", 0, 0.42, \
        giViolinA, $TEST_BODY, $TEST_SYMPATHETIC, $TEST_MUTE
    if $TEST_VARIANT == 0 then
      event_i "i", "BridgeImpulse", 0.10, 0.001, giViolinA, 1, 1, 1
      event_i "i", "BridgeImpulse", 0.10, 0.001, giViolinA, 2, 2, 2
      event_i "i", "BridgeImpulse", 0.10, 0.001, giViolinA, 3, 3, 3
      event_i "i", "BridgeImpulse", 0.10, 0.001, giViolinA, 4, 4, 4
    else
      event_i "i", "BridgeImpulse", 0.10, 0.001, \
          giViolinA, $TEST_VARIANT, 4, 1
    endif
    event_i "i", "BodyProbe", 0.41, 0.001, giViolinA, 1
    event_i "i", "ScheduleModes", 0.20, 0.001, 0, giViolinA, 1
  elseif $TEST_CASE == 6 then
    event_i "i", "Renderer", 0, 0.60, \
        giViolinA, $TEST_BODY, $TEST_SYMPATHETIC, $TEST_MUTE
    event_i "i", "BridgeImpulse", 0.10, 0.001, giViolinA, 2, 4, 1
    event_i "i", "StringSeed", 0.05, 0.001, \
        giViolinA, 1, 333, 0.8, 1
    event_i "i", "BodyProbe", 0.19, 0.001, giViolinA, 1
    event_i "i", "WaveProbe", 0.19, 0.001, giViolinA, 1, 1
    event_i "i", "BodyFault", 0.20, 0.001, giViolinA, 3, 1
    event_i "i", "BodyProbe", 0.22, 0.001, giViolinA, 2
    event_i "i", "BridgeImpulse", 0.30, 0.001, giViolinA, 2, 4, 2
    event_i "i", "BodyProbe", 0.45, 0.001, giViolinA, 3
    event_i "i", "WaveProbe", 0.45, 0.001, giViolinA, 1, 2
    event_i "i", "ScheduleModes", 0.45, 0.001, 0, giViolinA, 1
  elseif $TEST_CASE == 7 then
    event_i "i", "StressVoice", 0, 10, \
        giViolinA, 1, 195.997717990875, 0
    event_i "i", "StressVoice", 0, 10, \
        giViolinA, 2, 293.664767917408, 0.25
    event_i "i", "StressVoice", 0, 10, giViolinA, 3, 440, 0.5
    event_i "i", "StressVoice", 0, 10, \
        giViolinA, 4, 659.25511382574, 0.75
    event_i "i", "MovingRenderer", 0, 10, giViolinA
    event_i "i", "BodyProbe", 10.001, 0.001, giViolinA, 1
    event_i "i", "ScheduleModes", 10.001, 0.001, 0, giViolinA, 1
  elseif $TEST_CASE == 8 then
    event_i "i", "Renderer", 0, 0.42, \
        giViolinA, $TEST_BODY, $TEST_SYMPATHETIC, $TEST_MUTE
    event_i "i", "QuietRenderer", 0, 0.42, \
        giViolinB, $TEST_BODY, $TEST_SYMPATHETIC, $TEST_MUTE
    event_i "i", "BridgeImpulse", 0.10, 0.001, giViolinA, 1, 4, 1
    event_i "i", "BodyProbe", 0.41, 0.001, giViolinA, 1
    event_i "i", "BodyProbe", 0.41, 0.001, giViolinB, 2
    event_i "i", "ScheduleModes", 0.20, 0.001, 0, giViolinB, 2
  elseif $TEST_CASE == 9 then
    event_i "i", "Renderer", 0, 0.50, \
        giViolinA, $TEST_BODY, $TEST_SYMPATHETIC, $TEST_MUTE
    event_i "i", "ReleaseVoice", 0, 0.50, giViolinA, 0.08
    event_i "i", "BodyProbe", 0.09, 0.001, giViolinA, 1
    event_i "i", "BodyProbe", 0.20, 0.001, giViolinA, 2
    event_i "i", "BodyProbe", 0.49, 0.001, giViolinA, 3
  endif
endin

</CsInstruments>
<CsScore>
i "ScheduleTest" 0 0.001
e
</CsScore>
</CsoundSynthesizer>
