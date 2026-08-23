<CsoundSynthesizer>
<CsOptions>
-d -m128
</CsOptions>
<CsInstruments>

#ifndef TRANSIENT_CASE
#define TRANSIENT_CASE #1#
#endif

#ifndef TRANSIENT_DIRECT_LEVEL
#define TRANSIENT_DIRECT_LEVEL #1#
#endif

#ifndef TRANSIENT_BODY_LEVEL
#define TRANSIENT_BODY_LEVEL #1#
#endif

#ifndef TRANSIENT_BRIDGE_SCALE
#define TRANSIENT_BRIDGE_SCALE #1#
#endif

#ifndef TRANSIENT_NUT_SCALE
#define TRANSIENT_NUT_SCALE #1#
#endif

#ifndef TRANSIENT_NUT_SCALE_G
#define TRANSIENT_NUT_SCALE_G #1#
#endif

#ifndef TRANSIENT_NUT_SCALE_D
#define TRANSIENT_NUT_SCALE_D #1#
#endif

#ifndef TRANSIENT_BRIDGE_SCALE_G
#define TRANSIENT_BRIDGE_SCALE_G #1#
#endif

#ifndef TRANSIENT_BRIDGE_SCALE_D
#define TRANSIENT_BRIDGE_SCALE_D #1#
#endif

#ifndef TRANSIENT_ROOM_LEVEL
#define TRANSIENT_ROOM_LEVEL #0.075#
#endif

#ifndef TRANSIENT_FINGER_SCALE
#define TRANSIENT_FINGER_SCALE #1#
#endif

#ifndef TRANSIENT_BOARD_SCALE
#define TRANSIENT_BOARD_SCALE #1#
#endif

#ifndef TRANSIENT_ROSIN_SCALE
#define TRANSIENT_ROSIN_SCALE #1#
#endif

#ifndef TRANSIENT_MECHANICAL_SCALE
#define TRANSIENT_MECHANICAL_SCALE #1#
#endif

sr = 48000
ksmps = 32
nchnls = 2
0dbfs = 1

giReferencePitch = 440 * exp(log(2) * 24.299978636644809 / 1200)
giReferenceRatio = giReferencePitch / 440
giViolin hlolli_wg_violin_create giReferencePitch
gaDryLeft init 0
gaDryRight init 0
gaWetLeft init 0
gaWetRight init 0
gaRoomLeft init 0
gaRoomRight init 0

giTransientRoomFrames = int(0.20 * sr)
opcode TransientRoomIR, i, 0
  iIR ftgen 0, 0, -(2 * giTransientRoomFrames), -2, 0
  iN = int(0.008 * sr)
  iSeedLeft = 12457
  iSeedRight = 89173
  iBlurLeft = 0
  iBlurRight = 0
  iDampLeft = 0
  iDampRight = 0
  while iN < giTransientRoomFrames do
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
giTransientRoomIR TransientRoomIR

instr NoteVoice
  kTime timeinsts
  kTrigger = kTime < 0.51062333053141 ? 0.6787395724595651 : 0
  aLeft, aRight hlolli_wg_violin \
      kTrigger, giReferenceRatio * cpsmidinn(57), \
      0.4785820190170106, -0.5588971259021194, 0.12, \
      18.9803058196807, 5.448621407377649, 1, 0, 0, 1, giViolin
  gaDryLeft += aLeft
  gaDryRight += aRight
endin

instr ChordVoice
  kTime timeinsts
  kTrigger = kTime < 1.22588083470912 ? 0.808727138405271 : 0
  aLeft, aRight hlolli_wg_violin \
      kTrigger, giReferenceRatio * cpsmidinn(p4), \
      0.6248180307059299, 0.6726362461046123, 0.12, \
      21.01136153758236, 5.590795307630765, 1, 0, 0, p5, giViolin
  gaDryLeft += aLeft
  gaDryRight += aRight
endin

instr Body
  aLeft, aRight hlolli_wg_violin_resonance giViolin, 0.76, 0.5, 0
  gaWetLeft += aLeft
  gaWetRight += aRight
endin

instr Room
  aSourceLeft = $TRANSIENT_DIRECT_LEVEL * gaDryLeft + \
      $TRANSIENT_BODY_LEVEL * gaWetLeft
  aSourceRight = $TRANSIENT_DIRECT_LEVEL * gaDryRight + \
      $TRANSIENT_BODY_LEVEL * gaWetRight
  aSend = 0.5 * (aSourceLeft + aSourceRight)
  denorm aSend
  aLeft, aRight ftconv \
      aSend, giTransientRoomIR, 128, 0, giTransientRoomFrames
  gaRoomLeft += aLeft
  gaRoomRight += aRight
endin

instr Master
  outs 0.48 * ($TRANSIENT_DIRECT_LEVEL * gaDryLeft + \
               $TRANSIENT_BODY_LEVEL * gaWetLeft + \
               $TRANSIENT_ROOM_LEVEL * gaRoomLeft), \
       0.48 * ($TRANSIENT_DIRECT_LEVEL * gaDryRight + \
               $TRANSIENT_BODY_LEVEL * gaWetRight + \
               $TRANSIENT_ROOM_LEVEL * gaRoomRight)
  clear gaDryLeft, gaDryRight, gaWetLeft, gaWetRight, \
      gaRoomLeft, gaRoomRight
endin

instr Schedule
#ifdef TRANSIENT_TEST_API
  iString = 1
  while iString <= 4 do
    iNutScale = $TRANSIENT_NUT_SCALE
    iBridgeScale = $TRANSIENT_BRIDGE_SCALE
    if iString == 1 then
      iNutScale *= $TRANSIENT_NUT_SCALE_G
      iBridgeScale *= $TRANSIENT_BRIDGE_SCALE_G
    elseif iString == 2 then
      iNutScale *= $TRANSIENT_NUT_SCALE_D
      iBridgeScale *= $TRANSIENT_BRIDGE_SCALE_D
    endif
    iOk hlolli_wg_violin_test_diagnostic_gains \
        giViolin, iString, $TRANSIENT_FINGER_SCALE, \
        $TRANSIENT_BOARD_SCALE, $TRANSIENT_ROSIN_SCALE, \
        $TRANSIENT_MECHANICAL_SCALE, iNutScale, iBridgeScale
    if iOk != 1 then
      prints "could not set transient diagnostic gains\n"
      turnoff
    endif
    iString += 1
  od
#endif
  event_i "i", "Body", 0, 3.20
  event_i "i", "Room", 0, 3.20
  event_i "i", "Master", 0, 3.20
  if $TRANSIENT_CASE == 1 then
    event_i "i", "NoteVoice", 0.20, 1.25
  elseif $TRANSIENT_CASE == 2 then
    event_i "i", "ChordVoice", 0.20, 2.10, 76, 1
    event_i "i", "ChordVoice", 0.20, 2.10, 64, 2
  else
    prints "TRANSIENT_CASE must be 1 or 2\n"
    turnoff
  endif
endin

</CsInstruments>
<CsScore>
i "Schedule" 0 0.001
e
</CsScore>
</CsoundSynthesizer>
