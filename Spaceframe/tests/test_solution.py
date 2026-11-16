"""Task 3 tests: firing solution score."""
import math
import sys
import types
sys.path.insert(0, "/mnt/user-data/outputs/Spaceframe/tests")
import mock_app
import test_autofire_base as base


def load():
	App = mock_app.make_app()
	mock_app.install(App)
	base.register_packages(base.make_config())
	S = mock_app.load_module("Modules/AutoFire/Solution.py", "Custom.Spaceframe.Modules.AutoFire.Solution")
	return App, S


def scene(dist=10.0, angle_deg=0.0, accel=0.0, radius=1.0, vel=None, predict=1):
	ship = mock_app.Ship("Galaxy", 1)
	target = mock_app.Ship("Bug", 7)
	target.pos = mock_app.Point(dist, 0.0, 0.0)
	target.radius = radius
	target.accel = accel
	target.predict = predict
	if vel:
		target.vel = vel
	a = math.radians(angle_deg)
	tube = mock_app.Tube(mock_app.Point(math.cos(a), math.sin(a), 0.0))
	return ship, target, tube


def test_score_aligned_still():
	App, S = load()
	ship, target, tube = scene(10.0)
	f = S.Score(ship, target, None, tube, tube.CalculateRoughDirection(), (100.0, 0.1, 10.0, 0.0))
	assert f >= 95, f


def test_score_behind():
	App, S = load()
	ship, target, tube = scene(10.0, 120.0)
	assert S.Score(ship, target, None, tube, tube.CalculateRoughDirection(), (100.0, 0.1, 10.0, 0.0)) == 0


def test_score_far_maneuvering():
	App, S = load()
	ship, target, tube = scene(30.0, 0.0, accel=5.0)
	f = S.Score(ship, target, None, tube, tube.CalculateRoughDirection(), (10.0, 0.0, 0.0, 0.0))
	assert f < 70, f


def test_score_guidance_helps():
	App, S = load()
	ship, target, tube = scene(10.0, 8.0)
	f0 = S.Score(ship, target, None, tube, tube.CalculateRoughDirection(), (10.0, 0.0, 10.0, 0.0))
	f3 = S.Score(ship, target, None, tube, tube.CalculateRoughDirection(), (10.0, 3.0, 10.0, 0.0))
	assert f3 > f0, (f0, f3)


def test_score_beyond_lifetime():
	App, S = load()
	ship, target, tube = scene(30.0)
	assert S.Score(ship, target, None, tube, tube.CalculateRoughDirection(), (10.0, 0.0, 0.0, 2.0)) == 0


def test_score_leads_moving_target():
	# Target crossing: tube pointed at where it will be scores higher than
	# a tube pointed at where it is now.
	App, S = load()
	ship, target, tube = scene(10.0, 0.0, vel=mock_app.Point(0.0, 5.0, 0.0))
	tInfo = (10.0, 0.0, 0.0, 0.0)
	now = S.Score(ship, target, None, tube, tube.CalculateRoughDirection(), tInfo)
	lead = mock_app.Point(10.0, 5.0, 0.0)
	lead.Unitize()
	ahead = S.Score(ship, target, None, tube, lead, tInfo)
	assert ahead > now, (now, ahead)


def test_score_no_prediction():
	App, S = load()
	ship, target, tube = scene(10.0, predict=0)
	f = S.Score(ship, target, None, tube, tube.CalculateRoughDirection(), (100.0, 0.1, 10.0, 0.0))
	assert f >= 95, f


def test_projectile_info_from_script():
	App, S = load()
	mod = types.ModuleType("Tactical.Projectiles.Photon1")
	mod.GetLaunchSpeed = lambda: 100.0
	mod.GetGuidanceLifetime = lambda: 0.1
	mod.GetMaxAngularAccel = lambda: 10.0
	sys.modules["Tactical.Projectiles.Photon1"] = mod
	sys.modules["Tactical"] = types.ModuleType("Tactical")
	sys.modules["Tactical.Projectiles"] = types.ModuleType("Tactical.Projectiles")
	sys.modules["Tactical"].Projectiles = sys.modules["Tactical.Projectiles"]
	sys.modules["Tactical.Projectiles"].Photon1 = mod
	system = mock_app.WeaponGroup([])
	system.torpedo = 1
	system.ammo = mock_app.Ammo(100.0, "Tactical.Projectiles.Photon1")
	assert S.GetProjectileInfo(None, system) == (100.0, 0.1, 10.0, 0.0)


def test_target_size_scales():
	App, S = load()
	ship, target, tube = scene(10.0, 0.0, accel=3.0)
	tInfo = (10.0, 0.0, 0.0, 0.0)
	S.TARGET_SIZE = 1.0
	f1 = S.Score(ship, target, None, tube, tube.CalculateRoughDirection(), tInfo)
	S.TARGET_SIZE = 2.0
	f2 = S.Score(ship, target, None, tube, tube.CalculateRoughDirection(), tInfo)
	assert f2 > f1, (f1, f2)


def test_guidance_strength_zero():
	App, S = load()
	ship, target, tube = scene(10.0, 8.0)
	S.GUIDANCE_STRENGTH = 0.0
	f0 = S.Score(ship, target, None, tube, tube.CalculateRoughDirection(), (10.0, 0.0, 10.0, 0.0))
	f3 = S.Score(ship, target, None, tube, tube.CalculateRoughDirection(), (10.0, 3.0, 10.0, 0.0))
	assert f0 == f3, (f0, f3)


def test_guidance_limit():
	App, S = load()
	ship, target, tube = scene(10.0, 8.0)
	S.GUIDANCE_LIMIT = 0.0
	f = S.Score(ship, target, None, tube, tube.CalculateRoughDirection(), (10.0, 3.0, 10.0, 0.0))
	assert f == 0, f


def test_max_angle():
	# Tube more than MAX_ANGLE (degrees) off the predicted position: 0,
	# even when the guidance could have steered the shot back.
	App, S = load()
	ship, target, tube = scene(10.0, 20.0)
	tInfo = (10.0, 3.0, 10.0, 0.0)
	S.MAX_ANGLE = 90.0
	assert S.Score(ship, target, None, tube, tube.CalculateRoughDirection(), tInfo) > 0
	S.MAX_ANGLE = 15.0
	assert S.Score(ship, target, None, tube, tube.CalculateRoughDirection(), tInfo) == 0


def test_max_angle_above_90():
	# TubeMaxAngle above 90: a tube pointing away may still fire when the
	# guidance can bring the torpedo round (miss taken as the whole distance).
	App, S = load()
	ship, target, tube = scene(10.0, 100.0)
	tInfo = (10.0, 3.0, 10.0, 0.0)
	S.GUIDANCE_LIMIT = 1.0
	S.MAX_ANGLE = 120.0
	assert S.Score(ship, target, None, tube, tube.CalculateRoughDirection(), tInfo) > 0
	S.MAX_ANGLE = 90.0
	assert S.Score(ship, target, None, tube, tube.CalculateRoughDirection(), tInfo) == 0


def test_score_self_aimed():
	# No direction (a pulse cannon aims itself): only evasion and lifetime.
	App, S = load()
	ship, target, tube = scene(10.0, 60.0)
	assert S.Score(ship, target, None, tube, None, (150.0, 0.0, 0.0, 10.0)) >= 95
	assert S.Score(ship, target, None, tube, None, (1.0, 0.0, 0.0, 2.0)) == 0


def test_pulse_projectile_info():
	App, S = load()
	mod = types.ModuleType("Tactical.Projectiles.Disruptor1")
	mod.GetLifetime = lambda: 10.0
	sys.modules["Tactical.Projectiles.Disruptor1"] = mod
	sys.modules["Tactical"] = types.ModuleType("Tactical")
	sys.modules["Tactical.Projectiles"] = types.ModuleType("Tactical.Projectiles")
	sys.modules["Tactical"].Projectiles = sys.modules["Tactical.Projectiles"]
	sys.modules["Tactical.Projectiles"].Disruptor1 = mod
	system = mock_app.WeaponGroup([])
	system.pulse = 1
	assert S.GetProjectileInfo(mock_app.Pulse(), system) == (150.0, 0.0, 0.0, 10.0)


def cone(S):
	S.TORPEDO_RULE = 2
	S.CONE_FAR = 15.0
	S.CONE_NEAR = 45.0
	S.CONE_FAR_DISTANCE = 30.0
	S.CONE_NEAR_DISTANCE = 5.0


def test_cone_far_inside():
	App, S = load()
	cone(S)
	ship, target, tube = scene(40.0, 10.0)
	assert S.Score(ship, target, None, tube, tube.CalculateRoughDirection(), (100.0, 0.1, 10.0, 0.0)) > 0


def test_cone_far_outside():
	App, S = load()
	cone(S)
	ship, target, tube = scene(40.0, 20.0)
	assert S.Score(ship, target, None, tube, tube.CalculateRoughDirection(), (100.0, 0.1, 10.0, 0.0)) == 0


def test_cone_opens_when_near():
	App, S = load()
	cone(S)
	ship, target, tube = scene(4.0, 40.0)
	assert S.Score(ship, target, None, tube, tube.CalculateRoughDirection(), (100.0, 0.1, 10.0, 0.0)) > 0
	ship, target, tube = scene(17.5, 28.0)	# halfway: 30 degrees allowed
	assert S.Score(ship, target, None, tube, tube.CalculateRoughDirection(), (100.0, 0.1, 10.0, 0.0)) > 0
	ship, target, tube = scene(17.5, 32.0)
	assert S.Score(ship, target, None, tube, tube.CalculateRoughDirection(), (100.0, 0.1, 10.0, 0.0)) == 0


def test_cone_centred_scores_high():
	App, S = load()
	cone(S)
	ship, target, tube = scene(40.0, 0.0)
	assert S.Score(ship, target, None, tube, tube.CalculateRoughDirection(), (100.0, 0.1, 10.0, 0.0)) >= 99


def test_cone_respects_lifetime():
	App, S = load()
	cone(S)
	ship, target, tube = scene(40.0, 0.0)
	assert S.Score(ship, target, None, tube, tube.CalculateRoughDirection(), (10.0, 0.1, 10.0, 2.0)) == 0


def test_cone_not_for_pulse():
	# Pulse weapons aim themselves: the cone rule is for torpedo tubes.
	App, S = load()
	cone(S)
	ship, target, tube = scene(10.0, 0.0, accel=3.0)
	S.TORPEDO_RULE = 1
	f1 = S.Score(ship, target, None, tube, None, (10.0, 0.0, 0.0, 0.0))
	S.TORPEDO_RULE = 2
	f2 = S.Score(ship, target, None, tube, None, (10.0, 0.0, 0.0, 0.0))
	assert f1 == f2


def test_rule_argument():
	# The rule can be given per call (pulse weapons have their own).
	App, S = load()
	cone(S)
	S.TORPEDO_RULE = 1
	ship, target, tube = scene(40.0, 20.0)
	d = tube.CalculateRoughDirection()
	assert S.Score(ship, target, None, tube, d, (100.0, 0.1, 10.0, 0.0), 2) == 0
	ship, target, tube = scene(40.0, 10.0)
	d = tube.CalculateRoughDirection()
	assert S.Score(ship, target, None, tube, d, (100.0, 0.1, 10.0, 0.0), 2) > 0


def test_pulse_cone_separate():
	# The pulse cone has its own angles: same shot, torpedo cone (15) says
	# no, pulse cone (60) says yes.
	App, S = load()
	cone(S)
	S.PULSE_CONE_FAR = 60.0
	S.PULSE_CONE_NEAR = 90.0
	S.PULSE_CONE_FAR_DISTANCE = 30.0
	S.PULSE_CONE_NEAR_DISTANCE = 5.0
	ship, target, tube = scene(40.0, 40.0)
	d = tube.CalculateRoughDirection()
	tInfo = (100.0, 0.0, 0.0, 0.0)
	assert S.Score(ship, target, None, tube, d, tInfo, 2) == 0
	assert S.Score(ship, target, None, tube, d, tInfo, 2, 1) > 0


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
