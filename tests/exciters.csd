<CsoundSynthesizer>
<CsOptions>
-n -d -m128
</CsOptions>
<CsInstruments>

#ifndef TEST_CASE
#define TEST_CASE #1#
#endif
#ifndef TEST_MODE
#define TEST_MODE #5#
#endif
#ifndef TEST_SPEED
#define TEST_SPEED #0.7#
#endif
#ifndef TEST_FORCE
#define TEST_FORCE #0.64#
#endif
#ifndef TEST_POSITION
#define TEST_POSITION #0.25#
#endif
#ifndef TEST_TRIGGER
#define TEST_TRIGGER #1#
#endif
#ifndef TEST_SPLIT
#define TEST_SPLIT #0#
#endif
#ifndef TEST_SPLIT_TIME
#define TEST_SPLIT_TIME #0.016125#
#endif
#ifndef TEST_FAULT
#define TEST_FAULT #1#
#endif
#ifndef TEST_END
#define TEST_END #0.112#
#endif
#ifndef TEST_NOTE_OFF
#define TEST_NOTE_OFF #0.12#
#endif
#ifndef TEST_ATTACK_FREQUENCY
#define TEST_ATTACK_FREQUENCY #440#
#endif
#ifndef TEST_RELEASE_FREQUENCY
#define TEST_RELEASE_FREQUENCY #440#
#endif
#ifndef TEST_RELEASE_FREQUENCY_2
#define TEST_RELEASE_FREQUENCY_2 #440#
#endif
#ifndef TEST_RELEASE_CHANGE
#define TEST_RELEASE_CHANGE #0#
#endif
#ifndef TEST_RELEASE_MODE
#define TEST_RELEASE_MODE #-1#
#endif
#ifndef TEST_RELEASE_SPEED
#define TEST_RELEASE_SPEED #2#
#endif

sr = 48000
ksmps = 32
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

instr GateVoice
  kTime timeinsts
  kTrigger = 1
  if kTime >= 0.008 && kTime < 0.016 then
    kTrigger = 0.55
  elseif kTime >= 0.016 && kTime < 0.032 then
    kTrigger = 0
  endif

  aLeft, aRight hlolli_wg_violin \
      kTrigger, 440, 0.64, 0.72, 0.20, \
      0, 0, 5, 0, 0, 3, giViolinA
  outs aLeft, aRight
endin

instr HeldModeChangeVoice
  kTime timeinsts
  kArticulation = 5
  if kTime >= 0.016 then
    kArticulation = 7
  elseif kTime >= 0.008 then
    kArticulation = 6
  endif

  aLeft, aRight hlolli_wg_violin \
      1, 440, 0.64, 0.72, 0.20, \
      0, 0, kArticulation, 0, 0, 3, giViolinA
  outs aLeft, aRight
endin

instr Renderer
  aLeft, aRight hlolli_wg_violin_resonance \
      p4, 0.72, 0.55, 0
  outs aLeft, aRight
endin

instr ExciterProbe
  iArticulation, iMode, iArmed, iActive, iAge, iTotalSamples, \
      iPulseSamples, iNotchDelay, iPosition, iContactTarget, \
      iContact, iSpeedTarget, iSpeed, iLastOutput, iEnergy, iPeak, \
      iRng, iPendingImpact, iNormalPizzicatoAttacks, \
      iLeftHandPizzicatoAttacks, iBartokPizzicatoAttacks, \
      iFingerboardImpacts, iWoodStrikes, iWoodTrattoAttacks, \
      iWoodTrattoSamples, iCollisionSamples, iCollisionCompression, \
      iCollisionForce, iExciterSamples, iRecoveries, iFinite \
      hlolli_wg_violin_test_exciter p4, p5
  printf_i \
      "WG_EXCITER_A %d %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g\n", \
      1, p6, iArticulation, iMode, iArmed, iActive, iAge, \
      iTotalSamples, iPulseSamples, iNotchDelay, iPosition, \
      iContactTarget, iContact, iSpeedTarget, iSpeed, iLastOutput, \
      iEnergy, iPeak
  printf_i \
      "WG_EXCITER_B %d %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g\n", \
      1, p6, iRng, iPendingImpact, iNormalPizzicatoAttacks, \
      iLeftHandPizzicatoAttacks, iBartokPizzicatoAttacks, \
      iFingerboardImpacts, iWoodStrikes, iWoodTrattoAttacks, \
      iWoodTrattoSamples, iCollisionSamples, iCollisionCompression, \
      iCollisionForce, iExciterSamples, iRecoveries, iFinite
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

instr ExciterFault
  iOk hlolli_wg_violin_test_exciter_fault p4, p5, p6
  printf_i "WG_EXCITER_FAULT %d %.17g\n", 1, p7, iOk
endin

instr KeepAlive
  aSilence init 0
  outs aSilence, aSilence
endin

instr ScheduleTest
  event_i "i", "KeepAlive", 0, $TEST_END

  if $TEST_CASE == 1 then
    event_i "i", "Voice", 0, 0.08, \
        giViolinA, 3, 440, $TEST_TRIGGER, $TEST_FORCE, $TEST_SPEED, \
        $TEST_POSITION, $TEST_MODE
    event_i "i", "ExciterProbe", 0.060, 0.001, \
        giViolinA, 3, 1
    event_i "i", "WaveProbe", 0.060, 0.001, giViolinA, 3, 1
  elseif $TEST_CASE == 2 then
    event_i "i", "GateVoice", 0, 0.064
    event_i "i", "ExciterProbe", 0.012, 0.001, \
        giViolinA, 3, 1
    event_i "i", "ExciterProbe", 0.028, 0.001, \
        giViolinA, 3, 2
    event_i "i", "ExciterProbe", 0.052, 0.001, \
        giViolinA, 3, 3
    event_i "i", "WaveProbe", 0.052, 0.001, giViolinA, 3, 3
  elseif $TEST_CASE == 3 then
    event_i "i", "Renderer", 0, 0.060, giViolinA
    if $TEST_SPLIT == 0 then
      event_i "i", "Voice", 0, 0.056, \
          giViolinA, 3, 440, 1, 0.58, $TEST_SPEED, \
          $TEST_POSITION, $TEST_MODE
    else
      event_i "i", "Voice", 0, $TEST_SPLIT_TIME, \
          giViolinA, 3, 440, 1, 0.58, $TEST_SPEED, \
          $TEST_POSITION, $TEST_MODE
      event_i "i", "Voice", $TEST_SPLIT_TIME, \
          0.056 - $TEST_SPLIT_TIME, \
          giViolinA, 3, 440, 1, 0.58, $TEST_SPEED, \
          $TEST_POSITION, $TEST_MODE
    endif
    event_i "i", "ExciterProbe", 0.052, 0.001, \
        giViolinA, 3, 1
    event_i "i", "WaveProbe", 0.052, 0.001, giViolinA, 3, 1
  elseif $TEST_CASE == 4 then
    event_i "i", "Renderer", 0, 0.100, giViolinA
    event_i "i", "Voice", 0, 0.056, \
        giViolinA, 1, 247, 1, 0.50, 0.67, 0.20, 5
    event_i "i", "Voice", 0, 0.056, \
        giViolinA, 2, 370, 1, 0.57, -0.62, 0.18, 6
    event_i "i", "Voice", 0, 0.056, \
        giViolinA, 3, 554, 1, 0.66, 0.73, 0.14, 7
    event_i "i", "Voice", 0, 0.056, \
        giViolinA, 4, 740, 1, 0.43, -0.55, 0.11, 8
    iString = 1
    while iString <= 4 do
      event_i "i", "ExciterProbe", 0.052, 0.001, \
          giViolinA, iString, iString
      event_i "i", "WaveProbe", 0.052, 0.001, \
          giViolinA, iString, iString
      event_i "i", "StringProbe", 0.065, 0.001, \
          giViolinA, iString, iString
      iString += 1
    od
    event_i "i", "BodyProbe", 0.094, 0.001, giViolinA, 1
  elseif $TEST_CASE == 5 then
    event_i "i", "Voice", 0, 0.056, \
        giViolinA, 3, 440, $TEST_TRIGGER, $TEST_FORCE, $TEST_SPEED, 0.20, \
        $TEST_MODE
    event_i "i", "ExciterProbe", 0.052, 0.001, \
        giViolinA, 3, 1
    event_i "i", "WaveProbe", 0.052, 0.001, giViolinA, 3, 1
  elseif $TEST_CASE == 6 then
    iMode = 5
    if $TEST_FAULT == 2 then
      iMode = 7
    elseif $TEST_FAULT == 3 then
      iMode = 8
    endif
    event_i "i", "Voice", 0, 0.064, \
        giViolinA, 3, 440, 1, 0.64, 0.70, 0.20, iMode
    event_i "i", "ExciterFault", 0.012, 0.001, \
        giViolinA, 3, $TEST_FAULT, 1
    event_i "i", "ExciterProbe", 0.044, 0.001, \
        giViolinA, 3, 1
    event_i "i", "WaveProbe", 0.044, 0.001, giViolinA, 3, 1
  elseif $TEST_CASE == 7 then
    ; Handle B must not change when handle A runs a separate exciter.
    event_i "i", "Voice", 0, 0.056, \
        giViolinB, 2, 370, 1, 0.57, -0.62, 0.18, 6
    if $TEST_TRIGGER != 0 then
      event_i "i", "Voice", 0, 0.056, \
          giViolinA, 1, 247, 1, 0.70, 0.74, 0.21, 7
    endif
    event_i "i", "ExciterProbe", 0.052, 0.001, \
        giViolinB, 2, 1
    event_i "i", "WaveProbe", 0.052, 0.001, giViolinB, 2, 1
  elseif $TEST_CASE == 8 then
    ; Keep a zero-gate controller after note-off so the dry tail and rail
    ; damper advance for the full set of release snapshots.
    iTail = $TEST_END - $TEST_NOTE_OFF
    iReleaseMode = $TEST_MODE
    iReleaseSpeed = $TEST_SPEED
    if $TEST_RELEASE_MODE >= 0 then
      iReleaseMode = $TEST_RELEASE_MODE
    endif
    if $TEST_RELEASE_SPEED <= 1 then
      iReleaseSpeed = $TEST_RELEASE_SPEED
    endif
    event_i "i", "Voice", 0, $TEST_NOTE_OFF, \
        giViolinA, 3, $TEST_ATTACK_FREQUENCY, 1, $TEST_FORCE, $TEST_SPEED, \
        $TEST_POSITION, $TEST_MODE
    if $TEST_RELEASE_CHANGE > $TEST_NOTE_OFF && \
          $TEST_RELEASE_CHANGE < $TEST_END then
      event_i "i", "Voice", $TEST_NOTE_OFF, \
          $TEST_RELEASE_CHANGE - $TEST_NOTE_OFF, \
          giViolinA, 3, $TEST_RELEASE_FREQUENCY, 0, $TEST_FORCE, \
          iReleaseSpeed, $TEST_POSITION, iReleaseMode
      event_i "i", "Voice", $TEST_RELEASE_CHANGE, \
          $TEST_END - $TEST_RELEASE_CHANGE, \
          giViolinA, 3, $TEST_RELEASE_FREQUENCY_2, 0, $TEST_FORCE, \
          iReleaseSpeed, $TEST_POSITION, iReleaseMode
    else
      event_i "i", "Voice", $TEST_NOTE_OFF, iTail, \
          giViolinA, 3, $TEST_RELEASE_FREQUENCY, 0, $TEST_FORCE, \
          iReleaseSpeed, $TEST_POSITION, iReleaseMode
    endif
    event_i "i", "WaveProbe", $TEST_NOTE_OFF - 0.001, 0.001, \
        giViolinA, 3, 1
    event_i "i", "WaveProbe", $TEST_NOTE_OFF + 0.050, 0.001, \
        giViolinA, 3, 2
    event_i "i", "WaveProbe", $TEST_NOTE_OFF + 0.100, 0.001, \
        giViolinA, 3, 3
    event_i "i", "WaveProbe", $TEST_NOTE_OFF + 0.250, 0.001, \
        giViolinA, 3, 4
    event_i "i", "WaveProbe", $TEST_NOTE_OFF + 0.500, 0.001, \
        giViolinA, 3, 5
    event_i "i", "ExciterProbe", $TEST_NOTE_OFF + 0.500, 0.001, \
        giViolinA, 3, 1
  elseif $TEST_CASE == 9 then
    ; End the gate while the one-shot pulse is still live. The zero-gate
    ; owner must finish the stored transient, then damp the rails.
    iTail = $TEST_END - $TEST_NOTE_OFF
    event_i "i", "Voice", 0, $TEST_NOTE_OFF, \
        giViolinA, 3, 440, 1, $TEST_FORCE, $TEST_SPEED, \
        $TEST_POSITION, $TEST_MODE
    event_i "i", "Voice", $TEST_NOTE_OFF, iTail, \
        giViolinA, 3, 440, 0, $TEST_FORCE, $TEST_SPEED, \
        $TEST_POSITION, $TEST_MODE
    event_i "i", "ExciterProbe", 0.00068, 0.00001, \
        giViolinA, 3, 1
    event_i "i", "ExciterProbe", 0.003, 0.00001, \
        giViolinA, 3, 2
    event_i "i", "WaveProbe", 0.003, 0.00001, giViolinA, 3, 1
    event_i "i", "WaveProbe", 0.050, 0.00001, giViolinA, 3, 2
    event_i "i", "WaveProbe", 0.150, 0.00001, giViolinA, 3, 3
    event_i "i", "WaveProbe", 0.350, 0.00001, giViolinA, 3, 4
  elseif $TEST_CASE == 10 then
    ; A held trigger fires one attack even if its mode changes.
    event_i "i", "HeldModeChangeVoice", 0, 0.040
    event_i "i", "ExciterProbe", 0.006, 0.001, \
        giViolinA, 3, 1
    event_i "i", "ExciterProbe", 0.012, 0.001, \
        giViolinA, 3, 2
    event_i "i", "ExciterProbe", 0.020, 0.001, \
        giViolinA, 3, 3
    event_i "i", "WaveProbe", 0.020, 0.001, giViolinA, 3, 1
  endif
endin

</CsInstruments>
<CsScore>
i "ScheduleTest" 0 0.001
e
</CsScore>
</CsoundSynthesizer>
