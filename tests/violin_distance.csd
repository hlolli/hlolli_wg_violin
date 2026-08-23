<CsoundSynthesizer>
<CsOptions>
-n -d -m128
</CsOptions>
<CsInstruments>

sr = 48000
ksmps = 32
nchnls = 4
0dbfs = 1

#include "../examples/violin_distance.inc"

instr Probe
  aImpulse mpulse 0.5, 0
  aNearLeft, aNearRight, aNearRoomLeft, aNearRoomRight \
      HlolViolinDistance aImpulse, aImpulse, 1
  aFarLeft, aFarRight, aFarRoomLeft, aFarRoomRight \
      HlolViolinDistance aImpulse, aImpulse, 4
  outch 1, aNearLeft, 2, aFarLeft, \
      3, aNearRoomLeft, 4, aFarRoomLeft
endin

</CsInstruments>
<CsScore>
i "Probe" 0 0.05
e
</CsScore>
</CsoundSynthesizer>
