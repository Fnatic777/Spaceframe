###############################################################################
#	Spaceframe - lightweight module framework for Bridge Commander
#	Version 0.6
#
#	A small core that loads gameplay modules and gives them shared services,
#	so every module does not need its own timer, event handler or hook in the
#	game files. Built for BC Remastered and Orion Delta.
#
#	Services for modules:
#	  - one shared timer: Tick(lShips) is called on every cycle with the list
#	    of live ships in play (built once per cycle for all modules);
#	  - one shared weapon hit handler: WeaponHit(pShip, pEvent) is called
#	    when a weapon hits a ship;
#	  - ship identification by file name, cached: GetShipFileName(pShip);
#	  - per-ship technology settings from Ships.py (or the ship's Bedrock
#	    plugin), cached: GetShipTech(pShip, sTech, pDefault);
#	  - the timer interval in seconds: GetInterval();
#	  - access to another running module: GetModule(sName) (or None);
#	  - logging to the Test Mode console: Log(sModule, sText);
#	  - error isolation: a module that fails too often is disabled alone,
#	    the other modules keep running.
#
#	Writing a module: create scripts\Custom\Spaceframe\Modules\<Name>\ with
#	an empty __init__.py and <Name>.py. All functions are optional:
#	    Start(pCore)            - at mission start (pCore = this module)
#	    Stop()                  - at mission end
#	    Tick(lShips)            - on every cycle
#	    WeaponHit(pShip, pEvent) - when a weapon hits a ship
#	    Diag()                  - extra lines for the diagnostics command
#	Modules are found automatically. To disable one, set it to 0 in
#	Config.py ("Modules").
#	Which ships use which module is set in Ships.py, with the module name
#	as the key: a module reads it with pCore.GetShipTech(pShip, NAME).
#
#	Written for Python 1.5.2 (Bridge Commander's interpreter):
#	no "+=", no list comprehensions, no True/False, and no "continue"
#	inside a "try" block.
###############################################################################
import App
import sys
import string
import time

VERSION = "0.6"
MODULES_PATH = "scripts/Custom/Spaceframe/Modules"
MODULES_PACKAGE = "Custom.Spaceframe.Modules."
HIT_HANDLER = "Custom.Spaceframe.Spaceframe.OnWeaponHit"
MAX_ERRORS = 50

g_lModules = []		# list of [name, module, active, errors]
g_pRunner = None	# shared timer
g_pMission = None	# mission the weapon hit handler was registered on
g_dShipNames = {}	# ship ObjID -> ship file name
g_dShipTechs = {}	# ship file name -> {technology: value}
g_fInterval = 0.25	# seconds between timer cycles
LOG_FILE = "Spaceframe_debug.log"	# in the game folder (Debug = 1 only)
g_fOpen = open		# the file opener of the logger (tests replace it)
g_pLogFile = None	# plain Python file object, opened on the first Log call
g_bLogOpenFailed = 0	# 1 = the file logger is off until the next Start()
g_bLogBanner = 0	# 1 = the "log file unavailable" banner was shown this session
g_bStopping = 0		# 1 = Stop() ran since the last Start(): no banner from the logger
g_iLogLines = 0		# lines written to the log file this session
LOG_MAX_LINES = 5000	# size cap per session


###############################################################################
#	Configuration
###############################################################################
def GetConfig():
	import Custom.Spaceframe.Config
	return Custom.Spaceframe.Config


def GetInterval():
	# Seconds of game time between two Tick() calls.
	return g_fInterval


def GetConfigValue(sName, pDefault):
	try:
		return getattr(GetConfig(), sName, pDefault)
	except:
		return pDefault


###############################################################################
#	Logging (Test Mode console only, when Debug = 1 in Config.py)
###############################################################################
def LogStamp():
	# Game time with 2 decimals; the real clock when the game time is unavailable.
	try:
		return "%.2f" % App.g_kUtopiaModule.GetGameTime()
	except:
		pass
	try:
		return "%.2f" % time.time()
	except:
		return "0.00"


def LogFileState():
	# "off" (Debug 0), "ok" (file open), "failed" (open/write failed) or "unopened".
	if not GetConfigValue("Debug", 0):
		return "off"
	if g_pLogFile != None:
		return "ok"
	if g_bLogOpenFailed:
		return "failed"
	return "unopened"


def LogToFile(sLine):
	# Appends one line to the log file (opened on the first call of a session).
	# Returns 1 when written, 0 when the file logger is unavailable.
	global g_pLogFile, g_bLogOpenFailed, g_bLogBanner, g_iLogLines
	if g_bLogOpenFailed:
		return 0
	if g_pLogFile == None:
		pNew = None
		try:
			pNew = g_fOpen(LOG_FILE, "a")
			pNew.write("==== Spaceframe session " + time.ctime(time.time()) + " ====\n")
			g_pLogFile = pNew
		except:
			g_bLogOpenFailed = 1
			g_pLogFile = None
			if pNew != None:
				try:
					pNew.close()
				except:
					pass
			if (not g_bLogBanner) and (not g_bStopping):
				g_bLogBanner = 1
				ShowProblem("Spaceframe log file unavailable (file IO blocked by the game)")
			return 0
	try:
		if g_iLogLines >= LOG_MAX_LINES:
			if g_iLogLines == LOG_MAX_LINES:
				g_iLogLines = g_iLogLines + 1
				g_pLogFile.write("==== log capped at " + str(LOG_MAX_LINES) + " lines ====\n")
				g_pLogFile.flush()
			return 0
		g_iLogLines = g_iLogLines + 1
		g_pLogFile.write(sLine)
		g_pLogFile.flush()
		return 1
	except:
		g_bLogOpenFailed = 1
		CloseLogFile()
		return 0


def CloseLogFile():
	global g_pLogFile
	pFile = g_pLogFile
	g_pLogFile = None
	if pFile != None:
		try:
			pFile.close()
		except:
			pass


def Log(sModule, sText):
	if not GetConfigValue("Debug", 0):
		return
	try:
		sLine = "%s %s: %s\n" % (LogStamp(), sModule, sText)
		if LogToFile(sLine):
			return
	except:
		pass
	try:
		App.CPyDebug().Print(sModule + ": " + sText + "\n")
	except:
		pass


def ShowProblem(sText):
	# Visible banner for a failure the player must know about (not Debug).
	try:
		import MissionLib
		MissionLib.TextBanner(None, App.TGString(sText), 0.0, 0.0, 0.1, 12, 1)
	except:
		pass


def ModuleError(lEntry, sWhere):
	lEntry[3] = lEntry[3] + 1
	try:
		eType, eValue = sys.exc_info()[:2]
		Log("Spaceframe", "ERROR in " + lEntry[0] + "." + sWhere + ": " + str(eType) + " - " + str(eValue))
	except:
		pass
	if (lEntry[3] >= MAX_ERRORS) and lEntry[2]:
		lEntry[2] = 0
		Log("Spaceframe", "Too many errors, module " + lEntry[0] + " disabled until the next mission.")


###############################################################################
#	Ship helpers
###############################################################################
def GetShipFileName(pShip):
	# Returns the ship's file name (e.g. "AkiraCVS"), cached per ship.
	# The hardpoint name is only used if the file name is not available:
	# variants often reuse another ship's hardpoint and would be mistaken.
	try:
		iID = pShip.GetObjID()
	except:
		iID = None
	if (iID != None) and g_dShipNames.has_key(iID):
		return g_dShipNames[iID]

	sName = ""
	try:
		sScript = pShip.GetScript()
		if sScript:
			lParts = string.split(sScript, ".")
			sName = lParts[-1]
	except:
		pass
	if not sName:
		try:
			sName = pShip.GetShipProperty().GetShipName()
		except:
			sName = ""
	if not sName:
		sName = ""

	if iID != None:
		g_dShipNames[iID] = sName
	return sName


def GetBedrockPlugin(sName):
	# The ship's Orion Delta (Bedrock) plugin, or None (stock ships).
	if not sName:
		return None
	sPath = "Custom.Bedrock.Ships." + sName
	try:
		__import__(sPath)
		return sys.modules.get(sPath)
	except:
		return None


def GetShipGroups(sName):
	# (race, family) of a ship type, from its Bedrock plugin: Race (e.g.
	# "Federation") and SubMenu (e.g. "Galaxy", the sub-menu its variants
	# share in the ship menus; "N/A" = no family). None where unknown.
	sRace = None
	sFamily = None
	pPlugin = GetBedrockPlugin(sName)
	if pPlugin != None:
		sRace = getattr(pPlugin, "Race", None)
		sFamily = getattr(pPlugin, "SubMenu", None)
		if sFamily == "N/A":
			sFamily = None
	return (sRace, sFamily)


def MergeTechs(dTechs, dFrom):
	if dFrom != None:
		for sTech in dFrom.keys():
			dTechs[sTech] = dFrom[sTech]


def GetShipTechs(sName):
	# All technology settings of a ship type. Each level overrides the one
	# before (0 switches a technology off):
	#   1. Ships.py All          - every ship
	#   2. Ships.py Races        - by race (plugin's Race)
	#   3. Ships.py Families     - by family (plugin's SubMenu)
	#   4. the ship's Bedrock plugin (Orion Delta): a module name set there,
	#      e.g. "MVShields = 100"
	#   5. Ships.py Ships        - this ship
	if g_dShipTechs.has_key(sName):
		return g_dShipTechs[sName]
	dTechs = {}
	try:
		import Custom.Spaceframe.Ships
		pShips = Custom.Spaceframe.Ships
	except:
		pShips = None
		Log("Spaceframe", "Could not read Ships.py: " + str(sys.exc_info()[1]))
	tGroups = GetShipGroups(sName)
	try:
		if pShips != None:
			MergeTechs(dTechs, getattr(pShips, "All", None))
			dRaces = getattr(pShips, "Races", {})
			if (tGroups[0] != None) and dRaces.has_key(tGroups[0]):
				MergeTechs(dTechs, dRaces[tGroups[0]])
			dFamilies = getattr(pShips, "Families", {})
			if (tGroups[1] != None) and dFamilies.has_key(tGroups[1]):
				MergeTechs(dTechs, dFamilies[tGroups[1]])
	except:
		Log("Spaceframe", "Ships.py groups error: " + str(sys.exc_info()[1]))
	pPlugin = GetBedrockPlugin(sName)
	if pPlugin != None:
		for lEntry in g_lModules:
			if hasattr(pPlugin, lEntry[0]):
				dTechs[lEntry[0]] = getattr(pPlugin, lEntry[0])
	try:
		if (pShips != None) and sName:
			dShips = getattr(pShips, "Ships", {})
			if dShips.has_key(sName):
				MergeTechs(dTechs, dShips[sName])
	except:
		Log("Spaceframe", "Could not read Ships.py: " + str(sys.exc_info()[1]))
	g_dShipTechs[sName] = dTechs
	return dTechs


def GetShipTech(pShip, sTech, pDefault = 0):
	# A ship's setting for one technology (e.g. "MVShields"), or pDefault
	# if the ship does not have it.
	dTechs = GetShipTechs(GetShipFileName(pShip))
	if dTechs.has_key(sTech):
		return dTechs[sTech]
	return pDefault


def GetShipsInPlay():
	# Live ships in the player's set and in the rendered set.
	lShips = []
	lSetNames = []
	lSets = []
	try:
		import MissionLib
		pPlayer = MissionLib.GetPlayer()
		if pPlayer != None:
			pSet = pPlayer.GetContainingSet()
			if pSet != None:
				lSets.append(pSet)
				lSetNames.append(pSet.GetName())
	except:
		pass
	try:
		pSet = App.g_kSetManager.GetRenderedSet()
		if (pSet != None) and (pSet.GetName() not in lSetNames):
			lSets.append(pSet)
	except:
		pass
	for pSet in lSets:
		for kObj in pSet.GetClassObjectList(App.CT_SHIP):
			pShip = App.ShipClass_Cast(kObj)
			if (pShip != None) and (not pShip.IsDead()) and (not pShip.IsDying()):
				lShips.append(pShip)
	return lSets, lShips


###############################################################################
#	Module loading
###############################################################################
def FindModules():
	lNames = []
	try:
		import nt
		lFiles = nt.listdir(MODULES_PATH)
	except:
		lFiles = []
		Log("Spaceframe", "Could not list " + MODULES_PATH)
	for sFile in lFiles:
		# Module folders have no extension; skip files like __init__.py.
		if string.find(sFile, ".") < 0:
			lNames.append(sFile)
	lNames.sort()
	return lNames


def LoadModules():
	global g_lModules
	g_lModules = []
	try:
		dEnabled = GetConfig().Modules
	except:
		dEnabled = {}
	for sName in FindModules():
		iOn = 1
		if dEnabled.has_key(sName):
			iOn = dEnabled[sName]
		if not iOn:
			Log("Spaceframe", "Module " + sName + " disabled in Config.py")
		else:
			sPath = MODULES_PACKAGE + sName + "." + sName
			try:
				__import__(sPath)
				pModule = sys.modules[sPath]
				g_lModules.append([sName, pModule, 1, 0])
				Log("Spaceframe", "Module loaded: " + sName)
			except:
				eType, eValue = sys.exc_info()[:2]
				Log("Spaceframe", "Could not load module " + sName + ": " + str(eType) + " - " + str(eValue))


def GetModule(sName):
	# Another module, if it is loaded and active (else None). Lets modules
	# use each other without depending on each other being installed.
	for lEntry in g_lModules:
		if (lEntry[0] == sName) and lEntry[2]:
			return lEntry[1]
	return None


def CallModules(sFunction, lArgs, bDisableOnError = 0, bAll = 0):
	# Calls sFunction on every active module that defines it (bAll: on every
	# loaded module, disabled ones too; used for Stop so they can clean up).
	# With bDisableOnError, a module that fails is disabled at once
	# (used for Start: a module that cannot start must not keep running).
	# After a Tick that completes without error the module's error counter
	# goes back to 0: MAX_ERRORS counts consecutive failing cycles.
	for lEntry in g_lModules:
		if lEntry[2] or bAll:
			pFunc = getattr(lEntry[1], sFunction, None)
			if pFunc != None:
				try:
					apply(pFunc, lArgs)
					if sFunction == "Tick":
						lEntry[3] = 0
				except:
					ModuleError(lEntry, sFunction)
					if bDisableOnError:
						lEntry[2] = 0
						Log("Spaceframe", "Module " + lEntry[0] + " could not start and was disabled.")


###############################################################################
#	Shared timer and weapon hit handler
###############################################################################
class Runner:
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
			lSets, lShips = GetShipsInPlay()
		except:
			return
		CallModules("Tick", (lShips,))


def OnWeaponHit(pObject, pEvent):
	if (g_pRunner == None) or (not g_pRunner.bActive):
		return
	try:
		pShip = App.ShipClass_Cast(pEvent.GetDestination())
	except:
		pShip = None
	if pShip == None:
		return
	CallModules("WeaponHit", (pShip, pEvent))


###############################################################################
#	Public interface: Start() at mission start, Stop() at mission end.
###############################################################################
def Start(pMission = None):
	global g_pRunner, g_pMission, g_dShipNames, g_dShipTechs, g_fInterval
	global g_bLogOpenFailed, g_bLogBanner, g_bStopping, g_iLogLines
	Stop()
	# A new session: the file logger may try (and warn) again.
	g_bLogOpenFailed = 0
	g_bLogBanner = 0
	g_bStopping = 0
	g_iLogLines = 0
	g_dShipNames = {}
	g_dShipTechs = {}
	try:
		import Custom.Spaceframe.Ships
		reload(Custom.Spaceframe.Ships)
	except:
		Log("Spaceframe", "Could not load Ships.py: " + str(sys.exc_info()[1]))
	try:
		import Custom.Spaceframe.Config
		reload(Custom.Spaceframe.Config)
		if App.g_kUtopiaModule.IsMultiplayer() and (not GetConfigValue("EnableInMultiplayer", 0)):
			Log("Spaceframe", "Multiplayer detected, Spaceframe disabled.")
			return
	except:
		Log("Spaceframe", "Could not load Config.py: " + str(sys.exc_info()[1]))
		ShowProblem("Spaceframe: Config.py has an error, the mod is off for this battle")
		return

	LoadModules()
	if len(g_lModules) == 0:
		Log("Spaceframe", "No modules to run.")
		return

	# The interval is set before the modules start, so GetInterval() is right in Start().
	fInterval = 0.25
	bIntervalOK = 1
	try:
		fInterval = float(GetConfigValue("Interval", 0.25))
		if fInterval < 0.05:
			fInterval = 0.05
		g_fInterval = fInterval
	except:
		bIntervalOK = 0

	CallModules("Start", (sys.modules[__name__],), 1)

	try:
		if not bIntervalOK:
			raise ValueError("bad Interval")
		g_pRunner = Runner(fInterval)
	except:
		Log("Spaceframe", "Could not start the timer.")
		return

	try:
		if pMission == None:
			pMission = App.Game_GetCurrentGame().GetCurrentEpisode().GetCurrentMission()
		if pMission != None:
			App.g_kEventManager.AddBroadcastPythonFuncHandler(App.ET_WEAPON_HIT, pMission, HIT_HANDLER)
			g_pMission = pMission
	except:
		g_pMission = None
		Log("Spaceframe", "Could not register the weapon hit handler.")

	Log("Spaceframe", "Spaceframe " + VERSION + " started, " + str(len(g_lModules)) + " module(s), interval " + str(fInterval) + "s.")


def Stop():
	global g_pRunner, g_pMission, g_lModules, g_bStopping
	g_bStopping = 1
	if g_pMission != None:
		try:
			App.g_kEventManager.RemoveBroadcastHandler(App.ET_WEAPON_HIT, g_pMission, HIT_HANDLER)
		except:
			pass
		g_pMission = None
	if g_pRunner != None:
		g_pRunner.bActive = 0
		g_pRunner.pProcess = None
		g_pRunner = None
	if len(g_lModules) > 0:
		CallModules("Stop", (), 0, 1)
		g_lModules = []
		Log("Spaceframe", "Spaceframe stopped.")
	CloseLogFile()


###############################################################################
#	Diagnostics: in the Test Mode console type, one line at a time:
#	    import Custom.Spaceframe.Spaceframe
#	    Custom.Spaceframe.Spaceframe.Diag()
###############################################################################
def Diag():
	print ("--- Spaceframe " + VERSION + " Diag ---")
	if g_pRunner == None:
		print ("Timer: NOT running")
	else:
		print ("Timer: running, active = " + str(g_pRunner.bActive))
	print ("Weapon hit handler: " + str(g_pMission != None))
	for lEntry in g_lModules:
		print ("Module " + lEntry[0] + " v" + str(getattr(lEntry[1], "VERSION", "?")) + ": active = " + str(lEntry[2]) + ", errors = " + str(lEntry[3]))
	lSets, lShips = GetShipsInPlay()
	print ("Sets: " + str(len(lSets)) + ", live ships: " + str(len(lShips)))
	for pShip in lShips:
		sFile = GetShipFileName(pShip)
		tGroups = GetShipGroups(sFile)
		print ("  Ship " + str(pShip.GetName()) + " | file=" + sFile + " | race=" + str(tGroups[0]) + " | family=" + str(tGroups[1]) + " | techs=" + str(GetShipTechs(sFile)))
	for lEntry in g_lModules:
		pFunc = getattr(lEntry[1], "Diag", None)
		if pFunc != None:
			print ("--- " + lEntry[0] + " ---")
			try:
				pFunc()
			except:
				print ("  ERROR " + str(sys.exc_info()[1]))
