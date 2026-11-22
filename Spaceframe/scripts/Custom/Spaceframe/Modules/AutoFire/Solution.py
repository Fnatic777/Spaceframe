###############################################################################
#	Solution.py
#
#	Spaceframe AutoFire: geometry helpers of a torpedo tube or pulse weapon
#	against a target (projectile data, lead point, arc depth). No interface
#	here, only the calculation; AutoFire turns it into the arc percent rule.
#
#	The target is predicted where it will be when the projectile arrives,
#	the same way the game's own AI does it (AI/Preprocessors.py,
#	PredictTargetLocation).
#
#	Written for Python 1.5.2: no "+=", no list comprehensions, no
#	True/False, no string methods.
###############################################################################
import App
import math
import sys

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
	# weapon's launch speed, and its projectile's guidance time and lifetime (a
	# pulse-class weapon can fire guided missiles).
	pTorpedoes = App.TorpedoSystem_Cast(pSystem)
	if pTorpedoes != None:
		pAmmo = pTorpedoes.GetCurrentAmmoType()
		fSpeed = float(pAmmo.GetLaunchSpeed())
		tScript = GetScriptInfo(str(pAmmo.GetTorpedoScript()))
		return (fSpeed, tScript[0], tScript[1], tScript[2])
	fLifetime = 0.0
	fGuidance = 0.0
	try:
		sModule = str(pWeapon.GetProperty().GetModuleName())
		tScript = GetScriptInfo(sModule)
		fGuidance = tScript[0]
		fLifetime = tScript[2]
	except:
		pass
	return (float(pWeapon.GetLaunchSpeed()), fGuidance, 0.0, fLifetime)


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


def LeadPoint(pTarget, vOffset, vLaunch, fSpeed):
	# The point the arc rule aims at: where the target (or the chosen
	# subsystem) will be when a projectile of speed fSpeed from vLaunch
	# arrives (three iterations). A new point, in world axes.
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
#	Pulse weapon arc (arc percent rule). Static RE of the game: the arc is a box
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
#	Torpedo tube cone (arc percent rule). The tube's arc is a fixed cone of +-30
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


###############################################################################
#	Cone / ellipse depth (replaces the box depth when the arc shape switch is 1).
#	The engine's arc is a box in two angles, whose corners are further from the
#	centre than the sides. The depth here is measured as one angle from the
#	centre direction of the box, relative to an ellipse inscribed in the box
#	(semi-axes = half the width and height ranges): 0 at the centre, 1 on the
#	boundary, more outside. A symmetric +-30 tube gives exactly angle / 30 deg.
###############################################################################
def Norm3(tV):
	# Unit vector, or None when the vector is (almost) zero.
	fLen = math.sqrt(Dot3(tV, tV))
	if fLen <= 0.000000001:
		return None
	return (tV[0] / fLen, tV[1] / fLen, tV[2] / fLen)


def ConeDepth(tPos, tFwd, tRight, tUp, tPoint, fWmin, fWmax, fHmin, fHmax):
	# Depth of tPoint in the cone/ellipse of a weapon at tPos with axes
	# (tFwd, tRight, tUp) and limits in radians. ARC_BEHIND when the point is
	# behind the weapon (dot with forward <= 0). None when not computable.
	try:
		fA = (fWmax - fWmin) / 2.0
		fB = (fHmax - fHmin) / 2.0
		if (fA <= 0.000001) or (fB <= 0.000001):
			return None
		tDelta = (tPoint[0] - tPos[0], tPoint[1] - tPos[1], tPoint[2] - tPos[2])
		if Dot3(tDelta, tFwd) <= 0.0:
			return ARC_BEHIND
		tF = Norm3(tFwd)
		tR = Norm3(tRight)
		tU = Norm3(tUp)
		tD = Norm3(tDelta)
		if (tF == None) or (tR == None) or (tU == None) or (tD == None):
			return None
		fHc = (fWmax + fWmin) / 2.0
		fVc = (fHmax + fHmin) / 2.0
		fTh = math.tan(fHc)
		fTv = math.tan(fVc)
		tC = Norm3((tF[0] + fTh * tR[0] + fTv * tU[0], tF[1] + fTh * tR[1] + fTv * tU[1], tF[2] + fTh * tR[2] + fTv * tU[2]))
		if tC == None:
			return None
		fRc = Dot3(tR, tC)
		tP1 = Norm3((tR[0] - fRc * tC[0], tR[1] - fRc * tC[1], tR[2] - fRc * tC[2]))
		if tP1 == None:
			return None
		tP2 = (tC[1] * tP1[2] - tC[2] * tP1[1], tC[2] * tP1[0] - tC[0] * tP1[2], tC[0] * tP1[1] - tC[1] * tP1[0])
		if Dot3(tP2, tU) < 0.0:
			tP2 = (-tP2[0], -tP2[1], -tP2[2])
		fCos = Dot3(tD, tC)
		if fCos > 1.0:
			fCos = 1.0
		if fCos < -1.0:
			fCos = -1.0
		fTheta = math.acos(fCos)
		fPhi = math.atan2(Dot3(tD, tP2), Dot3(tD, tP1))
		fCp = math.cos(fPhi) / fA
		fSp = math.sin(fPhi) / fB
		fRadius = 1.0 / math.sqrt(fCp * fCp + fSp * fSp)
		return fTheta / fRadius
	except:
		return None


def TubeConeDepth(tFrame, vPoint):
	# ConeDepth of the torpedo tube cone (+-30 degrees). None on any error.
	if tFrame == None:
		return None
	try:
		return ConeDepth(tFrame[0], tFrame[1], tFrame[2], tFrame[3], Triple(vPoint), -TORP_ARC_HALF, TORP_ARC_HALF, -TORP_ARC_HALF, TORP_ARC_HALF)
	except:
		return None


def ArcConeDepth(pShip, pWeapon, vPoint, sMode=None):
	# ConeDepth of a pulse weapon's own arc limits (axes as ArcDepth). None
	# when anything is unavailable.
	if sMode == None:
		sMode = WEAPON_POSITION
	try:
		tAxes = ArcAxes(pShip, pWeapon)
		tLim = ArcLimits(pWeapon)
		return ConeDepth(Triple(WeaponPosition(pShip, pWeapon, sMode)), Triple(tAxes[0]), Triple(tAxes[1]), Triple(tAxes[2]), Triple(vPoint), tLim[0], tLim[1], tLim[2], tLim[3])
	except:
		return None


def TorpedoArcDepth(pShip, pTube, vPoint):
	# TubeFrame + TubeDepth; None if the frame is unavailable.
	tFrame = TubeFrame(pShip, pTube)
	if tFrame == None:
		return None
	return TubeDepth(tFrame, vPoint)
