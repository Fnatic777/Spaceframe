"""SecondaryTarget: HoldMode 2 (raise MinFiringCharge of a held bank, restore on release)."""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mock_app
import test_secondary_cycle as T

ORDER = []	# ("stop", bank name) for every StopFiring()
ORIG = 0.37
CLOCK = [0.0]


class Prop:
	"""A bank's EnergyWeaponProperty."""
	def __init__(self):
		self.fMin = ORIG
		self.sets = []
		self.failSets = 0	# the next N SetMinFiringCharge calls raise

	def GetMinFiringCharge(self):
		return self.fMin

	def SetMinFiringCharge(self, f):
		self.sets.append(f)
		if self.failSets > 0:
			self.failSets = self.failSets - 1
			raise RuntimeError("set failed")
		self.fMin = f


class HBank(T.ReachBank):
	def __init__(self, sName, iTarget, fCharge=1.0):
		T.ReachBank.__init__(self, [20.0, 30.0])
		self.sName = sName
		self.iTarget = iTarget
		self.fCharge = fCharge
		self.bFire = 1
		self.prop = Prop()

	def IsFiring(self):
		return self.bFire

	def GetTargetID(self):
		return self.iTarget

	def StopFiring(self):
		ORDER.append(("stop", self.sName))
		self.bFire = 0

	def SetFiring(self, i):
		ORDER.append(("set" + str(i), self.sName))

	def GetMaxCharge(self):
		return 1.0

	def GetProperty(self):
		return self.prop


class FGroup(T.ListGroup):
	def __init__(self, lWeapons, sTag):
		T.ListGroup.__init__(self, lWeapons, sTag)
		self.forced = 0

	def SetForceUpdate(self, i):
		self.forced = self.forced + 1


def build(iCount=2, **kw):
	del ORDER[:]
	CLOCK[0] = 0.0
	kw.setdefault("PhaserPerTarget", 1)
	kw.setdefault("HoldMode", 2)
	App, ST, core, ship = T.setup(**kw)
	ST.Now = lambda: CLOCK[0]
	main, b, c, pSys = T.scene(core, ship)
	lBanks = [HBank("a", 3, 0.2), HBank("b", 3, 0.9), HBank("c", 3, 0.5)][:iCount]
	pSys = FGroup(lBanks, "g0")
	ship.groups[0] = pSys
	pSys.Press(main)
	return ST, core, ship, pSys, main, lBanks


def test_hold_records_original_and_raises_to_max_plus_one():
	ST, core, ship, pSys, main, l = build()
	ST.Cycle()
	assert ST.g_dHold2 == {(1, 0, 0): ORIG}
	assert l[0].prop.fMin == 2.0
	assert ORDER == [("stop", "a")]
	# held again next cycle: no second StopFiring, no second record change
	ST.Cycle()
	assert ORDER == [("stop", "a")] and l[0].prop.sets == [2.0]
	assert ST.g_dHold2 == {(1, 0, 0): ORIG}
	assert ST.HeldCount() == 1


def test_restore_writes_exact_original_and_forces_update():
	ST, core, ship, pSys, main, l = build()
	ST.Cycle()
	ship.target.dead = 1
	ST.Cycle()
	assert l[0].prop.fMin == ORIG
	assert ST.g_dHold2 == {} and ST.g_dHold2Target == {}
	assert pSys.forced == 1


def m_main_dies(ship, pSys, l):
	ship.target.dead = 1


def m_main_gone(ship, pSys, l):
	ship.target = None


def m_no_alert(ship, pSys, l):
	ship.alert = 0


def m_cloak(ship, pSys, l):
	ship.cloaked = 1


def m_tech_lost(ship, pSys, l):
	ship.core.techs["Galaxy"] = {}


def m_key_release(ship, pSys, l):
	pSys.Release()


def m_target_one_bank_left(ship, pSys, l):
	l[1].bFire = 0	# b stops firing: only the held a wants target 3


def m_feature_off(ship, pSys, l):
	ship.ST.g_iPhaserPerTarget = 0


def m_ship_change(ship, pSys, l):
	other = mock_app.Ship("Galaxy", 7)
	other.groups = T.CountDict()
	ship.App._player[0] = other


def m_dying(ship, pSys, l):
	ship.IsDying = lambda: 1


def m_dead(ship, pSys, l):
	ship.dead = 1


def m_stop_groups(ship, pSys, l):
	ship.ST.StopGroups()


def test_restore_on_every_release_path():
	for fMut in [m_main_dies, m_main_gone, m_no_alert, m_cloak, m_tech_lost, m_key_release,
			m_target_one_bank_left, m_feature_off, m_ship_change, m_dying, m_dead, m_stop_groups]:
		ST, core, ship, pSys, main, l = build()
		ship.core = core
		ship.ST = ST
		ship.App = sys.modules["App"]
		ST.Cycle()
		assert l[0].prop.fMin == 2.0, fMut.__name__
		fMut(ship, pSys, l)
		ST.Cycle()
		assert l[0].prop.fMin == ORIG, fMut.__name__
		assert ST.g_dHold2 == {}, fMut.__name__
		assert pSys.forced >= 1, fMut.__name__


def test_kept_bank_becomes_released_and_other_held():
	ST, core, ship, pSys, main, l = build()
	ST.Cycle()
	CLOCK[0] = 2.0
	l[0].fCharge = 0.95
	l[1].fCharge = 0.3
	ST.Cycle()
	assert l[0].prop.fMin == ORIG
	assert l[1].prop.fMin == 2.0
	assert ST.g_dHold2 == {(1, 0, 1): ORIG}
	assert ST.g_dKept[(1, 0, 3)] == 0


def test_no_restore_call_when_ship_is_none():
	ST, core, ship, pSys, main, l = build()
	ST.Cycle()
	del mock_app.SHIPS[1]
	n = len(l[0].prop.sets)
	assert ST.ReleaseHeld(1) == 0
	assert len(l[0].prop.sets) == n and l[0].prop.fMin == 2.0
	assert ST.g_dHold2 == {} and ST.g_dHold2Target == {}
	# same through the cycle paths: the player is gone, nothing is asked
	ST.ReleaseCurrent(1)
	ST.ReleaseShipID(1)
	assert len(l[0].prop.sets) == n


def test_kept_and_lone_banks_never_held():
	ST, core, ship, pSys, main, l = build()
	ST.Cycle()
	assert l[1].prop.sets == [] and ORDER == [("stop", "a")]
	ST, core, ship, pSys, main, l = build(iCount=1)
	ST.Cycle()
	assert ST.g_dHold2 == {} and l[0].prop.sets == [] and ORDER == []


def test_three_banks_two_held_one_kept():
	ST, core, ship, pSys, main, l = build(iCount=3)
	ST.Cycle()
	assert sorted(ST.g_dHold2.keys()) == [(1, 0, 0), (1, 0, 2)]
	assert l[1].prop.sets == []


def test_hysteresis_blocks_swap_and_rehold():
	ST, core, ship, pSys, main, l = build()
	ST.Cycle()
	# charges flip at t=0.5: the kept bank stays (hysteresis 1.0 s)
	CLOCK[0] = 0.5
	l[0].fCharge = 0.95
	l[1].fCharge = 0.3
	ST.Cycle()
	assert ST.g_dHold2 == {(1, 0, 0): ORIG} and l[1].prop.sets == []
	# b stops firing at t=0.6: a is released (forced), then b fires again
	CLOCK[0] = 0.6
	l[1].bFire = 0
	ST.Cycle()
	assert ST.g_dHold2 == {} and l[0].prop.fMin == ORIG
	l[0].bFire = 1	# the engine refires the freed bank
	l[1].bFire = 1
	l[0].fCharge = 0.1
	l[1].fCharge = 0.9
	del ORDER[:]
	CLOCK[0] = 0.8
	ST.Cycle()
	# a was released 0.2 s ago: it may not be held again yet
	assert ST.g_dHold2 == {} and ORDER == []
	CLOCK[0] = 1.8
	ST.Cycle()
	assert ST.g_dHold2 == {(1, 0, 0): ORIG} and ORDER == [("stop", "a")]


def test_mode_0_and_1_do_not_touch_the_property():
	for iMode in [0, 1]:
		ST, core, ship, pSys, main, l = build(HoldMode=iMode)
		ST.Cycle()
		assert ORDER[0] == ("stop", "a")
		assert l[0].prop.sets == [] and ST.g_dHold2 == {}
		assert ST.g_pFastTimer != None


def test_fast_timer_not_started_in_mode_2():
	ST, core, ship, pSys, main, l = build()
	ST.Cycle()
	assert ST.g_dLifted != {} and ST.g_pFastTimer == None
	assert ST.g_dHold2 != {}


def test_errors_are_isolated_per_bank():
	ST, core, ship, pSys, main, l = build(iCount=3)
	l[0].prop.failSets = 1000
	ST.Cycle()
	# c is held although a failed; a's restore was attempted (2 writes)
	assert (1, 0, 2) in ST.g_dHold2
	assert l[2].prop.fMin == 2.0
	assert len(l[0].prop.sets) >= 2
	# a bank whose first write fails and whose restore works leaves no record
	ST, core, ship, pSys, main, l = build()
	l[0].prop.failSets = 1
	ST.Cycle()
	assert ST.g_dHold2 == {} and l[0].prop.fMin == ORIG
	assert len(l[0].prop.sets) == 2


def test_stop_failure_leaves_no_record():
	ST, core, ship, pSys, main, l = build()
	def boom():
		raise RuntimeError("stop failed")
	l[0].StopFiring = boom
	ST.Cycle()
	assert ST.g_dHold2 == {} and l[0].prop.sets == []


def test_safety_valve_forgets_or_restores_foreign_records():
	ST, core, ship, pSys, main, l = build()
	other = mock_app.Ship("Galaxy", 7)
	# record of a live ship that is not the player's: restored, then forgotten
	oB = HBank("x", 3)
	oB.prop.fMin = 2.0
	other.groups = T.CountDict()
	oG = FGroup([oB], "g1")
	other.groups[0] = oG
	ST.g_dHold2[(7, 0, 0)] = ORIG
	ST.g_dHold2Target[(7, 0, 0)] = 3
	# record of a ship that does not exist: forgotten, nothing asked
	ST.g_dHold2[(99, 0, 0)] = ORIG
	ST.g_dHold2Target[(99, 0, 0)] = 3
	ST.Cycle()
	assert oB.prop.fMin == ORIG
	assert (7, 0, 0) not in ST.g_dHold2 and (99, 0, 0) not in ST.g_dHold2
	# HoldSafety 0: left alone
	ST, core, ship, pSys, main, l = build(HoldSafety=0)
	ST.g_dHold2[(99, 0, 0)] = ORIG
	ST.Cycle()
	assert (99, 0, 0) in ST.g_dHold2


def test_stop_touches_no_ship_and_forgets():
	ST, core, ship, pSys, main, l = build()
	ST.Start(core)
	ST.Now = lambda: CLOCK[0]
	ST.Cycle()
	assert ST.g_dHold2 != {}
	n = len(l[0].prop.sets)
	del mock_app.TOUCHED[:]
	ST.Stop()
	assert ST.g_dHold2 == {} and ST.g_dHold2Target == {} and ST.g_dHoldAt == {}
	assert len(l[0].prop.sets) == n and mock_app.TOUCHED == []
	assert pSys.forced == 0


def test_config_defaults_and_diag():
	ST, core, ship, pSys, main, l = build(HoldMode=0)
	assert ST.g_fHoldHysteresis == 1.0 and ST.g_iHoldSafety == 1
	ST, core, ship, pSys, main, l = build(HoldHysteresis=-3, HoldSafety=0)
	assert ST.g_fHoldHysteresis == 0.0 and ST.g_iHoldSafety == 0
	ST.Diag()


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
