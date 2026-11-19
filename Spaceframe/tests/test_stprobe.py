"""STProbe tests (throwaway probe module): lifecycle, keys, run engine, pure functions."""
import builtins
import os
import string
import sys
import types
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mock_app

builtins.reload = lambda m: m
builtins.apply = lambda f, a: f(*a)
# The Python 1.5 string functions the module uses.
string.join = lambda l, sep=" ": sep.join(l)
string.upper = lambda s: s.upper()
string.find = lambda s, sub: s.find(sub)
string.split = lambda s, sep=None: s.split(sep)
string.strip = lambda s: s.strip()

CLOCK = [0.0]
CALLS = []	# every call made into the fake ships and weapons
BANNERS = []	# every banner line shown


class FakeWeapon:
	def __init__(self, sName, sKind, tReach=(1, 1)):
		self.sName = sName
		self.kind = sKind
		self.reach = {10.0: tReach[0], 20.0: tReach[1], 30.0: 0}	# by target x position
		if len(tReach) > 2:
			self.reach[30.0] = tReach[2]
		self.firing = 0
		self.tgt = 0
		self.raise_tgt = 0
		self.ready = 1
		self.parent = None

	def IsFiring(self):
		return self.firing

	def GetTargetID(self):
		if self.raise_tgt:
			raise RuntimeError("GetTargetID broke")
		return self.tgt

	def GetName(self):
		return self.sName

	def StopFiring(self):
		CALLS.append(("w.StopFiring", self.sName))
		self.firing = 0

	def Fire(self, f, i):
		CALLS.append(("w.Fire", self.sName))
		return 1

	def FireDumb(self, f, i):
		CALLS.append(("w.FireDumb", self.sName))
		return 1

	def CanHit(self, pLoc):
		return self.reach[pLoc.x]

	def CanHitTarget(self, pTarget, vOffset):
		# The real call takes a world point (confirmed); a ship is accepted too.
		if hasattr(pTarget, "GetWorldLocation"):
			return self.reach[pTarget.GetWorldLocation().x]
		return self.reach[pTarget.x]

	def GetNumReady(self):
		return self.ready

	def GetChargeLevel(self):
		return 5.0

	def GetMinFiringCharge(self):
		return 2.0

	def GetParentShip(self):
		return self.parent


class FakeProp:
	def __init__(self):
		self.single = 0

	def IsSingleFire(self):
		return self.single

	def SetSingleFire(self, i):
		CALLS.append(("p.SetSingleFire", i))
		self.single = i


class FakeSystem:
	def __init__(self, sKind, lWeapons):
		self.kind = sKind
		self.weapons = lWeapons
		self.targets = []
		self.log = []
		self.assign = []	# per weapon: target ID to fire at on force update, or None
		self.mode = 1
		self.prop = FakeProp()
		self.reject_modes = []	# group modes SetGroupFireMode silently ignores
		self.policy = None	# optional callable(system) choosing self.assign on force update

	def StartFiring(self, pTarget=None, vOffset=None):
		CALLS.append(("s.StartFiring",))
		self.log.append(("start", pTarget.GetObjID()))
		if pTarget not in self.targets:
			self.targets.append(pTarget)

	def StopFiring(self):
		CALLS.append(("s.StopFiring",))
		self.log.append(("stop",))
		self.targets = []
		for w in self.weapons:
			w.firing = 0

	def ClearTargetList(self):
		self.log.append(("clear",))
		self.targets = []

	def IsInTargetList(self, pTarget):
		return int(pTarget in self.targets)

	def SetForceUpdate(self, i):
		self.log.append(("force", i))
		if self.policy != None:
			self.policy(self)
		for n in range(len(self.assign)):
			if self.assign[n] != None:
				self.weapons[n].firing = 1
				self.weapons[n].tgt = self.assign[n]

	def GetGroupFireMode(self):
		return self.mode

	def SetGroupFireMode(self, i):
		CALLS.append(("s.SetGroupFireMode", i))
		if i in self.reject_modes:
			return
		self.mode = i

	def IsSingleFire(self):
		return self.prop.single

	def GetProperty(self):
		return self.prop

	def GetNumChildSubsystems(self):
		return len(self.weapons)

	def GetChildSubsystem(self, i):
		return self.weapons[i]

	def GetNumReady(self):
		return len(self.weapons)


class RecShip(mock_app.Ship):
	def GetWeaponSystemGroup(self, e):
		CALLS.append(("ship.GetWeaponSystemGroup", e))
		return self.groups.get(e)


class FakeEvent:
	def __init__(self, pSource=None, pDest=None):
		self.pSource = pSource
		self.pDest = pDest

	def GetSource(self):
		return self.pSource

	def GetDestination(self):
		return self.pDest


class FakeTorp:
	def __init__(self, iParent, iTarget):
		self.iParent = iParent
		self.iTarget = iTarget
		self.settarget = []

	def GetParentID(self):
		return self.iParent

	def GetTargetID(self):
		return self.iTarget

	def SetTarget(self, iID):
		self.settarget.append(iID)
		self.iTarget = iID

	def SetTargetOffset(self, v):
		pass


def make_config(**kw):
	c = types.ModuleType("Custom.Spaceframe.Modules.STProbe.Config")
	c.AnyShip = 1
	c.SelectKey = "K"
	c.RunKey = "O"
	c.SampleSeconds = 2.0
	c.BannerSeconds = 8.0
	for k in kw:
		setattr(c, k, kw[k])
	return c


def register_packages(cfg):
	names = ["Custom", "Custom.Spaceframe", "Custom.Spaceframe.Modules", "Custom.Spaceframe.Modules.STProbe"]
	for n in names:
		if n not in sys.modules:
			sys.modules[n] = types.ModuleType(n)
	sys.modules["Custom"].Spaceframe = sys.modules["Custom.Spaceframe"]
	sys.modules["Custom.Spaceframe"].Modules = sys.modules["Custom.Spaceframe.Modules"]
	sys.modules["Custom.Spaceframe.Modules"].STProbe = sys.modules["Custom.Spaceframe.Modules.STProbe"]
	sys.modules["Custom.Spaceframe.Modules.STProbe.Config"] = cfg
	sys.modules["Custom.Spaceframe.Modules.STProbe"].Config = cfg


class World:
	pass


def setup(anyship=1, lPhaser=None, lTorp=None):
	W = World()
	W.App = App = mock_app.make_app()
	mock_app.install(App)
	CLOCK[0] = 0.0
	del CALLS[:]
	del BANNERS[:]
	App.g_kUtopiaModule.GetGameTime = lambda: CLOCK[0]
	App.ET_WEAPON_FIRED = 9201
	App.ET_TORPEDO_ENTERED_SET = 9202
	App.Weapon_Cast = lambda o: (isinstance(o, FakeWeapon) and o) or None
	App.PhaserBank_Cast = lambda o: (isinstance(o, FakeWeapon) and o.kind == "phaser" and o) or None
	App.TorpedoTube_Cast = lambda o: (isinstance(o, FakeWeapon) and o.kind == "torp" and o) or None
	App.PulseWeapon_Cast = lambda o: (isinstance(o, FakeWeapon) and o.kind == "pulse" and o) or None
	App.PhaserSystem_Cast = lambda o: (isinstance(o, FakeSystem) and o.kind == "phaser" and o) or None
	App.TorpedoSystem_Cast = lambda o: (isinstance(o, FakeSystem) and o.kind == "torp" and o) or None
	App.PulseWeaponSystem_Cast = lambda o: (isinstance(o, FakeSystem) and o.kind == "pulse" and o) or None
	App.Torpedo_Cast = lambda o: o
	App.WeaponSystemProperty_Cast = lambda o: o

	def banner(*a):
		BANNERS.append(a[1].s)
	sys.modules["MissionLib"].TextBanner = banner
	register_packages(make_config(AnyShip=anyship))
	W.ship = RecShip("Galaxy", 1)
	W.ship.GetAI = lambda: None
	W.A = RecShip("Romulan A", 2)
	W.A.pos = mock_app.Point(10.0, 0.0, 0.0)
	W.B = RecShip("Romulan B", 3)
	W.B.pos = mock_app.Point(20.0, 0.0, 0.0)
	W.ship.target = W.A
	if lPhaser == None:
		lPhaser = [FakeWeapon("Phaser 1", "phaser"), FakeWeapon("Phaser 2", "phaser"), FakeWeapon("Phaser 3", "phaser")]
	if lTorp == None:
		lTorp = [FakeWeapon("Torp 1", "torp"), FakeWeapon("Torp 2", "torp")]
	for w in lPhaser + lTorp:
		w.parent = W.ship
	W.phasers = FakeSystem("phaser", lPhaser)
	W.torps = FakeSystem("torp", lTorp)
	W.ship.groups[0] = W.phasers
	if len(lTorp) > 0:
		W.ship.groups[1] = W.torps
	W.core = mock_app.Core()
	W.core.g_pMission = mock_app.Mission([W.A, W.B])
	App._player[0] = W.ship
	W.STP = mock_app.load_module("Modules/STProbe/STProbe.py", "Custom.Spaceframe.Modules.STProbe.STProbe")
	W.STP.Start(W.core)
	W.STP.g_sLogFile = os.devnull	# tests never write the real log file
	return W


def key(W, iChar, iState=None):
	if iState == None:
		iState = W.App.TGKeyboardEvent.KS_KEYDOWN
	return mock_app.KeyEvent(iChar, iState)


def advance(W, fSeconds):
	# Game time passes in core-cycle steps; the core ticks the module.
	fEnd = CLOCK[0] + fSeconds
	while (CLOCK[0] < fEnd - 0.001) and (W.STP.g_dRun != None):
		CLOCK[0] = CLOCK[0] + 0.25
		W.STP.Tick([])


def text():
	return "\n".join(BANNERS)


def fire_torp_ab(W):
	# Engine policy of the fake: tube 0 fires at A, tube 1 at B.
	W.torps.assign = [W.A.GetObjID(), W.B.GetObjID()]


def torp_world():
	# A single-fire torpedo system: the engine only fires one tube at a time
	# unless the PROPERTY flag was cleared (group modes do not help).
	W = setup(lTorp=[FakeWeapon("T1", "torp", (1, 1)), FakeWeapon("T2", "torp", (0, 1)), FakeWeapon("T3", "torp", (1, 0))])
	pSys = W.torps
	pSys.prop.single = 1
	idA = W.A.GetObjID()
	idB = W.B.GetObjID()

	def policy(p):
		if p.prop.single:
			p.assign = [idA, None, None]
		else:
			p.assign = [idA, idB, None]
	pSys.policy = policy
	W.kindsys = pSys
	return W


# --- lifecycle -------------------------------------------------------------
def test_start_twice_stop_clean():
	W = setup()
	W.STP.Start(W.core)
	for eType in (9201, 9202):
		assert W.App.g_kEventManager.count(eType) == 1
	assert W.App._top.handlers.count((W.App.ET_KEYBOARD, W.STP.KEY_HANDLER)) == 1
	del CALLS[:]
	W.STP.Stop()
	for eType in (9201, 9202):
		assert W.App.g_kEventManager.count(eType) == 0
	assert W.App._top.handlers == []
	assert CALLS == []


def test_stop_during_run_touches_no_ship():
	W = setup()
	fire_torp_ab(W)
	W.STP.Begin("MULTI_TORP")
	assert W.STP.g_dRun != None
	del CALLS[:]
	W.STP.Stop()
	assert W.STP.g_dRun == None and CALLS == []


# --- keys --------------------------------------------------------------------
def test_keys_consumed_and_passed():
	W = setup()
	for iChar in (107, 111):
		ev = key(W, iChar)
		W.STP.OnKeyboard(W.App._top, ev)
		assert ev.handled == 1 and ev.passed == 0
	W.STP.Stop()
	W.STP.Start(W.core)
	for iChar in (75, 79, 108, 97):
		ev = key(W, iChar)
		W.STP.OnKeyboard(W.App._top, ev)
		assert ev.passed == 1 and ev.handled == 0
	for iChar in (107, 111):
		ev = key(W, iChar, W.App.TGKeyboardEvent.KS_KEYUP)
		W.STP.OnKeyboard(W.App._top, ev)
		assert ev.passed == 1 and ev.handled == 0


def test_keys_not_consumed_when_not_allowed():
	W = setup(anyship=0)
	for iChar in (107, 111):
		ev = key(W, iChar)
		W.STP.OnKeyboard(W.App._top, ev)
		assert ev.passed == 1 and ev.handled == 0
	W.core.techs["Galaxy"] = {"STProbe": 1}
	ev = key(W, 107)
	W.STP.OnKeyboard(W.App._top, ev)
	assert ev.handled == 1


def test_select_cycles_and_shows_results():
	W = setup()
	W.STP.g_dResults["MULTI_TORP"] = ["RESULT LINE ONE"]
	seen = []
	iNum = len(W.STP.TESTS)
	for n in range(iNum):
		del BANNERS[:]
		W.STP.OnKeyboard(W.App._top, key(W, 107))
		seen.append(W.STP.TESTS[W.STP.g_iSel])
		assert W.STP.TESTS[W.STP.g_iSel] in text()
		if W.STP.TESTS[W.STP.g_iSel] == "MULTI_TORP":
			assert "RESULT LINE ONE" in text()
	assert W.STP.g_iSel == 0
	assert len(seen) == iNum and seen[0] == "MULTI_TORP" and seen[-2] == "ALL" and seen[-1] == "INFO"
	for sName in W.STP.TESTS:
		assert sName in W.STP.HINT and sName in W.STP.KINDS
	assert sorted(W.STP.TESTS) == sorted(["INFO", "MULTI_TORP", "FIRE_ONE", "TORP_RETARGET",
		"SINGLEFIRE_TORP", "ARCFORMULA", "ALL"])


def test_k_aborts_running_test():
	W = setup()
	fire_torp_ab(W)
	W.STP.Begin("MULTI_TORP")
	W.STP.OnKeyboard(W.App._top, key(W, 107))
	assert W.STP.g_dRun == None
	assert "aborted" in text()
	assert W.torps.log[-1] == ("stop",)


# --- preconditions -------------------------------------------------------------
def test_begin_refuses():
	W = setup()
	af = types.SimpleNamespace(IsEnabled=lambda: 1)
	W.core.modules["AutoFire"] = af
	W.STP.Begin("MULTI_TORP")
	assert W.STP.g_dRun == None and "NOT RUN" in text() and "Auto Fire" in text()
	W.core.modules["AutoFire"] = None
	del BANNERS[:]
	W.core.g_pMission = mock_app.Mission([W.A])
	W.STP.Begin("MULTI_TORP")
	assert W.STP.g_dRun == None and "no second enemy" in text()
	W.core.g_pMission = mock_app.Mission([W.A, W.B])
	del BANNERS[:]
	W.ship.groups = {0: W.phasers}
	W.STP.Begin("MULTI_TORP")
	assert W.STP.g_dRun == None and "NOT RUN" in text() and "torp" in text()
	del BANNERS[:]
	W.ship.target = None
	W.STP.Begin("MULTI_TORP")
	assert W.STP.g_dRun == None and "NOT RUN" in text()


# --- MULTI_TORP --------------------------------------------------------------------
def test_multi_torp_uses_fired_events():
	W = setup()
	W.STP.Begin("MULTI_TORP")
	assert W.torps.log[1] == ("start", W.A.GetObjID())
	assert W.STP.g_dRun["kind"] == "torp"
	w = W.torps.weapons[0]
	w.tgt = W.B.GetObjID()
	W.STP.OnWeaponFired(W.App._top, FakeEvent(w))
	other = FakeWeapon("Torp 1", "torp")	# same name on another ship: ignored
	other.parent = W.A
	other.tgt = W.A.GetObjID()
	W.STP.OnWeaponFired(W.App._top, FakeEvent(other))
	advance(W, 5.0)
	assert W.STP.g_dRun == None
	assert "T3 TORP" in text() and "onB:1" in text() and "onA:0" in text() and "rdy:2" in text()


def test_weapon_error_is_reported():
	W = setup()
	fire_torp_ab(W)
	W.torps.weapons[0].raise_tgt = 1
	W.STP.Begin("MULTI_TORP")
	advance(W, 5.0)
	assert W.STP.g_dRun == None
	assert "ERR GetTargetID" in text()


def test_ship_removed_mid_run_aborts():
	W = setup()
	fire_torp_ab(W)
	W.STP.Begin("MULTI_TORP")
	advance(W, 0.5)
	del mock_app.SHIPS[W.A.GetObjID()]
	W.A.IsDead = lambda: 1 / 0	# any later call into A would blow up
	advance(W, 0.5)
	assert W.STP.g_dRun == None and "ABORT" in text() and "A gone" in text()
	assert W.torps.log[-1] == ("stop",)
	# The player's ship gone: abort without touching its weapons.
	W = setup()
	fire_torp_ab(W)
	W.STP.Begin("MULTI_TORP")
	advance(W, 0.5)
	del mock_app.SHIPS[W.ship.GetObjID()]
	n = len(CALLS)
	advance(W, 0.5)
	assert W.STP.g_dRun == None and "ABORT" in text()
	assert len(CALLS) == n


# --- INFO -----------------------------------------------------------------------
def test_info_lines():
	W = setup()
	W.STP.Begin("INFO")
	assert W.STP.g_dRun == None
	assert "G0 phaser n=3" in text() and "G1 torp n=2" in text()
	sInfo = "\n".join(W.STP.g_dResults["INFO"])
	assert "torp reach A: CanHit(pt) w0=1 w1=1" in sInfo
	assert "CanHit(ship) w0=E w1=E [AttributeError" in sInfo	# the ship form is an error
	assert "pulse reach" not in sInfo


def test_info_pulse_arg_forms():
	W = setup(lPhaser=[FakeWeapon("Pulse 1", "pulse"), FakeWeapon("Pulse 2", "pulse", (0, 1))], lTorp=[])
	W.ship.groups[0] = FakeSystem("pulse", W.phasers.weapons)
	W.STP.Begin("INFO")
	sInfo = "\n".join(W.STP.g_dResults["INFO"])
	assert "pulse reach A: CHT(pt,v) w0=1 w1=0 |" in sInfo
	assert "CHT(ship) w0=E w1=E [TypeError" in sInfo
	assert "CHT(ship,v) w0=1 w1=0" in sInfo


def test_info_without_target_says_so():
	W = setup()
	W.ship.target = None
	W.STP.Begin("INFO")
	assert "select an enemy target (A)" in "\n".join(W.STP.g_dResults["INFO"])


# --- FIRE_ONE, TORP_RETARGET -----------------------------------------------------
def test_fire_one():
	W = setup()
	W.STP.Begin("FIRE_ONE")
	advance(W, 8.0)
	assert W.STP.g_dRun == None
	assert "Fire no-list" in text() and "Fire list A" in text() and "FireDumb" in text()
	assert ("w.Fire", "Torp 1") in CALLS and ("w.Fire", "Torp 2") in CALLS and ("w.FireDumb", "Torp 1") in CALLS
	assert W.torps.log[0] == ("stop",) and W.torps.log[1] == ("clear",)


def test_torp_retarget():
	W = setup()
	W.STP.Begin("TORP_RETARGET")
	assert W.STP.g_dRun["armed"] == 1
	t1 = FakeTorp(W.ship.GetObjID(), W.A.GetObjID())
	t2 = FakeTorp(W.ship.GetObjID(), W.A.GetObjID())
	W.STP.OnTorpedoEntered(W.App._top, FakeEvent(None, t1))
	W.STP.OnTorpedoEntered(W.App._top, FakeEvent(None, t2))
	assert t1.settarget == [W.B.GetObjID()]
	assert t2.settarget == []
	advance(W, 1.0)
	assert W.STP.g_dRun == None
	assert "tgt A->B" in text() and "parent=ship" in text()


def test_torp_retarget_ignores_foreign_torpedo_and_times_out():
	W = setup()
	W.STP.Begin("TORP_RETARGET")
	t1 = FakeTorp(99, W.B.GetObjID())
	W.STP.OnTorpedoEntered(W.App._top, FakeEvent(None, t1))
	assert t1.settarget == [] and W.STP.g_dRun["armed"] == 1
	advance(W, 21.0)
	assert W.STP.g_dRun == None and "no torpedo seen" in text()


# --- SINGLEFIRE_TORP, ALL, log file ----------------------------------------------
def test_singlefire_torp_variants_and_restore():
	W = torp_world()
	W.STP.Begin("SINGLEFIRE_TORP")
	assert W.STP.g_dRun["kind"] == "torp" and W.STP.g_dRun["base"] == "SINGLEFIRE"
	advance(W, 20.0)
	assert W.STP.g_dRun == None
	t = text()
	assert "base [s1 m1 p1] FAIL simul:0" in t
	assert "prop0 [s0 m1 p0] PASS simul:1" in t
	assert "mode0 [s1 m0 p1] FAIL" in t and "mode2 [s1 m2 p1] FAIL" in t
	assert "mode1 [" not in t	# the current mode is not tried
	assert "restored: ok [s1 m1 p1]" in t
	assert W.kindsys.prop.single == 1 and W.kindsys.mode == 1
	assert ("p.SetSingleFire", 0) in CALLS and ("p.SetSingleFire", 1) in CALLS
	assert "log file: written" in t
	assert W.STP.g_dResults["SINGLEFIRE_TORP"][0].startswith("base")


def test_singlefire_restore_failure_reported():
	W = torp_world()
	W.torps.reject_modes = [1]	# the original mode cannot be set back
	W.STP.Begin("SINGLEFIRE_TORP")
	advance(W, 20.0)
	assert W.STP.g_dRun == None
	assert "restored: failed" in text()


def test_singlefire_stop_touches_no_ship():
	W = torp_world()
	W.STP.Begin("SINGLEFIRE_TORP")
	advance(W, 5.0)
	del CALLS[:]
	W.STP.Stop()
	assert W.STP.g_dRun == None and CALLS == []


def test_singlefire_property_errors_are_reported():
	W = torp_world()
	W.App.WeaponSystemProperty_Cast = lambda o: 1 / 0
	W.STP.Begin("SINGLEFIRE_TORP")
	advance(W, 20.0)
	assert W.STP.g_dRun == None
	assert "WeaponSystemProperty_Cast" in "\n".join(W.STP.g_dResults["SINGLEFIRE_TORP"])


def test_singlefire_torp_leaves_phasers_alone():
	W = torp_world()
	W.phasers.prop.single = 1
	W.STP.Begin("SINGLEFIRE_TORP")
	advance(W, 20.0)
	assert W.phasers.prop.single == 1 and W.phasers.log == []
	assert ("p.SetSingleFire", 0) in CALLS


def test_singlefire_torp_missing_not_run():
	W = setup()
	W.ship.groups = {0: W.phasers}
	W.STP.Begin("SINGLEFIRE_TORP")
	assert W.STP.g_dRun == None and "NOT RUN" in text() and "torp" in text()


def test_singlefire_torp_abort_restores():
	W = torp_world()
	W.STP.Begin("SINGLEFIRE_TORP")
	advance(W, 5.0)		# inside the prop0 variant
	assert W.kindsys.prop.single == 0
	W.STP.OnKeyboard(W.App._top, key(W, 111))
	assert W.STP.g_dRun == None and W.kindsys.prop.single == 1 and "restored: ok" in text()
	assert W.torps.log[-1] == ("stop",)


# --- dying ship still gets its property back ---------------------------------------
def test_release_restores_property_of_dying_ship():
	W = torp_world()
	W.STP.Begin("SINGLEFIRE_TORP")
	for n in range(200):
		if W.torps.prop.single == 0 or W.STP.g_dRun == None:
			break
		advance(W, 0.25)
	assert W.torps.prop.single == 0 and W.STP.g_dRun != None
	W.ship.IsDying = lambda: 1		# still looked up by ID, but dying
	W.STP.Abort("test")
	assert W.STP.g_dRun == None
	assert W.torps.prop.single == 1
	assert "restored: ok" in text()
	# A ship that is really gone cannot be restored: reported, not crashed.
	W = torp_world()
	W.STP.Begin("SINGLEFIRE_TORP")
	for n in range(200):
		if W.torps.prop.single == 0 or W.STP.g_dRun == None:
			break
		advance(W, 0.25)
	del mock_app.SHIPS[W.ship.GetObjID()]
	del BANNERS[:]
	W.STP.Abort("test")
	assert "restored: failed (ship gone)" in text()


# --- banner wrapping --------------------------------------------------------------------
def test_wrap_line():
	STP = STP_mod()
	assert STP.WrapLine("short", 70) == ["short"]
	sLong = string.join(["word%d" % n for n in range(40)], " ")
	lOut = STP.WrapLine(sLong, 70)
	assert len(lOut) >= 3
	for s in lOut:
		assert len(s) <= 70
	assert string.join([s.strip() for s in lOut], " ") == sLong
	lOut = STP.WrapLine("x" * 150, 70)
	assert max([len(s) for s in lOut]) <= 70
	assert string.join([s.strip() for s in lOut], "") == "x" * 150


def test_show_wraps_instead_of_cutting_and_keeps_last_line():
	W = setup()
	sEnd = "THE END OF THE LINE"
	W.STP.Show(["HOLD " + "word " * 20 + sEnd])
	assert len(BANNERS) >= 2 and sEnd in BANNERS[-1]
	for s in BANNERS:
		assert len(s) <= W.STP.MAX_WIDTH
	del BANNERS[:]
	W.STP.Show(["line " + str(n) for n in range(12)] + ["log file: written (3 lines)"])
	assert len(BANNERS) == W.STP.MAX_LINES and BANNERS[-1] == "log file: written (3 lines)"
	assert BANNERS[0] == "line 0"


def test_show_keeps_restore_line_when_cutting():
	W = setup()
	lLines = ["line " + str(n) for n in range(12)] + ["restored: ok [s1 m1 p1]", "log file: written (3 lines)"]
	W.STP.Show(lLines)
	assert len(BANNERS) == W.STP.MAX_LINES
	assert "restored: ok [s1 m1 p1]" in BANNERS and BANNERS[-1] == "log file: written (3 lines)"
	assert BANNERS[0] == "line 0"


def test_finish_banner_keeps_restore_line_with_long_report():
	W = torp_world()
	W.STP.Begin("SINGLEFIRE_TORP")
	advance(W, 20.0)
	assert W.STP.g_dRun == None
	assert "restored: ok" in text()


def run_all(W):
	W.STP.Begin("ALL")
	advance(W, 120.0)


def test_all_runs_and_reports():
	W = setup()
	fire_torp_ab(W)
	path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_stprobe_test_log.txt")
	if os.path.exists(path):
		os.remove(path)
	W.STP.g_sLogFile = path
	try:
		run_all(W)
		assert W.STP.g_dRun == None
		lRep = W.STP.g_dResults["ALL"]
		assert 1 <= len(lRep) <= W.STP.MAX_LINES
		sRep = "\n".join(lRep)
		for sName in W.STP.ALL_TESTS:
			assert sName in sRep
		assert "MULTI_TORP PASS" in sRep
		assert "MANUAL" not in sRep and "TORP_RETARGET" not in sRep
		for sLine in lRep:
			assert len(sLine) <= W.STP.MAX_WIDTH
		assert "log file: written" in text()
		sFile = open(path).read()
		assert "== MULTI_TORP PASS ==" in sFile and "T3 TORP" in sFile
		assert "base [s0 m1 p0]" in sFile
		# every single test result is kept
		for sName in ("INFO", "SINGLEFIRE_TORP", "MULTI_TORP", "FIRE_ONE"):
			assert W.STP.g_dResults.get(sName)
	finally:
		if os.path.exists(path):
			os.remove(path)


def test_all_k_reshows_report():
	W = setup()
	W.STP.g_dResults["ALL"] = ["REPORT LINE"]
	W.STP.g_iSel = W.STP.TESTS.index("ALL") - 1
	del BANNERS[:]
	W.STP.OnKeyboard(W.App._top, key(W, 107))
	assert W.STP.TESTS[W.STP.g_iSel] == "ALL" and "REPORT LINE" in text()


def test_all_abort_in_singlefire_variant_restores():
	W = torp_world()
	W.STP.Begin("ALL")
	advance(W, 5.0)		# INFO is instant; inside the prop0 variant of SINGLEFIRE_TORP
	assert W.STP.g_dRun["name"] == "SINGLEFIRE_TORP" and W.torps.prop.single == 0
	W.STP.OnKeyboard(W.App._top, key(W, 111))
	assert W.STP.g_dRun == None
	assert W.torps.prop.single == 1 and W.torps.mode == 1 and "restored: ok" in text()
	assert W.torps.log[-1] == ("stop",)
	assert "ABORT" in text()
	n = len(CALLS)
	advance(W, 5.0)		# nothing continues
	assert len(CALLS) == n


def test_all_refuses_without_second_enemy():
	W = setup()
	W.core.g_pMission = mock_app.Mission([W.A])
	W.STP.Begin("ALL")
	assert W.STP.g_dRun == None and "NOT RUN" in text()


def test_log_file_failure_does_not_raise():
	W = setup()
	fire_torp_ab(W)
	pReal = builtins.open

	def broken(*a):
		raise IOError("denied")
	builtins.open = broken
	try:
		W.STP.Begin("MULTI_TORP")
		advance(W, 5.0)
		assert W.STP.g_dRun == None
		assert "PASS" in text() and "log file: FAILED" in text() and "denied" in text()
		del BANNERS[:]
		W.STP.Begin("INFO")
		assert "log file: FAILED" in text()
		W.STP.Begin("ALL")
		advance(W, 120.0)
		assert W.STP.g_dRun == None
		assert "log file: FAILED" in text()
	finally:
		builtins.open = pReal


def test_log_file_written_for_single_test():
	W = setup()
	fire_torp_ab(W)
	path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_stprobe_test_log2.txt")
	if os.path.exists(path):
		os.remove(path)
	W.STP.g_sLogFile = path
	try:
		W.STP.Begin("MULTI_TORP")
		advance(W, 5.0)
		assert "log file: written" in text()
		long_line_check = open(path).read()
		assert "=== STProbe MULTI_TORP" in long_line_check and "w0 r:AB f:A" in long_line_check
	finally:
		if os.path.exists(path):
			os.remove(path)


def test_pack_compact():
	STP = STP_mod()
	assert STP.PackCompact([]) == []
	assert STP.PackCompact(["A ok", "B ok"]) == ["A ok | B ok"]
	lItems = ["X" * 40, "Y" * 40, "Z" * 10]
	assert STP.PackCompact(lItems) == ["X" * 40, "Y" * 40 + " | " + "Z" * 10]


# --- pure functions ------------------------------------------------------------
def test_classify_verdict_weaponline():
	dSeen = {0: {"A": 3}, 1: {"B": 2}}
	dReach = {0: (1, 1), 1: (0, 1), 2: (1, 0)}
	dC = W_classify(dSeen, dReach, 1)
	assert dC["onA"] == [0] and dC["onB"] == [1]
	assert dC["bothReach"] == [0] and dC["bothPickA"] == [0] and dC["bothPickB"] == []
	assert dC["onlyB"] == [1] and dC["onlyBFired"] == [1] and dC["onlyA"] == [2]
	assert STP_mod().Verdict(dC) == "PASS"
	assert STP_mod().WeaponLine(dSeen, dReach) == ["w0 r:AB f:A  w1 r:B f:B  w2 r:A f:-"]
	dC = W_classify({0: {"A": 1}}, {0: (1, 1), 1: (1, 1)}, 0)
	assert STP_mod().Verdict(dC) == "INCONCLUSIVE geometry"
	dC = W_classify({0: {"A": 1}}, {0: (1, 1), 1: (0, 1)}, 0)
	assert STP_mod().Verdict(dC) == "FAIL"
	assert dC["onlyBFired"] == []
	lLines = STP_mod().WeaponLine({}, {0: (1, 1), 1: (1, 0), 2: (0, 1), 3: (0, 0)})
	assert lLines == ["w0 r:AB f:-  w1 r:A f:-", "w2 r:B f:-  w3 r:- f:-"]
	assert STP_mod().WeaponLine({}, {}) == []
	assert STP_mod().WeaponLine({0: {"B": 1}}, {0: (1, "E")}) == ["w0 r:A? f:B"]


_MOD = [None]


def STP_mod():
	if _MOD[0] == None:
		_MOD[0] = setup().STP
	return _MOD[0]


def W_classify(dSeen, dReach, iSimul):
	return STP_mod().Classify(dSeen, dReach, iSimul)


# --- ARCFORMULA -----------------------------------------------------------------------
class ArcPulse(mock_app.Pulse):
	"""A pulse weapon whose IsInArc is the box test (weapon at the origin, identity axes)."""
	def IsInArc(self, p):
		import math
		if p.x <= 0.0:
			return 0
		aw = math.atan2(p.y, p.x)
		ah = math.atan2(p.z, p.x)
		return int(self.limits[0] <= aw <= self.limits[1] and self.limits[2] <= ah <= self.limits[3])


def arc_world():
	W = setup(lPhaser=[], lTorp=[])
	W.App.Weapon_Cast = lambda o: (isinstance(o, mock_app.Pulse) and o) or None
	W.App.PulseWeapon_Cast = lambda o: (isinstance(o, mock_app.Pulse) and o) or None
	for n in ("Custom.Spaceframe.Modules.AutoFire",):
		sys.modules[n] = types.ModuleType(n)
	sys.modules["Custom.Spaceframe.Modules"].AutoFire = sys.modules["Custom.Spaceframe.Modules.AutoFire"]
	S = mock_app.load_module("Modules/AutoFire/Solution.py", "Custom.Spaceframe.Modules.AutoFire.Solution")
	sys.modules["Custom.Spaceframe.Modules.AutoFire"].Solution = S
	W.arc = ArcPulse()
	W.ship.groups[0] = FakeSystem("pulse", [W.arc])
	return W


def test_arcformula_registered_and_not_in_all():
	W = setup()
	assert "ARCFORMULA" in W.STP.TESTS and "ARCFORMULA" in W.STP.HINT and "ARCFORMULA" in W.STP.KINDS
	assert "ARCFORMULA" not in W.STP.ALL_TESTS


def test_arcformula_all_points_match():
	W = arc_world()
	W.STP.Begin("ARCFORMULA")
	sLine = W.STP.g_dResults["ARCFORMULA"][1]
	assert sLine.startswith("w0 candA: 12/12 match, candB: 12/12 match, W[-29,29] H[-29,29]deg"), sLine
	assert "tgt depth A=" in sLine	# the selected target A is read


def test_arcformula_asymmetric_limits():
	W = arc_world()
	W.arc.limits = (0.0, 1.0, -0.2, 0.2)
	W.STP.Begin("ARCFORMULA")
	sLine = W.STP.g_dResults["ARCFORMULA"][1]
	assert "candA: 12/12 match" in sLine and "W[0,57] H[-11,11]deg" in sLine, sLine


def test_arcformula_reports_a_wrong_candidate():
	# The game's arc is around the weapon's own world point (A): candidate B
	# puts the weapon 200 units to the side and disagrees.
	W = arc_world()
	W.ship.pos = mock_app.Point(0.0, 200.0, 0.0)
	W.STP.Begin("ARCFORMULA")
	sLine = W.STP.g_dResults["ARCFORMULA"][1]
	assert "candA: 12/12 match" in sLine and "candB: 12/12 match" not in sLine, sLine
	assert "miss(ours/game)" in sLine


def test_arcformula_accessor_error_is_reported():
	W = arc_world()
	W.arc.limits = "raise"
	W.STP.Begin("ARCFORMULA")
	assert "ERR" in W.STP.g_dResults["ARCFORMULA"][1]


def run():
	failed = 0
	names = [n for n in sorted(globals()) if n.startswith("test_")]
	for n in names:
		try:
			globals()[n]()
			print("PASS " + n)
		except Exception as e:
			failed = failed + 1
			print("FAIL " + n + ": " + type(e).__name__ + " " + str(e)[:120])
	print("%d/%d passed" % (len(names) - failed, len(names)))
	return failed


if __name__ == "__main__":
	sys.exit(run())
