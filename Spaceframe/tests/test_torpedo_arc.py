"""TorpedoRule 3 (arc percent on the tube's fixed 30 degree cone): Solution.TubeDepth
and the ready/hysteresis rule of Auto Fire."""
import math
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mock_app
import test_autofire_base as base

HALF = 0.5235988	# 30 degrees
GROUP = 0		# WG_PRIMARY


def P(x, y, z):
	return mock_app.Point(x, y, z)


def deg(f):
	return f * math.pi / 180.0


def load_solution():
	S = mock_app.load_module("Modules/AutoFire/Solution.py", "Custom.Spaceframe.Modules.AutoFire.Solution")
	sys.modules["Custom.Spaceframe.Modules.AutoFire"].Solution = S
	return S


def setup_solution():
	App = mock_app.make_app()
	mock_app.install(App)
	base.register_packages(base.make_config())
	S = load_solution()
	ship = mock_app.Ship("Galaxy", 1)
	return App, S, ship, mock_app.Tube()


def at(fWidth, fHeight, fDist=10.0):
	# A point at the given width/height angles (radians) from a tube at the origin.
	return P(fDist, fDist * math.tan(fWidth), fDist * math.tan(fHeight))


# --- Solution: TubeFrame / TubeDepth ----------------------------------------
def test_depth_centre_is_zero():
	App, S, ship, tube = setup_solution()
	assert abs(S.TorpedoArcDepth(ship, tube, P(10.0, 0.0, 0.0))) < 1e-9


def test_depth_fractions_of_the_cone():
	App, S, ship, tube = setup_solution()
	assert abs(S.TorpedoArcDepth(ship, tube, at(deg(15.0), 0.0)) - 0.5) < 1e-4
	assert abs(S.TorpedoArcDepth(ship, tube, at(deg(30.0), 0.0)) - 1.0) < 1e-4
	assert S.TorpedoArcDepth(ship, tube, at(deg(33.0), 0.0)) > 1.0
	assert abs(S.TorpedoArcDepth(ship, tube, at(0.0, deg(-30.0))) - 1.0) < 1e-4


def test_depth_both_axes_deeper_counts():
	App, S, ship, tube = setup_solution()
	assert abs(S.TorpedoArcDepth(ship, tube, at(deg(15.0), deg(24.0))) - 0.8) < 1e-4
	assert abs(S.TorpedoArcDepth(ship, tube, at(deg(24.0), deg(15.0))) - 0.8) < 1e-4


def test_depth_behind_is_99():
	App, S, ship, tube = setup_solution()
	assert S.TorpedoArcDepth(ship, tube, P(-10.0, 0.0, 0.0)) == 99.0
	assert S.TorpedoArcDepth(ship, tube, P(0.0, 10.0, 0.0)) == 99.0	# dot with forward == 0


def test_depth_follows_ship_rotation():
	# The ship turned 90 degrees about z: the tube's forward is world +y.
	App, S, ship, tube = setup_solution()
	ship.rot = [[0.0, -1.0, 0.0], [1.0, 0.0, 0.0], [0.0, 0.0, 1.0]]
	assert abs(S.TorpedoArcDepth(ship, tube, P(0.0, 10.0, 0.0))) < 1e-9
	assert S.TorpedoArcDepth(ship, tube, P(10.0, 0.0, 0.0)) == 99.0


def test_depth_uses_the_tube_position():
	App, S, ship, tube = setup_solution()
	tube.pPos = P(0.0, 10.0, 0.0)
	assert abs(S.TorpedoArcDepth(ship, tube, P(10.0, 10.0, 0.0))) < 1e-9


def test_depth_agrees_with_is_in_arc():
	# Both signs of Up: the cone is symmetric, so the sign never matters.
	App, S, ship, tube = setup_solution()
	for iSign in (1, -1):
		tube.iUpSign = iSign
		for iW in range(-6, 7):
			for iH in range(-6, 7):
				fW = deg(iW * 7.0)
				fH = deg(iH * 7.0)
				fDepth = S.TorpedoArcDepth(ship, tube, at(fW, fH))
				assert (fDepth <= 1.0) == bool(tube.IsInArc(at(fW, fH))), (iSign, iW, iH, fDepth)
		assert S.TorpedoArcDepth(ship, tube, P(-5.0, 1.0, 1.0)) > 1.0
		assert not tube.IsInArc(P(-5.0, 1.0, 1.0))


def test_depth_unavailable_is_none():
	App, S, ship, tube = setup_solution()

	def boom():
		raise TypeError("GetDirection")
	tube.GetDirection = boom
	assert S.TubeFrame(ship, tube) == None
	assert S.TorpedoArcDepth(ship, tube, P(10.0, 0.0, 0.0)) == None
	assert S.TubeDepth(None, P(10.0, 0.0, 0.0)) == None


# --- AutoFire: TorpedoRule 3 --------------------------------------------------
def rule3(**kw):
	dCfg = {"TorpedoRule": 1, "TapFire": 0, "TorpedoArcPercentFar": 50,
		"TorpedoArcPercentNear": 90, "TorpedoArcFarDistance": 30, "TorpedoArcNearDistance": 5,
		"TorpedoArcHysteresis": 10}
	for k in kw:
		dCfg[k] = kw[k]
	App, AF, core, ship = base.setup(**dCfg)
	S = load_solution()
	target = mock_app.Ship("Bug", 7)
	core.g_pMission = mock_app.Mission([target])
	ship.target = target
	tube = mock_app.Tube()
	torps = mock_app.WeaponGroup([tube])
	torps.torpedo = 1
	ship.groups[GROUP] = torps
	return App, AF, core, ship, target, torps, S


def place(target, fDepth, fKm):
	# Target at fKm kilometres, at fDepth of the 30 degree cone (width axis).
	fDist = fKm / 0.175
	fAngle = fDepth * HALF
	target.pos = P(fDist * math.cos(fAngle), fDist * math.sin(fAngle), 0.0)


def best(AF, ship, torps, target):
	return AF.BestTorpedoScore(ship, torps, target)


def test_config_read():
	App, AF, core, ship, target, torps, S = rule3(TorpedoArcPercentFar=40, TorpedoArcPercentNear=80,
		TorpedoArcFarDistance=20, TorpedoArcNearDistance=2, TorpedoArcHysteresis=5)
	assert AF.g_iTorpedoRule == 1 and AF.g_fTorpArcFar == 40.0 and AF.g_fTorpArcNear == 80.0
	assert AF.g_fTorpArcHysteresis == 5.0
	assert abs(AF.g_fTorpArcFarDistance - 20 / 0.175) < 1e-6
	assert abs(AF.g_fTorpArcNearDistance - 2 / 0.175) < 1e-6


def test_config_defaults():
	App, AF, core, ship = base.setup()
	assert AF.g_fTorpArcFar == 50.0 and AF.g_fTorpArcNear == 90.0 and AF.g_fTorpArcHysteresis == 10.0
	assert abs(AF.g_fTorpArcFarDistance - 30 / 0.175) < 1e-6
	assert abs(AF.g_fTorpArcNearDistance - 5 / 0.175) < 1e-6


def test_allowed_uses_the_torpedo_band():
	App, AF, core, ship, target, torps, S = rule3()
	tBand = AF.ArcBand("torpedo")[0]
	assert AF.ArcAllowed(100 / 0.175, tBand) == 50.0
	assert AF.ArcAllowed(1 / 0.175, tBand) == 90.0
	assert abs(AF.ArcAllowed(17.5 / 0.175, tBand) - 70.0) < 1e-6
	AF.g_fArcFar = 10.0	# the pulse band is separate
	assert AF.ArcAllowed(100 / 0.175, tBand) == 50.0
	assert AF.ArcAllowed(100 / 0.175) == 10.0


def test_tube_within_percent_fires_and_score_is_depth():
	App, AF, core, ship, target, torps, S = rule3()

	place(target, 0.4, 40.0)
	assert AF.TorpedoTarget(ship, torps, [target], GROUP) == target
	assert abs(AF.g_dScore[GROUP] - 60.0) < 0.5


def test_tube_outside_percent_holds_fire_though_in_arc():
	App, AF, core, ship, target, torps, S = rule3()
	place(target, 0.6, 40.0)
	assert torps.lChildren[0].IsInArc(target.GetWorldLocation())
	assert AF.TorpedoTarget(ship, torps, [target], GROUP) == None


def test_low_score_still_fires():
	# A score of 15: the arc rule only needs >= 1.
	App, AF, core, ship, target, torps, S = rule3()
	place(target, 0.85, 3.0)
	assert AF.TorpedoTarget(ship, torps, [target], GROUP) == target
	assert AF.g_dScore[GROUP] < 70.0


def test_hysteresis_holds_then_releases():
	App, AF, core, ship, target, torps, S = rule3()
	tube = torps.lChildren[0]
	place(target, 0.45, 40.0)
	assert best(AF, ship, torps, target) > 0.0
	assert (tube.GetObjID(), 7) in AF.g_dArcReady
	place(target, 0.55, 40.0)
	assert best(AF, ship, torps, target) > 0.0	# held: limit 50 + 10
	place(target, 0.65, 40.0)
	assert best(AF, ship, torps, target) == 0.0	# released
	place(target, 0.55, 40.0)
	assert best(AF, ship, torps, target) == 0.0	# needs <= 50 to start again


def test_hysteresis_zero_is_off():
	for iHys in (0, -5):
		App, AF, core, ship, target, torps, S = rule3(TorpedoArcHysteresis=iHys)
		place(target, 0.45, 40.0)
		assert best(AF, ship, torps, target) > 0.0
		assert AF.g_dArcReady == {}
		place(target, 0.51, 40.0)	# 1 point past the allowed 50
		assert best(AF, ship, torps, target) == 0.0
		assert AF.g_dArcReady == {}
	App, AF, core, ship, target, torps, S = rule3(TorpedoArcHysteresis=10)
	place(target, 0.45, 40.0)
	assert best(AF, ship, torps, target) > 0.0
	place(target, 0.51, 40.0)
	assert best(AF, ship, torps, target) > 0.0	# held with 10
	assert len(AF.g_dArcReady) == 1


def test_unready_tube_scores_zero_and_forgets():
	App, AF, core, ship, target, torps, S = rule3()
	tube = torps.lChildren[0]
	place(target, 0.45, 40.0)
	assert best(AF, ship, torps, target) > 0.0
	assert len(AF.g_dArcReady) == 1
	tube.iReady = 0
	assert best(AF, ship, torps, target) == 0.0
	assert AF.g_dArcReady == {}


def test_lifetime_check():
	App, AF, core, ship, target, torps, S = rule3()
	place(target, 0.1, 40.0)
	S.g_dScripts["Tactical.Projectiles.Photon1"] = (0.0, 0.0, 1.0)	# flies 1 s: 100 units
	assert best(AF, ship, torps, target) == 0.0
	assert AF.g_dArcReady == {}
	S.g_dScripts["Tactical.Projectiles.Photon1"] = (0.0, 0.0, 100.0)
	assert best(AF, ship, torps, target) > 0.0


def test_lead_point_comes_from_the_ship():
	# The target moves sideways: the lead point is further off the centre.
	App, AF, core, ship, target, torps, S = rule3()
	target.pos = P(100.0, 0.0, 0.0)
	target.vel = P(0.0, 60.0, 0.0)
	fLead = best(AF, ship, torps, target)
	AF.ForgetArc()
	target.vel = P(0.0, 0.0, 0.0)
	fStill = best(AF, ship, torps, target)
	assert fStill > fLead


def test_frame_failure_falls_back_to_is_in_arc():
	App, AF, core, ship, target, torps, S = rule3()
	tube = torps.lChildren[0]

	def boom():
		raise TypeError("GetDirection")
	tube.GetDirection = boom
	place(target, 0.1, 10.0)
	tube.iArc = 1
	assert best(AF, ship, torps, target) == 1.0
	tube.iArc = 0
	assert best(AF, ship, torps, target) == 0.0
	tube.iArc = "raise"
	assert best(AF, ship, torps, target) == 1.0	# nothing to check: ready


def test_settle_keeps_listed_ids_only():
	App, AF, core, ship, target, torps, S = rule3()
	tube = torps.lChildren[0]
	AF.g_dArcReady[(tube.GetObjID(), 7)] = 1
	AF.g_dArcReady[(tube.GetObjID(), 8)] = 1
	AF.g_dArcReady[(tube.GetObjID(), 9)] = 1
	AF.ArcSettle(torps, [7, 9])
	assert sorted(AF.g_dArcReady.keys()) == [(tube.GetObjID(), 7), (tube.GetObjID(), 9)]
	AF.ArcSettle(torps, None)
	assert AF.g_dArcReady == {}


def test_legacy_rule_3_is_rule_2():
	App, AF, core, ship, target, torps, S = rule3(TorpedoRule=3)
	assert AF.g_iTorpedoRule == 2


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
