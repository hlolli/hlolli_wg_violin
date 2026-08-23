; Shared bow and pitch controls for the Bach Chaconne demo and its test.
; Plain slurs keep the rail alive, but they do not turn written notes into
; portamento. A three-millisecond half-time keeps the handoff smooth without
; a long audible pitch bend.
opcode HlolBachPitchTransition, k, kk
  kTarget, kLegato xin
  kHalfTime = 0.001
  if kLegato != 0 then
    kHalfTime = 0.003
  endif
  kFrequency portk kTarget, kHalfTime
  xout kFrequency
endop

; Phase is clamped to one stroke. Chord size is the written onset size.
opcode HlolBachStrokeShape, kkk, ki
  kPhase, iChordSize xin
  kPhase limit kPhase, 0, 1
  kShape = kPhase * kPhase * kPhase * \
      (10 + kPhase * (-15 + 6 * kPhase))
  kShoulder = sin(3.141592653589793 * kPhase)
  kShoulder *= kShoulder

  if iChordSize > 1 then
    ; The bow catches, pushes through the middle, then unloads before the
    ; next stroke. The small shoulder bends the path without a level control.
    kContact = 0.98 - 0.23 * kShape + 0.05 * kShoulder
    kForce = 1.10 - 0.15 * kShape + 0.07 * kShoulder
    kSpeed = 1.05 - 0.08 * kShape + 0.07 * kShoulder
  else
    kContact = 1.00
    kForce = 1.00
    kSpeed = 1.00
  endif

  kContact limit kContact, 0.10, 1.00
  kForce limit kForce, 0.50, 1.20
  kSpeed limit kSpeed, 0.50, 1.20
  xout kContact, kForce, kSpeed
endop

opcode HlolBachChordContact, k, iiii
  iDuration, iChordSize, iChordRank, iLead xin
  if iChordSize <= 1 then
    kContact init 1
  else
    iRollSpan = min(0.650, iDuration * 0.45)
    iUpperPlane = iChordSize > 2 && iChordRank < iChordSize - 2 ? 1 : 0
    iDelay = iUpperPlane * iRollSpan
    iAvailable = max(0.001, iDuration - iDelay)
    iAttack = min(0.008, iAvailable * 0.16)
    if iLead != 0 then
      iHold = max(0.001, iAvailable - iAttack)
      if iDelay > 0 then
        kContact linseg 0, iDelay, 0, iAttack, 1, iHold, 1
      else
        kContact linseg 0, iAttack, 1, iHold, 1
      endif
    else
      iMinimumSound = min(0.850, max(max(0.105, iDuration * 0.18), \
          iRollSpan + 0.180))
      iSound = min(iMinimumSound, iAvailable * 0.75)
      iHold = max(0.001, (iSound - iAttack) * 0.24)
      iRelease = max(0.001, iSound - iAttack - iHold)
      iRest = max(0.001, iAvailable - iSound)
      if iDelay > 0 then
        kContact linseg 0, iDelay, 0, iAttack, 1, iHold, 0.82, \
            iRelease, 0, iRest, 0
      else
        kContact linseg 0, iAttack, 1, iHold, 0.82, iRelease, 0, \
            iRest, 0
      endif
    endif
  endif
  xout kContact
endop
