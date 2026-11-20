###############################################################################
#	Solution.py
#
#	Spaceframe AutoFire: firing solution score (0 to 100) of a torpedo tube
#	or pulse weapon against a target, the chance-like number Auto Fire uses
#	to decide whether to launch. No interface here, only the calculation.
#
#	The target is predicted where it will be when the projectile arrives,
#	the same way the game's own AI does it (AI/Preprocessors.py,
#	PredictTargetLocation), then:
#	  - aim error: the weapon's direction against the predicted position;
#	  - the projectile's guidance can correct part of that error;
#	  - the target can still manoeuvre away during the flight;
#	  - score = how much of the target's radius the expected miss leaves.
#	Out of reach of the projectile's lifetime, or further off than
#	TubeMaxAngle: 0.
#
#	Written for Python 1.5.2: no "+=", no list comprehensions, no
#	True/False, no string methods.
###############################################################################
import App
import math
import sys

# The calculation's settings, set by AutoFire from its Config.py (each
# described there):
MANEUVER_WEIGHT = 0.1		# TargetEvasion / 100
GUIDANCE_STRENGTH = 1.0		# GuidanceStrength / 100
GUIDANCE_LIMIT = 0.5		# GuidanceLimit / 100
TARGET_SIZE = 1.0		# TargetSize / 100
MAX_ANGLE = 90.0		# TubeMaxAngle, degrees
TORPEDO_RULE = 1		# TorpedoRule: 1 = this score, 2 = firing cone
PULSE_RULE = 1			# PulseRule: the same, for pulse weapons
CONE_FAR = 15.0			# ConeAngleFar, degrees
CONE_NEAR = 45.0		# ConeAngleNear, degrees
CONE_FAR_DISTANCE = 171.0	# ConeFarDistance, in world units
CONE_NEAR_DISTANCE = 29.0	# ConeNearDistance, in world units
PULSE_CONE_FAR = 45.0		# PulseConeAngleFar, degrees
PULSE_CONE_NEAR = 90.0		# PulseConeAngleNear, degrees
PULSE_CONE_FAR_DISTANCE = 171.0	# PulseConeFarDistance, in world units
PULSE_CONE_NEAR_DISTANCE = 29.0	# PulseConeNearDistance, in world units
WEAPON_POSITION = "A"		# ArcDepth weapon position: "A" = pWeapon.GetWorldLocation(), "B" = ship + rotation * pWeapon.GetPosition()
ARC_BEHIND = 99.0		# ArcDepth of a point behind the weapon
TORP_ARC_HALF = 0.5235988	# the torpedo tube cone: +-30 degrees on both axes (fixed in the engine)

g_dScripts = {}		# torpedo script name -> (guidance, turn, lifetime)


def NewPoint(vFrom):
	vPoint = App.TGPoint3()
	vPoint.Set(vFrom)
	return vPoint


def GetScriptInfo(sScript):
	# (guidance lifetime, max angular accel, lifetime or 0 = unlimited)
	# from the projectile's script, e.g. Tactical.Projectiles.Photon1.
	if g_dScripts.has_key(sScript):
		return g_dScripts[sScript]
	fGuidance = 0.0
	fTurn = 0.0
	fLifetime = 0.0
	try:
		__import__(sScript)
		pModule = sys.modules[sScript]
		if hasattr(pModule, "GetGuidanceLifetime"):
			fGuidance = float(pModule.GetGuidanceLifetime())
		if hasattr(pModule, "GetMaxAngularAccel"):
			fTurn = float(pModule.GetMaxAngularAccel())
		if hasattr(pModule, "GetLifetime"):
			fLifetime = float(pModule.GetLifetime())
	except:
		pass
	tInfo = (fGuidance, fTurn, fLifetime)
	g_dScripts[sScript] = tInfo
	return tInfo


def GetProjectileInfo(pWeapon, pSystem):
	# (speed, guidance lifetime, max angular accel, lifetime) of what the
	# weapon fires. Torpedoes: the system's current ammo. Pulse: the
	# weapon's launch speed and its projectile's lifetime, no guidance.
	pTorpedoes = App.TorpedoSystem_Cast(pSystem)
	if pTorpedoes != None:
		pAmmo = pTorpedoes.GetCurrentAmmoType()
		fSpeed = float(pAmmo.GetLaunchSpeed())
		tScript = GetScriptInfo(str(pAmmo.GetTorpedoScript()))
		return (fSpeed, tScript[0], tScript[1], tScript[2])
	fLifetime = 0.0
	try:
		sModule = str(pWeapon.GetProperty().GetModuleName())
		fLifetime = GetScriptInfo(sModule)[2]
	except:
		pass
	return (float(pWeapon.GetLaunchSpeed()), 0.0, 0.0, fLifetime)


def PredictPosition(pTarget, vOffset, fTime):
	# Where the target (or the chosen subsystem, vOffset in the target's
	# own axes) will be in fTime seconds. Without the game's prediction:
	# where it is now.
	vPosition = pTarget.GetWorldLocation()
	try:
		pPhysics = App.PhysicsObjectClass_Cast(pTarget)
		if pPhysics != None:
			vPredicted = pPhysics.GetPredictedPosition(pTarget.GetWorldLocation(), pPhysics.GetVelocityTG(), pPhysics.GetAccelerationTG(), fTime)
			vPosition.Set(vPredicted)
	except:
		pass
	if vOffset != None:
		try:
			vSubsystem = NewPoint(vOffset)
			vSubsystem.MultMatrixLeft(pTarget.GetWorldRotation())
			vPosition.Add(vSubsystem)
		except:
			pass
	return vPosition


def GetTargetAccel(pTarget):
	# The target's top acceleration (0 if unknown: taken as not dodging).
	try:
		pEngines = pTarget.GetImpulseEngineSubsystem()
		if pEngines != None:
			return float(pEngines.GetMaxAccel())
	except:
		pass
	return 0.0


def ScoreValues(fDistance, fAngle, fSpeed, fGuidance, fTurn, fLifetime, fAccel, fRadius):
	# The score from plain numbers (angle in radians).
	if (fSpeed <= 0.0) or (fRadius <= 0.0):
		return 0.0
	if fAngle > MAX_ANGLE * App.PI / 180.0:
		return 0.0
	fTime = fDistance / fSpeed
	if (fLifetime > 0.0) and (fTime > fLifetime):
		return 0.0
	# How far beside the target the shot would pass, aimed as it is
	# (pointing 90 degrees or more away: the whole distance).
	if fAngle >= App.PI * 0.5:
		fMiss = fDistance
	else:
		fMiss = fDistance * math.sin(fAngle)
	# How much of that the guidance can steer back.
	fGuided = fGuidance
	if fGuided > fTime:
		fGuided = fTime
	fCorrection = GUIDANCE_STRENGTH * fSpeed * 0.5 * fTurn * fGuided * fGuided
	if fCorrection > fDistance * GUIDANCE_LIMIT:
		fCorrection = fDistance * GUIDANCE_LIMIT
	fMiss = fMiss - fCorrection
	if fMiss < 0.0:
		fMiss = 0.0
	# How far the target can get away during the flight.
	fDodge = MANEUVER_WEIGHT * 0.5 * fAccel * fTime * fTime
	fError = math.sqrt(fMiss * fMiss + fDodge * fDodge)
	fRadius = fRadius * TARGET_SIZE
	if fRadius <= 0.0:
		return 0.0
	fScore = 100.0 * (1.0 - fError / fRadius)
	if fScore < 0.0:
		fScore = 0.0
	if fScore > 100.0:
		fScore = 100.0
	return fScore


def ConeScore(fDistance, fAngle, fSpeed, fLifetime, bPulse):
	# Firing cone, the way the game's own AI decides (AI/Preprocessors.py,
	# CheckGoodShot): a tube fires when the predicted target is within an
	# angle of where it points. The cone opens from CONE_FAR (at
	# CONE_FAR_DISTANCE and beyond) to CONE_NEAR (at CONE_NEAR_DISTANCE and
	# closer); pulse weapons have their own (PULSE_CONE_*). Inside: 1 (at
	# the edge) to 100 (dead centre); outside: 0.
	if fSpeed <= 0.0:
		return 0.0
	if (fLifetime > 0.0) and (fDistance / fSpeed > fLifetime):
		return 0.0
	if bPulse:
		tCone = (PULSE_CONE_FAR, PULSE_CONE_NEAR, PULSE_CONE_FAR_DISTANCE, PULSE_CONE_NEAR_DISTANCE)
	else:
		tCone = (CONE_FAR, CONE_NEAR, CONE_FAR_DISTANCE, CONE_NEAR_DISTANCE)
	if fDistance <= tCone[3]:
		fAllowed = tCone[1]
	elif fDistance >= tCone[2]:
		fAllowed = tCone[0]
	else:
		fShare = (fDistance - tCone[3]) / (tCone[2] - tCone[3])
		fAllowed = tCone[1] + (tCone[0] - tCone[1]) * fShare
	fAllowed = fAllowed * App.PI / 180.0
	if (fAllowed <= 0.0) or (fAngle > fAllowed):
		return 0.0
	return 1.0 + 99.0 * (1.0 - fAngle / fAllowed)


def Score(pShip, pTarget, vOffset, pWeapon, vDirection, tInfo, iRule=None, bPulse=0):
	# Score of a weapon (pointing along vDirection, in world axes) against
	# the target; tInfo from GetProjectileInfo. vDirection None: a weapon
	# that aims itself (pulse cannon inside its arc), no aim error. iRule:
	# 1 = firing solution, 2 = firing cone (needs vDirection); None = the
	# torpedo rule. bPulse: use the pulse weapons' cone.
	if iRule == None:
		iRule = TORPEDO_RULE
	fSpeed = tInfo[0]
	if fSpeed <= 0.0:
		return 0.0
	vLaunch = pWeapon.GetWorldLocation()
	# Flight time to where the target is, then once more to where it will be.
	vTo = PredictPosition(pTarget, vOffset, 0.0)
	vTo.Subtract(vLaunch)
	fTime = vTo.Length() / fSpeed
	vTo = PredictPosition(pTarget, vOffset, fTime)
	vTo.Subtract(vLaunch)
	fTime = vTo.Length() / fSpeed
	vTo = PredictPosition(pTarget, vOffset, fTime)
	vTo.Subtract(vLaunch)
	fDistance = vTo.Unitize()
	fAngle = 0.0
	if vDirection != None:
		vAim = NewPoint(vDirection)
		vAim.Unitize()
		fDot = vTo.Dot(vAim)
		if fDot > 1.0:
			fDot = 1.0
		if fDot < -1.0:
			fDot = -1.0
		fAngle = math.acos(fDot)
		if iRule == 2:
			return ConeScore(fDistance, fAngle, fSpeed, tInfo[3], bPulse)
	return ScoreValues(fDistance, fAngle, fSpeed, tInfo[1], tInfo[2], tInfo[3], GetTargetAccel(pTarget), pTarget.GetRadius())


def LeadPoint(pTarget, vOffset, vLaunch, fSpeed):
	# The point Score() aims at: where the target (or the chosen subsystem)
	# will be when a projectile of speed fSpeed from vLaunch arrives (same
	# iteration as Score). A new point, in world axes.
	vPoint = PredictPosition(pTarget, vOffset, 0.0)
	if fSpeed <= 0.0:
		return vPoint
	for i in range(3):
		vTo = NewPoint(vPoint)
		vTo.Subtract(vLaunch)
		fTime = vTo.Length() / fSpeed
		vPoint = PredictPosition(pTarget, vOffset, fTime)
	return vPoint


###############################################################################
#	Pulse weapon arc (PulseRule 3). Static RE of the game: the arc is a box
#	in two angles (radians), inside when dot(D, forward) > 0 and
#	WidthMin <= atan2(D.right, D.forward) <= WidthMax and the same for the
#	height with up; D = point - weapon position, axes in world space.
###############################################################################
def Rotate(pShip, vLocal):
	# vLocal (ship axes) into world axes: a copy, the ship's world rotation
	# applied as PredictPosition does for the subsystem offset.
	vWorld = NewPoint(vLocal)
	vWorld.MultMatrixLeft(pShip.GetWorldRotation())
	return vWorld


def WeaponPosition(pShip, pWeapon, sMode):
	# A new point: where the weapon is, in the world. "A" = the weapon's own
	# GetWorldLocation(); "B" = the ship's location plus the weapon's local
	# position rotated by the ship (the engine's own formula, by static RE).
	if sMode == "B":
		vWorld = NewPoint(pShip.GetWorldLocation())
		vWorld.Add(Rotate(pShip, pWeapon.GetPosition()))
		return vWorld
	return NewPoint(pWeapon.GetWorldLocation())


def ArcAxes(pShip, pWeapon):
	# (forward, right, up) of the weapon's arc in world axes.
	pProp = pWeapon.GetProperty()
	try:
		pCast = App.PulseWeaponProperty_Cast(pProp)
		if pCast != None:
			pProp = pCast
	except:
		pass
	return (Rotate(pShip, pProp.GetOrientationForward()), Rotate(pShip, pProp.GetOrientationRight()), Rotate(pShip, pProp.GetOrientationUp()))


def ArcLimits(pWeapon):
	# (width min, width max, height min, height max) in radians. Min and Max
	# are read apart: the combined getters use out pointers.
	return (float(pWeapon.GetArcWidthAngleMin()), float(pWeapon.GetArcWidthAngleMax()), float(pWeapon.GetArcHeightAngleMin()), float(pWeapon.GetArcHeightAngleMax()))


def AxisDepth(fAngle, fMin, fMax):
	# 0 at the middle of [fMin, fMax], 1 at either end, more outside.
	fHalf = (fMax - fMin) / 2.0
	fMid = (fMax + fMin) / 2.0
	if fHalf <= 0.000001:
		if abs(fAngle - fMid) <= 0.000001:
			return 0.0
		return ARC_BEHIND
	return abs(fAngle - fMid) / fHalf


def ArcDepth(pShip, pWeapon, vPoint, sMode=None):
	# How deep the world point vPoint is inside the pulse weapon's arc: 0 at
	# the centre, 1 at the edge (inside iff <= 1), ARC_BEHIND (99.0) when
	# the point is behind the weapon (dot with forward <= 0). None when
	# anything is unavailable (the caller falls back to IsInArc).
	if sMode == None:
		sMode = WEAPON_POSITION
	try:
		vDelta = NewPoint(vPoint)
		vDelta.Subtract(WeaponPosition(pShip, pWeapon, sMode))
		tAxes = ArcAxes(pShip, pWeapon)
		tLimits = ArcLimits(pWeapon)
		fForward = vDelta.Dot(tAxes[0])
		if fForward <= 0.0:
			return ARC_BEHIND
		fWidth = math.atan2(vDelta.Dot(tAxes[1]), fForward)
		fHeight = math.atan2(vDelta.Dot(tAxes[2]), fForward)
		return max(AxisDepth(fWidth, tLimits[0], tLimits[1]), AxisDepth(fHeight, tLimits[2], tLimits[3]))
	except:
		return None


###############################################################################
#	Torpedo tube cone (TorpedoRule 3). The tube's arc is a fixed cone of +-30
#	degrees on both axes (confirmed TORPARC model): Fwd = ship rotation *
#	tube.GetDirection(), Right = ship rotation * tube.GetRight(), Up = Right x
#	Fwd (its sign is irrelevant: the cone is symmetric). Pure floats after the
#	frame is read.
###############################################################################
def Triple(vAny):
	# Any vector wrapper -> (x, y, z) floats.
	return (float(vAny.GetX()), float(vAny.GetY()), float(vAny.GetZ()))


def LocalToWorld(pShip, vAny):
	# A tube-local vector into world axes, as a float triple (a fresh TGPoint3,
	# the ship's world rotation applied).
	tLocal = Triple(vAny)
	vPoint = App.TGPoint3()
	vPoint.SetXYZ(tLocal[0], tLocal[1], tLocal[2])
	vPoint.MultMatrixLeft(pShip.GetWorldRotation())
	return Triple(vPoint)


def TubeFrame(pShip, pTube):
	# (position, forward, right, up) of the tube in world axes as float tuples,
	# or None when anything is unavailable.
	try:
		tFwd = LocalToWorld(pShip, pTube.GetDirection())
		tRight = LocalToWorld(pShip, pTube.GetRight())
		tUp = (tRight[1] * tFwd[2] - tRight[2] * tFwd[1],
			tRight[2] * tFwd[0] - tRight[0] * tFwd[2],
			tRight[0] * tFwd[1] - tRight[1] * tFwd[0])
		tPos = Triple(pTube.GetWorldLocation())
		return (tPos, tFwd, tRight, tUp)
	except:
		return None


def Dot3(tA, tB):
	return tA[0] * tB[0] + tA[1] * tB[1] + tA[2] * tB[2]


def TubeDepth(tFrame, vPoint):
	# How deep the world point is inside the tube's cone: 0 at the centre, 1 at
	# the edge (+-30 degrees, the deeper axis counts), ARC_BEHIND when it is
	# behind the tube. None on any error.
	if tFrame == None:
		return None
	try:
		tPoint = Triple(vPoint)
		tDelta = (tPoint[0] - tFrame[0][0], tPoint[1] - tFrame[0][1], tPoint[2] - tFrame[0][2])
		fForward = Dot3(tDelta, tFrame[1])
		if fForward <= 0.0:
			return ARC_BEHIND
		fWidth = math.atan2(Dot3(tDelta, tFrame[2]), fForward)
		fHeight = math.atan2(Dot3(tDelta, tFrame[3]), fForward)
		return max(abs(fWidth), abs(fHeight)) / TORP_ARC_HALF
	except:
		return None


def TorpedoArcDepth(pShip, pTube, vPoint):
	# TubeFrame + TubeDepth; None if the frame is unavailable.
	tFrame = TubeFrame(pShip, pTube)
	if tFrame == None:
		return None
	return TubeDepth(tFrame, vPoint)
