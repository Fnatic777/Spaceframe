"""Task 3 tests: torpedoes fire on the firing solution."""
import os
import sys
import types
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mock_app
import test_autofire_base as base


def setup(score=75.0, available=10, reserve=0, ready=1, tap=0, rule=1):
	App, AF, core, ship = base.setup(TorpedoMinSolution=70, TorpedoReserve=reserve, TapFire=tap, TorpedoRule=rule)
	S = types.ModuleType("Custom.Spaceframe.Modules.AutoFire.Solution")
	S.Score = lambda *a: score
	S.GetProjectileInfo = lambda w, s: (100.0, 0.1, 10.0, 0.0)
	sys.modules["Custom.Spaceframe.Modules.AutoFire.Solution"] = S
	sys.modules["Custom.Spaceframe.Modules.AutoFire"].Solution = S
	S.TORPEDO_RULE = rule
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


def test_torps_fire_above_min():
	App, AF, ship, target, torps = setup(75.0)
	AF.FireCycle()
	assert torps.starts() == 1


def test_torps_hold_below_min():
	App, AF, ship, target, torps = setup(65.0)
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


def test_torps_stop_when_solution_drops():
	App, AF, ship, target, torps = setup(90.0)
	AF.FireCycle()
	sys.modules["Custom.Spaceframe.Modules.AutoFire.Solution"].Score = lambda *a: 40.0
	AF.FireCycle()
	assert torps.stops() == 1


def test_torps_score_error_does_not_break_phasers():
	App, AF, ship, target, torps = setup(90.0)

	def boom(*a):
		raise ValueError("bad")
	sys.modules["Custom.Spaceframe.Modules.AutoFire.Solution"].Score = boom
	primary = mock_app.WeaponGroup([mock_app.Bank(100.0, 1.0, 1)])
	ship.groups[App.ShipClass.WG_PRIMARY] = primary
	AF.FireCycle()
	assert primary.starts() == 1 and torps.starts() == 0


def test_target_evasion_config():
	App, AF, core, ship = base.setup(TargetEvasion=10, GuidanceStrength=80, GuidanceLimit=40, TargetSize=120, TubeMaxAngle=30)
	S = types.ModuleType("Custom.Spaceframe.Modules.AutoFire.Solution")
	S.MANEUVER_WEIGHT = 0.5
	sys.modules["Custom.Spaceframe.Modules.AutoFire.Solution"] = S
	sys.modules["Custom.Spaceframe.Modules.AutoFire"].Solution = S
	AF.Start(core)
	assert abs(S.MANEUVER_WEIGHT - 0.1) < 1e-9
	assert abs(S.GUIDANCE_STRENGTH - 0.8) < 1e-9
	assert abs(S.GUIDANCE_LIMIT - 0.4) < 1e-9
	assert abs(S.TARGET_SIZE - 1.2) < 1e-9
	assert S.MAX_ANGLE == 30.0


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
	sys.modules["Custom.Spaceframe.Modules.AutoFire.Solution"].Score = lambda *a: 10.0
	AF.FireCycle()
	AF.FireCycle()
	assert [c[0] for c in torps.calls] == ["start", "stop"]


def test_hold_when_tap_off():
	App, AF, ship, target, torps = setup(90.0, tap=0)
	for i in range(4):
		AF.FireCycle()
	assert [c[0] for c in torps.calls] == ["start"]


def test_phasers_never_tapped():
	App, AF, ship, target, torps = setup(10.0, tap=1)
	primary = mock_app.WeaponGroup([mock_app.Bank(100.0, 1.0, 1)])
	ship.groups[App.ShipClass.WG_PRIMARY] = primary
	for i in range(4):
		AF.FireCycle()
	assert [c[0] for c in primary.calls] == ["start"]


def test_cone_rule_fires_in_cone():
	# Cone rule: any tube inside the cone fires (TorpedoMinSolution unused).
	App, AF, ship, target, torps = setup(5.0, rule=2)
	AF.FireCycle()
	assert torps.starts() == 1


def test_cone_rule_holds_outside():
	App, AF, ship, target, torps = setup(0.0, rule=2)
	AF.FireCycle()
	assert torps.starts() == 0


def test_cone_config():
	App, AF, core, ship = base.setup(TorpedoRule=2, ConeAngleFar=12, ConeAngleNear=40, ConeFarDistance=35, ConeNearDistance=4)
	S = types.ModuleType("Custom.Spaceframe.Modules.AutoFire.Solution")
	sys.modules["Custom.Spaceframe.Modules.AutoFire.Solution"] = S
	sys.modules["Custom.Spaceframe.Modules.AutoFire"].Solution = S
	AF.Start(core)
	assert S.TORPEDO_RULE == 2 and S.CONE_FAR == 12.0 and S.CONE_NEAR == 40.0
	assert abs(S.CONE_FAR_DISTANCE - 35 / 0.175) < 1e-6 and abs(S.CONE_NEAR_DISTANCE - 4 / 0.175) < 1e-6


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
