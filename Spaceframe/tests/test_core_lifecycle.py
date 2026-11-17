"""Spaceframe core characterization tests: Start/Stop lifecycle, error
isolation, ship technologies, multiplayer, interval. They pin the CURRENT
behavior (see "suspected bug" comments)."""
import os
import sys
import types
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mock_app
import fake_ships
from fake_ships import near, FakeShip, FakeShields

CORE = "Custom.Spaceframe.Spaceframe"
PKG = "Custom.Spaceframe.Modules."
HIT = 7777


# --- test harness -----------------------------------------------------------------------
class StringShim:
	"""The Python 1.5 string functions the core uses."""
	def find(self, s, sub):
		return s.find(sub)

	def split(self, s, sep=None):
		return s.split(sep)


def make_fake(sName, log, bBadStart=0, lTickFail=None, bStopFail=0, bHitFail=0):
	"""A module that logs (name, call) tuples. lTickFail(n) -> 1 makes the
	n-th Tick (1-based) raise."""
	m = types.ModuleType(PKG + sName + "." + sName)
	m.nTick = 0
	m.nStop = 0
	m.nHit = 0
	m.pCore = None
	m.fIntervalAtStart = None

	def Start(pCore):
		log.append((sName, "Start"))
		m.pCore = pCore
		m.fIntervalAtStart = pCore.GetInterval()
		if bBadStart:
			raise RuntimeError("cannot start")

	def Stop():
		m.nStop = m.nStop + 1
		log.append((sName, "Stop"))
		if bStopFail:
			raise RuntimeError("cannot stop")

	def Tick(lShips):
		m.nTick = m.nTick + 1
		log.append((sName, "Tick"))
		if lTickFail != None and lTickFail(m.nTick):
			raise RuntimeError("tick failed")

	def WeaponHit(pShip, pEvent):
		m.nHit = m.nHit + 1
		log.append((sName, "Hit"))
		if bHitFail:
			raise RuntimeError("hit failed")
	m.Start = Start
	m.Stop = Stop
	m.Tick = Tick
	m.WeaponHit = WeaponHit
	return m


class Utopia:
	def __init__(self, bMulti):
		self.bMulti = bMulti

	def IsMultiplayer(self):
		return self.bMulti


def plugin(sName, sRace, sSubMenu, **techs):
	m = types.ModuleType("Custom.Bedrock.Ships." + sName)
	m.Race = sRace
	m.SubMenu = sSubMenu
	for k in techs.keys():
		setattr(m, k, techs[k])
	sys.modules["Custom.Bedrock.Ships." + sName] = m
	sys.modules["Custom.Bedrock.Ships"].__dict__[sName] = m


def load_core(lMods=None, bMulti=0, All=None, Races=None, Families=None, Ships=None, **cfg):
	"""lMods: list of (name, module or None). A None module is listed in the
	Modules folder but cannot be imported. Returns (C, App)."""
	for n in list(sys.modules.keys()):
		if n.startswith("Custom"):
			del sys.modules[n]
	App = mock_app.make_app()
	mock_app.install(App)
	App.ET_WEAPON_HIT = HIT
	App.g_kUtopiaModule = Utopia(bMulti)
	for n in ("Custom", "Custom.Bedrock", "Custom.Bedrock.Ships", "Custom.Spaceframe", "Custom.Spaceframe.Modules"):
		sys.modules[n] = types.ModuleType(n)
	sys.modules["Custom"].Spaceframe = sys.modules["Custom.Spaceframe"]
	sys.modules["Custom"].Bedrock = sys.modules["Custom.Bedrock"]
	sys.modules["Custom.Bedrock"].Ships = sys.modules["Custom.Bedrock.Ships"]
	sys.modules["Custom.Spaceframe"].Modules = sys.modules["Custom.Spaceframe.Modules"]

	ships = types.ModuleType("Custom.Spaceframe.Ships")
	ships.All = All or {}
	ships.Races = Races or {}
	ships.Families = Families or {}
	ships.Ships = Ships or {}
	sys.modules["Custom.Spaceframe.Ships"] = ships
	sys.modules["Custom.Spaceframe"].Ships = ships

	config = types.ModuleType("Custom.Spaceframe.Config")
	config.Modules = {}
	config.Interval = 0.25
	config.EnableInMultiplayer = 0
	config.Debug = 0
	for k in cfg.keys():
		setattr(config, k, cfg[k])
	sys.modules["Custom.Spaceframe.Config"] = config
	sys.modules["Custom.Spaceframe"].Config = config

	lNames = []
	for t in (lMods or []):
		lNames.append(t[0])
		if t[1] != None:
			pMod = t[1]
			if callable(pMod):
				pMod = pMod()		# a factory: needs the new App installed first
			if (PKG + t[0]) not in sys.modules:
				sys.modules[PKG + t[0]] = types.ModuleType(PKG + t[0])
			sys.modules[PKG + t[0] + "." + t[0]] = pMod
	nt = types.ModuleType("nt")
	nt.listdir = lambda sPath: lNames + ["__init__.py"]
	sys.modules["nt"] = nt

	C = mock_app.load_module("Spaceframe.py", CORE)
	C.string = StringShim()
	sys.modules["Custom.Spaceframe"].Spaceframe = C
	return C, App


def fakes(*lNames, **kw):
	log = []
	lMods = []
	for s in lNames:
		lMods.append((s, make_fake(s, log, **kw)))
	return log, lMods


def tick_all(C, n=1, lShips=None):
	C.GetShipsInPlay = lambda: ([], lShips or [])
	for i in range(n):
		C.g_pRunner.Update(0.25)


def entry(C, sName):
	for l in C.g_lModules:
		if l[0] == sName:
			return l
	return None


# --- Start / Stop ------------------------------------------------------------------------
def test_start_runs_modules_in_name_order_with_core():
	log, lMods = fakes("Gamma", "Alpha", "Beta")
	C, App = load_core(lMods)
	C.Start(object())
	assert log == [("Alpha", "Start"), ("Beta", "Start"), ("Gamma", "Start")]
	assert lMods[0][1].pCore is C
	assert [l[0] for l in C.g_lModules] == ["Alpha", "Beta", "Gamma"]


def test_tick_order_and_stop_order_are_the_same():
	# CURRENT BEHAVIOR: Stop() visits modules in load order, not reversed.
	log, lMods = fakes("Alpha", "Beta")
	C, App = load_core(lMods)
	C.Start(object())
	del log[:]
	tick_all(C)
	C.Stop()
	assert log == [("Alpha", "Tick"), ("Beta", "Tick"), ("Alpha", "Stop"), ("Beta", "Stop")]


def test_start_registers_timer_and_hit_handler_stop_removes_them():
	log, lMods = fakes("Alpha")
	C, App = load_core(lMods)
	pMission = object()
	C.Start(pMission)
	pRunner = C.g_pRunner
	assert pRunner != None and pRunner.bActive == 1
	assert pRunner.pProcess.delay == 0.25
	assert App.g_kEventManager.handlers == [(HIT, pMission, C.HIT_HANDLER)]
	assert C.g_pMission is pMission
	C.Stop()
	assert C.g_pRunner == None and C.g_pMission == None
	assert pRunner.bActive == 0 and pRunner.pProcess == None
	assert App.g_kEventManager.handlers == []
	assert C.g_lModules == []


def test_stop_is_idempotent_and_safe_without_start():
	C, App = load_core([])
	C.Stop()
	log, lMods = fakes("Alpha")
	C, App = load_core(lMods)
	C.Start(object())
	C.Stop()
	C.Stop()
	assert lMods[0][1].nStop == 1


def test_start_twice_stops_the_first_run():
	log, lMods = fakes("Alpha")
	C, App = load_core(lMods)
	C.Start(object())
	pFirst = C.g_pRunner
	C.Start(object())
	assert log == [("Alpha", "Start"), ("Alpha", "Stop"), ("Alpha", "Start")]
	assert pFirst.bActive == 0 and C.g_pRunner != pFirst
	assert len(App.g_kEventManager.handlers) == 1


def test_start_resets_ship_caches():
	log, lMods = fakes("Alpha")
	C, App = load_core(lMods, Ships={"Galaxy": {"Alpha": 1}})
	C.Start(object())
	assert C.GetShipTechs("Galaxy") == {"Alpha": 1}
	sys.modules["Custom.Spaceframe.Ships"].Ships = {"Galaxy": {"Alpha": 2}}
	assert C.GetShipTechs("Galaxy") == {"Alpha": 1}		# cached
	C.Start(object())
	assert C.GetShipTechs("Galaxy") == {"Alpha": 2}


def test_no_modules_means_no_timer_and_no_handler():
	C, App = load_core([])
	C.Start(object())
	assert C.g_pRunner == None and App.g_kEventManager.handlers == []


def test_module_disabled_in_config_or_missing_is_skipped():
	log, lMods = fakes("Alpha", "Beta")
	lMods.append(("Broken", None))		# listed but import fails
	C, App = load_core(lMods, Modules={"Beta": 0})
	C.Start(object())
	assert [l[0] for l in C.g_lModules] == ["Alpha"]
	assert log == [("Alpha", "Start")]


# --- failures --------------------------------------------------------------------------------
def test_module_start_failure_disables_only_that_module():
	logA, lA = fakes("Alpha")
	logB, lB = fakes("Beta", bBadStart=1)
	C, App = load_core(lA + lB)
	C.Start(object())
	assert entry(C, "Alpha")[2] == 1
	assert entry(C, "Beta")[2] == 0 and entry(C, "Beta")[3] == 1
	assert C.g_pRunner != None
	tick_all(C, 2)
	assert lA[0][1].nTick == 2 and lB[0][1].nTick == 0
	assert C.GetModule("Beta") == None and C.GetModule("Alpha") is lA[0][1]


def test_tick_error_in_one_module_does_not_stop_the_others():
	log = []
	lMods = [("Alpha", make_fake("Alpha", log)),
		("Beta", make_fake("Beta", log, lTickFail=lambda n: 1)),
		("Gamma", make_fake("Gamma", log))]
	C, App = load_core(lMods)
	C.Start(object())
	tick_all(C, 3)
	assert lMods[0][1].nTick == 3 and lMods[2][1].nTick == 3
	assert entry(C, "Beta")[3] == 3 and entry(C, "Beta")[2] == 1


def test_max_errors_disables_module_while_others_keep_running():
	log = []
	lMods = [("Alpha", make_fake("Alpha", log)),
		("Bad", make_fake("Bad", log, lTickFail=lambda n: 1))]
	C, App = load_core(lMods)
	C.Start(object())
	tick_all(C, 60)
	assert C.MAX_ERRORS == 50
	assert entry(C, "Bad")[2] == 0 and entry(C, "Bad")[3] == 50
	assert lMods[1][1].nTick == 50		# never called again once disabled
	assert lMods[0][1].nTick == 60
	assert C.GetModule("Bad") == None


def test_one_error_below_max_keeps_module_active():
	log = []
	lMods = [("Bad", make_fake("Bad", log, lTickFail=lambda n: 1))]
	C, App = load_core(lMods)
	C.Start(object())
	tick_all(C, 49)
	assert entry(C, "Bad")[2] == 1 and entry(C, "Bad")[3] == 49


def test_error_counter_never_resets():
	# FIXED: the counter goes back to 0 after a Tick that completes without
	# error, so a module that fails once in a while is never disabled.
	log = []
	lMods = [("Flaky", make_fake("Flaky", log, lTickFail=lambda n: n % 2 == 1))]
	C, App = load_core(lMods)
	C.Start(object())
	tick_all(C, 20)
	assert entry(C, "Flaky")[3] == 0		# the last Tick (even n) was good
	tick_all(C, 100)
	assert entry(C, "Flaky")[2] == 1 and entry(C, "Flaky")[3] == 0
	assert lMods[0][1].nTick == 120
	# only consecutive failures count (Start and WeaponHit errors still do)
	log2 = []
	lBad = [("Bad", make_fake("Bad", log2, lTickFail=lambda n: n <= 10 or n > 20))]
	C, App = load_core(lBad)
	C.Start(object())
	tick_all(C, 10)
	assert entry(C, "Bad")[3] == 10
	tick_all(C, 10)
	assert entry(C, "Bad")[3] == 0 and entry(C, "Bad")[2] == 1


def test_stop_not_called_on_disabled_modules():
	# FIXED: Stop() also calls modules disabled by errors or a failed Start,
	# so they can clean up (remove handlers, delete HUD texts).
	log = []
	lMods = [("Alpha", make_fake("Alpha", log, lTickFail=lambda n: 1)),
		("Beta", make_fake("Beta", log, bBadStart=1)),
		("Gamma", make_fake("Gamma", log))]
	C, App = load_core(lMods)
	C.Start(object())
	tick_all(C, 50)
	assert entry(C, "Alpha")[2] == 0 and entry(C, "Beta")[2] == 0
	C.Stop()
	assert lMods[0][1].nStop == 1 and lMods[1][1].nStop == 1
	assert lMods[2][1].nStop == 1
	# a disabled module whose Stop raises does not block the others
	log = []
	lMods = [("Alpha", make_fake("Alpha", log, bBadStart=1, bStopFail=1)), ("Beta", make_fake("Beta", log))]
	C, App = load_core(lMods)
	C.Start(object())
	C.Stop()
	assert lMods[0][1].nStop == 1 and lMods[1][1].nStop == 1
	assert C.g_lModules == []


def test_stop_error_in_one_module_does_not_block_the_others():
	log = []
	lMods = [("Alpha", make_fake("Alpha", log, bStopFail=1)), ("Beta", make_fake("Beta", log))]
	C, App = load_core(lMods)
	C.Start(object())
	C.Stop()
	assert lMods[0][1].nStop == 1 and lMods[1][1].nStop == 1
	assert C.g_lModules == []


def test_weapon_hit_dispatch_and_isolation():
	log = []
	lMods = [("Alpha", make_fake("Alpha", log, bHitFail=1)), ("Beta", make_fake("Beta", log))]
	C, App = load_core(lMods)
	C.Start(object())
	pShip = FakeShip("Galaxy", 1)
	C.OnWeaponHit(None, mock_app.Event(HIT, 0, pShip))
	assert lMods[0][1].nHit == 1 and lMods[1][1].nHit == 1
	assert entry(C, "Alpha")[3] == 1
	C.OnWeaponHit(None, mock_app.Event(HIT, 0, None))		# no ship: ignored
	assert lMods[1][1].nHit == 1
	C.Stop()
	C.OnWeaponHit(None, mock_app.Event(HIT, 0, pShip))		# after Stop: ignored
	assert lMods[1][1].nHit == 1


# --- multiplayer / interval -------------------------------------------------------------
def test_multiplayer_disabled_by_default():
	log, lMods = fakes("Alpha")
	C, App = load_core(lMods, bMulti=1)
	C.Start(object())
	assert log == [] and C.g_lModules == [] and C.g_pRunner == None
	assert App.g_kEventManager.handlers == []


def test_multiplayer_allowed_with_setting():
	log, lMods = fakes("Alpha")
	C, App = load_core(lMods, bMulti=1, EnableInMultiplayer=1)
	C.Start(object())
	assert log == [("Alpha", "Start")] and C.g_pRunner != None


def test_interval_clamped_to_minimum():
	for fIn, fOut in ((0.01, 0.05), (0, 0.05), (-3, 0.05), (0.05, 0.05), (0.5, 0.5), (2.0, 2.0)):
		log, lMods = fakes("Alpha")
		C, App = load_core(lMods, Interval=fIn)
		C.Start(object())
		assert C.GetInterval() == fOut, fIn
		assert C.g_pRunner.pProcess.delay == fOut, fIn


def test_interval_not_a_number_leaves_modules_started_without_timer():
	# CURRENT BEHAVIOR: modules are already started when the interval fails
	# to parse; there is no timer and no hit handler, and nothing stops them
	# until the next Stop().
	log, lMods = fakes("Alpha")
	C, App = load_core(lMods, Interval="abc")
	C.Start(object())
	assert C.g_pRunner == None and App.g_kEventManager.handlers == []
	assert log == [("Alpha", "Start")] and entry(C, "Alpha")[2] == 1
	C.Stop()
	assert lMods[0][1].nStop == 1


def test_modules_see_the_configured_interval_in_start():
	# FIXED: g_fInterval is set before the modules' Start() runs, so
	# GetInterval() is right inside Start().
	log, lMods = fakes("Alpha")
	C, App = load_core(lMods, Interval=1.0)
	C.Start(object())
	assert lMods[0][1].fIntervalAtStart == 1.0
	assert C.GetInterval() == 1.0


# --- ship technologies ---------------------------------------------------------------------
def tech_core(**kw):
	C, App = load_core([], **kw)
	plugin("GalaxyX", "Federation", "Galaxy", MVShields=60, NotAModule=1)
	C.g_lModules = [("MVShields", None), ("AutoFire", None)]
	return C


def test_techs_precedence_one_level_at_a_time():
	assert tech_core(All={"MVShields": 30}).GetShipTechs("GalaxyX")["MVShields"] == 60		# plugin beats All
	C, App = load_core([], All={"MVShields": 30}, Races={"Federation": {"MVShields": 50}})
	plugin("Plain", "Federation", "N/A")
	C.g_lModules = [("MVShields", None)]
	assert C.GetShipTechs("Plain")["MVShields"] == 50
	C, App = load_core([], All={"MVShields": 30}, Races={"Federation": {"MVShields": 50}},
		Families={"Galaxy": {"MVShields": 70}})
	plugin("Fam", "Federation", "Galaxy")
	C.g_lModules = [("MVShields", None)]
	assert C.GetShipTechs("Fam")["MVShields"] == 70


def test_techs_plugin_beats_family_and_ships_beats_plugin():
	kw = dict(All={"MVShields": 30}, Races={"Federation": {"MVShields": 50}},
		Families={"Galaxy": {"MVShields": 70}})
	C = tech_core(**kw)
	assert C.GetShipTechs("GalaxyX")["MVShields"] == 60		# 60 < 70: order, not max
	C = tech_core(Ships={"GalaxyX": {"MVShields": 90}}, **kw)
	assert C.GetShipTechs("GalaxyX")["MVShields"] == 90


def test_techs_zero_switches_off_at_any_level():
	C = tech_core(All={"MVShields": 30}, Ships={"GalaxyX": {"MVShields": 0}})
	d = C.GetShipTechs("GalaxyX")
	assert "MVShields" in d and d["MVShields"] == 0
	C, App = load_core([], All={"MVShields": 30}, Races={"Federation": {"MVShields": 0}})
	plugin("Plain", "Federation", "N/A")
	C.g_lModules = [("MVShields", None)]
	assert C.GetShipTechs("Plain")["MVShields"] == 0
	C = tech_core(Races={"Federation": {"MVShields": 50}}, Ships={"GalaxyX": {"MVShields": 0}})
	assert C.GetShipTechs("GalaxyX")["MVShields"] == 0


def test_techs_levels_merge_instead_of_replace():
	C = tech_core(All={"AutoFire": 5}, Ships={"GalaxyX": {"AblativeArmor": -1}})
	assert C.GetShipTechs("GalaxyX") == {"AutoFire": 5, "MVShields": 60, "AblativeArmor": -1}


def test_techs_plugin_only_counts_for_loaded_module_names():
	C = tech_core()
	assert "NotAModule" not in C.GetShipTechs("GalaxyX")


def test_techs_cached_and_unknown_ship_gets_all_only():
	C = tech_core(All={"AutoFire": 5})
	assert C.GetShipTechs("Stock") == {"AutoFire": 5}
	sys.modules["Custom.Spaceframe.Ships"].All = {"AutoFire": 9}
	assert C.GetShipTechs("Stock") == {"AutoFire": 5}
	assert C.GetShipTechs("") == {"AutoFire": 9}		# never asked before, so not cached


def test_get_ship_tech_default_and_filename():
	C = tech_core(Ships={"GalaxyX": {"MVShields": 7}})
	pShip = FakeShip("GalaxyX", 1)
	assert C.GetShipFileName(pShip) == "GalaxyX"
	assert C.GetShipTech(pShip, "MVShields") == 7
	assert C.GetShipTech(pShip, "Nope") == 0
	assert C.GetShipTech(pShip, "Nope", 5) == 5


# --- real modules: one ship raising inside a module's Tick ------------------------------------
class BadShields(FakeShields):
	def GetCurShields(self, i):
		raise RuntimeError("broken shield generator")


def real_aa():
	fake_ships.install_armor_api(sys.modules["App"])
	fake_ships.register_config("AblativeArmor", DefaultArmor=50, ArmorComplexity=200, BleedStart=50,
		BleedMax=50, SubsystemDamageCost=50, CreateSubsystem=0, Targetable=1)
	return mock_app.load_module("Modules/AblativeArmor/AblativeArmor.py", PKG + "AblativeArmor.AblativeArmor")


def real_mv():
	fake_ships.register_config("MVShields", DefaultEfficiency=100, Mode=3)
	return mock_app.load_module("Modules/MVShields/MVShields.py", PKG + "MVShields.MVShields")


def real_core():
	"""Core running the real AblativeArmor and MVShields over two ships."""
	techs = {"AblativeArmor": -1, "MVShields": -1}
	C, App = load_core([("AblativeArmor", real_aa), ("MVShields", real_mv)],
		Ships={"Alpha": techs, "Beta": dict(techs)})
	C.Start(object())
	AA = sys.modules[PKG + "AblativeArmor.AblativeArmor"]
	MV = sys.modules[PKG + "MVShields.MVShields"]
	return C, AA, MV


def unbalanced():
	return [100.0, 0.0, 0.0, 0.0, 0.0, 0.0]


def test_armor_ship_raising_in_tick_does_not_abort_the_rest_of_the_cycle():
	# FIXED: each ship is guarded on its own; a ship whose subsystem raises
	# is logged and the ships after it in the list are still protected.
	C, AA, MV = real_core()
	a = FakeShip("Alpha", 1, 1000.0, [("Phasers", 100.0)])
	b = FakeShip("Beta", 2, 1000.0, [("Phasers", 100.0)])
	tick_all(C, 1, [a, b])
	assert sorted(AA.g_dShips.keys()) == [1, 2]
	a.Sub("Phasers").bRaise = 1
	b.hull.fCond = 900.0
	tick_all(C, 3, [a, b])
	assert entry(C, "AblativeArmor")[3] == 0		# no error reaches the core
	assert b.hull.fCond == 1000.0		# Beta's damage was absorbed
	assert C.GetModule("AblativeArmor") != None


def test_armor_stale_records_not_cleaned_when_a_ship_raises():
	C, AA, MV = real_core()
	a = FakeShip("Alpha", 1, 1000.0, [("Phasers", 100.0)])
	gone = FakeShip("Beta", 2, 1000.0, [("Phasers", 100.0)])
	tick_all(C, 1, [a, gone])
	a.Sub("Phasers").bRaise = 1
	tick_all(C, 1, [a])
	assert 2 not in AA.g_dShips		# FIXED: the cleanup runs even when a ship errored


def test_armor_ship_that_errors_keeps_its_record():
	C, AA, MV = real_core()
	a = FakeShip("Alpha", 1, 1000.0, [("Phasers", 100.0)])
	tick_all(C, 1, [a])
	pRec = AA.g_dShips[1]
	a.Sub("Phasers").bRaise = 1
	tick_all(C, 2, [a])
	assert AA.g_dShips[1] is pRec


def test_mvshields_ship_raising_in_tick_does_not_abort_the_rest_of_the_cycle():
	# FIXED: MVShields.Tick guards each ship on its own: a failing shield
	# generator no longer keeps later ships from being equalized.
	C, AA, MV = real_core()
	a = FakeShip("Alpha", 1, 1000.0, [("Phasers", 100.0)], BadShields([100.0] * 6, unbalanced()))
	b = FakeShip("Beta", 2, 1000.0, [("Phasers", 100.0)], FakeShields([100.0] * 6, unbalanced()))
	tick_all(C, 2, [a, b])
	assert entry(C, "MVShields")[3] == 0
	assert b.shields.writes != []


def test_armor_error_does_not_stop_mvshields():
	C, AA, MV = real_core()
	a = FakeShip("Alpha", 1, 1000.0, [("Phasers", 100.0)])
	b = FakeShip("Beta", 2, 1000.0, [("Phasers", 100.0)], FakeShields([100.0] * 6, unbalanced()))
	tick_all(C, 1, [a, b])
	a.Sub("Phasers").bRaise = 1
	tick_all(C, 1, [a, b])
	assert entry(C, "AblativeArmor")[3] == 0
	assert entry(C, "MVShields")[3] == 0 and b.shields.writes != []


def run():
	return fake_ships.run(globals())


if __name__ == "__main__":
	sys.exit(run())
