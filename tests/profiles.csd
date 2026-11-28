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
#ifndef TEST_SR
#define TEST_SR #48000#
#endif
#ifndef TEST_KSMPS
#define TEST_KSMPS #32#
#endif
#ifndef TEST_PROFILE
#define TEST_PROFILE #generic_violin#
#endif
#ifndef TEST_BAD_PROFILE
#define TEST_BAD_PROFILE #missing_violin#
#endif
#ifndef TEST_END
#define TEST_END #0.54#
#endif
#ifndef TEST_REFERENCE_PITCH
#define TEST_REFERENCE_PITCH #440#
#endif

sr = $TEST_SR
ksmps = $TEST_KSMPS
nchnls = 2
0dbfs = 1

#ifdef TEST_INVALID
giViolinA init 0
giViolinB init 0
#else
#ifdef TEST_DUAL
giViolinA hlolli_wg_violin_create "generic_violin"
giViolinB hlolli_wg_violin_create "generic_violin"
#else
#ifdef TEST_TUNED_DEFAULT
giViolinA hlolli_wg_violin_create $TEST_REFERENCE_PITCH
#else
#ifdef TEST_TUNED_NAMED
giViolinA hlolli_wg_violin_create \
    "$TEST_PROFILE", $TEST_REFERENCE_PITCH
#else
#ifdef TEST_DEFAULT
giViolinA hlolli_wg_violin_create
#else
giViolinA hlolli_wg_violin_create "$TEST_PROFILE"
#endif
#endif
#endif
giViolinB init 0
#endif
#endif

instr CreateGoodA
  giViolinA hlolli_wg_violin_create "generic_violin"
endin

instr CreateGoodB
  giViolinB hlolli_wg_violin_create "generic_violin"
endin

instr CreateBad
  iHandle hlolli_wg_violin_create "$TEST_BAD_PROFILE"
endin

instr CreateBadTuning
  iHandle hlolli_wg_violin_create \
      "generic_violin", $TEST_REFERENCE_PITCH
endin

instr Voice
  kTime timeinsts
  kTrigger = kTime < 0.30 ? 1 : 0
  kFrequency init 440
  kForce = kTrigger > 0 ? 0.58 : 0
  kSpeed = kTrigger > 0 ? 0.54 : 0
  aLeft, aRight hlolli_wg_violin \
      kTrigger, kFrequency, kForce, kSpeed, 0.115, \
      6, 5.1, 0, 0, 0, 3, p4
  outs 0.18 * aLeft, 0.18 * aRight
endin

instr Renderer
  aLeft, aRight hlolli_wg_violin_resonance \
      p4, 0.78, 0, 0
  outs aLeft, aRight
endin

instr ProfileProbe
  iIndex, iSchemaVersion, iProfileCount, iValidationCount, \
      iMuZero, iMuPointOne, iBridgeCoupling, iStaticMu, \
      iStaticMuMatchesProfile, iFinite \
      hlolli_wg_violin_test_profile p4
  printf_i \
      "WG_PROFILE %d %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g\n", \
      1, p5, iIndex, iSchemaVersion, iProfileCount, iValidationCount, \
      iMuZero, iMuPointOne, iBridgeCoupling, iStaticMu, \
      iStaticMuMatchesProfile, iFinite
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
      "WG_PROFILE_BODY %d %.17g %.17g %.17g %.17g %.17g\n", \
      1, p5, iModalEnergy, iOutputEnergyLeft, iOutputEnergyRight, \
      iProcessedSamples, iFinite
endin

instr ModeProbe
  iFrequency, iBaseBandwidth, iEffectiveBandwidth, iRadius, iGain, \
      iPan, iReal, iImaginary, iFinite \
      hlolli_wg_violin_test_body_mode p4, p5
  printf_i \
      "WG_PROFILE_MODE %d %d %.17g %.17g %.17g %.17g %.17g\n", \
      1, p6, p5, iFrequency, iBaseBandwidth, iGain, iPan, iFinite
endin

instr HandleProbe
  printf_i "WG_PROFILE_HANDLES %.17g %.17g\n", \
      1, giViolinA, giViolinB
  event_i "i", "ProfileProbe", 0, 0.001, giViolinA, 1
  event_i "i", "ProfileProbe", 0, 0.001, giViolinB, 2
endin

instr TuningProbe
  iOpenFrequency, iTargetPosition, iPosition, iTargetPressure, \
      iPressure, iVelocity, iDelayVelocity, iEffectiveFrequency, \
      iLastNoise, iNoiseEnergy, iNoisePeak, iNoiseState, iArrivals, \
      iReleases, iShifts, iMovementSamples, iNoiseSamples, iFinite \
      hlolli_wg_violin_test_finger p4, p5
  printf_i "WG_PROFILE_TUNING %d %.17g %.17g\n", \
      1, p5, iOpenFrequency, iFinite
endin

instr OwnerProbe
  iPhase, iVibratoPhase, iFrequency, iTrigger, iForce, iSpeed, \
      iActivity, iLastSample, iGapSamples, iOwner, iSuccessor \
      hlolli_wg_violin_test_string p4, p5
  printf_i "WG_PROFILE_OWNER %d %.17g\n", 1, p5, iOwner
endin

instr TuningVoice
  aLeft, aRight hlolli_wg_violin \
      1, p5, 0.52, 0.50, 0.12, \
      0, 0, 0, p6, 0, 0, p4
  outs 0.18 * aLeft, 0.18 * aRight
endin

instr KeepAlive
  aSilence init 0
  outs aSilence, aSilence
endin

instr ScheduleModes
  iMode = 1
  while iMode <= 17 do
    event_i "i", "ModeProbe", 0, 0.001, p4, iMode, p5
    iMode += 1
  od
endin

instr ScheduleTest
  event_i "i", "KeepAlive", 0, $TEST_END
  if $TEST_CASE == 1 then
    event_i "i", "Voice", 0.01, 0.45, giViolinA
    event_i "i", "Renderer", 0.01, 0.45, giViolinA
    event_i "i", "ProfileProbe", 0.445, 0.001, giViolinA, 1
    event_i "i", "BodyProbe", 0.445, 0.001, giViolinA, 1
    event_i "i", "ScheduleModes", 0.445, 0.001, giViolinA, 1
  elseif $TEST_CASE == 2 then
    iDriven = $TEST_VARIANT == 0 ? giViolinA : giViolinB
    event_i "i", "Voice", 0.01, 0.40, iDriven
    event_i "i", "Renderer", 0.01, 0.42, giViolinA
    event_i "i", "Renderer", 0.01, 0.42, giViolinB
    event_i "i", "ProfileProbe", 0.405, 0.001, giViolinA, 1
    event_i "i", "ProfileProbe", 0.405, 0.001, giViolinB, 2
    event_i "i", "BodyProbe", 0.405, 0.001, giViolinA, 1
    event_i "i", "BodyProbe", 0.405, 0.001, giViolinB, 2
    event_i "i", "ScheduleModes", 0.405, 0.001, giViolinA, 1
    event_i "i", "ScheduleModes", 0.405, 0.001, giViolinB, 2
  elseif $TEST_CASE == 3 then
    event_i "i", "CreateGoodA", 0, 0.001
    event_i "i", "CreateBad", 0.01, 0.001
    event_i "i", "CreateGoodB", 0.02, 0.001
    event_i "i", "HandleProbe", 0.03, 0.001
  elseif $TEST_CASE == 4 then
    iString = 1
    while iString <= 4 do
      event_i "i", "TuningProbe", 0, 0.001, giViolinA, iString
      iString += 1
    od
    iHarmonic = $TEST_VARIANT == 0 ? 0 : 2
    iFrequency = $TEST_REFERENCE_PITCH * ($TEST_VARIANT == 0 ? 1 : 2)
    event_i "i", "TuningVoice", 0.01, 0.12, \
        giViolinA, iFrequency, iHarmonic
    iString = 1
    while iString <= 4 do
      event_i "i", "OwnerProbe", 0.08, 0.001, giViolinA, iString
      iString += 1
    od
  elseif $TEST_CASE == 5 then
    event_i "i", "CreateGoodA", 0, 0.001
    event_i "i", "CreateBadTuning", 0.01, 0.001
    event_i "i", "CreateGoodB", 0.02, 0.001
    event_i "i", "HandleProbe", 0.03, 0.001
  endif
endin

</CsInstruments>
<CsScore>
i "ScheduleTest" 0 0.001
e $TEST_END
</CsScore>
</CsoundSynthesizer>
