"""Solution helpers: projectile data from the scripts and the lead point
(the firing solution score and cone of the old rules 1 and 2 are gone)."""
import math
import os
import sys
import types
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mock_app
import test_autofire_base as base


def load():
	App = mock_app.make_app()
	mock_app.install(App)
	base.register_packages(base.make_config())
	S = mock_app.load_module("Modules/AutoFire/Solution.py", "Custom.Spaceframe.Modules.AutoFire.Solution")
	return App, S


def scene(dist=10.0, vel=None, predict=1):
	target = mock_app.Ship("Bug", 7)
	target.pos = mock_app.Point(dist, 0.0, 0.0)
	target.predict = predict
	if vel:
		target.vel = vel
	return target


def test_removed_rule_api_is_gone():
	App, S = load()
	for sName in ("Score", "ScoreValues", "ConeScore", "GetTargetAccel", "MAX_ANGLE", "CONE_FAR", "PULSE_CONE_FAR"):
		assert not hasattr(S, sName), sName


def test_lead_point_leads_moving_target():
	# Target crossing: the lead point is ahead of where it is now.
	App, S = load()
	target = scene(10.0, vel=mock_app.Point(0.0, 5.0, 0.0))
	vPoint = S.LeadPoint(target, None, mock_app.Point(0.0, 0.0, 0.0), 10.0)
	assert vPoint.y > 0.0
	assert abs(vPoint.x - 10.0) < 1e-6


def test_lead_point_no_prediction():
	App, S = load()
	target = scene(10.0, predict=0)
	vPoint = S.LeadPoint(target, None, mock_app.Point(0.0, 0.0, 0.0), 10.0)
	assert abs(vPoint.x - 10.0) < 1e-6 and abs(vPoint.y) < 1e-6


def test_lead_point_speed_unknown_is_target_now():
	App, S = load()
	target = scene(10.0, vel=mock_app.Point(0.0, 5.0, 0.0))
	vPoint = S.LeadPoint(target, None, mock_app.Point(0.0, 0.0, 0.0), 0.0)
	assert abs(vPoint.y) < 1e-6


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


def test_pulse_weapon_firing_guided_missiles():
	# A pulse-class weapon whose projectile is guided (e.g. Orion's Missile):
	# the guidance time and lifetime of its script come through.
	App, S = load()
	mod = types.ModuleType("Tactical.Projectiles.MissileX")
	mod.GetLifetime = lambda: 30.0
	mod.GetGuidanceLifetime = lambda: 30.0
	sys.modules["Tactical.Projectiles.MissileX"] = mod
	sys.modules["Tactical"] = types.ModuleType("Tactical")
	sys.modules["Tactical.Projectiles"] = types.ModuleType("Tactical.Projectiles")
	sys.modules["Tactical"].Projectiles = sys.modules["Tactical.Projectiles"]
	sys.modules["Tactical.Projectiles"].MissileX = mod
	system = mock_app.WeaponGroup([])
	system.pulse = 1
	pWeapon = mock_app.Pulse()
	pWeapon.GetProperty = lambda: type("P", (), {"GetModuleName": lambda self: "Tactical.Projectiles.MissileX"})()
	assert S.GetProjectileInfo(pWeapon, system) == (150.0, 30.0, 0.0, 30.0)


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
