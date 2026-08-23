<CsoundSynthesizer>
<CsOptions>
-d -m128
</CsOptions>
<CsInstruments>

#ifndef PROBE_CASE
#define PROBE_CASE #1#
#endif

#ifndef PROBE_KSMPS
#define PROBE_KSMPS #32#
#endif

sr = 48000
ksmps = $PROBE_KSMPS
nchnls = 2
0dbfs = 1

giViolin hlolli_wg_violin_create

gaDryLeft init 0
gaDryRight init 0
gaWetLeft init 0
gaWetRight init 0

instr Voice
  kTrigger init 0.68
  kFrequency init p5
  kForce init 0.46
  kSpeed init 0.52
  kPosition init 0.12

  aLeft, aRight hlolli_wg_violin \
      kTrigger, kFrequency, kForce, kSpeed, kPosition, \
      0, 0, 0, 0, 0, p4, giViolin
  gaDryLeft += aLeft
  gaDryRight += aRight
endin

instr Body
  aLeft, aRight hlolli_wg_violin_resonance giViolin, 0.72, 0, 0
  gaWetLeft += aLeft
  gaWetRight += aRight
endin

instr BridgeImpulse
  iOk hlolli_wg_violin_test_bridge_impulse giViolin, p4, p5
  printf_i "WG_PHYSICAL_BODY_IMPULSE %d %.17g\n", 1, p4, iOk
endin

instr Master
  outs gaDryLeft + gaWetLeft, gaDryRight + gaWetRight
  clear gaDryLeft, gaDryRight, gaWetLeft, gaWetRight
endin

instr Schedule
  event_i "i", "Body", 0, 2.5
  event_i "i", "Master", 0, 2.5
  if $PROBE_CASE == 1 then
    event_i "i", "Voice", 0.20, 1.00, 2, 440
  elseif $PROBE_CASE == 2 then
    event_i "i", "Voice", 0.20, 1.00, 3, 442
  elseif $PROBE_CASE == 3 then
    event_i "i", "Voice", 0.20, 1.00, 2, 293.664767917408
  elseif $PROBE_CASE == 4 then
    event_i "i", "Voice", 0.20, 1.00, 3, 440
  elseif $PROBE_CASE == 5 then
    event_i "i", "Voice", 0.20, 1.00, 2, 293.664767917408
    event_i "i", "Voice", 0.20, 1.00, 3, 440
  elseif $PROBE_CASE == 6 then
    event_i "i", "BridgeImpulse", 0.10, 0.001, 2, 4
  elseif $PROBE_CASE == 7 then
    event_i "i", "Voice", 0.20, 1.00, 4, 1760
  endif
endin

</CsInstruments>
<CsScore>
i "Schedule" 0 0.001
e
</CsScore>
</CsoundSynthesizer>
