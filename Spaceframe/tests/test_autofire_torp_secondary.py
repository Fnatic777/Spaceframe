"""Torpedo secondaries under Auto Fire: tubes that cannot reach the main target
fire at secondary targets (AutoFire plans the group's list, SecondaryTarget
only supplies candidates)."""
import os
import sys
import types
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mock_app
import test_autofire_base as base

GROUP = 1	# WG_SECONDARY


class FakeST:
	"""Stands in for the SecondaryTarget module."""
	def __init__(self, lIDs):
		self.lIDs = lIDs
		self.n = 0

	def TorpedoCandidates(self, pShip, pSystem, pMain):
		self.n = self.n + 1
		return list(self.lIDs)


def setup(tap=1, rule=1, fwd=1, aft=1, secx=-20.0, scores=None, available=10, reserve=0,
		secondary=1, module=1, extra=0):
	"""Player at the origin; main (7) ahead at x=10; secondary (8) at secx (default
	behind). One forward tube (+x) and one aft tube (-x). Score stub: 0 outside the
	tube's arc, else scores[target ID] (default 90)."""
	App, AF, core, ship = base.setup(TorpedoMinSolution=70, TorpedoReserve=reserve, TapFire=tap,
		TorpedoRule=rule, SecondaryTorpedoes=secondary)
	S = types.ModuleType("Custom.Spaceframe.Modules.AutoFire.Solution")
	S.scores = scores or {}

	def score(pShip, pTarget, vOffset, pTube, vDir, tInfo, *a):
		try:
			if not pTube.IsInArc(pTarget.GetWorldLocation()):
				return 0.0
		except:
			return 0.0
		return S.scores.get(pTarget.GetObjID(), 90.0)
	S.Score = score
	S.GetProjectileInfo = lambda w, s: (100.0, 0.1, 10.0, 0.0)
	S.TORPEDO_RULE = rule
	sys.modules["Custom.Spaceframe.Modules.AutoFire.Solution"] = S
	sys.modules["Custom.Spaceframe.Modules.AutoFire"].Solution = S
	main = mock_app.Ship("Main", 7)
	main.pos = mock_app.Point(10.0, 0.0, 0.0)
	sec = mock_app.Ship("Sec", 8)
	sec.pos = mock_app.Point(secx, 0.0, 0.0)
	lEnemies = [main, sec]
	if extra:
		sec2 = mock_app.Ship("Sec2", 9)
		sec2.pos = mock_app.Point(-30.0, 0.0, 0.0)
		lEnemies.append(sec2)
	ship.target = main
	core.g_pMission = mock_app.Mission(lEnemies)
	tFwd = mock_app.Tube(iReady=fwd)
	tAft = mock_app.Tube(mock_app.Point(-1.0, 0.0, 0.0), iReady=aft)
	torps = mock_app.WeaponGroup([tFwd, tAft])
	torps.torpedo = 1
	torps.available = available
	ship.groups[GROUP] = torps
	fake = FakeST([8, 9] if extra else [8])
	if module:
		core.modules["SecondaryTarget"] = fake
	AF.Toggle()
	return AF, core, ship, main, sec, torps, fake, S


def started(torps):
	return [c[1].GetObjID() for c in torps.calls if c[0] == "start"]


def test_main_shot_plus_secondary():
	AF, core, ship, main, sec, torps, fake, S = setup()
	AF.FireCycle()
	assert started(torps) == [7, 8]


def test_main_shot_plus_secondary_held():
	AF, core, ship, main, sec, torps, fake, S = setup(tap=0)
	AF.FireCycle()
	assert started(torps) == [7, 8]


def test_secondary_only_single_spread():
	AF, core, ship, main, sec, torps, fake, S = setup(fwd=0)
	torps.chains = 3
	torps.chain = 2
	AF.FireCycle()
	assert started(torps) == [8]
	assert torps.chain == 0


def test_secondary_only_held():
	AF, core, ship, main, sec, torps, fake, S = setup(fwd=0, tap=0)
	AF.FireCycle()
	assert started(torps) == [8]


def test_held_secondary_head_keeps_firing_without_replan():
	AF, core, ship, main, sec, torps, fake, S = setup(fwd=0, tap=0)
	for i in range(4):
		AF.FireCycle()
	assert [c[0] for c in torps.calls] == ["start"]
	assert fake.n == 1


def test_held_and_still_firing_no_replan():
	AF, core, ship, main, sec, torps, fake, S = setup(tap=0)
	for i in range(4):
		AF.FireCycle()
	assert started(torps) == [7, 8]
	assert fake.n == 1
	# the game stopped the group: the next cycle plans and starts again
	torps.GameStop()
	AF.FireCycle()
	assert started(torps) == [7, 8, 7, 8]
	assert fake.n == 2


def test_poor_main_and_forward_tube_reaches_secondary_no_start():
	# Main shot below the minimum, the secondary is ahead too: a ready forward
	# tube would take it, so nothing is pressed.
	AF, core, ship, main, sec, torps, fake, S = setup(secx=20.0, scores={7: 10.0})
	AF.FireCycle()
	assert started(torps) == []


def test_secondary_below_min_not_added():
	AF, core, ship, main, sec, torps, fake, S = setup(scores={8: 40.0})
	AF.FireCycle()
	assert started(torps) == [7]


def test_rule_2_uses_threshold_one():
	AF, core, ship, main, sec, torps, fake, S = setup(rule=2, scores={8: 5.0})
	AF.FireCycle()
	assert started(torps) == [7, 8]
	AF2, core2, ship2, main2, sec2, torps2, fake2, S2 = setup(rule=2, scores={8: 0.5})
	AF2.FireCycle()
	assert started(torps2) == [7]


def test_reserve_blocks_everything():
	AF, core, ship, main, sec, torps, fake, S = setup(available=3, reserve=3)
	AF.FireCycle()
	assert started(torps) == []


def test_no_secondary_target_module_same_as_before():
	AF, core, ship, main, sec, torps, fake, S = setup(module=0)
	for i in range(4):
		AF.FireCycle()
	assert [c[0] for c in torps.calls] == ["start", "stop", "start", "stop"]
	assert started(torps) == [7, 7]


def test_switch_off():
	AF, core, ship, main, sec, torps, fake, S = setup(secondary=0)
	AF.FireCycle()
	assert started(torps) == [7]
	assert AF.ManagesTorpedoSecondaries(GROUP) == 0


def test_release_cycle_does_not_plan():
	AF, core, ship, main, sec, torps, fake, S = setup()
	AF.FireCycle()
	AF.FireCycle()
	assert [c[0] for c in torps.calls] == ["start", "start", "stop"]
	assert fake.n == 1


def test_manual_key_hands_off():
	AF, core, ship, main, sec, torps, fake, S = setup()
	AF.g_dManual[GROUP] = 1
	AF.FireCycle()
	assert torps.calls == []
	assert AF.ManagesTorpedoSecondaries(GROUP) == 0
	AF.g_dManual[GROUP] = 0
	assert AF.ManagesTorpedoSecondaries(GROUP) == 1


def test_candidate_dead_before_press_skipped():
	AF, core, ship, main, sec, torps, fake, S = setup(extra=1)
	pOrig = AF.PlanTorpedoGroup

	def plan(*a):
		t = pOrig(*a)
		mock_app.SHIPS[9].dead = 1
		return t
	AF.PlanTorpedoGroup = plan
	AF.FireCycle()
	assert started(torps) == [7, 8]


def test_candidate_dead_head_still_started():
	AF, core, ship, main, sec, torps, fake, S = setup()
	pOrig = AF.PlanTorpedoGroup

	def plan(*a):
		t = pOrig(*a)
		mock_app.SHIPS[8].dead = 1
		return t
	AF.PlanTorpedoGroup = plan
	AF.FireCycle()
	assert started(torps) == [7]


def test_isinarc_raising_tube_never_free():
	AF, core, ship, main, sec, torps, fake, S = setup()
	torps.lChildren[1].iArc = "raise"
	AF.FireCycle()
	assert started(torps) == [7]
	AF2, core2, ship2, main2, sec2, torps2, fake2, S2 = setup()
	torps2.lChildren[0].iArc = "raise"
	AF2.FireCycle()	# no exception escapes
	assert fake2.n == 1


def test_force_update_after_secondaries():
	AF, core, ship, main, sec, torps, fake, S = setup()
	AF.FireCycle()
	assert torps.forced == [2]


def test_phasers_untouched_by_plan():
	AF, core, ship, main, sec, torps, fake, S = setup()
	primary = mock_app.WeaponGroup([mock_app.Bank(100.0, 1.0, 1)])
	ship.groups[0] = primary
	AF.FireCycle()
	assert primary.starts() == 1
	assert fake.n == 1


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
