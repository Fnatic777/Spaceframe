###############################################################################
#	WarpHold.py
#
#	Spaceframe AutoFire: hold fire on a target doing an in-system warp (the
#	enemy "intercept" speed boost), and for WarpHoldGrace seconds after it
#	ends: its velocity is far off its normal one and the lead prediction is
#	stale. Auto Fire only (ArcScore with bNeedReady); the player's manual
#	fire is never affected.
#
#	Held(pTarget) is called by AutoFire's ArcScore for every candidate it
#	scores, so a warp is seen at least once per Auto Fire cycle.
#
#	Settings live in AutoFire (g_bHoldOnWarp, g_fWarpGrace), read through
#	the AutoFire module object (AF()).
#
#	Written for Python 1.5.2: no "+=", no list comprehensions, no
#	True/False, no string methods.
###############################################################################
import App
import sys

g_dWarp = {}	# target ID -> game time the warp was last seen
g_dLog = {}	# target ID -> game time of the last debug line


def AF():
	import Custom.Spaceframe.Modules.AutoFire.AutoFire
	return Custom.Spaceframe.Modules.AutoFire.AutoFire


def Reset():
	global g_dWarp, g_dLog
	g_dWarp = {}
	g_dLog = {}


def IsWarping(pTarget):
	# 1 while the target is doing an in-system warp; method missing or any error: 0.
	try:
		if pTarget.IsDoingInSystemWarp():
			return 1
	except:
		pass
	return 0


def Prune(fNow, fGrace):
	# Forget warps whose grace is long over (the dict never grows without bound).
	global g_dWarp
	if len(g_dWarp) < 16:
		return
	for iKey in g_dWarp.keys():
		if fNow - g_dWarp[iKey] > fGrace + 10.0:
			del g_dWarp[iKey]
	if len(g_dLog) > 64:
		Reset2()


def Reset2():
	global g_dLog
	g_dLog = {}


def SpeedRatio(pTarget):
	# Velocity length / impulse max speed, or None when unreadable.
	try:
		fMax = pTarget.GetImpulseEngineSubsystem().GetMaxSpeed()
		if fMax <= 0.0:
			return None
		return pTarget.GetVelocityTG().Length() / fMax
	except:
		return None


def LogHold(pTarget, iTarget, sState, fNow):
	# Debug only, one line per target at most every 2 seconds of game time.
	global g_dLog
	pAF = AF()
	if (not pAF.g_bDebug) or (pAF.g_pCore == None):
		return
	try:
		if g_dLog.has_key(iTarget) and (fNow - g_dLog[iTarget] < 2.0):
			return
		g_dLog[iTarget] = fNow
		sText = "Warp hold: target " + str(iTarget) + " " + sState
		fRatio = SpeedRatio(pTarget)
		if fRatio != None:
			sText = sText + ", speed ratio " + ("%.2f" % fRatio)
		pAF.g_pCore.Log(pAF.NAME, sText)
	except:
		pass


def Held(pTarget):
	# 1 when no weapon should fire at pTarget now: it is warping, or its warp
	# ended less than WarpHoldGrace seconds ago. Any error: 0.
	global g_dWarp
	pAF = AF()
	if not pAF.g_bHoldOnWarp:
		return 0
	try:
		fNow = App.g_kUtopiaModule.GetGameTime()
		iTarget = pTarget.GetObjID()
	except:
		return 0
	fGrace = pAF.g_fWarpGrace
	if fGrace < 0.0:
		fGrace = 0.0
	if IsWarping(pTarget):
		g_dWarp[iTarget] = fNow
		Prune(fNow, fGrace)
		LogHold(pTarget, iTarget, "warping", fNow)
		return 1
	if g_dWarp.has_key(iTarget):
		if fNow - g_dWarp[iTarget] < fGrace:
			LogHold(pTarget, iTarget, "grace", fNow)
			return 1
		del g_dWarp[iTarget]
	return 0
