"""SecondaryTarget: one phaser bank firing per target (PhaserPerTarget)."""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mock_app
import test_secondary_cycle as T

HOLDS = []
SETFIRING = []	# must stay empty: SetFiring froze beams in game	bank name for every StopFiring()


class FireBank(T.ReachBank):
	"""A phaser bank that reports its own firing state and target."""
	def __init__(self, sName, iTarget, fCharge=1.0, bFire=1, lReach=None):
		T.ReachBank.__init__(self, lReach or [20.0, 30.0])
		self.sName = sName
		self.iTarget = iTarget
		self.fCharge = fCharge
		self.bFire = bFire
		self.bFail = 0

	def IsFiring(self):
		if self.bFail:
			raise RuntimeError("bank error")
		return self.bFire

	def GetTargetID(self):
		return self.iTarget

	def StopFiring(self):
		HOLDS.append(self.sName)
		self.bFire = 0

	def SetFiring(self, i):
		SETFIRING.append(self.sName)


def build(lBanks, **kw):
	del HOLDS[:]
	del SETFIRING[:]
	if "PhaserPerTarget" not in kw:
		kw["PhaserPerTarget"] = 1
	App, ST, core, ship = T.setup(**kw)
	main, b, c, pSys = T.scene(core, ship)
	pSys = T.ListGroup(lBanks, "g0")
	ship.groups[0] = pSys
	pSys.Press(main)
	return ST, core, ship, pSys, main


def test_three_banks_same_target_keeps_highest_charge():
	ST, core, ship, pSys, main = build([FireBank("a", 3, 0.2), FireBank("b", 3, 0.9), FireBank("c", 3, 0.5)])
	ST.Cycle()
	assert sorted(HOLDS) == ["a", "c"]
	assert SETFIRING == []


def test_two_targets_two_banks_each_one_kept_per_target():
	ST, core, ship, pSys, main = build([FireBank("a", 3, 0.9), FireBank("b", 3, 0.1),
		FireBank("c", 4, 0.3), FireBank("d", 4, 0.8)])
	ST.Cycle()
	assert sorted(HOLDS) == ["b", "c"]


def test_config_zero_no_calls():
	ST, core, ship, pSys, main = build([FireBank("a", 3), FireBank("b", 3)], PhaserPerTarget=0)
	ST.Cycle()
	assert HOLDS == []


def test_pulse_group_never_limited():
	ST, core, ship, pSys, main = build([FireBank("a", 3)])
	pPulse = T.ListGroup([FireBank("p1", 3), FireBank("p2", 3)], "g1", 1)
	ship.groups[1] = pPulse
	pPulse.Press(main)
	ST.Cycle()
	assert "p1" not in HOLDS and "p2" not in HOLDS


def test_not_lifted_vanilla_no_calls():
	# no secondary reachable: single-fire is never lifted by the module
	ST, core, ship, pSys, main = build([FireBank("a", 3, lReach=[10.0]), FireBank("b", 3, lReach=[10.0])])
	ST.Cycle()
	assert ST.g_dLifted == {}
	assert HOLDS == []


def test_one_bank_per_target_no_calls():
	ST, core, ship, pSys, main = build([FireBank("a", 3), FireBank("b", 4), FireBank("c", 2, bFire=0)])
	ST.Cycle()
	assert HOLDS == []


def test_error_on_one_bank_does_not_stop_rest():
	bad = FireBank("x", 3)
	bad.bFail = 1
	ST, core, ship, pSys, main = build([bad, FireBank("a", 3, 0.1), FireBank("b", 3, 0.9)])
	ST.Cycle()
	assert HOLDS == ["a"]
	# the hold itself failing on one bank does not stop the other target
	ST, core, ship, pSys, main = build([FireBank("a", 3, 0.9), FireBank("b", 3, 0.1),
		FireBank("c", 4, 0.9), FireBank("d", 4, 0.1)])
	pSys.lChildren[1].StopFiring = lambda: (_ for _ in ()).throw(RuntimeError("hold failed"))
	ST.Cycle()
	assert HOLDS == ["d"]


def test_kept_bank_switches_on_higher_charge_and_ties_stay():
	a = FireBank("a", 3, 0.9)
	b = FireBank("b", 3, 0.5)
	ST, core, ship, pSys, main = build([a, b])
	ST.Cycle()
	assert HOLDS == ["b"]
	assert ST.g_dKept[(1, 0, 3)] == 0
	# tie: the kept one (a) stays
	b.bFire = 1
	b.fCharge = 0.9
	del HOLDS[:]
	ST.Cycle()
	assert HOLDS == ["b"]
	# b now clearly higher: kept moves to b, a is held
	b.bFire = 1
	b.fCharge = 1.0
	a.fCharge = 0.4
	del HOLDS[:]
	ST.Cycle()
	assert HOLDS == ["a"]
	assert ST.g_dKept[(1, 0, 3)] == 1


def test_restore_forgets_kept_map():
	ST, core, ship, pSys, main = build([FireBank("a", 3, 0.9), FireBank("b", 3, 0.1)])
	ST.Cycle()
	assert ST.g_dKept != {}
	ship.target.dead = 1
	ST.Cycle()
	assert ST.g_dKept == {}


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
