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
gaLeft init 0
gaRight init 0

instr Note
  iArticulation = int(p6)
  iOneShot = iArticulation >= 5 && iArticulation <= 7
  iPulse = min(0.012, max(0.002, p3 * 0.08))
  kPulse linseg p7, iPulse, 0, max(0.001, p3 - iPulse), 0
  kTrigger init p7
  if iOneShot != 0 then
    kTrigger = kPulse
  endif
  kFrequency init cpsmidinn(p4)
  kForce init p7
  kSpeed init p8
  kPosition init p9
  kVibratoDepth init p10
  kVibratoRate init 5.2
  kArticulation init iArticulation
  kHarmonic init p11
  kStrange init 0
  aLeft, aRight hlolli_wg_violin \
      kTrigger, kFrequency, kForce, kSpeed, kPosition, \
      kVibratoDepth, kVibratoRate, kArticulation, \
      kHarmonic, kStrange, p5, giViolin
  gaLeft += aLeft
  gaRight += aRight
endin

instr Body
  aLeft, aRight hlolli_wg_violin_resonance \
      giViolin, 0.74, 0.48, 0
  gaLeft += aLeft
  gaRight += aRight
endin

instr Output
  outs gaLeft, gaRight
  clear gaLeft, gaRight
endin

</CsInstruments>
<CsScore>
; Direct legato: the D-string handoff keeps one physical rail and bow.
i "Note" 0.00 1.40 62 2 0 0.46  0.48 0.17 18 0
i "Note" 1.40 1.40 66 2 0 0.44  0.43 0.15 20 0

; Natural and artificial fourth harmonics; p4 stays the sounding pitch.
i "Note" 3.15 1.25 79 1 0 0.42  0.42 0.19  4 4
i "Note" 4.60 1.25 83 1 0 0.45 -0.40 0.18  5 4

; Right-hand, left-hand, and Bartok pizzicato.
i "Note" 6.15 0.65 69 3 5 0.58  0.66 0.23  0 0
i "Note" 7.05 0.55 71 3 5 0.46 -0.58 0.28  0 0
i "Note" 7.85 0.65 62 2 6 0.70  0.72 0.20  0 0

; Col legno battuto and a held col legno tratto stroke.
i "Note" 8.85 0.60 67 2 7 0.60  0.56 0.16  0 0
i "Note" 9.70 1.35 72 3 8 0.40 -0.36 0.21  0 0

; Mixed bow presets: detache, martele, spiccato, then tremolo.
i "Note" 11.35 0.75 74 3 1 0.48  0.46 0.16  8 0
i "Note" 12.25 0.70 76 3 2 0.66 -0.56 0.13  5 0
i "Note" 13.10 0.55 78 3 3 0.45  0.50 0.18  0 0
i "Note" 13.85 1.55 81 4 4 0.42 -0.48 0.20 12 0

i "Body" 0 16.25
i "Output" 0 16.25
e
</CsScore>
</CsoundSynthesizer>
