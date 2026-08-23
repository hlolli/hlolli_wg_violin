<CsoundSynthesizer>
<CsOptions>
-d -m128
</CsOptions>
<CsInstruments>

sr = 48000
ksmps = 32
nchnls = 2
0dbfs = 1

giViolin hlolli_wg_violin_create
giCompareSymOff hlolli_wg_violin_create
giCompareSymHalf hlolli_wg_violin_create
giCompareSymFull hlolli_wg_violin_create
giCompareStrangeLow hlolli_wg_violin_create
giCompareStrangeZero hlolli_wg_violin_create
giCompareStrangeHigh hlolli_wg_violin_create

gaDryLeft init 0
gaDryRight init 0
gaWetLeft init 0
gaWetRight init 0

opcode CompareHandle, i, i
  iCase xin
  iHandle = giCompareSymOff
  if iCase == 2 then
    iHandle = giCompareSymHalf
  elseif iCase == 3 then
    iHandle = giCompareSymFull
  elseif iCase == 4 then
    iHandle = giCompareStrangeLow
  elseif iCase == 5 then
    iHandle = giCompareStrangeZero
  elseif iCase == 6 then
    iHandle = giCompareStrangeHigh
  endif
  xout iHandle
endop

instr ViolinNote
  iArticulation = int(p10)
  iOneShot = iArticulation >= 5 && iArticulation <= 7
  iPulse = min(0.012, max(0.001, p3 * 0.08))
  kOneShot linseg p5, iPulse, 0, max(0.001, p3 - iPulse), 0
  kTrigger init p5
  if iOneShot != 0 then
    kTrigger = kOneShot
  endif
  kFrequency init cpsmidinn(p4)
  kForce init p7
  kSpeed init p8
  kPosition init p9
  iVibratoDepth = 18
  if iArticulation >= 5 then
    iVibratoDepth = 0
  endif
  kVibratoDepth init iVibratoDepth
  kVibratoRate init 5.2
  kArticulation init iArticulation
  kHarmonic init p12
  kStrange init p11
  iString = p6

  aDryLeft, aDryRight hlolli_wg_violin \
      kTrigger, kFrequency, kForce, kSpeed, kPosition, \
      kVibratoDepth, kVibratoRate, kArticulation, \
      kHarmonic, kStrange, iString, giViolin
  gaDryLeft += aDryLeft
  gaDryRight += aDryRight
endin

instr ViolinGlide
  kTrigger init p7
  kFrequency expseg cpsmidinn(p4), p3, cpsmidinn(p5)
  kForce init p8
  kSpeed init p9
  kPosition init p10
  kVibratoDepth init 10
  kVibratoRate init 5.0
  kArticulation init 0
  kHarmonic init 0
  kStrange init 0
  iString = p6

  aDryLeft, aDryRight hlolli_wg_violin \
      kTrigger, kFrequency, kForce, kSpeed, kPosition, \
      kVibratoDepth, kVibratoRate, kArticulation, \
      kHarmonic, kStrange, iString, giViolin
  gaDryLeft += aDryLeft
  gaDryRight += aDryRight
endin

instr BowControlTour
  ; Code 0 leaves these live k-rate paths unshaped. The held speed change
  ; crosses zero, so the string makes one bowed reversal without a new note.
  iRise = max(0.001, p3 * 0.28)
  iReverse = max(0.001, p3 * 0.30)
  iSettle = max(0.001, p3 - iRise - iReverse)
  kTrigger init 0.72
  kFrequency init cpsmidinn(p4)
  kForce linseg 0.30, iRise, 0.62, iReverse, 0.44, iSettle, 0.50
  kSpeed linseg 0.38, iRise, 0.58, iReverse, -0.44, iSettle, -0.32
  kPosition linseg 0.18, p3, 0.09
  kVibratoDepth init 12
  kVibratoRate init 5.0
  kArticulation init 0
  kHarmonic init 0
  kStrange init 0
  iString = p5

  aDryLeft, aDryRight hlolli_wg_violin \
      kTrigger, kFrequency, kForce, kSpeed, kPosition, \
      kVibratoDepth, kVibratoRate, kArticulation, \
      kHarmonic, kStrange, iString, giViolin
  gaDryLeft += aDryLeft
  gaDryRight += aDryRight
endin

instr SecondaryPhysicsTour
  ; neutral bow stays on the neutral physical path. The slow, hard move toward
  ; the bridge exposes contact memory, heat, hair lag, noise, and one reversal.
  iFirst = max(0.001, p3 * 0.36)
  iSecond = max(0.001, p3 * 0.32)
  iLast = max(0.001, p3 - iFirst - iSecond)
  kTrigger init 0.76
  kFrequency init cpsmidinn(p4)
  kForce linseg 0.34, iFirst, 0.82, iSecond, 0.66, iLast, 0.48
  kSpeed linseg 0.56, iFirst, 0.20, iSecond, -0.34, iLast, -0.28
  kPosition linseg 0.18, iFirst, 0.055, iSecond, 0.075, iLast, 0.11
  kVibratoDepth init 6
  kVibratoRate init 4.9
  kArticulation init 0
  kHarmonic init 0
  kStrange init 0
  iString = p5

  aDryLeft, aDryRight hlolli_wg_violin \
      kTrigger, kFrequency, kForce, kSpeed, kPosition, \
      kVibratoDepth, kVibratoRate, kArticulation, \
      kHarmonic, kStrange, iString, giViolin
  gaDryLeft += aDryLeft
  gaDryRight += aDryRight
endin

instr CompareVoice
  iHandle CompareHandle int(p5)
  kTrigger init 0.70
  kFrequency init cpsmidinn(p4)
  kForce init p7
  kSpeed init p8
  kPosition init p9
  kVibratoDepth init 0
  kVibratoRate init 0
  kArticulation init 0
  kHarmonic init 0
  kStrange init p6
  iString = int(p10)
  iDryGain = p11

  aDryLeft, aDryRight hlolli_wg_violin \
      kTrigger, kFrequency, kForce, kSpeed, kPosition, \
      kVibratoDepth, kVibratoRate, kArticulation, \
      kHarmonic, kStrange, iString, iHandle
  gaDryLeft += iDryGain * aDryLeft
  gaDryRight += iDryGain * aDryRight
endin

instr CompareBody
  iHandle CompareHandle int(p4)
  kSympathetic init p5
  aWetLeft, aWetRight hlolli_wg_violin_resonance \
      iHandle, 0.72, kSympathetic, 0
  gaWetLeft += aWetLeft
  gaWetRight += aWetRight
endin

instr CompareMark
  iCase = int(p4)
  if iCase == 1 then
    prints "\nkSympathetic 0 (exact off)\n"
  elseif iCase == 2 then
    prints "kSympathetic 0.5\n"
  elseif iCase == 3 then
    prints "kSympathetic 1\n"
  elseif iCase == 4 then
    prints "kStrange -0.7\n"
  elseif iCase == 5 then
    prints "kStrange 0 (neutral)\n"
  else
    prints "kStrange 0.7\n"
  endif
  turnoff
endin

instr ViolinBody
  ; One renderer owns the shared body for the earlier tour. Exact-zero
  ; sympathy keeps the neutral bow positive-gate bridge return unchanged.
  aWetLeft, aWetRight hlolli_wg_violin_resonance \
      giViolin, 0.72, 0, 0
  gaWetLeft += aWetLeft
  gaWetRight += aWetRight
endin

instr Master
  outs gaDryLeft + gaWetLeft, gaDryRight + gaWetRight
  clear gaDryLeft, gaDryRight, gaWetLeft, gaWetRight
endin

</CsInstruments>
<CsScore>
; First, one held A string moves from A4 to E5 with no second attack.
; Then the D and A strings play an open-fifth double stop. Both voices use
; explicit strings, so each owns its own waveguide inside the same violin.
; The articulation tour follows: two right-hand pizzicato notes at different pluck
; points, a gentler left-hand pizzicato, Bartók pizzicato, col legno battuto,
; and a held col legno tratto stroke. Natural and artificial fourth harmonics
; come next. The closing bow-gesture tour plays direct arco with a held bow change,
; then détaché, martelé, one spiccato pulse, and held tremolo. The neutral bow
; close uses neutral controls for a slow hard stroke and reversal, a strong
; stopped G-string note, and an open D beside a quiet open G listener.
; p4 remains the sounding MIDI pitch for both harmonics. Positive code-5 speed
; selects the normal release; negative speed selects the left-hand release.
; The closing comparison repeats one source on fresh handles at sympathy 0, 0.5,
; and 1, then repeats another source at strange -0.7, 0, and 0.7.
; The renderer stays on after the direct notes so each body can ring out.
i "ViolinBody" 0 34.0
i "Master" 0 56.5
i "ViolinGlide" 0.20 2.40 69 76 3 0.68 0.38 0.54 0.12
i "ViolinNote" 3.10 1.80 62 0.66 2 0.40 0.52 0.13 0 0 0
i "ViolinNote" 3.10 1.80 69 0.66 3 0.38 -0.50 0.11 0 0 0
; Normal pizzicato: the repeated A4 exposes the position-dependent notch.
i "ViolinNote" 5.35 0.75 69 0.78 3 0.46 0.66 0.10 5 0 0
i "ViolinNote" 6.25 0.75 69 0.78 3 0.46 0.66 0.30 5 0 0
; Left-hand pizzicato uses the same mode with a negative, gentler release.
i "ViolinNote" 7.15 0.75 72 0.68 3 0.34 -0.52 0.22 5 0 0
; Bartók snap, wood strike, then a sustained wood-hair stroke.
i "ViolinNote" 8.05 1.00 62 0.96 2 0.90 0.94 0.18 6 0 0
i "ViolinNote" 9.25 0.80 69 0.84 3 0.62 0.86 0.16 7 0 0
i "ViolinNote" 10.25 1.70 76 0.58 4 0.28 -0.34 0.12 8 0 0
; A6 is the fourth natural harmonic of the open A string.
i "ViolinNote" 12.35 1.55 93 0.68 3 0.34 0.46 0.14 0 0 4
; C6 sounds from an artificial fourth harmonic: C4 is stopped on G, then
; touched one quarter of that speaking length from the stopped finger.
i "ViolinNote" 14.35 1.55 84 0.68 1 0.36 -0.44 0.13 0 0 4
; Direct code 0 follows all live controls and unloads contact at the reversal.
i "BowControlTour" 16.35 1.90 69 3
; Presets treat force, speed, and position as their live peak controls.
i "ViolinNote" 18.55 0.70 72 0.72 3 0.43 0.55 0.14 1 0 0
i "ViolinNote" 19.45 0.70 74 0.74 3 0.55 -0.64 0.12 2 0 0
i "ViolinNote" 20.35 0.70 76 0.78 3 0.48 0.70 0.16 3 0 0
i "ViolinNote" 21.25 1.75 79 0.70 3 0.40 0.72 0.14 4 0 0
; Contact memory, heat, compliant hair, noise, and a reversal at kStrange = 0.
i "SecondaryPhysicsTour" 23.60 3.00 69 3
; A hard stopped low string makes bounded fingerboard contact easy to hear.
i "ViolinNote" 27.00 1.40 60 0.86 1 0.84 0.24 0.07 0 0 0
; A final open D leaves space for the weak bridge return and body tail. The
; positive-gate G listener has no force or speed, so only the neighbouring
; string drives it.
i "ViolinNote" 28.85 1.50 62 0.70 2 0.42 -0.46 0.13 1 0 0
i "ViolinNote" 28.85 2.00 55 0.18 1 0.00 0.00 0.13 0 0 0
; Identical D5-on-A strokes: sympathy off, half, then full. The lower direct
; gain leaves the open-string response and its tail easier to compare.
i "CompareMark" 35.00 0.001 1
i "CompareBody" 35.00 2.60 1 0.00
i "CompareVoice" 35.15 1.20 74 1 0.00 0.52 0.44 0.12 3 0.45
i "CompareMark" 38.05 0.001 2
i "CompareBody" 38.05 2.60 2 0.50
i "CompareVoice" 38.20 1.20 74 2 0.00 0.52 0.44 0.12 3 0.45
i "CompareMark" 41.10 0.001 3
i "CompareBody" 41.10 2.60 3 1.00
i "CompareVoice" 41.25 1.20 74 3 0.00 0.52 0.44 0.12 3 0.45
; Identical C5 strokes with the same normal sympathy: airy/weak strange,
; neutral violin, then the positive nonlinear range.
i "CompareMark" 44.55 0.001 4
i "CompareBody" 44.55 2.65 4 0.50
i "CompareVoice" 44.70 1.75 72 4 -0.70 0.58 0.34 0.11 3 0.85
i "CompareMark" 47.65 0.001 5
i "CompareBody" 47.65 2.65 5 0.50
i "CompareVoice" 47.80 1.75 72 5 0.00 0.58 0.34 0.11 3 0.85
i "CompareMark" 50.75 0.001 6
i "CompareBody" 50.75 2.65 6 0.50
i "CompareVoice" 50.90 1.75 72 6 0.70 0.58 0.34 0.11 3 0.85
e 56.5
</CsScore>
</CsoundSynthesizer>
