"""Task 5 tests: pulse weapons fire on the firing solution."""
import sys
import types
sys.path.insert(0, "/mnt/user-data/outputs/Spaceframe/tests")
import mock_app
import test_autofire_base as base


def setup(score=75.0, charge=5.0, arc=1, tap=0, rule=1):
	App, AF, core, ship = base.setup(PulseMinSolution=50, TapFire=tap, PulseRule=rule)
	S = types.ModuleType("Custom.Spaceframe.Modules.AutoFire.Solution")
	S.calls = []

	def Score(pShip, pTarget, vOffset, pWeapon, vDirection, tInfo, iRule=None, bPulse=0):
		S.calls.append(vDirection)
		S.rules.append(iRule)
		S.pulse.append(bPulse)
		return S.score
	S.rules = []
	S.pulse = []
	S.Score = Score
	S.score = score
	S.GetProjectileInfo = lambda w, s: (150.0, 0.0, 0.0, 10.0)
	sys.modules["Custom.Spaceframe.Modules.AutoFire.Solution"] = S
	sys.modules["Custom.Spaceframe.Modules.AutoFire"].Solution = S
	target = mock_app.Ship("Bug", 7)
	target.pos = mock_app.Point(10.0, 0.0, 0.0)
	ship.target = target
	core.g_pMission = mock_app.Mission([target])	# the target is an enemy
	pulse = mock_app.WeaponGroup([mock_app.Pulse(charge, 2.0, arc)])
	pulse.pulse = 1
	ship.groups[App.ShipClass.WG_TERTIARY] = pulse
	AF.Toggle()
	return App, AF, ship, target, pulse, S


def test_pulse_fires_above_min():
	App, AF, ship, target, pulse, S = setup(75.0)
	AF.FireCycle()
	assert pulse.starts() == 1


def test_pulse_aims_itself():
	# A pulse cannon turns its shot to the target inside its arc: no aim
	# error from the mount direction (direction None).
	App, AF, ship, target, pulse, S = setup(75.0)
	AF.FireCycle()
	assert S.calls == [None]


def test_pulse_hold_below_min():
	App, AF, ship, target, pulse, S = setup(40.0)
	AF.FireCycle()
	assert pulse.starts() == 0


def test_pulse_no_charge():
	App, AF, ship, target, pulse, S = setup(90.0, charge=1.0)
	AF.FireCycle()
	assert pulse.starts() == 0


def test_pulse_out_of_arc():
	App, AF, ship, target, pulse, S = setup(90.0, arc=0)
	AF.FireCycle()
	assert pulse.starts() == 0


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


def test_pulse_rule_solution():
	App, AF, ship, target, pulse, S = setup(75.0, rule=1)
	AF.FireCycle()
	assert S.calls == [None] and S.rules == [1]


def test_pulse_rule_cone():
	# Cone rule: the cone is around where the pulse weapon points, and any
	# weapon inside it fires (PulseMinSolution not used).
	App, AF, ship, target, pulse, S = setup(5.0, rule=2)
	AF.FireCycle()
	assert S.rules == [2] and S.calls[0] is not None
	assert pulse.starts() == 1


def test_pulse_rule_cone_outside():
	App, AF, ship, target, pulse, S = setup(0.0, rule=2)
	AF.FireCycle()
	assert pulse.starts() == 0


def test_pulse_cone_is_the_pulse_one():
	App, AF, ship, target, pulse, S = setup(5.0, rule=2)
	AF.FireCycle()
	assert S.pulse == [1]


def test_pulse_cone_config():
	App, AF, core, ship = base.setup(PulseConeAngleFar=50, PulseConeAngleNear=80, PulseConeFarDistance=20, PulseConeNearDistance=2)
	S = types.ModuleType("Custom.Spaceframe.Modules.AutoFire.Solution")
	sys.modules["Custom.Spaceframe.Modules.AutoFire.Solution"] = S
	sys.modules["Custom.Spaceframe.Modules.AutoFire"].Solution = S
	AF.Start(core)
	assert S.PULSE_CONE_FAR == 50.0 and S.PULSE_CONE_NEAR == 80.0
	assert abs(S.PULSE_CONE_FAR_DISTANCE - 20 / 0.175) < 1e-6 and abs(S.PULSE_CONE_NEAR_DISTANCE - 2 / 0.175) < 1e-6


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
