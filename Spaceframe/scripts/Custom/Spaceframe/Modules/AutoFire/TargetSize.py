###############################################################################
#	TargetSize.py
#
#	Spaceframe AutoFire: stretches the flight-time limit (rule 2) for targets
#	that cannot get out of the way of a long shot: large, slow to accelerate,
#	or without working impulse engines. It judges what the target CAN do, not
#	what it is doing now, and never goes below the configured limit.
#
#	The time is the one the target needs to move its own radius (scaled by
#	TargetSizeAllowance) from standstill at its current best acceleration:
#		T = sqrt(2 * allowance / 100 * radius / acceleration)
#	capped at TargetSizeFlightTimeMax. No impulse engines or no acceleration:
#	the cap. FlightBlocked (AutoFire.py) adds the guidance time and applies
#	the projectile's lifetime.
#
#	Settings live in AutoFire (g_fSizeAllowance, g_fSizeFtMax), read through
#	the AutoFire module object (AF()).
#
#	Written for Python 1.5.2: no "+=", no list comprehensions, no
#	True/False, no string methods.
###############################################################################
import math

MIN_ACCEL = 0.01	# at or below this the target counts as unable to move (game units / s2)


def AF():
	import Custom.Spaceframe.Modules.AutoFire.AutoFire
	return Custom.Spaceframe.Modules.AutoFire.AutoFire


def Extend(pTarget, fBase):
	# (limit, radius, acceleration) for a shot at pTarget whose configured limit
	# is fBase seconds. limit >= fBase always. radius (game units) is None when
	# the rule is off or the target cannot be read; acceleration is None when the
	# target has no impulse engine subsystem. Any error: (fBase, None, None).
	try:
		pAF = AF()
		fAllowance = pAF.g_fSizeAllowance
		fMax = pAF.g_fSizeFtMax
		if (fAllowance <= 0.0) or (fMax <= 0.0):
			return (fBase, None, None)
		fRadius = float(pTarget.GetRadius())
		pEngines = pTarget.GetImpulseEngineSubsystem()
		fAccel = None
		if pEngines != None:
			fAccel = float(pEngines.GetCurMaxAccel())
		fTime = 0.0
		if fRadius > 0.0:
			if (fAccel == None) or (fAccel <= MIN_ACCEL):
				fTime = fMax
			else:
				fTime = math.sqrt(2.0 * (fAllowance / 100.0) * fRadius / fAccel)
				if fTime > fMax:
					fTime = fMax
		if fTime < fBase:
			fTime = fBase
		return (fTime, fRadius, fAccel)
	except:
		return (fBase, None, None)
