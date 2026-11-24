"""Pulse secondaries under Auto Fire (arc percent rule): AutoFire plans
the group's list (SecondaryTarget only supplies candidates)."""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mock_app
import test_autofire_base as base

GROUP = 2	# WG_TERTIARY


class FakeST:
	"""Stands in for the SecondaryTarget module."""
	def __init__(self, lIDs):
		self.lIDs = lIDs
		self.n = 0
		self.bRaise = 0

	def PulseCandidates(self, pShip, pSystem, pMain):
		self.n = self.n + 1
		if self.bRaise:
			raise TypeError("PulseCandidates")
		return list(self.lIDs)


def make_weapon(aft, fCharge=5.0):
	w = mock_app.Pulse(fCharge, 2.0, "box")
	if aft:
		w.axes = (mock_app.Point(-1.0, 0.0, 0.0), mock_app.Point(0.0, 1.0, 0.0), mock_app.Point(0.0, 0.0, 1.0))
	return w


def setup(rule=3, tap=1, fore=5.0, aft=5.0, secy=0.0, manual=0, module=1):
	"""Player at the origin; main (7) ahead at x=10; secondary (8) behind at (-20, secy).
	One fore pulse weapon (+x) and one aft (-x), arcs +-0.5 rad on both axes,
	charge `fore` / `aft` (minimum 2.0)."""
	App, AF, core, ship = base.setup(PulseRule=rule, TapFire=tap, PulseArcPercentFar=50,
		PulseArcPercentNear=90, PulseArcHysteresis=10)
	S = mock_app.load_module("Modules/AutoFire/Solution.py", "Custom.Spaceframe.Modules.AutoFire.Solution")
	sys.modules["Custom.Spaceframe.Modules.AutoFire"].Solution = S
	main = mock_app.Ship("Main", 7)
	main.pos = mock_app.Point(10.0, 0.0, 0.0)
	sec = mock_app.Ship("Sec", 8)
	sec.pos = mock_app.Point(-20.0, secy, 0.0)
	ship.target = main
	core.g_pMission = mock_app.Mission([main, sec])
	wFore = make_weapon(0, fore)
	wAft = make_weapon(1, aft)
	pulse = mock_app.WeaponGroup([wFore, wAft])
	pulse.pulse = 1
	ship.groups[GROUP] = pulse
	fake = FakeST([8])
	if module:
		core.modules["SecondaryTarget"] = fake
	AF.Toggle()
	AF.g_dManual[GROUP] = manual
	return AF, core, ship, main, sec, pulse, fake


def started(pulse):
	return [c[1].GetObjID() for c in pulse.calls if c[0] == "start"]


def test_main_shot_plus_secondary_within_percent():
	AF, core, ship, main, sec, pulse, fake = setup()
	AF.FireCycle()
	assert started(pulse) == [7, 8]


def test_secondary_outside_percent_of_every_free_weapon_main_only():
	# 0.475 rad off the aft axis: inside the 0.5 rad arc, deeper than 90 %.
	AF, core, ship, main, sec, pulse, fake = setup(secy=10.3)
	assert pulse.lChildren[1].IsInArc(sec.GetWorldLocation())
	AF.FireCycle()
	assert started(pulse) == [7]


def test_no_main_shot_fires_at_secondary_alone():
	AF, core, ship, main, sec, pulse, fake = setup(fore=1.0)
	AF.g_bDebug = 1
	AF.FireCycle()
	assert started(pulse) == [8]
	assert [l for l in core.logs if l[1].find("at secondary 8") >= 0] != []
	assert [l for l in core.logs if l[1].find("plan: main - sec 8 head sec") >= 0] != []


def test_no_main_shot_main_reaching_weapon_also_has_secondary_no_start():
	# The fore weapon is charged but the main is outside its percent; the
	# secondary is ahead as well (inside the fore arc): it would take it.
	AF, core, ship, main, sec, pulse, fake = setup()
	main.pos = mock_app.Point(10.0, 5.2, 0.0)	# 0.48 rad off the fore axis: inside the arc, deeper than 90 %
	sec.pos = mock_app.Point(20.0, 0.0, 0.0)	# dead ahead of the fore weapon
	assert pulse.lChildren[0].IsInArc(main.GetWorldLocation())
	AF.FireCycle()
	assert started(pulse) == []


def test_uncharged_free_weapon_secondary_not_added():
	AF, core, ship, main, sec, pulse, fake = setup(aft=1.0)
	AF.FireCycle()
	assert started(pulse) == [7]


def test_rules_1_and_2_both_plan_secondaries():
	# Both rules are arc rules now (rule 2 adds the flight-time filter).
	for iRule in (1, 2, 3):
		AF, core, ship, main, sec, pulse, fake = setup(rule=iRule)
		AF.FireCycle()
		assert fake.n > 0
		assert AF.ManagesPulseSecondaries(GROUP) == 1
		assert started(pulse) == [7, 8]


def test_manual_key_hands_off():
	AF, core, ship, main, sec, pulse, fake = setup(manual=1)
	AF.FireCycle()
	assert pulse.calls == []
	assert fake.n == 0
	assert AF.ManagesPulseSecondaries(GROUP) == 0
	AF.g_dManual[GROUP] = 0
	assert AF.ManagesPulseSecondaries(GROUP) == 1


def test_release_cycle_does_not_plan():
	AF, core, ship, main, sec, pulse, fake = setup()
	AF.FireCycle()
	AF.FireCycle()
	assert [c[0] for c in pulse.calls] == ["start", "start", "stop"]
	assert fake.n == 1


def test_candidates_raising_main_still_started():
	AF, core, ship, main, sec, pulse, fake = setup()
	fake.bRaise = 1
	AF.FireCycle()
	assert started(pulse) == [7]


def test_no_secondary_target_module_main_only():
	AF, core, ship, main, sec, pulse, fake = setup(module=0)
	AF.FireCycle()
	assert started(pulse) == [7]


def test_held_secondary_head_keeps_firing_without_replan():
	AF, core, ship, main, sec, pulse, fake = setup(fore=1.0, tap=0)
	for i in range(4):
		AF.FireCycle()
	assert [c[0] for c in pulse.calls] == ["start"]
	assert fake.n == 1


def test_secondary_hysteresis_survives_the_release_cycle():
	AF, core, ship, main, sec, pulse, fake = setup()
	AF.FireCycle()
	iAft = pulse.lChildren[1].GetObjID()
	assert (iAft, 8) in AF.g_dArcReady
	AF.FireCycle()
	assert pulse.calls[-1] == ("stop",)
	assert (iAft, 8) in AF.g_dArcReady


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
