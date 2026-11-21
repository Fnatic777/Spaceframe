"""Pulse weapons fire on the arc score (ArcScore stubbed here: charge, tap, hold)."""
import os
import sys
import types
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mock_app
import test_autofire_base as base


def setup(score=75.0, charge=5.0, tap=0, rule=2):
	App, AF, core, ship = base.setup(TapFire=tap, PulseRule=rule)
	S = types.ModuleType("Custom.Spaceframe.Modules.AutoFire.Solution")
	S.score = score
	S.GetProjectileInfo = lambda w, s: (150.0, 0.0, 0.0, 10.0)
	sys.modules["Custom.Spaceframe.Modules.AutoFire.Solution"] = S
	sys.modules["Custom.Spaceframe.Modules.AutoFire"].Solution = S
	base.fake_arc_score(AF, lambda pTarget: S.score)
	target = mock_app.Ship("Bug", 7)
	target.pos = mock_app.Point(10.0, 0.0, 0.0)
	ship.target = target
	core.g_pMission = mock_app.Mission([target])	# the target is an enemy
	pulse = mock_app.WeaponGroup([mock_app.Pulse(charge, 2.0, 1)])
	pulse.pulse = 1
	ship.groups[App.ShipClass.WG_TERTIARY] = pulse
	AF.Toggle()
	return App, AF, ship, target, pulse, S


def test_pulse_fires_when_a_weapon_reaches():
	App, AF, ship, target, pulse, S = setup(75.0)
	AF.FireCycle()
	assert pulse.starts() == 1


def test_pulse_low_score_still_fires():
	# The arc rule only needs a weapon inside the allowed percent (score >= 1).
	App, AF, ship, target, pulse, S = setup(3.0)
	AF.FireCycle()
	assert pulse.starts() == 1


def test_pulse_hold_when_outside():
	App, AF, ship, target, pulse, S = setup(0.0)
	AF.FireCycle()
	assert pulse.starts() == 0


def test_pulse_no_charge():
	App, AF, ship, target, pulse, S = setup(90.0, charge=1.0)
	AF.FireCycle()
	assert pulse.starts() == 0


def test_pulse_best_score_ignores_uncharged():
	App, AF, ship, target, pulse, S = setup(90.0, charge=1.0)
	assert AF.BestPulseScore(ship, pulse, target) == 0.0
	pulse.lChildren.append(mock_app.Pulse(5.0, 2.0, 1))
	assert AF.BestPulseScore(ship, pulse, target) == 90.0


def test_pulse_manual_priority():
	App, AF, ship, target, pulse, S = setup(90.0)
	AF.g_dManual[App.ShipClass.WG_TERTIARY] = 1
	AF.FireCycle()
	assert pulse.calls == []


def test_pulse_tap_fire():
	App, AF, ship, target, pulse, S = setup(90.0, tap=1)
	for i in range(3):
		AF.FireCycle()
	assert [c[0] for c in pulse.calls] == ["start", "stop", "start"]


def test_pulse_rule_1_also_fires():
	App, AF, ship, target, pulse, S = setup(75.0, rule=1)
	AF.FireCycle()
	assert pulse.starts() == 1


def test_pulse_old_helpers_removed():
	App, AF, ship, target, pulse, S = setup(75.0)
	assert not hasattr(AF, "PulseReady") and not hasattr(AF, "ApplySolutionConfig")


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
	print(str(len(names) - failed) + "/" + str(len(names)) + " passed")
	return failed


if __name__ == "__main__":
	sys.exit(run())
