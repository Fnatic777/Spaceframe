###############################################################################
#	TorpDiag.py
#
#	Spaceframe AutoFire: the torpedo and pulse launch diagnostics (Debug
#	only). One log line per launch of our own guided torpedo (target, aim,
#	motion, tube angles), one per unguided bolt, and a follow-up of each
#	torpedo until it ends (hit or miss). Nothing here fires or decides:
#	AutoFire calls it from the launch event handler, from FireCycle and from
#	Stop.
#
#	State owned by AutoFire (g_pCore, g_iShipID, g_bDebug, the shared
#	helpers) is read through the AutoFire module object (AF()), never copied.
#
#	Written for Python 1.5.2: no "+=", no list comprehensions, no
#	True/False, no string methods.
###############################################################################
import App
import math
import sys

g_dPulseLast = {}	# module name -> game time of its last pulse launch line
g_iPulseLines = 0	# pulse launch lines written this session (max 80)
g_lTorpWatch = []	# [ID, target, launch time, min dist, last dist, last time, grew, last target, radius, module, time the target was gone or None, predicted point or None, predicted flight time, target velocity at launch, sample at the predicted arrival or None, seconds after launch when the min dist was last lowered or None] being followed
g_bTorpLookup = 0	# 1 once Torpedo_GetObjectByID failed (logged once)
g_lTorpList = None	# [head ID or None, secondary IDs, game time] of the torpedo group's list


def AF():
	# The AutoFire module (lazy import: AutoFire imports this module lazily too).
	import Custom.Spaceframe.Modules.AutoFire.AutoFire
	return Custom.Spaceframe.Modules.AutoFire.AutoFire


def GetSolution():
	return AF().GetSolution()


def KmPerUnit():
	return AF().KmPerUnit()


def AngleDeg3(tA, tB):
	return AF().AngleDeg3(tA, tB)


def BoxAngles(tPos, tFwd, tRight, tUp, tPoint):
	return AF().BoxAngles(tPos, tFwd, tRight, tUp, tPoint)


def WeaponReady(pWeapon, sKind):
	return AF().WeaponReady(pWeapon, sKind)


def Reset():
	# Forgets everything remembered (called by AutoFire's Stop).
	global g_lTorpList, g_lTorpWatch, g_dPulseLast, g_iPulseLines
	g_lTorpList = None
	g_lTorpWatch = []
	g_dPulseLast = {}
	g_iPulseLines = 0


def NoteTorpList(pSystem, iHead, lSec):
	# Remembers the torpedo group's target list (iHead None = emptied by
	# StopFiring) and when it changed, for the launch log (OnTorpedoLaunched).
	global g_lTorpList
	if not AF().g_bDebug:
		return
	if App.TorpedoSystem_Cast(pSystem) == None:
		return
	fNow = 0.0
	try:
		fNow = App.g_kUtopiaModule.GetGameTime()
	except:
		pass
	lIDs = []
	if lSec:
		lIDs = list(lSec)
	g_lTorpList = [iHead, lIDs, fNow]


def TorpRange(pTorp):
	# " dist <km>" from the torpedo to its target's centre, as the game shows km.
	try:
		pTarget = App.ShipClass_GetObjectByID(None, pTorp.GetTargetID())
		if pTarget == None:
			return " dist ?"
		vDiff = pTarget.GetWorldLocation()
		vDiff.Subtract(pTorp.GetWorldLocation())
		return " dist %.1f km (%.1f units)" % (vDiff.Length() * KmPerUnit(), vDiff.Length())
	except:
		return " dist ?"


def TorpMeasure(pTorp):
	# (target ID, distance km to the target's centre, target radius km), or None.
	try:
		iTarget = pTorp.GetTargetID()
		pTarget = App.ShipClass_GetObjectByID(None, iTarget)
		if pTarget == None:
			return (iTarget, None, None)
		vDiff = pTarget.GetWorldLocation()
		vDiff.Subtract(pTorp.GetWorldLocation())
		fK = KmPerUnit()
		return (iTarget, vDiff.Length() * fK, pTarget.GetRadius() * fK)
	except:
		return None


def TorpAim(pTorp):
	# " aim <deg> deg (<pct>% of the 30 degree cone)": the angle between the
	# torpedo's heading at launch and the direction to its target's centre.
	try:
		pTarget = App.ShipClass_GetObjectByID(None, pTorp.GetTargetID())
		if pTarget == None:
			return ""
		pSolution = GetSolution()
		tFwd = pSolution.Triple(pTorp.GetWorldForwardTG())
		tTarget = pSolution.Triple(pTarget.GetWorldLocation())
		tFrom = pSolution.Triple(pTorp.GetWorldLocation())
		tDir = (tTarget[0] - tFrom[0], tTarget[1] - tFrom[1], tTarget[2] - tFrom[2])
		fLen = math.sqrt(pSolution.Dot3(tDir, tDir)) * math.sqrt(pSolution.Dot3(tFwd, tFwd))
		if fLen <= 0.0:
			return ""
		fCos = pSolution.Dot3(tDir, tFwd) / fLen
		if fCos > 1.0:
			fCos = 1.0
		if fCos < -1.0:
			fCos = -1.0
		fDeg = math.acos(fCos) * 180.0 / math.pi
		return " aim %.1f deg (%d%% of cone)" % (fDeg, int(fDeg * 100.0 / 30.0 + 0.5))
	except:
		return " aim ?"


def TorpMotion(pTorp):
	# " tgt <km/s> closing <km/s> lateral <km/s> own <km/s> proj <km/s> ft <s> drift <km>":
	# the target's speed, how fast it closes on the shooter along the line of sight, its sideways
	# speed against that line (both relative to our ship), our own speed, the projectile's speed,
	# the estimated flight time and the sideways drift expected over it (lateral x flight time).
	# "vel" = angle between the projectile's velocity and the direction to the target at launch.
	try:
		pTarget = App.ShipClass_GetObjectByID(None, pTorp.GetTargetID())
		pOwn = App.ShipClass_GetObjectByID(None, AF().g_iShipID)
		if (pTarget == None) or (pOwn == None):
			return ""
		pSolution = GetSolution()
		fK = KmPerUnit()
		tT = pSolution.Triple(pTarget.GetVelocityTG())
		tO = pSolution.Triple(pOwn.GetVelocityTG())
		tRel = (tT[0] - tO[0], tT[1] - tO[1], tT[2] - tO[2])
		tFrom = pSolution.Triple(pTorp.GetWorldLocation())
		tTo = pSolution.Triple(pTarget.GetWorldLocation())
		tDir = (tTo[0] - tFrom[0], tTo[1] - tFrom[1], tTo[2] - tFrom[2])
		fDist = math.sqrt(pSolution.Dot3(tDir, tDir))
		if fDist <= 0.0:
			return ""
		tU = (tDir[0] / fDist, tDir[1] / fDist, tDir[2] / fDist)
		fAlong = pSolution.Dot3(tRel, tU)
		fLat = pSolution.Dot3(tRel, tRel) - fAlong * fAlong
		if fLat < 0.0:
			fLat = 0.0
		fLat = math.sqrt(fLat)
		fProj = 0.0
		try:
			tP = pSolution.Triple(pTorp.GetVelocityTG())
			fProj = math.sqrt(pSolution.Dot3(tP, tP))
		except:
			pass
		sText = " tgt %.2f km/s closing %.2f km/s lateral %.2f km/s own %.2f km/s" % (math.sqrt(pSolution.Dot3(tT, tT)) * fK, -fAlong * fK, fLat * fK, math.sqrt(pSolution.Dot3(tO, tO)) * fK)
		if fProj > 0.0:
			fFlight = fDist / fProj
			sText = sText + " proj %.1f km/s ft %.2f s drift %.2f km" % (fProj * fK, fFlight, fLat * fFlight * fK)
			# Angle between the projectile's velocity (its real direction of flight) and the
			# direction to the target, at the moment it appears.
			fCosV = pSolution.Dot3(tP, tU) / fProj
			if fCosV > 1.0:
				fCosV = 1.0
			if fCosV < -1.0:
				fCosV = -1.0
			sText = sText + " vel %.1f deg" % (math.acos(fCosV) * 180.0 / math.pi)
		else:
			sText = sText + " proj ?"
		return sText
	except:
		return " motion ?"


def Dist3(tA, tB):
	# Distance between two (x, y, z) triples, game units.
	fX = tA[0] - tB[0]
	fY = tA[1] - tB[1]
	fZ = tA[2] - tB[2]
	return math.sqrt(fX * fX + fY * fY + fZ * fZ)


def TorpPrediction(pTorp):
	# What the aim assumed at launch, to compare with what happened:
	# (predicted point (x, y, z) in game units, predicted flight time in s, the target's velocity
	# (x, y, z)), the point being where the target is predicted to be when a projectile of the
	# torpedo's real speed arrives. None when anything is unavailable.
	try:
		pTarget = App.ShipClass_GetObjectByID(None, pTorp.GetTargetID())
		if pTarget == None:
			return None
		pSolution = GetSolution()
		tP = pSolution.Triple(pTorp.GetVelocityTG())
		fProj = math.sqrt(pSolution.Dot3(tP, tP))
		if fProj <= 0.0:
			return None
		vFrom = pTorp.GetWorldLocation()
		tPoint = pSolution.Triple(pSolution.LeadPoint(pTarget, None, vFrom, fProj))
		fFlight = Dist3(tPoint, pSolution.Triple(vFrom)) / fProj
		return (tPoint, fFlight, pSolution.Triple(pTarget.GetVelocityTG()))
	except:
		return None


def TorpIsGuided(pTorp):
	# 0 for projectiles without guidance (pulse, disruptor and similar bolts: guidance
	# lifetime 0), which would only flood the log. 1 when guided, or when the lookup fails.
	try:
		sMod = str(pTorp.GetModuleName())
		if GetSolution().GetScriptInfo(sMod)[0] <= 0.0:
			return 0
	except:
		pass
	return 1


def TorpPointAngle(pTorp, tPoint):
	# " toward-point X.X deg", the angle between the torpedo's real velocity and the
	# direction from the torpedo to the predicted point; " toward-point ?" when unavailable.
	try:
		pSolution = GetSolution()
		tV = pSolution.Triple(pTorp.GetVelocityTG())
		tFrom = pSolution.Triple(pTorp.GetWorldLocation())
		tD = (tPoint[0] - tFrom[0], tPoint[1] - tFrom[1], tPoint[2] - tFrom[2])
		fLenV = math.sqrt(pSolution.Dot3(tV, tV))
		fLenD = math.sqrt(pSolution.Dot3(tD, tD))
		if (fLenV <= 0.000001) or (fLenD <= 0.000001):
			return " toward-point ?"
		fCos = pSolution.Dot3(tV, tD) / (fLenV * fLenD)
		if fCos > 1.0:
			fCos = 1.0
		if fCos < -1.0:
			fCos = -1.0
		return " toward-point %.1f deg" % (math.acos(fCos) * 180.0 / math.pi)
	except:
		return " toward-point ?"


def TorpShipAngles(pTorp, tPoint):
	# " rel-point Y.Y deg own-shift Z.Z deg" to test whether our ship's velocity bends
	# the torpedo's flight. rel-point: angle between (torpedo velocity - ship velocity) and the
	# direction torpedo -> predicted point. own-shift: angle between the torpedo velocity and
	# (torpedo velocity - ship velocity). Each is "?" when unavailable.
	sRel = "?"
	sShift = "?"
	try:
		pSolution = GetSolution()
		pOwn = App.ShipClass_GetObjectByID(None, AF().g_iShipID)
		if pOwn != None:
			tV = pSolution.Triple(pTorp.GetVelocityTG())
			tS = pSolution.Triple(pOwn.GetVelocityTG())
			tR = (tV[0] - tS[0], tV[1] - tS[1], tV[2] - tS[2])
			fShift = AngleDeg3(tV, tR)
			if fShift != None:
				sShift = "%.1f deg" % fShift
			if tPoint != None:
				tFrom = pSolution.Triple(pTorp.GetWorldLocation())
				tD = (tPoint[0] - tFrom[0], tPoint[1] - tFrom[1], tPoint[2] - tFrom[2])
				fRel = AngleDeg3(tR, tD)
				if fRel != None:
					sRel = "%.1f deg" % fRel
	except:
		pass
	return " rel-point " + sRel + " own-shift " + sShift


def TorpSample(lEntry, pTorp, fNow):
	# Keeps, in lEntry[14], the sample taken closest in time to the predicted arrival:
	# (seconds from the predicted arrival, km the target is from the predicted point, km the
	# torpedo is from it or None, km/s the target's velocity changed, degrees its velocity turned).
	try:
		if (len(lEntry) < 15) or (lEntry[11] == None):
			return
		fDt = abs((fNow - lEntry[2]) - lEntry[12])
		if (lEntry[14] != None) and (fDt >= lEntry[14][0]):
			return
		pTarget = App.ShipClass_GetObjectByID(None, lEntry[1])
		if pTarget == None:
			return
		pSolution = GetSolution()
		fK = KmPerUnit()
		fErr = Dist3(pSolution.Triple(pTarget.GetWorldLocation()), lEntry[11]) * fK
		tNow = pSolution.Triple(pTarget.GetVelocityTG())
		fDv = Dist3(tNow, lEntry[13]) * fK
		fTurn = 0.0
		fLenA = math.sqrt(pSolution.Dot3(tNow, tNow))
		fLenB = math.sqrt(pSolution.Dot3(lEntry[13], lEntry[13]))
		if (fLenA > 0.000001) and (fLenB > 0.000001):
			fCos = pSolution.Dot3(tNow, lEntry[13]) / (fLenA * fLenB)
			if fCos > 1.0:
				fCos = 1.0
			if fCos < -1.0:
				fCos = -1.0
			fTurn = math.acos(fCos) * 180.0 / math.pi
		fOff = None
		if pTorp != None:
			fOff = Dist3(pSolution.Triple(pTorp.GetWorldLocation()), lEntry[11]) * fK
		lEntry[14] = (fDt, fErr, fOff, fDv, fTurn)
	except:
		pass


def TargetGone(iTarget):
	# 1 when the ship with this ID no longer exists or is dead or dying (a cloaked
	# ship still counts as there), so a torpedo that flew on after its target died is not a miss.
	try:
		pTarget = App.ShipClass_GetObjectByID(None, iTarget)
		if pTarget == None:
			return 1
		if pTarget.IsDead() or pTarget.IsDying():
			return 1
	except:
		pass
	return 0


def TorpFollowUp():
	# Every cycle, follows each launched torpedo (lookup by ID) and keeps its
	# closest approach and last target. When it disappears, logs how close it got: near the
	# target's radius = a hit, far = a miss; "grew" counts the samples where it moved away.
	global g_lTorpWatch, g_bTorpLookup
	pAF = AF()
	if (not g_lTorpWatch) or (pAF.g_pCore == None):
		return
	fNow = 0.0
	try:
		fNow = App.g_kUtopiaModule.GetGameTime()
	except:
		return
	lKeep = []
	for lEntry in g_lTorpWatch:
		# lEntry: ID, target at launch, launch time, min dist, last dist, last time, grew, last target, radius
		pTorp = None
		bFailed = 0
		try:
			pTorp = App.Torpedo_GetObjectByID(None, lEntry[0])
		except:
			bFailed = 1
			if not g_bTorpLookup:
				g_bTorpLookup = 1
				pAF.g_pCore.Log(pAF.NAME, "Torpedo_GetObjectByID failed: " + str(sys.exc_info()[1]))
		if (lEntry[10] == None) and lEntry[1]:
			if TargetGone(lEntry[1]):
				lEntry[10] = fNow
		if pTorp != None:
			TorpSample(lEntry, pTorp, fNow)
			tM = TorpMeasure(pTorp)
			if tM != None:
				lEntry[7] = tM[0]
				if tM[1] != None:
					if (lEntry[4] != None) and (tM[1] > lEntry[4] + 0.05):
						lEntry[6] = lEntry[6] + 1
					lEntry[4] = tM[1]
					lEntry[5] = fNow
					if (lEntry[3] == None) or (tM[1] < lEntry[3]):
						lEntry[3] = tM[1]
						if len(lEntry) > 15:
							lEntry[15] = fNow - lEntry[2]
					lEntry[8] = tM[2]
			if fNow - lEntry[2] > 10.0:
				pAF.g_pCore.Log(pAF.NAME, "Torpedo " + str(lEntry[0]) + " still flying after 10 s: " + TorpSummary(lEntry, fNow))
			else:
				lKeep.append(lEntry)
		elif not bFailed:
			pAF.g_pCore.Log(pAF.NAME, "Torpedo " + str(lEntry[0]) + " ended: " + TorpSummary(lEntry, fNow))
	g_lTorpWatch = lKeep


def TorpSummary(lEntry, fNow):
	sText = "mod " + lEntry[9] + " flew " + ("%.1f" % (fNow - lEntry[2])) + " s, target " + str(lEntry[7]) + " (launched at " + str(lEntry[1]) + ")"
	if lEntry[3] != None:
		sText = sText + ", closest " + ("%.2f" % lEntry[3]) + " km"
		if lEntry[8] != None:
			sText = sText + " (radius " + ("%.2f" % lEntry[8]) + " km)"
		if (len(lEntry) > 15) and (lEntry[15] != None):
			sText = sText + " at " + ("%.1f" % lEntry[15]) + " s"
		if (len(lEntry) > 14) and (lEntry[11] != None):
			sText = sText + " (predicted arrival " + ("%.1f" % lEntry[12]) + " s)"
		sText = sText + ", last " + ("%.2f" % lEntry[4]) + " km " + ("%.1f" % (fNow - lEntry[5])) + " s before the end, grew " + str(lEntry[6]) + "x"
	if lEntry[10] != None:
		sText = sText + ", target gone " + ("%.1f" % (lEntry[10] - lEntry[2])) + " s after launch (dead or removed)"
	else:
		sText = sText + ", target alive"
	if (len(lEntry) > 14) and (lEntry[11] != None):
		if lEntry[14] == None:
			sText = sText + ", no sample at the predicted arrival (" + ("%.1f" % lEntry[12]) + " s)"
		else:
			tS = lEntry[14]
			sText = sText + ", predicted arrival " + ("%.1f" % lEntry[12]) + " s (sampled " + ("%.2f" % tS[0]) + " s off): target " + ("%.2f" % tS[1]) + " km from the predicted point"
			if tS[2] != None:
				sText = sText + ", torpedo " + ("%.2f" % tS[2]) + " km from it"
			sText = sText + ", target velocity changed " + ("%.2f" % tS[3]) + " km/s, turned " + ("%.1f" % tS[4]) + " deg"
	return sText


def NearestWeapon(pSystem, bTube, tFrom):
	# The child of pSystem (torpedo tube if bTube, else pulse weapon) whose world
	# location is nearest to tFrom (x, y, z); None when there is none.
	pBest = None
	fBest = 0.0
	pSolution = GetSolution()
	for iChild in range(pSystem.GetNumChildSubsystems()):
		pChild = pSystem.GetChildSubsystem(iChild)
		if bTube:
			pWeapon = App.TorpedoTube_Cast(pChild)
		else:
			pWeapon = App.PulseWeapon_Cast(pChild)
		if pWeapon != None:
			try:
				fDist = Dist3(pSolution.Triple(pWeapon.GetWorldLocation()), tFrom)
				if (pBest == None) or (fDist < fBest):
					pBest = pWeapon
					fBest = fDist
			except:
				pass
	return pBest


def TorpTubeAngles(pTorp, tPoint):
	# " tube-h X.X tube-v Y.Y tube-ang Z.Z" for the tube that fired (our torpedo tube
	# nearest to the torpedo's world location) and the predicted point: the signed box angles of
	# the tube's arc test and the 3D angle from the tube's forward. "?" for each when unavailable.
	sOut = " tube-h ? tube-v ? tube-ang ?"
	try:
		if tPoint == None:
			return sOut
		pSolution = GetSolution()
		pOwn = App.ShipClass_GetObjectByID(None, AF().g_iShipID)
		if pOwn == None:
			return sOut
		pTube = NearestWeapon(pOwn.GetTorpedoSystem(), 1, pSolution.Triple(pTorp.GetWorldLocation()))
		if pTube == None:
			return sOut
		tFrame = pSolution.TubeFrame(pOwn, pTube)
		if tFrame == None:
			return sOut
		tAng = BoxAngles(tFrame[0], tFrame[1], tFrame[2], tFrame[3], tPoint)
		if tAng == None:
			return sOut
		return " tube-h %.1f tube-v %.1f tube-ang %.1f" % (tAng[0], tAng[1], tAng[2])
	except:
		return sOut


def EnginePoint(pOwn, pTarget, pTorp):
	# The point the engine's own tube test (TorpedoTube::CanHit) aims at, worked out
	# in script: P' = Ptarget + V*t + 0.5*A*t^2 with t = |Ptarget - Pship| / (|Vship - Vtarget| +
	# launch speed), launch speed = the torpedo's real speed, aim offset dropped. The acceleration
	# term uses GetAccelerationTG (listed in App-index.txt, unconfirmed in game); when it raises
	# the term is dropped. Returns an (x, y, z) triple or None.
	pSolution = GetSolution()
	tP = pSolution.Triple(pTarget.GetWorldLocation())
	tV = pSolution.Triple(pTarget.GetVelocityTG())
	tS = pSolution.Triple(pOwn.GetWorldLocation())
	tVs = pSolution.Triple(pOwn.GetVelocityTG())
	tTorp = pSolution.Triple(pTorp.GetVelocityTG())
	tA = (0.0, 0.0, 0.0)
	try:
		tA = pSolution.Triple(pTarget.GetAccelerationTG())
	except:
		tA = (0.0, 0.0, 0.0)
	fLaunch = math.sqrt(pSolution.Dot3(tTorp, tTorp))
	tRel = (tVs[0] - tV[0], tVs[1] - tV[1], tVs[2] - tV[2])
	fDen = math.sqrt(pSolution.Dot3(tRel, tRel)) + fLaunch
	if fDen <= 0.000001:
		return None
	fT = Dist3(tP, tS) / fDen
	return (tP[0] + tV[0] * fT + 0.5 * tA[0] * fT * fT,
		tP[1] + tV[1] * fT + 0.5 * tA[1] * fT * fT,
		tP[2] + tV[2] * fT + 0.5 * tA[2] * fT * fT)


def TubeEntry(pOwn, pTube, iIndex, bFired, tPoint, tEng, pHit):
	# "<index>[*]:<ang>/<ch>/<eng>" for one tube: ang = 3D angle from the tube's
	# forward to our lead point, ch = pTube.CanHit(target location) as 1/0, eng = the same angle
	# to the engine-style point; "?" for each that is unavailable. Returns (entry text, eng text).
	sAng = "?"
	sEng = "?"
	sHit = "?"
	try:
		tFrame = GetSolution().TubeFrame(pOwn, pTube)
		if tFrame != None:
			if tPoint != None:
				tD = (tPoint[0] - tFrame[0][0], tPoint[1] - tFrame[0][1], tPoint[2] - tFrame[0][2])
				sAng = DegText(AngleDeg3(tFrame[1], tD))
			if tEng != None:
				tD = (tEng[0] - tFrame[0][0], tEng[1] - tFrame[0][1], tEng[2] - tFrame[0][2])
				sEng = DegText(AngleDeg3(tFrame[1], tD))
	except:
		pass
	try:
		if pHit != None:
			iHit = pTube.CanHit(pHit)
			if iHit != None:
				if iHit:
					sHit = "1"
				else:
					sHit = "0"
	except:
		sHit = "?"
	sMark = ""
	if bFired:
		sMark = "*"
	return (str(iIndex) + sMark + ":" + sAng + "/" + sHit + "/" + sEng, sEng)


def TorpTubeDiag(pTorp, tPoint):
	# " eng-ang X.X tubes [ ... ]": the engine-style angle for the tube that fired and
	# one TubeEntry per ready tube of our torpedo system plus the fired one (the tube nearest to
	# the torpedo, marked *), at most 16 entries. Everything "?" on failure; never raises.
	sEng = "?"
	sList = ""
	try:
		pSolution = GetSolution()
		pOwn = App.ShipClass_GetObjectByID(None, AF().g_iShipID)
		pTarget = App.ShipClass_GetObjectByID(None, pTorp.GetTargetID())
		if pOwn != None:
			tEng = None
			pHit = None
			if pTarget != None:
				try:
					tEng = EnginePoint(pOwn, pTarget, pTorp)
				except:
					tEng = None
				try:
					pHit = pTarget.GetWorldLocation()
				except:
					pHit = None
			pSystem = pOwn.GetTorpedoSystem()
			tTorp = pSolution.Triple(pTorp.GetWorldLocation())
			lTubes = []
			iFired = -1
			fBest = 0.0
			for iChild in range(pSystem.GetNumChildSubsystems()):
				pTube = App.TorpedoTube_Cast(pSystem.GetChildSubsystem(iChild))
				if pTube != None:
					lTubes.append((iChild, pTube))
					try:
						fDist = Dist3(pSolution.Triple(pTube.GetWorldLocation()), tTorp)
						if (iFired < 0) or (fDist < fBest):
							iFired = iChild
							fBest = fDist
					except:
						pass
			lPick = []
			for tItem in lTubes:
				if (tItem[0] == iFired) or WeaponReady(tItem[1], "torpedo"):
					lPick.append(tItem)
			while len(lPick) > 16:
				# over the cap: drop the last tube that is not the fired one
				iDrop = len(lPick) - 1
				if lPick[iDrop][0] == iFired:
					iDrop = iDrop - 1
				del lPick[iDrop]
			for tItem in lPick:
				tEntry = TubeEntry(pOwn, tItem[1], tItem[0], tItem[0] == iFired, tPoint, tEng, pHit)
				if tItem[0] == iFired:
					sEng = tEntry[1]
				if sList != "":
					sList = sList + " "
				sList = sList + tEntry[0]
	except:
		pass
	return " eng-ang " + sEng + " tubes [" + sList + "]"


def DegText(fAngle):
	# "12.3" or "?" for None.
	if fAngle == None:
		return "?"
	return "%.1f" % fAngle


def PulseDiag(pTorp):
	# One rate-limited line for an unguided bolt of ours (pulse, disruptor): does it
	# fly along the weapon or toward the target? At most one per module name per second of game
	# time and 80 per session. Each piece is "?" when unavailable.
	global g_dPulseLast, g_iPulseLines
	if g_iPulseLines >= 80:
		return
	pAF = AF()
	sMod = "?"
	try:
		sMod = str(pTorp.GetModuleName())
		iDot = -1
		for i in range(len(sMod)):
			if sMod[i] == ".":
				iDot = i
		sMod = sMod[iDot + 1:]
	except:
		pass
	fNow = 0.0
	try:
		fNow = App.g_kUtopiaModule.GetGameTime()
	except:
		pass
	if g_dPulseLast.has_key(sMod) and (fNow - g_dPulseLast[sMod] < 1.0):
		return
	g_dPulseLast[sMod] = fNow
	g_iPulseLines = g_iPulseLines + 1
	sDist = "?"
	sA = "?"
	sB = "?"
	sC = "?"
	sE = "?"
	sH = "?"
	sV = "?"
	tV = None
	tFrom = None
	tT = None
	tLead = None
	try:
		pSolution = GetSolution()
		tV = pSolution.Triple(pTorp.GetVelocityTG())
		tFrom = pSolution.Triple(pTorp.GetWorldLocation())
		pTarget = App.ShipClass_GetObjectByID(None, pTorp.GetTargetID())
		if pTarget != None:
			tT = pSolution.Triple(pTarget.GetWorldLocation())
			sDist = "%.2f" % (Dist3(tT, tFrom) * KmPerUnit())
			sA = DegText(AngleDeg3(tV, (tT[0] - tFrom[0], tT[1] - tFrom[1], tT[2] - tFrom[2])))
		tPred = TorpPrediction(pTorp)
		if tPred != None:
			tLead = tPred[0]
			sB = DegText(AngleDeg3(tV, (tLead[0] - tFrom[0], tLead[1] - tFrom[1], tLead[2] - tFrom[2])))
	except:
		pass
	try:
		pSolution = GetSolution()
		pOwn = App.ShipClass_GetObjectByID(None, pAF.g_iShipID)
		pWeapon = NearestWeapon(pOwn.GetPulseWeaponSystem(), 0, tFrom)
		if pWeapon != None:
			tAxes = pSolution.ArcAxes(pOwn, pWeapon)
			tFwd = pSolution.Triple(tAxes[0])
			tRight = pSolution.Triple(tAxes[1])
			tUp = pSolution.Triple(tAxes[2])
			tPos = pSolution.Triple(pWeapon.GetWorldLocation())
			if tT != None:
				sC = DegText(AngleDeg3(tFwd, (tT[0] - tPos[0], tT[1] - tPos[1], tT[2] - tPos[2])))
			sE = DegText(AngleDeg3(tV, tFwd))
			if tLead != None:
				tBox = BoxAngles(tPos, tFwd, tRight, tUp, tLead)
				if tBox != None:
					sH = DegText(tBox[0])
					sV = DegText(tBox[1])
	except:
		pass
	pAF.g_pCore.Log(pAF.NAME, "Pulse launched: mod " + sMod + " dist " + sDist + " km vel-target " + sA + " deg vel-point " + sB + " deg weapon-target " + sC + " deg vel-weapon " + sE + " deg w-h " + sH + " deg w-v " + sV + " deg")


def OnTorpedoLaunched(pObject, pEvent):
	# Which target each of our torpedoes was born with, against the list
	# Auto Fire had armed (a torpedo with target 0 or another ID flies without tracking).
	pAF = AF()
	try:
		if pAF.g_bDebug and (pAF.g_pCore != None) and (pAF.g_iShipID != None):
			pTorp = App.Torpedo_Cast(pEvent.GetDestination())
			if (pTorp != None) and (pTorp.GetParentID() == pAF.g_iShipID) and (not TorpIsGuided(pTorp)):
				PulseDiag(pTorp)
			if (pTorp != None) and (pTorp.GetParentID() == pAF.g_iShipID) and TorpIsGuided(pTorp):
				fNow = 0.0
				try:
					fNow = App.g_kUtopiaModule.GetGameTime()
				except:
					pass
				tPred = TorpPrediction(pTorp)
				sText = "Torpedo launched: target " + str(pTorp.GetTargetID())
				if g_lTorpList == None:
					sText = sText + ", no list armed yet"
				else:
					sText = sText + ", list head " + str(g_lTorpList[0]) + " sec " + str(g_lTorpList[1])
					sText = sText + " (set " + ("%.2f" % (fNow - g_lTorpList[2])) + " s ago)"
				sText = sText + TorpRange(pTorp)
				sText = sText + TorpAim(pTorp)
				sText = sText + TorpMotion(pTorp)
				try:
					sText = sText + " mod " + str(pTorp.GetModuleName())
				except:
					sText = sText + " mod ?"
				if tPred == None:
					sText = sText + " toward-point ?" + TorpShipAngles(pTorp, None) + TorpTubeAngles(pTorp, None) + TorpTubeDiag(pTorp, None)
				else:
					sText = sText + TorpPointAngle(pTorp, tPred[0])
					sText = sText + TorpShipAngles(pTorp, tPred[0]) + TorpTubeAngles(pTorp, tPred[0]) + TorpTubeDiag(pTorp, tPred[0])
				sText = sText + pAF.TorpDecisionText(fNow)
				pAF.g_pCore.Log(pAF.NAME, sText)
				if len(g_lTorpWatch) < 60:
					sMod = "?"
					try:
						sMod = str(pTorp.GetModuleName())
					except:
						pass
					if tPred == None:
						tPred = (None, 0.0, None)
					g_lTorpWatch.append([pTorp.GetObjID(), pTorp.GetTargetID(), fNow, None, None, fNow, 0, pTorp.GetTargetID(), None, sMod, None, tPred[0], tPred[1], tPred[2], None, None])
	except:
		if pAF.g_pCore != None:
			pAF.g_pCore.Log(pAF.NAME, "Torpedo event error: " + str(sys.exc_info()[1]))
