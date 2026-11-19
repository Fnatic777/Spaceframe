###############################################################################
#	SecondaryTarget.py
#
#	Spaceframe module, version 0.2
#
#	Weapons that cannot reach the player's main target shoot at other
#	enemies of the mission, without taking fire from the main target. Only
#	the ship the player controls, and only if it has the SecondaryTarget
#	technology (Ships.py: a sum of 1 phasers, 2 torpedoes, 4 pulse weapons;
#	Def = Weapons in Config.py; 0 = off).
#	- Switched on and off with a key (ToggleKey, default J) or with the
#	  "Secondary Target" button in the tactical officer's menu (same
#	  mechanism as Auto Fire).
#	- While ON the single-fire restriction of the ship's phasers is lifted
#	  (pulse weapons keep their own setting); the original values are
#	  restored when it goes OFF.
#	Settings: Modules\SecondaryTarget\Config.py
###############################################################################
import App
import sys

NAME = "SecondaryTarget"
VERSION = "0.2"
BUTTON_TEXT = "Secondary Target"

g_pCore = None
g_pTimer = None		# the module's own timer, only while switched on
g_pMission = None	# object the broadcast handlers were registered on
g_dLifted = {}		# ship ID -> {weapon group: original IsSingleFire}
g_dAdded = {}		# (ship ID, weapon group) -> IDs of the secondaries this module added
g_iShipID = None	# the player's ship the module last worked on
g_pAutoFire = None	# AutoFire module (helpers), imported on first use
g_bAutoFireFailed = 0	# 1 = the import failed: no candidates, logged once
g_iOn = 0		# switched on (by StartEnabled or the player)
g_eButton = None	# event type of the menu button (one per game session)
g_iKey = None		# key code of the toggle key (lower case)
g_pTopWindow = None	# window holding the keyboard handler
g_pButton = None	# the menu button
g_pMenu = None		# the tactical menu holding the button

# Settings read once by LoadConfig() at Start (the hot path never asks Config).
# Initial values = the defaults, so code run before Start behaves the same.
g_bDebug = 0
g_iWeapons = 7
g_fInterval = 0.2
g_iMaxCandidates = 4
g_fSecondaryRange = 100.0
g_fTorpedoMinSolution = 70.0
g_iStartEnabled = 1

BIT_PHASER = 1
BIT_TORPEDO = 2
BIT_PULSE = 4
BIT_ALL = 7

FIRE_HANDLER = "Custom.Spaceframe.Modules.SecondaryTarget.SecondaryTarget.OnFireKey"
KEY_HANDLER = "Custom.Spaceframe.Modules.SecondaryTarget.SecondaryTarget.OnKeyboard"
BUTTON_HANDLER = "Custom.Spaceframe.Modules.SecondaryTarget.SecondaryTarget.OnMenuButton"


def GetConfig():
	import Custom.Spaceframe.Modules.SecondaryTarget.Config
	return Custom.Spaceframe.Modules.SecondaryTarget.Config


def LoadConfig():
	# Reads every setting once; edits apply from the next battle (Start).
	global g_bDebug, g_iWeapons, g_fInterval, g_iMaxCandidates
	global g_fSecondaryRange, g_fTorpedoMinSolution, g_iStartEnabled
	pConfig = GetConfig()
	g_iStartEnabled = int(getattr(pConfig, "StartEnabled", 1))
	g_iWeapons = int(getattr(pConfig, "Weapons", 7)) & BIT_ALL
	g_fInterval = float(getattr(pConfig, "Interval", 0.2))
	if g_fInterval < 0.05:
		g_fInterval = 0.05
	g_iMaxCandidates = int(getattr(pConfig, "MaxCandidates", 4))
	if g_iMaxCandidates < 1:
		g_iMaxCandidates = 1
	g_fSecondaryRange = float(getattr(pConfig, "SecondaryRange", 100))
	g_fTorpedoMinSolution = float(getattr(pConfig, "SecondaryTorpedoMinSolution", 70))
	g_bDebug = int(getattr(pConfig, "Debug", 0))
	if (not g_bDebug) and (g_pCore != None):
		try:
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


def DebugLog(sText):
	if g_bDebug and (g_pCore != None):
		g_pCore.Log(NAME, sText)


###############################################################################
#	State
###############################################################################
def GetMask(pShip):
	# Weapon types allowed on this ship: the bit sum of its SecondaryTarget
	# technology (-1 = Def: Config Weapons; 0 = off).
	if (pShip == None) or (g_pCore == None):
		return 0
	try:
		iValue = int(g_pCore.GetShipTech(pShip, NAME, 0))
	except:
		return 0
	if iValue == -1:
		iValue = g_iWeapons
	return iValue & BIT_ALL


def HasTech(pShip):
	return GetMask(pShip) != 0


###############################################################################
#	Single-fire lift and restore
#	(confirmed in game: the property belongs to the ship, not to its class;
#	SetSingleFire(0) lifts the one-target restriction, SetSingleFire(1) restores)
#	The lift happens for as long as the module is switched ON (all groups of
#	the kinds in the ship's mask); it is restored when it goes OFF, when the
#	ship changes, dies or loses the technology.
###############################################################################
def GetProp(pSystem):
	# The system's WeaponSystemProperty (cast unconfirmed: falls back to the
	# raw property object). Looked up fresh at every use, never kept.
	pRaw = pSystem.GetProperty()
	if pRaw == None:
		return None
	try:
		pProp = App.WeaponSystemProperty_Cast(pRaw)
		if pProp != None:
			return pProp
	except:
		pass
	return pRaw


def LiftSingleFire(pShip, pSystem, eGroup):
	# Sets IsSingleFire to 0 on the group's property. The original value is
	# recorded BEFORE the change (first lift wins), so a failure halfway still
	# leaves something to restore. Returns 1 when the lift went through.
	if (pShip == None) or (pSystem == None):
		return 0
	try:
		iID = pShip.GetObjID()
		pProp = GetProp(pSystem)
		if pProp == None:
			return 0
		if not g_dLifted.has_key(iID):
			g_dLifted[iID] = {}
		if not g_dLifted[iID].has_key(eGroup):
			g_dLifted[iID][eGroup] = pProp.IsSingleFire()
		pProp.SetSingleFire(0)
		return 1
	except:
		DebugLog("Lift error: " + str(sys.exc_info()[1]))
		return 0


def RestoreSingleFire(pShip):
	# Writes the recorded original back on the live ship (also while it is
	# dying: the engine still answers) and forgets it. Skipped only when the
	# ship object is gone. Never forces 1: an original 0 stays 0.
	if pShip == None:
		return 0
	try:
		iID = pShip.GetObjID()
	except:
		return 0
	if not g_dLifted.has_key(iID):
		return 0
	dGroups = g_dLifted[iID]
	del g_dLifted[iID]
	iDone = 0
	for eGroup in dGroups.keys():
		try:
			pSystem = pShip.GetWeaponSystemGroup(eGroup)
			if pSystem != None:
				pProp = GetProp(pSystem)
				if pProp != None:
					pProp.SetSingleFire(dGroups[eGroup])
					iDone = iDone + 1
		except:
			DebugLog("Restore error: " + str(sys.exc_info()[1]))
	return iDone


def RestoreGroup(pShip, eGroup):
	# Puts back the recorded single-fire of ONE group, only if it is lifted
	# right now (so it never flips back and forth). Returns 1 when written.
	try:
		iID = pShip.GetObjID()
		if (not g_dLifted.has_key(iID)) or (not g_dLifted[iID].has_key(eGroup)):
			return 0
		iOrig = g_dLifted[iID][eGroup]
		del g_dLifted[iID][eGroup]
		if len(g_dLifted[iID]) == 0:
			del g_dLifted[iID]
		pSystem = pShip.GetWeaponSystemGroup(eGroup)
		if pSystem == None:
			return 0
		pProp = GetProp(pSystem)
		if pProp == None:
			return 0
		pProp.SetSingleFire(iOrig)
		return 1
	except:
		DebugLog("RestoreGroup error: " + str(sys.exc_info()[1]))
		return 0


def ReleaseShipID(iID):
	# Restores by ID: looks the ship up again; nothing is asked when it is gone.
	pShip = None
	try:
		pShip = App.ShipClass_GetObjectByID(None, iID)
	except:
		pShip = None
	if pShip == None:
		if g_dLifted.has_key(iID):
			del g_dLifted[iID]
		return 0
	return RestoreSingleFire(pShip)


def ForgetAll():
	# Drops every record without touching any ship (used by Stop).
	global g_dLifted, g_dAdded, g_iShipID
	g_dLifted = {}
	g_dAdded = {}
	g_iShipID = None


###############################################################################
#	Candidates and free weapons
#	(confirmed in game: PhaserBank.CanHit takes a WORLD POINT; for pulse
#	weapons CanHitTarget(point, vector) answers 0 even dead ahead, so pulse
#	weapons are all treated as free and every candidate as reachable)
###############################################################################
def GetAutoFire():
	# AutoFire's helpers (enemy list, distances). If the import fails the
	# module has no candidates: it disables itself and logs once.
	global g_pAutoFire, g_bAutoFireFailed
	if g_pAutoFire != None:
		return g_pAutoFire
	if g_bAutoFireFailed:
		return None
	try:
		import Custom.Spaceframe.Modules.AutoFire.AutoFire
		g_pAutoFire = Custom.Spaceframe.Modules.AutoFire.AutoFire
	except:
		g_bAutoFireFailed = 1
		g_pAutoFire = None
		if g_pCore != None:
			g_pCore.Log(NAME, "AutoFire helpers not available, module disabled: " + str(sys.exc_info()[1]))
	return g_pAutoFire


def GetWeapons(pSystem, sKind):
	# The group's weapons of the kind ("phaser" or "pulse"), looked up fresh.
	lWeapons = []
	if (pSystem == None) or ((sKind != "phaser") and (sKind != "pulse")):
		return lWeapons
	try:
		for iChild in range(pSystem.GetNumChildSubsystems()):
			pChild = pSystem.GetChildSubsystem(iChild)
			if sKind == "phaser":
				pWeapon = App.PhaserBank_Cast(pChild)
			else:
				pWeapon = App.PulseWeapon_Cast(pChild)
			if pWeapon != None:
				lWeapons.append(pWeapon)
	except:
		DebugLog("GetWeapons error: " + str(sys.exc_info()[1]))
		return []
	return lWeapons


def GetCandidates(pShip, pMain, pSystem, sKind):
	# Live enemy ships of the mission, nearest first, other than the main
	# target; at most MaxCandidates. Phasers: only those within SecondaryRange
	# percent of the banks' maximum damage distance. Pulse: no range filter.
	lResult = []
	pAF = GetAutoFire()
	if (pAF == None) or (pShip == None):
		return lResult
	try:
		fLimit = 0.0
		if sKind == "phaser":
			for pBank in GetWeapons(pSystem, "phaser"):
				fMax = pBank.GetMaxDamageDistance()
				if fMax > fLimit:
					fLimit = fMax
			fLimit = fLimit * g_fSecondaryRange / 100.0
			if fLimit <= 0.0:
				return lResult
		elif sKind != "pulse":
			return lResult
		iMain = None
		if pMain != None:
			iMain = pMain.GetObjID()
		iShip = pShip.GetObjID()
		lEnemies = []
		for pEnemy in pAF.GetEnemies(pShip):
			iID = pEnemy.GetObjID()
			if (iID != iMain) and (iID != iShip) and pAF.IsLive(pEnemy):
				lEnemies.append(pEnemy)
		for pEnemy in pAF.SortByDistance(pShip, lEnemies):
			if len(lResult) >= g_iMaxCandidates:
				break
			if (sKind == "pulse") or (pAF.GetDistance(pShip, pEnemy) <= fLimit):
				lResult.append(pEnemy)
	except:
		DebugLog("GetCandidates error: " + str(sys.exc_info()[1]))
		return []
	return lResult


def FreeWeapons(pSystem, pMain, sKind):
	# Weapons that do not reach the main target (phaser: CanHit on its world
	# point is false). Pulse weapons are all free. No main target: nothing.
	lFree = []
	if pMain == None:
		return lFree
	lWeapons = GetWeapons(pSystem, sKind)
	if sKind != "phaser":
		return lWeapons
	try:
		pPoint = pMain.GetWorldLocation()
	except:
		DebugLog("FreeWeapons error: " + str(sys.exc_info()[1]))
		return lFree
	for pBank in lWeapons:
		try:
			if not pBank.CanHit(pPoint):
				lFree.append(pBank)
		except:
			DebugLog("CanHit error: " + str(sys.exc_info()[1]))
	return lFree


def WantedTargets(pShip, pSystem, pMain, sKind):
	# Object IDs of the candidates that at least one free weapon can reach.
	lWanted = []
	try:
		lFree = FreeWeapons(pSystem, pMain, sKind)
		if len(lFree) == 0:
			return lWanted
		for pCandidate in GetCandidates(pShip, pMain, pSystem, sKind):
			bReach = 0
			if sKind == "pulse":
				bReach = 1
			else:
				pPoint = pCandidate.GetWorldLocation()
				for pBank in lFree:
					try:
						if pBank.CanHit(pPoint):
							bReach = 1
							break
					except:
						DebugLog("CanHit error: " + str(sys.exc_info()[1]))
			if bReach:
				lWanted.append(pCandidate.GetObjID())
	except:
		DebugLog("WantedTargets error: " + str(sys.exc_info()[1]))
		return []
	return lWanted


###############################################################################
#	Cycle timer
###############################################################################
class Timer:
	# The module's own timer (same form as AutoFire's), only while the
	# player's ship has the technology.
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
			Cycle()
		except:
			if g_pCore != None:
				g_pCore.Log(NAME, "Cycle error: " + str(sys.exc_info()[1]))


def StartTimer():
	global g_pTimer
	if g_pTimer == None:
		g_pTimer = Timer(g_fInterval)


def StopTimer():
	global g_pTimer
	if g_pTimer != None:
		g_pTimer.bActive = 0
		g_pTimer.pProcess = None
	g_pTimer = None


###############################################################################
#	Target list maintenance
#	(confirmed in game: StartFiring(target, point) adds to the system's target
#	list; list order = [main, secondaries]; weapons that reach several targets
#	fire at the first listed; the key release empties the whole list. The
#	module NEVER starts a group: it only adds secondaries to a group that is
#	already firing at the player's selected target, because pressing fire
#	again at the same target may stop it)
###############################################################################
def DebugPrint(sText):
	# Debug = 1 only: console line (plus the core log).
	if not g_bDebug:
		return
	DebugLog(sText)
	try:
		App.CPyDebug().Print("SecondaryTarget: " + sText + "\n")
	except:
		pass


def DebugBanner(sText):
	# Debug = 1 only: a short line on screen (the console is not enough).
	if not g_bDebug:
		return
	try:
		import MissionLib
		MissionLib.TextBanner(None, App.TGString(sText), 0.0, 0.2, 4.0, 12, 1, 0)
	except:
		DebugLog("TextBanner error: " + str(sys.exc_info()[1]))


def IDText(lIDs):
	sText = ""
	for iID in lIDs:
		if sText != "":
			sText = sText + ","
		sText = sText + str(iID)
	return sText


def GroupKind(pSystem):
	# "pulse", "torpedo" or "phaser" (anything else a group can be).
	try:
		if App.PulseWeaponSystem_Cast(pSystem) != None:
			return "pulse"
		if App.TorpedoSystem_Cast(pSystem) != None:
			return "torpedo"
	except:
		return ""
	return "phaser"


def KindBit(sKind):
	if sKind == "phaser":
		return BIT_PHASER
	if sKind == "pulse":
		return BIT_PULSE
	return 0


def ZeroPoint():
	pPoint = App.TGPoint3()
	try:
		pPoint.SetXYZ(0.0, 0.0, 0.0)
	except:
		pass
	return pPoint


def Lookup(iID):
	# A ship by ID, looked up fresh (never kept between calls).
	try:
		return App.ShipClass_GetObjectByID(None, iID)
	except:
		return None


def ForgetAdded(iID, eGroup=None):
	# Drops the record of secondaries this module added (ship, one group or all).
	global g_dAdded
	for tKey in g_dAdded.keys():
		if (tKey[0] == iID) and ((eGroup == None) or (tKey[1] == eGroup)):
			del g_dAdded[tKey]


def StopAdded(pSystem, lIDs, iMain):
	# Stops firing at the secondaries in lIDs that are still in the group's
	# list (never the main target); each one guarded.
	for iID in lIDs:
		if iID != iMain:
			try:
				pOld = Lookup(iID)
				if (pOld != None) and pSystem.IsInTargetList(pOld):
					pSystem.StopFiringAtTarget(pOld)
			except:
				DebugLog("Stop secondary error: " + str(sys.exc_info()[1]))


def StopAllAdded(pShip):
	# Removes every secondary this module added on the (live) ship, all groups.
	try:
		iShip = pShip.GetObjID()
	except:
		return
	for tKey in g_dAdded.keys():
		if tKey[0] == iShip:
			try:
				pSystem = pShip.GetWeaponSystemGroup(tKey[1])
				if pSystem != None:
					StopAdded(pSystem, g_dAdded[tKey], None)
			except:
				DebugLog("StopAllAdded error: " + str(sys.exc_info()[1]))


def MaintainGroup(pShip, pMain, eGroup, iMask):
	# One group, one cycle. Secondaries are only added to a group that is
	# firing with the player's selected target in its list; otherwise the
	# group's secondaries are removed. Single-fire is not touched here (it is
	# lifted for as long as the module is ON, see LiftShip).
	global g_dAdded
	try:
		pSystem = pShip.GetWeaponSystemGroup(eGroup)
		if pSystem == None:
			return
		sKind = GroupKind(pSystem)
		if (KindBit(sKind) & iMask) == 0:
			return
		iShip = pShip.GetObjID()
		iMain = pMain.GetObjID()
		tKey = (iShip, eGroup)
		lRecord = []
		if g_dAdded.has_key(tKey):
			lRecord = g_dAdded[tKey]
		if (not pSystem.IsFiring()) or (not pSystem.IsInTargetList(pMain)):
			# Not our case (the key release normally emptied the list already).
			StopAdded(pSystem, lRecord, iMain)
			ForgetAdded(iShip, eGroup)
			return
		lWanted = WantedTargets(pShip, pSystem, pMain, sKind)
		if (len(lWanted) == 0) and (len(lRecord) == 0):
			return
		lAdded = []
		lRemoved = []
		lKeep = []
		for iID in lRecord:
			if (iID in lWanted) and (iID != iMain):
				lKeep.append(iID)
			elif iID != iMain:
				pOld = Lookup(iID)
				if pOld != None:
					if pSystem.IsInTargetList(pOld):
						pSystem.StopFiringAtTarget(pOld)
						lRemoved.append(iID)
		pZero = ZeroPoint()
		for iID in lWanted:
			pNew = Lookup(iID)
			if pNew != None:
				if not pSystem.IsInTargetList(pNew):
					pSystem.StartFiring(pNew, pZero)
					lAdded.append(iID)
				if not (iID in lKeep):
					lKeep.append(iID)
		g_dAdded[tKey] = lKeep
		if (len(lAdded) > 0) or (len(lRemoved) > 0):
			sText = "group " + str(eGroup) + " (" + sKind + ")"
			if len(lAdded) > 0:
				sText = sText + " +" + IDText(lAdded)
			if len(lRemoved) > 0:
				sText = sText + " -" + IDText(lRemoved)
			DebugPrint(sText)
			DebugBanner("Secondary target: " + sText)
	except:
		DebugLog("Group " + str(eGroup) + " error: " + str(sys.exc_info()[1]))


def ReleaseCurrent(iID):
	# Takes the secondaries back and gives the single-fire property back, both
	# only if the ship is found live by ID (a gone ship is just forgotten).
	pShip = Lookup(iID)
	if pShip != None:
		StopAllAdded(pShip)
	ForgetAdded(iID)
	if g_dLifted.has_key(iID):
		ReleaseShipID(iID)


def StopGroups():
	# The player's ship changed: release the old ship (only if it is still
	# live, looked up by ID) and forget it.
	global g_iShipID
	if g_iShipID != None:
		ReleaseCurrent(g_iShipID)
	g_iShipID = None


def LiftShip(pShip, iMask):
	# Lifts single-fire on every PHASER group in the mask that is not lifted
	# yet. Pulse weapons keep their own single-fire setting (a Defiant fires
	# its four cannons together; a single-fire pulse stays single) and
	# torpedoes stay inactive. Groups whose kind left the mask, or that are
	# not phasers, are given back. The original value is recorded before the
	# first change.
	for tEntry in GetFireEvents():
		try:
			pSystem = pShip.GetWeaponSystemGroup(tEntry[1])
			if pSystem != None:
				iShip = pShip.GetObjID()
				sKind = GroupKind(pSystem)
				if (sKind != "phaser") or ((KindBit(sKind) & iMask) == 0):
					RestoreGroup(pShip, tEntry[1])
				elif (not g_dLifted.has_key(iShip)) or (not g_dLifted[iShip].has_key(tEntry[1])):
					LiftSingleFire(pShip, pSystem, tEntry[1])
		except:
			DebugLog("LiftShip error: " + str(sys.exc_info()[1]))


def DropSecondaries(pShip):
	# Removes the secondaries this module added (the ship stays lifted).
	StopAllAdded(pShip)
	try:
		ForgetAdded(pShip.GetObjID())
	except:
		pass


def Cycle():
	# One cycle of the module (timer target, only while switched ON).
	global g_iShipID
	if not g_iOn:
		return
	pPlayer = GetPlayer()
	if pPlayer == None:
		return
	iID = pPlayer.GetObjID()
	if (g_iShipID != None) and (g_iShipID != iID):
		StopGroups()
		UpdateButton()
	g_iShipID = iID
	iMask = GetMask(pPlayer)
	if iMask == 0:
		# No tech (any more): nothing is asked of the groups.
		ReleaseCurrent(iID)
		return
	if pPlayer.IsDead() or pPlayer.IsDying():
		ReleaseCurrent(iID)
		return
	LiftShip(pPlayer, iMask)
	bOK = 1
	try:
		if pPlayer.IsCloaked():
			bOK = 0
		if pPlayer.GetAlertLevel() != App.ShipClass.RED_ALERT:
			bOK = 0
	except:
		bOK = 0
	if not bOK:
		DropSecondaries(pPlayer)
		return
	pAF = GetAutoFire()
	if pAF == None:
		DropSecondaries(pPlayer)
		return
	pMain = pAF.GetPlayerTarget(pPlayer)
	if (pMain == None) or (not pAF.IsEnemy(pMain)):
		# No usable main target: take the secondaries back (single-fire stays
		# lifted while the module is ON).
		DropSecondaries(pPlayer)
		return
	for tEntry in GetFireEvents():
		MaintainGroup(pPlayer, pMain, tEntry[1], iMask)


def OnFireKey(pObject, pEvent):
	# Fire-key handler. The key is not applied yet when this runs, so the
	# list is NOT touched here (starting the group would be wrong): the next
	# Cycle re-adds the secondaries once the group fires. A release empties
	# the game's list, so the record of added targets is forgotten.
	try:
		eType = pEvent.GetEventType()
		for tEntry in GetFireEvents():
			if (tEntry[0] == eType) and (not pEvent.GetBool()):
				if g_iShipID != None:
					ForgetAdded(g_iShipID, tEntry[1])
	except:
		DebugLog("OnFireKey error: " + str(sys.exc_info()[1]))
	try:
		pObject.CallNextHandler(pEvent)
	except:
		pass


###############################################################################
#	Switch (same mechanism as AutoFire's): key and menu button
###############################################################################
def IsEnabled():
	# 1 while switched ON and the ship the player controls has the technology.
	if not g_iOn:
		return 0
	return HasTech(GetPlayer())


def TurnOn(pPlayer):
	# Switches ON: the timer runs and single-fire is lifted at once on the
	# player's ship (when it has the technology; otherwise the cycle does it
	# as soon as the player gets a ship that has it).
	global g_iOn, g_iShipID
	g_iOn = 1
	StartTimer()
	iMask = GetMask(pPlayer)
	if (iMask != 0) and (not pPlayer.IsDead()) and (not pPlayer.IsDying()):
		g_iShipID = pPlayer.GetObjID()
		LiftShip(pPlayer, iMask)


def TurnOff():
	# Switches OFF: secondaries removed and single-fire restored in one step
	# (only if the ship is found live by ID).
	global g_iOn
	g_iOn = 0
	StopTimer()
	StopGroups()


def SetEnabled(iOn):
	pPlayer = GetPlayer()
	if iOn:
		if HasTech(pPlayer):
			TurnOn(pPlayer)
	else:
		TurnOff()
	UpdateButton()
	if g_pCore != None:
		g_pCore.Log(NAME, "Secondary Target " + str(IsEnabled()))


def Toggle():
	SetEnabled(not IsEnabled())


def GetKeyCode():
	sKey = str(getattr(GetConfig(), "ToggleKey", "J"))
	if len(sKey) != 1:
		sKey = "J"
	iKey = ord(sKey)
	if (iKey >= 65) and (iKey <= 90):
		iKey = iKey + 32	# the game binds lower-case letters
	return iKey


def BindKey():
	# Read straight from the keyboard on the top window (as AutoFire does): it
	# sees every key, even while a clicked menu has the focus.
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
	# Every key passes here: the toggle key (pressed, either case) switches the
	# module on a ship with the technology and is kept from the game; anything
	# else goes on as normal.
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


###############################################################################
#	Spaceframe module interface
###############################################################################
def Start(pCore):
	global g_pCore, g_pMission, g_pAutoFire, g_bAutoFireFailed
	Stop()
	g_pCore = pCore
	g_pAutoFire = None
	g_bAutoFireFailed = 0
	import Custom.Spaceframe.Modules.SecondaryTarget.Config
	reload(Custom.Spaceframe.Modules.SecondaryTarget.Config)
	LoadConfig()
	try:
		BindKey()
	except:
		pCore.Log(NAME, "Could not bind the key: " + str(sys.exc_info()[1]))
	g_pMission = GetMission()
	if g_pMission != None:
		try:
			for tEntry in GetFireEvents():
				App.g_kEventManager.AddBroadcastPythonFuncHandler(tEntry[0], g_pMission, FIRE_HANDLER)
		except:
			pCore.Log(NAME, "Could not register handlers: " + str(sys.exc_info()[1]))
	try:
		CreateButton()
	except:
		pCore.Log(NAME, "Could not create the menu button: " + str(sys.exc_info()[1]))
	# A ship without the technology can still be switched ON here: the lift
	# happens as soon as the player controls a ship that has it.
	if g_iStartEnabled:
		TurnOn(GetPlayer())
	UpdateButton()


def Stop():
	# Called when the battle ends, while the game is destroying the ships:
	# nothing is asked of them. Only handlers, the key, the button and the
	# timer are removed; the records are forgotten.
	global g_pMission, g_iOn
	StopTimer()
	ForgetAll()
	g_iOn = 0
	if g_pMission != None:
		try:
			for tEntry in GetFireEvents():
				App.g_kEventManager.RemoveBroadcastHandler(tEntry[0], g_pMission, FIRE_HANDLER)
		except:
			pass
	g_pMission = None
	UnbindKey()
	DeleteButton()


def Tick(lShips=None):
	# The core's cycle hook: not used, the module has its own timer.
	pass


def Diag():
	print ("  on = " + str(g_iOn) + ", key = " + str(g_iKey) + ", timer = " + str(g_pTimer != None) + ", mission = " + str(g_pMission != None) + ", weapons = " + str(g_iWeapons) + ", lifted = " + str(len(g_dLifted)))
