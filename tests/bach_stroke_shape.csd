<CsoundSynthesizer>
<CsOptions>
-n -d -m128
</CsOptions>
<CsInstruments>

sr = 48000
ksmps = 32
nchnls = 2
0dbfs = 1

giSine ftgen 0, 0, 16384, 10, 1

#include "../examples/bach_chaconne_stroke.inc"

instr Probe
  kPhase init p4
  iChordSize = int(p5)
  kContact, kForce, kSpeed \
      HlolBachStrokeShape kPhase, iChordSize
  kFirst = timeinstk() == 1 ? 1 : 0
  printf "BACH_STROKE %.9f %d %.17g %.17g %.17g\n", \
      kFirst, kPhase, iChordSize, kContact, kForce, kSpeed
  if kFirst == 1 then
    turnoff
  endif
endin

instr Render
  iChordSize = int(p4)
  kPhase line 0, p3, 1
  kContact, kForce, kSpeed \
      HlolBachStrokeShape kPhase, iChordSize
  aTone poscil 0.06 * kContact * kForce * kSpeed, 440, giSine
  outs aTone, aTone
endin

instr PitchProbe
  kAge timeinsts
  if kAge < 0.08 then
    kTarget = cpsmidinn(58)
  else
    kTarget = cpsmidinn(55)
  endif
  kFrequency HlolBachPitchTransition kTarget
  printks "BACH_PITCH %.9f %.17g %.17g\n", \
      ksmps / sr, kAge, kTarget, kFrequency
endin

instr ChordProbe
  iChordSize = int(p4)
  iChordRank = int(p5)
  iLead = int(p6)
  kContact HlolBachChordContact p3, iChordSize, iChordRank, iLead
  kAge timeinsts
  printks "BACH_CHORD %d %d %d %.9f %.17g\n", \
      ksmps / sr, iChordSize, iChordRank, iLead, kAge, kContact
endin

instr Schedule
  iIndex = 0
  while iIndex <= 8 do
    iPhase = iIndex / 8
    iStart = 0.01 * iIndex
    event_i "i", "Probe", iStart, 0.001, iPhase, 1
    event_i "i", "Probe", 0.10 + iStart, 0.001, iPhase, 3
    iIndex += 1
  od
  event_i "i", "Probe", 0.20, 0.001, -0.5, 3
  event_i "i", "Probe", 0.21, 0.001, 1.5, 3
  event_i "i", "Render", 0.30, 1.0, 1
  event_i "i", "Render", 1.30, 1.0, 3
  event_i "i", "ChordProbe", 0.30, 0.25, 1, 0, 1
  event_i "i", "ChordProbe", 0.60, 0.25, 2, 1, 0
  event_i "i", "ChordProbe", 0.60, 0.25, 2, 0, 1
  event_i "i", "ChordProbe", 0.90, 0.25, 4, 3, 0
  event_i "i", "ChordProbe", 0.90, 0.25, 4, 2, 0
  event_i "i", "ChordProbe", 0.90, 0.25, 4, 1, 0
  event_i "i", "ChordProbe", 0.90, 0.25, 4, 0, 1
  event_i "i", "ChordProbe", 2.31, 1.50, 3, 2, 0
  event_i "i", "ChordProbe", 2.31, 1.50, 3, 1, 0
  event_i "i", "ChordProbe", 2.31, 1.50, 3, 0, 1
endin

</CsInstruments>
<CsScore>
i "Schedule" 0 0.001
i "PitchProbe" 0 0.16
f 0 3.82
e
</CsScore>
</CsoundSynthesizer>
