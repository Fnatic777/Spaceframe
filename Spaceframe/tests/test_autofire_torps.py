"""Torpedoes fire on the arc score (ArcScore stubbed here: tap, reserve, hold)."""
import os
import sys
import types
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mock_app
import test_autofire_base as base


def setup(score=75.0, available=10, reserve=0, ready=1, tap=0, rule=2):
	App, AF, core, ship = base.setup(TorpedoReserve=reserve, TapFire=tap, TorpedoRule=rule)
	S = types.ModuleType("Custom.Spaceframe.Modules.AutoFire.Solution")
	S.score = score
	S.GetProjectileInfo = lambda w, s: (100.0, 0.1, 10.0, 0.0)
	sys.modules["Custom.Spaceframe.Modules.AutoFire.Solution"] = S
	sys.modules["Custom.Spaceframe.Modules.AutoFire"].Solution = S
	base.fake_arc_score(AF, lambda pTarget: S.score)
	target = mock_app.Ship("Bug", 7)
	target.pos = mock_app.Point(10.0, 0.0, 0.0)
	ship.target = target
	core.g_pMission = mock_app.Mission([target])	# the target is an enemy
	torps = mock_app.WeaponGroup([mock_app.Tube(iReady=ready)])
	torps.torpedo = 1
	torps.available = available
	ship.groups[App.ShipClass.WG_SECONDARY] = torps
	AF.Toggle()
	return App, AF, ship, target, torps


def test_torps_fire_when_a_tube_reaches():
	App, AF, ship, target, torps = setup(75.0)
	AF.FireCycle()
	assert torps.starts() == 1


def test_torps_low_score_still_fires():
	# The arc rule only needs a tube inside the allowed percent (score >= 1).
	App, AF, ship, target, torps = setup(5.0)
	AF.FireCycle()
	assert torps.starts() == 1


def test_torps_hold_when_no_tube_reaches():
	App, AF, ship, target, torps = setup(0.0)
	AF.FireCycle()
	assert torps.starts() == 0


def test_torps_reserve():
	App, AF, ship, target, torps = setup(90.0, available=3, reserve=3)
	AF.FireCycle()
	assert torps.starts() == 0


def test_torps_none_ready():
	App, AF, ship, target, torps = setup(90.0, ready=0)
	AF.FireCycle()
	assert torps.starts() == 0


def test_torps_stop_when_tube_leaves_the_arc():
	App, AF, ship, target, torps = setup(90.0)
	AF.FireCycle()
	sys.modules["Custom.Spaceframe.Modules.AutoFire.Solution"].score = 0.0
	AF.FireCycle()
	assert torps.stops() == 1


def test_torps_score_error_does_not_break_phasers():
	App, AF, ship, target, torps = setup(90.0)

	def boom(pTarget):
		raise ValueError("bad")
	base.fake_arc_score(AF, boom)
	primary = mock_app.WeaponGroup([mock_app.Bank(100.0, 1.0, 1)])
	ship.groups[App.ShipClass.WG_PRIMARY] = primary
	AF.FireCycle()
	assert primary.starts() == 1 and torps.starts() == 0


def test_removed_solution_settings_not_applied():
	# The old firing-solution settings are gone: Start sets nothing on Solution.
	App, AF, core, ship = base.setup(TargetEvasion=10, GuidanceStrength=80, TubeMaxAngle=30)
	S = types.ModuleType("Custom.Spaceframe.Modules.AutoFire.Solution")
	sys.modules["Custom.Spaceframe.Modules.AutoFire.Solution"] = S
	sys.modules["Custom.Spaceframe.Modules.AutoFire"].Solution = S
	AF.Start(core)
	assert not hasattr(AF, "ApplySolutionConfig")
	assert [n for n in dir(S) if n.isupper()] == []


def test_tap_fire_alternates():
	# Tapping the fire key fires torpedoes faster than holding it: press on
	# one cycle, release on the next, while the solution holds.
	App, AF, ship, target, torps = setup(90.0, tap=1)
	for i in range(4):
		AF.FireCycle()
	assert [c[0] for c in torps.calls] == ["start", "stop", "start", "stop"]


def test_tap_fire_stops_when_bad():
	App, AF, ship, target, torps = setup(90.0, tap=1)
	AF.FireCycle()
	sys.modules["Custom.Spaceframe.Modules.AutoFire.Solution"].score = 0.0
	AF.FireCycle()
	AF.FireCycle()
	assert [c[0] for c in torps.calls] == ["start", "stop"]


def test_hold_when_tap_off():
	App, AF, ship, target, torps = setup(90.0, tap=0)
	for i in range(4):
		AF.FireCycle()
	assert [c[0] for c in torps.calls] == ["start"]


def test_phasers_never_tapped():
	App, AF, ship, target, torps = setup(0.0, tap=1)
	primary = mock_app.WeaponGroup([mock_app.Bank(100.0, 1.0, 1)])
	ship.groups[App.ShipClass.WG_PRIMARY] = primary
	for i in range(4):
		AF.FireCycle()
	assert [c[0] for c in primary.calls] == ["start"]


def test_rule_1_also_fires():
	App, AF, ship, target, torps = setup(5.0, rule=1)
	AF.FireCycle()
	assert torps.starts() == 1


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
