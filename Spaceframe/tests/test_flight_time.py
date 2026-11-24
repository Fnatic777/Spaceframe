"""TorpedoRule / PulseRule 2: the flight-time filter on top of the arc percent
(rule 1 = arc percent only; anything else = rule 2). One flight-time limit per
kind and role; the arc percent itself follows the flight time (ArcFlightTime*)."""
import math
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mock_app
import test_autofire_base as base
import test_torpedo_arc as TT
import test_autofire_arc as TP

KM = 1.0 / 0.175	# game units per km


def torp(**kw):
	# Arc percent wide open (100 %) so only the flight time can block, main and
	# secondary alike. Torpedo speed 100.
	dCfg = {"TorpedoRule": 2, "TorpedoArcPercentFar": 100, "TorpedoArcPercentNear": 100,
		"TorpedoArcPercentFarSecondary": 100, "TorpedoArcPercentNearSecondary": 100,
		"TorpedoArcHysteresis": 0}
	for k in kw:
		dCfg[k] = kw[k]
	return TT.rule3(**dCfg)


def pulse(**kw):
	# Same for pulse weapons (speed 150).
	dCfg = {"PulseRule": 2, "PulseArcPercentFar": 100, "PulseArcPercentNear": 100,
		"PulseArcPercentFarSecondary": 100, "PulseArcPercentNearSecondary": 100,
		"PulseArcHysteresis": 0}
	for k in kw:
		dCfg[k] = kw[k]
	return TP.rule3(**dCfg)


def tscore(AF, ship, torps, target, bSec=0):
	# One tube's score, main (BestTorpedoScore) or secondary (ArcReaches).
	if bSec:
		return AF.ArcReaches(ship, torps, torps.lChildren[0], target, "torpedo", 1)
	return AF.BestTorpedoScore(ship, torps, target)


def pscore(AF, ship, pul, target, bSec=0):
	if bSec:
		return AF.ArcReaches(ship, pul, pul.lChildren[0], target, "pulse", 1)
	return AF.PulseArcScore(ship, pul, pul.lChildren[0], target, None)


# --- rules --------------------------------------------------------------------
def test_rule_default_is_2_and_legacy_3_is_2():
	App, AF, core, ship = base.setup()
	assert AF.g_iTorpedoRule == 2 and AF.g_iPulseRule == 2
	for pValue in (3, 0, 7, 2):
		App, AF, core, ship = base.setup(TorpedoRule=pValue, PulseRule=pValue)
		assert AF.g_iTorpedoRule == 2 and AF.g_iPulseRule == 2
	App, AF, core, ship = base.setup(TorpedoRule=1, PulseRule=1)
	assert AF.g_iTorpedoRule == 1 and AF.g_iPulseRule == 1


def test_config_read():
	App, AF, core, ship = base.setup(TorpedoFlightTimeLimit=2.5, PulseFlightTimeLimit=1.25,
		TorpedoFlightTimeLimitSecondary=1.0, PulseFlightTimeLimitSecondary=0.5)
	assert AF.FlightBand("torpedo") == 2.5 and AF.FlightBand("pulse") == 1.25
	assert AF.FlightBand("torpedo", 1) == 1.0 and AF.FlightBand("pulse", 1) == 0.5


def test_config_secondary_falls_back_to_primary():
	App, AF, core, ship = base.setup(TorpedoFlightTimeLimit=2.5, PulseFlightTimeLimit=1.25)
	assert AF.FlightBand("torpedo", 1) == 2.5 and AF.FlightBand("pulse", 1) == 1.25


def test_config_missing_means_off():
	App, AF, core, ship = base.setup()
	assert AF.FlightBand("torpedo") == 0.0 and AF.FlightLimit("torpedo", 0) == 0.0


def test_limit_is_one_value_per_kind_and_role():
	App, AF, core, ship, target, torps, S = torp(TorpedoFlightTimeLimit=1.5, TorpedoFlightTimeLimitSecondary=0.75,
		PulseFlightTimeLimit=1.25, PulseFlightTimeLimitSecondary=0.25)
	assert AF.FlightLimit("torpedo", 0) == 1.5 and AF.FlightLimit("torpedo", 1) == 0.75
	assert AF.FlightLimit("pulse", 0) == 1.25 and AF.FlightLimit("pulse", 1) == 0.25


# --- arc percent follows the flight time --------------------------------------------
def test_torpedo_arc_percent_at_near_far_and_between_flight_time():
	# Rule 1, percent Far 50 / Near 90, times Near 0.5 s / Far 1.5 s, speed 100:
	# 5 km = 0.29 s (<= near: 90 %), 20 km = 1.14 s (64.3 %), 40 km = 2.29 s (>= far: 50 %).
	dCfg = {"TorpedoRule": 1, "TorpedoArcPercentFar": 50, "TorpedoArcPercentNear": 90,
		"ArcFlightTimeNear": 0.5, "ArcFlightTimeFar": 1.5, "TorpedoArcHysteresis": 0}
	App, AF, core, ship, target, torps, S = TT.rule3(**dCfg)
	TT.place(target, 0.85, 5.0)
	assert tscore(AF, ship, torps, target) > 0.0
	TT.place(target, 0.95, 5.0)
	assert tscore(AF, ship, torps, target) == 0.0
	TT.place(target, 0.6, 20.0)
	assert tscore(AF, ship, torps, target) > 0.0
	TT.place(target, 0.7, 20.0)
	assert tscore(AF, ship, torps, target) == 0.0
	TT.place(target, 0.45, 40.0)
	assert tscore(AF, ship, torps, target) > 0.0
	TT.place(target, 0.55, 40.0)
	assert tscore(AF, ship, torps, target) == 0.0


def test_torpedo_arc_percent_unknown_speed_uses_near():
	dCfg = {"TorpedoRule": 1, "TorpedoArcPercentFar": 50, "TorpedoArcPercentNear": 90,
		"ArcFlightTimeNear": 0.5, "ArcFlightTimeFar": 1.5, "TorpedoArcHysteresis": 0}
	App, AF, core, ship, target, torps, S = TT.rule3(**dCfg)
	torps.ammo = mock_app.Ammo(0.0)
	TT.place(target, 0.85, 40.0)	# far away, but the speed is unknown: the Near 90 % applies
	assert tscore(AF, ship, torps, target) > 0.0


def test_pulse_arc_percent_follows_flight_time():
	# Pulse speed 150: 30 km = 1.14 s; Near 0.5 s / Far 1.5 s, percent 50 / 90 -> 66 %.
	dCfg = {"PulseRule": 1, "PulseArcPercentFar": 50, "PulseArcPercentNear": 90,
		"ArcFlightTimeNear": 0.5, "ArcFlightTimeFar": 1.5, "PulseArcHysteresis": 0}
	App, AF, core, ship, target, pul, S = TP.rule3(**dCfg)
	TP.place(target, 0.6, 30.0)
	assert pscore(AF, ship, pul, target) > 0.0
	TP.place(target, 0.7, 30.0)
	assert pscore(AF, ship, pul, target) == 0.0
	TP.place(target, 0.85, 5.0)	# 0.19 s: Near
	assert pscore(AF, ship, pul, target) > 0.0
	TP.place(target, 0.55, 80.0)	# 3 s: Far 50 %
	assert pscore(AF, ship, pul, target) == 0.0


def test_debug_decision_allowed_percent_comes_from_flight_time():
	dCfg = {"TorpedoRule": 1, "TorpedoArcPercentFar": 50, "TorpedoArcPercentNear": 90,
		"ArcFlightTimeNear": 0.5, "ArcFlightTimeFar": 1.5, "TorpedoArcHysteresis": 0}
	App, AF, core, ship, target, torps, S = TT.rule3(**dCfg)
	AF.g_bDebug = 1
	lSeen = []
	AF.NoteTorpDecision = lambda tFrame, vPoint, iTarget, fDepth, fLimit, bSec: lSeen.append(fLimit)
	TT.place(target, 0.4, 5.0)
	assert tscore(AF, ship, torps, target) > 0.0
	assert len(lSeen) == 1 and abs(lSeen[0] - 90.0) < 1e-6	# allowed percent at 0.29 s


# --- torpedoes: blocks / passes -----------------------------------------------
def test_torpedo_blocks_over_the_limit_and_passes_under():
	# 20 km = 114.3 units at speed 100 = est 1.14 s.
	App, AF, core, ship, target, torps, S = torp(TorpedoFlightTimeLimit=1.0)
	TT.place(target, 0.1, 20.0)
	assert tscore(AF, ship, torps, target) == 0.0
	assert AF.TorpedoTarget(ship, torps, [target], TT.GROUP) == None
	App, AF, core, ship, target, torps, S = torp(TorpedoFlightTimeLimit=1.2)
	TT.place(target, 0.1, 20.0)
	assert tscore(AF, ship, torps, target) > 0.0
	assert AF.TorpedoTarget(ship, torps, [target], TT.GROUP) == target


def test_torpedo_limit_does_not_depend_on_distance():
	# The same limit 1.2 s at 5 km (0.29 s) and 20 km (1.14 s) passes; 30 km (1.71 s) blocks.
	# (Spread window moved far away: it would bypass the limit at 30 km.)
	App, AF, core, ship, target, torps, S = torp(TorpedoFlightTimeLimit=1.2, SpreadFlightTimeMin=50.0, SpreadFlightTimeMax=0)
	TT.place(target, 0.1, 5.0)
	assert tscore(AF, ship, torps, target) > 0.0
	TT.place(target, 0.1, 20.0)
	assert tscore(AF, ship, torps, target) > 0.0
	TT.place(target, 0.1, 30.0)
	assert tscore(AF, ship, torps, target) == 0.0


def test_torpedo_filter_off_with_zero():
	App, AF, core, ship, target, torps, S = torp(TorpedoFlightTimeLimit=0)
	TT.place(target, 0.1, 40.0)
	assert tscore(AF, ship, torps, target) > 0.0


def test_torpedo_rule_1_ignores_the_filter():
	App, AF, core, ship, target, torps, S = torp(TorpedoRule=1, TorpedoFlightTimeLimit=0.1)
	TT.place(target, 0.1, 20.0)
	assert tscore(AF, ship, torps, target) > 0.0


def test_torpedo_legacy_rule_3_applies_the_filter():
	App, AF, core, ship, target, torps, S = torp(TorpedoRule=3, TorpedoFlightTimeLimit=1.0)
	TT.place(target, 0.1, 20.0)
	assert tscore(AF, ship, torps, target) == 0.0


def test_torpedo_default_rule_applies_the_filter():
	# No TorpedoRule in the config at all: rule 2.
	dCfg = {"TapFire": 0, "TorpedoArcPercentFar": 100, "TorpedoArcPercentNear": 100,
		"TorpedoFlightTimeLimit": 1.0}
	App, AF, core, ship = base.setup(**dCfg)
	S = TT.load_solution()
	target = mock_app.Ship("Bug", 7)
	tube = mock_app.Tube()
	torps = mock_app.WeaponGroup([tube])
	torps.torpedo = 1
	ship.groups[TT.GROUP] = torps
	TT.place(target, 0.1, 20.0)
	assert AF.BestTorpedoScore(ship, torps, target) == 0.0


def test_torpedo_speed_unknown_does_not_block_and_logs_once():
	App, AF, core, ship, target, torps, S = torp(TorpedoFlightTimeLimit=0.01)
	AF.g_bDebug = 1
	torps.ammo = mock_app.Ammo(0.0)
	TT.place(target, 0.1, 20.0)
	assert tscore(AF, ship, torps, target) > 0.0
	assert tscore(AF, ship, torps, target) > 0.0
	lLog = [l for l in core.logs if l[1].find("speed unknown") >= 0]
	assert len(lLog) == 1


def test_torpedo_secondary_uses_the_secondary_limit():
	# Main limit 2.0 s passes at 20 km (est 1.14), the secondary 1.0 s blocks.
	App, AF, core, ship, target, torps, S = torp(TorpedoFlightTimeLimit=2.0, TorpedoFlightTimeLimitSecondary=1.0)
	TT.place(target, 0.1, 20.0)
	assert tscore(AF, ship, torps, target, 0) > 0.0
	assert tscore(AF, ship, torps, target, 1) == 0.0
	assert AF.TubeScore(ship, torps, torps.lChildren[0], target, None, None, None, 1) == 0.0
	assert AF.TubeScore(ship, torps, torps.lChildren[0], target, None, None, None, 0) > 0.0
	App, AF, core, ship, target, torps, S = torp(TorpedoFlightTimeLimit=1.0, TorpedoFlightTimeLimitSecondary=2.0)
	TT.place(target, 0.1, 20.0)
	assert tscore(AF, ship, torps, target, 0) == 0.0
	assert tscore(AF, ship, torps, target, 1) > 0.0


def test_torpedo_blocked_tube_drops_hysteresis_key():
	App, AF, core, ship, target, torps, S = torp(TorpedoFlightTimeLimit=1.2, TorpedoArcHysteresis=10)
	TT.place(target, 0.1, 20.0)
	assert tscore(AF, ship, torps, target) > 0.0
	assert len(AF.g_dArcReady) == 1
	AF.g_fTorpFtLimit = 1.0
	assert tscore(AF, ship, torps, target) == 0.0
	assert AF.g_dArcReady == {}


def test_torpedo_secondary_plan_applies_the_filter():
	# The secondary plan (SecondaryTorpedoPlan) scores through TubeScore(.., 1).
	import test_autofire_torp_secondary as TS
	AF, core, ship, main, sec, torps, fake, S = TS.setup3(secx=-20.0)
	AF.g_fTorpFtLimitSec = 0.0001
	AF.g_iTorpedoRule = 2
	AF.g_bDebug = 0
	lPlan = AF.SecondaryTorpedoPlan(ship, torps, main, 1)
	assert lPlan == []
	AF.g_fTorpFtLimitSec = 0.0
	lPlan = AF.SecondaryTorpedoPlan(ship, torps, main, 1)
	assert [t[1] for t in lPlan] == [8]


# --- pulse ---------------------------------------------------------------------
def test_pulse_blocks_over_the_limit_and_passes_under():
	# 20 km = 114.3 units at speed 150 = est 0.76 s.
	App, AF, core, ship, target, pul, S = pulse(PulseFlightTimeLimit=0.5)
	TP.place(target, 0.1, 20.0)
	assert pscore(AF, ship, pul, target) == 0.0
	assert AF.BestPulseScore(ship, pul, target) == 0.0
	App, AF, core, ship, target, pul, S = pulse(PulseFlightTimeLimit=1.0)
	TP.place(target, 0.1, 20.0)
	assert pscore(AF, ship, pul, target) > 0.0
	assert AF.BestPulseScore(ship, pul, target) > 0.0


def test_pulse_limit_is_the_same_at_any_distance():
	# Limit 1.0 s at speed 150: 22 km = 0.84 s passes, 30 km = 1.14 s blocks.
	App, AF, core, ship, target, pul, S = pulse(PulseFlightTimeLimit=1.0)
	TP.place(target, 0.1, 22.0)
	assert pscore(AF, ship, pul, target) > 0.0
	TP.place(target, 0.1, 30.0)
	assert pscore(AF, ship, pul, target) == 0.0


def test_pulse_filter_off_with_zero_and_rule_1():
	App, AF, core, ship, target, pul, S = pulse(PulseFlightTimeLimit=0)
	TP.place(target, 0.1, 20.0)
	assert pscore(AF, ship, pul, target) > 0.0
	App, AF, core, ship, target, pul, S = pulse(PulseRule=1, PulseFlightTimeLimit=0.1)
	TP.place(target, 0.1, 20.0)
	assert pscore(AF, ship, pul, target) > 0.0


def test_pulse_secondary_uses_the_secondary_limit():
	App, AF, core, ship, target, pul, S = pulse(PulseFlightTimeLimit=1.0, PulseFlightTimeLimitSecondary=0.5)
	TP.place(target, 0.1, 20.0)
	assert pscore(AF, ship, pul, target, 0) > 0.0
	assert pscore(AF, ship, pul, target, 1) == 0.0


def test_pulse_speed_unknown_does_not_block():
	App, AF, core, ship, target, pul, S = pulse(PulseFlightTimeLimit=0.01)
	pul.lChildren[0].fSpeed = 0.0
	TP.place(target, 0.1, 20.0)
	assert pscore(AF, ship, pul, target) > 0.0


def test_pulse_fire_cycle_holds_fire_when_too_far_in_time():
	App, AF, core, ship, target, pul, S = pulse(PulseFlightTimeLimit=0.5)
	AF.Toggle()
	TP.place(target, 0.1, 20.0)
	AF.FireCycle()
	assert pul.starts() == 0
	AF.g_fFtLimit = 1.0
	AF.FireCycle()
	assert pul.starts() == 1


# --- debug log ---------------------------------------------------------------------
def test_debug_log_line_and_throttle():
	App, AF, core, ship, target, torps, S = torp(TorpedoFlightTimeLimit=1.0)
	AF.g_bDebug = 1
	fNow = [10.0]
	App.g_kUtopiaModule.GetGameTime = lambda: fNow[0]
	TT.place(target, 0.1, 20.0)
	tscore(AF, ship, torps, target)
	tscore(AF, ship, torps, target)
	lLog = [l[1] for l in core.logs if l[1].find("Flight time filter") >= 0]
	assert len(lLog) == 1
	assert lLog[0] == "Flight time filter: torpedo main est 1.1 s > limit 1.0 s at 20 km", lLog[0]
	fNow[0] = 11.0
	tscore(AF, ship, torps, target)
	assert len([l for l in core.logs if l[1].find("Flight time filter") >= 0]) == 1
	fNow[0] = 12.5
	tscore(AF, ship, torps, target)
	assert len([l for l in core.logs if l[1].find("Flight time filter") >= 0]) == 2
	tscore(AF, ship, torps, target, 1)	# secondary: its own line
	assert [l[1] for l in core.logs if l[1].find("torpedo sec") >= 0] != []


def test_debug_off_no_log():
	App, AF, core, ship, target, torps, S = torp(TorpedoFlightTimeLimit=1.0)
	App.g_kUtopiaModule.GetGameTime = lambda: 10.0
	TT.place(target, 0.1, 20.0)
	assert tscore(AF, ship, torps, target) == 0.0
	assert [l for l in core.logs if l[1].find("Flight time filter") >= 0] == []


# --- guidance time and lifetime ------------------------------------------------
def test_guidance_extends_the_limit():
	# Limit 1.0 s; 20 km at speed 100 = est 1.143 s. Guidance 0.1 s: still blocked;
	# guidance 0.2 s: limit 1.2 s, passes. Guidance 0 / unknown: as before.
	App, AF, core, ship, target, torps, S = torp(TorpedoFlightTimeLimit=1.0)
	fDist = 20 * KM
	assert AF.FlightBlocked("torpedo", 0, fDist, 100.0, 1) == 1
	assert AF.FlightBlocked("torpedo", 0, fDist, 100.0, 1, 0.0, 0.0) == 1
	assert AF.FlightBlocked("torpedo", 0, fDist, 100.0, 1, 0.1, 0.0) == 1
	assert AF.FlightBlocked("torpedo", 0, fDist, 100.0, 1, 0.2, 0.0) == 0


def test_guidance_does_not_turn_the_filter_on():
	App, AF, core, ship, target, torps, S = torp(TorpedoFlightTimeLimit=0)
	assert AF.FlightBlocked("torpedo", 0, 90 * KM, 100.0, 1, 5.0, 0.0) == 0


def test_lifetime_caps_the_limit():
	# Limit 1.5 s + guidance 1.0 s = 2.5 s, but the projectile lives 1.2 s: the
	# estimate 1.43 s (25 km) is over the cap; 1.14 s (20 km) is under it.
	App, AF, core, ship, target, torps, S = torp(TorpedoFlightTimeLimit=1.5)
	assert AF.FlightBlocked("torpedo", 0, 25 * KM, 100.0, 1, 1.0, 0.0) == 0
	assert AF.FlightBlocked("torpedo", 0, 25 * KM, 100.0, 1, 1.0, 1.2) == 1
	assert AF.FlightBlocked("torpedo", 0, 20 * KM, 100.0, 1, 1.0, 1.2) == 0


def test_guidance_secondary_and_pulse():
	App, AF, core, ship, target, torps, S = torp(TorpedoFlightTimeLimitSecondary=1.0)
	assert AF.FlightBlocked("torpedo", 1, 20 * KM, 100.0, 1, 0.1, 0.0) == 1
	assert AF.FlightBlocked("torpedo", 1, 20 * KM, 100.0, 1, 0.2, 0.0) == 0


def test_shot_tuple_carries_the_guidance():
	App, AF, core, ship, target, torps, S = torp(TorpedoFlightTimeLimit=1.0)
	TT.place(target, 0.1, 20.0)
	tShot = AF.TorpedoShot(ship, torps, target, None)
	assert len(tShot) == 4 and tShot[3] >= 0.0


def test_guided_pulse_projectile_is_not_held_at_range():
	# Orion's Missile (pulse-class weapon): speed 4.4 km/s, guidance and lifetime 30 s.
	# At 25 km the estimate is 5.7 s: held with no guidance (limit 1.5 s), free with it.
	App, AF, core, ship, target, torps, S = pulse(PulseFlightTimeLimit=1.5)
	fSpeed = 25.0
	assert AF.FlightBlocked("pulse", 0, 25 * KM, fSpeed, 1, 0.0, 30.0) == 1
	assert AF.FlightBlocked("pulse", 0, 25 * KM, fSpeed, 1, 30.0, 30.0) == 0
	assert AF.FlightBlocked("pulse", 0, 100 * KM, fSpeed, 1, 30.0, 30.0) == 0	# 22.9 s, under the 30 s cap
	assert AF.FlightBlocked("pulse", 0, 150 * KM, fSpeed, 1, 30.0, 30.0) == 1	# 34.3 s, over the 30 s lifetime


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
