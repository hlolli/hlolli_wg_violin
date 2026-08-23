opcode HlolViolinDistance, aaaa, aai
  aLeft, aRight, iMeters xin
  iMeters limit iMeters, 1, 50
  iDelay = max(1 / sr, (iMeters - 1) / 343)
  iCutoff = max(6500, 18000 / sqrt(iMeters))
  iDirectGain = 1 / iMeters
  iRoomGain = 1
  if iMeters > 1 then
    aDelayedLeft delay aLeft, iDelay
    aDelayedRight delay aRight, iDelay
    aDirectLeft butterlp aDelayedLeft, iCutoff
    aDirectRight butterlp aDelayedRight, iCutoff
    aDirectLeft *= iDirectGain
    aDirectRight *= iDirectGain
    aRoomLeft = iRoomGain * aDelayedLeft
    aRoomRight = iRoomGain * aDelayedRight
  else
    aDirectLeft = aLeft
    aDirectRight = aRight
    aRoomLeft = aLeft
    aRoomRight = aRight
  endif
  xout aDirectLeft, aDirectRight, aRoomLeft, aRoomRight
endop
