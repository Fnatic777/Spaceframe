###############################################################################
#	STProbe.py
#
#	Spaceframe module, version 0.2 - throwaway in-game probe.
#
#	Validates, in game and on screen, torpedo behavior (target list, fired
#	events, single fire, retarget, direct Fire) and the pulse arc formula
#	AutoFire uses (ARCFORMULA). The multi-target questions it answered earlier
#	are now handled by the SecondaryTarget module and the engine patch.
#	Key K selects a test, key O runs / aborts it; results are shown as banner
#	lines (and appended to a log file).
#	Delete the STProbe folder when the validation is over.
###############################################################################
import App
import sys
import string
import math

NAME = "STProbe"
VERSION = "0.2"
PKG = "Custom.Spaceframe.Modules.STProbe.STProbe"
KEY_HANDLER = PKG + ".OnKeyboard"
FIRED_HANDLER = PKG + ".OnWeaponFired"
TORP_HANDLER = PKG + ".OnTorpedoEntered"

TESTS = ("INFO", "MULTI_TORP", "FIRE_ONE", "TORP_RETARGET", "SINGLEFIRE_TORP",
	"ARCFORMULA", "ALL")

# What ALL runs, back to back (TORP_RETARGET needs the user).
ALL_TESTS = ("INFO", "SINGLEFIRE_TORP", "MULTI_TORP", "FIRE_ONE")

# Tests that are another test with a variation: name -> test whose phases run.
BASES = {"SINGLEFIRE_TORP": "SINGLEFIRE"}

LOG_FILE = "STProbe_log.txt"	# appended to in the game's working directory

HINT = {
	"ALL": "A ahead, B to the side; torps loaded; press o, wait 1 min; o aborts",
	"INFO": "no setup needed; prints weapon info. Press o",
	"MULTI_TORP": "A ahead, B to the side; torps loaded; Auto Fire off; press o",
	"FIRE_ONE": "torps (or pulse) ready; press o, wait 6 s",
	"TORP_RETARGET": "press o, then FIRE a torpedo at A within 20 s",
	"SINGLEFIRE_TORP": "SINGLEFIRE on torpedoes; torps loaded; A ahead, B aside; press o, wait 20 s",
	"ARCFORMULA": "pulse ship; optionally select a target; checks AutoFire's arc formula against IsInArc; press o",
}

# Weapon system kinds each test needs, in order of preference.
KINDS = {
	"INFO": (),
	"MULTI_TORP": ("torp",),
	"FIRE_ONE": ("torp", "pulse"),
	"TORP_RETARGET": (),
	"SINGLEFIRE_TORP": ("torp",),
	"ARCFORMULA": ("pulse",),
	"ALL": (),
}

MAX_LINES = 8	# rendered banner lines (long lines are wrapped, not cut)
MAX_WIDTH = 70
MAX_WEAPONS = 20
TIMEOUT = 20.0

g_pCore = None
g_pTopWindow = None	# window holding the keyboard handler
g_pMission = None	# object the broadcast handlers were registered on
g_iSel = 0		# index in TESTS of the selected test
g_dRun = None		# the running test, or None
g_dResults = {}		# test name -> result lines (survives battles)
g_iKeySel = 107
g_iKeyRun = 111
g_iAnyShip = 1
g_fSample = 2.0
g_fBanner = 8.0
g_sLogFile = LOG_FILE


###############################################################################
#	Config, logging, helpers
###############################################################################
def GetConfig():
	import Custom.Spaceframe.Modules.STProbe.Config
	return Custom.Spaceframe.Modules.STProbe.Config


def KeyCode(sKey, iDefault):
	sKey = str(sKey)
	if len(sKey) != 1:
		return iDefault
	iKey = ord(sKey)
	if (iKey >= 65) and (iKey <= 90):
		iKey = iKey + 32	# the game binds lower-case letters
	return iKey


def LoadConfig():
	global g_iKeySel, g_iKeyRun, g_iAnyShip, g_fSample, g_fBanner
	pConfig = GetConfig()
	g_iAnyShip = int(getattr(pConfig, "AnyShip", 1))
	g_iKeySel = KeyCode(getattr(pConfig, "SelectKey", "K"), 107)
	g_iKeyRun = KeyCode(getattr(pConfig, "RunKey", "O"), 111)
	g_fSample = float(getattr(pConfig, "SampleSeconds", 2.0))
	g_fBanner = float(getattr(pConfig, "BannerSeconds", 8.0))


def Log(sText):
	try:
		if g_pCore != None:
			g_pCore.Log(NAME, sText)
	except:
		pass


def ErrText():
	pType = sys.exc_info()[0]
	return str(getattr(pType, "__name__", pType)) + ": " + str(sys.exc_info()[1])


def Short(s, iMax):
	s = str(s)
	if len(s) > iMax:
		return s[:iMax]
	return s


def Call(sLabel, pFunc, tArgs):
	# (1, value) or (0, "ExcType: msg"); no engine error gets out of here.
	try:
		return (1, apply(pFunc, tArgs))
	except:
		return (0, ErrText())


def CallM(sLabel, pObj, sMethod, tArgs):
	# Like Call, but the method lookup is guarded too.
	try:
		pFunc = getattr(pObj, sMethod)
	except:
		return (0, ErrText())
	return Call(sLabel, pFunc, tArgs)


def AddError(dRun, sText):
	if dRun == None:
		return
	sText = Short(sText, 200)	# Show() cuts the banner; the log file gets all
	lErrors = dRun["errors"]
	if len(lErrors) >= 8:
		return
	for sOld in lErrors:
		if sOld == sText:
			return
	lErrors.append(sText)


def Do(dRun, pObj, sMethod, tArgs, pDefault):
	# Calls pObj.sMethod(*tArgs); on failure records the error, returns pDefault.
	tR = CallM(sMethod, pObj, sMethod, tArgs)
	if tR[0]:
		return tR[1]
	AddError(dRun, sMethod + " " + tR[1])
	return pDefault


def CastTo(sFunc, pObj):
	return getattr(App, sFunc)(pObj)


def Cast(dRun, sFunc, pObj):
	tR = Call(sFunc, CastTo, (sFunc, pObj))
	if tR[0]:
		return tR[1]
	AddError(dRun, sFunc + " " + tR[1])
	return None


def Now():
	try:
		return App.g_kUtopiaModule.GetGameTime()
	except:
		return 0.0


def WrapLine(sLine, iMax):
	# Splits a line at spaces into pieces of at most iMax characters (the
	# banner cuts anything longer); continuation pieces start with a space.
	sLine = str(sLine)
	lOut = []
	while len(sLine) > iMax:
		iCut = -1
		for i in range(1, iMax):
			if sLine[i] == " ":
				iCut = i
		if iCut <= 0:
			iCut = iMax
		lOut.append(sLine[:iCut])
		sLine = " " + string.strip(sLine[iCut:])
	lOut.append(sLine)
	return lOut


def WrapAll(lLines):
	# Wraps every line; when that gives more than MAX_LINES the middle goes
	# (the first lines and the last one, the log file line, stay).
	# The "restored:" line is kept too: it says whether the ship was put back.
	lOut = []
	lKeep = []
	for sLine in lLines:
		lPieces = WrapLine(sLine, MAX_WIDTH)
		bKeep = (string.find(str(sLine), "restored:") == 0)
		for sPiece in lPieces:
			lOut.append(sPiece)
			lKeep.append(bKeep)
	if len(lOut) > MAX_LINES:
		iLast = len(lOut) - 1
		iFree = MAX_LINES
		for i in range(len(lOut)):
			if lKeep[i] or i == iLast:
				iFree = iFree - 1
		lNew = []
		for i in range(len(lOut)):
			if lKeep[i] or i == iLast:
				lNew.append(lOut[i])
			elif iFree > 0:
				lNew.append(lOut[i])
				iFree = iFree - 1
		lOut = lNew
	return lOut


def Show(lLines):
	# Banner lines (at most MAX_LINES of MAX_WIDTH characters, long lines
	# wrapped); also logged (Debug = 1).
	i = 0
	for sLine in WrapAll(lLines):
		Log(sLine)
		try:
			import MissionLib
			MissionLib.TextBanner(None, App.TGString(sLine), 0.0, 0.12 + 0.035 * i, g_fBanner, 12, 1, 0)
		except:
			Log("TextBanner error: " + ErrText())
		i = i + 1


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


def Gone(pShip):
	# 1 for a ship that is missing, dead or dying (or cannot be asked).
	if pShip == None:
		return 1
	try:
		if pShip.IsDead() or pShip.IsDying():
			return 1
	except:
		return 1
	return 0


def IsLive(pShip):
	if Gone(pShip):
		return 0
	try:
		if pShip.IsCloaked():
			return 0
	except:
		pass
	return 1


def IsEnemy(pShip):
	try:
		return GetMission().GetEnemyGroup().IsNameInGroup(pShip.GetName())
	except:
		return 0


def GetEnemies(pShip):
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


def Distance(pFrom, pTo):
	try:
		vDiff = pTo.GetWorldLocation()
		vDiff.Subtract(pFrom.GetWorldLocation())
		return vDiff.Length()
	except:
		return 1.0e9


def Allowed(pShip):
	if pShip == None:
		return 0
	if g_iAnyShip:
		return 1
	try:
		return g_pCore.GetShipTech(pShip, NAME, 0) != 0
	except:
		return 0


def GetAB(pShip):
	# (A, B, reason): A = the player's target (an enemy), B = nearest other enemy.
	pA = None
	try:
		pA = App.ShipClass_Cast(pShip.GetTarget())
	except:
		pA = None
	if (not IsLive(pA)) or (not IsEnemy(pA)):
		return (None, None, "select an enemy target (A)")
	pB = None
	fBest = 0.0
	for pEnemy in GetEnemies(pShip):
		if pEnemy.GetObjID() != pA.GetObjID():
			fDist = Distance(pShip, pEnemy)
			if (pB == None) or (fDist < fBest):
				pB = pEnemy
				fBest = fDist
	if pB == None:
		return (None, None, "no second enemy (B)")
	return (pA, pB, "")


def NewZero(dRun):
	# A zero offset vector (made fresh each step, never kept).
	tR = Call("TGPoint3", NewZeroRaw, ())
	if tR[0]:
		return tR[1]
	AddError(dRun, "TGPoint3 " + tR[1])
	return None


def NewZeroRaw():
	vZero = App.TGPoint3()
	vZero.SetXYZ(0.0, 0.0, 0.0)
	return vZero


def StartArgs(pTarget, vZero):
	if vZero == None:
		return (pTarget,)
	return (pTarget, vZero)


###############################################################################
#	Weapon systems and weapons
###############################################################################
def KindOf(pSystem):
	# "phaser", "torp", "pulse" or "" for a weapon system.
	if pSystem == None:
		return ""
	lKinds = (("phaser", "PhaserSystem_Cast"), ("torp", "TorpedoSystem_Cast"), ("pulse", "PulseWeaponSystem_Cast"))
	for tKind in lKinds:
		tR = Call(tKind[1], CastTo, (tKind[1], pSystem))
		if tR[0] and (tR[1] != None):
			return tKind[0]
	return ""


def GroupList():
	return (App.ShipClass.WG_PRIMARY, App.ShipClass.WG_SECONDARY, App.ShipClass.WG_TERTIARY)


def FindSystem(dRun, pShip, sKind):
	# (group, system, kind) of the first group of that kind.
	# (None, None, "") when there is none.
	try:
		lGroups = GroupList()
	except:
		return (None, None, "")
	for eGroup in lGroups:
		pSystem = Do(dRun, pShip, "GetWeaponSystemGroup", (eGroup,), None)
		if pSystem != None:
			sFound = KindOf(pSystem)
			if sFound == sKind:
				return (eGroup, pSystem, sFound)
	return (None, None, "")


def GetSystem(dRun, pShip):
	return Do(dRun, pShip, "GetWeaponSystemGroup", (dRun["group"],), None)


def GetWeapons(dRun, pSystem):
	lWeapons = []
	iNum = Do(dRun, pSystem, "GetNumChildSubsystems", (), 0)
	if iNum > MAX_WEAPONS:
		iNum = MAX_WEAPONS
	for i in range(iNum):
		pChild = Do(dRun, pSystem, "GetChildSubsystem", (i,), None)
		lWeapons.append(Cast(dRun, "Weapon_Cast", pChild))
	return lWeapons


def ReachOne(pWeapon, sKind, pTarget, vZero):
	if sKind == "torp":
		return App.TorpedoTube_Cast(pWeapon).CanHit(pTarget.GetWorldLocation())
	return App.PulseWeapon_Cast(pWeapon).CanHitTarget(pTarget, vZero)


def Reach(dRun, pWeapon, sKind, pTarget, vZero):
	# 1 / 0, or "E" when the call failed.
	tR = Call("Reach", ReachOne, (pWeapon, sKind, pTarget, vZero))
	if not tR[0]:
		AddError(dRun, "Reach " + tR[1])
		return "E"
	if tR[1]:
		return 1
	return 0


def Code(iID, dRun):
	# "A" / "B" / "-" (no target) / "X" (somebody else).
	try:
		if (iID == None) or (iID == 0) or (iID == getattr(App, "NULL_ID", 0)):
			return "-"
		if iID == dRun["idA"]:
			return "A"
		if iID == dRun["idB"]:
			return "B"
	except:
		return "X"
	return "X"


def Bump(dD, i, sCode):
	if not dD.has_key(i):
		dD[i] = {}
	dD[i][sCode] = dD[i].get(sCode, 0) + 1


def Lookup(dRun):
	# (ship, A, B) fetched again by ID; None (after aborting the run) when
	# one of them is gone or the player changed ship.
	pShip = None
	try:
		pShip = App.ShipClass_GetObjectByID(None, dRun["ship"])
	except:
		pShip = None
	if Gone(pShip):
		Abort("ABORT: ship gone")
		return None
	pPlayer = GetPlayer()
	if (pPlayer == None) or (pPlayer.GetObjID() != dRun["ship"]):
		Abort("ABORT: player ship changed")
		return None
	lOthers = []
	for sKey in ("idA", "idB"):
		pOther = None
		try:
			pOther = App.ShipClass_GetObjectByID(None, dRun[sKey])
		except:
			pOther = None
		if Gone(pOther):
			Abort("ABORT: " + sKey[2:] + " gone")
			return None
		lOthers.append(pOther)
	return (pShip, lOthers[0], lOthers[1])


###############################################################################
#	Pure functions
###############################################################################
def SeenCount(dSeen, i, sCode):
	return dSeen.get(i, {}).get(sCode, 0)


def NumWeapons(dSeen, dReach):
	iNum = 0
	for i in dReach.keys():
		if i + 1 > iNum:
			iNum = i + 1
	for i in dSeen.keys():
		if i + 1 > iNum:
			iNum = i + 1
	return iNum


def Classify(dSeen, dReach, iSimul = 0):
	# dSeen[i] = {code: samples}, dReach[i] = (reaches A, reaches B).
	dC = {"onA": [], "onB": [], "simul": iSimul, "bothReach": [], "bothPickA": [],
		"bothPickB": [], "onlyA": [], "onlyB": [], "onlyBFired": []}
	for i in range(NumWeapons(dSeen, dReach)):
		tReach = dReach.get(i, (0, 0))
		bA = SeenCount(dSeen, i, "A") > 0
		bB = SeenCount(dSeen, i, "B") > 0
		if bA:
			dC["onA"].append(i)
		if bB:
			dC["onB"].append(i)
		if (tReach[0] == 1) and (tReach[1] == 1):
			dC["bothReach"].append(i)
			if bA:
				dC["bothPickA"].append(i)
			if bB:
				dC["bothPickB"].append(i)
		elif tReach[1] == 1:
			dC["onlyB"].append(i)
			if bB:
				dC["onlyBFired"].append(i)
		elif tReach[0] == 1:
			dC["onlyA"].append(i)
	return dC


def Verdict(dC):
	if dC["simul"]:
		return "PASS"
	if (len(dC["onlyA"]) == 0) and (len(dC["onlyB"]) == 0):
		return "INCONCLUSIVE geometry"
	return "FAIL"


def WeaponLine(dSeen, dReach):
	# "w0 r:AB f:A  w1 r:B f:B  w2 r:- f:-", over at most 2 lines. dReach[i] has
	# one entry (1 / 0 / "E") for A and one for B.
	sLetters = "AB"
	lParts = []
	for i in range(NumWeapons(dSeen, dReach)):
		tReach = dReach.get(i, (0, 0))
		sReach = ""
		bError = 0
		for n in range(len(sLetters)):
			if tReach[n] == 1:
				sReach = sReach + sLetters[n]
			if tReach[n] == "E":
				bError = 1
		if bError:
			sReach = sReach + "?"
		if sReach == "":
			sReach = "-"
		sFired = ""
		for sCode in ("A", "B", "X"):
			if SeenCount(dSeen, i, sCode) > 0:
				sFired = sFired + sCode
		if sFired == "":
			sFired = "-"
		lParts.append("w" + str(i) + " r:" + sReach + " f:" + sFired)
	if len(lParts) == 0:
		return []
	if len(lParts) <= 3:
		return [string.join(lParts, "  ")]
	iHalf = int((len(lParts) + 1) / 2)
	return [string.join(lParts[:iHalf], "  "), string.join(lParts[iHalf:], "  ")]


def MergeSeen(dSeen, dFired):
	dOut = {}
	for dSrc in (dSeen, dFired):
		for i in dSrc.keys():
			if not dOut.has_key(i):
				dOut[i] = {}
			for sCode in dSrc[i].keys():
				dOut[i][sCode] = dOut[i].get(sCode, 0) + dSrc[i][sCode]
	return dOut


###############################################################################
#	Keys and handlers
###############################################################################
def BindKey():
	global g_pTopWindow
	g_pTopWindow = App.TopWindow_GetTopWindow()
	g_pTopWindow.AddPythonFuncHandlerForInstance(App.ET_KEYBOARD, KEY_HANDLER)


def UnbindKey():
	global g_pTopWindow
	if g_pTopWindow != None:
		try:
			g_pTopWindow.RemoveHandlerForInstance(App.ET_KEYBOARD, KEY_HANDLER)
		except:
			pass
	g_pTopWindow = None


def OnKeyboard(pObject, pEvent):
	# Only lower-case k / o pressed on an allowed ship are consumed.
	iAct = 0
	try:
		iChar = pEvent.GetUnicode()
		if pEvent.GetKeyState() == App.TGKeyboardEvent.KS_KEYDOWN:
			if iChar == g_iKeySel:
				iAct = 1
			elif iChar == g_iKeyRun:
				iAct = 2
		if iAct and (not Allowed(GetPlayer())):
			iAct = 0
	except:
		iAct = 0
	if iAct == 0:
		pObject.CallNextHandler(pEvent)
		return
	pEvent.SetHandled()
	try:
		if iAct == 1:
			OnSelect()
		else:
			OnRun()
	except:
		Log("Key error: " + ErrText())


def OnSelect():
	global g_iSel
	if g_dRun != None:
		Abort("aborted")
		return
	g_iSel = (g_iSel + 1) % len(TESTS)
	sName = TESTS[g_iSel]
	lLines = ["STProbe " + str(g_iSel + 1) + "/" + str(len(TESTS)) + " " + sName, HINT[sName]]
	Show(lLines + g_dResults.get(sName, []))


def OnRun():
	if g_dRun != None:
		Abort("aborted")
		return
	Begin(TESTS[g_iSel])


def OnWeaponFired(pObject, pEvent):
	try:
		if g_dRun != None:
			RecordFired(g_dRun, pEvent)
	except:
		Log("Fired event error: " + ErrText())
	try:
		pObject.CallNextHandler(pEvent)
	except:
		pass


def RecordFired(dRun, pEvent):
	pWeapon = Cast(dRun, "Weapon_Cast", Do(dRun, pEvent, "GetSource", (), None))
	if pWeapon == None:
		return
	# Only this ship's weapons (unconfirmed call: if it fails, go by name).
	tParent = CallM("GetParentShip", pWeapon, "GetParentShip", ())
	if tParent[0] and (tParent[1] != None):
		tID = CallM("GetObjID", tParent[1], "GetObjID", ())
		if tID[0] and (tID[1] != dRun["ship"]):
			return
	sName = Do(dRun, pWeapon, "GetName", (), None)
	for i in range(len(dRun["names"])):
		if dRun["names"][i] == sName:
			Bump(dRun["fired"], i, Code(Do(dRun, pWeapon, "GetTargetID", (), None), dRun))
			return


def OnTorpedoEntered(pObject, pEvent):
	try:
		if (g_dRun != None) and (g_dRun["name"] == "TORP_RETARGET") and g_dRun["armed"]:
			Retarget(g_dRun, pEvent)
	except:
		Log("Torpedo event error: " + ErrText())
	try:
		pObject.CallNextHandler(pEvent)
	except:
		pass


def Retarget(dRun, pEvent):
	pTorp = Cast(dRun, "Torpedo_Cast", Do(dRun, pEvent, "GetDestination", (), None))
	if pTorp == None:
		return
	iParent = Do(dRun, pTorp, "GetParentID", (), None)
	iOld = Do(dRun, pTorp, "GetTargetID", (), None)
	sWho = "ship"
	if iParent != dRun["ship"]:
		if iOld != dRun["idA"]:
			return		# somebody else's torpedo
		sWho = "other(by target)"
	sOld = Code(iOld, dRun)
	tSet = CallM("SetTarget", pTorp, "SetTarget", (dRun["idB"],))
	if not tSet[0]:
		AddError(dRun, "SetTarget " + tSet[1])
	vZero = NewZero(dRun)
	if vZero != None:
		Do(dRun, pTorp, "SetTargetOffset", (vZero,), None)
	sNew = Code(Do(dRun, pTorp, "GetTargetID", (), None), dRun)
	sOk = "SetTarget ok"
	if not tSet[0]:
		sOk = "SetTarget FAILED"
	dRun["armed"] = 0
	dRun["lines"] = ["T10 torp parent=" + sWho + " tgt " + sOld + "->" + sNew + "  " + sOk,
		"watch: does it turn to B?"]
	dRun["phase"] = 2
	dRun["t"] = Now()


###############################################################################
#	Run engine
###############################################################################
def Precheck(sName):
	# (reason, ship, A, B, group, kind); reason "" = ready to run.
	pShip = GetPlayer()
	if Gone(pShip) or (not Allowed(pShip)):
		return ("no live player ship allowed", None, None, None, None, "")
	try:
		pAF = g_pCore.GetModule("AutoFire")
		if (pAF != None) and pAF.IsEnabled():
			return ("press L to turn Auto Fire off", None, None, None, None, "")
	except:
		pass
	try:
		if pShip.IsCloaked():
			return ("ship is cloaked", None, None, None, None, "")
	except:
		pass
	pA = None
	pB = None
	if (sName == "INFO") or (sName == "ARCFORMULA"):
		try:
			pTarget = App.ShipClass_Cast(pShip.GetTarget())
			if IsLive(pTarget):
				pA = pTarget
		except:
			pA = None
	else:
		tAB = GetAB(pShip)
		if tAB[2] != "":
			return (tAB[2], None, None, None, None, "")
		pA = tAB[0]
		pB = tAB[1]
	eGroup = None
	sKind = ""
	lKinds = KINDS[sName]
	if len(lKinds) > 0:
		for sWant in lKinds:
			if eGroup == None:
				tFound = FindSystem(None, pShip, sWant)
				if tFound[1] != None:
					eGroup = tFound[0]
					sKind = tFound[2]
		if eGroup == None:
			return ("no " + string.join(lKinds, "/") + " system on this ship", None, None, None, None, "")
	return ("", pShip, pA, pB, eGroup, sKind)


def NewRun(sName, tPre):
	# The run dict for a test, or None when the target ids cannot be read.
	pShip = tPre[1]
	dRun = {"name": sName, "phase": 0, "ship": pShip.GetObjID(), "idA": None, "idB": None,
		"group": tPre[4], "kind": tPre[5], "t": Now(), "seen": {}, "reach": {}, "fired": {},
		"errors": [], "started": 0, "simul": 0, "names": [], "sample": 0,
		"last": (0, 0, 0), "armed": 0, "lines": [], "w": None,
		"snaps": [], "orig": None, "chgProp": 0, "chgMode": 0, "restored": "ok", "rtext": "",
		"short": "", "drv": None, "maxl": 4, "base": sName, "vstate": ""}
	if BASES.has_key(sName):
		dRun["base"] = BASES[sName]
	try:
		dRun["idA"] = tPre[2].GetObjID()
		dRun["idB"] = tPre[3].GetObjID()
	except:
		return None
	return dRun


def Begin(sName):
	global g_dRun
	tPre = Precheck(sName)
	if tPre[0] != "":
		Show(["STProbe " + sName + ": NOT RUN - " + tPre[0]])
		return
	pShip = tPre[1]
	if sName == "INFO":
		RunInfo(pShip, tPre[2])
		return
	if sName == "ARCFORMULA":
		RunArc(pShip, tPre[2], tPre[4])
		return
	if sName == "ALL":
		StartAll()
		return
	dRun = NewRun(sName, tPre)
	if dRun == None:
		Show(["STProbe " + sName + ": NOT RUN - target ids"])
		return
	g_dRun = dRun
	try:
		RunPhase(dRun, pShip, tPre[2], tPre[3])
	except:
		Abort("error: " + ErrText())


def StartAll():
	dDrv = {"queue": list(ALL_TESTS), "done": []}
	Show(["STProbe ALL: running " + str(len(ALL_TESTS)) + " tests, o aborts"])
	try:
		Advance(dDrv)
	except:
		if g_dRun != None:
			Abort("error: " + ErrText())
		else:
			Show(["STProbe ALL error: " + ErrText()])


def Advance(dDrv):
	# Starts the next test of an ALL run (skipped ones are recorded at once);
	# when the queue is empty, reports. Called again by Finish of each test.
	global g_dRun
	lQueue = dDrv["queue"]
	while len(lQueue) > 0:
		sName = lQueue[0]
		del lQueue[0]
		tPre = Precheck(sName)
		if tPre[0] != "":
			dDrv["done"].append((sName, "SKIP", ["skipped: " + tPre[0]]))
		elif sName == "INFO":
			lLines = InfoLines(tPre[1], tPre[2])
			g_dResults["INFO"] = lLines
			dDrv["done"].append((sName, "ok", lLines))
		else:
			dRun = NewRun(sName, tPre)
			if dRun == None:
				dDrv["done"].append((sName, "SKIP", ["skipped: target ids"]))
			else:
				dRun["drv"] = dDrv
				g_dRun = dRun
				RunPhase(dRun, tPre[1], tPre[2], tPre[3])
				return
	FinishAll(dDrv)


def PackCompact(lItems):
	# Packs short items into banner lines of at most MAX_WIDTH characters.
	lOut = []
	sCur = ""
	for sItem in lItems:
		if sCur == "":
			sCur = sItem
		elif len(sCur) + 3 + len(sItem) <= MAX_WIDTH:
			sCur = sCur + " | " + sItem
		else:
			lOut.append(sCur)
			sCur = sItem
	if sCur != "":
		lOut.append(sCur)
	return lOut


def FinishAll(dDrv):
	lItems = []
	lFull = []
	for tDone in dDrv["done"]:
		lItems.append(tDone[0] + " " + tDone[1])
		lFull.append("== " + tDone[0] + " " + tDone[1] + " ==")
		lFull = lFull + tDone[2]
	lCompact = PackCompact(lItems)
	g_dResults["ALL"] = lCompact
	sLog = WriteLog("ALL", lCompact + lFull)
	Show(lCompact[:MAX_LINES - 1] + [sLog])


def WriteLog(sName, lLines):
	# Appends the lines (uncut) to the log file; returns the banner line.
	# This is also the check that a script can write files in game. Never raises.
	pFile = None
	iNum = 0
	try:
		pFile = open(g_sLogFile, "a")
		pFile.write("=== STProbe " + sName + " t=" + str(Now()) + " ===\n")
		for sLine in lLines:
			pFile.write(str(sLine) + "\n")
			iNum = iNum + 1
		pFile.close()
	except:
		sErr = ErrText()
		try:
			if pFile != None:
				pFile.close()
		except:
			pass
		return "log file: FAILED " + sErr
	return "log file: written (" + str(iNum) + " lines)"


def Step():
	dRun = g_dRun
	tShips = Lookup(dRun)
	if tShips == None:
		return
	if dRun["sample"]:
		Sample(dRun, tShips[0])
	if Now() >= dRun["t"]:
		RunPhase(dRun, tShips[0], tShips[1], tShips[2])


def Sample(dRun, pShip):
	# Which weapons fire now, and at whom (a handful of calls every 0.25 s,
	# only while a test runs).
	pSystem = GetSystem(dRun, pShip)
	if pSystem == None:
		return
	lWeapons = GetWeapons(dRun, pSystem)
	iA = 0
	iB = 0
	iFiring = 0
	for i in range(len(lWeapons)):
		pWeapon = lWeapons[i]
		if pWeapon != None:
			if Do(dRun, pWeapon, "IsFiring", (), 0):
				iFiring = iFiring + 1
				sCode = Code(Do(dRun, pWeapon, "GetTargetID", (), None), dRun)
				Bump(dRun["seen"], i, sCode)
				if sCode == "A":
					iA = iA + 1
				elif sCode == "B":
					iB = iB + 1
	dRun["last"] = (iA, iB, iFiring)
	if iA and iB:
		dRun["simul"] = 1


def Release(dRun):
	# Stops the system the probe started and puts back any fire setting it
	# changed, if the ship is still alive (the only place that touches ships
	# on the way out; Stop never does).
	if dRun == None:
		return
	bChanged = dRun["chgProp"] or dRun["chgMode"]
	if (not dRun["started"]) and (not bChanged):
		return
	bStarted = dRun["started"]
	dRun["started"] = 0
	pShip = None
	try:
		pShip = App.ShipClass_GetObjectByID(None, dRun["ship"])
	except:
		pShip = None
	if pShip == None:
		if bChanged:
			dRun["restored"] = "failed"
			dRun["rtext"] = "(ship gone)"
			dRun["chgProp"] = 0
			dRun["chgMode"] = 0
		return
	# A dying or dead ship that still exists is restored anyway: the single-fire
	# property may be shared by every ship of the class.
	pSystem = None
	try:
		pSystem = GetSystem(dRun, pShip)
	except:
		pSystem = None
	if pSystem != None:
		try:
			if bStarted:
				Do(dRun, pSystem, "StopFiring", (), None)
			if bChanged:
				RestoreState(dRun, pSystem)
		except:
			AddError(dRun, "release " + ErrText())
			if bChanged and dRun["restored"] == "ok" and dRun["rtext"] == "":
				dRun["restored"] = "failed"
				dRun["rtext"] = "(release error)"
	elif bChanged:
		dRun["restored"] = "failed"
		dRun["rtext"] = "(system gone)"
		dRun["chgProp"] = 0
		dRun["chgMode"] = 0


def RestoreLine(dRun):
	if dRun["restored"] == "ok":
		return "restored: ok " + StateText(dRun["orig"])
	return "restored: failed " + dRun["rtext"] + " want " + StateText(dRun["orig"])


def Abort(sWhy):
	global g_dRun
	dRun = g_dRun
	if dRun == None:
		return
	try:
		Release(dRun)
	except:
		pass
	g_dRun = None
	if string.find(sWhy, "ABORT") < 0:
		sWhy = "ABORT: " + sWhy
	lLines = ["STProbe " + dRun["name"] + " " + sWhy]
	if dRun["orig"] != None:
		lLines.append(RestoreLine(dRun))
	Show(lLines)


def ShortOf(dRun):
	sShort = dRun["short"]
	if sShort == "":
		sShort = "done"
	if len(dRun["errors"]) > 0:
		sShort = sShort + "!"
	return sShort


def Finish(lLines):
	global g_dRun
	dRun = g_dRun
	if dRun == None:
		return
	try:
		Release(dRun)
	except:
		pass
	lOut = lLines[:dRun["maxl"]]
	lFull = lLines[:]
	if dRun["orig"] != None:
		# Right after the first line, so cutting the banner never drops it.
		lOut = lOut[:1] + [RestoreLine(dRun)] + lOut[1:]
		lFull.append(RestoreLine(dRun))
	for sError in dRun["errors"]:
		lFull.append("ERR " + sError)
	for sError in dRun["errors"][:2]:
		lOut.append("ERR " + sError)
	g_dResults[dRun["name"]] = lOut
	g_dRun = None
	if dRun["drv"] != None:
		dRun["drv"]["done"].append((dRun["name"], ShortOf(dRun), lFull))
		Advance(dRun["drv"])
		return
	sLog = WriteLog(dRun["name"], lFull)
	Show(lOut[:MAX_LINES - 1] + [sLog])


def RunPhase(dRun, pShip, pA, pB):
	vZero = NewZero(dRun)
	sName = dRun["base"]
	if sName == "MULTI_TORP":
		PhaseMulti(dRun, pShip, pA, pB, vZero)
	elif sName == "FIRE_ONE":
		PhaseFire(dRun, pShip, pA, pB, vZero)
	elif sName == "TORP_RETARGET":
		PhaseRetarget(dRun)
	elif sName == "SINGLEFIRE":
		PhaseSingle(dRun, pShip, pA, pB, vZero)


def Multi(dRun, pShip, lTargets, vZero):
	# StopFiring, StartFiring once per target (in order), force update.
	# Returns (A in list, B in list) as strings; None when the system is gone.
	pSystem = GetSystem(dRun, pShip)
	if pSystem == None:
		Abort("ABORT: weapon system gone")
		return None
	Do(dRun, pSystem, "StopFiring", (), None)
	for pTarget in lTargets:
		Do(dRun, pSystem, "StartFiring", StartArgs(pTarget, vZero), None)
	Do(dRun, pSystem, "SetForceUpdate", (1,), None)
	dRun["started"] = 1
	return (InList(dRun, pSystem, lTargets[0]), InList(dRun, pSystem, lTargets[1]))


def InList(dRun, pSystem, pTarget):
	return str(Do(dRun, pSystem, "IsInTargetList", (pTarget,), "E"))


def CacheWeapons(dRun, pShip, pA, pB, vZero):
	pSystem = GetSystem(dRun, pShip)
	if pSystem == None:
		return
	lWeapons = GetWeapons(dRun, pSystem)
	dRun["names"] = []
	for i in range(len(lWeapons)):
		pWeapon = lWeapons[i]
		dRun["names"].append(Do(dRun, pWeapon, "GetName", (), "w" + str(i)))
		if pWeapon == None:
			dRun["reach"][i] = ("E", "E")
		else:
			dRun["reach"][i] = (Reach(dRun, pWeapon, dRun["kind"], pA, vZero), Reach(dRun, pWeapon, dRun["kind"], pB, vZero))


###############################################################################
#	Tests (each function handles every phase of its test)
###############################################################################
def PhaseMulti(dRun, pShip, pA, pB, vZero):
	if dRun["phase"] == 0:
		CacheWeapons(dRun, pShip, pA, pB, vZero)
		tIn = Multi(dRun, pShip, [pA, pB], vZero)
		if tIn == None:
			return
		dRun["in"] = tIn
		pSystem = GetSystem(dRun, pShip)
		if pSystem != None:
			dRun["ready"] = Do(dRun, Cast(dRun, "TorpedoSystem_Cast", pSystem), "GetNumReady", (), "?")
		fWindow = g_fSample
		if fWindow < 4.0:
			fWindow = 4.0
		dRun["t"] = Now() + fWindow
		dRun["phase"] = 1
		dRun["sample"] = 1
		return
	dSeen = MergeSeen(dRun["seen"], dRun["fired"])
	dC = Classify(dSeen, dRun["reach"], dRun["simul"])
	dRun["short"] = FirstWord(Verdict(dC))
	lLines = []
	sPick = "both-reach picked A:" + str(len(dC["bothPickA"])) + " B:" + str(len(dC["bothPickB"]))
	sHead = "T3 " + string.upper(dRun["kind"]) + " " + Verdict(dC) + " list A:" + dRun["in"][0] + " B:" + dRun["in"][1]
	sHead = sHead + " onA:" + str(len(dC["onA"])) + " onB:" + str(len(dC["onB"])) + " simul:" + str(dC["simul"])
	sHead = sHead + " rdy:" + str(dRun.get("ready", "?"))
	lLines.append(sHead)
	lLines.append(sPick + "  onlyB fired:" + str(len(dC["onlyBFired"])) + "/" + str(len(dC["onlyB"])))
	lLines = lLines + WeaponLine(dSeen, dRun["reach"])
	Finish(lLines)


def FirstWord(s):
	i = string.find(s, " ")
	if i >= 0:
		return s[:i]
	return s


def GetProp(dRun, pSystem):
	# The system's WeaponSystemProperty (cast unconfirmed: falls back to the
	# raw property object). Looked up fresh at every use.
	pRaw = Do(dRun, pSystem, "GetProperty", (), None)
	if pRaw == None:
		return None
	pProp = Cast(dRun, "WeaponSystemProperty_Cast", pRaw)
	if pProp != None:
		return pProp
	return pRaw


def ReadState(dRun, pSystem):
	# (system IsSingleFire, GetGroupFireMode, property IsSingleFire); "?" = unreadable.
	pProp = GetProp(dRun, pSystem)
	iProp = "?"
	if pProp != None:
		iProp = Do(dRun, pProp, "IsSingleFire", (), "?")
	return (Do(dRun, pSystem, "IsSingleFire", (), "?"), Do(dRun, pSystem, "GetGroupFireMode", (), "?"), iProp)


def StateText(tState):
	return "[s" + str(tState[0]) + " m" + str(tState[1]) + " p" + str(tState[2]) + "]"


def VariantList(tOrig):
	# (label, what, value): baseline, property single-fire off, other group modes.
	lVars = [("base", "none", 0), ("prop0", "prop", 0)]
	for iMode in (0, 1, 2):
		if iMode != tOrig[1]:
			lVars.append(("mode" + str(iMode), "mode", iMode))
	return lVars


def ApplyVariant(dRun, pSystem, tVar):
	# The change flags are set first, so an abort half way still restores.
	if tVar[1] == "prop":
		dRun["chgProp"] = 1
		pProp = GetProp(dRun, pSystem)
		if pProp != None:
			Do(dRun, pProp, "SetSingleFire", (tVar[2],), None)
	elif tVar[1] == "mode":
		dRun["chgMode"] = 1
		Do(dRun, pSystem, "SetGroupFireMode", (tVar[2],), None)


def RestoreState(dRun, pSystem):
	# Puts back what the variant changed, reads the state back, notes a mismatch.
	tOrig = dRun["orig"]
	if dRun["chgProp"] and (tOrig[2] != "?"):
		pProp = GetProp(dRun, pSystem)
		if pProp != None:
			Do(dRun, pProp, "SetSingleFire", (tOrig[2],), None)
	if dRun["chgMode"] and (tOrig[1] != "?"):
		Do(dRun, pSystem, "SetGroupFireMode", (tOrig[1],), None)
	dRun["chgProp"] = 0
	dRun["chgMode"] = 0
	tNow = ReadState(dRun, pSystem)
	if tNow != tOrig:
		dRun["restored"] = "failed"
		dRun["rtext"] = StateText(tNow)


def StartVariant(dRun, pShip, pA, pB, vZero, pSystem):
	dRun["seen"] = {}
	dRun["fired"] = {}
	dRun["simul"] = 0
	dRun["last"] = (0, 0, 0)
	dRun["nerr"] = len(dRun["errors"])
	ApplyVariant(dRun, pSystem, dRun["variants"][dRun["var"]])
	dRun["vstate"] = StateText(ReadState(dRun, pSystem))
	if Multi(dRun, pShip, [pA, pB], vZero) == None:
		return
	fWindow = g_fSample
	if fWindow < 4.0:
		fWindow = 4.0
	dRun["t"] = Now() + fWindow
	dRun["phase"] = 1
	dRun["sample"] = 1


def PhaseSingle(dRun, pShip, pA, pB, vZero):
	# MULTI measurement repeated with single-fire / group-mode changes, each undone.
	pSystem = GetSystem(dRun, pShip)
	if pSystem == None:
		Abort("ABORT: weapon system gone")
		return
	if dRun["phase"] == 0:
		dRun["orig"] = ReadState(dRun, pSystem)
		dRun["variants"] = VariantList(dRun["orig"])
		dRun["var"] = 0
		dRun["res"] = []
		dRun["vshort"] = []
		dRun["maxl"] = 5
		CacheWeapons(dRun, pShip, pA, pB, vZero)
		StartVariant(dRun, pShip, pA, pB, vZero, pSystem)
		return
	tVar = dRun["variants"][dRun["var"]]
	dSeen = MergeSeen(dRun["seen"], dRun["fired"])
	dC = Classify(dSeen, dRun["reach"], dRun["simul"])
	sVerdict = Verdict(dC)
	sLine = tVar[0] + " " + dRun["vstate"] + " " + sVerdict + " simul:" + str(dC["simul"])
	sLine = sLine + " onA:" + str(len(dC["onA"])) + " onB:" + str(len(dC["onB"]))
	if len(dRun["errors"]) > dRun["nerr"]:
		sLine = sLine + " ERR " + dRun["errors"][-1]
	dRun["res"].append(sLine)
	dRun["vshort"].append(tVar[0] + ":" + sVerdict[:1])
	Release(dRun)
	dRun["var"] = dRun["var"] + 1
	if dRun["var"] < len(dRun["variants"]):
		StartVariant(dRun, pShip, pA, pB, vZero, pSystem)
		return
	dRun["short"] = dRun["kind"] + " " + string.join(dRun["vshort"], " ")
	Finish(dRun["res"])


def ReadyWeapon(dRun, pSystem, iAfter):
	# Index of the first weapon ready to fire (after index iAfter), or None.
	lWeapons = GetWeapons(dRun, pSystem)
	for i in range(len(lWeapons)):
		pWeapon = lWeapons[i]
		if (i > iAfter) and (pWeapon != None):
			if dRun["kind"] == "torp":
				if Do(dRun, Cast(dRun, "TorpedoTube_Cast", pWeapon), "GetNumReady", (), 0) > 0:
					return i
			else:
				pPulse = Cast(dRun, "PulseWeapon_Cast", pWeapon)
				if pPulse != None:
					if Do(dRun, pPulse, "GetChargeLevel", (), 0.0) >= Do(dRun, pPulse, "GetMinFiringCharge", (), 0.0):
						return i
	return None


def FireWeapon(dRun, pSystem, iIndex, sMethod):
	# Fires weapon iIndex; returns "ret=..".
	lWeapons = GetWeapons(dRun, pSystem)
	pWeapon = lWeapons[iIndex]
	dRun["names"] = []
	for i in range(len(lWeapons)):
		dRun["names"].append(Do(dRun, lWeapons[i], "GetName", (), "w" + str(i)))
	dRun["fired"] = {}
	tR = CallM(sMethod, pWeapon, sMethod, (0.0, 1))
	if not tR[0]:
		AddError(dRun, sMethod + " " + tR[1])
		return "ret=ERR"
	return "ret=" + str(tR[1])


def FireResult(dRun, pSystem, iIndex, sRet, sTitle):
	iFired = 0
	for sCode in dRun["fired"].get(iIndex, {}).keys():
		iFired = iFired + dRun["fired"][iIndex][sCode]
	lWeapons = GetWeapons(dRun, pSystem)
	sTgt = Code(Do(dRun, lWeapons[iIndex], "GetTargetID", (), None), dRun)
	return sTitle + ": " + sRet + " fired=" + str(iFired) + " tgt=" + sTgt


def PhaseFire(dRun, pShip, pA, pB, vZero):
	iPhase = dRun["phase"]
	pSystem = GetSystem(dRun, pShip)
	if pSystem == None:
		Abort("ABORT: weapon system gone")
		return
	if iPhase == 0:
		Do(dRun, pSystem, "StopFiring", (), None)
		Do(dRun, pSystem, "ClearTargetList", (), None)
		dRun["started"] = 1
		sMethod = "Fire"
	elif iPhase == 1:
		dRun["snaps"].append(FireResult(dRun, pSystem, dRun["w"], dRun["ret"], "Fire no-list"))
		Do(dRun, pSystem, "StartFiring", StartArgs(pA, vZero), None)
		Do(dRun, pSystem, "SetForceUpdate", (1,), None)
		sMethod = "Fire"
	elif iPhase == 2:
		dRun["snaps"].append(FireResult(dRun, pSystem, dRun["w"], dRun["ret"], "Fire list A"))
		sMethod = "FireDumb"
	else:
		dRun["snaps"].append(FireResult(dRun, pSystem, dRun["w"], dRun["ret"], "FireDumb"))
		Finish(dRun["snaps"])
		return
	iAfter = -1
	if iPhase >= 1:
		iAfter = dRun["w"]
	iIndex = ReadyWeapon(dRun, pSystem, iAfter)
	if (iIndex == None) and (iPhase >= 1):
		iIndex = ReadyWeapon(dRun, pSystem, -1)
	if iIndex == None:
		dRun["snaps"].append("no ready weapon for step " + str(iPhase + 1))
		Finish(dRun["snaps"])
		return
	dRun["w"] = iIndex
	dRun["ret"] = FireWeapon(dRun, pSystem, iIndex, sMethod)
	dRun["t"] = Now() + 2.0
	dRun["phase"] = iPhase + 1


def PhaseRetarget(dRun):
	iPhase = dRun["phase"]
	if iPhase == 0:
		dRun["armed"] = 1
		dRun["t"] = Now() + TIMEOUT
		dRun["phase"] = 1
		Show(["FIRE a torpedo at A now (20 s)"])
	elif iPhase == 1:
		dRun["armed"] = 0
		Finish(["T10 TORP_RETARGET: no torpedo seen"])
	else:
		Finish(dRun["lines"])


def RunInfo(pShip, pA):
	# INFO: no firing, only questions; shown at once.
	lLines = InfoLines(pShip, pA)
	g_dResults["INFO"] = lLines
	sLog = WriteLog("INFO", lLines)
	Show(lLines[:MAX_LINES - 1] + [sLog])


def InfoLines(pShip, pA):
	dTmp = {"errors": [], "idA": None, "idB": None}
	vZero = NewZero(dTmp)
	lLines = []
	lPulse = None
	lTubes = None
	try:
		lGroups = GroupList()
	except:
		lGroups = ()
	i = 0
	for eGroup in lGroups:
		pSystem = Do(dTmp, pShip, "GetWeaponSystemGroup", (eGroup,), None)
		if pSystem != None:
			sKind = KindOf(pSystem)
			lWeapons = GetWeapons(dTmp, pSystem)
			sLine = "G" + str(i) + " " + sKind + " n=" + str(len(lWeapons))
			sLine = sLine + " mode=" + str(Do(dTmp, pSystem, "GetGroupFireMode", (), "?"))
			sLine = sLine + " single=" + str(Do(dTmp, pSystem, "IsSingleFire", (), "?"))
			if (len(lWeapons) > 0) and (lWeapons[0] != None):
				sLine = sLine + " w0 tgt=" + str(Do(dTmp, lWeapons[0], "GetTargetID", (), "?")) + " fire=" + str(Do(dTmp, lWeapons[0], "IsFiring", (), "?"))
				if (sKind == "pulse") and (lPulse == None):
					lPulse = lWeapons
				if (sKind == "torp") and (lTubes == None):
					lTubes = lWeapons
			lLines.append(sLine)
		i = i + 1
	if pA != None:
		vLoc = Do(dTmp, pA, "GetWorldLocation", (), None)
		if lTubes != None:
			lLines.append(ReachLine(dTmp, "torp", lTubes, "TorpedoTube_Cast", (
				("CanHit(pt)", "CanHit", (vLoc,)),
				("CanHit(ship)", "CanHit", (pA,)))))
		if lPulse != None:
			lLines.append(ReachLine(dTmp, "pulse", lPulse, "PulseWeapon_Cast", (
				("CHT(pt,v)", "CanHitTarget", (vLoc, vZero)),
				("CHT(ship)", "CanHitTarget", (pA,)),
				("CHT(ship,v)", "CanHitTarget", (pA, vZero)))))
	else:
		if (lTubes != None) or (lPulse != None):
			lLines.append("torp/pulse reach: select an enemy target (A) first")
	if Do(dTmp, pShip, "GetAI", (), None) != None:
		lLines.append("WARNING ship has AI (tactical orders?)")
	if len(dTmp["errors"]) > 0:
		lLines.append("ERR " + dTmp["errors"][0])
	return lLines


def ReachLine(dTmp, sKind, lWeapons, sCast, lForms):
	# "torp reach A: CanHit(pt) w0=1 w1=0 | CanHit(ship) E:TypeError ..." - for
	# every call form, what each weapon answers for the target A (or the error).
	lParts = []
	for tForm in lForms:
		lRes = []
		lErr = []
		for i in range(len(lWeapons)):
			pWeapon = None
			if lWeapons[i] != None:
				pWeapon = Cast(dTmp, sCast, lWeapons[i])
			if pWeapon == None:
				lRes.append("w" + str(i) + "=E")
				continue
			tR = CallM(tForm[0], pWeapon, tForm[1], tForm[2])
			if tR[0]:
				lRes.append("w" + str(i) + "=" + str(tR[1]))
			else:
				lRes.append("w" + str(i) + "=E")
				lErr.append(tR[1])
		sPart = tForm[0] + " " + string.join(lRes, " ")
		if len(lErr) > 0:
			sPart = sPart + " [" + Short(lErr[0], 30) + "]"
		lParts.append(sPart)
	return sKind + " reach A: " + string.join(lParts, " | ")


###############################################################################
#	ARCFORMULA: does AutoFire's pulse arc formula (Solution.ArcDepth) agree
#	with the game's own PulseWeapon.IsInArc? No firing, answered at once.
###############################################################################
def GetArcSolution():
	import Custom.Spaceframe.Modules.AutoFire.Solution
	return Custom.Spaceframe.Modules.AutoFire.Solution


def ArcDistance():
	# 5 km in world units.
	try:
		return App.g_kUtopiaModule.ConvertKilometersToGameUnits(5.0)
	except:
		return 5.0 / 0.175


def ArcPoint(S, pShip, pWeapon, sMode, tAxes, fForward, fRight, fUp, fDist):
	# The world point at distance fDist from the weapon (as candidate sMode
	# places it) along D = fForward * Fwd + fRight * Right + fUp * Up.
	vD = S.NewPoint(tAxes[0])
	vD.Scale(fForward)
	vR = S.NewPoint(tAxes[1])
	vR.Scale(fRight)
	vD.Add(vR)
	vU = S.NewPoint(tAxes[2])
	vU.Scale(fUp)
	vD.Add(vU)
	fLen = vD.Length()
	if fLen <= 0.0:
		fLen = 1.0
	vD.Scale(fDist / fLen)
	vPoint = S.WeaponPosition(pShip, pWeapon, sMode)
	vPoint.Add(vD)
	return vPoint


def ArcSpecs(tLim):
	# (label, forward, right, up) of the probe points: just inside and just
	# outside every limit, the centre, a corner, behind, and df = 0.
	fWm = (tLim[0] + tLim[1]) / 2.0
	fHm = (tLim[2] + tLim[3]) / 2.0
	lAngles = (("w-in", tLim[0] + 0.02, fHm), ("w+in", tLim[1] - 0.02, fHm),
		("w-out", tLim[0] - 0.02, fHm), ("w+out", tLim[1] + 0.02, fHm),
		("h-in", fWm, tLim[2] + 0.02), ("h+in", fWm, tLim[3] - 0.02),
		("h-out", fWm, tLim[2] - 0.02), ("h+out", fWm, tLim[3] + 0.02),
		("mid", fWm, fHm), ("corner", tLim[0] + 0.02, tLim[2] + 0.02))
	lSpecs = []
	for tA in lAngles:
		if (abs(tA[1]) < 1.5) and (abs(tA[2]) < 1.5):
			lSpecs.append((tA[0], 1.0, math.tan(tA[1]), math.tan(tA[2])))
	lSpecs.append(("behind", -1.0, 0.0, 0.0))
	lSpecs.append(("df0", 0.0, 1.0, 0.0))
	return lSpecs


def ArcDeg(f):
	return "%.0f" % (f * 180.0 / App.PI)


def ArcNum(f):
	if f == None:
		return "E"
	if f >= 99.0:
		return "behind"
	return "%.2f" % f


def ArcWeaponLine(S, dTmp, pShip, pWeapon, i, pA):
	tLim = S.ArcLimits(pWeapon)
	tAxes = S.ArcAxes(pShip, pWeapon)
	fDist = ArcDistance()
	lSpecs = ArcSpecs(tLim)
	lParts = []
	lMiss = []
	for sMode in ("A", "B"):
		iMatch = 0
		for n in range(len(lSpecs)):
			tSpec = lSpecs[n]
			fDepth = None
			iGame = None
			try:
				# The points of this candidate: ours and the game's answer for each.
				vPoint = ArcPoint(S, pShip, pWeapon, sMode, tAxes, tSpec[1], tSpec[2], tSpec[3], fDist)
				fDepth = S.ArcDepth(pShip, pWeapon, vPoint, sMode)
				tR = CallM("IsInArc", pWeapon, "IsInArc", (vPoint,))
				if tR[0]:
					iGame = int(tR[1] != 0)
				else:
					AddError(dTmp, "IsInArc " + tR[1])
			except:
				AddError(dTmp, "ArcDepth " + ErrText())
			if (fDepth != None) and (iGame != None) and (int(fDepth <= 1.0) == iGame):
				iMatch = iMatch + 1
			else:
				lMiss.append(sMode + ":" + tSpec[0] + "=" + ArcNum(fDepth) + "/" + str(iGame))
		lParts.append("cand" + sMode + ": " + str(iMatch) + "/" + str(len(lSpecs)) + " match")
	sLine = "w" + str(i) + " " + string.join(lParts, ", ") + ", W[" + ArcDeg(tLim[0]) + "," + ArcDeg(tLim[1]) + "] H[" + ArcDeg(tLim[2]) + "," + ArcDeg(tLim[3]) + "]deg"
	if pA != None:
		vLoc = Do(dTmp, pA, "GetWorldLocation", (), None)
		if vLoc != None:
			sLine = sLine + ", tgt depth A=" + ArcNum(S.ArcDepth(pShip, pWeapon, vLoc, "A")) + " B=" + ArcNum(S.ArcDepth(pShip, pWeapon, vLoc, "B"))
	if len(lMiss) > 0:
		sLine = sLine + " | miss(ours/game) " + string.join(lMiss[:6], " ")
	return sLine


def ArcLines(pShip, pA, eGroup):
	try:
		S = GetArcSolution()
	except:
		return ["ARCFORMULA: AutoFire.Solution not importable: " + ErrText()]
	dTmp = {"errors": [], "idA": None, "idB": None}
	pSystem = Do(dTmp, pShip, "GetWeaponSystemGroup", (eGroup,), None)
	lLines = ["ARCFORMULA pulse arc, 12 points at 5 km, default weapon position " + str(S.WEAPON_POSITION)]
	if pA == None:
		lLines.append("no target selected: only the points are checked")
	lWeapons = GetWeapons(dTmp, pSystem)
	for i in range(len(lWeapons)):
		pWeapon = None
		if lWeapons[i] != None:
			pWeapon = Cast(dTmp, "PulseWeapon_Cast", lWeapons[i])
		if pWeapon == None:
			lLines.append("w" + str(i) + " E: not a PulseWeapon")
		else:
			try:
				lLines.append(ArcWeaponLine(S, dTmp, pShip, pWeapon, i, pA))
			except:
				lLines.append("w" + str(i) + " ERR " + Short(ErrText(), 60))
	for sError in dTmp["errors"][:2]:
		lLines.append("ERR " + Short(sError, 60))
	return lLines


def RunArc(pShip, pA, eGroup):
	lLines = ArcLines(pShip, pA, eGroup)
	g_dResults["ARCFORMULA"] = lLines
	sLog = WriteLog("ARCFORMULA", lLines)
	Show(lLines[:MAX_LINES - 1] + [sLog])


###############################################################################
#	Lifecycle
###############################################################################
def GetHandlerEvents():
	# (event type, handler) pairs registered on the mission.
	lEvents = []
	for tEntry in (("ET_WEAPON_FIRED", FIRED_HANDLER), ("ET_TORPEDO_ENTERED_SET", TORP_HANDLER)):
		eType = getattr(App, tEntry[0], None)
		if eType != None:
			lEvents.append((eType, tEntry[1]))
	return lEvents


def Start(pCore):
	global g_pCore, g_pMission
	Stop()
	g_pCore = pCore
	try:
		import Custom.Spaceframe.Modules.STProbe.Config
		reload(Custom.Spaceframe.Modules.STProbe.Config)
		LoadConfig()
	except:
		Log("Config error: " + ErrText())
	try:
		BindKey()
	except:
		Log("Could not bind the keys: " + ErrText())
	g_pMission = GetMission()
	if g_pMission != None:
		for tEntry in GetHandlerEvents():
			try:
				App.g_kEventManager.AddBroadcastPythonFuncHandler(tEntry[0], g_pMission, tEntry[1])
			except:
				Log("Could not register a handler: " + ErrText())


def Stop():
	# Battle end: the ships are being destroyed, so nothing is asked of them.
	global g_dRun, g_pMission
	g_dRun = None
	if g_pMission != None:
		for tEntry in GetHandlerEvents():
			try:
				App.g_kEventManager.RemoveBroadcastHandler(tEntry[0], g_pMission, tEntry[1])
			except:
				pass
	g_pMission = None
	UnbindKey()


def Tick(lShips):
	if g_dRun == None:
		return
	try:
		Step()
	except:
		Abort("error: " + ErrText())
