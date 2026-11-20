"""PulseRule 3 (arc percent): Solution.ArcDepth and the ready/hysteresis rule."""
import math
import os
import sys
import types
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mock_app
import test_autofire_base as base

FAR_KM = 30.0
NEAR_KM = 5.0


def P(x, y, z):
	return mock_app.Point(x, y, z)


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
	return App, S, ship, mock_app.Pulse()


def at(fWidth, fHeight, fDist=10.0):
	# A point at the given width/height angles (radians) from the weapon at the origin.
	return P(fDist, fDist * math.tan(fWidth), fDist * math.tan(fHeight))


# --- ArcDepth ---------------------------------------------------------------
def test_depth_centre_is_zero():
	App, S, ship, w = setup_solution()
	assert abs(S.ArcDepth(ship, w, P(10.0, 0.0, 0.0))) < 1e-9


def test_depth_edge_is_one_and_outside_more():
	App, S, ship, w = setup_solution()
	assert abs(S.ArcDepth(ship, w, at(0.5, 0.0)) - 1.0) < 1e-6
	assert abs(S.ArcDepth(ship, w, at(0.0, -0.5)) - 1.0) < 1e-6
	assert abs(S.ArcDepth(ship, w, at(0.6, 0.0)) - 1.2) < 1e-6
	assert abs(S.ArcDepth(ship, w, at(0.1, 0.4)) - 0.8) < 1e-6	# the deeper axis counts


def test_depth_behind_is_99():
	App, S, ship, w = setup_solution()
	assert S.ArcDepth(ship, w, P(-10.0, 0.0, 0.0)) == 99.0
	assert S.ArcDepth(ship, w, P(0.0, 10.0, 0.0)) == 99.0	# dot with forward == 0


def test_depth_asymmetric_limits():
	App, S, ship, w = setup_solution()
	w.limits = (0.0, 1.0, -0.2, 0.2)
	assert abs(S.ArcDepth(ship, w, at(0.5, 0.0))) < 1e-6
	assert abs(S.ArcDepth(ship, w, at(0.0, 0.0)) - 1.0) < 1e-6
	assert abs(S.ArcDepth(ship, w, at(-0.1, 0.0)) - 1.2) < 1e-6
	assert abs(S.ArcDepth(ship, w, at(1.0, 0.0)) - 1.0) < 1e-6


def test_depth_unavailable_is_none():
	App, S, ship, w = setup_solution()
	w.limits = "raise"
	assert S.ArcDepth(ship, w, P(10.0, 0.0, 0.0)) == None
	w.limits = (-0.5, 0.5, -0.5, 0.5)
	w.axes = "raise"
	assert S.ArcDepth(ship, w, P(10.0, 0.0, 0.0)) == None


def test_depth_ship_rotation():
	# The ship turned 90 degrees about z: the weapon's forward is world +y.
	App, S, ship, w = setup_solution()
	ship.rot = [[0.0, -1.0, 0.0], [1.0, 0.0, 0.0], [0.0, 0.0, 1.0]]
	assert abs(S.ArcDepth(ship, w, P(0.0, 10.0, 0.0))) < 1e-9
	assert S.ArcDepth(ship, w, P(10.0, 0.0, 0.0)) == 99.0


def test_weapon_position_candidates():
	# A: the weapon's own world location; B: ship location + rotated local position.
	App, S, ship, w = setup_solution()
	ship.pos = P(100.0, 0.0, 0.0)
	w.pPos = P(0.0, 0.0, 0.0)
	vPoint = P(110.0, 10.0, 0.0)
	assert S.ArcDepth(ship, w, vPoint, "A") < 1.0
	assert S.ArcDepth(ship, w, vPoint, "B") > 1.0
	S.WEAPON_POSITION = "B"
	assert S.ArcDepth(ship, w, vPoint) > 1.0


def test_lead_point_leads_moving_target():
	App, S, ship, w = setup_solution()
	target = mock_app.Ship("Bug", 7)
	target.pos = P(100.0, 0.0, 0.0)
	target.vel = P(0.0, 15.0, 0.0)
	v = S.LeadPoint(target, None, P(0.0, 0.0, 0.0), 150.0)
	assert v.y > 5.0 and abs(v.x - 100.0) < 1e-6
	v0 = S.LeadPoint(target, None, P(0.0, 0.0, 0.0), 0.0)
	assert v0.y == 0.0


# --- PulseRule 3 ------------------------------------------------------------
def rule3(**kw):
	dCfg = {"PulseRule": 3, "TapFire": 0, "PulseArcPercentFar": 50, "PulseArcPercentNear": 90,
		"PulseArcFarDistance": FAR_KM, "PulseArcNearDistance": NEAR_KM, "PulseArcHysteresis": 10}
	for k in kw:
		dCfg[k] = kw[k]
	App, AF, core, ship = base.setup(**dCfg)
	S = load_solution()
	target = mock_app.Ship("Bug", 7)
	core.g_pMission = mock_app.Mission([target])
	ship.target = target
	pulse = mock_app.WeaponGroup([mock_app.Pulse(5.0, 2.0, 1)])
	pulse.pulse = 1
	ship.groups[App.ShipClass.WG_TERTIARY] = pulse
	return App, AF, core, ship, target, pulse, S


def place(target, fDepth, fKm, fHalf=0.5):
	# Target at fKm kilometres, at fDepth of a +-fHalf rad arc (width axis).
	fDist = fKm / 0.175
	fAngle = fDepth * fHalf
	target.pos = P(fDist * math.cos(fAngle), fDist * math.sin(fAngle), 0.0)


def score(AF, ship, pulse, w, target):
	return AF.PulseArcScore(ship, pulse, w, target, None)


def test_config_read():
	App, AF, core, ship, target, pulse, S = rule3(PulseArcPercentFar=40, PulseArcPercentNear=80,
		PulseArcFarDistance=20, PulseArcNearDistance=2, PulseArcHysteresis=5)
	assert AF.g_iPulseRule == 3 and AF.g_fArcFar == 40.0 and AF.g_fArcNear == 80.0 and AF.g_fArcHysteresis == 5.0
	assert abs(AF.g_fArcFarDistance - 20 / 0.175) < 1e-6 and abs(AF.g_fArcNearDistance - 2 / 0.175) < 1e-6


def test_config_defaults():
	App, AF, core, ship = base.setup()
	assert AF.g_fArcFar == 50.0 and AF.g_fArcNear == 90.0 and AF.g_fArcHysteresis == 10.0
	assert abs(AF.g_fArcFarDistance - 30 / 0.175) < 1e-6 and abs(AF.g_fArcNearDistance - 5 / 0.175) < 1e-6


def test_allowed_far_near_middle():
	App, AF, core, ship, target, pulse, S = rule3()
	assert AF.ArcAllowed(100 / 0.175) == 50.0	# beyond far
	assert AF.ArcAllowed(FAR_KM / 0.175) == 50.0
	assert AF.ArcAllowed(NEAR_KM / 0.175) == 90.0
	assert AF.ArcAllowed(1 / 0.175) == 90.0	# closer than near
	assert abs(AF.ArcAllowed(17.5 / 0.175) - 70.0) < 1e-6


def test_ready_far():
	App, AF, core, ship, target, pulse, S = rule3()
	w = pulse.lChildren[0]
	place(target, 0.45, 40.0)
	assert score(AF, ship, pulse, w, target) > 0.0
	AF.ForgetArc()
	place(target, 0.55, 40.0)
	assert score(AF, ship, pulse, w, target) == 0.0


def test_ready_near():
	App, AF, core, ship, target, pulse, S = rule3()
	w = pulse.lChildren[0]
	place(target, 0.85, 3.0)
	assert score(AF, ship, pulse, w, target) > 0.0
	AF.ForgetArc()
	place(target, 0.95, 3.0)
	assert score(AF, ship, pulse, w, target) == 0.0


def test_ready_middle():
	App, AF, core, ship, target, pulse, S = rule3()
	w = pulse.lChildren[0]
	place(target, 0.65, 17.5)
	assert score(AF, ship, pulse, w, target) > 0.0
	AF.ForgetArc()
	place(target, 0.75, 17.5)
	assert score(AF, ship, pulse, w, target) == 0.0


def test_hysteresis_holds_then_releases():
	App, AF, core, ship, target, pulse, S = rule3()
	w = pulse.lChildren[0]
	place(target, 0.45, 40.0)
	assert score(AF, ship, pulse, w, target) > 0.0
	place(target, 0.55, 40.0)
	assert score(AF, ship, pulse, w, target) > 0.0	# held: limit 50 + 10
	place(target, 0.65, 40.0)
	assert score(AF, ship, pulse, w, target) == 0.0	# released
	place(target, 0.55, 40.0)
	assert score(AF, ship, pulse, w, target) == 0.0	# needs <= 50 to start again
	place(target, 0.45, 40.0)
	assert score(AF, ship, pulse, w, target) > 0.0


def test_hysteresis_zero_is_off():
	for iHys in (0, -5):
		App, AF, core, ship, target, pulse, S = rule3(PulseArcHysteresis=iHys)
		w = pulse.lChildren[0]
		place(target, 0.45, 40.0)
		assert score(AF, ship, pulse, w, target) > 0.0
		assert AF.g_dArcReady == {}
		place(target, 0.51, 40.0)	# 1 point past the allowed 50
		assert score(AF, ship, pulse, w, target) == 0.0
		assert AF.g_dArcReady == {}
	App, AF, core, ship, target, pulse, S = rule3(PulseArcHysteresis=10)
	w = pulse.lChildren[0]
	place(target, 0.45, 40.0)
	assert score(AF, ship, pulse, w, target) > 0.0
	place(target, 0.51, 40.0)
	assert score(AF, ship, pulse, w, target) > 0.0	# held with 10
	assert len(AF.g_dArcReady) == 1


def test_hysteresis_never_beyond_the_arc():
	App, AF, core, ship, target, pulse, S = rule3(PulseArcPercentNear=95, PulseArcPercentFar=95, PulseArcHysteresis=20)
	w = pulse.lChildren[0]
	place(target, 0.9, 40.0)
	assert score(AF, ship, pulse, w, target) > 0.0
	place(target, 1.05, 40.0)
	assert score(AF, ship, pulse, w, target) == 0.0	# outside the arc, hysteresis or not


def test_hysteresis_is_per_weapon():
	App, AF, core, ship, target, pulse, S = rule3()
	w1 = pulse.lChildren[0]
	w2 = mock_app.Pulse(5.0, 2.0, 1)
	w2.limits = (-1.0, 1.0, -1.0, 1.0)
	w3 = mock_app.Pulse(5.0, 2.0, 1)
	pulse.lChildren.append(w2)
	pulse.lChildren.append(w3)
	place(target, 0.45, 40.0)	# 0.225 rad: w1 depth 0.45, w2 0.225
	assert score(AF, ship, pulse, w1, target) > 0.0 and score(AF, ship, pulse, w2, target) > 0.0
	place(target, 0.55, 40.0)	# w1 depth 0.55 (held), w2 0.275
	assert score(AF, ship, pulse, w1, target) > 0.0
	assert score(AF, ship, pulse, w3, target) == 0.0	# w3 never was ready: no hold
	assert len(AF.g_dArcReady) == 2


def test_hysteresis_cleared_on_target_change():
	App, AF, core, ship, target, pulse, S = rule3()
	other = mock_app.Ship("Bug", 8)
	place(target, 0.45, 40.0)
	assert AF.PulseTarget(ship, pulse, [target], App.ShipClass.WG_TERTIARY) == target
	place(other, 0.55, 40.0)
	assert AF.PulseTarget(ship, pulse, [other], App.ShipClass.WG_TERTIARY) == None
	assert AF.g_dArcReady == {}
	place(target, 0.55, 40.0)
	assert AF.PulseTarget(ship, pulse, [target], App.ShipClass.WG_TERTIARY) == None


def two_targets_in_band(bChooseFirst):
	# The weapon is ready for A (held at 0.55 of the arc, limit 50 + 10); B is
	# scored too, in either order, and the group chooses A.
	App, AF, core, ship, target, pulse, S = rule3()
	w = pulse.lChildren[0]
	other = mock_app.Ship("Bug", 8)
	place(target, 0.45, 40.0)
	assert score(AF, ship, pulse, w, target) > 0.0	# ready for A
	place(target, 0.55, 40.0)	# inside A's stay-ready band
	place(other, 0.30, 40.0)	# B: becomes ready too
	if bChooseFirst:
		assert score(AF, ship, pulse, w, target) > 0.0
		assert score(AF, ship, pulse, w, other) > 0.0
	else:
		assert score(AF, ship, pulse, w, other) > 0.0
		assert score(AF, ship, pulse, w, target) > 0.0
	AF.ArcSettle(pulse, target.GetObjID())
	assert score(AF, ship, pulse, w, target) > 0.0	# hysteresis kept for A
	assert len(AF.g_dArcReady) == 1


def test_hysteresis_kept_when_other_target_scored_after():
	two_targets_in_band(1)


def test_hysteresis_kept_when_other_target_scored_before():
	two_targets_in_band(0)


def test_hysteresis_cleared_on_toggle_off():
	App, AF, core, ship, target, pulse, S = rule3()
	AF.Toggle()
	place(target, 0.45, 40.0)
	score(AF, ship, pulse, pulse.lChildren[0], target)
	assert len(AF.g_dArcReady) == 1
	AF.Toggle()
	assert AF.g_dArcReady == {}


def test_uncharged_is_not_ready_and_forgets():
	App, AF, core, ship, target, pulse, S = rule3()
	w = pulse.lChildren[0]
	place(target, 0.45, 40.0)
	assert score(AF, ship, pulse, w, target) > 0.0
	w.fCharge = 1.0
	assert score(AF, ship, pulse, w, target) == 0.0
	assert AF.g_dArcReady == {}


def test_score_orders_by_depth():
	App, AF, core, ship, target, pulse, S = rule3()
	w = pulse.lChildren[0]
	place(target, 0.1, 3.0)
	fDeep = score(AF, ship, pulse, w, target)
	AF.ForgetArc()
	place(target, 0.8, 3.0)
	fEdge = score(AF, ship, pulse, w, target)
	assert fDeep > fEdge >= 1.0
	assert AF.BestPulseScore(ship, pulse, target) >= 1.0


def test_lead_point_is_used():
	# The target moves sideways: its lead point is further off the centre than
	# where it is now.
	App, AF, core, ship, target, pulse, S = rule3()
	w = pulse.lChildren[0]
	target.pos = P(100.0, 0.0, 0.0)
	target.vel = P(0.0, 60.0, 0.0)
	fLead = score(AF, ship, pulse, w, target)
	AF.ForgetArc()
	target.vel = P(0.0, 0.0, 0.0)
	fStill = score(AF, ship, pulse, w, target)
	assert fStill > fLead


def test_fallback_to_is_in_arc():
	App, AF, core, ship, target, pulse, S = rule3()
	w = pulse.lChildren[0]
	w.limits = "raise"
	place(target, 0.1, 10.0)
	w.iArc = 1
	assert score(AF, ship, pulse, w, target) == 1.0
	w.iArc = 0
	assert score(AF, ship, pulse, w, target) == 0.0
	w.iArc = "raise"
	assert score(AF, ship, pulse, w, target) == 1.0	# nothing to check: ready


def test_fire_cycle_fires_inside_stops_outside():
	App, AF, core, ship, target, pulse, S = rule3()
	AF.Toggle()
	place(target, 0.45, 40.0)
	AF.FireCycle()
	assert pulse.starts() == 1
	place(target, 0.65, 40.0)
	AF.FireCycle()
	assert pulse.calls[-1] == ("stop",)


def test_rules_1_and_2_do_not_use_the_arc_state():
	for iRule in (1, 2):
		App, AF, core, ship, target, pulse, S = rule3(PulseRule=iRule)
		target.pos = P(10.0, 0.0, 0.0)
		AF.BestPulseScore(ship, pulse, target)
		assert AF.g_dArcReady == {}


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
