"""Task 3 tests: SecondaryTarget candidates, free weapons, wanted targets."""
import builtins
import os
import sys
import types
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mock_app

builtins.reload = lambda m: m
builtins.apply = lambda f, a: f(*a)

PKG = "Custom.Spaceframe.Modules.SecondaryTarget"
AFPKG = "Custom.Spaceframe.Modules.AutoFire"


class ReachBank(mock_app.Bank):
	"""A bank that reaches only the points whose x is in lReach."""
	def __init__(self, lReach, fMax=100.0):
		mock_app.Bank.__init__(self, fMax)
		self.lReach = lReach

	def CanHit(self, pPoint):
		return pPoint.x in self.lReach


class BadBank(ReachBank):
	def CanHit(self, pPoint):
		raise RuntimeError("engine error")


def make_config(**kw):
	c = types.ModuleType(PKG + ".Config")
	c.Weapons = 7
	c.Interval = 0.2
	c.MaxCandidates = 4
	c.SecondaryRange = 100
	c.SecondaryTorpedoMinSolution = 70
	c.Debug = 0
	for k in kw:
		setattr(c, k, kw[k])
	return c


def register_packages(cfg, bAutoFire=1):
	names = ["Custom", "Custom.Spaceframe", "Custom.Spaceframe.Modules", PKG, AFPKG]
	for n in names:
		if n not in sys.modules:
			sys.modules[n] = types.ModuleType(n)
	sys.modules["Custom"].Spaceframe = sys.modules["Custom.Spaceframe"]
	sys.modules["Custom.Spaceframe"].Modules = sys.modules["Custom.Spaceframe.Modules"]
	sys.modules["Custom.Spaceframe.Modules"].SecondaryTarget = sys.modules[PKG]
	sys.modules["Custom.Spaceframe.Modules"].AutoFire = sys.modules[AFPKG]
	sys.modules[PKG + ".Config"] = cfg
	sys.modules[PKG].Config = cfg
	if AFPKG + ".AutoFire" in sys.modules:
		del sys.modules[AFPKG + ".AutoFire"]
	if hasattr(sys.modules[AFPKG], "AutoFire"):
		del sys.modules[AFPKG].AutoFire
	if bAutoFire:
		return mock_app.load_module("Modules/AutoFire/AutoFire.py", AFPKG + ".AutoFire")
	return None


def setup(bAutoFire=1, **kw):
	App = mock_app.make_app()
	mock_app.install(App)
	AF = register_packages(make_config(**kw), bAutoFire)
	if AF != None:
		sys.modules[AFPKG].AutoFire = AF
	ST = mock_app.load_module("Modules/SecondaryTarget/SecondaryTarget.py", PKG + ".SecondaryTarget")
	core = mock_app.Core()
	ship = mock_app.Ship("Galaxy", 1)
	App._player[0] = ship
	ST.g_pCore = core
	if AF != None:
		AF.g_pCore = core
	return App, ST, AF, core, ship


def enemy(sName, iID, fX):
	pShip = mock_app.Ship(sName, iID)
	pShip.pos = mock_app.Point(fX, 0.0, 0.0)
	return pShip


def group(lWeapons, bPulse=0):
	pGroup = mock_app.WeaponGroup(lWeapons)
	pGroup.pulse = bPulse
	return pGroup


def ids(lShips):
	return [p.GetObjID() for p in lShips]


def test_main_excluded():
	App, ST, AF, core, ship = setup()
	main = enemy("Main", 2, 10.0)
	other = enemy("Other", 3, 20.0)
	core.g_pMission = mock_app.Mission([main, other])
	pSys = group([ReachBank([20.0])])
	assert ids(ST.GetCandidates(ship, main, pSys, "phaser")) == [3]


def test_friendly_and_neutral_never_candidates():
	App, ST, AF, core, ship = setup()
	main = enemy("Main", 2, 10.0)
	friend = enemy("Friend", 3, 12.0)
	neutral = enemy("Neutral", 4, 14.0)
	core.g_pMission = mock_app.Mission([main], [friend])
	pSys = group([ReachBank([])])
	assert ST.GetCandidates(ship, main, pSys, "phaser") == []
	assert ST.GetCandidates(ship, main, pSys, "pulse") == []
	assert ST.WantedTargets(ship, pSys, main, "pulse") == []


def test_max_candidates_nearest():
	App, ST, AF, core, ship = setup(MaxCandidates=2)
	ST.LoadConfig()
	main = enemy("Main", 2, 5.0)
	far = enemy("Far", 3, 50.0)
	near = enemy("Near", 4, 10.0)
	mid = enemy("Mid", 5, 20.0)
	core.g_pMission = mock_app.Mission([main, far, near, mid])
	pSys = group([ReachBank([])], 1)
	assert ids(ST.GetCandidates(ship, main, pSys, "pulse")) == [4, 5]


def test_phaser_range_filter():
	App, ST, AF, core, ship = setup(SecondaryRange=50)
	ST.LoadConfig()
	main = enemy("Main", 2, 5.0)
	inside = enemy("In", 3, 30.0)
	outside = enemy("Out", 4, 80.0)
	core.g_pMission = mock_app.Mission([main, inside, outside])
	pSys = group([ReachBank([], 100.0)])
	# limit 50 units from the ship, to the hull (radius 1)
	assert ids(ST.GetCandidates(ship, main, pSys, "phaser")) == [3]


def test_weapon_reaching_main_is_not_free():
	App, ST, AF, core, ship = setup()
	main = enemy("Main", 2, 10.0)
	core.g_pMission = mock_app.Mission([main])
	bReach = ReachBank([10.0])
	bFree = ReachBank([20.0])
	pSys = group([bReach, bFree])
	assert ST.FreeWeapons(pSys, main, "phaser") == [bFree]
	assert ST.FreeWeapons(pSys, None, "phaser") == []


def test_candidate_needs_a_free_weapon_that_reaches():
	App, ST, AF, core, ship = setup()
	main = enemy("Main", 2, 10.0)
	b = enemy("B", 3, 20.0)
	c = enemy("C", 4, 30.0)
	core.g_pMission = mock_app.Mission([main, b, c])
	# the first bank reaches main and C (so it is reserved for main),
	# the second only B: C has no FREE weapon that reaches it
	pSys = group([ReachBank([10.0, 30.0]), ReachBank([20.0])])
	assert ST.WantedTargets(ship, pSys, main, "phaser") == [3]
	# every weapon reaches main: no free weapon, nothing wanted
	pAll = group([ReachBank([10.0, 20.0])])
	assert ST.WantedTargets(ship, pAll, main, "phaser") == []


def test_no_enemies_returns_empty():
	App, ST, AF, core, ship = setup()
	main = enemy("Main", 2, 10.0)
	core.g_pMission = mock_app.Mission([main])
	pSys = group([ReachBank([])])
	assert ST.GetCandidates(ship, main, pSys, "phaser") == []
	assert ST.WantedTargets(ship, pSys, main, "phaser") == []


def test_pulse_treats_all_weapons_free():
	App, ST, AF, core, ship = setup()
	main = enemy("Main", 2, 10.0)
	b = enemy("B", 3, 500.0)
	core.g_pMission = mock_app.Mission([main, b])
	w1 = mock_app.Pulse()
	w2 = mock_app.Pulse()
	pSys = group([w1, w2], 1)
	assert ST.FreeWeapons(pSys, main, "pulse") == [w1, w2]
	assert ST.WantedTargets(ship, pSys, main, "pulse") == [3]


def test_dead_and_cloaked_not_candidates():
	App, ST, AF, core, ship = setup()
	main = enemy("Main", 2, 10.0)
	dead = enemy("Dead", 3, 12.0)
	dead.dead = 1
	cloaked = enemy("Cloak", 4, 14.0)
	cloaked.cloaked = 1
	core.g_pMission = mock_app.Mission([main, dead, cloaked])
	pSys = group([mock_app.Pulse()], 1)
	assert ST.GetCandidates(ship, main, pSys, "pulse") == []


def test_engine_error_returns_empty():
	App, ST, AF, core, ship = setup()
	main = enemy("Main", 2, 10.0)
	b = enemy("B", 3, 20.0)
	core.g_pMission = mock_app.Mission([main, b])
	pSys = group([BadBank([])])
	assert ST.FreeWeapons(pSys, main, "phaser") == []
	assert ST.WantedTargets(ship, pSys, main, "phaser") == []
	assert ST.GetCandidates(ship, main, None, "phaser") == []
	assert ST.GetCandidates(ship, main, pSys, "torpedo") == []


def test_autofire_import_failure_disables_and_logs_once():
	App, ST, AF, core, ship = setup(bAutoFire=0)
	main = enemy("Main", 2, 10.0)
	b = enemy("B", 3, 20.0)
	pSys = group([ReachBank([])], 1)
	assert ST.GetCandidates(ship, main, pSys, "pulse") == []
	assert ST.GetCandidates(ship, main, pSys, "pulse") == []
	assert ST.WantedTargets(ship, pSys, main, "pulse") == []
	n = 0
	for t in core.logs:
		if t[0] == "SecondaryTarget":
			n = n + 1
	assert n == 1


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
