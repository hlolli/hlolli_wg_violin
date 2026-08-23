<CsoundSynthesizer>
<CsOptions>
-d -m128
</CsOptions>
<CsInstruments>

#ifndef DIAG_MODE
#define DIAG_MODE #phrase#
#endif
#ifndef DIAG_STRING
#define DIAG_STRING #3#
#endif
#ifndef DIAG_FREQUENCY
#define DIAG_FREQUENCY #440#
#endif
#ifndef DIAG_FINGER_GAIN
#define DIAG_FINGER_GAIN #1#
#endif
#ifndef DIAG_BOARD_GAIN
#define DIAG_BOARD_GAIN #1#
#endif
#ifndef DIAG_ROSIN_GAIN
#define DIAG_ROSIN_GAIN #1#
#endif
#ifndef DIAG_MECHANICAL_GAIN
#define DIAG_MECHANICAL_GAIN #1#
#endif
#ifndef DIAG_NUT_CUTOFF_SCALE
#define DIAG_NUT_CUTOFF_SCALE #1#
#endif
#ifndef DIAG_BRIDGE_CUTOFF_SCALE
#define DIAG_BRIDGE_CUTOFF_SCALE #1#
#endif
#ifndef DIAG_DIRECT_GAIN
#define DIAG_DIRECT_GAIN #1#
#endif
#ifndef DIAG_BODY_GAIN
#define DIAG_BODY_GAIN #1#
#endif
#ifndef DIAG_BODY
#define DIAG_BODY #0.72#
#endif
#ifndef DIAG_DIRECT_DELAY_SAMPLES
#define DIAG_DIRECT_DELAY_SAMPLES #0#
#endif
#ifndef DIAG_FORCE
#define DIAG_FORCE #0.46#
#endif
#ifndef DIAG_SPEED
#define DIAG_SPEED #0.52#
#endif
#ifndef DIAG_POSITION
#define DIAG_POSITION #0.12#
#endif
#ifndef DIAG_OPEN_HOLD_SECONDS
#define DIAG_OPEN_HOLD_SECONDS #2.75#
#endif
#ifndef DIAG_TOTAL_SECONDS
#define DIAG_TOTAL_SECONDS #4.00#
#endif

sr = 44100
ksmps = 32
nchnls = 2
0dbfs = 1

giViolin hlolli_wg_violin_create

gaDryLeft init 0
gaDryRight init 0
gaWetLeft init 0
gaWetRight init 0

instr Phrase
  kTime timeinsts
  kTrigger = kTime < 3.20 ? 1 : 0
  kFrequency = 440
  kSpeed = 0.52
  if kTime >= 0.35 && kTime < 1.10 then
    kFrequency = 493.883301256124
  elseif kTime >= 1.10 && kTime < 2.60 then
    kFrequency = 587.329535834815
  elseif kTime >= 2.60 then
    kFrequency = 440
  endif
  if kTime >= 1.85 then
    kSpeed = -0.52
  endif
  aLeft, aRight hlolli_wg_violin \
      kTrigger, kFrequency, 0.46, kSpeed, 0.12, \
      0, 0, 0, 0, 0, 3, giViolin
  gaDryLeft += aLeft
  gaDryRight += aRight
endin

instr OpenString
  kTime timeinsts
  kTrigger = kTime < $DIAG_OPEN_HOLD_SECONDS ? 1 : 0
  aLeft, aRight hlolli_wg_violin \
      kTrigger, $DIAG_FREQUENCY, $DIAG_FORCE, $DIAG_SPEED, $DIAG_POSITION, \
      0, 0, 0, 0, 0, $DIAG_STRING, giViolin
  gaDryLeft += aLeft
  gaDryRight += aRight
endin

instr Body
  aLeft, aRight hlolli_wg_violin_resonance giViolin, $DIAG_BODY, 0, 0
  gaWetLeft += aLeft
  gaWetRight += aRight
endin

instr Master
  aDelayedLeft delay gaDryLeft, max(1, $DIAG_DIRECT_DELAY_SAMPLES) / sr
  aDelayedRight delay gaDryRight, max(1, $DIAG_DIRECT_DELAY_SAMPLES) / sr
  aDirectLeft = $DIAG_DIRECT_DELAY_SAMPLES > 0 ? aDelayedLeft : gaDryLeft
  aDirectRight = $DIAG_DIRECT_DELAY_SAMPLES > 0 ? aDelayedRight : gaDryRight
  outs 0.9 * ($DIAG_DIRECT_GAIN * aDirectLeft + \
                  $DIAG_BODY_GAIN * gaWetLeft), \
       0.9 * ($DIAG_DIRECT_GAIN * aDirectRight + \
                  $DIAG_BODY_GAIN * gaWetRight)
  clear gaDryLeft, gaDryRight, gaWetLeft, gaWetRight
endin

instr Schedule
  iOk hlolli_wg_violin_test_diagnostic_gains \
      giViolin, $DIAG_STRING, $DIAG_FINGER_GAIN, $DIAG_BOARD_GAIN, \
      $DIAG_ROSIN_GAIN, $DIAG_MECHANICAL_GAIN, \
      $DIAG_NUT_CUTOFF_SCALE, $DIAG_BRIDGE_CUTOFF_SCALE
  if iOk != 1 then
    prints "could not set realism diagnostic gains\n"
    turnoff
  endif
  event_i "i", "Body", 0, $DIAG_TOTAL_SECONDS
  event_i "i", "Master", 0, $DIAG_TOTAL_SECONDS
  if strcmp("$DIAG_MODE", "open") == 0 then
    event_i "i", "OpenString", 0.20, $DIAG_TOTAL_SECONDS - 0.20
  else
    event_i "i", "Phrase", 0.20, 3.40
  endif
endin

</CsInstruments>
<CsScore>
i "Schedule" 0 0.001
e
</CsScore>
</CsoundSynthesizer>
