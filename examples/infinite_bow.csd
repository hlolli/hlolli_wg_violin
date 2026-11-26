<CsoundSynthesizer>
<CsOptions>
-d -m128 --sample-accurate --num-threads=1
</CsOptions>
<CsInstruments>
#ifndef CONTINUOUS
#define CONTINUOUS #1#
#endif
sr = 48000
ksmps = 32
nchnls = 2
0dbfs = 1

giViolin hlolli_wg_violin_create

instr BowedNote
  kGate = 1
  kFrequency = p4
  kDirection = $CONTINUOUS != 0 ? 1 : p6
  kArticulation = $CONTINUOUS != 0 ? 0 : 1
  if $CONTINUOUS == 0 && timeinsts() >= p3 - ksmps / sr then
    kGate = 0
  endif
  aLeft, aRight hlolli_wg_violin \
      kGate, kFrequency, 0.45, 0.55 * kDirection, 0.14, \
      6, 5.2, kArticulation, 0, 0, p5, giViolin
  outs aLeft, aRight
endin

instr Body
  aLeft, aRight hlolli_wg_violin_resonance giViolin, 0.92, 0.35, 0
  outs aLeft, aRight
endin
</CsInstruments>
<CsScore>
; One phrase per string. Notes meet exactly; each repeated pitch stays bowed.
; Rests and changes of physical string begin a new phrase.
i "Body" 0 7
i "BowedNote" 0.00 0.25 220 1 1
i "BowedNote" 0.25 0.25 246.941650628062 1 -1
i "BowedNote" 0.50 0.25 246.941650628062 1 1
i "BowedNote" 0.75 0.25 261.625565300599 1 -1
i "BowedNote" 1.25 0.25 329.62755691287 2 1
i "BowedNote" 1.50 0.25 349.228231433004 2 -1
i "BowedNote" 1.75 0.25 349.228231433004 2 1
i "BowedNote" 2.00 0.25 391.995435981749 2 -1
i "BowedNote" 2.50 0.25 493.883301256124 3 1
i "BowedNote" 2.75 0.25 523.251130601197 3 -1
i "BowedNote" 3.00 0.25 523.251130601197 3 1
i "BowedNote" 3.25 0.25 587.329535834815 3 -1
i "BowedNote" 3.75 0.25 739.988845423269 4 1
i "BowedNote" 4.00 0.25 783.990871963499 4 -1
i "BowedNote" 4.25 0.25 783.990871963499 4 1
i "BowedNote" 4.50 0.25 880 4 -1
e
</CsScore>
</CsoundSynthesizer>
