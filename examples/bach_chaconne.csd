<CsoundSynthesizer>
<CsOptions>
-d -m128
</CsOptions>
<CsInstruments>

#ifndef MODEL_LEVEL
#define MODEL_LEVEL #0.88#
#endif
#ifndef DIRECT_LEVEL
#define DIRECT_LEVEL #0.50#
#endif
#ifndef BODY_LEVEL
#define BODY_LEVEL #0.92#
#endif
#ifndef SYMPATHETIC_LEVEL
#define SYMPATHETIC_LEVEL #0.46#
#endif
#ifndef ROOM_LEVEL
#define ROOM_LEVEL #0.075#
#endif
#ifndef SHOW_MARKS
#define SHOW_MARKS #1#
#endif
#ifndef SHOW_BARS
#define SHOW_BARS #1#
#endif
#ifndef VIOLIN_REFERENCE_PITCH
#define VIOLIN_REFERENCE_PITCH #440#
#endif
#ifndef VIBRATO_LEVEL
#define VIBRATO_LEVEL #1#
#endif
#ifndef VIOLIN_DISTANCE_METERS
#define VIOLIN_DISTANCE_METERS #2.5#
#endif
#ifndef INFINITE_BOW
#define INFINITE_BOW #1#
#endif

sr = 48000
ksmps = 32
nchnls = 2
0dbfs = 1

#include "violin_distance.inc"

giSine ftgen 0, 0, 16384, 10, 1
giReferenceRatio = $VIOLIN_REFERENCE_PITCH / 440
giViolin hlolli_wg_violin_create $VIOLIN_REFERENCE_PITCH
giOpenFrequency[] fillarray 0, \
    195.99771799087463 * giReferenceRatio, \
    293.6647679174076 * giReferenceRatio, \
    440 * giReferenceRatio, 659.2551138257398 * giReferenceRatio

opcode HlolBachHumanVibrato, k, kki
  kDepth, kRateTarget, iString xin
  kDepthScale rspline 0.86, 1.13, \
      2.00 + 0.08 * iString, 4.50 + 0.10 * iString
  kRateOffset rspline -0.35, 0.30, \
      1.80 + 0.06 * iString, 3.60 + 0.08 * iString
  kSecondLevel rspline 0.035, 0.085, \
      1.20 + 0.05 * iString, 2.40 + 0.07 * iString
  kDepthScale = max(0.75, min(1.22, kDepthScale))
  kRate = max(4.8, min(7.1, kRateTarget + kRateOffset))
  kSecondLevel = max(0.02, min(0.10, kSecondLevel))
  kPhase phasor kRate, frac((iString - 1) * 0.217)
  kFundamental tablei kPhase, giSine, 1
  kSecond tablei frac(2 * kPhase + 0.17), giSine, 1
  xout kDepth * kDepthScale * \
      (kFundamental + kSecondLevel * kSecond) / (1 + kSecondLevel)
endop

giTinyRoomFrames = int(0.20 * sr)
opcode TinyRoomIR, i, 0
  iIR ftgen 0, 0, -(2 * giTinyRoomFrames), -2, 0
  iN = int(0.008 * sr)
  iSeedLeft = 12457
  iSeedRight = 89173
  iBlurLeft = 0
  iBlurRight = 0
  iDampLeft = 0
  iDampRight = 0
  while iN < giTinyRoomFrames do
    iSeedLeft = (iSeedLeft * 48271) % 2147483647
    iSeedRight = (iSeedRight * 40692) % 2147483399
    iRawLeft = 2 * iSeedLeft / 2147483647 - 1
    iRawRight = 2 * iSeedRight / 2147483399 - 1
    iBlurLeft += 0.025 * (iRawLeft - iBlurLeft)
    iBlurRight += 0.025 * (iRawRight - iBlurRight)
    iDampLeft += 0.62 * (iRawLeft - iBlurLeft - iDampLeft)
    iDampRight += 0.62 * (iRawRight - iBlurRight - iDampRight)
    iAge = (iN - int(0.008 * sr)) / sr
    iGain = 0.006 * min(1, iAge / 0.008) * \
        exp(-6.907755278982137 * iAge / 0.16)
    tableiw iGain * iDampLeft, 2 * iN, iIR
    tableiw iGain * iDampRight, 2 * iN + 1, iIR
    iN += 1
  od
  tableiw 0.28, 2 * 96, iIR
  tableiw 0.17, 2 * 173, iIR
  tableiw -0.12, 2 * 271, iIR
  tableiw 0.08, 2 * 349, iIR
  tableiw 0.25, 2 * 124 + 1, iIR
  tableiw -0.15, 2 * 211 + 1, iIR
  tableiw 0.11, 2 * 296 + 1, iIR
  tableiw 0.07, 2 * 367 + 1, iIR
  xout iIR
endop
giTinyRoomIR TinyRoomIR

#include "bach_chaconne_stroke.inc"
#include "bach_chaconne_phrases.inc"
giBachBowSlope[] init lenarray(giBachBowSpan)
giBachBowBend[] init lenarray(giBachBowSpan)
#ifdef BACH_BOW_GUIDE
#includestr "$BACH_BOW_GUIDE"
#endif
gkPhrase[] init 5
giActivePhrase[] init 5
giActivePhraseEnd[] init 5

gkGestureId[] init 5
gkTrigger[] init 5
gkFrequency[] init 5
gkDynamic[] init 5
gkBowTravel[] fillarray 1, 1, 1, 1, 1
gkChordSize[] init 5
gkChordRank[] init 5
gkChordContact[] init 5
gkRolled[] init 5
gkVibratoDepth[] init 5
gkVibratoRate[] init 5
gkArticulation[] init 5
gkLegato[] init 5
gkVoice[] init 5
gkLead[] init 5
gkDottedShort[] init 5
gkBowDirection init 1
gkStrokeId init 0
gkStrokeGate init 0
gkStrokeForce init 1
gkStrokeSpeed init 1
gaAudible init 0

gaDryLeft init 0
gaDryRight init 0
gaWetLeft init 0
gaWetRight init 0
gaListenerLeft init 0
gaListenerRight init 0
gaRoomSourceLeft init 0
gaRoomSourceRight init 0
gaRoomLeft init 0
gaRoomRight init 0

instr VibratoSeed
  seed 271828
  turnoff
endin

instr BachAudible
  gaAudible += 1
endin

instr BachMark
  iSection = int(p4)
  if $SHOW_MARKS != 0 then
    if iSection == 0 then
      prints "\nCHACONNE — D minor, grave\n"
    elseif iSection == 1 then
      prints "FLOWING VARIATIONS — broader bow, growing motion\n"
    elseif iSection == 2 then
      prints "D MAJOR — soft light, restrained vibrato\n"
    elseif iSection == 3 then
      prints "D MINOR RETURNS — firm bow, rising weight\n"
    else
      prints "CODA — broadening into the final D\n"
    endif
  endif
  turnoff
endin

instr BachBar
  iBar = int(p4)
  if $SHOW_BARS != 0 then
    printf_i "BAR %d\n", 1, iBar
  endif
  turnoff
endin

instr BachStroke
  iDirection = int(p4)
  iStrokeId = int(p5)
  iChordSize = int(p6)
  kPhase line 0, p3, 1
  kContact, kForce, kSpeed \
      HlolBachStrokeShape kPhase, iChordSize

  ; Old and new stroke events can share one control block. Once a newer
  ; serial arrives, the old event must not take the shared bow back.
  if iStrokeId >= gkStrokeId then
    gkStrokeId = iStrokeId
  endif
  if gkStrokeId == iStrokeId then
    gkBowDirection = iDirection
    gkStrokeGate = kContact
    gkStrokeForce = kForce
    gkStrokeSpeed = kSpeed
  endif
endin

instr BachNote
  iMidi = int(p4)
  iString = int(p5)
  iDirection = int(p6)
  iLegato = int(p7)
  iDynamic = p8
  iVibratoDepth = p9 * $VIBRATO_LEVEL
  iVibratoRate = p10
  iGestureId = int(p11)
  iRolled = int(p12)
  iChordSize = int(p13)
  iVoice = int(p14)
  iLead = int(p15)
  iChordRank = int(p16)
  iDottedShort = int(p17)
  iPhrase = $INFINITE_BOW != 0 ? giBachPhrase[iGestureId] : 0
  iContinuation = iPhrase != 0 && giActivePhrase[iString] == iPhrase && \
      abs(giActivePhraseEnd[iString] - p2) < 0.5 / sr ? 1 : 0
  giActivePhrase[iString] = iPhrase
  giActivePhraseEnd[iString] = p2 + p3
  iJoinNext = iPhrase != 0 ? giBachJoinNext[iGestureId] : 0

  iArticulation = 1
  if iLegato != 0 then
    iArticulation = 0
  endif
  if iPhrase != 0 then
    iArticulation = 0
    iLegato = 1
  endif
  iTriggerLevel = 0.42 + 0.58 * iDynamic

  if iVibratoDepth > 0 then
    if p3 >= 0.75 then
      iDelay = min(0.42, max(0.10, p3 * 0.18))
      iRise = min(0.25, max(0.14, p3 * 0.12))
    else
      iDelay = min(0.10, max(0.045, p3 * 0.16))
      iRise = min(0.10, max(0.055, p3 * 0.10))
    endif
    iVibratoHold = max(0.001, p3 - iDelay - iRise)
    kVibratoDepth cosseg 0, iDelay, 0, iRise, iVibratoDepth, \
        iVibratoHold, iVibratoDepth
    if p3 >= 0.75 then
      iRateRise = min(0.50, max(0.20, 3 / iVibratoRate))
      iRateHold = max(0.001, p3 - iRateRise)
      kVibratoRate cosseg iVibratoRate, iRateHold, iVibratoRate, \
          iRateRise, iVibratoRate * 1.10
    else
      kVibratoRate init iVibratoRate
    endif
  else
    kVibratoDepth init 0
    kVibratoRate init 0
  endif

  if iContinuation != 0 then
    kVibratoDepth = iVibratoDepth
    kVibratoRate = iVibratoRate
  endif

  kChordContact HlolBachChordContact \
      p3, iChordSize, iChordRank, iLead
  iBowSpan = giBachBowSpan[iGestureId]
  if iPhrase == 0 && giBachPhrase[iGestureId] != 0 then
    iBowSpan = 0
  endif
  kElapsed timeinsts
  kBowTravel HlolBachBowTravel kElapsed, giBachBowElapsed[iGestureId], \
      giBachBowDuration[iBowSpan], giBachBowJoined[iBowSpan], \
      giBachBowSlope[iBowSpan], giBachBowBend[iBowSpan]

  gkGestureId[iString] = iGestureId
  ; BachStroke owns the shared bow sign. Held notes must not write an older
  ; direction after a new stroke has started.
  if gkGestureId[iString] == iGestureId then
    gkTrigger[iString] = iTriggerLevel
    ; Only phrase attacks and ends release contact for one block.
    if iPhrase != 0 && ((iContinuation == 0 && timeinstk() == 1) || \
        (iJoinNext == 0 && timeinsts() >= p3 - ksmps / sr)) then
      gkTrigger[iString] = 0
    endif
    gkPhrase[iString] = iPhrase
    gkFrequency[iString] = cpsmidinn(iMidi) * giReferenceRatio
    gkDynamic[iString] = iDynamic
    gkBowTravel[iString] = kBowTravel
    gkChordSize[iString] = iChordSize
    gkChordRank[iString] = iChordRank
    gkChordContact[iString] = kChordContact
    gkRolled[iString] = iRolled
    gkVibratoDepth[iString] = kVibratoDepth
    gkVibratoRate[iString] = kVibratoRate
    gkArticulation[iString] = iArticulation
    gkLegato[iString] = iLegato
    gkVoice[iString] = iVoice
    gkLead[iString] = iLead
    gkDottedShort[iString] = iDottedShort
  endif
  event_i "i", "BachOff", p3 + ksmps / sr, 0.001, \
      iString, iGestureId, iPhrase
endin

instr BachOff
  iString = int(p4)
  iGestureId = int(p5)
  if gkGestureId[iString] == iGestureId then
    gkTrigger[iString] = 0
    gkVibratoDepth[iString] = 0
    if $SYMPATHETIC_LEVEL > 0 && p6 == 0 && timeinstk() == 1 then
      event "i", "BachOpen", 0.16, 0.001, iString, iGestureId
    endif
  endif
endin

instr BachOpen
  iString = int(p4)
  iGestureId = int(p5)
  if gkGestureId[iString] == iGestureId && gkTrigger[iString] == 0 then
    gkFrequency[iString] = giOpenFrequency[iString]
    gkArticulation[iString] = 0
    gkLegato[iString] = 0
  endif
endin

instr StringController
  iString = int(p4)
  if gkFrequency[iString] <= 0 then
    gkFrequency[iString] = giOpenFrequency[iString]
  endif

  kBaseFrequency HlolBachPitchTransition \
      gkFrequency[iString], gkLegato[iString]
  kDepth portk gkVibratoDepth[iString], 0.060
  kRate = max(4.8, gkVibratoRate[iString])
  kCents HlolBachHumanVibrato kDepth, kRate, iString
  kFrequency = max(20, kBaseFrequency) * exp(log(2) * kCents / 1200)
  if gkTrigger[iString] == 0 && gkFrequency[iString] == giOpenFrequency[iString] then
    kFrequency = giOpenFrequency[iString]
  endif

  kDynamic = gkDynamic[iString]
  ; Preserve the written upper voice while lower voices move beneath it.
  ; Within one source voice, prefer its marked lead and then its latest note.
  kLeadString = 0
  kLeadVoice = 4
  kLeadMarked = -1
  kLeadGesture = -1
  kLeadFrequency = -1
  kScan = 1
  while kScan <= 4 do
    if gkTrigger[kScan] > 0.000001 then
      if gkVoice[kScan] < kLeadVoice then
        kLeadString = kScan
        kLeadVoice = gkVoice[kScan]
        kLeadMarked = gkLead[kScan]
        kLeadGesture = gkGestureId[kScan]
        kLeadFrequency = gkFrequency[kScan]
      elseif gkVoice[kScan] == kLeadVoice then
        if gkLead[kScan] > kLeadMarked || \
            (gkLead[kScan] == kLeadMarked && \
             gkGestureId[kScan] > kLeadGesture) || \
            (gkLead[kScan] == kLeadMarked && \
             gkGestureId[kScan] == kLeadGesture && \
             gkFrequency[kScan] > kLeadFrequency) then
          kLeadString = kScan
          kLeadMarked = gkLead[kScan]
          kLeadGesture = gkGestureId[kScan]
          kLeadFrequency = gkFrequency[kScan]
        endif
      endif
    endif
    kScan += 1
  od

  ; Keep one clear lead. Rank the other active strings by pitch so source
  ; voice numbering cannot reverse the intended balance.
  kVoiceDistance = 1
  kScan = 1
  while kScan <= 4 do
    if kScan != kLeadString && kScan != iString && \
        gkTrigger[kScan] > 0.000001 && \
        gkFrequency[kScan] > gkFrequency[iString] then
      kVoiceDistance += 1
    endif
    kScan += 1
  od
  if iString == kLeadString then
    kVoiceForce = 1.08
    kVoiceSpeed = 1.04
  elseif kVoiceDistance == 1 then
    kVoiceForce = 1.00
    kVoiceSpeed = 1.00
  elseif kVoiceDistance == 2 then
    kVoiceForce = 0.94
    kVoiceSpeed = 0.96
  else
    kVoiceForce = 0.88
    kVoiceSpeed = 0.93
  endif

  ; The shared sign and motion describe one physical bow. The sign selects
  ; direction-specific base controls. BachStroke shapes their travel. The
  ; marked lead gets more bow, while lower chord notes ring after the roll.
  kDirection = gkPhrase[iString] != 0 ? gkPhrase[iString] : gkBowDirection
  if kDirection > 0 then
    kSpeed = 0.30 + 0.48 * kDynamic
    kForce = 0.15 + 0.63 * kDynamic
    kPosition = gkStrokeId <= 187 ? 0.145 : 0.118
  else
    kSpeed = -(0.27 + 0.43 * kDynamic)
    kForce = 0.14 + 0.58 * kDynamic
    kPosition = gkStrokeId <= 187 ? 0.155 : 0.142
  endif
  kSpeed = max(-0.92, min(0.92, kSpeed * gkStrokeSpeed * kVoiceSpeed))
  kForce = max(0.10, min(0.95, kForce * gkStrokeForce * kVoiceForce))
  if gkChordSize[iString] > 1 then
    kPosition = max(0.09, kPosition - 0.008)
  endif
  if gkStrokeId <= 187 && gkDottedShort[iString] != 0 then
    kPosition = 0.142
  endif
  if gkRolled[iString] != 0 then
    kForce = min(1, kForce * 1.04)
  endif
  if gkDottedShort[iString] != 0 then
    kForce = min(1, kForce * 1.10)
    kSpeed = max(-1, min(1, kSpeed * 1.08))
  endif

  kStrokeTrigger = gkTrigger[iString] * gkStrokeGate * \
      gkChordContact[iString]

  ; Phrase motion belongs to this string, even while shared strokes advance.
  kPhraseDynamic portk kDynamic, 0.010
  if gkPhrase[iString] != 0 then
    if kDirection > 0 then
      kSpeed = 0.30 + 0.48 * kPhraseDynamic
      kForce = 0.15 + 0.63 * kPhraseDynamic
    else
      kSpeed = -(0.27 + 0.43 * kPhraseDynamic)
      kForce = 0.14 + 0.58 * kPhraseDynamic
    endif
    kSpeed *= kVoiceSpeed
    kForce *= kVoiceForce
    kStrokeTrigger = gkTrigger[iString]
  endif

  ; Keep the chord lead close to the bridge through the roll.
  if iString == kLeadString && gkChordSize[iString] >= 3 then
    kPosition = 0.11
    kSpeed *= 0.96
  endif

  ; Shortening the string moves the bow less in millimetres than a fixed ratio.
  kSpeakingLengthRatio = min(1, giOpenFrequency[iString] / max(20, kBaseFrequency))
  kPosition *= 1 + 0.35 * (1 / max(0.40, kSpeakingLengthRatio) - 1)

  kForce *= gkChordSize[iString] < 3 ? 1.05 : 1.0
  kSpeed = max(-1, min(1, kSpeed * gkBowTravel[iString]))
  kPosition *= 1 - 0.17 * (gkBowTravel[iString] - 1)
  aLeft, aRight hlolli_wg_violin \
      kStrokeTrigger, kFrequency, kForce, kSpeed, kPosition, \
      0, 0, gkArticulation[iString], 0, 0, iString, giViolin
  iDirectWeight = iString == 1 ? 0.76 : 1.0
  gaDryLeft += iDirectWeight * aLeft
  gaDryRight += iDirectWeight * aRight
endin

instr ViolinBody
  aLeft, aRight hlolli_wg_violin_resonance \
      giViolin, 0.78, $SYMPATHETIC_LEVEL, 0
  gaWetLeft += aLeft
  gaWetRight += aRight
endin

instr Listener
  aDryLeft delay gaDryLeft, ksmps / sr
  aDryRight delay gaDryRight, ksmps / sr
  aSourceLeft = $DIRECT_LEVEL * aDryLeft + $BODY_LEVEL * gaWetLeft
  aSourceRight = $DIRECT_LEVEL * aDryRight + $BODY_LEVEL * gaWetRight
  aDirectLeft, aDirectRight, aRoomLeft, aRoomRight \
      HlolViolinDistance \
      aSourceLeft, aSourceRight, $VIOLIN_DISTANCE_METERS
  gaListenerLeft += aDirectLeft
  gaListenerRight += aDirectRight
  gaRoomSourceLeft += aRoomLeft
  gaRoomSourceRight += aRoomRight
endin

instr Room
  aRoomSend = 0.5 * (gaRoomSourceLeft + gaRoomSourceRight)
  denorm aRoomSend
  aRoomLeft, aRoomRight ftconv \
      aRoomSend, giTinyRoomIR, 128, 0, giTinyRoomFrames
  gaRoomLeft += aRoomLeft
  gaRoomRight += aRoomRight
endin

instr Master
  aLeft = $MODEL_LEVEL * \
      (gaListenerLeft + $ROOM_LEVEL * gaRoomLeft)
  aRight = $MODEL_LEVEL * \
      (gaListenerRight + $ROOM_LEVEL * gaRoomRight)
  outs gaAudible * tanh(aLeft * 0.90), \
      gaAudible * tanh(aRight * 0.90)
  clear gaDryLeft, gaDryRight, gaWetLeft, gaWetRight, \
      gaListenerLeft, gaListenerRight, gaRoomSourceLeft, \
      gaRoomSourceRight, gaRoomLeft, gaRoomRight, gaAudible
endin

giStringControllerInstr nstrnum "StringController"
alwayson "VibratoSeed"
alwayson giStringControllerInstr + 0.01, 1
alwayson giStringControllerInstr + 0.02, 2
alwayson giStringControllerInstr + 0.03, 3
alwayson giStringControllerInstr + 0.04, 4
alwayson "ViolinBody"
alwayson "Listener"
alwayson "Room"
alwayson "Master"

</CsInstruments>
<CsScore>
#ifndef BACH_PERFORMANCE
#define BACH_PERFORMANCE #bach_chaconne_performance.inc#
#endif
#includestr "$BACH_PERFORMANCE"
</CsScore>
</CsoundSynthesizer>
