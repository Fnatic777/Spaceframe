###############################################################################
#	Ablative Armor
#	Spaceframe module, version 1.5
#
#	Gives a ship a layer of ablative armor. Once damage gets past the
#	shields, the armor absorbs it before it reaches the hull or any
#	subsystem: whatever the ship loses is restored and the same amount is
#	taken from the armor. When the armor runs out, damage passes normally.
#
#	The armor is a real subsystem of the ship ("Ablative Armor"), created
#	when the ship enters play. Other modules (e.g. StatusHUD, which draws
#	the armor bar) read it with GetArmorInfo(pShip).
#	If the game refuses to create the subsystem, the module falls back to
#	an internal armor value with its own regeneration (version 0.1 mode).
#
#	- Armor capacity: a percentage of the ship's hull (default 50%).
#	- Regeneration: the armor is repaired with the ship's repair rate (the
#	  repair points per second of its repair system), as a subsystem harder
#	  to repair than the ship's own hull (ArmorComplexity, default 200% of
#	  the hull's repair complexity), slower when the repair system is
#	  damaged. It waits while the hull is damaged: the hull is repaired
#	  first, then the armor. Done by the module itself whenever the game is
#	  not repairing the armor.
#	- Bleed-through: like the game's shields, a worn armor lets part of each
#	  hit through. Above BleedStart (default 50%) of armor it stops
#	  everything; below, the share that goes through grows in a straight
#	  line up to BleedMax (default 50%) when the armor is empty.
#	- HUD: drawn by the StatusHUD module.
#
#	How it works: the module remembers the condition of the hull and every
#	subsystem of armored ships. On every weapon hit and on every cycle of
#	the Spaceframe timer it compares them, restores any loss and charges it
#	to the armor. This catches every kind of damage (weapons, collisions,
#	explosions), whatever the order in which the game applies it.
#
#	Written for Python 1.5.2 (Bridge Commander's interpreter):
#	no "+=", no list comprehensions, no True/False, and no "continue"
#	inside a "try" block.
#
#	Enabling it on a ship: add "AblativeArmor" to the ship in
#	scripts\Custom\Spaceframe\Ships.py.
###############################################################################
import App
import sys

NAME = "AblativeArmor"
ARMOR_NAME = "Ablative Armor"
MIN_ARMOR = 1.0		# the armor subsystem never goes below this condition

# Armor record (one per armored ship), a list:
REC_ARMOR = 0		# armor now (internal mode only)
REC_MAX = 1		# armor capacity
REC_REGEN = 2		# armor regeneration per second (internal mode only)
REC_ENTRIES = 3		# [subsystem, last known condition, cost factor] list
REC_SUB = 4		# the armor subsystem, or None in internal mode
REC_LAST = 5		# armor subsystem condition after our last change
REC_COMPLEXITY = 6	# armor repair complexity

g_pCore = None		# the Spaceframe core, set in Start()
g_dTypeCache = {}	# ship file name -> armor percentage (0 = no armor)
g_dShips = {}		# ship ObjID -> armor record, or None (no armor)
g_fSubsystemCost = 1.0
g_fArmorComplexity = 2.0	# times the hull's repair complexity
g_fBleedStart = 0.5		# armor fraction below which hits bleed through
g_fBleedMax = 0.5		# share that bleeds through with the armor empty
g_iCreateSubsystem = 1
g_iTargetable = 1
g_iReported = 0		# subsystem creation result already shown on screen


###############################################################################
#	Configuration and messages
###############################################################################
def GetConfig():
	import Custom.Spaceframe.Modules.AblativeArmor.Config
	return Custom.Spaceframe.Modules.AblativeArmor.Config


def Notify(sText):
	# Console log, plus an on-screen banner when Debug = 1 in the core config.
	g_pCore.Log(NAME, sText)
	if g_pCore.GetConfigValue("Debug", 0):
		try:
			import MissionLib
			MissionLib.TextBanner(None, App.TGString(sText), 0.0, 0.0, 0.1, 12, 1)
		except:
			pass


def GetArmorPercent(pShip):
	# Returns the ship's armor as a percentage of its hull, or 0.
	sName = g_pCore.GetShipFileName(pShip)
	if g_dTypeCache.has_key(sName):
		return g_dTypeCache[sName]

	fValue = 0.0

	# 1) Spaceframe's Ships.py (or the ship's Bedrock plugin), via the core.
	#    -1 (Def in Ships.py) means DefaultArmor from this Config.py.
	fValue = g_pCore.GetShipTech(pShip, NAME, 0)
	if fValue == -1:
		fValue = getattr(GetConfig(), "DefaultArmor", 50)

	# 2) Old list in this module's Config.py, still accepted.
	if fValue <= 0:
		try:
			dShips = GetConfig().Ships
			if dShips.has_key(sName):
				fValue = dShips[sName]
		except:
			pass

	try:
		fValue = float(fValue)
	except:
		fValue = 0.0
	if fValue < 0.0:
		fValue = 0.0

	g_dTypeCache[sName] = fValue
	if fValue > 0.0:
		g_pCore.Log(NAME, "Ship type with armor: " + sName + " " + str(fValue) + "% of hull")
	return fValue


###############################################################################
#	Armor subsystem
###############################################################################
def GetCoord(pPoint, sAxis):
	# Reads one coordinate of a game point (GetX() or .x style).
	try:
		return float(getattr(pPoint, "Get" + sAxis)())
	except:
		return float(getattr(pPoint, {"X": "x", "Y": "y", "Z": "z"}[sAxis]))


def GetXYZ(pPoint):
	return GetCoord(pPoint, "X"), GetCoord(pPoint, "Y"), GetCoord(pPoint, "Z")


def GetXY(pPoint):
	return GetCoord(pPoint, "X"), GetCoord(pPoint, "Y")


def GetArmorComplexity(pShip):
	# How hard the armor is to repair: the hull's repair complexity (set by
	# each ship, usually 1.0) times ArmorComplexity.
	fHull = 1.0
	try:
		fHull = float(pShip.GetHull().GetRepairComplexity())
	except:
		try:
			fHull = float(pShip.GetHull().GetProperty().GetRepairComplexity())
		except:
			fHull = 1.0
	if fHull <= 0.0:
		fHull = 1.0
	return fHull * g_fArmorComplexity


def CreateArmorSubsystem(pShip, fMax, fComplexity):
	# Creates the "Ablative Armor" subsystem on the ship. Returns it, or
	# None if the game does not accept it.
	global g_iReported
	pSub = None
	try:
		pHull = pShip.GetHull()
		# Same complexity as the module's own regeneration, so the game's
		# repair teams (if they ever repair it) are not faster.

		# Same definitions as the ship's own hull, except:
		#   Critical = 0: a critical subsystem destroys the ship when it is
		#                 lost, and the armor is meant to be used up;
		#   Primary  = 0: the primary hull is the one the game uses for the
		#                 ship's health and death.
		fX, fY, fZ = 0.0, 0.0, 0.0
		f2DX, f2DY = 64.0, 64.0
		try:
			pHullProp = pHull.GetProperty()
			fX, fY, fZ = GetXYZ(pHullProp.GetPosition())
			f2DX, f2DY = GetXY(pHullProp.GetPosition2D())
		except:
			g_pCore.Log(NAME, "Could not read the hull position, using defaults.")

		pProp = App.HullProperty_Create(ARMOR_NAME)
		pProp.SetMaxCondition(fMax)
		pProp.SetCritical(0)
		pProp.SetTargetable(g_iTargetable)
		pProp.SetPrimary(0)
		pProp.SetPosition(fX, fY, fZ)
		pProp.SetPosition2D(f2DX, f2DY)
		pProp.SetRepairComplexity(fComplexity)
		pProp.SetDisabledPercentage(0.0)
		pProp.SetRadius(1.0)

		pSub = App.HullClass_Create(pProp)
		if pSub != None:
			pShip.AddSubsystem(pSub)
			try:
				pSub.SetParentShip(pShip)
			except:
				pass
			pSub.SetCondition(fMax)
			if pSub.GetMaxCondition() <= 0.0:
				pSub = None
	except:
		g_pCore.Log(NAME, "Subsystem creation failed: " + str(sys.exc_info()[0]) + " - " + str(sys.exc_info()[1]))
		pSub = None

	if pSub != None:
		# Register the armor with the repair system, so it shows in the
		# repair list and the repair teams work on it.
		try:
			pShip.GetRepairSubsystem().AddSubsystem(pSub)
		except:
			g_pCore.Log(NAME, "Could not register the armor with the repair system: " + str(sys.exc_info()[1]))
		# Let the player's damage display know about the new subsystem.
		try:
			import MissionLib
			pPlayer = MissionLib.GetPlayer()
			if (pPlayer != None) and (pPlayer.GetObjID() == pShip.GetObjID()):
				pDisplay = App.TacticalControlWindow_GetTacticalControlWindow().GetShipDisplay()
				pDisplay.GetDamageDisplay().UpdateForNewShip()
		except:
			pass

	if not g_iReported:
		g_iReported = 1
		if pSub != None:
			Notify("Ablative Armor: subsystem mode")
		else:
			Notify("Ablative Armor: internal mode (subsystem not available)")
	return pSub


###############################################################################
#	Armor records
###############################################################################
def GetSubsystems(pShip):
	# Hull plus every subsystem and child subsystem, without duplicates.
	lResult = []
	dSeen = {}
	lQueue = []

	pHull = pShip.GetHull()
	if pHull != None:
		lQueue.append(pHull)

	try:
		kIter = pShip.StartGetSubsystemMatch(App.CT_SHIP_SUBSYSTEM)
		pSub = pShip.GetNextSubsystemMatch(kIter)
		while pSub != None:
			lQueue.append(pSub)
			pSub = pShip.GetNextSubsystemMatch(kIter)
		pShip.EndGetSubsystemMatch(kIter)
	except:
		g_pCore.Log(NAME, "Subsystem list not available, using known systems only.")
		for pSub in (pShip.GetShields(), pShip.GetPowerSubsystem(), pShip.GetSensorSubsystem(),
				pShip.GetImpulseEngineSubsystem(), pShip.GetWarpEngineSubsystem(),
				pShip.GetRepairSubsystem(), pShip.GetCloakingSubsystem(),
				pShip.GetTractorBeamSystem(), pShip.GetPhaserSystem(),
				pShip.GetTorpedoSystem(), pShip.GetPulseWeaponSystem()):
			if pSub != None:
				lQueue.append(pSub)

	while len(lQueue) > 0:
		pSub = lQueue[0]
		del lQueue[0]
		try:
			iID = pSub.GetObjID()
		except:
			iID = None
		if (iID == None) or (not dSeen.has_key(iID)):
			if iID != None:
				dSeen[iID] = 1
			lResult.append(pSub)
			try:
				for i in range(pSub.GetNumChildSubsystems()):
					pChild = pSub.GetChildSubsystem(i)
					if pChild != None:
						lQueue.append(pChild)
			except:
				pass
	return lResult


def NewRecord(pShip, fPercent):
	pHull = pShip.GetHull()
	fMax = pHull.GetMaxCondition() * fPercent / 100.0

	fComplexity = GetArmorComplexity(pShip)

	pArmor = None
	if g_iCreateSubsystem:
		pArmor = CreateArmorSubsystem(pShip, fMax, fComplexity)
	iArmorID = None
	if pArmor != None:
		try:
			iArmorID = pArmor.GetObjID()
		except:
			iArmorID = None

	lEntries = []
	for pSub in GetSubsystems(pShip):
		iID = None
		try:
			iID = pSub.GetObjID()
		except:
			pass
		# The armor subsystem is never restored: its losses are armor spent.
		if (iArmorID == None) or (iID != iArmorID):
			fCost = g_fSubsystemCost
			try:
				if iID == pHull.GetObjID():
					fCost = 1.0
			except:
				pass
			lEntries.append([pSub, pSub.GetCondition(), fCost])

	g_pCore.Log(NAME, str(pShip.GetName()) + ": armor " + str(int(fMax)) + ", repair complexity " + str(fComplexity) + ", " + str(len(lEntries)) + " subsystems tracked")
	return [fMax, fMax, 0.0, lEntries, pArmor, None, fComplexity]


def GetRecord(pShip):
	try:
		iID = pShip.GetObjID()
	except:
		return None
	if g_dShips.has_key(iID):
		return g_dShips[iID]
	fPercent = GetArmorPercent(pShip)
	if fPercent <= 0.0:
		g_dShips[iID] = None
		return None
	lRecord = NewRecord(pShip, fPercent)
	g_dShips[iID] = lRecord
	return lRecord


def GetArmor(lRecord):
	pArmor = lRecord[REC_SUB]
	if pArmor != None:
		fArmor = pArmor.GetCondition() - MIN_ARMOR
		if fArmor < 0.0:
			fArmor = 0.0
		return fArmor
	return lRecord[REC_ARMOR]


def SetArmor(pShip, lRecord, fArmor):
	if fArmor < 0.0:
		fArmor = 0.0
	pArmor = lRecord[REC_SUB]
	if pArmor != None:
		pArmor.SetCondition(fArmor + MIN_ARMOR)
		lRecord[REC_LAST] = fArmor + MIN_ARMOR
		# Make sure the repair teams know the armor needs work.
		try:
			if fArmor + MIN_ARMOR < pArmor.GetMaxCondition():
				pShip.GetRepairSubsystem().AddToRepairList(pArmor)
		except:
			pass
	else:
		lRecord[REC_ARMOR] = fArmor


###############################################################################
#	Core logic
###############################################################################
def Absorb(pShip, lRecord):
	# Restores every loss since the last check, paid by the armor.
	lLosses = []
	fCost = 0.0
	for lEntry in lRecord[REC_ENTRIES]:
		fNow = lEntry[0].GetCondition()
		fLoss = lEntry[1] - fNow
		if fLoss > 0.0:
			lLosses.append([lEntry, fNow, fLoss])
			fCost = fCost + fLoss * lEntry[2]
		else:
			# Unchanged or repaired: just remember the new value.
			lEntry[1] = fNow

	if len(lLosses) == 0:
		return

	fArmor = GetArmor(lRecord)
	if (fArmor <= 0.0) or (fCost <= 0.0):
		for lLoss in lLosses:
			lLoss[0][1] = lLoss[1]
		return

	# Restore the share the armor stops (all of it, unless it is worn below
	# BleedStart), as far as the armor can pay for it.
	fFraction = 1.0 - GetBleed(fArmor, lRecord[REC_MAX])
	if fCost * fFraction > fArmor:
		fFraction = fArmor / fCost

	for lLoss in lLosses:
		lEntry = lLoss[0]
		fNew = lLoss[1] + lLoss[2] * fFraction
		try:
			fMaxCond = lEntry[0].GetMaxCondition()
			if fNew > fMaxCond:
				fNew = fMaxCond
		except:
			pass
		lEntry[0].SetCondition(fNew)
		lEntry[1] = fNew

	SetArmor(pShip, lRecord, fArmor - fCost * fFraction)


def GetBleed(fArmor, fMax):
	# Share of a hit that goes through the armor: 0 at BleedStart or more,
	# growing in a straight line to BleedMax when the armor is empty.
	if (fMax <= 0.0) or (g_fBleedMax <= 0.0) or (g_fBleedStart <= 0.0):
		return 0.0
	fLevel = fArmor / fMax
	if fLevel >= g_fBleedStart:
		return 0.0
	return g_fBleedMax * (1.0 - fLevel / g_fBleedStart)


def HullDamaged(pShip):
	# 1 while the hull is below full condition, that is, while the repair
	# teams still have hull work to do.
	try:
		pHull = pShip.GetHull()
		return pHull.GetCondition() < pHull.GetMaxCondition() - 0.5
	except:
		return 0


def Regenerate(pShip, lRecord, fSeconds):
	# Internal mode: always. Subsystem mode: only while the game's repair
	# teams are not repairing the armor themselves (it rises on its own).
	# Either way, only once the hull is fully repaired.
	pArmor = lRecord[REC_SUB]
	if pArmor != None:
		fNow = pArmor.GetCondition()
		fMaxCond = pArmor.GetMaxCondition()
		fLast = lRecord[REC_LAST]
		lRecord[REC_LAST] = fNow
		if fNow >= fMaxCond:
			return
		if (fLast != None) and (fNow > fLast + 0.01):
			lRecord[REC_REGEN] = 0.0
			return
	elif lRecord[REC_ARMOR] >= lRecord[REC_MAX]:
		return
	if HullDamaged(pShip):
		lRecord[REC_REGEN] = 0.0
		return
	fRate = 0.0
	try:
		pRepair = pShip.GetRepairSubsystem()
		if pRepair != None:
			fRate = pRepair.GetProperty().GetMaxRepairPoints() * pRepair.GetConditionPercentage()
	except:
		fRate = 0.0
	# Repair points spent on a harder subsystem fix less of it.
	fRate = fRate / lRecord[REC_COMPLEXITY]
	lRecord[REC_REGEN] = fRate
	if pArmor != None:
		fNew = fNow + fRate * fSeconds
		if fNew > fMaxCond:
			fNew = fMaxCond
		pArmor.SetCondition(fNew)
		lRecord[REC_LAST] = fNew
		return
	fArmor = lRecord[REC_ARMOR] + fRate * fSeconds
	if fArmor > lRecord[REC_MAX]:
		fArmor = lRecord[REC_MAX]
	lRecord[REC_ARMOR] = fArmor


###############################################################################
#	Information for other modules (e.g. StatusHUD)
###############################################################################
def GetArmorInfo(pShip):
	# Returns (armor now, armor capacity, armor subsystem or None) for an
	# armored ship, or None if the ship has no armor.
	lRecord = GetRecord(pShip)
	if (lRecord == None) or (lRecord[REC_MAX] <= 0.0):
		return None
	pArmor = lRecord[REC_SUB]
	if pArmor != None:
		return (pArmor.GetCondition(), pArmor.GetMaxCondition(), pArmor)
	return (lRecord[REC_ARMOR], lRecord[REC_MAX], None)


###############################################################################
#	Spaceframe module interface
###############################################################################
def Start(pCore):
	global g_pCore, g_dTypeCache, g_dShips, g_iReported
	global g_fSubsystemCost, g_fArmorComplexity, g_iCreateSubsystem, g_iTargetable
	global g_fBleedStart, g_fBleedMax
	g_pCore = pCore
	g_dTypeCache = {}
	g_dShips = {}
	g_iReported = 0
	import Custom.Spaceframe.Modules.AblativeArmor.Config
	reload(Custom.Spaceframe.Modules.AblativeArmor.Config)
	pConfig = GetConfig()
	# Percentages (0 to 100) in the config, fractions here.
	g_fSubsystemCost = float(getattr(pConfig, "SubsystemDamageCost", 100)) / 100.0
	g_fArmorComplexity = float(getattr(pConfig, "ArmorComplexity", 200)) / 100.0
	if g_fArmorComplexity <= 0.0:
		g_fArmorComplexity = 0.01
	g_fBleedStart = float(getattr(pConfig, "BleedStart", 50)) / 100.0
	g_fBleedMax = float(getattr(pConfig, "BleedMax", 50)) / 100.0
	if g_fBleedMax > 1.0:
		g_fBleedMax = 1.0
	g_iCreateSubsystem = getattr(pConfig, "CreateSubsystem", 1)
	g_iTargetable = getattr(pConfig, "Targetable", 1)


def Stop():
	global g_dTypeCache, g_dShips
	g_dTypeCache = {}
	g_dShips = {}


def Tick(lShips):
	fSeconds = g_pCore.GetInterval()
	dAlive = {}
	for pShip in lShips:
		lRecord = GetRecord(pShip)
		dAlive[pShip.GetObjID()] = 1
		if lRecord != None:
			Absorb(pShip, lRecord)
			Regenerate(pShip, lRecord, fSeconds)

	# Forget ships that are gone, so no stale subsystem is ever touched.
	for iID in g_dShips.keys():
		if not dAlive.has_key(iID):
			del g_dShips[iID]


def WeaponHit(pShip, pEvent):
	# Absorb right away; the next cycle catches anything applied later.
	# Hits stopped by the shields do no hull or subsystem damage, so they
	# are skipped (the full subsystem check is the costly part).
	try:
		if not pEvent.IsHullHit():
			return
	except:
		pass
	if pShip.IsDead() or pShip.IsDying():
		return
	lRecord = GetRecord(pShip)
	if lRecord != None:
		Absorb(pShip, lRecord)


def Diag():
	lSets, lShips = g_pCore.GetShipsInPlay()
	for pShip in lShips:
		lRecord = GetRecord(pShip)
		if lRecord == None:
			print ("  " + str(pShip.GetName()) + " | no armor")
		else:
			sMode = "internal"
			if lRecord[REC_SUB] != None:
				sMode = "subsystem"
			print ("  " + str(pShip.GetName()) + " | " + sMode + " | armor " + str(int(GetArmor(lRecord))) + "/" + str(int(lRecord[REC_MAX])) + " | subsystems " + str(len(lRecord[REC_ENTRIES])))
