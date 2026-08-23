<CsoundSynthesizer>
<CsOptions>
-d -m128
</CsOptions>
<CsInstruments>
sr = 48000
ksmps = 32
nchnls = 2
0dbfs = 1

giPlayer1 hlolli_wg_violin_create
giPlayer2 hlolli_wg_violin_create
giPlayer3 hlolli_wg_violin_create
giPlayer4 hlolli_wg_violin_create
gaLeft init 0
gaRight init 0

instr Player
  iHandle = p4
  iFrequency = cpsmidinn(p5)
  iString = p6
  iMotion = p7
  kPhase phasor 0.18 + 0.013 * iMotion, 0.17 * iMotion
  kTriangle = 1 - abs(2 * kPhase - 1)
  kForce = p8 + 0.06 * kTriangle
  kSpeed = p9 * (0.90 + 0.10 * kTriangle)
  kPosition = p10 + 0.012 * (kTriangle - 0.5)
  aLeft, aRight hlolli_wg_violin \
      1, iFrequency, kForce, kSpeed, kPosition, \
      8 + 2 * iMotion, 4.8 + 0.09 * iMotion, 0, 0, 0, \
      iString, iHandle
  gaLeft += 0.42 * aLeft
  gaRight += 0.42 * aRight
endin

instr Body
  aLeft, aRight hlolli_wg_violin_resonance \
      p4, 0.70, 0.38, p5
  gaLeft += 0.42 * aLeft
  gaRight += 0.42 * aRight
endin

instr Output
  outs gaLeft, gaRight
  clear gaLeft, gaRight
endin

instr Section
  ; Four separate handles mean four separate players and physical violins.
  event_i "i", "Player", 0.0, 3.0, giPlayer1, 67, 2, 1, 0.38,  0.42, 0.16
  event_i "i", "Player", 0.0, 3.0, giPlayer2, 62, 2, 2, 0.40, -0.39, 0.18
  event_i "i", "Player", 0.0, 3.0, giPlayer3, 59, 1, 3, 0.42,  0.36, 0.20
  event_i "i", "Player", 0.0, 3.0, giPlayer4, 55, 1, 4, 0.44, -0.34, 0.22
  event_i "i", "Player", 3.0, 3.0, giPlayer1, 69, 3, 1, 0.40, -0.43, 0.15
  event_i "i", "Player", 3.0, 3.0, giPlayer2, 64, 2, 2, 0.42,  0.40, 0.17
  event_i "i", "Player", 3.0, 3.0, giPlayer3, 60, 2, 3, 0.43, -0.37, 0.19
  event_i "i", "Player", 3.0, 3.0, giPlayer4, 57, 1, 4, 0.45,  0.35, 0.21
  event_i "i", "Player", 6.0, 3.0, giPlayer1, 71, 3, 1, 0.39,  0.44, 0.14
  event_i "i", "Player", 6.0, 3.0, giPlayer2, 67, 2, 2, 0.41, -0.41, 0.16
  event_i "i", "Player", 6.0, 3.0, giPlayer3, 62, 2, 3, 0.44,  0.38, 0.18
  event_i "i", "Player", 6.0, 3.0, giPlayer4, 59, 1, 4, 0.46, -0.36, 0.20
  event_i "i", "Player", 9.0, 2.4, giPlayer1, 72, 3, 1, 0.37, -0.40, 0.16
  event_i "i", "Player", 9.0, 2.4, giPlayer2, 67, 2, 2, 0.39,  0.38, 0.18
  event_i "i", "Player", 9.0, 2.4, giPlayer3, 64, 2, 3, 0.42, -0.36, 0.20
  event_i "i", "Player", 9.0, 2.4, giPlayer4, 60, 2, 4, 0.44,  0.34, 0.22
  event_i "i", "Body", 0, 12.2, giPlayer1, 0.00
  event_i "i", "Body", 0, 12.2, giPlayer2, 0.05
  event_i "i", "Body", 0, 12.2, giPlayer3, 0.10
  event_i "i", "Body", 0, 12.2, giPlayer4, 0.15
endin

</CsInstruments>
<CsScore>
i "Section" 0 0.001
i "Output" 0 12.2
e
</CsScore>
</CsoundSynthesizer>
