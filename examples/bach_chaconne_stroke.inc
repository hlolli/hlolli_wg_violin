; Shared bow and pitch controls for the Bach Chaconne demo and its test.
; A 1 ms half-time lets each pitch settle quickly under a continuous bow.
opcode HlolBachPitchTransition, k, k
  kTarget xin
  kFrequency portk kTarget, 0.001
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

opcode HlolBachBowTravel, k, kiiiii
  kElapsed, iOffset, iSpan, iJoined, iSlope, iBend xin
  kTravel = 1
  if iSpan > 0 then
    kPhase limit (iOffset + kElapsed) / iSpan, 0, 1
    if iJoined != 0 then
      kX = 2 * kPhase - 1
      kDb limit iSlope * kX + iBend * (2 * kX * kX - 0.6666666667), -4, 4
      kTravel = exp(log(10) * kDb / 20)
    else
      iDepth limit (iSpan - 0.22) / 0.48, 0, 1
      if kPhase < 0.42 then
        kShape = kPhase / 0.42
        kShape = kShape * kShape * (3 - 2 * kShape)
        kSpeed = 0.88 + 0.36 * kShape
      else
        kShape = (kPhase - 0.42) / 0.58
        kShape = kShape * kShape * (3 - 2 * kShape)
        kSpeed = 1.24 - 0.58 * kShape
      endif
      kTravel = 1 + iDepth * (kSpeed - 1)
    endif
  endif
  xout kTravel
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
