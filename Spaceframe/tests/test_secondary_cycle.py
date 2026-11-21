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

	def SetForceUpdate(self, i):
		LOG.append(("force", self.sTag, i))

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
	c.SecondaryTorpedoRange = 30
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
	AF.ArcRuleOn = lambda sKind: 0	# arc rule is always on in AutoFire now: these tests cover the non-arc path; arc tests set their own stubs
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
	lBanner = []
	# the separate banner is gone: the change goes to DebugPrint (and the ADD/DEL trace lines)
	sys.modules["MissionLib"].TextBanner = lambda *a: lBanner.append(a[1].s)
	ST.DebugPrint = lShown.append
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
	assert lBanner == []	# nothing on screen until the trace idles


def torp_scene(core, ship, iEgroup=2):
	"""Main at x=10 (ahead), B at x=20 (ahead), C at x=-20 (behind). One
	forward tube and one aft tube in the torpedo group."""
	main = enemy("Main", 2, 10.0)
	b = enemy("B", 3, 20.0)
	c = enemy("C", 4, -20.0)
	core.g_pMission = mock_app.Mission([main, b, c])
	ship.target = main
	tFwd = mock_app.Tube()
	tAft = mock_app.Tube(mock_app.Point(-1.0, 0.0, 0.0))
	pSys = ListGroup([tFwd, tAft], "gt")
	pSys.torpedo = 1
	ship.groups[iEgroup] = pSys
	return main, b, c, pSys


def test_torpedo_group_gets_only_reachable_secondaries():
	App, ST, core, ship = setup()
	main, b, c, pSys = torp_scene(core, ship)
	pSys.Press(main)
	ST.Cycle()
	# only the aft tube is free and it reaches C, not B
	assert pSys.ids() == [2, 4]
	assert [t[2] for t in calls("start")] == [4]
	ST.Cycle()
	assert len(calls("start")) == 1
	# key release empties the list: re-added once when fired again
	pSys.Release()
	ST.Cycle()
	assert pSys.ids() == []
	pSys.Press(main)
	ST.Cycle()
	assert pSys.ids() == [2, 4]


def state_scene(iDebug):
	# banners need Debug 2
	App, ST, core, ship = setup(Debug=iDebug * 2)
	lShown = []
	# the rare "Secondary target: group ..." banner is not part of the trace display
	sys.modules["MissionLib"].TextBanner = lambda *a: (a[4] > 5.0) and lShown.append((a[1].s, a[3], a[4]))
	CLOCK = [100.0]
	App.g_kUtopiaModule.GetGameTime = lambda: CLOCK[0]
	main, b, c, pSys = torp_scene(core, ship)
	pSys.Press(main)
	return ST, pSys, lShown, CLOCK


def test_state_banner_text_and_throttle():
	ST, pSys, lShown, CLOCK = state_scene(1)
	ST.Cycle()
	assert ST.g_lTrace == ["t=0.0 T2 f1 M:in S:in fwd=1 free=1 ff=0", "t=0.0 ADD 4"], ST.g_lTrace
	ST.Cycle()
	CLOCK[0] = 100.4
	ST.Cycle()
	assert len(ST.g_lTrace) == 2
	CLOCK[0] = 100.5
	ST.Cycle()
	assert len(ST.g_lTrace) == 2	# same state within 2.0 s: compressed
	CLOCK[0] = 101.9
	ST.Cycle()
	assert len(ST.g_lTrace) == 2
	assert [s for s in ST.g_lTrace if "FWD EMPTY" in s] == []
	assert lShown == []	# nothing on screen until idle
	CLOCK[0] = 103.0	# idle for 3.0 s: shown (and cleared) before anything new
	ST.Cycle()
	assert len(lShown) == 2 and lShown[0][0] == "t=0.0 T2 f1 M:in S:in fwd=1 free=1 ff=0"
	assert len(ST.g_lTrace) == 1	# cleared, then only the fresh refresh line of the new trace


def test_trace_lines_reach_the_core_log_once():
	ST, pSys, lShown, CLOCK = state_scene(1)
	core = ST.g_pCore
	ST.Cycle()
	lTrace = list(ST.g_lTrace)
	assert len(lTrace) == 2
	lLogged = [t[1] for t in core.logs]
	for s in ("T2 f1 M:in S:in fwd=1 free=1 ff=0", "ADD 4"):
		assert lLogged.count(s) == 1, lLogged
	CLOCK[0] = 103.5
	ST.Cycle()		# idle: ShowTrace runs
	assert len(lShown) == 2
	lLogged = [t[1] for t in core.logs]
	assert lLogged.count("ADD 4") == 1	# ShowTrace did not log it again
	assert [s for s in lLogged if s.startswith("t=")] == []
	assert lLogged.count("Cycle: main target ok") == 1	# idle cycles stay silent


def test_state_changed_text_is_appended():
	ST, pSys, lShown, CLOCK = state_scene(1)
	ST.Cycle()
	assert len(ST.g_lTrace) == 2
	pSys.lChildren[0].iReady = 0	# fwd=1 -> fwd=0
	CLOCK[0] = 100.5
	ST.Cycle()
	assert len([s for s in ST.g_lTrace if "fwd=0" in s]) == 1, ST.g_lTrace


def test_state_fwd_empty_once_per_press():
	ST, pSys, lShown, CLOCK = state_scene(1)
	pSys.lChildren[0].iReady = 0
	ST.Cycle()
	CLOCK[0] = 101.0
	ST.Cycle()
	assert len([s for s in ST.g_lTrace if "FWD EMPTY" in s]) == 1
	pSys.Release()
	ST.Cycle()
	CLOCK[0] = 104.1
	ST.Cycle()
	assert len([s for s in lShown if "FWD EMPTY" in s[0]]) == 1
	assert ST.g_lTrace == []
	pSys.Press(ST.Lookup(2))
	ST.Cycle()
	assert len([s for s in ST.g_lTrace if "FWD EMPTY" in s]) == 1


def test_state_nothing_with_debug_off():
	ST, pSys, lShown, CLOCK = state_scene(0)
	pSys.lChildren[0].iReady = 0
	ST.Cycle()
	pSys.Release()
	ST.Cycle()
	assert lShown == []
	assert ST.g_lTrace == []
	assert ST.g_dStateAt == {}


def test_trace_add_del_lines():
	ST, pSys, lShown, CLOCK = state_scene(1)
	ST.Cycle()
	ST.Lookup(4).dead = 1
	CLOCK[0] = 101.0
	ST.Cycle()
	assert [s for s in ST.g_lTrace if "ADD 4" in s] == ["t=0.0 ADD 4"]
	assert [s for s in ST.g_lTrace if "DEL 4" in s] == ["t=1.0 DEL 4"], ST.g_lTrace


def test_trace_shown_by_cycle_after_2s_idle_once_last_15():
	ST, pSys, lShown, CLOCK = state_scene(1)
	for i in range(30):
		CLOCK[0] = 100.0 + 1.0 * i	# a new line every second: never idle 2.0 s
		ST.TraceAdd("x" + str(i))
		ST.Cycle()
	lTrace = list(ST.g_lTrace)
	assert len(lTrace) > 12
	assert lShown == []	# lines keep coming: never idle 2.0 s
	pSys.Release()
	CLOCK[0] = 130.0
	ST.Cycle()		# appends STOP at 130.0
	assert lShown == []
	CLOCK[0] = 132.9
	ST.Cycle()
	assert lShown == []
	lAll = list(ST.g_lTrace)
	CLOCK[0] = 133.0
	ST.Cycle()
	assert [t[0] for t in lShown] == lAll[-15:]
	lY = [t[1] for t in lShown]
	assert len(lY) == 15
	for i in range(15):
		assert abs(lY[i] - (0.03 + 0.03 * i)) < 0.0001
	assert abs(lY[-1] - 0.45) < 0.0001
	assert lShown[0][2] == 15.0
	assert ST.g_lTrace == []
	CLOCK[0] = 170.0
	ST.Cycle()
	assert len(lShown) == 15	# shown once


def test_trace_collapses_consecutive_identical_lines():
	ST, pSys, lShown, CLOCK = state_scene(1)
	ST.TraceAdd("KEY up g2")
	assert ST.g_lTrace == ["t=0.0 KEY up g2"]
	CLOCK[0] = 101.0
	ST.TraceAdd("KEY up g2")
	assert ST.g_lTrace == ["t=0.0 KEY up g2 x2"], ST.g_lTrace
	assert ST.g_fTraceLast == 101.0
	for i in range(4):
		CLOCK[0] = 102.0 + i
		ST.TraceAdd("KEY up g2")
	assert ST.g_lTrace == ["t=0.0 KEY up g2 x6"], ST.g_lTrace
	assert ST.g_fTraceLast == 105.0
	# non-consecutive duplicates are kept
	ST.TraceAdd("KEY dn g2")
	ST.TraceAdd("KEY up g2")
	assert len(ST.g_lTrace) == 3
	assert ST.g_lTrace[2].endswith("KEY up g2") and "x" not in ST.g_lTrace[2]
	# a new trace after clearing starts fresh
	ST.ShowTrace()
	ST.TraceAdd("KEY up g2")
	assert len(ST.g_lTrace) == 1 and "x" not in ST.g_lTrace[0]


def test_stop_line_carries_key_state():
	ST, pSys, lShown, CLOCK = state_scene(1)
	obj = type("O", (), {"CallNextHandler": lambda s, e: None})()
	ST.Cycle()
	ST.OnFireKey(obj, mock_app.Event(ST.GetFireEvents()[2][0], 1))
	pSys.Release()
	CLOCK[0] = 100.1
	ST.Cycle()
	assert len([s for s in ST.g_lTrace if "STOP g" in s and s.endswith("key=1")]) == 1, ST.g_lTrace
	ST, pSys, lShown, CLOCK = state_scene(1)
	ST.Cycle()
	ST.OnFireKey(obj, mock_app.Event(ST.GetFireEvents()[2][0], 1))
	ST.OnFireKey(obj, mock_app.Event(ST.GetFireEvents()[2][0], 0))
	ST.g_dAdded[(ST.g_iShipID, ST.GetFireEvents()[2][1])] = [4]	# the key-up forgot it: restore
	pSys.Release()
	CLOCK[0] = 100.1
	ST.Cycle()
	assert len([s for s in ST.g_lTrace if "STOP g" in s and s.endswith("key=0")]) == 1, ST.g_lTrace
	ST.ForgetAll()
	assert ST.g_dKeyHeld == {}


def test_key_lines_with_debug_only():
	ST, pSys, lShown, CLOCK = state_scene(1)
	ST.OnFireKey(mock_app.Obj() if hasattr(mock_app, "Obj") else type("O", (), {"CallNextHandler": lambda s, e: None})(), mock_app.Event(App_FIRE(ST), 1))
	ST.OnFireKey(type("O", (), {"CallNextHandler": lambda s, e: None})(), mock_app.Event(App_FIRE(ST), 0))
	assert len(ST.g_lTrace) == 2
	assert ST.g_lTrace[0].startswith("t=0.0 KEY dn g"), ST.g_lTrace
	assert " KEY up g" in ST.g_lTrace[1], ST.g_lTrace
	ST2, pSys2, lShown2, CLOCK2 = state_scene(0)
	ST2.OnFireKey(type("O", (), {"CallNextHandler": lambda s, e: None})(), mock_app.Event(App_FIRE(ST2), 1))
	assert ST2.g_lTrace == []


def App_FIRE(ST):
	return ST.GetFireEvents()[0][0]


def test_stop_line_once_per_transition():
	ST, pSys, lShown, CLOCK = state_scene(1)
	ST.Cycle()
	pSys.Release()
	CLOCK[0] = 100.1
	ST.Cycle()
	ST.Cycle()
	CLOCK[0] = 100.2
	ST.Cycle()
	assert len([s for s in ST.g_lTrace if "STOP g" in s]) == 1, ST.g_lTrace
	assert lShown == []


def test_trace_toggle_off_shows_and_clears():
	ST, pSys, lShown, CLOCK = state_scene(1)
	ST.Cycle()
	ST.SetEnabled(0)
	assert len(lShown) == 2
	assert ST.g_lTrace == []


def test_trace_empty_shows_nothing_and_cap_60():
	ST, pSys, lShown, CLOCK = state_scene(1)
	ST.ShowTrace()
	assert lShown == []
	for i in range(75):
		ST.TraceAdd("x" + str(i))
	assert len(ST.g_lTrace) == 60
	assert ST.g_lTrace[-1].endswith("x74") and ST.g_lTrace[0].endswith("x15")


def test_torpedo_no_free_tube_adds_nothing():
	App, ST, core, ship = setup()
	main, b, c, pSys = torp_scene(core, ship)
	pSys.lChildren = [mock_app.Tube(), mock_app.Tube()]
	pSys.Press(main)
	ST.Cycle()
	assert pSys.ids() == [2]
	assert calls("start") == []


def test_torpedo_single_fire_never_lifted_or_restored():
	App, ST, core, ship = setup()
	main, b, c, pSys = torp_scene(core, ship)
	for iOrig in (0, 1):
		pSys.pProp.iSingle = iOrig
		pSys.Press(main)
		ST.Cycle()
		ST.Cycle()
		assert pSys.ids() == [2, 4]
		assert pSys.pProp.iSingle == iOrig
		assert ST.g_dLifted == {}
		assert calls("single") == []
		ST.TurnOff()
		assert pSys.pProp.iSingle == iOrig
		assert calls("single") == []
		assert pSys.ids() == [2]
		ST.g_iOn = 1


def test_torpedo_arc_error_adds_nothing_no_exception():
	App, ST, core, ship = setup()
	main, b, c, pSys = torp_scene(core, ship)
	pSys.lChildren[1].iArc = "raise"
	pSys.Press(main)
	ST.Cycle()
	assert pSys.ids() == [2]
	assert calls("start") == []


def test_torpedo_bit_off_ignores_torpedo_groups():
	# mask 5 = phasers + pulse
	App, ST, core, ship = setup(iTech=5)
	main, b, c, pSys = torp_scene(core, ship)
	pSys.Press(main)
	ST.Cycle()
	assert pSys.ids() == [2]
	assert calls("start") == []
	# mask 2 = torpedoes only: they work
	App, ST, core, ship = setup(iTech=2)
	main, b, c, pSys = torp_scene(core, ship)
	pSys.Press(main)
	ST.Cycle()
	assert pSys.ids() == [2, 4]


def test_mixed_ship_groups_independent_and_toggle_off_clears_all():
	App, ST, core, ship = setup()
	main = enemy("Main", 2, 10.0)
	b = enemy("B", 3, 20.0)
	c = enemy("C", 4, -20.0)
	core.g_pMission = mock_app.Mission([main, b, c])
	ship.target = main
	gp = ListGroup([ReachBank([20.0])], "gp")
	gu = ListGroup([mock_app.Pulse()], "gu", 1)
	gt = ListGroup([mock_app.Tube(), mock_app.Tube(mock_app.Point(-1.0, 0.0, 0.0))], "gt")
	gt.torpedo = 1
	ship.groups[0] = gp
	ship.groups[1] = gu
	ship.groups[2] = gt
	# only the phaser and torpedo groups fire
	gp.Press(main)
	gt.Press(main)
	ST.Cycle()
	assert gp.ids() == [2, 3]
	assert gt.ids() == [2, 4]
	assert gu.ids() == []
	# one group released: the other keeps its secondaries
	gp.Release()
	ST.Cycle()
	assert gp.ids() == []
	assert gt.ids() == [2, 4]
	gp.Press(main)
	ST.Cycle()
	assert gp.ids() == [2, 3]
	ST.TurnOff()
	assert gp.ids() == [2]
	assert gt.ids() == [2]
	assert ST.g_dAdded == {}
	assert ST.g_dLifted == {}


NULL = type("O", (), {"CallNextHandler": lambda s, e: None})()


REARM_DEFAULTS = []


def rearm_scene(iDebug=0, iFwdReady=0, iAftReady=2):
	"""Torpedo group (event group 2): forward tube at main/B, aft tube reaches C.
	The key of group 2 is down and the group is not firing (it just stopped)."""
	App, ST, core, ship = setup(Debug=iDebug)
	REARM_DEFAULTS.append((ST.REARM_MAX, ST.REARM_MAX_TIME, ST.REARM_STALE))
	ST.REARM_MAX = 6	# small limits keep the guard tests short
	ST.REARM_MAX_TIME = 8.0
	ST.REARM_STALE = 10.0
	CLOCK = [100.0]
	App.g_kUtopiaModule.GetGameTime = lambda: CLOCK[0]
	main, b, c, pSys = torp_scene(core, ship)
	pSys.lChildren[0].iReady = iFwdReady
	pSys.lChildren[1].iReady = iAftReady
	ST.OnFireKey(NULL, mock_app.Event(ST.GetFireEvents()[2][0], 1))
	return ST, ship, pSys, CLOCK, main


def test_rearm_default_limits_fit_a_full_volley():
	rearm_scene()
	iMax, fTime, fStale = REARM_DEFAULTS[-1]
	assert iMax >= 14 and fTime >= 15.0 and fStale > fTime


def test_rearm_torpedo_key_held_order_and_secondary():
	ST, ship, pSys, CLOCK, main = rearm_scene()
	ST.Cycle()
	assert [t[0] for t in LOG] == ["start", "force", "start"], LOG
	assert LOG[0][2] == 2 and LOG[2][2] == 4
	assert LOG[1][2] == 1
	assert pSys.ids() == [2, 4]


def test_rearm_not_for_phaser_or_pulse():
	App, ST, core, ship = setup()
	main = enemy("Main", 2, 10.0)
	b = enemy("B", 3, 20.0)
	core.g_pMission = mock_app.Mission([main, b])
	ship.target = main
	ship.groups[0] = ListGroup([ReachBank([20.0])], "gp")
	ship.groups[1] = ListGroup([mock_app.Pulse()], "gu", 1)
	for e in (0, 1):
		ST.OnFireKey(NULL, mock_app.Event(ST.GetFireEvents()[e][0], 1))
	ST.Cycle()
	assert calls("start") == []


def test_rearm_not_when_key_up():
	ST, ship, pSys, CLOCK, main = rearm_scene()
	ST.OnFireKey(NULL, mock_app.Event(ST.GetFireEvents()[2][0], 0))
	ST.Cycle()
	assert calls("start") == []


def test_rearm_not_while_main_tubes_have_torpedoes():
	ST, ship, pSys, CLOCK, main = rearm_scene(iFwdReady=1)
	ST.Cycle()
	assert calls("start") == []


def test_rearm_not_without_free_ready_tube():
	ST, ship, pSys, CLOCK, main = rearm_scene(iAftReady=0)
	ST.Cycle()
	assert calls("start") == []


def test_rearm_not_without_wanted_secondary():
	ST, ship, pSys, CLOCK, main = rearm_scene()
	core = ST.g_pCore
	core.g_pMission = mock_app.Mission([main, enemy("B", 3, 20.0)])	# nothing behind
	ST.Cycle()
	assert calls("start") == []


def test_rearm_throttled_half_second():
	ST, ship, pSys, CLOCK, main = rearm_scene()
	ST.Cycle()
	assert len(calls("start")) == 2
	pSys.Release()
	CLOCK[0] = 100.2
	ST.Cycle()
	assert len(calls("start")) == 2
	CLOCK[0] = 100.5
	ST.Cycle()
	assert len(calls("start")) == 4
	assert ST.g_dRearmAt != {}
	ST.ForgetAll()
	assert ST.g_dRearmAt == {} and ST.g_dNoRearm == {}


def norearm(ST):
	return [s for s in ST.g_lTrace if "NOREARM" in s]


def test_norearm_reason_lines_once_per_transition():
	ST, ship, pSys, CLOCK, main = rearm_scene(iDebug=1, iFwdReady=1)
	ST.Cycle()
	ST.Cycle()
	assert len(norearm(ST)) == 1 and "why=fwdready" in norearm(ST)[0], ST.g_lTrace
	pSys.lChildren[0].iReady = 0
	pSys.lChildren[1].iReady = 0
	ST.Cycle()
	assert len(norearm(ST)) == 2 and "why=nofree" in norearm(ST)[1]
	pSys.lChildren[1].iReady = 2
	ST.Cycle()
	assert len([s for s in ST.g_lTrace if "REARM g2 key=1 free rdy=2" in s and "NO" not in s]) == 1
	pSys.Release()
	CLOCK[0] = 100.2
	ST.Cycle()
	assert "why=throttle" in norearm(ST)[-1], ST.g_lTrace
	# Debug off: no NOREARM lines at all
	ST2, ship2, pSys2, CLOCK2, main2 = rearm_scene(iDebug=0, iFwdReady=1)
	ST2.Cycle()
	assert ST2.g_lTrace == []


def test_norearm_nosec_reason():
	ST, ship, pSys, CLOCK, main = rearm_scene(iDebug=1)
	ST.g_pCore.g_pMission = mock_app.Mission([main, enemy("B", 3, 20.0)])
	ST.Cycle()
	assert "why=nosec" in norearm(ST)[0], ST.g_lTrace


def test_key_trace_deduplicated_per_instant():
	ST, ship, pSys, CLOCK, main = rearm_scene(iDebug=1)
	for i in range(5):
		ST.OnFireKey(NULL, mock_app.Event(ST.GetFireEvents()[2][0], 1))
	ST.OnFireKey(NULL, mock_app.Event(ST.GetFireEvents()[2][0], 0))
	lKeys = [s for s in ST.g_lTrace if "KEY" in s]
	assert len(lKeys) == 2 and "x" not in lKeys[0].split("KEY")[1], ST.g_lTrace
	assert ST.KeyHeld(2) == 0


def rearm_n(ST, pSys, CLOCK, n, fStep=1.0):
	"""n Cycles, each followed by a release (the group stops) and fStep seconds."""
	for i in range(n):
		ST.Cycle()
		pSys.Release()
		CLOCK[0] = CLOCK[0] + fStep


def guard_lines(core, sWhy):
	return [t for t in core.logs if t[1] == "REARM-GUARD g2 " + sWhy]


def test_guard_cap_by_count_seventh_refused_logged_once():
	ST, ship, pSys, CLOCK, main = rearm_scene(iDebug=1)
	rearm_n(ST, pSys, CLOCK, 6)
	assert len(calls("start")) == 12, LOG
	assert ST.g_dRearmCnt[2] == 6
	ST.Cycle()
	pSys.Release()
	ST.Cycle()
	assert len(calls("start")) == 12
	assert len(guard_lines(ST.g_pCore, "cap")) == 1, ST.g_pCore.logs


def test_guard_cap_by_time():
	ST, ship, pSys, CLOCK, main = rearm_scene()
	CLOCK[0] = 109.0	# 9 s after the key down, 9 s after the last event (< stale)
	ST.Cycle()
	assert calls("start") == []
	assert ST.KeyHeld(2) == 1	# the cap refuses but does not clear


def test_guard_new_key_down_resets_counters():
	ST, ship, pSys, CLOCK, main = rearm_scene()
	rearm_n(ST, pSys, CLOCK, 6)
	ST.Cycle()
	assert len(calls("start")) == 12
	# a repeated key down (key already down) does NOT restart the counters
	iCnt = ST.g_dRearmCnt[2]
	ST.OnFireKey(NULL, mock_app.Event(ST.GetFireEvents()[2][0], 1))
	assert ST.g_dRearmCnt[2] == iCnt and iCnt > 0
	# a real new press (up, then down) does
	ST.OnFireKey(NULL, mock_app.Event(ST.GetFireEvents()[2][0], 0))
	ST.OnFireKey(NULL, mock_app.Event(ST.GetFireEvents()[2][0], 1))
	assert ST.g_dRearmCnt[2] == 0 and ST.g_dPressAt[2] == CLOCK[0]
	ST.Cycle()
	assert len(calls("start")) == 14
	# the time cap restarts too
	pSys.Release()
	ST.OnFireKey(NULL, mock_app.Event(ST.GetFireEvents()[2][0], 0))
	CLOCK[0] = CLOCK[0] + 9.0
	ST.OnFireKey(NULL, mock_app.Event(ST.GetFireEvents()[2][0], 1))
	ST.Cycle()
	assert len(calls("start")) == 16


def test_guard_key_up_clears_press_numbers():
	ST, ship, pSys, CLOCK, main = rearm_scene()
	ST.OnFireKey(NULL, mock_app.Event(ST.GetFireEvents()[2][0], 0))
	assert ST.g_dPressAt == {} and ST.g_dRearmCnt == {} and ST.g_dPressTgt == {}


def test_guard_target_change_clears_and_refuses():
	ST, ship, pSys, CLOCK, main = rearm_scene(iDebug=1)
	assert ST.g_dPressTgt[2] == 2
	b = enemy("B", 3, 20.0)
	ST.g_pCore.g_pMission = mock_app.Mission([main, b])
	ship.target = b
	ST.Cycle()
	assert calls("start") == []
	assert ST.g_dKeyHeld == {} and ST.g_dPressTgt == {}
	assert len(guard_lines(ST.g_pCore, "target")) == 1, ST.g_pCore.logs
	ship.target = main
	pSys.Release()
	ST.Cycle()
	assert calls("start") == []


def test_guard_target_stored_at_first_decision_when_no_main_at_key_down():
	App, ST, core, ship = setup()
	CLOCK = [100.0]
	App.g_kUtopiaModule.GetGameTime = lambda: CLOCK[0]
	main, b, c, pSys = torp_scene(core, ship)
	ship.target = None
	ST.OnFireKey(NULL, mock_app.Event(ST.GetFireEvents()[2][0], 1))
	assert ST.g_dPressTgt == {}
	ship.target = main
	pSys.lChildren[0].iReady = 0
	pSys.lChildren[1].iReady = 2
	ST.g_dKeyHeld[2] = 1
	ST.Cycle()
	assert ST.g_dPressTgt[2] == 2


def clear_scene(iDebug=0):
	"""Held group 2, a first Cycle done (ship known) without re-arming."""
	ST, ship, pSys, CLOCK, main = rearm_scene(iDebug, iFwdReady=1)
	ST.Cycle()
	assert calls("start") == [] and ST.KeyHeld(2) == 1
	pSys.lChildren[0].iReady = 0
	return ST, ship, pSys, CLOCK, main


def assert_cleared(ST, pSys):
	assert ST.g_dKeyHeld == {} and ST.g_dPressAt == {} and ST.g_dRearmCnt == {}
	assert ST.g_dPressTgt == {} and ST.g_dFireAt == {}
	pSys.Release()
	ST.Cycle()
	assert calls("start") == [], LOG


def test_guard_clear_on_toggle_off():
	ST, ship, pSys, CLOCK, main = clear_scene(1)
	ST.TurnOff()
	assert_cleared(ST, pSys)
	assert len(guard_lines(ST.g_pCore, "cleared")) == 1


def test_guard_clear_on_ship_change():
	ST, ship, pSys, CLOCK, main = clear_scene()
	AppMod = sys.modules["App"]
	other = mock_app.Ship("Galaxy", 7)
	ST.g_pCore.techs["Galaxy"] = {"SecondaryTarget": -1}
	AppMod._player[0] = other
	ST.Cycle()
	assert ST.g_dKeyHeld == {}
	AppMod._player[0] = ship
	assert_cleared(ST, pSys)


def test_guard_clear_on_dead_ship():
	ST, ship, pSys, CLOCK, main = clear_scene()
	ship.dead = 1
	ST.Cycle()
	assert ST.g_dKeyHeld == {}
	ship.dead = 0
	assert_cleared(ST, pSys)


def test_guard_clear_on_no_main_target():
	ST, ship, pSys, CLOCK, main = clear_scene()
	ship.target = None
	ST.Cycle()
	assert ST.g_dKeyHeld == {}
	ship.target = main
	assert_cleared(ST, pSys)


def test_guard_clear_on_red_alert_off():
	ST, ship, pSys, CLOCK, main = clear_scene()
	iOld = ship.alert
	ship.alert = 0
	ST.Cycle()
	assert ST.g_dKeyHeld == {}
	ship.alert = iOld
	assert_cleared(ST, pSys)


def test_guard_clear_on_cloak():
	ST, ship, pSys, CLOCK, main = clear_scene()
	ship.cloaked = 1
	ST.Cycle()
	assert ST.g_dKeyHeld == {}
	ship.cloaked = 0
	assert_cleared(ST, pSys)


def test_guard_clear_on_tech_lost():
	ST, ship, pSys, CLOCK, main = clear_scene()
	ST.g_pCore.techs["Galaxy"] = {"SecondaryTarget": 0}
	ST.Cycle()
	assert ST.g_dKeyHeld == {}


def test_guard_stale_no_event_for_10s():
	ST, ship, pSys, CLOCK, main = rearm_scene(iDebug=1)
	CLOCK[0] = 110.5
	ST.Cycle()
	assert calls("start") == []
	assert ST.g_dKeyHeld == {}
	assert len(guard_lines(ST.g_pCore, "stale")) == 1, ST.g_pCore.logs


def test_guard_not_cleared_in_normal_firing_path():
	ST, ship, pSys, CLOCK, main = rearm_scene()
	ST.Cycle()
	assert ST.KeyHeld(2) == 1 and len(calls("start")) == 2
	ST.Cycle()	# the group is firing: nothing is cleared
	assert ST.KeyHeld(2) == 1


class FakeWeapon:
	def __init__(self, pParent, sName="Fwd 1"):
		self.pParent = pParent
		self.sName = sName

	def GetName(self):
		return self.sName

	def GetTargetID(self):
		return 77

	def GetParentShip(self):
		return self.pParent


class FakeFired:
	def __init__(self, pWeapon):
		self.pWeapon = pWeapon

	def GetSource(self):
		return self.pWeapon


class Chain:
	def __init__(self):
		self.n = 0

	def CallNextHandler(self, pEvent):
		self.n = self.n + 1


def test_fired_handler_logs_only_with_debug_and_chains():
	for iDebug in (0, 1):
		App, ST, core, ship = setup(Debug=iDebug)
		App.g_kUtopiaModule.GetGameTime = lambda: 12.5
		chain = Chain()
		ST.OnWeaponFired(chain, FakeFired(FakeWeapon(ship)))
		ST.OnWeaponFired(chain, FakeFired(FakeWeapon(mock_app.Ship("Other", 9))))
		ST.OnWeaponFired(chain, "not an event")
		assert chain.n == 3
		lFired = [t[1] for t in core.logs if t[1].startswith("FIRED")]
		if iDebug:
			assert lFired == ["FIRED Fwd 1 tgt=77 t=12.50"], core.logs
		else:
			assert lFired == []


def test_torpedo_candidates_nearest_first_in_range():
	App, ST, core, ship = setup()
	main, b, c, pSys = torp_scene(core, ship)
	c.pos = mock_app.Point(-25.0, 0.0, 0.0)
	assert ST.TorpedoCandidates(ship, pSys, main) == [3, 4]
	# beyond SecondaryTorpedoRange (30 km = 171 units): left out
	c.pos = mock_app.Point(-500.0, 0.0, 0.0)
	assert ST.TorpedoCandidates(ship, pSys, main) == [3]


def test_torpedo_candidates_empty_when_not_allowed():
	App, ST, core, ship = setup()
	main, b, c, pSys = torp_scene(core, ship)
	ST.g_iOn = 0
	assert ST.TorpedoCandidates(ship, pSys, main) == []
	ST.g_iOn = 1
	# no torpedo bit (phasers + pulse only)
	core.techs["Galaxy"] = {"SecondaryTarget": 5}
	assert ST.TorpedoCandidates(ship, pSys, main) == []
	core.techs["Galaxy"] = {"SecondaryTarget": -1}
	assert ST.TorpedoCandidates(ship, pSys, main) == [3, 4]
	# not the player's ship
	other = mock_app.Ship("Galaxy", 50)
	assert ST.TorpedoCandidates(other, pSys, main) == []
	# main target is not an enemy
	friend = enemy("Friend", 60, 5.0)
	assert ST.TorpedoCandidates(ship, pSys, friend) == []
	assert ST.TorpedoCandidates(ship, pSys, None) == []


def test_maintain_torpedo_group_owned_by_autofire_is_left_alone():
	App, ST, core, ship = setup()
	main, b, c, pSys = torp_scene(core, ship)
	AF = ST.GetAutoFire()
	AF.ManagesTorpedoSecondaries = lambda eGroup: 1
	ST.g_dAdded[(1, 2)] = [4]
	pSys.Press(main)
	ST.Cycle()
	assert calls("start") == [] and calls("stopat") == []
	assert pSys.ids() == [2]
	assert (1, 2) not in ST.g_dAdded
	# AutoFire hands the group back (manual key): the old path adds secondaries
	AF.ManagesTorpedoSecondaries = lambda eGroup: 0
	ST.Cycle()
	assert pSys.ids() == [2, 4]


# --- arc-percent rule (pulse and torpedo): candidates, filter, hand-off ------------
def pulse_scene(core, ship, iEgroup=1):
	"""Main at x=10 (ahead), B at x=20 (ahead), C at x=-20 (behind). One fore and one
	aft pulse weapon (geometric arcs) in the pulse group."""
	main = enemy("Main", 2, 10.0)
	b = enemy("B", 3, 20.0)
	c = enemy("C", 4, -20.0)
	core.g_pMission = mock_app.Mission([main, b, c])
	ship.target = main
	wFore = mock_app.Pulse(5.0, 2.0, "box")
	wAft = mock_app.Pulse(5.0, 2.0, "box")
	wAft.axes = (mock_app.Point(-1.0, 0.0, 0.0), mock_app.Point(0.0, 1.0, 0.0), mock_app.Point(0.0, 0.0, 1.0))
	pSys = ListGroup([wFore, wAft], "gu", 1)
	ship.groups[iEgroup] = pSys
	return main, b, c, pSys


def arc_rule(ST, sKind, fnReaches=None):
	"""Makes Auto Fire (the real module object) report the arc-percent rule on for sKind."""
	AF = ST.GetAutoFire()
	AF.ArcRuleOn = lambda s: s == sKind
	if fnReaches == None:
		fnReaches = lambda pShip, pSys, pWeapon, pCand, s, bSec=0: 1
	AF.ArcReaches = fnReaches
	return AF


def test_pulse_candidates_nearest_first_no_range_limit():
	App, ST, core, ship = setup()
	main, b, c, pSys = pulse_scene(core, ship)
	c.pos = mock_app.Point(-5000.0, 0.0, 0.0)	# far away: pulse has no range filter
	assert ST.PulseCandidates(ship, pSys, main) == [3, 4]


def test_pulse_candidates_empty_when_not_allowed():
	App, ST, core, ship = setup()
	main, b, c, pSys = pulse_scene(core, ship)
	ST.g_iOn = 0
	assert ST.PulseCandidates(ship, pSys, main) == []
	ST.g_iOn = 1
	core.techs["Galaxy"] = {"SecondaryTarget": 3}	# no pulse bit
	assert ST.PulseCandidates(ship, pSys, main) == []
	core.techs["Galaxy"] = {"SecondaryTarget": 4}
	assert ST.PulseCandidates(ship, pSys, main) == [3, 4]
	assert ST.TorpedoCandidates(ship, pSys, main) == []	# torpedo needs bit 2
	other = mock_app.Ship("Galaxy", 50)
	assert ST.PulseCandidates(other, pSys, main) == []
	friend = enemy("Friend", 60, 5.0)
	assert ST.PulseCandidates(ship, pSys, friend) == []
	assert ST.PulseCandidates(ship, pSys, None) == []


def test_pulse_all_free_without_the_arc_rule():
	App, ST, core, ship = setup()
	main, b, c, pSys = pulse_scene(core, ship)
	assert ST.FreeWeapons(pSys, main, "pulse") == pSys.lChildren
	assert ST.WantedTargets(ship, pSys, main, "pulse") == [3, 4]
	arc_rule(ST, "torpedo")	# the rule is on for the other kind only
	assert ST.WantedTargets(ship, pSys, main, "pulse") == [3, 4]


def test_pulse_arc_rule_free_weapons_are_those_not_reaching_main():
	App, ST, core, ship = setup()
	main, b, c, pSys = pulse_scene(core, ship)
	arc_rule(ST, "pulse")
	assert ST.FreeWeapons(pSys, main, "pulse") == [pSys.lChildren[1]]
	# a failing IsInArc counts as reaching the main target: not free
	pSys.lChildren[1].iArc = "raise"
	assert ST.FreeWeapons(pSys, main, "pulse") == []


def test_pulse_arc_rule_wanted_needs_reach_and_arc_percent():
	App, ST, core, ship = setup()
	main, b, c, pSys = pulse_scene(core, ship)
	arc_rule(ST, "pulse")
	assert ST.WantedTargets(ship, pSys, main, "pulse") == [4]	# B is not in the aft arc
	arc_rule(ST, "pulse", lambda pShip, pSys_, pWeapon, pCand, s, bSec=0: 0)
	assert ST.WantedTargets(ship, pSys, main, "pulse") == []
	# ArcReaches is asked with the kind and the candidate
	lAsked = []
	arc_rule(ST, "pulse", lambda pShip, pSys_, pWeapon, pCand, s, bSec=0: lAsked.append((pCand.GetObjID(), s)) or 1)
	ST.WantedTargets(ship, pSys, main, "pulse")
	assert lAsked == [(4, "pulse")]


def test_pulse_arc_rule_debug_skip_line_on_change_only():
	App, ST, core, ship = setup(Debug=1)
	main, b, c, pSys = pulse_scene(core, ship)
	arc_rule(ST, "pulse", lambda pShip, pSys_, pWeapon, pCand, s, bSec=0: 0)
	ST.WantedTargets(ship, pSys, main, "pulse")
	ST.WantedTargets(ship, pSys, main, "pulse")
	assert [s for s in ST.g_lTrace if "ARC-SKIP pulse 4" in s] != []
	assert len([t for t in core.logs if "ARC-SKIP pulse 4" in t[1]]) == 1
	arc_rule(ST, "pulse")
	ST.WantedTargets(ship, pSys, main, "pulse")
	assert len([t for t in core.logs if "ARC-SKIP pulse none" in t[1]]) == 1


def test_arc_rule_off_when_autofire_lacks_the_functions():
	App, ST, core, ship = setup()
	main, b, c, pSys = pulse_scene(core, ship)
	AF = ST.GetAutoFire()
	AF.ArcRuleOn = lambda s: 1
	del AF.ArcReaches
	assert ST.ArcRule("pulse") == 0
	assert ST.WantedTargets(ship, pSys, main, "pulse") == [3, 4]


def test_torpedo_arc_rule_wanted_and_nosec():
	ST, ship, pSys, CLOCK, main = rearm_scene()
	assert ST.WantedTargets(ship, pSys, main, "torpedo") == [4]
	assert ST.RearmReason(ship, pSys, main, 2, (ship.GetObjID(), 2))[0] == ""
	arc_rule(ST, "torpedo", lambda pShip, pSys_, pWeapon, pCand, s, bSec=0: 0)
	assert ST.WantedTargets(ship, pSys, main, "torpedo") == []
	assert ST.RearmReason(ship, pSys, main, 2, (ship.GetObjID(), 2))[0] == "nosec"
	arc_rule(ST, "torpedo")
	assert ST.WantedTargets(ship, pSys, main, "torpedo") == [4]
	assert ST.RearmReason(ship, pSys, main, 2, (ship.GetObjID(), 2))[0] == ""


def test_maintain_pulse_group_owned_by_autofire_is_left_alone():
	App, ST, core, ship = setup()
	main, b, c, pSys = pulse_scene(core, ship)
	AF = ST.GetAutoFire()
	AF.ManagesPulseSecondaries = lambda eGroup: 1
	ST.g_dAdded[(1, 1)] = [4]
	pSys.Press(main)
	ST.Cycle()
	assert calls("start") == [] and calls("stopat") == []
	assert pSys.ids() == [2]
	assert (1, 1) not in ST.g_dAdded
	# Auto Fire hands the group back: the old path adds the secondaries again
	AF.ManagesPulseSecondaries = lambda eGroup: 0
	ST.Cycle()
	assert pSys.ids() == [2, 3, 4]


def test_maintain_pulse_group_without_the_autofire_function_is_not_owned():
	App, ST, core, ship = setup()
	main, b, c, pSys = pulse_scene(core, ship)
	AF = ST.GetAutoFire()
	if hasattr(AF, "ManagesPulseSecondaries"):
		del AF.ManagesPulseSecondaries
	assert ST.AutoFireOwns(1, "pulse") == 0
	pSys.Press(main)
	ST.Cycle()
	assert pSys.ids() == [2, 3, 4]


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
