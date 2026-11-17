###############################################################################
#	MV Shields - Multivectral Shields
#	Spaceframe module, version 0.7
#
#	Makes the 6 shield facings of a ship work as a single shield: the total
#	charge is redistributed among the facings in proportion to each facing's
#	maximum capacity. The total charge is never increased or decreased, it
#	only moves between facings.
#
#	Redistribution happens on Spaceframe's periodic cycle and/or
#	immediately on every weapon hit (Mode in Config.py). Damage that goes through a facing
#	reaches the hull normally (original game mechanic).
#
#	Written for Python 1.5.2 (Bridge Commander's interpreter):
#	no "+=", no list comprehensions, no True/False, and no "continue"
#	inside a "try" block.
#
#	Enabling it on a ship: add "MVShields" to the ship in
#	scripts\Custom\Spaceframe\Ships.py.
###############################################################################
import App
import sys

NAME = "MVShields"
VERSION = "0.7"
NUM_FACES = 6

g_pCore = None		# the Spaceframe core, set in Start()
g_dTypeCache = {}	# ship file name -> MV value (0 = no MV)
g_dErrorLogged = {}	# ship ObjID -> last error text logged for it
g_iMode = 3		# 0 = off, 1 = on hit only, 2 = cycle only, 3 = both


###############################################################################
#	Configuration
###############################################################################
def GetConfig():
	import Custom.Spaceframe.Modules.MVShields.Config
	return Custom.Spaceframe.Modules.MVShields.Config


def GetMVValue(pShip):
	# Returns the ship's MV efficiency (0-100), or 0 if it has no MV.
	sName = g_pCore.GetShipFileName(pShip)
	if g_dTypeCache.has_key(sName):
		return g_dTypeCache[sName]

	iValue = 0

	# 1) Spaceframe's Ships.py (or the ship's Bedrock plugin), via the core.
	#    -1 (Def in Ships.py) means DefaultEfficiency from this Config.py.
	iValue = g_pCore.GetShipTech(pShip, NAME, None)
	if iValue == -1:
		iValue = getattr(GetConfig(), "DefaultEfficiency", 100)

	# 2) Old list in this module's Config.py, still accepted, but only for
	#    ships with no entry at all above (an explicit 0 stays 0).
	if iValue == None:
		iValue = 0
		try:
			dShips = GetConfig().Ships
			if dShips.has_key(sName):
				iValue = dShips[sName]
		except:
			pass

	try:
		iValue = int(iValue)
	except:
		iValue = 0
	if iValue < 0:
		iValue = 0
	if iValue > 100:
		iValue = 100

	g_dTypeCache[sName] = iValue
	if iValue > 0:
		g_pCore.Log(NAME, "Ship type with MV: " + sName + " value " + str(iValue))
	return iValue


###############################################################################
#	Core logic
###############################################################################
def EqualizeShip(pShip, iValue):
	pShields = pShip.GetShields()
	if pShields == None:
		return
	if pShields.IsDisabled() or (not pShields.IsOn()):
		return
	pProp = pShields.GetProperty()
	if pProp == None:
		return

	lMax = []
	lCur = []
	fTotMax = 0.0
	fTotCur = 0.0
	for i in range(NUM_FACES):
		fMax = pProp.GetMaxShields(i)
		fCur = pShields.GetCurShields(i)
		if fMax < 0.0:
			fMax = 0.0
		if fCur < 0.0:
			fCur = 0.0
		lMax.append(fMax)
		lCur.append(fCur)
		fTotMax = fTotMax + fMax
		fTotCur = fTotCur + fCur

	if fTotMax <= 0.0:
		return

	# Each facing moves towards its proportional share of the total charge.
	# iValue = 100 reaches the target at once; lower values move part way.
	fEff = iValue / 100.0
	for i in range(NUM_FACES):
		fTarget = fTotCur * lMax[i] / fTotMax
		fNew = lCur[i] + (fTarget - lCur[i]) * fEff
		if fNew > lMax[i]:
			fNew = lMax[i]
		if fNew < 0.0:
			fNew = 0.0
		if abs(fNew - lCur[i]) > 0.01:
			pShields.SetCurShields(i, fNew)


###############################################################################
#	Spaceframe module interface
###############################################################################
def Start(pCore):
	global g_pCore, g_dTypeCache, g_iMode, g_dErrorLogged
	g_pCore = pCore
	g_dTypeCache = {}
	g_dErrorLogged = {}
	import Custom.Spaceframe.Modules.MVShields.Config
	reload(Custom.Spaceframe.Modules.MVShields.Config)
	pConfig = GetConfig()
	if hasattr(pConfig, "Mode"):
		g_iMode = pConfig.Mode
	else:
		# Older configs: ReactOnHit = 1 means both, 0 means cycle only.
		if getattr(pConfig, "ReactOnHit", 1):
			g_iMode = 3
		else:
			g_iMode = 2
	try:
		g_iMode = int(g_iMode)
	except:
		g_iMode = 3
	if (g_iMode < 0) or (g_iMode > 3):
		g_iMode = 3
	pCore.Log(NAME, "Mode " + str(g_iMode))


def Stop():
	global g_dTypeCache, g_dErrorLogged
	g_dTypeCache = {}
	g_dErrorLogged = {}


def LogShipError(pShip):
	# Logs a ship's error only the first time (or when its text changes):
	# a ship failing on every cycle would log a line every interval.
	sText = str(sys.exc_info()[0]) + " - " + str(sys.exc_info()[1])
	try:
		iID = pShip.GetObjID()
	except:
		iID = None
	if iID != None:
		if g_dErrorLogged.has_key(iID) and (g_dErrorLogged[iID] == sText):
			return
		g_dErrorLogged[iID] = sText
	try:
		sShip = str(pShip.GetName())
	except:
		sShip = "?"
	g_pCore.Log(NAME, "Error on ship " + sShip + ": " + sText)


def Tick(lShips):
	# Periodic cycle (modes 2 and 3); ships are already alive (core filter).
	if (g_iMode != 2) and (g_iMode != 3):
		return
	for pShip in lShips:
		try:
			iValue = GetMVValue(pShip)
			if iValue > 0:
				EqualizeShip(pShip, iValue)
		except:
			LogShipError(pShip)


def WeaponHit(pShip, pEvent):
	# Immediate reaction to weapon hits (modes 1 and 3).
	if (g_iMode != 1) and (g_iMode != 3):
		return
	if pShip.IsDead() or pShip.IsDying():
		return
	iValue = GetMVValue(pShip)
	if iValue > 0:
		EqualizeShip(pShip, iValue)


def Diag():
	print ("  Mode = " + str(g_iMode) + " (0 off, 1 on hit, 2 cycle, 3 both)")
	lSets, lShips = g_pCore.GetShipsInPlay()
	for pShip in lShips:
		iValue = GetMVValue(pShip)
		sLine = "  " + str(pShip.GetName()) + " | MV=" + str(iValue)
		try:
			pShields = pShip.GetShields()
			pProp = pShields.GetProperty()
			sLine = sLine + " | on=" + str(pShields.IsOn()) + " disabled=" + str(pShields.IsDisabled()) + " facings:"
			for i in range(NUM_FACES):
				sLine = sLine + " " + str(int(pShields.GetCurShields(i))) + "/" + str(int(pProp.GetMaxShields(i)))
		except:
			sLine = sLine + " | shields: ERROR " + str(sys.exc_info()[1])
		print (sLine)
