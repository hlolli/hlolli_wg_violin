<CsoundSynthesizer>
<CsOptions>
-d -m128
</CsOptions>
<CsInstruments>

#ifndef GUIDE_LEVEL
#define GUIDE_LEVEL #0.28#
#endif
#ifndef MODEL_LEVEL
#define MODEL_LEVEL #0.90#
#endif
#ifndef DIRECT_LEVEL
#define DIRECT_LEVEL #1.00#
#endif
#ifndef BODY_LEVEL
#define BODY_LEVEL #1.00#
#endif
#ifndef PRACTICE_HARMONICS
#define PRACTICE_HARMONICS #0#
#endif
#ifndef SYMPATHETIC_LEVEL
#define SYMPATHETIC_LEVEL #0.5#
#endif
#ifndef SHOW_MARKS
#define SHOW_MARKS #1#
#endif
#ifndef ST_NICOLAES_IR
#define ST_NICOLAES_IR #St Nicolaes Church.wav#
#endif
#ifndef REVERB_LEVEL
#define REVERB_LEVEL #0.05#
#endif

; This offline version keeps the Caprice performance map and replaces the
; guide-only algorithmic room with a full-mix convolution return.

sr = 44100
ksmps = 32
nchnls = 2
0dbfs = 1

giSine ftgen 0, 0, 16384, 10, 1

; St Nicolaes Church.wav has 352193 stereo frames at 44.1 kHz. GEN01 keeps its
; stored level. GEN52 copies its interleaved left and right channels into the
; exact table layout that ftconv expects.
giChurchSource ftgen 0, 0, 0, -1, "$ST_NICOLAES_IR", 0, 0, 0
giChurchFrames = nsamp(giChurchSource)
giChurchIR ftgen 0, 0, -(2 * giChurchFrames), -52, 2, \
    giChurchSource, 0, 2, giChurchSource, 1, 2

giViolin hlolli_wg_violin_create
giOpenFrequency[] fillarray 0, \
    195.99771799087463, 293.6647679174076, 440, 659.2551138257398

gkGestureId[] init 5
gkTrigger[] init 5
gkFrequency[] init 5
gkForce[] init 5
gkSpeed[] init 5
gkPosition[] init 5
gkVibratoDepth[] init 5
gkVibratoRate[] init 5
gkArticulation[] init 5
gkHarmonic[] init 5

; Score-time state for same-string slur links. This remains at i-rate so a
; new note can claim the string before the old note's CapriceOff event runs.
giPriorEndBeat[] init 5
giPriorSlur[] init 5
giBowDirection[] init 5

gaGuideLeft init 0
gaGuideRight init 0
gaModelDryLeft init 0
gaModelDryRight init 0
gaModelWetLeft init 0
gaModelWetRight init 0

; Variation X is monophonic. In optional practice mode, use the highest valid
; order from 4 down to 2, then put its derived fundamental on the highest
; playable string. The score pitch remains the requested sounding pitch.
opcode CapricePracticeHarmonic, ii, ii
  iMidi, iScoreString xin
  iOrder = 4
  iFundamentalMidi = iMidi - 12 * log(iOrder) / log(2)
  if iFundamentalMidi < 55 - 0.000000001 then
    iOrder = 3
    iFundamentalMidi = iMidi - 12 * log(iOrder) / log(2)
  endif
  if iFundamentalMidi < 55 - 0.000000001 then
    iOrder = 2
    iFundamentalMidi = iMidi - 12
  endif

  iString = iScoreString
  if iFundamentalMidi >= 76 - 0.000000001 then
    iString = 4
  elseif iFundamentalMidi >= 69 - 0.000000001 then
    iString = 3
  elseif iFundamentalMidi >= 62 - 0.000000001 then
    iString = 2
  elseif iFundamentalMidi >= 55 - 0.000000001 then
    iString = 1
  else
    ; Keep the fixed control-array index safe if the score data changes.
    iOrder = 0
  endif
  xout iOrder, iString
endop

instr CapriceMark
  iSection = int(p4)
  if $SHOW_MARKS != 0 then
    if iSection == 0 then
      prints "\nTEMA — quasi Presto, p\n"
    elseif iSection == 1 then
      prints "VAR. I — f, grace notes, accented staccato triplets\n"
    elseif iSection == 2 then
      prints "VAR. II — p, grace notes, open strings, short diminuendos\n"
    elseif iSection == 3 then
      prints "VAR. III — f, double stops on the third and fourth strings\n"
    elseif iSection == 4 then
      prints "VAR. IV — p, 8va, slurred chromatic runs\n"
    elseif iSection == 5 then
      prints "VAR. V — p, accented bass notes and wide slurred crossings\n"
    elseif iSection == 6 then
      prints "VAR. VI — f, double stops and 8va\n"
    elseif iSection == 7 then
      prints "VAR. VII — p, 3/4, slurred turns and accents\n"
    elseif iSection == 8 then
      prints "VAR. VIII — f, 3/4, multiple stops\n"
    elseif iSection == 9 then
      prints "VAR. IX — f, bowed notes with circled left-hand pizzicato notes\n"
    elseif iSection == 10 then
      prints "VAR. X — p, 8va; optional harmonic practice mode\n"
    elseif iSection == 11 then
      prints "VAR. XI — f, chords and fast arpeggios\n"
    elseif iSection == 12 then
      prints "FINALE — alternating p arpeggios and f chords\n"
    elseif iSection == 13 then
      prints "A-MAJOR CLOSE — p, rising tuplets, trills, ff chord\n"
    else
      prints "FINAL REST — fermata\n"
    endif
  endif
  turnoff
endin

instr CapriceNote
  iMidi = p4
  iVelocity = p5
  iString = int(p6)
  iSection = int(p7)
  iFlags = int(p8)
  iGestureId = int(p9)

  iStaccato = int(iFlags / 1) % 2
  iAccent = int(iFlags / 2) % 2
  iSlur = int(iFlags / 4) % 2
  iGrace = int(iFlags / 8) % 2
  iChord = int(iFlags / 16) % 2
  iPizzicato = int(iFlags / 32) % 2
  iTrill = int(iFlags / 64) % 2
  iHarmonicOption = int(iFlags / 256) % 2

  iHarmonic = 0
  if $PRACTICE_HARMONICS != 0 && iHarmonicOption != 0 then
    iHarmonic, iString CapricePracticeHarmonic iMidi, iString
  endif

  iStartsSlurLink = 0
  if iSlur != 0 && giPriorSlur[iString] != 0 && \
      abs(p2 - giPriorEndBeat[iString]) <= (0.5 / sr) then
    iStartsSlurLink = 1
  endif

  ; Fixed demo mapping. The score marks choose the bow preset. Force, speed,
  ; position, and the editorial tempo curve stay separate live controls.
  iDynamic = (iVelocity / 127) ^ 1.55
  iForce = min(1, 0.12 + 0.72 * iDynamic)
  if iAccent != 0 then
    iForce = min(1, iForce * 1.16)
  endif

  ; The dotted slurs in Variation I use the spiccato preset for this demo.
  ; Other same-string score slurs use direct arco so their gate stays positive.
  ; An un-slurred accent selects martelé; every other separate bowed note uses
  ; détaché. The score has no bow-tremolo mark, so it never selects code 4.
  iArticulation = 1
  if iPizzicato != 0 then
    iArticulation = 5
  elseif iSection == 1 && iStaccato != 0 then
    iArticulation = 3
  elseif iSlur != 0 then
    iArticulation = 0
  elseif iAccent != 0 then
    iArticulation = 2
  endif

  iDirection = 1
  if int(iGestureId / 4) % 2 == 0 then
    iDirection = -1
  endif
  if iStartsSlurLink != 0 && iArticulation == 0 then
    iDirection = giBowDirection[iString]
  endif
  giBowDirection[iString] = iDirection
  iSpeed = iDirection * (0.28 + 0.56 * iDynamic)
  iPosition = 0.12
  if iPizzicato != 0 then
    ; Negative pluck speed selects the left-hand release model.
    iSpeed = -0.72
    iPosition = 0.18
  endif

  iVibratoDepth = 14 + 10 * iDynamic
  if iPizzicato != 0 || iGrace != 0 || p3 < 0.18 then
    iVibratoDepth = 0
  endif
  iVibratoRate = 5.1 + 0.7 * iDynamic

  iAttack = min(0.014, max(0.001, p3 * 0.18))
  iRelease = min(0.035, max(0.001, p3 * 0.24))
  if iPizzicato != 0 then
    iAttack = min(0.002, max(0.0005, p3 * 0.08))
    iRelease = min(0.060, max(0.001, p3 * 0.48))
  endif
  iSustain = max(0.001, p3 - iAttack - iRelease)
  iGestureStart = 0
  if iStartsSlurLink != 0 && iArticulation == 0 then
    iGestureStart = 0.86
  endif
  iGestureEnd = 0
  if iSlur != 0 && iArticulation == 0 then
    iGestureEnd = 0.86
  endif
  kGesture linseg iGestureStart, iAttack, 1, \
      iSustain, 0.86, iRelease, iGestureEnd

  ; Presets get one clean k-rate gate edge. Their own force, speed, and
  ; contact paths make the onset, so the model does not stack this guide
  ; envelope on top. Direct arco keeps the score envelope for linked slurs.
  iPresetAttack = min(ksmps / sr, max(0.0001, p3 * 0.25))
  iPresetHold = max(0.001, p3 - iPresetAttack)
  kPresetGate linseg 0, iPresetAttack, 1, iPresetHold, 1
  kModelGate = kGesture
  if iArticulation != 0 then
    kModelGate = kPresetGate
  endif
  iTriggerLevel = 0.16 + 0.88 * iDynamic
  if iArticulation <= 4 then
    ; Dynamics already shape bowed force and speed. Keep contact above the
    ; stable floor so short p strokes do not lose the string.
    iTriggerLevel = 0.36 + 0.64 * iDynamic
  endif

  ; The generated events already expand the two printed finale trills.
  kFrequency init cpsmidinn(iMidi)

  gkGestureId[iString] = iGestureId
  giPriorEndBeat[iString] = p2 + p3
  giPriorSlur[iString] = iSlur
  if gkGestureId[iString] == iGestureId then
    gkTrigger[iString] = min(1.20, iTriggerLevel * kModelGate)
    gkFrequency[iString] = kFrequency
    gkForce[iString] = iForce
    gkSpeed[iString] = iSpeed
    gkPosition[iString] = iPosition
    gkVibratoDepth[iString] = iVibratoDepth
    gkVibratoRate[iString] = iVibratoRate
    gkArticulation[iString] = iArticulation
    gkHarmonic[iString] = iHarmonic
  endif
  ; Let an exact next note claim the string before the old off event checks it.
  event_i "i", "CapriceOff", p3 + ksmps / sr, 0.001, \
      iString, iGestureId

  iGuideAmp = $GUIDE_LEVEL * (0.035 + 0.16 * iDynamic)
  if iPizzicato != 0 then
    aTone pluck iGuideAmp, cpsmidinn(iMidi), cpsmidinn(iMidi), 0, 1
  else
    aOne poscil iGuideAmp * 0.64, kFrequency, giSine
    aTwo poscil iGuideAmp * 0.24, kFrequency * 2, giSine
    aThree poscil iGuideAmp * 0.12, kFrequency * 3, giSine
    aTone = aOne + aTwo + aThree
  endif
  aTone *= a(kGesture)
  aLeft, aRight pan2 aTone, 0.34 + 0.105 * iString
  gaGuideLeft += aLeft
  gaGuideRight += aRight
endin

instr CapriceOff
  iString = int(p4)
  iGestureId = int(p5)
  if gkGestureId[iString] == iGestureId then
    gkTrigger[iString] = 0
    ; The always-on controller still owns this rail. Leave its finger open so
    ; the renderer can drive a sympathetic release. Exact-off A/B runs keep
    ; the stored stopped-tail path.
    if $SYMPATHETIC_LEVEL > 0 then
      gkFrequency[iString] = giOpenFrequency[iString]
      gkArticulation[iString] = 0
      gkHarmonic[iString] = 0
    endif
  endif
endin

instr StringController
  iString = int(p4)
  ; Before this string's first score note, start its owned rail safely open
  ; when sympathy is in use. With exact-off sympathy, retain the old 20 Hz
  ; empty-rail setup until the first note claims it.
  if $SYMPATHETIC_LEVEL > 0 && gkFrequency[iString] <= 0 then
    gkFrequency[iString] = giOpenFrequency[iString]
  endif
  kFrequency = max(20, gkFrequency[iString])
  aDryLeft, aDryRight hlolli_wg_violin \
      gkTrigger[iString], kFrequency, gkForce[iString], \
      gkSpeed[iString], gkPosition[iString], \
      gkVibratoDepth[iString], gkVibratoRate[iString], \
      gkArticulation[iString], gkHarmonic[iString], 0, \
      iString, giViolin
  gaModelDryLeft += aDryLeft
  gaModelDryRight += aDryRight
endin

instr ViolinBody
  ; One renderer owns the shared body. This global physical response does not
  ; change the score events or their articulation map.
  aWetLeft, aWetRight hlolli_wg_violin_resonance \
      giViolin, 0.76, $SYMPATHETIC_LEVEL, 0
  gaModelWetLeft += aWetLeft
  gaModelWetRight += aWetRight
endin

instr Master
  aModelLeft = $DIRECT_LEVEL * gaModelDryLeft + \
      $BODY_LEVEL * gaModelWetLeft
  aModelRight = $DIRECT_LEVEL * gaModelDryRight + \
      $BODY_LEVEL * gaModelWetRight
  aDryLeft = $GUIDE_LEVEL / max($GUIDE_LEVEL, 0.000001) * \
      gaGuideLeft + $MODEL_LEVEL * aModelLeft
  aDryRight = $GUIDE_LEVEL / max($GUIDE_LEVEL, 0.000001) * \
      gaGuideRight + $MODEL_LEVEL * aModelRight

  ; This stereo response was made for one source. Sum the dry stereo bus to one
  ; send, then keep the two distinct response channels as the wet return.
  ; The 256-frame partition adds 5.8 ms at 44.1 kHz; the IR onset adds 1.5 ms.
  aReverbSend = 0.5 * (aDryLeft + aDryRight)
  denorm aReverbSend
  aRoomLeft, aRoomRight ftconv \
      aReverbSend, giChurchIR, 256, 0, giChurchFrames
  aLeft = aDryLeft + $REVERB_LEVEL * aRoomLeft
  aRight = aDryRight + $REVERB_LEVEL * aRoomRight

  outs tanh(aLeft * 0.92), tanh(aRight * 0.92)
  clear gaGuideLeft, gaGuideRight, \
      gaModelDryLeft, gaModelDryRight, gaModelWetLeft, gaModelWetRight
endin

</CsInstruments>
<CsScore>
; Paganini marks only "quasi Presto". This fixed tempo curve is an editorial
; performance choice: each phrase moves forward, then broadens at its cadence.
t 0 124 7 130 7.75 112 8 124 15 132 15.75 110 16 126 23 130 31 108 32 136 \
  39 143 47 120 48 132 55 138 63 114 64 129 71 136 79 112 80 94 \
  87 98 95 82 96 147 103 155 111 130 112 132 119 139 127 116 128 131 \
  135 138 143 114 144 92 151 98 159 80 160 131 167 139 175 113 176 134 \
  183 141 191 116 192 96 199 101 207 84 208 98 215 102 223 86 224 110 \
  235 116 235.75 98 236 111 247 117 247.75 96 248 112 259 116 271 94 \
  272 106 283 112 283.75 94 284 107 295 113 295.75 92 296 108 307 113 \
  318 90 319 123 326 130 334 111 342 130 350 104 351 88 358 94 366 82 \
  374 93 382 75 383 123 390 130 398 108 406 132 412.75 105 413 136 \
  421 145 429 154 435 160 437.5 132 439 116 440.5 92 441.4375 60 \
  442.4375 60

i "StringController" 0 442.4375 1
i "StringController" 0 442.4375 2
i "StringController" 0 442.4375 3
i "StringController" 0 442.4375 4
i "ViolinBody" 0 445.4375
; Keep ftconv alive for the full 7.986-second response after the body stops.
i "Master" 0 453.5

#include "paganini_caprice_24_score.inc"

f 0 453.5
e
</CsScore>
</CsoundSynthesizer>
