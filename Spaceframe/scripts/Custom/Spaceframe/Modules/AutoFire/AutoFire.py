###############################################################################
#	AutoFire.py
#
#	Spaceframe module, version 0.3
#
#	Fires the player's weapons by firing-solution rules while switched on,
#	so the player can concentrate on manoeuvring. Only the ship the player
#	controls, and only if it has the AutoFire technology (Ships.py).
#	- Switched on and off with a key (ToggleKey, default L) or with the
#	  "Auto Fire" button in the tactical officer's menu.
#	- Manual fire has priority: while the player holds the fire key of a
#	  weapon group, Auto Fire leaves that group alone.
#	- Phasers by range, arc and charge; torpedoes by firing solution or
#	  firing cone (Solution.py), with automatic spread; pulse weapons by
#	  firing solution; torpedoes and pulse tapped (TapFire).
#	- Targets: the player's, the nearest enemy, or each group's best
#	  (TargetMode).
#	Settings: Modules\AutoFire\Config.py
###############################################################################
import App
import sys

NAME = "AutoFire"
BUTTON_TEXT = "Auto Fire"

g_pCore = None
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

KEY_HANDLER = "Custom.Spaceframe.Modules.AutoFire.AutoFire.OnKeyboard"
BUTTON_HANDLER = "Custom.Spaceframe.Modules.AutoFire.AutoFire.OnMenuButton"
MANUAL_HANDLER = "Custom.Spaceframe.Modules.AutoFire.AutoFire.OnManualFire"


def GetConfig():
	import Custom.Spaceframe.Modules.AutoFire.Config
	return Custom.Spaceframe.Modules.AutoFire.Config


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
		StopAll()
		RestoreSpread()
		StopTimer()
	UpdateButton()
	if g_pCore != None:
		g_pCore.Log(NAME, "Auto Fire " + str(IsEnabled()))


def Toggle():
	SetEnabled(not IsEnabled())


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
	iMode = int(getattr(GetConfig(), "TargetMode", 0))
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
	pConfig = GetConfig()
	if not pBank.CanHit(pTarget.GetWorldLocation()):
		return 0
	if pBank.GetChargePercentage() * 100.0 < float(getattr(pConfig, "PhaserMinCharge", 50)):
		return 0
	fRange = pBank.GetMaxDamageDistance() * float(getattr(pConfig, "PhaserRange", 100)) / 100.0
	if GetDistance(pBank, pTarget) > fRange:
		return 0
	return 1


def GetSolution():
	import Custom.Spaceframe.Modules.AutoFire.Solution
	return Custom.Spaceframe.Modules.AutoFire.Solution


def ApplySolutionConfig():
	# The firing solution's settings, from Config.py (percent -> fraction).
	pConfig = GetConfig()
	pSolution = GetSolution()
	pSolution.MANEUVER_WEIGHT = float(getattr(pConfig, "TargetEvasion", 10)) / 100.0
	pSolution.GUIDANCE_STRENGTH = float(getattr(pConfig, "GuidanceStrength", 100)) / 100.0
	pSolution.GUIDANCE_LIMIT = float(getattr(pConfig, "GuidanceLimit", 50)) / 100.0
	pSolution.TARGET_SIZE = float(getattr(pConfig, "TargetSize", 100)) / 100.0
	pSolution.MAX_ANGLE = float(getattr(pConfig, "TubeMaxAngle", 90))
	pSolution.TORPEDO_RULE = int(getattr(pConfig, "TorpedoRule", 1))
	pSolution.PULSE_RULE = int(getattr(pConfig, "PulseRule", 1))
	pSolution.CONE_FAR = float(getattr(pConfig, "ConeAngleFar", 15))
	pSolution.CONE_NEAR = float(getattr(pConfig, "ConeAngleNear", 45))
	pSolution.CONE_FAR_DISTANCE = KilometersToUnits(float(getattr(pConfig, "ConeFarDistance", 30)))
	pSolution.CONE_NEAR_DISTANCE = KilometersToUnits(float(getattr(pConfig, "ConeNearDistance", 5)))
	pSolution.PULSE_CONE_FAR = float(getattr(pConfig, "PulseConeAngleFar", 45))
	pSolution.PULSE_CONE_NEAR = float(getattr(pConfig, "PulseConeAngleNear", 90))
	pSolution.PULSE_CONE_FAR_DISTANCE = KilometersToUnits(float(getattr(pConfig, "PulseConeFarDistance", 30)))
	pSolution.PULSE_CONE_NEAR_DISTANCE = KilometersToUnits(float(getattr(pConfig, "PulseConeNearDistance", 5)))


def BestTorpedoScore(pShip, pSystem, pTarget):
	# Best firing solution among the loaded tubes (0 if none is loaded).
	pSolution = GetSolution()
	tInfo = pSolution.GetProjectileInfo(None, pSystem)
	vOffset = GetOffset(pShip, pTarget)
	fBest = 0.0
	for iChild in range(pSystem.GetNumChildSubsystems()):
		pTube = App.TorpedoTube_Cast(pSystem.GetChildSubsystem(iChild))
		if (pTube != None) and (pTube.GetNumReady() > 0):
			fScore = pSolution.Score(pShip, pTarget, vOffset, pTube, pTube.CalculateRoughDirection(), tInfo)
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
	# The target with the best firing solution, if good enough.
	pConfig = GetConfig()
	if TorpedoesLeft(pTorpedoes) <= int(getattr(pConfig, "TorpedoReserve", 0)):
		return None
	pBest = None
	fBest = -1.0
	for pTarget in lTargets:
		fScore = BestTorpedoScore(pShip, pTorpedoes, pTarget)
		if fScore > fBest:
			fBest = fScore
			pBest = pTarget
	if pBest == None:
		return None
	g_dScore[eGroup] = fBest
	fMinimum = float(getattr(pConfig, "TorpedoMinSolution", 70))
	if int(getattr(pConfig, "TorpedoRule", 1)) == 2:
		fMinimum = 1.0	# firing cone: any tube inside it
	if fBest >= fMinimum:
		ApplySpread(pShip, pTorpedoes, pBest, fBest)
		return pBest
	return None


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


def ApplySpread(pShip, pTorpedoes, pTarget, fScore):
	# Spread torpedoes leave in a fan and only turn to the target after a
	# while: closer than SpreadMinDistance they would fly past it.
	global g_iPlayerSpread, g_iSetSpread, g_iSpreadShipID
	pConfig = GetConfig()
	iWant = 0
	if fScore >= float(getattr(pConfig, "SpreadMinSolution", 85)):
		fMinimum = KilometersToUnits(float(getattr(pConfig, "SpreadMinDistance", 0)))
		if GetDistance(pShip, pTarget) >= fMinimum:
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


def PulseReady(pWeapon, pTarget):
	# 1 if this pulse weapon is charged enough and can reach the target.
	if pWeapon.GetChargeLevel() < pWeapon.GetMinFiringCharge():
		return 0
	try:
		return pWeapon.CanHitTarget(pTarget)
	except:
		# Unknown: the game itself only fires weapons that can hit.
		return 1


def BestPulseScore(pShip, pSystem, pTarget):
	# Best score among the charged pulse weapons that can reach the target.
	# PulseRule 1 (firing solution): they aim themselves inside their arc,
	# so only the flight (target evasion, projectile lifetime) counts.
	# PulseRule 2 (firing cone): the pulse cone (PulseCone*) around where
	# the weapon points.
	pSolution = GetSolution()
	vOffset = GetOffset(pShip, pTarget)
	iRule = int(getattr(GetConfig(), "PulseRule", 1))
	fBest = 0.0
	for iChild in range(pSystem.GetNumChildSubsystems()):
		pWeapon = App.PulseWeapon_Cast(pSystem.GetChildSubsystem(iChild))
		if (pWeapon != None) and PulseReady(pWeapon, pTarget):
			tInfo = pSolution.GetProjectileInfo(pWeapon, pSystem)
			vDirection = None
			if iRule == 2:
				vDirection = pWeapon.CalculateRoughDirection()
			fScore = pSolution.Score(pShip, pTarget, vOffset, pWeapon, vDirection, tInfo, iRule, 1)
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
		return None
	g_dScore[eGroup] = fBest
	fMinimum = float(getattr(GetConfig(), "PulseMinSolution", 70))
	if int(getattr(GetConfig(), "PulseRule", 1)) == 2:
		fMinimum = 1.0	# firing cone: any weapon inside it
	if fBest >= fMinimum:
		return pBest
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
	if not int(getattr(GetConfig(), "TapFire", 1)):
		return 0
	if App.TorpedoSystem_Cast(pSystem) != None:
		return 1
	if App.PulseWeaponSystem_Cast(pSystem) != None:
		return 1
	return 0


def FireGroup(pShip, eGroup, pTarget, bFire):
	# Starts or stops one weapon group, like the game's fire keys do.
	# Only stops what Auto Fire itself started. Tapped groups are pressed
	# on one cycle and released on the next while they should fire.
	pSystem = pShip.GetWeaponSystemGroup(eGroup)
	if pSystem == None:
		g_dFiring[eGroup] = None
		return
	if bFire:
		iID = pTarget.GetObjID()
		if IsTapped(pSystem):
			if g_dFiring.get(eGroup) != None:
				pSystem.StopFiring()
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
		try:
			pSystem.SetForceUpdate(1)
		except:
			pass
		g_dFiring[eGroup] = iID
		SetFiringShip(pShip)
		if g_dScore.get(eGroup) != None:
			g_pCore.Log(NAME, "Group " + str(eGroup) + " fires, solution " + str(int(g_dScore[eGroup])))
	elif g_dFiring.get(eGroup) != None:
		pSystem.StopFiring()
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
				FireGroup(pShip, eGroup, pTarget, pTarget != None)
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
	global g_pCore, g_pMission, g_dManual, g_dFiring
	Stop()
	g_pCore = pCore
	import Custom.Spaceframe.Modules.AutoFire.Config
	reload(Custom.Spaceframe.Modules.AutoFire.Config)
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
	try:
		CreateButton()
	except:
		pCore.Log(NAME, "Could not create the menu button: " + str(sys.exc_info()[1]))
	try:
		ApplySolutionConfig()
	except:
		pCore.Log(NAME, "Solution settings error: " + str(sys.exc_info()[1]))
	SetEnabled(getattr(GetConfig(), "StartEnabled", 0))
	Probe()


def Stop():
	# Called when the battle ends, while the game is destroying the ships:
	# nothing is asked of them (their weapons stop with them), Auto Fire
	# only forgets what it was firing.
	global g_iOn, g_iShipID, g_pMission, g_iFiringShipID
	for tEntry in GetFireEvents():
		g_dFiring[tEntry[1]] = None
	g_iFiringShipID = None
	ForgetSpread()
	StopTimer()
	g_iOn = 0
	g_iShipID = None
	if g_pMission != None:
		try:
			for tEntry in GetFireEvents():
				App.g_kEventManager.RemoveBroadcastHandler(tEntry[0], g_pMission, MANUAL_HANDLER)
		except:
			pass
	g_pMission = None
	UnbindKey()
	DeleteButton()


def Tick(lShips):
	pass


def Diag():
	print ("  on = " + str(g_iOn) + ", enabled = " + str(IsEnabled()) + ", key = " + str(g_iKey) + ", manual = " + str(g_dManual) + ", firing = " + str(g_dFiring) + ", timer = " + str(g_pTimer != None))
