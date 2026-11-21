"""TorpedoRule / PulseRule 2: the flight-time filter on top of the arc percent
(rule 1 = arc percent only; anything else = rule 2)."""
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
	# Arc percent wide open (100 %) so only the flight time can block; bands
	# 40 km (far) / 20 km (near) for main and secondary alike. Torpedo speed 100.
	dCfg = {"TorpedoRule": 2, "TorpedoArcPercentFar": 100, "TorpedoArcPercentNear": 100,
		"TorpedoArcFarDistance": 40, "TorpedoArcNearDistance": 20,
		"TorpedoArcPercentFarSecondary": 100, "TorpedoArcPercentNearSecondary": 100,
		"TorpedoArcFarDistanceSecondary": 40, "TorpedoArcNearDistanceSecondary": 20,
		"TorpedoArcHysteresis": 0}
	for k in kw:
		dCfg[k] = kw[k]
	return TT.rule3(**dCfg)


def pulse(**kw):
	# Same for pulse weapons (speed 150).
	dCfg = {"PulseRule": 2, "PulseArcPercentFar": 100, "PulseArcPercentNear": 100,
		"PulseArcFarDistance": 40, "PulseArcNearDistance": 20,
		"PulseArcPercentFarSecondary": 100, "PulseArcPercentNearSecondary": 100,
		"PulseArcFarDistanceSecondary": 40, "PulseArcNearDistanceSecondary": 20,
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
	App, AF, core, ship = base.setup(TorpedoFlightTimeFar=2.5, TorpedoFlightTimeNear=1.5, PulseFlightTimeFar=1.25,
		PulseFlightTimeNear=0.5, TorpedoFlightTimeFarSecondary=1.0, TorpedoFlightTimeNearSecondary=0.75,
		PulseFlightTimeFarSecondary=0.5, PulseFlightTimeNearSecondary=0.25)
	assert AF.FlightBand("torpedo") == (2.5, 1.5) and AF.FlightBand("pulse") == (1.25, 0.5)
	assert AF.FlightBand("torpedo", 1) == (1.0, 0.75) and AF.FlightBand("pulse", 1) == (0.5, 0.25)


def test_config_secondary_falls_back_to_primary():
	App, AF, core, ship = base.setup(TorpedoFlightTimeFar=2.5, TorpedoFlightTimeNear=1.5, PulseFlightTimeFar=1.25,
		PulseFlightTimeNear=0.5)
	assert AF.FlightBand("torpedo", 1) == (2.5, 1.5) and AF.FlightBand("pulse", 1) == (1.25, 0.5)


def test_config_missing_means_off():
	App, AF, core, ship = base.setup()
	assert AF.FlightBand("torpedo") == (0.0, 0.0) and AF.FlightLimit("torpedo", 0, 100.0) == 0.0


# --- limit interpolation ---------------------------------------------------------
def test_limit_interpolates_like_the_arc_band():
	App, AF, core, ship, target, torps, S = torp(TorpedoFlightTimeFar=3.0, TorpedoFlightTimeNear=1.0)
	assert AF.FlightLimit("torpedo", 0, 10 * KM) == 1.0	# at or inside the Near distance
	assert AF.FlightLimit("torpedo", 0, 20 * KM) == 1.0
	assert abs(AF.FlightLimit("torpedo", 0, 30 * KM) - 2.0) < 1e-9	# halfway
	assert AF.FlightLimit("torpedo", 0, 40 * KM) == 3.0
	assert AF.FlightLimit("torpedo", 0, 90 * KM) == 3.0	# at or beyond the Far distance


def test_limit_uses_the_distances_of_its_own_band():
	App, AF, core, ship, target, torps, S = torp(TorpedoFlightTimeFar=3.0, TorpedoFlightTimeNear=1.0,
		TorpedoFlightTimeFarSecondary=3.0, TorpedoFlightTimeNearSecondary=1.0,
		TorpedoArcFarDistanceSecondary=100, TorpedoArcNearDistanceSecondary=0)
	assert abs(AF.FlightLimit("torpedo", 0, 30 * KM) - 2.0) < 1e-9
	assert abs(AF.FlightLimit("torpedo", 1, 50 * KM) - 2.0) < 1e-9


def test_limit_zero_in_either_end_is_off():
	for tVals in ((0.0, 0.0), (0.0, 2.0), (2.0, 0.0)):
		App, AF, core, ship, target, torps, S = torp(TorpedoFlightTimeFar=tVals[0], TorpedoFlightTimeNear=tVals[1])
		assert AF.FlightLimit("torpedo", 0, 30 * KM) == 0.0


# --- torpedoes: blocks / passes -----------------------------------------------
def test_torpedo_blocks_over_the_limit_and_passes_under():
	# 20 km = 114.3 units at speed 100 = est 1.14 s.
	App, AF, core, ship, target, torps, S = torp(TorpedoFlightTimeFar=1.0, TorpedoFlightTimeNear=1.0)
	TT.place(target, 0.1, 20.0)
	assert tscore(AF, ship, torps, target) == 0.0
	assert AF.TorpedoTarget(ship, torps, [target], TT.GROUP) == None
	App, AF, core, ship, target, torps, S = torp(TorpedoFlightTimeFar=1.2, TorpedoFlightTimeNear=1.2)
	TT.place(target, 0.1, 20.0)
	assert tscore(AF, ship, torps, target) > 0.0
	assert AF.TorpedoTarget(ship, torps, [target], TT.GROUP) == target


def test_torpedo_blocked_by_interpolated_limit():
	# Far 3.0 s / Near 1.0 s: limit 1.2 s at 22 km (est 1.257 -> blocked), 1.4 s at 24 km (est 1.371 -> passes).
	App, AF, core, ship, target, torps, S = torp(TorpedoFlightTimeFar=3.0, TorpedoFlightTimeNear=1.0)
	TT.place(target, 0.1, 22.0)
	assert tscore(AF, ship, torps, target) == 0.0
	TT.place(target, 0.1, 24.0)
	assert tscore(AF, ship, torps, target) > 0.0


def test_torpedo_filter_off_with_zero():
	App, AF, core, ship, target, torps, S = torp(TorpedoFlightTimeFar=0, TorpedoFlightTimeNear=0)
	TT.place(target, 0.1, 40.0)
	assert tscore(AF, ship, torps, target) > 0.0


def test_torpedo_rule_1_ignores_the_filter():
	App, AF, core, ship, target, torps, S = torp(TorpedoRule=1, TorpedoFlightTimeFar=0.1, TorpedoFlightTimeNear=0.1)
	TT.place(target, 0.1, 20.0)
	assert tscore(AF, ship, torps, target) > 0.0


def test_torpedo_legacy_rule_3_applies_the_filter():
	App, AF, core, ship, target, torps, S = torp(TorpedoRule=3, TorpedoFlightTimeFar=1.0, TorpedoFlightTimeNear=1.0)
	TT.place(target, 0.1, 20.0)
	assert tscore(AF, ship, torps, target) == 0.0


def test_torpedo_default_rule_applies_the_filter():
	# No TorpedoRule in the config at all: rule 2.
	dCfg = {"TapFire": 0, "TorpedoArcPercentFar": 100, "TorpedoArcPercentNear": 100, "TorpedoArcFarDistance": 40,
		"TorpedoArcNearDistance": 20, "TorpedoFlightTimeFar": 1.0, "TorpedoFlightTimeNear": 1.0}
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
	App, AF, core, ship, target, torps, S = torp(TorpedoFlightTimeFar=0.01, TorpedoFlightTimeNear=0.01)
	AF.g_bDebug = 1
	torps.ammo = mock_app.Ammo(0.0)
	TT.place(target, 0.1, 20.0)
	assert tscore(AF, ship, torps, target) > 0.0
	assert tscore(AF, ship, torps, target) > 0.0
	lLog = [l for l in core.logs if l[1].find("speed unknown") >= 0]
	assert len(lLog) == 1


def test_torpedo_secondary_uses_the_secondary_limits():
	# Main limit 2.0 s passes at 20 km (est 1.14), the secondary 1.0 s blocks.
	App, AF, core, ship, target, torps, S = torp(TorpedoFlightTimeFar=2.0, TorpedoFlightTimeNear=2.0,
		TorpedoFlightTimeFarSecondary=1.0, TorpedoFlightTimeNearSecondary=1.0)
	TT.place(target, 0.1, 20.0)
	assert tscore(AF, ship, torps, target, 0) > 0.0
	assert tscore(AF, ship, torps, target, 1) == 0.0
	assert AF.TubeScore(ship, torps, torps.lChildren[0], target, None, None, None, 1) == 0.0
	assert AF.TubeScore(ship, torps, torps.lChildren[0], target, None, None, None, 0) > 0.0
	App, AF, core, ship, target, torps, S = torp(TorpedoFlightTimeFar=1.0, TorpedoFlightTimeNear=1.0,
		TorpedoFlightTimeFarSecondary=2.0, TorpedoFlightTimeNearSecondary=2.0)
	TT.place(target, 0.1, 20.0)
	assert tscore(AF, ship, torps, target, 0) == 0.0
	assert tscore(AF, ship, torps, target, 1) > 0.0


def test_torpedo_blocked_tube_drops_hysteresis_key():
	App, AF, core, ship, target, torps, S = torp(TorpedoFlightTimeFar=1.2, TorpedoFlightTimeNear=1.2,
		TorpedoArcHysteresis=10)
	TT.place(target, 0.1, 20.0)
	assert tscore(AF, ship, torps, target) > 0.0
	assert len(AF.g_dArcReady) == 1
	AF.g_fTorpFtFar = 1.0
	AF.g_fTorpFtNear = 1.0
	assert tscore(AF, ship, torps, target) == 0.0
	assert AF.g_dArcReady == {}


def test_torpedo_secondary_plan_applies_the_filter():
	# The secondary plan (SecondaryTorpedoPlan) scores through TubeScore(.., 1).
	import test_autofire_torp_secondary as TS
	AF, core, ship, main, sec, torps, fake, S = TS.setup3(secx=-20.0)
	AF.g_fTorpFtFarSec = 0.0001
	AF.g_fTorpFtNearSec = 0.0001
	AF.g_iTorpedoRule = 2
	AF.g_bDebug = 0
	lPlan = AF.SecondaryTorpedoPlan(ship, torps, main, 1)
	assert lPlan == []
	AF.g_fTorpFtFarSec = 0.0
	AF.g_fTorpFtNearSec = 0.0
	lPlan = AF.SecondaryTorpedoPlan(ship, torps, main, 1)
	assert [t[1] for t in lPlan] == [8]


# --- pulse ---------------------------------------------------------------------
def test_pulse_blocks_over_the_limit_and_passes_under():
	# 20 km = 114.3 units at speed 150 = est 0.76 s.
	App, AF, core, ship, target, pul, S = pulse(PulseFlightTimeFar=0.5, PulseFlightTimeNear=0.5)
	TP.place(target, 0.1, 20.0)
	assert pscore(AF, ship, pul, target) == 0.0
	assert AF.BestPulseScore(ship, pul, target) == 0.0
	App, AF, core, ship, target, pul, S = pulse(PulseFlightTimeFar=1.0, PulseFlightTimeNear=1.0)
	TP.place(target, 0.1, 20.0)
	assert pscore(AF, ship, pul, target) > 0.0
	assert AF.BestPulseScore(ship, pul, target) > 0.0


def test_pulse_interpolated_limit():
	# Far 2.0 / Near 0.5: at 30 km the limit is 1.25 s (est 1.143 -> passes); at 22 km 0.8 s (est 0.838 -> blocked).
	App, AF, core, ship, target, pul, S = pulse(PulseFlightTimeFar=2.0, PulseFlightTimeNear=0.5)
	assert abs(AF.FlightLimit("pulse", 0, 30 * KM) - 1.25) < 1e-9
	TP.place(target, 0.1, 30.0)
	assert pscore(AF, ship, pul, target) > 0.0
	TP.place(target, 0.1, 22.0)
	assert pscore(AF, ship, pul, target) == 0.0


def test_pulse_filter_off_with_zero_and_rule_1():
	App, AF, core, ship, target, pul, S = pulse(PulseFlightTimeFar=0, PulseFlightTimeNear=0)
	TP.place(target, 0.1, 20.0)
	assert pscore(AF, ship, pul, target) > 0.0
	App, AF, core, ship, target, pul, S = pulse(PulseRule=1, PulseFlightTimeFar=0.1, PulseFlightTimeNear=0.1)
	TP.place(target, 0.1, 20.0)
	assert pscore(AF, ship, pul, target) > 0.0


def test_pulse_secondary_uses_the_secondary_limits():
	App, AF, core, ship, target, pul, S = pulse(PulseFlightTimeFar=1.0, PulseFlightTimeNear=1.0,
		PulseFlightTimeFarSecondary=0.5, PulseFlightTimeNearSecondary=0.5)
	TP.place(target, 0.1, 20.0)
	assert pscore(AF, ship, pul, target, 0) > 0.0
	assert pscore(AF, ship, pul, target, 1) == 0.0


def test_pulse_speed_unknown_does_not_block():
	App, AF, core, ship, target, pul, S = pulse(PulseFlightTimeFar=0.01, PulseFlightTimeNear=0.01)
	pul.lChildren[0].fSpeed = 0.0
	TP.place(target, 0.1, 20.0)
	assert pscore(AF, ship, pul, target) > 0.0


def test_pulse_fire_cycle_holds_fire_when_too_far_in_time():
	App, AF, core, ship, target, pul, S = pulse(PulseFlightTimeFar=0.5, PulseFlightTimeNear=0.5)
	AF.Toggle()
	TP.place(target, 0.1, 20.0)
	AF.FireCycle()
	assert pul.starts() == 0
	AF.g_fFtFar = 1.0
	AF.g_fFtNear = 1.0
	AF.FireCycle()
	assert pul.starts() == 1


# --- debug log ---------------------------------------------------------------------
def test_debug_log_line_and_throttle():
	App, AF, core, ship, target, torps, S = torp(TorpedoFlightTimeFar=1.0, TorpedoFlightTimeNear=1.0)
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
	App, AF, core, ship, target, torps, S = torp(TorpedoFlightTimeFar=1.0, TorpedoFlightTimeNear=1.0)
	App.g_kUtopiaModule.GetGameTime = lambda: 10.0
	TT.place(target, 0.1, 20.0)
	assert tscore(AF, ship, torps, target) == 0.0
	assert [l for l in core.logs if l[1].find("Flight time filter") >= 0] == []


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
