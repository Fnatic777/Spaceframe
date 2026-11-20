###############################################################################
#	SecondaryTarget.py
#
#	Spaceframe module, version 0.3
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
#	  (pulse and torpedo groups keep their own setting); the original values are
#	  restored when it goes OFF.
#	- Torpedoes under Auto Fire, and pulse weapons under Auto Fire with
#	  PulseRule 3, are handled by Auto Fire (this module only says which
#	  enemies may be secondaries: TorpedoCandidates, PulseCandidates).
#	- Phasers: secondaries are added here while the group fires at the main
#	  target; when no bank reaches the main target, Auto Fire starts the group
#	  at a secondary itself (PhaserCandidates).
#	- With the arc-percent rule (Auto Fire's PulseRule / TorpedoRule 3, pulse
#	  or torpedo), only secondaries a free weapon reaches inside the allowed
#	  arc percent are added; the main target is never restricted.
#	Settings: Modules\SecondaryTarget\Config.py
###############################################################################
import App
import sys

NAME = "SecondaryTarget"
VERSION = "0.3"
BUTTON_TEXT = "Secondary Target"

g_pCore = None
g_pTimer = None		# the module's own timer, only while switched on
g_pMission = None	# object the broadcast handlers were registered on
g_dLifted = {}		# ship ID -> {weapon group: original IsSingleFire}
g_dAdded = {}		# (ship ID, weapon group) -> IDs of the secondaries this module added
g_dStateAt = {}		# (ship ID, group) -> game time of the last Debug state line (float)
g_dEmptyShown = {}	# (ship ID, group) -> 1 once "fwd empty" was shown for this press
g_iShipID = None	# the player's ship the module last worked on
g_tLiftDone = None	# (ship ID, mask) LiftShip last handled; None = lift again
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
g_iDebug = 0	# Debug level: 0 off, 1 log, 2 log and banners
g_sCycleState = ""	# Debug = 1 only: the last outcome logged by Cycle
g_iWeapons = 7
g_fInterval = 0.2
g_iMaxCandidates = 4
g_fSecondaryRange = 100.0
g_fTorpedoRange = 30.0	# km as shown in game; 0 = no limit
g_iStartEnabled = 1
g_bArcLogged = 0	# 1 once an IsInArc failure was logged (no per-cycle spam)
g_lTrace = []		# Debug = 1 only: short state strings of the current fire (max 60)
g_fTraceLast = 0.0	# game time of the last TraceAdd
g_tTraceRep = None	# (text, "t=.." stamp, count) of the last trace line, for merging repeats
g_dKeyHeld = {}		# group -> 1/0, last fire event was a key down (kept always: the re-arm needs it)
g_dPressAt = {}		# group -> game time of the last fire key DOWN (float)
g_dRearmCnt = {}	# group -> re-arms done in the current press (int)
g_dPressTgt = {}	# group -> main target ID seen at the key down / first re-arm decision (int)
g_dFireAt = {}		# group -> game time of the last fire key event (down or up)
g_dGuardLogged = {}	# (group, reason) -> 1 once REARM-GUARD was logged in this press (Debug = 1)
g_dRearmAt = {}		# (ship ID, group) -> game time of the last torpedo re-arm (float)
g_dNoRearm = {}		# (ship ID, group) -> last NOREARM reason logged (Debug = 1 only)
g_tKeyLast = None	# Debug = 1 only: (event type, state, game time) of the last KEY trace line
g_dStateLast = {}	# (ship ID, group) -> (state text, game time it was appended)
g_fTraceT0 = 0.0	# game time of the first line of the current trace
g_dArcSkip = {}		# Debug = 1 only: (ship ID, kind) -> IDs the arc percent held back (logged on change)

BIT_PHASER = 1
BIT_TORPEDO = 2
BIT_PULSE = 4
BIT_ALL = 7

FIRE_HANDLER = "Custom.Spaceframe.Modules.SecondaryTarget.SecondaryTarget.OnFireKey"
FIRED_HANDLER = "Custom.Spaceframe.Modules.SecondaryTarget.SecondaryTarget.OnWeaponFired"
KEY_HANDLER = "Custom.Spaceframe.Modules.SecondaryTarget.SecondaryTarget.OnKeyboard"
BUTTON_HANDLER = "Custom.Spaceframe.Modules.SecondaryTarget.SecondaryTarget.OnMenuButton"


def GetConfig():
	import Custom.Spaceframe.Modules.SecondaryTarget.Config
	return Custom.Spaceframe.Modules.SecondaryTarget.Config


def LoadConfig():
	# Reads every setting once; edits apply from the next battle (Start).
	global g_bDebug, g_iDebug, g_iWeapons, g_fInterval, g_iMaxCandidates
	global g_fSecondaryRange, g_fTorpedoRange, g_iStartEnabled
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
	g_fTorpedoRange = float(getattr(pConfig, "SecondaryTorpedoRange", 30))
	if g_fTorpedoRange < 0.0:
		g_fTorpedoRange = 0.0
	g_iDebug = int(getattr(pConfig, "Debug", 0))
	if (g_iDebug < 2) and (g_pCore != None):
		try:
			iCore = int(g_pCore.GetConfigValue("Debug", 0))
			if iCore > g_iDebug:
				g_iDebug = iCore
		except:
			pass
	g_bDebug = 0
	if g_iDebug > 0:
		g_bDebug = 1


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
	global g_tLiftDone
	g_tLiftDone = None
	ClearAllHeld("cleared")
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
	global g_dLifted, g_dAdded, g_iShipID, g_tLiftDone, g_bArcLogged, g_dStateAt, g_dEmptyShown
	global g_lTrace, g_dStateLast, g_tTraceRep, g_dKeyHeld, g_dRearmAt, g_dNoRearm, g_tKeyLast
	global g_dPressAt, g_dRearmCnt, g_dPressTgt, g_dFireAt, g_dGuardLogged, g_dArcSkip
	g_dArcSkip = {}
	g_dPressAt = {}
	g_dRearmCnt = {}
	g_dPressTgt = {}
	g_dFireAt = {}
	g_dGuardLogged = {}
	g_dRearmAt = {}
	g_dNoRearm = {}
	g_tKeyLast = None
	g_lTrace = []
	g_tTraceRep = None
	g_dKeyHeld = {}
	g_dStateLast = {}
	g_tLiftDone = None
	g_bArcLogged = 0
	g_dLifted = {}
	g_dAdded = {}
	g_dStateAt = {}
	g_dEmptyShown = {}
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
	# The group's weapons of the kind ("phaser", "torpedo" tubes or "pulse"),
	# looked up fresh.
	lWeapons = []
	if (pSystem == None) or ((sKind != "phaser") and (sKind != "pulse") and (sKind != "torpedo")):
		return lWeapons
	try:
		for iChild in range(pSystem.GetNumChildSubsystems()):
			pChild = pSystem.GetChildSubsystem(iChild)
			if sKind == "phaser":
				pWeapon = App.PhaserBank_Cast(pChild)
			elif sKind == "torpedo":
				pWeapon = App.TorpedoTube_Cast(pChild)
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
	# percent of the banks' maximum damage distance (0 = no limit). Torpedoes: within
	# SecondaryTorpedoRange km (0 = no limit). Pulse: no range filter.
	lResult = []
	pAF = GetAutoFire()
	if (pAF == None) or (pShip == None):
		return lResult
	try:
		fLimit = 0.0
		bLimit = 0
		if sKind == "phaser":
			if g_fSecondaryRange > 0.0:
				bLimit = 1
				for pBank in GetWeapons(pSystem, "phaser"):
					fMax = pBank.GetMaxDamageDistance()
					if fMax > fLimit:
						fLimit = fMax
				fLimit = fLimit * g_fSecondaryRange / 100.0
				if fLimit <= 0.0:
					return lResult
		elif sKind == "torpedo":
			if g_fTorpedoRange > 0.0:
				bLimit = 1
				fLimit = pAF.KilometersToUnits(g_fTorpedoRange)
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
			if (not bLimit) or (pAF.GetDistance(pShip, pEnemy) <= fLimit):
				lResult.append(pEnemy)
	except:
		DebugLog("GetCandidates error: " + str(sys.exc_info()[1]))
		return []
	return lResult


def KindCandidates(pShip, pSystem, pMain, iBit, sKind):
	# IDs of the enemies that may be secondaries of this kind now, nearest
	# first. [] unless the module is ON, the ship is the player's and has the
	# kind's bit, and the main target is an enemy. Writes no state.
	try:
		if (not g_iOn) or (pShip == None) or (pSystem == None) or (pMain == None):
			return []
		pPlayer = GetPlayer()
		if (pPlayer == None) or (pPlayer.GetObjID() != pShip.GetObjID()):
			return []
		if (GetMask(pShip) & iBit) == 0:
			return []
		pAF = GetAutoFire()
		if (pAF == None) or (not pAF.IsEnemy(pMain)):
			return []
		lIDs = []
		for pEnemy in GetCandidates(pShip, pMain, pSystem, sKind):
			lIDs.append(pEnemy.GetObjID())
		return lIDs
	except:
		DebugLog(sKind + " candidates error: " + str(sys.exc_info()[1]))
		return []


def TorpedoCandidates(pShip, pSystem, pMain):
	# Public, used by Auto Fire: IDs of the enemies that may be torpedo
	# secondaries now (SecondaryTorpedoRange, MaxCandidates).
	return KindCandidates(pShip, pSystem, pMain, BIT_TORPEDO, "torpedo")


def PulseCandidates(pShip, pSystem, pMain):
	# Public, used by Auto Fire (PulseRule 3): IDs of the enemies that may be
	# pulse secondaries now (MaxCandidates, no range limit).
	return KindCandidates(pShip, pSystem, pMain, BIT_PULSE, "pulse")


def PhaserCandidates(pShip, pSystem, pMain):
	# Public, used by Auto Fire (SecondaryPhasers): IDs of the enemies that may
	# be phaser secondaries now (SecondaryRange % of the banks' full-damage
	# range, MaxCandidates), nearest first.
	return KindCandidates(pShip, pSystem, pMain, BIT_PHASER, "phaser")


def AutoFireOwns(eGroup, sKind="torpedo"):
	# 1 while Auto Fire builds the secondaries of this group itself.
	try:
		pAF = GetAutoFire()
		if pAF == None:
			return 0
		if sKind == "pulse":
			if hasattr(pAF, "ManagesPulseSecondaries") and pAF.ManagesPulseSecondaries(eGroup):
				return 1
		elif hasattr(pAF, "ManagesTorpedoSecondaries"):
			if pAF.ManagesTorpedoSecondaries(eGroup):
				return 1
	except:
		pass
	return 0


def ArcRule(sKind):
	# 1 when Auto Fire's arc-percent rule is selected for this kind (PulseRule /
	# TorpedoRule 3): then only secondaries a free weapon reaches inside the
	# allowed percent are added. 0 if Auto Fire is old or errors (today's way).
	try:
		pAF = GetAutoFire()
		if (pAF != None) and hasattr(pAF, "ArcRuleOn") and hasattr(pAF, "ArcReaches"):
			if pAF.ArcRuleOn(sKind):
				return 1
	except:
		pass
	return 0


def SecReach(pShip, pSystem, pWeapon, pCandidate, sKind):
	# 1 when the free weapon reaches the candidate by the engine's arc AND
	# inside the allowed arc percent (manual fire never restricts the main).
	try:
		if not Reaches(pWeapon, pCandidate.GetWorldLocation(), sKind, 0):
			return 0
		if GetAutoFire().ArcReaches(pShip, pSystem, pWeapon, pCandidate, sKind):
			return 1
	except:
		pass
	return 0


def FreeWeapons(pSystem, pMain, sKind):
	# Weapons that do not reach the main target (phaser: CanHit on its world
	# point is false; torpedo tube and, with the arc-percent rule, pulse weapon:
	# IsInArc on it is false, a failing call counts as NOT free). Pulse weapons
	# are all free without the arc-percent rule. No main target: nothing.
	lFree = []
	if pMain == None:
		return lFree
	lWeapons = GetWeapons(pSystem, sKind)
	if (sKind == "pulse") and (not ArcRule("pulse")):
		return lWeapons
	try:
		pPoint = pMain.GetWorldLocation()
	except:
		DebugLog("FreeWeapons error: " + str(sys.exc_info()[1]))
		return lFree
	for pWeapon in lWeapons:
		if not Reaches(pWeapon, pPoint, sKind, 1):
			lFree.append(pWeapon)
	return lFree


def Reaches(pWeapon, pPoint, sKind, iOnError):
	# 1 when the weapon can hit the world point: phaser CanHit, torpedo tube
	# IsInArc (the fixed +-30 degree cone). iOnError is the answer when the
	# engine call fails (logged once for tubes).
	global g_bArcLogged
	try:
		if (sKind == "torpedo") or (sKind == "pulse"):
			return pWeapon.IsInArc(pPoint)
		return pWeapon.CanHit(pPoint)
	except:
		if (sKind == "phaser") or (not g_bArcLogged):
			DebugLog("Reach error (" + sKind + "): " + str(sys.exc_info()[1]))
		if sKind != "phaser":
			g_bArcLogged = 1
		return iOnError


def WantedTargets(pShip, pSystem, pMain, sKind):
	# Object IDs of the candidates that at least one free weapon can reach. With
	# the arc-percent rule (pulse or torpedo) the weapon must also have the
	# candidate inside the allowed percent (SecReach).
	global g_dArcSkip
	lWanted = []
	try:
		lFree = FreeWeapons(pSystem, pMain, sKind)
		if len(lFree) == 0:
			return lWanted
		bArc = 0
		if (sKind == "pulse") or (sKind == "torpedo"):
			bArc = ArcRule(sKind)
		lSkipped = []
		for pCandidate in GetCandidates(pShip, pMain, pSystem, sKind):
			bReach = 0
			if (sKind == "pulse") and (not bArc):
				bReach = 1
			else:
				pPoint = pCandidate.GetWorldLocation()
				bSeen = 0
				for pWeapon in lFree:
					if bArc:
						if Reaches(pWeapon, pPoint, sKind, 0):
							bSeen = 1
						if SecReach(pShip, pSystem, pWeapon, pCandidate, sKind):
							bReach = 1
							break
					elif Reaches(pWeapon, pPoint, sKind, 0):
						bReach = 1
						break
				if bSeen and (not bReach):
					lSkipped.append(pCandidate.GetObjID())
			if bReach:
				lWanted.append(pCandidate.GetObjID())
		if g_bDebug and bArc:
			tKey = (pShip.GetObjID(), sKind)
			if g_dArcSkip.get(tKey) != lSkipped:
				g_dArcSkip[tKey] = lSkipped
				sSkip = IDText(lSkipped)
				if sSkip == "":
					sSkip = "none"
				TraceAdd("ARC-SKIP " + sKind + " " + sSkip)
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


def DebugBanner(sText, fY=0.2, fDur=4.0):
	# Debug = 2 only: a short line on screen (the console is not enough).
	if g_iDebug < 2:
		return
	try:
		import MissionLib
		MissionLib.TextBanner(None, App.TGString(sText), 0.0, fY, fDur, 12, 1, 0)
	except:
		DebugLog("TextBanner error: " + str(sys.exc_info()[1]))


def TraceAdd(sText):
	# Debug = 1 only: appends "t=<elapsed> <text>" to the trace (max 60 lines).
	# A line identical to the previous one is merged: "t=<first> <text> x<n>".
	global g_lTrace, g_fTraceT0, g_fTraceLast, g_tTraceRep
	if not g_bDebug:
		return
	DebugLog(sText)		# to the log file as it happens (ShowTrace does not log)
	try:
		fNow = Now()
		if len(g_lTrace) == 0:
			g_fTraceT0 = fNow
			g_tTraceRep = None
		g_fTraceLast = fNow
		if (g_tTraceRep != None) and (g_tTraceRep[0] == sText) and (len(g_lTrace) > 0):
			iCount = g_tTraceRep[2] + 1
			g_tTraceRep = (sText, g_tTraceRep[1], iCount)
			g_lTrace[-1] = g_tTraceRep[1] + " " + sText + " x" + str(iCount)
			return
		sStamp = "t=" + ("%.1f" % (fNow - g_fTraceT0))
		g_tTraceRep = (sText, sStamp, 1)
		g_lTrace.append(sStamp + " " + sText)
		while len(g_lTrace) > 60:
			del g_lTrace[0]
	except:
		DebugLog("TraceAdd error: " + str(sys.exc_info()[1]))


def KeyHeld(eGroup):
	if g_dKeyHeld.has_key(eGroup):
		return g_dKeyHeld[eGroup]
	return 0


# Re-arm safeguards: the re-arm fires by itself while the module believes the
# key is down, so a lost key-up must not leave it armed for ever.
# A launch needs about 0.6 s per torpedo (0.5 s engine gap + the re-arm cadence):
# 14 tubes of a Galaxy take about 9 s, so the limits leave room for a full
# volley of a big ship and still bound a key whose release event was lost.
REARM_MAX = 20		# re-arms per key press
REARM_MAX_TIME = 20.0	# seconds of game time per key press
REARM_STALE = 25.0	# seconds without any fire key event


def GuardLog(eGroup, sWhy):
	# Debug = 1 only: one line per (group, reason) per press.
	global g_dGuardLogged
	tKey = (eGroup, sWhy)
	if g_dGuardLogged.has_key(tKey):
		return
	g_dGuardLogged[tKey] = 1
	DebugLog("REARM-GUARD g" + str(eGroup) + " " + sWhy)


def ForgetPress(eGroup):
	# Drops the per-press numbers of one group (the guard log marks stay).
	for dTable in (g_dPressAt, g_dRearmCnt, g_dPressTgt, g_dFireAt):
		if dTable.has_key(eGroup):
			del dTable[eGroup]


def ClearHeld(eGroup, sWhy):
	# The group is no longer considered held: no re-arm until a new key down.
	if KeyHeld(eGroup):
		GuardLog(eGroup, sWhy)
	if g_dKeyHeld.has_key(eGroup):
		del g_dKeyHeld[eGroup]
	ForgetPress(eGroup)


def ClearAllHeld(sWhy):
	for eGroup in g_dKeyHeld.keys():
		ClearHeld(eGroup, sWhy)


def MainID():
	# ID of the player's main target now, or None (looked up fresh).
	try:
		pAF = GetAutoFire()
		pMain = pAF.GetPlayerTarget(GetPlayer())
		if pMain == None:
			return None
		return pMain.GetObjID()
	except:
		return None


def ShowTrace():
	# Debug = 1 only: the last 15 trace lines stacked on screen (one banner per
	# line), every line to the log. The list is cleared BEFORE displaying, so
	# a trace is never shown twice.
	global g_lTrace
	if not g_bDebug:
		return
	lTrace = g_lTrace
	g_lTrace = []
	if len(lTrace) == 0:
		return
	try:
		lTail = lTrace[-15:]
		for i in range(len(lTail)):
			DebugBanner(lTail[i], 0.03 + 0.03 * i, 15.0)
	except:
		DebugLog("ShowTrace error: " + str(sys.exc_info()[1]))


def TraceIdleCheck():
	# Debug = 1 only: shows the trace once no line was added for 3.0 s (longer than the 2.0 s state refresh).
	if (not g_bDebug) or (len(g_lTrace) == 0):
		return
	try:
		if (Now() - g_fTraceLast) >= 3.0:
			ShowTrace()
	except:
		DebugLog("TraceIdleCheck error: " + str(sys.exc_info()[1]))


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
	if sKind == "torpedo":
		return BIT_TORPEDO
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
	for tKey in g_dEmptyShown.keys():
		if (tKey[0] == iID) and ((eGroup == None) or (tKey[1] == eGroup)):
			del g_dEmptyShown[tKey]
	for tKey in g_dStateLast.keys():
		if (tKey[0] == iID) and ((eGroup == None) or (tKey[1] == eGroup)):
			del g_dStateLast[tKey]
	if eGroup == None:
		# Ship-wide release only: the per-group calls of MaintainGroup must keep
		# the re-arm throttle and the NOREARM transition state.
		for tKey in g_dRearmAt.keys():
			if tKey[0] == iID:
				del g_dRearmAt[tKey]
		for tKey in g_dNoRearm.keys():
			if tKey[0] == iID:
				del g_dNoRearm[tKey]


def Now():
	# Game time in seconds (0.0 when unavailable).
	try:
		return App.g_kUtopiaModule.GetGameTime()
	except:
		return 0.0


def StateReport(pSystem, pMain, sKind, tKey, lKeep):
	# Debug = 1 only: at most one state line per 0.5 s per group, plus one
	# "fwd empty" line per press (torpedo groups). Every engine call guarded.
	global g_dStateAt, g_dEmptyShown, g_dStateLast
	if not g_bDebug:
		return
	try:
		fNow = Now()
		bShow = 1
		if g_dStateAt.has_key(tKey):
			if (fNow - g_dStateAt[tKey]) < 0.5:
				bShow = 0
		bEmpty = 0
		iFreeRdy = 0
		sTail = ""
		if sKind == "torpedo":
			iFwdRdy = 0
			iFwd = 0
			iFlags = 0
			pPoint = pMain.GetWorldLocation()
			for pTube in GetWeapons(pSystem, sKind):
				try:
					if Reaches(pTube, pPoint, sKind, 1):
						iFwd = iFwd + 1
						iFwdRdy = iFwdRdy + pTube.GetNumReady()
					else:
						iFreeRdy = iFreeRdy + pTube.GetNumReady()
				except:
					DebugLog("State tube error: " + str(sys.exc_info()[1]))
				try:
					if pTube.IsFiring():
						iFlags = iFlags + 1
				except:
					pass
			sTail = " fwd=" + str(iFwdRdy) + " free=" + str(iFreeRdy) + " ff=" + str(iFlags)
			if (iFwd > 0) and (iFwdRdy == 0):
				bEmpty = 1
		if bShow:
			g_dStateAt[tKey] = fNow
			sMain = "out"
			if pSystem.IsInTargetList(pMain):
				sMain = "in"
			sSec = "out"
			pSec = Lookup(lKeep[0])
			if (pSec != None) and pSystem.IsInTargetList(pSec):
				sSec = "in"
			sText = {"torpedo": "T", "phaser": "P", "pulse": "U"}.get(sKind, "?") + str(tKey[1]) + " f" + str(pSystem.IsFiring())
			sText = sText + " M:" + sMain + " S:" + sSec + sTail
			# steady state is compressed: same text within 2.0 s is not added
			bAdd = 1
			if g_dStateLast.has_key(tKey):
				if (g_dStateLast[tKey][0] == sText) and ((fNow - g_dStateLast[tKey][1]) < 2.0):
					bAdd = 0
			if bAdd:
				g_dStateLast[tKey] = (sText, fNow)
				TraceAdd(sText)
		if bEmpty and (not g_dEmptyShown.has_key(tKey)):
			g_dEmptyShown[tKey] = 1
			TraceAdd("FWD EMPTY free rdy=" + str(iFreeRdy) + " key=" + str(KeyHeld(tKey[1])))
	except:
		DebugLog("StateReport error: " + str(sys.exc_info()[1]))


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


def NoRearm(tKey, sWhy, bHeld, lRecord):
	# Debug = 1 only: one "NOREARM g<group> why=<reason>" line per change of
	# reason (only while the key is held or the group just stopped with our record).
	global g_dNoRearm
	if (not g_bDebug) or ((not bHeld) and (len(lRecord) == 0)):
		return
	if g_dNoRearm.has_key(tKey) and (g_dNoRearm[tKey] == sWhy):
		return
	g_dNoRearm[tKey] = sWhy
	TraceAdd("NOREARM g" + str(tKey[1]) + " why=" + sWhy)


def RearmReason(pShip, pSystem, pMain, eGroup, tKey):
	# "" when a torpedo group should be re-armed, else the reason it should not
	# (nokey, nofree, fwdready, nosec, throttle). Also returns the free ready count.
	# Rule: manual fire completes only the free weapons. The engine's own fire
	# loop alternates tubes by itself while main-reaching tubes still have
	# torpedoes (main keeps priority); only when they are all empty and the key
	# is still down does the system stop firing and never restart, so the
	# free tubes that reach a wanted secondary must be started again.
	if not KeyHeld(eGroup):
		return ("nokey", 0)
	fNow = Now()
	if g_dFireAt.has_key(eGroup) and ((fNow - g_dFireAt[eGroup]) > REARM_STALE):
		ClearHeld(eGroup, "stale")
		return ("stale", 0)
	iMainID = pMain.GetObjID()
	if g_dPressTgt.has_key(eGroup):
		if g_dPressTgt[eGroup] != iMainID:
			ClearHeld(eGroup, "target")
			return ("target", 0)
	else:
		g_dPressTgt[eGroup] = iMainID
	bCap = 0
	if g_dRearmCnt.has_key(eGroup) and (g_dRearmCnt[eGroup] >= REARM_MAX):
		bCap = 1
	if g_dPressAt.has_key(eGroup) and ((fNow - g_dPressAt[eGroup]) > REARM_MAX_TIME):
		bCap = 1
	if bCap:
		GuardLog(eGroup, "cap")
		return ("cap", 0)
	pPoint = pMain.GetWorldLocation()
	iFwdRdy = 0
	iFreeRdy = 0
	lFreeTubes = []
	for pTube in GetWeapons(pSystem, "torpedo"):
		iRdy = 0
		try:
			iRdy = pTube.GetNumReady()
		except:
			DebugLog("Rearm ready error: " + str(sys.exc_info()[1]))
		if Reaches(pTube, pPoint, "torpedo", 1):
			iFwdRdy = iFwdRdy + iRdy
		else:
			iFreeRdy = iFreeRdy + iRdy
			if iRdy > 0:
				lFreeTubes.append(pTube)
	if iFreeRdy == 0:
		return ("nofree", 0)
	if iFwdRdy > 0:
		return ("fwdready", iFreeRdy)
	bSec = 0
	bArc = ArcRule("torpedo")
	for iID in WantedTargets(pShip, pSystem, pMain, "torpedo"):
		pSec = Lookup(iID)
		if (pSec != None) and (not bSec):
			pSecPoint = pSec.GetWorldLocation()
			for pTube in lFreeTubes:
				if Reaches(pTube, pSecPoint, "torpedo", 0) and ((not bArc) or SecReach(pShip, pSystem, pTube, pSec, "torpedo")):
					bSec = 1
					break
	if not bSec:
		return ("nosec", iFreeRdy)
	if g_dRearmAt.has_key(tKey) and ((Now() - g_dRearmAt[tKey]) < 0.5):
		return ("throttle", iFreeRdy)
	return ("", iFreeRdy)


def TryRearm(pShip, pSystem, pMain, eGroup, sKind, tKey, lRecord):
	# Torpedo groups only (phaser and pulse groups keep firing by themselves).
	# Called when the group is NOT firing; re-arms it when the key is still held.
	# Returns 1 when the group was started again at the main target.
	global g_dRearmAt, g_dNoRearm, g_dRearmCnt
	if sKind != "torpedo":
		return 0
	try:
		tWhy = RearmReason(pShip, pSystem, pMain, eGroup, tKey)
	except:
		DebugLog("Rearm check error: " + str(sys.exc_info()[1]))
		return 0
	if tWhy[0] != "":
		NoRearm(tKey, tWhy[0], KeyHeld(eGroup), lRecord)
		return 0
	g_dRearmAt[tKey] = Now()
	if g_dRearmCnt.has_key(eGroup):
		g_dRearmCnt[eGroup] = g_dRearmCnt[eGroup] + 1
	else:
		g_dRearmCnt[eGroup] = 1
	if g_dNoRearm.has_key(tKey):
		del g_dNoRearm[tKey]
	pOffset = None
	try:
		pOffset = pShip.GetTargetOffsetTG()
	except:
		pOffset = None
	if pOffset == None:
		pOffset = ZeroPoint()
	# Same two calls as the game's own fire handler: StartFiring, SetForceUpdate.
	pSystem.StartFiring(pMain, pOffset)
	try:
		pSystem.SetForceUpdate(1)
	except:
		DebugLog("Rearm SetForceUpdate error: " + str(sys.exc_info()[1]))
	TraceAdd("REARM g" + str(eGroup) + " key=1 free rdy=" + str(tWhy[1]))
	return 1


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
		if ((sKind == "torpedo") or (sKind == "pulse")) and AutoFireOwns(eGroup, sKind):
			# Auto Fire builds this group's list on every press (see AutoFire PlanGroup).
			ForgetAdded(iShip, eGroup)
			return
		lRecord = []
		if g_dAdded.has_key(tKey):
			lRecord = g_dAdded[tKey]
		if (not pSystem.IsFiring()) or (not pSystem.IsInTargetList(pMain)):
			# Not our case (the key release normally emptied the list already).
			StopAdded(pSystem, lRecord, iMain)
			ForgetAdded(iShip, eGroup)
			if g_bDebug and (len(lRecord) > 0):
				TraceAdd("STOP g" + str(eGroup) + " key=" + str(KeyHeld(eGroup)))
			# Key still held on a torpedo group: maybe start it again.
			if not TryRearm(pShip, pSystem, pMain, eGroup, sKind, tKey, lRecord):
				return
			lRecord = []
		elif g_dNoRearm.has_key(tKey):
			del g_dNoRearm[tKey]
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
		if g_bDebug and (len(lKeep) > 0):
			StateReport(pSystem, pMain, sKind, tKey, lKeep)
		if g_bDebug:
			for iID in lAdded:
				TraceAdd("ADD " + str(iID))
			for iID in lRemoved:
				TraceAdd("DEL " + str(iID))
		if (len(lAdded) > 0) or (len(lRemoved) > 0):
			sText = "group " + str(eGroup) + " (" + sKind + ")"
			if len(lAdded) > 0:
				sText = sText + " +" + IDText(lAdded)
			if len(lRemoved) > 0:
				sText = sText + " -" + IDText(lRemoved)
			DebugPrint(sText)
	except:
		DebugLog("Group " + str(eGroup) + " error: " + str(sys.exc_info()[1]))


def ReleaseCurrent(iID):
	# Takes the secondaries back and gives the single-fire property back, both
	# only if the ship is found live by ID (a gone ship is just forgotten).
	global g_tLiftDone
	g_tLiftDone = None
	ClearAllHeld("cleared")
	pShip = Lookup(iID)
	if pShip != None:
		StopAllAdded(pShip)
	ForgetAdded(iID)
	if g_dLifted.has_key(iID):
		ReleaseShipID(iID)


def StopGroups():
	# The player's ship changed: release the old ship (only if it is still
	# live, looked up by ID) and forget it.
	global g_iShipID, g_tLiftDone
	ClearAllHeld("cleared")
	if g_iShipID != None:
		ReleaseCurrent(g_iShipID)
	g_iShipID = None
	g_tLiftDone = None


def LiftShip(pShip, iMask):
	# Lifts single-fire on every PHASER group in the mask that is not lifted
	# yet. Pulse weapons keep their own single-fire setting (a Defiant fires
	# its four cannons together; a single-fire pulse stays single) and
	# torpedo groups keep their own setting too. Groups whose kind left the mask, or that are
	# not phasers, are given back. The original value is recorded before the
	# first change. The (ship ID, mask) pair is remembered even when a group
	# failed (logged once), so Cycle does not retry every tick.
	global g_tLiftDone
	for tEntry in GetFireEvents():
		try:
			pSystem = pShip.GetWeaponSystemGroup(tEntry[1])
			if pSystem != None:
				iShip = pShip.GetObjID()
				sKind = GroupKind(pSystem)
				if (sKind != "phaser") or ((KindBit(sKind) & iMask) == 0):
					RestoreGroup(pShip, tEntry[1])
				elif (not g_dLifted.has_key(iShip)) or (not g_dLifted[iShip].has_key(tEntry[1])):
					if not LiftSingleFire(pShip, pSystem, tEntry[1]):
						DebugLog("LiftShip: group " + str(tEntry[1]) + " not lifted")
		except:
			DebugLog("LiftShip error: " + str(sys.exc_info()[1]))
	try:
		g_tLiftDone = (pShip.GetObjID(), iMask)
	except:
		g_tLiftDone = None


def DropSecondaries(pShip):
	# Removes the secondaries this module added (the ship stays lifted).
	StopAllAdded(pShip)
	try:
		ForgetAdded(pShip.GetObjID())
	except:
		pass


def CycleNote(sState):
	# Debug = 1 only: logs the cycle's outcome only when it differs from the
	# previous cycle's (idle cycles stay silent).
	global g_sCycleState
	if (not g_bDebug) or (sState == g_sCycleState):
		return
	g_sCycleState = sState
	DebugLog("Cycle: " + sState)


def Cycle():
	# One cycle of the module (timer target, only while switched ON).
	global g_iShipID
	if not g_iOn:
		return
	TraceIdleCheck()
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
		CycleNote("no tech on ship " + str(iID))
		ReleaseCurrent(iID)
		return
	if pPlayer.IsDead() or pPlayer.IsDying():
		CycleNote("player dead")
		ReleaseCurrent(iID)
		return
	if g_tLiftDone != (iID, iMask):
		CycleNote("ship " + str(iID) + " mask " + str(iMask) + ", lifting single-fire")
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
		CycleNote("not red alert or cloaked")
		ClearAllHeld("cleared")
		DropSecondaries(pPlayer)
		return
	pAF = GetAutoFire()
	if pAF == None:
		CycleNote("AutoFire not available")
		ClearAllHeld("cleared")
		DropSecondaries(pPlayer)
		return
	pMain = pAF.GetPlayerTarget(pPlayer)
	if (pMain == None) or (not pAF.IsEnemy(pMain)):
		# No usable main target: take the secondaries back (single-fire stays
		# lifted while the module is ON).
		CycleNote("no usable main target")
		ClearAllHeld("cleared")
		DropSecondaries(pPlayer)
		return
	CycleNote("main target ok")
	for tEntry in GetFireEvents():
		MaintainGroup(pPlayer, pMain, tEntry[1], iMask)


def OnFireKey(pObject, pEvent):
	# Fire-key handler. The key is not applied yet when this runs, so the
	# list is NOT touched here (starting the group would be wrong): the next
	# Cycle re-adds the secondaries once the group fires. A release empties
	# the game's list, so the record of added targets is forgotten.
	global g_tKeyLast
	try:
		eType = pEvent.GetEventType()
		for tEntry in GetFireEvents():
			if tEntry[0] == eType:
				# The key state is kept always (torpedo re-arm needs it).
				iDown = 0
				if pEvent.GetBool():
					iDown = 1
				iWasDown = 0
				if g_dKeyHeld.has_key(tEntry[1]):
					iWasDown = g_dKeyHeld[tEntry[1]]
				g_dKeyHeld[tEntry[1]] = iDown
				if (iDown and (not iWasDown)) or (not iDown):
					ForgetPress(tEntry[1])
				g_dFireAt[tEntry[1]] = Now()
				if iDown and (not iWasDown):
					# New press (not a repeat of a key that is already down): counters
					# restart, the main target is remembered.
					g_dPressAt[tEntry[1]] = Now()
					g_dRearmCnt[tEntry[1]] = 0
					iMainID = MainID()
					if iMainID != None:
						g_dPressTgt[tEntry[1]] = iMainID
					for tMark in g_dGuardLogged.keys():
						if tMark[0] == tEntry[1]:
							del g_dGuardLogged[tMark]
				if g_bDebug:
					# The game calls this handler several times per key event:
					# the same (type, state) in the same game instant is traced once.
					fNow = Now()
					if (g_tKeyLast == None) or (g_tKeyLast != (eType, iDown, fNow)):
						g_tKeyLast = (eType, iDown, fNow)
						if iDown:
							TraceAdd("KEY dn g" + str(tEntry[1]))
						else:
							TraceAdd("KEY up g" + str(tEntry[1]))
				if not iDown:
					for tKey in g_dNoRearm.keys():
						if tKey[1] == tEntry[1]:
							del g_dNoRearm[tKey]
					if g_iShipID != None:
						ForgetAdded(g_iShipID, tEntry[1])
	except:
		DebugLog("OnFireKey error: " + str(sys.exc_info()[1]))
	try:
		pObject.CallNextHandler(pEvent)
	except:
		pass


def OnWeaponFired(pObject, pEvent):
	# Debug = 1 only: logs which of the player's weapons launched and at which
	# target ID, so the log shows what a re-arm really produced. Does nothing
	# otherwise; always passes the event on.
	if g_bDebug:
		try:
			pWeapon = App.Weapon_Cast(pEvent.GetSource())
			if pWeapon != None:
				bMine = 1
				try:
					pParent = pWeapon.GetParentShip()
					pPlayer = GetPlayer()
					if (pParent != None) and (pPlayer != None) and (pParent.GetObjID() != pPlayer.GetObjID()):
						bMine = 0
				except:
					bMine = 1	# GetParentShip unconfirmed: log anyway
				if bMine:
					DebugLog("FIRED " + str(pWeapon.GetName()) + " tgt=" + str(pWeapon.GetTargetID()) + " t=" + ("%.2f" % Now()))
		except:
			DebugLog("OnWeaponFired error: " + str(sys.exc_info()[1]))
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
	ClearAllHeld("cleared")
	StopGroups()


def SetEnabled(iOn):
	pPlayer = GetPlayer()
	if iOn:
		if HasTech(pPlayer):
			TurnOn(pPlayer)
	else:
		ShowTrace()
		TurnOff()
	UpdateButton()
	if g_pCore != None:
		g_pCore.Log(NAME, "Secondary Target " + str(IsEnabled()))


def Toggle():
	SetEnabled(not IsEnabled())
	# Player feedback (key and menu button only, not the battle start).
	sState = "OFF"
	if IsEnabled():
		sState = "ON"
	try:
		if g_pCore != None:
			g_pCore.ShowNotice("Secondary Target " + sState, 0.16, 2.5)
	except:
		pass


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
	global g_pCore, g_pMission, g_pAutoFire, g_bAutoFireFailed, g_sCycleState
	Stop()
	g_pCore = pCore
	g_pAutoFire = None
	g_bAutoFireFailed = 0
	g_sCycleState = ""
	import Custom.Spaceframe.Modules.SecondaryTarget.Config
	reload(Custom.Spaceframe.Modules.SecondaryTarget.Config)
	LoadConfig()
	if g_bDebug:
		DebugLog("Secondary Target started: Weapons(mask)=" + str(g_iWeapons) + " Interval=" + str(g_fInterval) + " MaxCandidates=" + str(g_iMaxCandidates) + " SecondaryRange=" + str(g_fSecondaryRange) + " SecondaryTorpedoRange=" + str(g_fTorpedoRange) + " StartEnabled(toggle)=" + str(g_iStartEnabled))
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
			App.g_kEventManager.AddBroadcastPythonFuncHandler(App.ET_WEAPON_FIRED, g_pMission, FIRED_HANDLER)
		except:
			pCore.Log(NAME, "Could not register the fired handler: " + str(sys.exc_info()[1]))
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
		try:
			App.g_kEventManager.RemoveBroadcastHandler(App.ET_WEAPON_FIRED, g_pMission, FIRED_HANDLER)
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
