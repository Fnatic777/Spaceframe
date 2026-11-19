"""Task 4 tests: SecondaryTarget cycle (target list maintenance)."""
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
LOG = []	# engine calls that change something: (what, group id, ...)


class FakeProp:
	def __init__(self, sTag, iSingle=1):
		self.sTag = sTag
		self.iSingle = iSingle

	def IsSingleFire(self):
		return self.iSingle

	def SetSingleFire(self, i):
		LOG.append(("single", self.sTag, i))
		self.iSingle = i


class ListGroup(mock_app.WeaponGroup):
	"""A weapon group with the engine's target list."""
	def __init__(self, lWeapons, sTag, bPulse=0):
		mock_app.WeaponGroup.__init__(self, lWeapons)
		self.pulse = bPulse
		self.sTag = sTag
		self.lTargets = []
		self.pProp = FakeProp(sTag)
		self.bFailStart = 0

	def GetProperty(self):
		return self.pProp

	def IsInTargetList(self, pTarget):
		return pTarget in self.lTargets

	def StartFiring(self, pTarget, vOffset):
		LOG.append(("start", self.sTag, pTarget.GetObjID()))
		if self.bFailStart:
			raise RuntimeError("start failed")
		if pTarget not in self.lTargets:
			self.lTargets.append(pTarget)
		self.firing = 1

	def StopFiringAtTarget(self, pTarget):
		LOG.append(("stopat", self.sTag, pTarget.GetObjID()))
		if pTarget in self.lTargets:
			self.lTargets.remove(pTarget)

	def Press(self, pMain):
		# What the game does on a key press: the main target in the list.
		self.lTargets = [pMain]
		self.firing = 1

	def Release(self):
		# What the game does on the key release: stop and empty the list.
		self.lTargets = []
		self.firing = 0

	def ids(self):
		return [p.GetObjID() for p in self.lTargets]


class ReachBank(mock_app.Bank):
	def __init__(self, lReach, fMax=100.0):
		mock_app.Bank.__init__(self, fMax)
		self.lReach = lReach

	def CanHit(self, pPoint):
		return pPoint.x in self.lReach


class CountDict(dict):
	def __init__(self):
		dict.__init__(self)
		self.n = 0

	def get(self, k, d=None):
		self.n = self.n + 1
		return dict.get(self, k, d)


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


def setup(iTech=-1, **kw):
	del LOG[:]
	App = mock_app.make_app()
	mock_app.install(App)
	for n in ["Custom", "Custom.Spaceframe", "Custom.Spaceframe.Modules", PKG, AFPKG]:
		if n not in sys.modules:
			sys.modules[n] = types.ModuleType(n)
	sys.modules["Custom"].Spaceframe = sys.modules["Custom.Spaceframe"]
	sys.modules["Custom.Spaceframe"].Modules = sys.modules["Custom.Spaceframe.Modules"]
	sys.modules["Custom.Spaceframe.Modules"].SecondaryTarget = sys.modules[PKG]
	sys.modules["Custom.Spaceframe.Modules"].AutoFire = sys.modules[AFPKG]
	cfg = make_config(**kw)
	sys.modules[PKG + ".Config"] = cfg
	sys.modules[PKG].Config = cfg
	AF = mock_app.load_module("Modules/AutoFire/AutoFire.py", AFPKG + ".AutoFire")
	sys.modules[AFPKG].AutoFire = AF
	ST = mock_app.load_module("Modules/SecondaryTarget/SecondaryTarget.py", PKG + ".SecondaryTarget")
	core = mock_app.Core()
	ship = mock_app.Ship("Galaxy", 1)
	ship.groups = CountDict()
	if iTech != None:
		core.techs["Galaxy"] = {"SecondaryTarget": iTech}
	App._player[0] = ship
	ST.g_pCore = core
	AF.g_pCore = core
	ST.LoadConfig()
	ST.g_iOn = 1	# the module is switched ON (the cycle does nothing otherwise)
	return App, ST, core, ship


def enemy(sName, iID, fX):
	pShip = mock_app.Ship(sName, iID)
	pShip.pos = mock_app.Point(fX, 0.0, 0.0)
	return pShip


def scene(core, ship, **kw):
	"""Main at x=10 (the bank does not reach it), B at 20, C at 30."""
	main = enemy("Main", 2, 10.0)
	b = enemy("B", 3, 20.0)
	c = enemy("C", 4, 30.0)
	core.g_pMission = mock_app.Mission([main, b, c])
	ship.target = main
	pSys = ListGroup([ReachBank([20.0, 30.0])], "g0")
	ship.groups[0] = pSys
	return main, b, c, pSys


def calls(sWhat):
	n = []
	for t in LOG:
		if t[0] == sWhat:
			n.append(t)
	return n


def test_secondaries_added_in_order_after_main():
	App, ST, core, ship = setup()
	main, b, c, pSys = scene(core, ship)
	pSys.Press(main)
	ST.Cycle()
	assert pSys.ids() == [2, 3, 4]
	assert [t[2] for t in calls("start")] == [3, 4]
	# the single-fire restriction was lifted once
	assert calls("single") == [("single", "g0", 0)]


def test_group_not_firing_untouched():
	App, ST, core, ship = setup()
	main, b, c, pSys = scene(core, ship)
	ST.Cycle()
	ST.Cycle()
	# only the single-fire lift (ON), no target list change
	assert LOG == [("single", "g0", 0)]
	assert pSys.lTargets == []
	# firing, but not at the player's selected target: still untouched
	pSys.firing = 1
	pSys.lTargets = [b]
	ST.Cycle()
	assert LOG == [("single", "g0", 0)]


def test_key_release_list_cleared_then_readded_once():
	App, ST, core, ship = setup()
	main, b, c, pSys = scene(core, ship)
	pSys.Press(main)
	ST.Cycle()
	assert len(calls("start")) == 2
	pSys.Release()
	ST.Cycle()
	assert len(calls("start")) == 2
	pSys.Press(main)
	ST.Cycle()
	ST.Cycle()
	assert len(calls("start")) == 4
	assert pSys.ids() == [2, 3, 4]


def test_main_dies_group_continues():
	App, ST, core, ship = setup()
	main, b, c, pSys = scene(core, ship)
	pSys.Press(main)
	ST.Cycle()
	del LOG[:]
	main.dead = 1
	ST.Cycle()
	# main gone: the secondaries are taken back; single-fire stays lifted (ON)
	assert [t[2] for t in calls("stopat")] == [3, 4]
	assert pSys.ids() == [2]
	assert pSys.pProp.iSingle == 0
	assert ST.g_dLifted == {1: {0: 1}}
	assert ST.g_dAdded == {}
	# the player picks B: nothing is re-added by a stale record
	del LOG[:]
	ship.target = b
	ST.Cycle()
	assert calls("stopat") == []
	assert 2 not in [t[2] for t in calls("stopat")]


def test_candidate_gone_removed_from_list():
	App, ST, core, ship = setup()
	main, b, c, pSys = scene(core, ship)
	pSys.Press(main)
	ST.Cycle()
	b.dead = 1
	ST.Cycle()
	assert [t[2] for t in calls("stopat")] == [3]
	assert pSys.ids() == [2, 4]
	assert 2 not in [t[2] for t in calls("stopat")]


def test_no_duplicate_start_for_listed_targets():
	App, ST, core, ship = setup()
	main, b, c, pSys = scene(core, ship)
	pSys.Press(main)
	pSys.lTargets.append(b)
	ST.Cycle()
	ST.Cycle()
	assert [t[2] for t in calls("start")] == [4]


def test_group_error_isolated():
	App, ST, core, ship = setup()
	main, b, c, pSys = scene(core, ship)
	pSys.bFailStart = 1
	pPulse = ListGroup([mock_app.Pulse()], "g1", 1)
	ship.groups[1] = pPulse
	pSys.Press(main)
	pPulse.Press(main)
	ST.Cycle()
	assert pPulse.ids() == [2, 3, 4]
	assert len(calls("start")) >= 3


def test_player_ship_change_restores_only_if_live():
	App, ST, core, ship = setup()
	main, b, c, pSys = scene(core, ship)
	pSys.Press(main)
	ST.Cycle()
	assert pSys.pProp.iSingle == 0
	other = mock_app.Ship("Galaxy", 7)
	core.techs["Galaxy"] = {"SecondaryTarget": -1}
	App._player[0] = other
	ST.Cycle()
	assert pSys.pProp.iSingle == 1
	assert ST.g_dLifted == {}
	# second case: the old ship is gone, nothing is asked of it
	App, ST, core, ship = setup()
	main, b, c, pSys = scene(core, ship)
	pSys.Press(main)
	ST.Cycle()
	del LOG[:]
	del mock_app.SHIPS[1]
	App._player[0] = mock_app.Ship("Galaxy", 8)
	ST.Cycle()
	assert LOG == []
	assert ST.g_dLifted == {}


def test_idle_cost_no_calls_without_tech():
	App, ST, core, ship = setup(iTech=None)
	main, b, c, pSys = scene(core, ship)
	pSys.Press(main)
	ST.Cycle()
	ST.Cycle()
	assert LOG == []
	assert ship.groups.n == 0


def test_tech_mask_selects_kinds():
	App, ST, core, ship = setup(iTech=4)
	main, b, c, pSys = scene(core, ship)
	pPulse = ListGroup([mock_app.Pulse()], "g1", 1)
	ship.groups[1] = pPulse
	pSys.Press(main)
	pPulse.Press(main)
	ST.Cycle()
	assert pSys.ids() == [2]
	assert pPulse.ids() == [2, 3, 4]


def test_preconditions_restore_and_do_nothing():
	App, ST, core, ship = setup()
	main, b, c, pSys = scene(core, ship)
	pSys.Press(main)
	ST.Cycle()
	assert pSys.pProp.iSingle == 0
	ship.alert = 0
	pSys.Release()
	pSys.Press(main)
	ST.Cycle()
	# below red alert: secondaries removed, single-fire still lifted (ON)
	assert pSys.pProp.iSingle == 0
	assert pSys.ids() == [2]
	assert ST.g_dAdded == {}
	# an ally selected as main target: nothing
	ship.alert = 2
	friend = enemy("Friend", 9, 5.0)
	ship.target = friend
	del LOG[:]
	pSys.Press(friend)
	ST.Cycle()
	assert LOG == []


def test_no_wanted_target_still_lifted_once_no_secondary():
	# Lifted for as long as the module is ON, whether or not a secondary is wanted.
	App, ST, core, ship = setup()
	main, b, c, pSys = scene(core, ship)
	pSys2 = ListGroup([ReachBank([10.0, 20.0, 30.0])], "g0")
	ship.groups[0] = pSys2
	pSys2.Press(main)
	ST.Cycle()
	ST.Cycle()
	assert calls("single") == [("single", "g0", 0)]
	assert calls("start") == []
	assert ST.g_dLifted == {1: {0: 1}}


def test_wanted_appears_then_disappears_lifted_once_never_restored_by_cycle():
	App, ST, core, ship = setup()
	main, b, c, pSys = scene(core, ship)
	pSys.Press(main)
	ST.Cycle()
	ST.Cycle()
	assert calls("single") == [("single", "g0", 0)]
	b.dead = 1
	c.dead = 1
	ST.Cycle()
	ST.Cycle()
	ST.Cycle()
	assert calls("single") == [("single", "g0", 0)]
	assert pSys.pProp.iSingle == 0
	assert pSys.ids() == [2]
	assert ST.g_dLifted == {1: {0: 1}}


def test_group_stops_firing_single_fire_stays_lifted():
	App, ST, core, ship = setup()
	main, b, c, pSys = scene(core, ship)
	pSys.Press(main)
	ST.Cycle()
	assert pSys.pProp.iSingle == 0
	pSys.Release()
	ST.Cycle()
	ST.Cycle()
	assert pSys.pProp.iSingle == 0
	assert ST.g_dLifted == {1: {0: 1}}
	assert calls("single") == [("single", "g0", 0)]


def test_main_not_enemy_releases_secondaries():
	App, ST, core, ship = setup()
	main, b, c, pSys = scene(core, ship)
	pSys.Press(main)
	ST.Cycle()
	friend = enemy("Friend", 9, 5.0)
	ship.target = friend
	ST.Cycle()
	assert pSys.ids() == [2]
	assert pSys.pProp.iSingle == 0
	assert ST.g_dAdded == {}


def test_on_fire_key_always_calls_next_handler():
	App, ST, core, ship = setup()
	main, b, c, pSys = scene(core, ship)
	pSys.Press(main)
	ST.Cycle()
	seen = []

	class Obj:
		def CallNextHandler(self, pEvent):
			seen.append(pEvent)

	class Bad:
		def CallNextHandler(self, pEvent):
			raise RuntimeError("x")

	ST.OnFireKey(Obj(), "not an event")
	ev = mock_app.Event(App.ET_INPUT_FIRE_PRIMARY, 0)
	ST.OnFireKey(Obj(), ev)
	ST.OnFireKey(Bad(), ev)
	assert len(seen) == 2
	assert ST.g_dAdded == {}
	assert LOG[-1][0] == "start"	# the handler itself touched no list


def test_debug_banner_once_per_change():
	App, ST, core, ship = setup(Debug=1)
	lShown = []
	sys.modules["MissionLib"].TextBanner = lambda *a: lShown.append(a[1].s)
	main, b, c, pSys = scene(core, ship)
	pSys.Press(main)
	ST.Cycle()
	ST.Cycle()
	assert len(lShown) == 1
	assert "+3,4" in lShown[0]
	b.dead = 1
	ST.Cycle()
	assert len(lShown) == 2
	assert "-3" in lShown[1]


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
