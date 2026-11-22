"""Cone / ellipse arc depth (TorpedoArcShape / PulseArcShape): Solution.ConeDepth and
its use by ArcScore, against the old box depth."""
import math
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mock_app
import test_autofire_base as base
import test_torpedo_arc as TT
import test_autofire_arc as TA

DIST = 40.0 / 0.175	# 40 km in world units


def P(x, y, z):
	return mock_app.Point(x, y, z)


def deg(f):
	return f * math.pi / 180.0


def at(fH, fV, fDist=10.0):
	# Point at width/height angles (degrees) from a weapon at the origin.
	return P(fDist, fDist * math.tan(deg(fH)), fDist * math.tan(deg(fV)))


def put(target, fH, fV):
	target.pos = at(fH, fV, DIST)


# --- ConeDepth: symmetric torpedo tube ---------------------------------------
def test_tube_axis_is_zero():
	App, S, ship, tube = TT.setup_solution()
	tFrame = S.TubeFrame(ship, tube)
	assert abs(S.TubeConeDepth(tFrame, at(0, 0))) < 1e-9


def test_tube_side_and_corners():
	App, S, ship, tube = TT.setup_solution()
	tFrame = S.TubeFrame(ship, tube)
	assert abs(S.TubeConeDepth(tFrame, at(27, 0)) - 0.9) < 1e-4
	assert abs(S.TubeConeDepth(tFrame, at(0, -30)) - 1.0) < 1e-4
	fCorner = S.TubeConeDepth(tFrame, at(24, 25))
	assert abs(fCorner - 1.09) < 0.01
	assert fCorner * 100.0 > 90.0
	fMild = S.TubeConeDepth(tFrame, at(19.8, 19.8))
	assert abs(fMild - 0.897) < 0.005
	assert fMild * 100.0 <= 90.0


def test_tube_behind_and_error():
	App, S, ship, tube = TT.setup_solution()
	tFrame = S.TubeFrame(ship, tube)
	assert S.TubeConeDepth(tFrame, P(-10.0, 0.0, 0.0)) == 99.0
	assert S.TubeConeDepth(tFrame, P(0.0, 10.0, 0.0)) == 99.0
	assert S.TubeConeDepth(None, at(0, 0)) == None


def test_tube_follows_rotation():
	App, S, ship, tube = TT.setup_solution()
	ship.rot = [[0.0, -1.0, 0.0], [1.0, 0.0, 0.0], [0.0, 0.0, 1.0]]
	tFrame = S.TubeFrame(ship, tube)
	assert abs(S.TubeConeDepth(tFrame, P(0.0, 10.0, 0.0))) < 1e-9
	assert S.TubeConeDepth(tFrame, P(10.0, 0.0, 0.0)) == 99.0


# --- ConeDepth: asymmetric pulse weapon --------------------------------------
def asym():
	App, S, ship, w = TA.setup_solution()
	w.limits = (deg(-15), deg(15), deg(-20), deg(10))
	return App, S, ship, w


def test_pulse_centre_is_zero():
	App, S, ship, w = asym()
	assert abs(S.ArcConeDepth(ship, w, at(0, -5))) < 1e-6


def test_pulse_side_midpoints_are_one():
	App, S, ship, w = asym()
	for tHv in ((15, -5), (-15, -5), (0, 10), (0, -20)):
		fDepth = S.ArcConeDepth(ship, w, at(tHv[0], tHv[1]))
		assert abs(fDepth - 1.0) < 0.01, (tHv, fDepth)


def test_pulse_corner_is_outside():
	App, S, ship, w = asym()
	assert S.ArcConeDepth(ship, w, at(15, 10)) > 1.3
	assert S.ArcConeDepth(ship, w, at(-15, -20)) > 1.3
	assert abs(S.ArcDepth(ship, w, at(15, 10)) - 1.0) < 1e-6	# the box still says edge


def test_pulse_behind_and_errors():
	App, S, ship, w = asym()
	assert S.ArcConeDepth(ship, w, P(-10.0, 0.0, 0.0)) == 99.0
	w.limits = "raise"
	assert S.ArcConeDepth(ship, w, at(0, 0)) == None
	w.limits = (0.1, 0.1, -0.5, 0.5)	# zero width: not computable
	assert S.ArcConeDepth(ship, w, at(0, 0)) == None


# --- ArcScore: torpedo ---------------------------------------------------------
def torp(**kw):
	dCfg = {"TorpedoArcPercentFar": 90, "TorpedoArcPercentNear": 90, "TorpedoArcHysteresis": 0}
	for k in kw:
		dCfg[k] = kw[k]
	return TT.rule3(**dCfg)


def test_config_default_and_read():
	App, AF, core, ship = base.setup()
	assert AF.g_iTorpArcShape == 1 and AF.g_iPulseArcShape == 1
	App, AF, core, ship, target, torps, S = torp(TorpedoArcShape=0, PulseArcShape=0)
	assert AF.g_iTorpArcShape == 0 and AF.g_iPulseArcShape == 0


def test_torpedo_corner_blocked_with_cone():
	App, AF, core, ship, target, torps, S = torp()
	put(target, 24, 25)
	assert TT.best(AF, ship, torps, target) == 0.0
	put(target, 19.8, 19.8)
	assert TT.best(AF, ship, torps, target) > 0.0
	put(target, 27, 0)
	assert TT.best(AF, ship, torps, target) > 0.0


def test_torpedo_corner_allowed_with_box():
	App, AF, core, ship, target, torps, S = torp(TorpedoArcShape=0)
	put(target, 24, 25)
	fScore = TT.best(AF, ship, torps, target)
	assert abs(fScore - 100.0 * (1.0 - 25.0 / 30.0)) < 0.5, fScore


def test_torpedo_hysteresis_on_the_diagonal():
	App, AF, core, ship, target, torps, S = torp(TorpedoArcPercentFar=50, TorpedoArcPercentNear=50, TorpedoArcHysteresis=10)

	def diag(fDepth):
		fT = fDepth * HALF_DEG
		fC = math.cos(deg(fT))
		fS = math.sin(deg(fT)) / math.sqrt(2.0)
		target.pos = P(DIST * fC, DIST * fS, DIST * fS)
	diag(0.45)
	assert TT.best(AF, ship, torps, target) > 0.0
	diag(0.55)
	assert TT.best(AF, ship, torps, target) > 0.0	# held: 50 + 10
	diag(0.65)
	assert TT.best(AF, ship, torps, target) == 0.0	# released
	diag(0.55)
	assert TT.best(AF, ship, torps, target) == 0.0	# starts again only <= 50


HALF_DEG = 30.0


# --- ArcScore: pulse -----------------------------------------------------------
def pulse(**kw):
	dCfg = {"PulseArcPercentFar": 90, "PulseArcPercentNear": 90, "PulseArcHysteresis": 0}
	for k in kw:
		dCfg[k] = kw[k]
	return TA.rule3(**dCfg)


def test_pulse_corner_blocked_with_ellipse():
	# Symmetric +-0.5 rad (28.6 deg) box: a 20/20 corner is 27.4 deg off the centre.
	App, AF, core, ship, target, grp, S = pulse()
	w = grp.lChildren[0]
	put(target, 20, 20)
	assert TA.score(AF, ship, grp, w, target) == 0.0
	AF.ForgetArc()
	put(target, 20, 0)
	assert TA.score(AF, ship, grp, w, target) > 0.0


def test_pulse_corner_allowed_with_box():
	App, AF, core, ship, target, grp, S = pulse(PulseArcShape=0)
	w = grp.lChildren[0]
	put(target, 20, 20)
	fScore = TA.score(AF, ship, grp, w, target)
	assert abs(fScore - 100.0 * (1.0 - deg(20) / 0.5)) < 0.5, fScore


def test_pulse_asymmetric_integration():
	App, AF, core, ship, target, grp, S = pulse()
	w = grp.lChildren[0]
	w.limits = (deg(-15), deg(15), deg(-20), deg(10))
	put(target, 0, -5)
	assert TA.score(AF, ship, grp, w, target) > 95.0
	AF.ForgetArc()
	put(target, 14, 9)	# inside the box, outside the ellipse
	assert TA.score(AF, ship, grp, w, target) == 0.0


def test_pulse_ellipse_failure_falls_back_to_box():
	App, AF, core, ship, target, grp, S = pulse()
	w = grp.lChildren[0]
	w.limits = (0.1, 0.1, -0.5, 0.5)	# the cone is not computable, the box is (depth 99 or 0)
	put(target, 0, 0)
	AF.ArcScore(ship, grp, w, target, None, "pulse", 1)	# must not raise


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
