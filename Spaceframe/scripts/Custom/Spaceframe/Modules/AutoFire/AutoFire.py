###############################################################################
#	AutoFire.py
#
#	Spaceframe module, version 0.5
#
#	Fires the player's weapons by firing-solution rules while switched on,
#	so the player can concentrate on manoeuvring. Only the ship the player
#	controls, and only if it has the AutoFire technology (Ships.py).
#	- Switched on and off with a key (ToggleKey, default L) or with the
#	  "Auto Fire" button in the tactical officer's menu.
#	- Manual fire has priority: while the player holds the fire key of a
#	  weapon group, Auto Fire leaves that group alone.
#	- Phasers by range, arc and charge; torpedoes and pulse weapons by the
#	  arc percent rule (below), torpedoes with automatic spread; torpedoes
#	  and pulse tapped (TapFire).
#	- Torpedo tubes that cannot reach the target fire at secondary targets
#	  they can reach, when Secondary Target allows it (SecondaryTorpedoes).
#	- A phaser group whose banks cannot reach the main target fires at a
#	  secondary target a ready bank reaches, when Secondary Target allows it
#	  (SecondaryPhasers); it returns to the main target as soon as a bank reaches it.
#	- Arc percent rule (PulseRule / TorpedoRule 1 and 2): a weapon fires when
#	  the predicted target point is inside its arc by a percentage that depends
#	  on the distance. Rule 2 (default) adds a flight-time filter: the shot is
#	  held when the estimated flight time exceeds a limit that depends on the
#	  distance. With Secondary Target it also chooses the secondary
#	  targets (here under Auto Fire; for manual fire Secondary Target asks
#	  ArcRuleOn / ArcReaches and only filters the secondaries it adds).
#	- Targets: the player's, the nearest enemy, or each group's best
#	  (TargetMode).
#	Settings: Modules\AutoFire\Config.py
###############################################################################
import App
import math
import sys

NAME = "AutoFire"
VERSION = "0.5"
BUTTON_TEXT = "Auto Fire"

g_pCore = None
g_bArcLogged = 0	# 1 once an IsInArc failure was logged (no per-tick spam)
g_dFtLog = {}		# (target ID, kind, sec) -> game time of the last flight-time log line (Debug only)
g_dSpreadOK = {}	# target ID -> 1 when a tube's shot at it qualifies for spread (set by ArcScore, read by ApplySpread)
g_bFtSpeedLogged = 0	# 1 once an unknown projectile speed was logged (Debug only)
g_iOn = 0		# switched on by the player
g_iShipID = None	# player ship it was switched on for
g_eButton = None	# event type of the menu button (one per game session)
g_iKey = None		# key code of the toggle key (lower case)
g_pTopWindow = None	# window holding the keyboard handler
g_pButton = None	# the menu button
g_pMenu = None		# the tactical menu holding the button
g_pMission = None	# object the broadcast handlers were registered on
g_dManual = {}		# weapon group -> 1 while the player holds its fire key
g_dFiring = {}		# weapon group -> ID of the target Auto Fire is firing it at
g_pTimer = None		# Auto Fire's own timer, only while switched on
g_iFiringShipID = None	# ship whose groups Auto Fire started (the player's)
g_dScore = {}		# weapon group -> last firing solution (torpedoes, pulse)
g_iPlayerSpread = None	# the player's torpedo spread, to go back to
g_iSetSpread = None	# the spread Auto Fire last set
g_iSpreadShipID = None	# ship whose spread Auto Fire changed
g_dArcReady = {}	# (weapon ID, target ID) -> 1 while 'ready' for that target (arc percent hysteresis, pulse and torpedo)
g_dArcSec = {}		# weapon group -> IDs of the secondaries of its last plan (their hysteresis keys survive ArcSettle)
g_dPlanNote = {}	# weapon group -> last plan line logged (Debug only, logged on change)
g_tTorpDecision = None	# Debug only: (game time, target ID, depth percent, allowed percent, 3D angle, h, v, secondary) of the last allowed torpedo tube decision
g_dSecHead = {}		# held torpedo/pulse/phaser group -> ID of the secondary it was started at (no main shot)
g_bTorpPlanLogged = 0	# 1 once a torpedo plan error was logged

# Settings read once by LoadConfig() at Start (the hot path never asks Config).
# Initial values = the defaults, so code run before Start behaves the same.
g_bDebug = 0
g_iTargetMode = 0
g_fPhaserMinCharge = 50.0
g_fPhaserRange = 100.0
g_iTorpedoReserve = 0
g_iTorpedoRule = 2		# 1 = arc percent only, 2 = plus the flight-time filter
g_bHoldOnWarp = 1		# HoldOnWarp (WarpHold.py)
g_fWarpGrace = 1.0		# WarpHoldGrace, seconds
g_fSpreadFtMin = 1.5		# SpreadFlightTimeMin, seconds
g_fSpreadFtMax = 2.5		# SpreadFlightTimeMax, seconds (0 = no upper bound)
g_fSpreadArcPercent = 35.0	# SpreadArcPercent, percent 0-100 (depth*100 limit for a spread shot)
g_fArcFtNear = 0.5		# ArcFlightTimeNear, seconds
g_fArcFtFar = 1.5		# ArcFlightTimeFar, seconds
g_iPulseRule = 2		# same, for pulse weapons
g_iTapFire = 1
g_iSecondaryTorpedoes = 1
g_iSecondaryPhasers = 1
g_fArcFar = 70.0		# PulseArcPercentFar
g_fArcNear = 90.0		# PulseArcPercentNear
g_fArcHysteresis = 10.0		# PulseArcHysteresis, percentage points
g_iTorpArcShape = 1		# TorpedoArcShape: 1 = cone depth, 0 = box depth
g_iPulseArcShape = 1		# PulseArcShape: 1 = ellipse depth, 0 = box depth
g_fTorpArcFar = 70.0		# TorpedoArcPercentFar
g_fTorpArcNear = 90.0		# TorpedoArcPercentNear
g_fTorpArcHysteresis = 10.0	# TorpedoArcHysteresis, percentage points
g_fArcFarSec = 70.0		# PulseArcPercentFarSecondary
g_fArcNearSec = 90.0		# PulseArcPercentNearSecondary
g_fTorpArcFarSec = 70.0		# TorpedoArcPercentFarSecondary
g_fTorpArcNearSec = 90.0	# TorpedoArcPercentNearSecondary
g_fTorpFtLimit = 0.0		# TorpedoFlightTimeLimit, seconds (0 = filter off)
g_fFtLimit = 0.0		# PulseFlightTimeLimit
g_fTorpFtLimitSec = 0.0		# TorpedoFlightTimeLimitSecondary
g_fFtLimitSec = 0.0		# PulseFlightTimeLimitSecondary
ARC_MINIMUM = 1.0	# lowest arc score that fires (any weapon inside the allowed percent)
PULSE_ARC_LIFETIME = 0	# 1 = pulse rule 3 also drops shots beyond the projectile lifetime (off: as before)

KEY_HANDLER = "Custom.Spaceframe.Modules.AutoFire.AutoFire.OnKeyboard"
BUTTON_HANDLER = "Custom.Spaceframe.Modules.AutoFire.AutoFire.OnMenuButton"
MANUAL_HANDLER = "Custom.Spaceframe.Modules.AutoFire.AutoFire.OnManualFire"
TORP_HANDLER = "Custom.Spaceframe.Modules.AutoFire.AutoFire.OnTorpedoLaunched"


def GetConfig():
	import Custom.Spaceframe.Modules.AutoFire.Config
	return Custom.Spaceframe.Modules.AutoFire.Config


def NormRule(pValue):
	# TorpedoRule / PulseRule: 1 stays 1, every other value (also unreadable) is 2.
	try:
		if int(pValue) == 1:
			return 1
	except:
		pass
	return 2


def LoadConfig():
	# Reads every hot-path setting once (same defaults and conversions as
	# the code that used to read them each cycle).
	global g_bDebug, g_iTargetMode, g_fPhaserMinCharge, g_fPhaserRange
	global g_iTorpedoReserve, g_iTorpedoRule
	global g_fSpreadFtMin, g_fSpreadFtMax, g_fArcFtNear, g_fArcFtFar, g_fSpreadArcPercent
	global g_iPulseRule, g_iTapFire, g_bArcLogged, g_dFtLog, g_bFtSpeedLogged
	global g_fTorpFtLimit, g_fFtLimit, g_fTorpFtLimitSec, g_fFtLimitSec
	global g_fArcFar, g_fArcNear, g_fArcHysteresis
	global g_iSecondaryTorpedoes, g_bTorpPlanLogged, g_dPlanNote, g_iSecondaryPhasers
	global g_fTorpArcFar, g_fTorpArcNear, g_fTorpArcHysteresis
	global g_fArcFarSec, g_fArcNearSec
	global g_fTorpArcFarSec, g_fTorpArcNearSec
	global g_iTorpArcShape, g_iPulseArcShape, g_dSpreadOK, g_bHoldOnWarp, g_fWarpGrace
	pConfig = GetConfig()
	g_bHoldOnWarp = int(getattr(pConfig, "HoldOnWarp", 1))
	g_fWarpGrace = float(getattr(pConfig, "WarpHoldGrace", 1.0))
	try:
		GetWarpHold().Reset()
	except:
		pass
	g_dPlanNote = {}
	g_dSpreadOK = {}
	g_fArcFtNear = float(getattr(pConfig, "ArcFlightTimeNear", 0.5))
	g_fArcFtFar = float(getattr(pConfig, "ArcFlightTimeFar", 1.5))
	g_fTorpArcFar = float(getattr(pConfig, "TorpedoArcPercentFar", 70))
	g_fTorpArcNear = float(getattr(pConfig, "TorpedoArcPercentNear", 90))
	g_fTorpArcHysteresis = float(getattr(pConfig, "TorpedoArcHysteresis", 10))
	g_fArcFar = float(getattr(pConfig, "PulseArcPercentFar", 70))
	g_fArcNear = float(getattr(pConfig, "PulseArcPercentNear", 90))
	g_fArcHysteresis = float(getattr(pConfig, "PulseArcHysteresis", 10))
	g_iTorpArcShape = int(getattr(pConfig, "TorpedoArcShape", 1))
	g_iPulseArcShape = int(getattr(pConfig, "PulseArcShape", 1))
	# secondary bands: a missing setting falls back to the main value
	g_fTorpArcFarSec = float(getattr(pConfig, "TorpedoArcPercentFarSecondary", g_fTorpArcFar))
	g_fTorpArcNearSec = float(getattr(pConfig, "TorpedoArcPercentNearSecondary", g_fTorpArcNear))
	g_fArcFarSec = float(getattr(pConfig, "PulseArcPercentFarSecondary", g_fArcFar))
	g_fArcNearSec = float(getattr(pConfig, "PulseArcPercentNearSecondary", g_fArcNear))
	# flight-time limits (seconds, 0 = off); a missing setting = off, a missing secondary one = the primary
	g_fTorpFtLimit = float(getattr(pConfig, "TorpedoFlightTimeLimit", 0))
	g_fFtLimit = float(getattr(pConfig, "PulseFlightTimeLimit", 0))
	g_fTorpFtLimitSec = float(getattr(pConfig, "TorpedoFlightTimeLimitSecondary", g_fTorpFtLimit))
	g_fFtLimitSec = float(getattr(pConfig, "PulseFlightTimeLimitSecondary", g_fFtLimit))
	g_dFtLog = {}
	g_bFtSpeedLogged = 0
	ForgetArc()
	g_iTargetMode = int(getattr(pConfig, "TargetMode", 0))
	g_fPhaserMinCharge = float(getattr(pConfig, "PhaserMinCharge", 50))
	g_fPhaserRange = float(getattr(pConfig, "PhaserRange", 100))
	g_iTorpedoReserve = int(getattr(pConfig, "TorpedoReserve", 0))
	# rule 1 = arc percent only; anything else (2, a legacy 3, ...) = rule 2
	g_iTorpedoRule = NormRule(getattr(pConfig, "TorpedoRule", 2))
	g_fSpreadFtMin = float(getattr(pConfig, "SpreadFlightTimeMin", 1.5))
	g_fSpreadFtMax = float(getattr(pConfig, "SpreadFlightTimeMax", 2.5))
	g_fSpreadArcPercent = float(getattr(pConfig, "SpreadArcPercent", 35))
	g_iPulseRule = NormRule(getattr(pConfig, "PulseRule", 2))
	g_iTapFire = int(getattr(pConfig, "TapFire", 1))
	g_iSecondaryTorpedoes = int(getattr(pConfig, "SecondaryTorpedoes", 1))
	g_iSecondaryPhasers = int(getattr(pConfig, "SecondaryPhasers", 1))
	g_bTorpPlanLogged = 0
	g_bArcLogged = 0
	g_bDebug = 0
	try:
		if g_pCore != None:
			g_bDebug = g_pCore.GetConfigValue("Debug", 0)
	except:
		g_bDebug = 0


def GetPlayer():
	try:
		import MissionLib
		return MissionLib.GetPlayer()
	except:
		return None


def GetMission():
	try:
		pMission = App.Game_GetCurrentGame().GetCurrentEpisode().GetCurrentMission()
		if pMission != None:
			return pMission
	except:
		pass
	return getattr(g_pCore, "g_pMission", None)


def GetFireEvents():
	# (event type, weapon group) pairs of the game's fire keys.
	return ((App.ET_INPUT_FIRE_PRIMARY, App.ShipClass.WG_PRIMARY),
		(App.ET_INPUT_FIRE_SECONDARY, App.ShipClass.WG_SECONDARY),
		(App.ET_INPUT_FIRE_TERTIARY, App.ShipClass.WG_TERTIARY))


###############################################################################
#	State
###############################################################################
def HasTech(pShip):
	if (pShip == None) or (g_pCore == None):
		return 0
	try:
		return g_pCore.GetShipTech(pShip, NAME, 0) != 0
	except:
		return 0


def IsEnabled():
	# 1 while switched on for the ship the player controls now, and that
	# ship has the technology.
	if not g_iOn:
		return 0
	pPlayer = GetPlayer()
	if (pPlayer == None) or (pPlayer.GetObjID() != g_iShipID):
		return 0
	if pPlayer.IsDead() or (not HasTech(pPlayer)):
		return 0
	return 1


def SetEnabled(iOn):
	global g_iOn, g_iShipID
	pPlayer = GetPlayer()
	if iOn and HasTech(pPlayer):
		g_iOn = 1
		g_iShipID = pPlayer.GetObjID()
		StartTimer()
	else:
		g_iOn = 0
		g_iShipID = None
		ForgetArc()
		StopAll()
		RestoreSpread()
		StopTimer()
	UpdateButton()
	if g_pCore != None:
		g_pCore.Log(NAME, "Auto Fire " + str(IsEnabled()))


def Toggle():
	SetEnabled(not IsEnabled())
	# Player feedback (key and menu button only, not the battle start).
	sState = "OFF"
	if IsEnabled():
		sState = "ON"
	try:
		if g_pCore != None:
			g_pCore.ShowNotice("Auto Fire " + sState, 0.12, 2.5)
	except:
		pass


###############################################################################
#	Key and menu button
###############################################################################
def GetKeyCode():
	sKey = str(getattr(GetConfig(), "ToggleKey", "L"))
	if len(sKey) != 1:
		sKey = "L"
	iKey = ord(sKey)
	if (iKey >= 65) and (iKey <= 90):
		iKey = iKey + 32	# the game binds lower-case letters
	return iKey


def BindKey():
	# The key is read straight from the keyboard on the top window, as the
	# game's own BridgeUtils.ModalKeyboardHandler does: the top window sees
	# every key, even while a clicked menu has the focus (a key binding
	# would go to the focused menu and be lost).
	global g_iKey, g_pTopWindow
	g_iKey = GetKeyCode()
	g_pTopWindow = App.TopWindow_GetTopWindow()
	g_pTopWindow.AddPythonFuncHandlerForInstance(App.ET_KEYBOARD, KEY_HANDLER)


def UnbindKey():
	global g_iKey, g_pTopWindow
	if g_pTopWindow != None:
		try:
			g_pTopWindow.RemoveHandlerForInstance(App.ET_KEYBOARD, KEY_HANDLER)
		except:
			pass
	g_pTopWindow = None
	g_iKey = None


def CreateButton():
	global g_eButton, g_pButton, g_pMenu
	if g_eButton == None:
		g_eButton = App.Game_GetNextEventType()
	pMenu = App.TacticalControlWindow_GetTacticalControlWindow().GetTacticalMenu()
	if pMenu == None:
		return
	from Bridge import BridgeUtils
	try:
		pButton = BridgeUtils.CreateBridgeMenuButton(App.TGString(BUTTON_TEXT), g_eButton, 0, pMenu)
	except:
		pEvent = App.TGIntEvent_Create()
		pEvent.SetEventType(g_eButton)
		pEvent.SetDestination(pMenu)
		pButton = App.STButton_Create(BUTTON_TEXT, pEvent)
	try:
		pButton.SetAutoChoose(0)
		pButton.SetChoosable(1)
	except:
		pass
	pMenu.AddChild(pButton)
	pMenu.AddPythonFuncHandlerForInstance(g_eButton, BUTTON_HANDLER)
	g_pButton = pButton
	g_pMenu = pMenu
	UpdateButton()


def DeleteButton():
	global g_pButton, g_pMenu
	if g_pMenu != None:
		try:
			g_pMenu.RemoveHandlerForInstance(g_eButton, BUTTON_HANDLER)
		except:
			pass
		if g_pButton != None:
			try:
				g_pMenu.DeleteChild(g_pButton)
			except:
				pass
	g_pButton = None
	g_pMenu = None


def UpdateButton():
	if g_pButton != None:
		try:
			g_pButton.SetChosen(IsEnabled())
		except:
			pass


def OnKeyboard(pObject, pEvent):
	# Every key passes here: the toggle key (pressed, either case) switches
	# Auto Fire on a ship with the technology and is kept from the game;
	# anything else goes on as normal.
	bMine = 0
	try:
		iChar = pEvent.GetUnicode()
		if (iChar >= 65) and (iChar <= 90):
			iChar = iChar + 32
		if (iChar == g_iKey) and (pEvent.GetKeyState() == App.TGKeyboardEvent.KS_KEYDOWN):
			bMine = HasTech(GetPlayer())
	except:
		bMine = 0
	if not bMine:
		pObject.CallNextHandler(pEvent)
		return
	pEvent.SetHandled()
	try:
		Toggle()
	except:
		if g_pCore != None:
			g_pCore.Log(NAME, "Toggle error: " + str(sys.exc_info()[1]))


def OnMenuButton(pObject, pEvent):
	try:
		Toggle()
	except:
		if g_pCore != None:
			g_pCore.Log(NAME, "Button error: " + str(sys.exc_info()[1]))
	try:
		pObject.CallNextHandler(pEvent)
	except:
		pass


def OnManualFire(pObject, pEvent):
	# Tracks the player's fire keys, so Auto Fire leaves those groups alone.
	# A left click on the menus also goes through the fire input; on
	# release the game stops that group itself, so Auto Fire forgets it
	# was firing it and starts it again on the next cycle.
	eType = pEvent.GetEventType()
	for tEntry in GetFireEvents():
		if tEntry[0] == eType:
			g_dManual[tEntry[1]] = pEvent.GetBool()
			g_dFiring[tEntry[1]] = None
			if pEvent.GetBool() and IsTorpedoGroup(tEntry[1]):
				# The player fires torpedoes by hand, with their own spread.
				RestoreSpread()


def IsTorpedoGroup(eGroup):
	try:
		return App.TorpedoSystem_Cast(GetPlayer().GetWeaponSystemGroup(eGroup)) != None
	except:
		return 0


###############################################################################
#	Fire cycle
###############################################################################
class Timer:
	# Auto Fire's own timer (same form as the core's), so it can fire more
	# often than the core cycle, and only runs while Auto Fire is on.
	def __init__(self, fInterval):
		self.bActive = 1
		self.pProcess = App.PythonMethodProcess()
		self.pProcess.SetInstance(self)
		self.pProcess.SetFunction("Update")
		self.pProcess.SetPriority(App.TimeSliceProcess.LOW)
		try:
			self.pProcess.SetDelayUsesGameTime(1)
		except:
			pass
		self.pProcess.SetDelay(fInterval)

	def Update(self, dTimeAvailable):
		if not self.bActive:
			return
		try:
			FireCycle()
		except:
			if g_pCore != None:
				g_pCore.Log(NAME, "Fire cycle error: " + str(sys.exc_info()[1]))


def StartTimer():
	global g_pTimer
	if g_pTimer == None:
		fInterval = float(getattr(GetConfig(), "FireInterval", 0.1))
		if fInterval < 0.05:
			fInterval = 0.05
		g_pTimer = Timer(fInterval)


def StopTimer():
	global g_pTimer
	if g_pTimer != None:
		g_pTimer.bActive = 0
		g_pTimer.pProcess = None
	g_pTimer = None


def IsLive(pTarget):
	# 1 for a ship that can be fired at: alive and not cloaked.
	if pTarget == None:
		return 0
	if pTarget.IsDead() or pTarget.IsDying():
		return 0
	try:
		if pTarget.IsCloaked():
			return 0
	except:
		pass
	return 1


def GetPlayerTarget(pShip):
	# The player's selected target, if it is a live ship.
	try:
		pTarget = App.ShipClass_Cast(pShip.GetTarget())
	except:
		return None
	if IsLive(pTarget):
		return pTarget
	return None


def GetEnemies(pShip):
	# Live enemy ships of the mission, in the player's set.
	lEnemies = []
	try:
		pGroup = GetMission().GetEnemyGroup()
		for pObject in pGroup.GetActiveObjectTupleInSet(pShip.GetContainingSet()):
			pEnemy = App.ShipClass_Cast(pObject)
			if IsLive(pEnemy):
				lEnemies.append(pEnemy)
	except:
		pass
	return lEnemies


def SortByDistance(pShip, lShips):
	# Nearest first (a few ships: a simple insertion sort).
	lDistances = []
	lSorted = []
	for pOther in lShips:
		fDistance = GetDistance(pShip, pOther)
		i = 0
		while (i < len(lDistances)) and (lDistances[i] <= fDistance):
			i = i + 1
		lDistances.insert(i, fDistance)
		lSorted.insert(i, pOther)
	return lSorted


def IsEnemy(pTarget):
	# 1 for a ship of the mission's enemy group. Auto Fire never fires at
	# friendly or neutral ships, even when the player selects one.
	try:
		return GetMission().GetEnemyGroup().IsNameInGroup(pTarget.GetName())
	except:
		return 0


def GetTargets(pShip):
	# Enemy ships Auto Fire may fire at, best first, by TargetMode:
	#   0: the player's target only;
	#   1: the player's target; without one, the nearest enemy, which then
	#      becomes the player's target (so it carries on after a kill). With
	#      a friendly or neutral ship selected, the selection is kept and
	#      the nearest enemy is fired at;
	#   2: every enemy, nearest first; each weapon group picks its own.
	iMode = g_iTargetMode
	if iMode == 2:
		return SortByDistance(pShip, GetEnemies(pShip))
	pSelected = GetPlayerTarget(pShip)
	if (pSelected != None) and IsEnemy(pSelected):
		return [pSelected]
	if iMode != 1:
		return []
	lEnemies = SortByDistance(pShip, GetEnemies(pShip))
	if len(lEnemies) == 0:
		return []
	if pSelected == None:
		try:
			pShip.SetTarget(lEnemies[0].GetName())
		except:
			pass
	return [lEnemies[0]]


def GetOffset(pShip, pTarget):
	# Where on the target to aim: the subsystem the player picked, when it
	# is the player's target; otherwise its centre (None).
	pSelected = GetPlayerTarget(pShip)
	if (pSelected != None) and (pSelected.GetObjID() == pTarget.GetObjID()):
		try:
			return pShip.GetTargetOffsetTG()
		except:
			pass
	return None


def GetDistance(pFrom, pTarget):
	# From a weapon (or ship) to the target's surface, roughly: centre
	# distance less the target's radius, as the beams hit the hull.
	vDiff = pTarget.GetWorldLocation()
	vDiff.Subtract(pFrom.GetWorldLocation())
	fDistance = vDiff.Length()
	try:
		fDistance = fDistance - pTarget.GetRadius()
	except:
		pass
	return fDistance


def PhaserReady(pBank, pTarget):
	# 1 if this phaser bank should fire at the target now.
	if not pBank.CanHit(pTarget.GetWorldLocation()):
		return 0
	# PhaserMinCharge 0 = no charge check; PhaserRange 0 = no range check.
	if g_fPhaserMinCharge > 0.0:
		if pBank.GetChargePercentage() * 100.0 < g_fPhaserMinCharge:
			return 0
	if g_fPhaserRange > 0.0:
		fRange = pBank.GetMaxDamageDistance() * g_fPhaserRange / 100.0
		if GetDistance(pBank, pTarget) > fRange:
			return 0
	return 1


def GetSolution():
	import Custom.Spaceframe.Modules.AutoFire.Solution
	return Custom.Spaceframe.Modules.AutoFire.Solution


def TorpedoShot(pShip, pTorpedoes, pTarget, vOffset):
	# (lead point, projectile speed, projectile lifetime, guidance lifetime),
	# worked out once per target from the SHIP's location (tube offsets are
	# metres, distances km). On error: (the target's location, 0.0, 0.0, 0.0).
	try:
		pSolution = GetSolution()
		tInfo = pSolution.GetProjectileInfo(None, pTorpedoes)
		vPoint = pSolution.LeadPoint(pTarget, vOffset, pShip.GetWorldLocation(), tInfo[0])
		return (vPoint, tInfo[0], tInfo[3], tInfo[1])
	except:
		return (pTarget.GetWorldLocation(), 0.0, 0.0, 0.0)


def TubeScore(pShip, pTorpedoes, pTube, pTarget, vOffset, tFrame, tShot, bSecondary=0):
	# One tube's score against the target: arc percent on the tube's cone
	# (plus the flight-time filter under rule 2).
	return ArcScore(pShip, pTorpedoes, pTube, pTarget, vOffset, "torpedo", 1, tFrame, tShot, bSecondary)


def BestTorpedoScore(pShip, pSystem, pTarget):
	# Best arc score among the loaded tubes (0 if none is loaded): every tube is
	# scored (ArcScore checks readiness itself and drops the hysteresis key of
	# an unready tube).
	vOffset = GetOffset(pShip, pTarget)
	tShot = TorpedoShot(pShip, pSystem, pTarget, vOffset)
	ForgetSpreadNote(pTarget.GetObjID())
	fBest = 0.0
	for iChild in range(pSystem.GetNumChildSubsystems()):
		pTube = App.TorpedoTube_Cast(pSystem.GetChildSubsystem(iChild))
		if pTube != None:
			fScore = TubeScore(pShip, pSystem, pTube, pTarget, vOffset, None, tShot)
			if fScore > fBest:
				fBest = fScore
	return fBest


def TorpedoesLeft(pTorpedoes):
	# Torpedoes left of the current type (a large number if unknown).
	try:
		iLeft = pTorpedoes.GetNumAvailableTorpsToType(pTorpedoes.GetCurrentAmmoTypeNumber())
		if iLeft >= 0:
			return iLeft
	except:
		pass
	return 9999


def TorpedoTarget(pShip, pTorpedoes, lTargets, eGroup):
	# The target with the best arc score, if any tube reaches it.
	if TorpedoesLeft(pTorpedoes) <= g_iTorpedoReserve:
		ArcSettle(pTorpedoes, ArcKeep(eGroup, None))
		return None
	pBest = None
	fBest = -1.0
	for pTarget in lTargets:
		fScore = BestTorpedoScore(pShip, pTorpedoes, pTarget)
		if fScore > fBest:
			fBest = fScore
			pBest = pTarget
	if pBest == None:
		ArcSettle(pTorpedoes, ArcKeep(eGroup, None))
		return None
	g_dScore[eGroup] = fBest
	if fBest >= ARC_MINIMUM:
		ArcSettle(pTorpedoes, ArcKeep(eGroup, pBest.GetObjID()))
		ApplySpread(pShip, pTorpedoes, pBest)
		return pBest
	ArcSettle(pTorpedoes, ArcKeep(eGroup, None))
	return None


###############################################################################
#	Torpedo secondaries: tubes that cannot reach the main target fire at
#	other enemies they reach. Secondary Target only says WHO may be a
#	secondary (TorpedoCandidates); Auto Fire decides WHEN and with WHICH
#	tube, and builds the group's target list in the same call that presses
#	the group (a tube fires at the first listed target it reaches).
###############################################################################
def GetSecondaryTarget(sFunc="TorpedoCandidates"):
	# The SecondaryTarget module if it is active and offers the function
	# (TorpedoCandidates, PulseCandidates or PhaserCandidates; looked up at each press, never kept).
	try:
		pModule = g_pCore.GetModule("SecondaryTarget")
		if (pModule != None) and hasattr(pModule, sFunc):
			return pModule
	except:
		pass
	return None


def ManagesTorpedoSecondaries(eGroup):
	# 1 while Auto Fire builds the torpedo secondaries of this group itself
	# (SecondaryTarget then leaves the group alone).
	try:
		if g_iSecondaryTorpedoes and IsEnabled() and (not g_dManual.get(eGroup)):
			return 1
	except:
		pass
	return 0


def ManagesPulseSecondaries(eGroup):
	# 1 while Auto Fire builds the pulse secondaries of this group itself
	# (SecondaryTarget then leaves the group alone).
	try:
		if IsEnabled() and (not g_dManual.get(eGroup)):
			return 1
	except:
		pass
	return 0


def ArcRuleOn(sKind):
	# Public: 1 when the arc-percent rule applies to this kind ("pulse" or
	# "torpedo": always, both rules 1 and 2 are arc rules). Also read by
	# SecondaryTarget for its manual-fire filter.
	if (sKind == "pulse") or (sKind == "torpedo"):
		return 1
	return 0


def ArcReaches(pShip, pSystem, pWeapon, pTarget, sKind, bSecondary=0):
	# Public (manual-fire filter): 1 when this weapon has the target inside its
	# allowed arc percent. Needs no charge (no flapping of the list while the
	# free weapon recharges). Any error: 0.
	try:
		if ArcScore(pShip, pSystem, pWeapon, pTarget, None, sKind, 0, None, None, bSecondary) >= 1.0:
			return 1
	except:
		pass
	return 0


def TubeInArc(pTube, vPoint, iOnError):
	# IsInArc of a torpedo tube on a world point; iOnError if the call fails.
	try:
		if pTube.IsInArc(vPoint):
			return 1
		return 0
	except:
		return iOnError


def AnyTubeInArc(lTubes, vPoint):
	for pTube in lTubes:
		if TubeInArc(pTube, vPoint, 1):
			return 1
	return 0


def LogPlanError(sText):
	global g_bTorpPlanLogged
	if g_bDebug and (not g_bTorpPlanLogged) and (g_pCore != None):
		g_bTorpPlanLogged = 1
		try:
			g_pCore.Log(NAME, sText)
		except:
			pass


def SecondaryTorpedoPlan(pShip, pTorpedoes, pMain, bMainShot):
	# [(solution, ship ID)] of the secondaries the ready free tubes can hit,
	# best first. Free tube = ready and the main target is outside its arc.
	# Without a main shot, a secondary that a ready main-reaching tube also
	# has in arc is dropped, so no main-reaching tube can launch.
	if (not g_iSecondaryTorpedoes) or (pMain == None):
		return []
	if TorpedoesLeft(pTorpedoes) <= g_iTorpedoReserve:
		return []
	pST = GetSecondaryTarget()
	if pST == None:
		return []
	try:
		lIDs = pST.TorpedoCandidates(pShip, pTorpedoes, pMain)
	except:
		LogPlanError("TorpedoCandidates error: " + str(sys.exc_info()[1]))
		return []
	if (lIDs == None) or (len(lIDs) == 0):
		return []
	vMain = pMain.GetWorldLocation()
	lMainReady = []
	lFree = []
	for iChild in range(pTorpedoes.GetNumChildSubsystems()):
		pTube = App.TorpedoTube_Cast(pTorpedoes.GetChildSubsystem(iChild))
		if pTube != None:
			iReady = 0
			try:
				iReady = pTube.GetNumReady()
			except:
				iReady = 0
			if iReady > 0:
				if TubeInArc(pTube, vMain, 1):
					lMainReady.append(pTube)
				else:
					lFree.append(pTube)
	if len(lFree) == 0:
		return []
	lFrames = []
	# One frame per free tube for the whole plan (about ten engine calls each).
	for pTube in lFree:
		lFrames.append(GetSolution().TubeFrame(pShip, pTube))
	iMain = pMain.GetObjID()
	lScores = []
	lPlan = []
	for iID in lIDs:
		if iID != iMain:
			try:
				pCandidate = App.ShipClass_GetObjectByID(None, iID)
				if IsLive(pCandidate):
					vPoint = pCandidate.GetWorldLocation()
					if bMainShot or (not AnyTubeInArc(lMainReady, vPoint)):
						fBest = -1.0
						ForgetSpreadNote(iID)
						tShot = TorpedoShot(pShip, pTorpedoes, pCandidate, None)
						for iTube in range(len(lFree)):
							pTube = lFree[iTube]
							if TubeInArc(pTube, vPoint, 0):
								fScore = TubeScore(pShip, pTorpedoes, pTube, pCandidate, None, lFrames[iTube], tShot, 1)
								if fScore > fBest:
									fBest = fScore
						if fBest >= ARC_MINIMUM:
							i = 0
							while (i < len(lScores)) and (lScores[i] >= fBest):
								i = i + 1
							lScores.insert(i, fBest)
							lPlan.insert(i, (fBest, iID))
			except:
				LogPlanError("Secondary " + str(iID) + " skipped: " + str(sys.exc_info()[1]))
	return lPlan


def PlanTorpedoGroup(pShip, pTorpedoes, pTarget, lTargets, eGroup):
	# (head target, secondary IDs, 1 if the head is a secondary) for a torpedo
	# group about to be pressed. With a main shot the head is the main target;
	# without one the head is the best secondary, fired Single.
	if pTarget != None:
		lPlan = SecondaryTorpedoPlan(pShip, pTorpedoes, pTarget, 1)
		lIDs = []
		for tEntry in lPlan:
			lIDs.append(tEntry[1])
		return (pTarget, lIDs, 0)
	if len(lTargets) == 0:
		return (None, [], 0)
	lPlan = SecondaryTorpedoPlan(pShip, pTorpedoes, lTargets[0], 0)
	if len(lPlan) == 0:
		return (None, [], 0)
	pHead = App.ShipClass_GetObjectByID(None, lPlan[0][1])
	if not IsLive(pHead):
		return (None, [], 0)
	g_dScore[eGroup] = lPlan[0][0]
	ApplySpread(pShip, pTorpedoes, pHead)
	lIDs = []
	for tEntry in lPlan[1:]:
		lIDs.append(tEntry[1])
	return (pHead, lIDs, 1)


def SecondaryPulsePlan(pShip, pPulse, pMain, bMainShot):
	# [(score, ship ID)] of the secondaries the free charged pulse
	# weapons can hit inside the allowed arc percent, best first. Free weapon =
	# charged and the main target is outside its arc. Without a main shot, a
	# secondary that a charged main-reaching weapon also has in arc is dropped,
	# so no main-reaching weapon can fire.
	if pMain == None:
		return []
	pST = GetSecondaryTarget("PulseCandidates")
	if pST == None:
		return []
	try:
		lIDs = pST.PulseCandidates(pShip, pPulse, pMain)
	except:
		LogPlanError("PulseCandidates error: " + str(sys.exc_info()[1]))
		return []
	if (lIDs == None) or (len(lIDs) == 0):
		return []
	vMain = pMain.GetWorldLocation()
	lMainReady = []
	lFree = []
	for iChild in range(pPulse.GetNumChildSubsystems()):
		pWeapon = App.PulseWeapon_Cast(pPulse.GetChildSubsystem(iChild))
		if (pWeapon != None) and WeaponReady(pWeapon, "pulse"):
			if TubeInArc(pWeapon, vMain, 1):
				lMainReady.append(pWeapon)
			else:
				lFree.append(pWeapon)
	if len(lFree) == 0:
		return []
	iMain = pMain.GetObjID()
	lScores = []
	lPlan = []
	for iID in lIDs:
		if iID != iMain:
			try:
				pCandidate = App.ShipClass_GetObjectByID(None, iID)
				if IsLive(pCandidate):
					vPoint = pCandidate.GetWorldLocation()
					if bMainShot or (not AnyTubeInArc(lMainReady, vPoint)):
						fBest = -1.0
						for pWeapon in lFree:
							if TubeInArc(pWeapon, vPoint, 0):
								fScore = ArcScore(pShip, pPulse, pWeapon, pCandidate, None, "pulse", 1, None, None, 1)
								if fScore > fBest:
									fBest = fScore
						if fBest >= 1.0:
							i = 0
							while (i < len(lScores)) and (lScores[i] >= fBest):
								i = i + 1
							lScores.insert(i, fBest)
							lPlan.insert(i, (fBest, iID))
			except:
				LogPlanError("Pulse secondary " + str(iID) + " skipped: " + str(sys.exc_info()[1]))
	return lPlan


def PlanPulseGroup(pShip, pPulse, pTarget, lTargets, eGroup):
	# (head target, secondary IDs, 1 if the head is a secondary) for a pulse
	# group about to be pressed, as PlanTorpedoGroup, no spread.
	if pTarget != None:
		lPlan = SecondaryPulsePlan(pShip, pPulse, pTarget, 1)
		lIDs = []
		for tEntry in lPlan:
			lIDs.append(tEntry[1])
		return (pTarget, lIDs, 0)
	if len(lTargets) == 0:
		return (None, [], 0)
	lPlan = SecondaryPulsePlan(pShip, pPulse, lTargets[0], 0)
	if len(lPlan) == 0:
		return (None, [], 0)
	pHead = App.ShipClass_GetObjectByID(None, lPlan[0][1])
	if not IsLive(pHead):
		return (None, [], 0)
	g_dScore[eGroup] = lPlan[0][0]
	lIDs = []
	for tEntry in lPlan[1:]:
		lIDs.append(tEntry[1])
	return (pHead, lIDs, 1)


def Plannable(pSystem):
	# "torpedo", "pulse" or None: the groups whose list Auto Fire builds at
	# every press.
	if App.TorpedoSystem_Cast(pSystem) != None:
		return "torpedo"
	if App.PulseWeaponSystem_Cast(pSystem) != None:
		return "pulse"
	return None


def PlanGroup(pShip, pSystem, pTarget, lTargets, eGroup):
	# The plan of a group about to be pressed (see PlanTorpedoGroup).
	pTorpedoes = App.TorpedoSystem_Cast(pSystem)
	if pTorpedoes != None:
		return PlanTorpedoGroup(pShip, pTorpedoes, pTarget, lTargets, eGroup)
	pPulse = App.PulseWeaponSystem_Cast(pSystem)
	if pPulse != None:
		return PlanPulseGroup(pShip, pPulse, pTarget, lTargets, eGroup)
	return (pTarget, [], 0)


def IsPhaserGroup(pSystem):
	# 1 for a group that is neither torpedoes nor pulse weapons (phaser banks).
	try:
		if App.TorpedoSystem_Cast(pSystem) != None:
			return 0
		if App.PulseWeaponSystem_Cast(pSystem) != None:
			return 0
		return 1
	except:
		return 0


def SecondaryPhaserPlan(pShip, pSystem, pMain):
	# IDs of the secondaries a ready phaser bank can hit now, nearest first (the
	# order of SecondaryTarget.PhaserCandidates). Used only when no bank can hit
	# the main target.
	if (not g_iSecondaryPhasers) or (pMain == None):
		return []
	pST = GetSecondaryTarget("PhaserCandidates")
	if pST == None:
		return []
	try:
		lIDs = pST.PhaserCandidates(pShip, pSystem, pMain)
	except:
		LogPlanError("PhaserCandidates error: " + str(sys.exc_info()[1]))
		return []
	if (lIDs == None) or (len(lIDs) == 0):
		return []
	iMain = pMain.GetObjID()
	lPlan = []
	for iID in lIDs:
		if iID != iMain:
			try:
				pCandidate = App.ShipClass_GetObjectByID(None, iID)
				if IsLive(pCandidate) and PhasersReady(pSystem, pCandidate):
					lPlan.append(iID)
			except:
				LogPlanError("Phaser secondary " + str(iID) + " skipped: " + str(sys.exc_info()[1]))
	return lPlan


def PhaserHeadReady(pSystem, iHead):
	# 1 while the secondary a held phaser group was started at is still a live
	# enemy that a ready bank can hit.
	try:
		pHead = App.ShipClass_GetObjectByID(None, iHead)
		if IsLive(pHead) and IsEnemy(pHead) and PhasersReady(pSystem, pHead):
			return 1
	except:
		pass
	return 0


def PlanPhaserStep(pShip, pSystem, pTarget, lTargets, eGroup):
	# (target, secondary IDs, 1 if the target is a secondary, 1 = keep the group
	# as it is) for a phaser group. With a target in reach nothing changes
	# (Secondary Target adds secondaries while the group fires). Without one,
	# the group is started at the first secondary a ready bank reaches; a group
	# already started that way is kept while that secondary stays reachable (no
	# stop and start every cycle).
	global g_dPlanNote
	if (not g_iSecondaryPhasers) or (len(lTargets) == 0):
		return (pTarget, [], 0, 0)
	if pTarget != None:
		if g_dPlanNote.has_key(eGroup):
			del g_dPlanNote[eGroup]
		return (pTarget, [], 0, 0)
	iHead = g_dSecHead.get(eGroup)
	if (iHead != None) and (g_dFiring.get(eGroup) == iHead) and IsFiring(pSystem):
		if PhaserHeadReady(pSystem, iHead):
			return (None, [], 0, 1)
	lPlan = SecondaryPhaserPlan(pShip, pSystem, lTargets[0])
	if len(lPlan) == 0:
		return (None, [], 0, 0)
	pHead = App.ShipClass_GetObjectByID(None, lPlan[0])
	if not IsLive(pHead):
		return (None, [], 0, 0)
	g_dScore[eGroup] = 100.0	# phasers have no solution: the log shows 100
	lIDs = lPlan[1:]
	if g_bDebug and (g_pCore != None):
		sSec = ""
		for iSec in lPlan:
			if sSec != "":
				sSec = sSec + ","
			sSec = sSec + str(iSec)
		sText = "Group " + str(eGroup) + " plan: main - sec " + sSec + " head sec"
		if g_dPlanNote.get(eGroup) != sText:
			g_dPlanNote[eGroup] = sText
			g_pCore.Log(NAME, sText)
			try:
				g_pCore.DebugNotice("AutoFire " + sText, 0.22, 3.0)
			except:
				pass
	return (pHead, lIDs, 1, 0)


def NoteArcPlan(pShip, pSystem, eGroup, pTarget, lSec, bHeadSec):
	# After an arc-percent plan: remembers the group's secondaries (their
	# hysteresis keys survive ArcSettle) and, in Debug, logs the plan line when
	# it changed.
	global g_dArcSec, g_dPlanNote
	lIDs = []
	for iSec in lSec:
		lIDs.append(iSec)
	iHead = None
	if pTarget != None:
		iHead = pTarget.GetObjID()
	if bHeadSec and (iHead != None):
		lIDs.append(iHead)
	g_dArcSec[eGroup] = lIDs
	ArcSettle(pSystem, ArcKeep(eGroup, iHead))
	if g_bDebug and (g_pCore != None):
		sSec = ""
		lShow = lSec
		if bHeadSec and (iHead != None):
			lShow = [iHead] + list(lSec)
		for iSec in lShow:
			if sSec != "":
				sSec = sSec + ","
			sSec = sSec + str(iSec)
		if sSec == "":
			sSec = "-"
		sMain = "-"
		sHead = "main"
		if iHead != None:
			if bHeadSec:
				sHead = "sec"
			else:
				sMain = str(iHead)
		sText = "Group " + str(eGroup) + " plan: main " + sMain + " sec " + sSec + " head " + sHead
		if g_dPlanNote.get(eGroup) != sText:
			g_dPlanNote[eGroup] = sText
			g_pCore.Log(NAME, sText)
			try:
				g_pCore.DebugNotice("AutoFire " + sText, 0.22, 3.0)
			except:
				pass


###############################################################################
#	Torpedo spread: the largest spread for the best solutions, Single for
#	the rest; the player's own choice comes back when Auto Fire lets go.
###############################################################################
def KilometersToUnits(fKilometers):
	# Distances as the game shows them (km) into world units.
	try:
		return App.g_kUtopiaModule.ConvertKilometersToGameUnits(fKilometers)
	except:
		return fKilometers / 0.175


def TorpedoSpeed(pTorpedoes):
	# Launch speed of the system's current torpedo (world units / s), 0.0 if unknown.
	try:
		return float(GetSolution().GetProjectileInfo(None, pTorpedoes)[0])
	except:
		return 0.0


def SpreadAllowed(fDistance, fSpeed):
	# 1 when the flight time (distance / speed) is inside the spread interval
	# SpreadFlightTimeMin..SpreadFlightTimeMax (Max 0 = no upper bound). Speed
	# unknown: 0.
	if fSpeed <= 0.0:
		return 0
	fFlight = fDistance / fSpeed
	if fFlight < g_fSpreadFtMin:
		return 0
	if (g_fSpreadFtMax > 0.0) and (fFlight > g_fSpreadFtMax):
		return 0
	return 1


def ForgetSpreadNote(iTarget):
	# Start of a new scoring of the target: drop the last spread verdict.
	if g_dSpreadOK.has_key(iTarget):
		del g_dSpreadOK[iTarget]


def NoteSpread(iTarget, bSpread):
	# A tube passed for the target: record the verdict (1 wins over 0).
	if bSpread or (not g_dSpreadOK.has_key(iTarget)):
		g_dSpreadOK[iTarget] = bSpread


def SpreadShot(pTorpedoes, fDistance, fSpeed, fDepth=0.0):
	# 1 when a torpedo shot would go out as spread: a spread chain exists, the
	# flight time is inside the spread window AND depth*100 <= SpreadArcPercent
	# (fixed, no hysteresis; fDepth is the same value ArcScore judges). Used by
	# ArcScore (to bypass the flight-time limit) and, through g_dSpreadOK, by
	# ApplySpread: one decision, one distance (tube to lead point).
	try:
		if pTorpedoes.GetNumFiringChains() - 1 <= 0:
			return 0	# no spread chain: the shot would go out Single
	except:
		return 0
	if fDepth * 100.0 > g_fSpreadArcPercent:
		return 0	# too far off the tube axis for a spread: judged as Single
	return SpreadAllowed(fDistance, fSpeed)


def ApplySpread(pShip, pTorpedoes, pTarget):
	# Spread torpedoes leave in a fan and only turn to the target after a
	# while: too close (flight time under SpreadFlightTimeMin) they would fly
	# past it, too far (over SpreadFlightTimeMax) the fan is too wide.
	global g_iPlayerSpread, g_iSetSpread, g_iSpreadShipID
	iWant = 0
	iTargetID = pTarget.GetObjID()
	if g_dSpreadOK.has_key(iTargetID):
		# The decision ArcScore took for the shots just scored (tube to lead
		# point distance, the same one the flight-time filter used).
		if g_dSpreadOK[iTargetID]:
			iWant = pTorpedoes.GetNumFiringChains() - 1
	if iWant < 0:
		iWant = 0
	iNow = pTorpedoes.GetFiringChainMode()
	if (g_iPlayerSpread == None) or ((g_iSetSpread != None) and (iNow != g_iSetSpread)):
		# First change, or the player picked a spread meanwhile: that is
		# the one to go back to.
		g_iPlayerSpread = iNow
	if iNow != iWant:
		pTorpedoes.SetFiringChainMode(iWant)
	g_iSetSpread = iWant
	g_iSpreadShipID = pShip.GetObjID()


def RestoreSpread():
	# Gives the player back the spread they had chosen.
	global g_iPlayerSpread, g_iSetSpread, g_iSpreadShipID
	if (g_iPlayerSpread != None) and (g_iSpreadShipID != None):
		try:
			pShip = App.ShipClass_GetObjectByID(None, g_iSpreadShipID)
			if (pShip != None) and (not pShip.IsDead()):
				for tEntry in GetFireEvents():
					pTorpedoes = App.TorpedoSystem_Cast(pShip.GetWeaponSystemGroup(tEntry[1]))
					if pTorpedoes != None:
						pTorpedoes.SetFiringChainMode(g_iPlayerSpread)
		except:
			pass
	g_iPlayerSpread = None
	g_iSetSpread = None
	g_iSpreadShipID = None


def ForgetSpread():
	global g_iPlayerSpread, g_iSetSpread, g_iSpreadShipID
	g_iPlayerSpread = None
	g_iSetSpread = None
	g_iSpreadShipID = None


def PhasersReady(pSystem, pTarget):
	# 1 if any phaser bank of the group can fire at the target now.
	for iChild in range(pSystem.GetNumChildSubsystems()):
		pBank = App.PhaserBank_Cast(pSystem.GetChildSubsystem(iChild))
		if pBank != None:
			if PhaserReady(pBank, pTarget):
				return 1
	return 0


def ForgetArc():
	# Forgets which weapons were 'ready' (arc hysteresis).
	global g_dArcReady, g_dArcSec
	g_dArcReady = {}
	g_dArcSec = {}


def ArcBand(sKind, bSecondary=0):
	# ((far percent, near percent, far flight time, near flight time),
	# hysteresis) of the arc-percent rule of this kind ("pulse" or "torpedo").
	# bSecondary: the band of secondary targets (hysteresis and the flight
	# times stay shared).
	if bSecondary:
		if sKind == "torpedo":
			return ((g_fTorpArcFarSec, g_fTorpArcNearSec, g_fArcFtFar, g_fArcFtNear), g_fTorpArcHysteresis)
		return ((g_fArcFarSec, g_fArcNearSec, g_fArcFtFar, g_fArcFtNear), g_fArcHysteresis)
	if sKind == "torpedo":
		return ((g_fTorpArcFar, g_fTorpArcNear, g_fArcFtFar, g_fArcFtNear), g_fTorpArcHysteresis)
	return ((g_fArcFar, g_fArcNear, g_fArcFtFar, g_fArcFtNear), g_fArcHysteresis)


def ArcAllowed(fDistance, fSpeed, tBand=None):
	# Arc percent rule: percent of the arc (from its centre) the predicted point
	# may use at this flight time (distance in world units / projectile speed):
	# the Near percent at the Near flight time and less, the Far percent at the
	# Far flight time and more, linear in between. Speed unknown (<= 0): the
	# Near percent. tBand = (far %, near %, far time, near time); None = the
	# pulse settings (PulseArc*).
	if tBand == None:
		tBand = ArcBand("pulse")[0]
	if fSpeed <= 0.0:
		fFlight = 0.0
	else:
		fFlight = fDistance / fSpeed
	if fFlight <= tBand[3]:
		fAllowed = tBand[1]
	elif fFlight >= tBand[2]:
		fAllowed = tBand[0]
	else:
		fShare = (fFlight - tBand[3]) / (tBand[2] - tBand[3])
		fAllowed = tBand[1] + (tBand[0] - tBand[1]) * fShare
	if fAllowed < 0.0:
		fAllowed = 0.0
	if fAllowed > 100.0:
		fAllowed = 100.0
	return fAllowed


def FlightBand(sKind, bSecondary=0):
	# The flight-time limit (seconds, 0 = off) of this kind ("pulse" or
	# "torpedo"); bSecondary: the secondary-target limit.
	if bSecondary:
		if sKind == "torpedo":
			return g_fTorpFtLimitSec
		return g_fFtLimitSec
	if sKind == "torpedo":
		return g_fTorpFtLimit
	return g_fFtLimit


def FlightLimit(sKind, bSecondary):
	# Longest flight time (seconds) allowed, or 0 = no limit.
	fLimit = FlightBand(sKind, bSecondary)
	if fLimit < 0.0:
		fLimit = 0.0
	return fLimit


def FlightBlocked(sKind, bSecondary, fDistance, fSpeed, iTarget, fGuidance=0.0, fLifetime=0.0, bSpread=0, fDepth=None):
	# Rule 2 only: 1 when the estimated flight time (distance / projectile
	# speed) is over the limit for that distance. The limit is the configured
	# one PLUS the projectile's guidance time (it can still correct its course
	# during it), never more than the projectile's lifetime (0 = unknown, no
	# cap). 0 = filter off, speed unknown (no block, logged once in Debug) or
	# within the limit.
	global g_bFtSpeedLogged
	if sKind == "torpedo":
		iRule = g_iTorpedoRule
	else:
		iRule = g_iPulseRule
	if iRule != 2:
		return 0
	fLimit = FlightLimit(sKind, bSecondary)
	if fLimit <= 0.0:
		return 0
	if fGuidance > 0.0:
		fLimit = fLimit + fGuidance
	if (fLifetime > 0.0) and (fLimit > fLifetime):
		fLimit = fLifetime
	if fSpeed <= 0.0:
		if g_bDebug and (not g_bFtSpeedLogged) and (g_pCore != None):
			g_bFtSpeedLogged = 1
			try:
				g_pCore.Log(NAME, "Flight time filter: " + sKind + " projectile speed unknown, not blocking")
			except:
				pass
		return 0
	fEstimate = fDistance / fSpeed
	if fEstimate <= fLimit:
		return 0
	if bSpread:
		# bSpread: the shot goes out as spread (SpreadShot), independent of the limit.
		if g_bDebug:
			LogFlightBlock(sKind, bSecondary, fEstimate, fLimit, fDistance, iTarget, 1, fDepth)
		return 0
	if g_bDebug:
		LogFlightBlock(sKind, bSecondary, fEstimate, fLimit, fDistance, iTarget)
	return 1


def LogFlightBlock(sKind, bSecondary, fEstimate, fLimit, fDistance, iTarget, bBypass=0, fDepth=None):
	# Debug only: the filter blocked a weapon; one line per target and kind at
	# most every 2 seconds of game time.
	if g_pCore == None:
		return
	try:
		fNow = App.g_kUtopiaModule.GetGameTime()
		sRole = "main"
		if bSecondary:
			sRole = "sec"
		tKey = (iTarget, sKind, bSecondary, bBypass)
		if g_dFtLog.has_key(tKey) and (fNow - g_dFtLog[tKey] < 2.0):
			return
		g_dFtLog[tKey] = fNow
		fKm = fDistance * KmPerUnit()
		sText = "Flight time filter: " + sKind + " " + sRole + " est " + ("%.1f" % fEstimate) + " s > limit " + ("%.1f" % fLimit) + " s at " + str(int(fKm)) + " km"
		if bBypass:
			sText = sText + ", passed as spread"
			if fDepth != None:
				sText = sText + " (depth " + ("%.0f" % (fDepth * 100.0)) + " <= spread arc " + ("%.0f" % g_fSpreadArcPercent) + ")"
		g_pCore.Log(NAME, sText)
	except:
		pass


def PulseCharged(pWeapon):
	return pWeapon.GetChargeLevel() >= pWeapon.GetMinFiringCharge()


def WeaponKey(pWeapon):
	# The weapon's object ID (None if unreadable: no hysteresis for it).
	try:
		return pWeapon.GetObjID()
	except:
		return None


def ArcFallback(pWeapon, vPoint):
	# ArcDepth unavailable: the game's boolean arc test; if that raises too,
	# ready (as PulseReady). Score 1 (the minimum) or 0.
	global g_bArcLogged
	try:
		if pWeapon.IsInArc(vPoint):
			return 1.0
		return 0.0
	except:
		if g_bDebug and (not g_bArcLogged):
			g_bArcLogged = 1
			try:
				g_pCore.Log(NAME, "ArcDepth and IsInArc failed, arc not checked: " + str(sys.exc_info()[1]))
			except:
				pass
		return 1.0


def WeaponReady(pWeapon, sKind):
	# 1 when the weapon can fire now: a pulse weapon is charged enough, a
	# torpedo tube has a torpedo loaded. Any error: 0.
	try:
		if sKind == "torpedo":
			return pWeapon.GetNumReady() > 0
		return PulseCharged(pWeapon)
	except:
		return 0


def GetWarpHold():
	import Custom.Spaceframe.Modules.AutoFire.WarpHold
	return Custom.Spaceframe.Modules.AutoFire.WarpHold


def WarpHeld(pTarget):
	# 1 when the target is warping / in its grace (WarpHold.py). Any error: 0.
	try:
		return GetWarpHold().Held(pTarget)
	except:
		return 0


def ArcDrop(iKey):
	# Forgets the hysteresis entry of one (weapon, target) pair.
	if (iKey != None) and g_dArcReady.has_key(iKey):
		del g_dArcReady[iKey]


def ArcScore(pShip, pSystem, pWeapon, pTarget, vOffset, sKind, bNeedReady, tFrame=None, tShot=None, bSecondary=0):
	# Arc percent rule (PulseRule / TorpedoRule 1 and 2): 0 when the weapon
	# should not fire at the target, else 1 to 100 (100 = predicted point at
	# the centre of the arc). The point is the lead point of Solution.LeadPoint
	# (tShot: (point, speed, lifetime, guidance) already worked out by the caller).
	# Rule 2 also holds the weapon when the flight time is over its limit
	# (FlightBlocked).
	# Ready from depth*100 <= the allowed percent at that distance; once ready
	# for this target it stays ready until depth*100 > allowed + hysteresis
	# (never beyond the arc). bNeedReady 1: an unready weapon scores 0 and its
	# entry is dropped.
	iWeapon = WeaponKey(pWeapon)
	iTarget = pTarget.GetObjID()
	iKey = None
	if iWeapon != None:
		iKey = (iWeapon, iTarget)	# per (weapon, target): scoring B never touches A's entry
	if bNeedReady and WarpHeld(pTarget):
		# in-system warp (or its grace): auto fire only, manual fire is untouched
		ArcDrop(iKey)
		return 0.0
	if bNeedReady and (not WeaponReady(pWeapon, sKind)):
		ArcDrop(iKey)
		return 0.0
	pSolution = GetSolution()
	vPoint = None
	fSpeed = 0.0
	fLifetime = 0.0
	fGuidance = 0.0
	if tShot != None:
		vPoint = tShot[0]
		fSpeed = tShot[1]
		fLifetime = tShot[2]
		if len(tShot) > 3:
			fGuidance = tShot[3]
	else:
		try:
			if sKind == "torpedo":
				tInfo = pSolution.GetProjectileInfo(None, pSystem)
			else:
				tInfo = pSolution.GetProjectileInfo(pWeapon, pSystem)
			fSpeed = tInfo[0]
			fLifetime = tInfo[3]
			fGuidance = tInfo[1]
			vPoint = pSolution.LeadPoint(pTarget, vOffset, pWeapon.GetWorldLocation(), tInfo[0])
		except:
			vPoint = None
	if vPoint == None:
		vPoint = pTarget.GetWorldLocation()
	fDepth = None
	try:
		if sKind == "torpedo":
			if tFrame == None:
				tFrame = pSolution.TubeFrame(pShip, pWeapon)
			fDepth = None
			if g_iTorpArcShape != 0:
				fDepth = pSolution.TubeConeDepth(tFrame, vPoint)
			if fDepth == None:
				fDepth = pSolution.TubeDepth(tFrame, vPoint)
		else:
			fDepth = None
			if g_iPulseArcShape != 0:
				fDepth = pSolution.ArcConeDepth(pShip, pWeapon, vPoint)
			if fDepth == None:
				fDepth = pSolution.ArcDepth(pShip, pWeapon, vPoint)
	except:
		fDepth = None
	if fDepth == None:
		return ArcFallback(pWeapon, vPoint)
	fDistance = 0.0
	try:
		vDiff = pWeapon.GetWorldLocation()
		vDiff.Subtract(vPoint)
		fDistance = vDiff.Length()
	except:
		fDistance = 0.0
	if (sKind == "torpedo") or PULSE_ARC_LIFETIME:
		if (fSpeed > 0.0) and (fLifetime > 0.0) and (fDistance / fSpeed > fLifetime):
			ArcDrop(iKey)
			return 0.0
	tBandHys = ArcBand(sKind, bSecondary)
	fLimit = ArcAllowed(fDistance, fSpeed, tBandHys[0])
	# hysteresis <= 0 = off: no ready key is stored, nothing is added to the limit
	if tBandHys[1] <= 0.0:
		iKey = None
	if (iKey != None) and g_dArcReady.has_key(iKey):
		fLimit = fLimit + tBandHys[1]
	if fLimit > 100.0:
		fLimit = 100.0
	if fDepth * 100.0 <= fLimit:
		fScore = 100.0 * (1.0 - fDepth)
		if fScore < 1.0:
			fScore = 1.0
		bSpread = 0
		bAuto = (sKind == "torpedo") and bNeedReady	# not ArcReaches (manual fire): no spread decision
		if bAuto:
			bSpread = SpreadShot(pSystem, fDistance, fSpeed, fDepth)
		if FlightBlocked(sKind, bSecondary, fDistance, fSpeed, iTarget, fGuidance, fLifetime, bSpread, fDepth):
			ArcDrop(iKey)
			return 0.0
		if bAuto:
			NoteSpread(iTarget, bSpread)
		if iKey != None:
			g_dArcReady[iKey] = 1
		if g_bDebug and (sKind == "torpedo"):
			NoteTorpDecision(tFrame, vPoint, iTarget, fDepth, fLimit, bSecondary)
		return fScore
	ArcDrop(iKey)
	return 0.0


def NoteTorpDecision(tFrame, vPoint, iTarget, fDepth, fLimit, bSecondary):
	# Debug only: remembers the angles of the last allowed torpedo tube decision (a plain tuple),
	# to compare with the angle at launch. Same game time: the larger 3D angle wins.
	global g_tTorpDecision
	try:
		fNow = App.g_kUtopiaModule.GetGameTime()
		tAng = BoxAngles(tFrame[0], tFrame[1], tFrame[2], tFrame[3], GetSolution().Triple(vPoint))
		if tAng == None:
			return
		tOld = g_tTorpDecision
		if (tOld != None) and (tOld[0] == fNow) and (tOld[4] >= tAng[2]):
			return
		g_tTorpDecision = (fNow, iTarget, fDepth * 100.0, fLimit, tAng[2], tAng[0], tAng[1], bSecondary)
	except:
		pass


def TorpDecisionText(fNow):
	# Debug only: the stored decision for the launch line, or " decision none".
	try:
		tD = g_tTorpDecision
		if tD == None:
			return " decision none"
		return " decision %.2f s ago ang %.1f h %.1f v %.1f depth %.1f%% allowed %.1f%% tgt %s sec %d" % (fNow - tD[0], tD[4], tD[5], tD[6], tD[2], tD[3], str(tD[1]), tD[7])
	except:
		return " decision none"


def PulseArcScore(pShip, pSystem, pWeapon, pTarget, vOffset):
	# Arc score of one pulse weapon (see ArcScore): charged weapons only.
	return ArcScore(pShip, pSystem, pWeapon, pTarget, vOffset, "pulse", 1)


def ArcKeep(eGroup, iTargetID):
	# IDs whose hysteresis keys survive ArcSettle: the chosen target (if any)
	# and the secondaries of the group's last plan.
	lKeep = []
	if iTargetID != None:
		lKeep.append(iTargetID)
	for iID in g_dArcSec.get(eGroup, []):
		lKeep.append(iID)
	return lKeep


def ArcSettle(pSystem, keep):
	# After the group chose its target: its weapons stay 'ready' only for the
	# target IDs in keep (None = none, an ID, or a list of IDs), so a target
	# change starts every weapon afresh. Pulse weapons and torpedo tubes.
	if keep == None:
		lKeep = []
	elif type(keep) == type([]):
		lKeep = keep
	else:
		lKeep = [keep]
	for iChild in range(pSystem.GetNumChildSubsystems()):
		pWeapon = App.PulseWeapon_Cast(pSystem.GetChildSubsystem(iChild))
		if pWeapon == None:
			pWeapon = App.TorpedoTube_Cast(pSystem.GetChildSubsystem(iChild))
		if pWeapon != None:
			iWeapon = WeaponKey(pWeapon)
			if iWeapon == None:
				continue
			for tKey in g_dArcReady.keys():
				if (tKey[0] == iWeapon) and (not (tKey[1] in lKeep)):
					del g_dArcReady[tKey]


def BestPulseScore(pShip, pSystem, pTarget):
	# Best score among the charged pulse weapons that can reach the target
	# (see PulseArcScore).
	vOffset = GetOffset(pShip, pTarget)
	fBest = 0.0
	for iChild in range(pSystem.GetNumChildSubsystems()):
		pWeapon = App.PulseWeapon_Cast(pSystem.GetChildSubsystem(iChild))
		if pWeapon != None:
			fScore = PulseArcScore(pShip, pSystem, pWeapon, pTarget, vOffset)
			if fScore > fBest:
				fBest = fScore
	return fBest


def PulseTarget(pShip, pSystem, lTargets, eGroup):
	# The target with the best pulse solution, if good enough.
	pBest = None
	fBest = -1.0
	for pTarget in lTargets:
		fScore = BestPulseScore(pShip, pSystem, pTarget)
		if fScore > fBest:
			fBest = fScore
			pBest = pTarget
	if pBest == None:
		ArcSettle(pSystem, ArcKeep(eGroup, None))
		return None
	g_dScore[eGroup] = fBest
	if fBest >= ARC_MINIMUM:	# any weapon inside the allowed percent
		ArcSettle(pSystem, ArcKeep(eGroup, pBest.GetObjID()))
		return pBest
	ArcSettle(pSystem, ArcKeep(eGroup, None))
	return None


def GroupTarget(pShip, pSystem, lTargets, eGroup):
	# What this group should fire at now (None: hold fire). lTargets is
	# best first (see GetTargets).
	pTorpedoes = App.TorpedoSystem_Cast(pSystem)
	if pTorpedoes != None:
		return TorpedoTarget(pShip, pTorpedoes, lTargets, eGroup)
	pPulse = App.PulseWeaponSystem_Cast(pSystem)
	if pPulse != None:
		return PulseTarget(pShip, pPulse, lTargets, eGroup)
	for pTarget in lTargets:
		if PhasersReady(pSystem, pTarget):
			return pTarget
	return None


def IsFiring(pSystem):
	# 1 if the group is still firing (the game may have stopped it).
	try:
		return pSystem.IsFiring()
	except:
		return 1


def IsTapped(pSystem):
	# Torpedoes and pulse weapons fire faster from quick presses of the
	# fire key than from holding it (TapFire); phaser beams are held.
	if not g_iTapFire:
		return 0
	if App.TorpedoSystem_Cast(pSystem) != None:
		return 1
	if App.PulseWeaponSystem_Cast(pSystem) != None:
		return 1
	return 0


def GetTorpDiag():
	import Custom.Spaceframe.Modules.AutoFire.TorpDiag
	return Custom.Spaceframe.Modules.AutoFire.TorpDiag


def NoteTorpList(pSystem, iHead, lSec):
	# Debug only: remembers the torpedo group's target list (iHead None = emptied by
	# StopFiring) for the launch log (TorpDiag.py).
	if not g_bDebug:
		return
	GetTorpDiag().NoteTorpList(pSystem, iHead, lSec)


def KmPerUnit():
	# Debug only: km per game unit from the game's own conversion (1 km in game units).
	try:
		fUnits = App.g_kUtopiaModule.ConvertKilometersToGameUnits(1.0)
		if fUnits > 0.0:
			return 1.0 / fUnits
	except:
		pass
	return 0.175


def AngleDeg3(tA, tB):
	# Debug only: angle in degrees between two triples; None for a zero-length vector.
	fLenA = math.sqrt(tA[0] * tA[0] + tA[1] * tA[1] + tA[2] * tA[2])
	fLenB = math.sqrt(tB[0] * tB[0] + tB[1] * tB[1] + tB[2] * tB[2])
	if (fLenA <= 0.000001) or (fLenB <= 0.000001):
		return None
	fCos = (tA[0] * tB[0] + tA[1] * tB[1] + tA[2] * tB[2]) / (fLenA * fLenB)
	if fCos > 1.0:
		fCos = 1.0
	if fCos < -1.0:
		fCos = -1.0
	return math.acos(fCos) * 180.0 / math.pi


def BoxAngles(tPos, tFwd, tRight, tUp, tPoint):
	# Debug only: (h, v, ang) in degrees of the world point seen from a weapon frame: h =
	# atan2(D.right, D.fwd), v = atan2(D.up, D.fwd) (the arc test's box angles, signed) and ang =
	# the unsigned 3D angle between the forward axis and D; None when D has no length.
	pSolution = GetSolution()
	tD = (tPoint[0] - tPos[0], tPoint[1] - tPos[1], tPoint[2] - tPos[2])
	fAng = AngleDeg3(tFwd, tD)
	if fAng == None:
		return None
	fFwd = pSolution.Dot3(tD, tFwd)
	fH = math.atan2(pSolution.Dot3(tD, tRight), fFwd) * 180.0 / math.pi
	fV = math.atan2(pSolution.Dot3(tD, tUp), fFwd) * 180.0 / math.pi
	return (fH, fV, fAng)


def OnTorpedoLaunched(pObject, pEvent):
	# Debug only: the launch log of our torpedoes and bolts (TorpDiag.py). Registered by
	# name in Start(); always passes the event on to the next handler.
	if g_bDebug:
		try:
			GetTorpDiag().OnTorpedoLaunched(pObject, pEvent)
		except:
			if g_pCore != None:
				g_pCore.Log(NAME, "Torpedo event error: " + str(sys.exc_info()[1]))
	try:
		pObject.CallNextHandler(pEvent)
	except:
		pass


def FireGroup(pShip, eGroup, pTarget, bFire, lSec=None, bHeadSec=0):
	# Starts or stops one weapon group, like the game's fire keys do.
	# Only stops what Auto Fire itself started. Tapped groups are pressed
	# on one cycle and released on the next while they should fire.
	# lSec: IDs of secondary targets added after pTarget (torpedo groups).
	pSystem = pShip.GetWeaponSystemGroup(eGroup)
	if pSystem == None:
		g_dFiring[eGroup] = None
		return
	if bFire:
		iID = pTarget.GetObjID()
		if IsTapped(pSystem):
			if g_dFiring.get(eGroup) != None:
				pSystem.StopFiring()
				NoteTorpList(pSystem, None, None)
				g_dFiring[eGroup] = None
				return
		elif (g_dFiring.get(eGroup) == iID) and IsFiring(pSystem):
			return
		vOffset = GetOffset(pShip, pTarget)
		if vOffset == None:
			vOffset = App.TGPoint3()
			try:
				vOffset.SetXYZ(0.0, 0.0, 0.0)
			except:
				pass
		pSystem.StartFiring(pTarget, vOffset)
		if lSec:
			pZero = App.TGPoint3()
			try:
				pZero.SetXYZ(0.0, 0.0, 0.0)
			except:
				pass
			for iSec in lSec:
				if iSec != iID:
					try:
						pSec = App.ShipClass_GetObjectByID(None, iSec)
						if IsLive(pSec):
							pSystem.StartFiring(pSec, pZero)
					except:
						if g_bDebug and (g_pCore != None):
							g_pCore.Log(NAME, "Secondary " + str(iSec) + " start error: " + str(sys.exc_info()[1]))
		try:
			pSystem.SetForceUpdate(1)
		except:
			pass
		NoteTorpList(pSystem, iID, lSec)
		g_dFiring[eGroup] = iID
		SetFiringShip(pShip)
		if g_bDebug and (g_dScore.get(eGroup) != None):
			sText = "Group " + str(eGroup) + " fires"
			if bHeadSec:
				sText = sText + " at secondary " + str(iID)
			sText = sText + ", solution " + str(int(g_dScore[eGroup]))
			if lSec:
				sText = sText + " +sec"
				for iSec in lSec:
					sText = sText + " " + str(iSec)
			g_pCore.Log(NAME, sText)
	elif g_dFiring.get(eGroup) != None:
		pSystem.StopFiring()
		NoteTorpList(pSystem, None, None)
		g_dFiring[eGroup] = None


def SetFiringShip(pShip):
	global g_iFiringShipID
	g_iFiringShipID = pShip.GetObjID()


def StopAll():
	# Stops every group Auto Fire is firing, on the ship it fired them on
	# (looked up by ID: that ship may no longer be the player's, or exist).
	global g_iFiringShipID
	pShip = None
	if g_iFiringShipID != None:
		try:
			pShip = App.ShipClass_GetObjectByID(None, g_iFiringShipID)
		except:
			pShip = None
	for tEntry in GetFireEvents():
		eGroup = tEntry[1]
		if g_dFiring.get(eGroup) != None:
			if pShip != None:
				try:
					FireGroup(pShip, eGroup, None, 0)
				except:
					pass
			g_dFiring[eGroup] = None
	g_iFiringShipID = None


def FireCycle():
	if not IsEnabled():
		# The player switched ships, died, or the ship lost the technology.
		SetEnabled(0)
		return
	if g_bDebug:
		try:
			GetTorpDiag().TorpFollowUp()
		except:
			g_pCore.Log(NAME, "Torpedo follow-up error: " + str(sys.exc_info()[1]))
	pShip = GetPlayer()
	lTargets = []
	if (not pShip.IsCloaked()) and (pShip.GetAlertLevel() == App.ShipClass.RED_ALERT):
		lTargets = GetTargets(pShip)
	if len(lTargets) == 0:
		StopAll()
		return
	for tEntry in GetFireEvents():
		eGroup = tEntry[1]
		if g_dManual.get(eGroup):
			# The player is firing this group: hands off.
			g_dFiring[eGroup] = None
		else:
			# Each group on its own: an error in one does not stop the others.
			try:
				pSystem = pShip.GetWeaponSystemGroup(eGroup)
				pTarget = None
				g_dScore[eGroup] = None
				if pSystem != None:
					pTarget = GroupTarget(pShip, pSystem, lTargets, eGroup)
				lSec = []
				bHeadSec = 0
				sPlan = None
				if pSystem != None:
					sPlan = Plannable(pSystem)
				bPlanned = 0
				if (sPlan != None) and ((g_dFiring.get(eGroup) == None) or (not IsFiring(pSystem))):
					# About to press (or press again) a torpedo or arc-percent pulse group: plan its list.
					bPlanned = 1
					try:
						tPlan = PlanGroup(pShip, pSystem, pTarget, lTargets, eGroup)
						pTarget = tPlan[0]
						lSec = tPlan[1]
						bHeadSec = tPlan[2]
						if ArcRuleOn(sPlan):
							NoteArcPlan(pShip, pSystem, eGroup, pTarget, lSec, bHeadSec)
					except:
						LogPlanError(sPlan + " plan error: " + str(sys.exc_info()[1]))
				bKeepHead = 0
				iOldHead = g_dSecHead.get(eGroup)
				bPhaser = 0
				if (pSystem != None) and (sPlan == None) and g_iSecondaryPhasers and IsPhaserGroup(pSystem):
					# Phaser group: no bank reaches the main target, start at a secondary a ready bank reaches.
					bPhaser = 1
					try:
						tStep = PlanPhaserStep(pShip, pSystem, pTarget, lTargets, eGroup)
						pTarget = tStep[0]
						lSec = tStep[1]
						bHeadSec = tStep[2]
						bKeepHead = tStep[3]
					except:
						LogPlanError("phaser plan error: " + str(sys.exc_info()[1]))
				if bKeepHead:
					# A held phaser group started at a secondary keeps firing: no stop and start.
					pass
				elif (not bPlanned) and (pTarget == None) and (sPlan != None) and (g_dFiring.get(eGroup) != None) and (g_dSecHead.get(eGroup) == g_dFiring.get(eGroup)) and (not IsTapped(pSystem)):
					# A held group started at a secondary keeps firing: its list stays.
					pass
				else:
					if bPhaser and (iOldHead != None) and (g_dFiring.get(eGroup) == iOldHead) and ((pTarget == None) or (pTarget.GetObjID() != iOldHead)):
						# Leaving a secondary head (main reachable again, or another head): restart clean.
						FireGroup(pShip, eGroup, None, 0)
					FireGroup(pShip, eGroup, pTarget, pTarget != None, lSec, bHeadSec)
					if bHeadSec and (pTarget != None):
						g_dSecHead[eGroup] = pTarget.GetObjID()
					else:
						g_dSecHead[eGroup] = None
			except:
				g_pCore.Log(NAME, "Group " + str(eGroup) + " error: " + str(sys.exc_info()[1]))
				try:
					FireGroup(pShip, eGroup, None, 0)
				except:
					pass


###############################################################################
#	Diagnostics (Debug = 1): which weapon functions this game offers
###############################################################################
def Probe():
	pPlayer = GetPlayer()
	if (pPlayer == None) or (g_pCore == None):
		return
	lNames = ("CanHit", "CanHitTarget", "IsInArc", "Fire", "IsTubeReady", "GetNumReady",
		"GetMaxDamageDistance", "GetChargePercentage", "GetLaunchSpeed", "SetFiringChainMode",
		"GetNumFiringChains", "GetFiringChainMode", "StartFiring", "StopFiring")
	for tEntry in GetFireEvents():
		pSystem = None
		try:
			pSystem = pPlayer.GetWeaponSystemGroup(tEntry[1])
		except:
			pass
		if pSystem == None:
			g_pCore.Log(NAME, "Group " + str(tEntry[1]) + ": none")
		else:
			lFound = []
			pChild = None
			try:
				if pSystem.GetNumChildSubsystems() > 0:
					pChild = pSystem.GetChildSubsystem(0)
			except:
				pass
			for sName in lNames:
				sWhere = ""
				if hasattr(pSystem, sName):
					sWhere = "S"
				if (pChild != None) and hasattr(pChild, sName):
					sWhere = sWhere + "W"
				if sWhere != "":
					lFound.append(sName + ":" + sWhere)
			g_pCore.Log(NAME, "Group " + str(tEntry[1]) + " " + str(pSystem.__class__.__name__) + ": " + str(lFound))
	g_pCore.Log(NAME, "GetPredictedPosition: " + str(hasattr(pPlayer, "GetPredictedPosition")))


###############################################################################
#	Spaceframe module interface
###############################################################################
def Start(pCore):
	global g_pCore, g_pMission, g_dManual, g_dFiring, g_dSecHead
	Stop()
	g_dSecHead = {}
	g_pCore = pCore
	import Custom.Spaceframe.Modules.AutoFire.Config
	reload(Custom.Spaceframe.Modules.AutoFire.Config)
	LoadConfig()
	g_dManual = {}
	g_dFiring = {}
	for tEntry in GetFireEvents():
		g_dManual[tEntry[1]] = 0
		g_dFiring[tEntry[1]] = None
	try:
		BindKey()
	except:
		pCore.Log(NAME, "Could not bind the key: " + str(sys.exc_info()[1]))
	g_pMission = GetMission()
	if g_pMission != None:
		try:
			for tEntry in GetFireEvents():
				App.g_kEventManager.AddBroadcastPythonFuncHandler(tEntry[0], g_pMission, MANUAL_HANDLER)
		except:
			pCore.Log(NAME, "Could not register handlers: " + str(sys.exc_info()[1]))
	if g_bDebug and (g_pMission != None):
		try:
			App.g_kEventManager.AddBroadcastPythonFuncHandler(App.ET_TORPEDO_ENTERED_SET, g_pMission, TORP_HANDLER)
		except:
			pCore.Log(NAME, "Could not register the torpedo handler: " + str(sys.exc_info()[1]))
	try:
		CreateButton()
	except:
		pCore.Log(NAME, "Could not create the menu button: " + str(sys.exc_info()[1]))
	SetEnabled(getattr(GetConfig(), "StartEnabled", 0))
	if g_bDebug:
		Probe()


def Stop():
	# Called when the battle ends, while the game is destroying the ships:
	# nothing is asked of them (their weapons stop with them), Auto Fire
	# only forgets what it was firing.
	global g_iOn, g_iShipID, g_pMission, g_iFiringShipID, g_dSecHead, g_dPlanNote, g_tTorpDecision
	g_tTorpDecision = None
	try:
		GetWarpHold().Reset()
	except:
		pass
	try:
		GetTorpDiag().Reset()
	except:
		if g_pCore != None:
			g_pCore.Log(NAME, "Torpedo diagnostics reset error: " + str(sys.exc_info()[1]))
	for tEntry in GetFireEvents():
		g_dFiring[tEntry[1]] = None
	g_dSecHead = {}
	g_dPlanNote = {}
	g_iFiringShipID = None
	ForgetSpread()
	ForgetArc()
	StopTimer()
	g_iOn = 0
	g_iShipID = None
	if g_pMission != None:
		try:
			for tEntry in GetFireEvents():
				App.g_kEventManager.RemoveBroadcastHandler(tEntry[0], g_pMission, MANUAL_HANDLER)
		except:
			pass
		try:
			App.g_kEventManager.RemoveBroadcastHandler(App.ET_TORPEDO_ENTERED_SET, g_pMission, TORP_HANDLER)
		except:
			pass
	g_pMission = None
	UnbindKey()
	DeleteButton()


def Tick(lShips):
	pass


def Diag():
	print ("  on = " + str(g_iOn) + ", enabled = " + str(IsEnabled()) + ", key = " + str(g_iKey) + ", manual = " + str(g_dManual) + ", firing = " + str(g_dFiring) + ", timer = " + str(g_pTimer != None))
