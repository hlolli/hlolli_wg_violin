<CsoundSynthesizer>
<CsOptions>
-n -d -m128
</CsOptions>
<CsInstruments>

sr = 48000
ksmps = 32
nchnls = 2
0dbfs = 1

giViolinA hlolli_wg_violin_create
giViolinB hlolli_wg_violin_create

instr Voice
  iViolin = p4
  iString = p5
  kTrigger init 0.6
  kFrequency init cpsmidinn(p6)
  kForce init 0.45
  kSpeed init 0.55
  kPosition init 0.12
  kVibratoDepth init 16
  kVibratoRate init 5.1
  kArticulation init p7
  kHarmonic init p8
  kStrange init p9

  aLeft, aRight hlolli_wg_violin \
      kTrigger, kFrequency, kForce, kSpeed, kPosition, \
      kVibratoDepth, kVibratoRate, kArticulation, \
      kHarmonic, kStrange, iString, iViolin
  outs aLeft, aRight
endin

instr BodyA
  aLeft, aRight hlolli_wg_violin_resonance \
      giViolinA, 0.72, 0.55, 0
  outs aLeft, aRight
endin

instr BodyB
  aLeft, aRight hlolli_wg_violin_resonance \
      giViolinB, 0.64, 0.35, 0.4
  outs aLeft, aRight
endin

instr StartVoices
  ; Pass the handles returned by the creator opcodes. Do not assume their IDs.
  event_i "i", "Voice", 0, 0.25, giViolinA, 2, 62, 0, 0, 0
  event_i "i", "Voice", 0, 0.25, giViolinA, 3, 69, 1, 0, -0.2
  event_i "i", "Voice", 0, 0.25, giViolinB, 2, 67, 5, 0, 0.2
endin

</CsInstruments>
<CsScore>
i "BodyA" 0 0.5
i "BodyB" 0 0.5
i "StartVoices" 0 0.01
e 0.5
</CsScore>
</CsoundSynthesizer>
