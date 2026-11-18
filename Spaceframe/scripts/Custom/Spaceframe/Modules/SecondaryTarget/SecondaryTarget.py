###############################################################################
#	SecondaryTarget.py
#
#	Spaceframe module, version 0.1 (skeleton)
#
#	Weapons that cannot reach the player's main target shoot at other
#	enemies of the mission, without taking fire from the main target. Only
#	the ship the player controls, and only if it has the SecondaryTarget
#	technology (Ships.py: a sum of 1 phasers, 2 torpedoes, 4 pulse weapons;
#	Def = Weapons in Config.py; 0 = off).
#	This version has the lifecycle only: config, tech lookup, own timer,
#	fire-key handlers. The target list work comes in the next steps.
#	Settings: Modules\SecondaryTarget\Config.py
###############################################################################
import App
import sys
import time

NAME = "SecondaryTarget"
VERSION = "0.1"

g_pCore = None
g_pTimer = None		# the module's own timer, only while the ship has the tech
g_pMission = None	# object the broadcast handlers were registered on
g_dLifted = {}		# ship ID -> {weapon group: original IsSingleFire}
g_dAdded = {}		# (ship ID, weapon group) -> IDs of the secondaries this module added
g_iShipID = None	# the player's ship the module last worked on
g_pAutoFire = None	# AutoFire module (helpers), imported on first use
g_bAutoFireFailed = 0	# 1 = the import failed: no candidates, logged once
g_dKept = {}		# (ship ID, group, target ID) -> weapon index of the bank left firing
g_dHeld = {}		# (ship ID, group) -> number of banks held last cycle (debug text)
g_pFastTimer = None	# fast timer for LimitPerTarget, only while a phaser group is lifted
g_dPhaser = {}		# (ship ID, group) -> 1 for the phaser groups this module lifted
g_dHold2 = {}		# HoldMode 2: (ship ID, group, bank index) -> ORIGINAL MinFiringCharge (float)
g_dHold2Target = {}	# HoldMode 2: same key -> ID of the target the held bank wants
g_dHoldAt = {}		# HoldMode 2: same key -> game time of its last hold or release
g_dKeptAt = {}		# HoldMode 2: (ship ID, group, target ID) -> game time the kept bank was chosen

# Settings read once by LoadConfig() at Start (the hot path never asks Config).
# Initial values = the defaults, so code run before Start behaves the same.
g_bDebug = 0
g_iWeapons = 7
g_fInterval = 0.2
g_iMaxCandidates = 4
g_fSecondaryRange = 100.0
g_fTorpedoMinSolution = 70.0
g_iPhaserPerTarget = 0
g_fLimitInterval = 0.05
g_iHoldMode = 0
g_fHoldHysteresis = 1.0
g_iHoldSafety = 1

BIT_PHASER = 1
BIT_TORPEDO = 2
BIT_PULSE = 4
BIT_ALL = 7

FIRE_HANDLER = "Custom.Spaceframe.Modules.SecondaryTarget.SecondaryTarget.OnFireKey"


def GetConfig():
	import Custom.Spaceframe.Modules.SecondaryTarget.Config
	return Custom.Spaceframe.Modules.SecondaryTarget.Config


def LoadConfig():
	# Reads every setting once; edits apply from the next battle (Start).
	global g_bDebug, g_iWeapons, g_fInterval, g_iMaxCandidates
	global g_fSecondaryRange, g_fTorpedoMinSolution, g_iPhaserPerTarget
	global g_fLimitInterval, g_iHoldMode, g_fHoldHysteresis, g_iHoldSafety
	pConfig = GetConfig()
	g_iWeapons = int(getattr(pConfig, "Weapons", 7)) & BIT_ALL
	g_fInterval = float(getattr(pConfig, "Interval", 0.2))
	if g_fInterval < 0.05:
		g_fInterval = 0.05
	g_iMaxCandidates = int(getattr(pConfig, "MaxCandidates", 4))
	if g_iMaxCandidates < 1:
		g_iMaxCandidates = 1
	g_fSecondaryRange = float(getattr(pConfig, "SecondaryRange", 100))
	g_fTorpedoMinSolution = float(getattr(pConfig, "SecondaryTorpedoMinSolution", 70))
	g_iPhaserPerTarget = int(getattr(pConfig, "PhaserPerTarget", 0))
	g_fLimitInterval = float(getattr(pConfig, "LimitInterval", 0.05))
	if g_fLimitInterval < 0.02:
		g_fLimitInterval = 0.02
	g_iHoldMode = int(getattr(pConfig, "HoldMode", 0))
	g_fHoldHysteresis = float(getattr(pConfig, "HoldHysteresis", 1.0))
	if g_fHoldHysteresis < 0.0:
		g_fHoldHysteresis = 0.0
	g_iHoldSafety = int(getattr(pConfig, "HoldSafety", 1))
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
#	The lift happens only while a group has secondary targets to shoot at;
#	it is restored per group when none is left, and for the whole ship when
#	the ship changes, the main target is gone, etc.
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


def ForgetKept(iID, eGroup=None):
	# Drops the per-target "kept bank" records of a ship (one group or all).
	for tKey in g_dKept.keys():
		if (tKey[0] == iID) and ((eGroup == None) or (tKey[1] == eGroup)):
			del g_dKept[tKey]
	for tKey in g_dHeld.keys():
		if (tKey[0] == iID) and ((eGroup == None) or (tKey[1] == eGroup)):
			del g_dHeld[tKey]
	for tKey in g_dPhaser.keys():
		if (tKey[0] == iID) and ((eGroup == None) or (tKey[1] == eGroup)):
			del g_dPhaser[tKey]
	for tKey in g_dKeptAt.keys():
		if (tKey[0] == iID) and ((eGroup == None) or (tKey[1] == eGroup)):
			del g_dKeptAt[tKey]


###############################################################################
#	HoldMode 2: a held bank gets StopFiring, then its property's
#	MinFiringCharge is raised above the bank's maximum charge, so the engine's
#	retry (every 0.33 s) always fails and the bank stays mute while it recharges
#	(exe analysis, not yet confirmed in game). The ORIGINAL value is recorded
#	before the change and written back on every release path. The ship is
#	always looked up fresh by ID; a ship that is gone is simply forgotten.
#	Stop() restores nothing on purpose: the battle end destroys the ships.
###############################################################################
def Now():
	# Game time in seconds (wall clock only if the engine call fails).
	try:
		return App.g_kUtopiaModule.GetGameTime()
	except:
		return time.time()


def GetBankProp(pBank):
	# The bank's EnergyWeaponProperty (cast unconfirmed: falls back to the raw
	# property object). Looked up fresh at every use, never kept.
	pRaw = pBank.GetProperty()
	if pRaw == None:
		return None
	try:
		pProp = App.EnergyWeaponProperty_Cast(pRaw)
		if pProp != None:
			return pProp
	except:
		pass
	return pRaw


def ForgetHeld(iID, eGroup=None, iIdx=None):
	# Drops hold records without touching any ship.
	for tKey in g_dHold2.keys():
		if (tKey[0] == iID) and ((eGroup == None) or (tKey[1] == eGroup)) and ((iIdx == None) or (tKey[2] == iIdx)):
			del g_dHold2[tKey]
			if g_dHold2Target.has_key(tKey):
				del g_dHold2Target[tKey]


def ReleaseHeld(iID, eGroup=None, pShip=None, iIdx=None):
	# Writes the recorded original MinFiringCharge back on the held banks of the
	# ship (one bank, one group or all), then SetForceUpdate(1) once per group so
	# the engine retries at once. pShip is looked up by ID when not given: a ship
	# that is gone just loses its records. A failed write keeps its record (it is
	# retried by the next release). Returns the number of banks restored.
	lKeys = []
	for tKey in g_dHold2.keys():
		if (tKey[0] == iID) and ((eGroup == None) or (tKey[1] == eGroup)) and ((iIdx == None) or (tKey[2] == iIdx)):
			lKeys.append(tKey)
	if len(lKeys) == 0:
		return 0
	if pShip == None:
		pShip = Lookup(iID)
	if pShip == None:
		ForgetHeld(iID, eGroup, iIdx)
		return 0
	fNow = Now()
	dSystems = {}
	dDone = {}
	iDone = 0
	for tKey in lKeys:
		try:
			if not dSystems.has_key(tKey[1]):
				dSystems[tKey[1]] = pShip.GetWeaponSystemGroup(tKey[1])
			pSystem = dSystems[tKey[1]]
			lBanks = []
			if pSystem != None:
				lBanks = GetWeapons(pSystem, "phaser")
			if tKey[2] >= len(lBanks):
				# The bank does not exist any more: nothing to write back.
				ForgetHeld(tKey[0], tKey[1], tKey[2])
			else:
				pProp = GetBankProp(lBanks[tKey[2]])
				if pProp == None:
					ForgetHeld(tKey[0], tKey[1], tKey[2])
				else:
					pProp.SetMinFiringCharge(g_dHold2[tKey])
					ForgetHeld(tKey[0], tKey[1], tKey[2])
					g_dHoldAt[tKey] = fNow
					dDone[tKey[1]] = pSystem
					iDone = iDone + 1
		except:
			DebugLog("Release hold error: " + str(sys.exc_info()[1]))
	for eKey in dDone.keys():
		try:
			dDone[eKey].SetForceUpdate(1)
		except:
			DebugLog("SetForceUpdate error: " + str(sys.exc_info()[1]))
	if (eGroup == None) and (iIdx == None):
		for tKey in g_dHoldAt.keys():
			if tKey[0] == iID:
				del g_dHoldAt[tKey]
	return iDone


def HoldBank2(pBank, tKey, iTarget, bFiring):
	# Holds one bank: StopFiring (only if it is firing), record the original
	# MinFiringCharge (first time only), raise it above the bank's max charge.
	# A failure after the record exists restores at once. Returns 1 when held.
	if bFiring:
		try:
			pBank.StopFiring()
		except:
			DebugLog("Hold2 StopFiring error: " + str(sys.exc_info()[1]))
			return 0
	try:
		pProp = GetBankProp(pBank)
		if pProp == None:
			return 0
		if not g_dHold2.has_key(tKey):
			g_dHold2[tKey] = pProp.GetMinFiringCharge()
			g_dHold2Target[tKey] = iTarget
		pProp.SetMinFiringCharge(pBank.GetMaxCharge() + 1.0)
		g_dHoldAt[tKey] = Now()
		return 1
	except:
		DebugLog("Hold2 error: " + str(sys.exc_info()[1]))
		if g_dHold2.has_key(tKey):
			ReleaseHeld(tKey[0], tKey[1], None, tKey[2])
		return 0


def HeldCount(iID=None, eGroup=None):
	iCount = 0
	for tKey in g_dHold2.keys():
		if ((iID == None) or (tKey[0] == iID)) and ((eGroup == None) or (tKey[1] == eGroup)):
			iCount = iCount + 1
	return iCount


def HoldSafetyCheck(iPlayer):
	# HoldSafety: a record whose ship is gone is forgotten; one whose ship is
	# not the player's ship (any more) is restored if the ship is live, then
	# forgotten.
	if not g_iHoldSafety:
		return
	try:
		dShips = {}
		for tKey in g_dHold2.keys():
			dShips[tKey[0]] = 1
		for iID in dShips.keys():
			if iID != iPlayer:
				ReleaseHeld(iID)
				ForgetHeld(iID)
			elif Lookup(iID) == None:
				ForgetHeld(iID)
	except:
		DebugLog("HoldSafety error: " + str(sys.exc_info()[1]))


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
	ReleaseHeld(iID, None, pShip)
	if not g_dLifted.has_key(iID):
		return 0
	dGroups = g_dLifted[iID]
	ForgetKept(iID)
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
		ReleaseHeld(iID, eGroup, pShip)
		if (not g_dLifted.has_key(iID)) or (not g_dLifted[iID].has_key(eGroup)):
			return 0
		iOrig = g_dLifted[iID][eGroup]
		ForgetKept(iID, eGroup)
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
		ForgetKept(iID)
		ForgetHeld(iID)
		return 0
	return RestoreSingleFire(pShip)


def ForgetAll():
	# Drops every record without touching any ship (used by Stop).
	global g_dLifted, g_dAdded, g_iShipID, g_dKept, g_dHeld, g_dPhaser
	global g_dHold2, g_dHold2Target, g_dHoldAt, g_dKeptAt
	StopFastTimer()
	g_dPhaser = {}
	g_dHold2 = {}
	g_dHold2Target = {}
	g_dHoldAt = {}
	g_dKeptAt = {}
	g_dLifted = {}
	g_dAdded = {}
	g_dKept = {}
	g_dHeld = {}
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


class FastTimer:
	# Second, faster timer (own process, same form as Timer). It only runs
	# LimitPerTarget, and only while a phaser group is lifted by the module.
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
			FastTick()
		except:
			if g_pCore != None:
				g_pCore.Log(NAME, "FastTick error: " + str(sys.exc_info()[1]))


def StartFastTimer():
	# A timer that marked itself dead (bActive 0) is released first, from here
	# (the slow Cycle), never from inside its own callback.
	global g_pFastTimer
	if (g_pFastTimer != None) and (not g_pFastTimer.bActive):
		StopFastTimer()
	if g_pFastTimer == None:
		g_pFastTimer = FastTimer(g_fLimitInterval)


def MarkFastDead():
	# The only stop allowed inside FastTick: just the flag. The process and
	# g_pFastTimer stay intact while the callback is still executing; the next
	# SyncFastTimer (another process) releases them.
	if g_pFastTimer != None:
		g_pFastTimer.bActive = 0


def StopFastTimer():
	global g_pFastTimer
	if g_pFastTimer != None:
		g_pFastTimer.bActive = 0
		g_pFastTimer.pProcess = None
	g_pFastTimer = None


def SyncFastTimer():
	# Runs at the end of every Cycle: the fast timer exists only while
	# PhaserPerTarget > 0, the ship is live and a phaser group is lifted.
	try:
		bWant = 0
		if (g_iPhaserPerTarget > 0) and (g_iHoldMode != 2):
			# HoldMode 2 needs no fast timer: the held bank stays mute.
			for tKey in g_dPhaser.keys():
				if g_dLifted.has_key(tKey[0]) and g_dLifted[tKey[0]].has_key(tKey[1]):
					bWant = 1
				else:
					del g_dPhaser[tKey]
		if bWant:
			pPlayer = GetPlayer()
			if (pPlayer == None) or pPlayer.IsDead() or pPlayer.IsDying():
				bWant = 0
		if bWant:
			StartFastTimer()
		else:
			StopFastTimer()
	except:
		StopFastTimer()
		DebugLog("SyncFastTimer error: " + str(sys.exc_info()[1]))


def FastTick():
	# Fast timer target: LimitPerTarget for the lifted phaser groups of the
	# player's ship, which is looked up fresh. Gone or dying ship: timer stops.
	pPlayer = GetPlayer()
	if (pPlayer == None) or pPlayer.IsDead() or pPlayer.IsDying():
		MarkFastDead()
		return
	iShip = pPlayer.GetObjID()
	iDone = 0
	for tKey in g_dPhaser.keys():
		if tKey[0] == iShip:
			iDone = iDone + 1
			try:
				pSystem = pPlayer.GetWeaponSystemGroup(tKey[1])
				if pSystem != None:
					LimitPerTarget(pPlayer, pSystem, None, tKey[1])
			except:
				DebugLog("FastTick group error: " + str(sys.exc_info()[1]))
	if iDone == 0:
		MarkFastDead()


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


def LimitPerTarget(pShip, pSystem, iMain, eGroup):
	# One phaser bank firing per target. Only while the module has this group's
	# single-fire lifted (never in vanilla single-fire mode). Banks that fire at
	# the same target: the one with the highest charge (a tie keeps the one kept
	# last cycle) stays, the others get Weapon.StopFiring() (SetFiring(0) left
	# the beam frozen in space). The engine refires a held bank about 0.25 s
	# later while its target is in the list, so the hold is renewed every
	# Cycle. Only indexes and IDs are kept. Returns the number of banks held this cycle.
	global g_dKept, g_dHeld
	if g_iPhaserPerTarget <= 0:
		if len(g_dHold2) > 0:
			try:
				ReleaseHeld(pShip.GetObjID(), eGroup, pShip)
			except:
				DebugLog("Per-target release error: " + str(sys.exc_info()[1]))
		return 0
	try:
		iShip = pShip.GetObjID()
		if (not g_dLifted.has_key(iShip)) or (not g_dLifted[iShip].has_key(eGroup)):
			ReleaseHeld(iShip, eGroup, pShip)
			ForgetKept(iShip, eGroup)
			return 0
		lBanks = GetWeapons(pSystem, "phaser")
		if g_iHoldMode == 2:
			iHeld = LimitHold2(pShip, pSystem, eGroup, iShip, lBanks)
			ReportHeld(iShip, eGroup, iHeld)
			return iHeld
		if len(g_dHold2) > 0:
			ReleaseHeld(iShip, eGroup, pShip)
		dByTarget = {}
		for iIdx in range(len(lBanks)):
			try:
				pBank = lBanks[iIdx]
				if pBank.IsFiring():
					iTarget = pBank.GetTargetID()
					fCharge = pBank.GetChargePercentage()
					if not dByTarget.has_key(iTarget):
						dByTarget[iTarget] = []
					dByTarget[iTarget].append((iIdx, fCharge))
			except:
				DebugLog("Per-target read error: " + str(sys.exc_info()[1]))
		iHeld = 0
		for iTarget in dByTarget.keys():
			lFiring = dByTarget[iTarget]
			if len(lFiring) >= 2:
				tKey = (iShip, eGroup, iTarget)
				tBest = lFiring[0]
				for tBank in lFiring:
					if tBank[1] > tBest[1]:
						tBest = tBank
				if g_dKept.has_key(tKey):
					for tBank in lFiring:
						if (tBank[0] == g_dKept[tKey]) and (tBank[1] >= tBest[1]):
							tBest = tBank
				g_dKept[tKey] = tBest[0]
				for tBank in lFiring:
					if tBank[0] != tBest[0]:
						try:
							lBanks[tBank[0]].StopFiring()
							iHeld = iHeld + 1
							if g_iHoldMode == 1:
								# EXPERIMENTAL: the beam is already ended, so the
								# disable should not freeze it. Never undone: the
								# engine re-enables the bank by itself (~2 s).
								try:
									lBanks[tBank[0]].SetFiring(0)
								except:
									DebugLog("Per-target SetFiring error: " + str(sys.exc_info()[1]))
						except:
							DebugLog("Per-target hold error: " + str(sys.exc_info()[1]))
		ReportHeld(iShip, eGroup, iHeld)
		return iHeld
	except:
		DebugLog("LimitPerTarget error: " + str(sys.exc_info()[1]))
		return 0


def ReportHeld(iShip, eGroup, iHeld):
	# Debug text when the number of held banks of a group changes.
	tGroup = (iShip, eGroup)
	iLast = 0
	if g_dHeld.has_key(tGroup):
		iLast = g_dHeld[tGroup]
	if iHeld != iLast:
		g_dHeld[tGroup] = iHeld
		if iHeld > 0:
			sText = "group " + str(eGroup) + " phaser: held " + str(iHeld) + " bank(s)"
			DebugPrint(sText)
			DebugBanner("Secondary target: " + sText)


def BankFree(tKey, fNow):
	# 1 when the bank's last hold/release is at least HoldHysteresis ago.
	if not g_dHoldAt.has_key(tKey):
		return 1
	return (fNow - g_dHoldAt[tKey]) >= g_fHoldHysteresis


def LimitHold2(pShip, pSystem, eGroup, iShip, lBanks):
	# HoldMode 2 of LimitPerTarget. Entries per target = the banks firing at it
	# plus the held banks that still want it (group firing, target live and in
	# the list). A target with 2+ entries keeps one bank (highest charge; the
	# kept one only changes after HoldHysteresis seconds and to a bank that is
	# itself free to change); the others are held. Every held bank not kept
	# up in this pass is released (forced, no hysteresis). Returns banks held.
	global g_dKept, g_dKeptAt
	fNow = Now()
	dByTarget = {}
	dSeen = {}
	for iIdx in range(len(lBanks)):
		try:
			pBank = lBanks[iIdx]
			if pBank.IsFiring():
				iTarget = pBank.GetTargetID()
				fCharge = pBank.GetChargePercentage()
				if not dByTarget.has_key(iTarget):
					dByTarget[iTarget] = []
				dByTarget[iTarget].append((iIdx, fCharge, 1))
				dSeen[iIdx] = 1
		except:
			DebugLog("Hold2 read error: " + str(sys.exc_info()[1]))
	bGroupFiring = 0
	try:
		bGroupFiring = pSystem.IsFiring()
	except:
		bGroupFiring = 0
	for tHeld in g_dHold2.keys():
		if (tHeld[0] == iShip) and (tHeld[1] == eGroup) and (not dSeen.has_key(tHeld[2])):
			try:
				iTarget = g_dHold2Target[tHeld]
				pTarget = Lookup(iTarget)
				if bGroupFiring and (pTarget != None) and (tHeld[2] < len(lBanks)):
					if (not pTarget.IsDead()) and pSystem.IsInTargetList(pTarget):
						if not dByTarget.has_key(iTarget):
							dByTarget[iTarget] = []
						dByTarget[iTarget].append((tHeld[2], lBanks[tHeld[2]].GetChargePercentage(), 0))
			except:
				DebugLog("Hold2 held read error: " + str(sys.exc_info()[1]))
	dStill = {}
	iHeld = 0
	for iTarget in dByTarget.keys():
		lEntries = dByTarget[iTarget]
		if len(lEntries) >= 2:
			try:
				tKey = (iShip, eGroup, iTarget)
				tBest = lEntries[0]
				tPrev = None
				for tEntry in lEntries:
					if tEntry[1] > tBest[1]:
						tBest = tEntry
					if g_dKept.has_key(tKey) and (tEntry[0] == g_dKept[tKey]):
						tPrev = tEntry
				tKeep = tBest
				if tPrev != None:
					tKeep = tPrev
					fSince = 0.0
					if g_dKeptAt.has_key(tKey):
						fSince = fNow - g_dKeptAt[tKey]
					if (tBest[1] > tPrev[1]) and (fSince >= g_fHoldHysteresis):
						tAlt = None
						for tEntry in lEntries:
							if BankFree((iShip, eGroup, tEntry[0]), fNow):
								if (tAlt == None) or (tEntry[1] > tAlt[1]):
									tAlt = tEntry
						if (tAlt != None) and (tAlt[1] > tPrev[1]):
							tKeep = tAlt
				if (not g_dKept.has_key(tKey)) or (g_dKept[tKey] != tKeep[0]) or (not g_dKeptAt.has_key(tKey)):
					g_dKept[tKey] = tKeep[0]
					g_dKeptAt[tKey] = fNow
				for tEntry in lEntries:
					tBank = (iShip, eGroup, tEntry[0])
					if tEntry[0] == tKeep[0]:
						if g_dHold2.has_key(tBank):
							ReleaseHeld(iShip, eGroup, pShip, tEntry[0])
					elif g_dHold2.has_key(tBank):
						dStill[tBank] = 1
						iHeld = iHeld + 1
						if tEntry[2] == 1:
							# The engine fired a held bank anyway: stop it again.
							HoldBank2(lBanks[tEntry[0]], tBank, iTarget, 1)
					elif BankFree(tBank, fNow):
						if HoldBank2(lBanks[tEntry[0]], tBank, iTarget, tEntry[2]):
							dStill[tBank] = 1
							iHeld = iHeld + 1
			except:
				DebugLog("Hold2 target error: " + str(sys.exc_info()[1]))
	for tHeld in g_dHold2.keys():
		if (tHeld[0] == iShip) and (tHeld[1] == eGroup) and (not dStill.has_key(tHeld)):
			ReleaseHeld(iShip, eGroup, pShip, tHeld[2])
	return iHeld


def MaintainGroup(pShip, pMain, eGroup, iMask):
	# One group, one cycle. Secondaries are only added to a group that is
	# firing with the player's selected target in its list; single-fire is
	# lifted only while there is at least one secondary to shoot at. Otherwise
	# the group's secondaries are removed and its single-fire is restored.
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
			RestoreGroup(pShip, eGroup)
			return
		lWanted = WantedTargets(pShip, pSystem, pMain, sKind)
		if (len(lWanted) == 0) and (len(lRecord) == 0):
			RestoreGroup(pShip, eGroup)
			return
		if len(lWanted) > 0:
			if (not g_dLifted.has_key(iShip)) or (not g_dLifted[iShip].has_key(eGroup)):
				LiftSingleFire(pShip, pSystem, eGroup)
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
		if len(lKeep) == 0:
			# The last secondary is gone: back to the original single-fire.
			RestoreGroup(pShip, eGroup)
		if sKind == "phaser":
			if g_dLifted.has_key(iShip) and g_dLifted[iShip].has_key(eGroup):
				g_dPhaser[tKey] = 1
			LimitPerTarget(pShip, pSystem, iMain, eGroup)
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
	# Gives the single-fire property back and forgets the added targets.
	ForgetAdded(iID)
	ReleaseHeld(iID)
	if g_dLifted.has_key(iID):
		ReleaseShipID(iID)


def StopGroups():
	# The player's ship changed: restore what was lifted on the old ship, only
	# if it is still live (ReleaseShipID looks it up by ID), and forget it.
	global g_iShipID
	if g_iShipID != None:
		ReleaseCurrent(g_iShipID)
	g_iShipID = None


def Cycle():
	# One cycle of the module (timer target): the work, then the fast timer
	# is started or stopped to match what is lifted.
	try:
		CycleBody()
	finally:
		SyncFastTimer()


def CycleBody():
	# design section 7.
	global g_iShipID
	pPlayer = GetPlayer()
	if pPlayer == None:
		return
	iID = pPlayer.GetObjID()
	if (g_iShipID != None) and (g_iShipID != iID):
		StopGroups()
	g_iShipID = iID
	HoldSafetyCheck(iID)
	iMask = GetMask(pPlayer)
	if iMask == 0:
		# No tech (any more): nothing is asked of the groups.
		ReleaseCurrent(iID)
		return
	if pPlayer.IsDead() or pPlayer.IsDying():
		# Held banks are written back while the ship still answers.
		ReleaseHeld(iID, None, pPlayer)
		return
	bOK = 1
	try:
		if pPlayer.IsCloaked():
			bOK = 0
		if pPlayer.GetAlertLevel() != App.ShipClass.RED_ALERT:
			bOK = 0
	except:
		bOK = 0
	if not bOK:
		ReleaseCurrent(iID)
		return
	pAF = GetAutoFire()
	if pAF == None:
		StopAllAdded(pPlayer)
		ReleaseCurrent(iID)
		return
	pMain = pAF.GetPlayerTarget(pPlayer)
	if (pMain == None) or (not pAF.IsEnemy(pMain)):
		# No usable main target: take the secondaries back, restore single-fire.
		StopAllAdded(pPlayer)
		ReleaseCurrent(iID)
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
	if not HasTech(GetPlayer()):
		return
	g_pMission = GetMission()
	if g_pMission != None:
		try:
			for tEntry in GetFireEvents():
				App.g_kEventManager.AddBroadcastPythonFuncHandler(tEntry[0], g_pMission, FIRE_HANDLER)
		except:
			pCore.Log(NAME, "Could not register handlers: " + str(sys.exc_info()[1]))
	StartTimer()


def Stop():
	# Called when the battle ends, while the game is destroying the ships:
	# nothing is asked of them. Only handlers and the timer are removed.
	global g_pMission
	StopTimer()
	StopFastTimer()
	ForgetAll()
	if g_pMission != None:
		try:
			for tEntry in GetFireEvents():
				App.g_kEventManager.RemoveBroadcastHandler(tEntry[0], g_pMission, FIRE_HANDLER)
		except:
			pass
	g_pMission = None


def Tick(lShips=None):
	# The core's cycle hook: not used, the module has its own timer.
	pass


def Diag():
	print ("  timer = " + str(g_pTimer != None) + ", fast = " + str(g_pFastTimer != None) + ", mission = " + str(g_pMission != None) + ", weapons = " + str(g_iWeapons) + ", hold mode = " + str(g_iHoldMode) + ", held banks = " + str(len(g_dHold2)))
