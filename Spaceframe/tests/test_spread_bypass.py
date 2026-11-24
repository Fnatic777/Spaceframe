"""Torpedo spread is independent of the flight-time limit: inside the spread
window (SpreadFlightTimeMin..Max) the limit
does not hold the tube and the shot goes out as spread."""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mock_app
import test_autofire_base as base
import test_torpedo_arc as TT
import test_autofire_arc as TP
import test_flight_time as FT


def torp(**kw):
	# Limit 1.0 s (secondary 0.5 s), spread window 1.5-2.5 s; speed 100.
	dCfg = {"TorpedoFlightTimeLimit": 1.0, "TorpedoFlightTimeLimitSecondary": 0.5,
		"SpreadFlightTimeMin": 1.5, "SpreadFlightTimeMax": 2.5}
	for k in kw:
		dCfg[k] = kw[k]
	App, AF, core, ship, target, torps, S = FT.torp(**dCfg)
	torps.chains = 3
	torps.chain = 0
	return App, AF, core, ship, target, torps, S


def test_bypass_inside_window():
	# 30 km = 1.71 s: over the 1.0 s limit but inside the window.
	App, AF, core, ship, target, torps, S = torp()
	TT.place(target, 0.1, 30.0)
	assert FT.tscore(AF, ship, torps, target) > 0.0
	assert AF.TorpedoTarget(ship, torps, [target], TT.GROUP) == target
	assert torps.chain == 2	# the same decision reached ApplySpread: spread


def test_bypass_secondary_uses_the_same_window():
	App, AF, core, ship, target, torps, S = torp()
	TT.place(target, 0.1, 30.0)
	assert AF.TubeScore(ship, torps, torps.lChildren[0], target, None, None, None, 1) > 0.0


def test_manual_fire_filter_never_bypasses():
	# ArcReaches (manual fire) keeps the limit and records no spread verdict.
	App, AF, core, ship, target, torps, S = torp()
	TT.place(target, 0.1, 30.0)
	assert FT.tscore(AF, ship, torps, target, 1) == 0.0
	assert AF.g_dSpreadOK == {}


def test_no_bypass_without_spread_chain():
	App, AF, core, ship, target, torps, S = torp()
	torps.chains = 1
	TT.place(target, 0.1, 30.0)
	assert FT.tscore(AF, ship, torps, target) == 0.0


def test_no_bypass_below_min():
	# 20 km = 1.14 s < 1.5 s: the limit 1.0 s holds, as before.
	App, AF, core, ship, target, torps, S = torp()
	TT.place(target, 0.1, 20.0)
	assert FT.tscore(AF, ship, torps, target) == 0.0
	assert FT.tscore(AF, ship, torps, target, 1) == 0.0


def test_no_bypass_above_max():
	# 60 km = 3.43 s > 2.5 s.
	App, AF, core, ship, target, torps, S = torp()
	TT.place(target, 0.1, 60.0)
	assert FT.tscore(AF, ship, torps, target) == 0.0


def test_max_zero_bypasses_any_time_from_min():
	App, AF, core, ship, target, torps, S = torp(SpreadFlightTimeMax=0)
	TT.place(target, 0.1, 60.0)
	assert FT.tscore(AF, ship, torps, target) > 0.0
	TT.place(target, 0.1, 20.0)	# still below Min
	assert FT.tscore(AF, ship, torps, target) == 0.0


def test_no_bypass_unknown_speed():
	# Unknown speed: the filter does not block anyway and spread is not allowed.
	App, AF, core, ship, target, torps, S = torp()
	torps.ammo = mock_app.Ammo(0.0)
	TT.place(target, 0.1, 30.0)
	assert FT.tscore(AF, ship, torps, target) > 0.0
	assert AF.TorpedoTarget(ship, torps, [target], TT.GROUP) == target
	assert torps.chain == 0


def test_arc_percent_still_applies_to_spread():
	App, AF, core, ship, target, torps, S = torp(TorpedoArcPercentFar=50, TorpedoArcPercentNear=50)
	TT.place(target, 0.7, 30.0)
	assert FT.tscore(AF, ship, torps, target) == 0.0


def test_single_shot_outside_window_not_spread():
	# 5 km: inside the limit, fires, but below the window: Single.
	App, AF, core, ship, target, torps, S = torp()
	TT.place(target, 0.1, 5.0)
	assert AF.TorpedoTarget(ship, torps, [target], TT.GROUP) == target
	assert torps.chain == 0


def test_filter_flightblocked_flag_only_for_torpedo_rule_2():
	App, AF, core, ship, target, torps, S = torp()
	fDist = 30 * FT.KM
	assert AF.FlightBlocked("torpedo", 0, fDist, 100.0, 1) == 1
	assert AF.FlightBlocked("torpedo", 0, fDist, 100.0, 1, 0.0, 0.0, 1) == 0


def test_debug_log_line_for_the_bypass_is_rate_limited():
	App, AF, core, ship, target, torps, S = torp()
	AF.g_bDebug = 1
	fNow = [10.0]
	App.g_kUtopiaModule.GetGameTime = lambda: fNow[0]
	TT.place(target, 0.1, 30.0)
	FT.tscore(AF, ship, torps, target)
	FT.tscore(AF, ship, torps, target)
	lLog = [l[1] for l in core.logs if l[1].find("passed as spread") >= 0]
	assert len(lLog) == 1, lLog
	fNow[0] = 12.5
	FT.tscore(AF, ship, torps, target)
	assert len([l for l in core.logs if l[1].find("passed as spread") >= 0]) == 2


def test_spread_arc_config_default_and_custom():
	App, AF, core, ship, target, torps, S = torp()
	assert AF.g_fSpreadArcPercent == 35.0
	App, AF, core, ship, target, torps, S = torp(SpreadArcPercent=60)
	assert AF.g_fSpreadArcPercent == 60.0
	import importlib
	sPath = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts", "Custom",
		"Spaceframe", "Modules", "AutoFire", "Config.py")
	assert open(sPath).read().find("SpreadArcPercent = 10") >= 0


def test_spread_shot_depth_boundary():
	App, AF, core, ship, target, torps, S = torp()
	fDist = 30 * FT.KM
	assert AF.SpreadShot(torps, fDist, 100.0, 0.35) == 1	# exactly 35: still spread
	assert AF.SpreadShot(torps, fDist, 100.0, 0.36) == 0
	assert AF.SpreadShot(torps, fDist, 100.0, 0.0) == 1
	assert AF.SpreadShot(torps, 5 * FT.KM, 100.0, 0.1) == 0	# outside window
	torps.chains = 1
	assert AF.SpreadShot(torps, fDist, 100.0, 0.1) == 0	# no chain


def test_depth_over_spread_arc_is_single_and_filtered():
	# Depth 50 in the window, allowed 90: not spread, so the limit (1.0 s) blocks it.
	App, AF, core, ship, target, torps, S = torp(TorpedoArcPercentFar=90, TorpedoArcPercentNear=90)
	TT.place(target, 0.5, 30.0)
	assert FT.tscore(AF, ship, torps, target) == 0.0
	# Same depth, limit large enough: fires, as Single.
	App, AF, core, ship, target, torps, S = torp(TorpedoArcPercentFar=90, TorpedoArcPercentNear=90,
		TorpedoFlightTimeLimit=2.0)
	TT.place(target, 0.5, 30.0)
	assert AF.TorpedoTarget(ship, torps, [target], TT.GROUP) == target
	assert torps.chain == 0


def test_depth_under_spread_arc_spreads_main_and_secondary():
	App, AF, core, ship, target, torps, S = torp(TorpedoArcPercentFar=90, TorpedoArcPercentNear=90,
		TorpedoArcPercentFarSecondary=90, TorpedoArcPercentNearSecondary=90)
	TT.place(target, 0.3, 30.0)
	assert AF.TorpedoTarget(ship, torps, [target], TT.GROUP) == target
	assert torps.chain == 2
	assert AF.TubeScore(ship, torps, torps.lChildren[0], target, None, None, None, 1) > 0.0
	TT.place(target, 0.5, 30.0)
	assert AF.TubeScore(ship, torps, torps.lChildren[0], target, None, None, None, 1) == 0.0


def test_custom_spread_arc_widens_spread():
	App, AF, core, ship, target, torps, S = torp(TorpedoArcPercentFar=90, TorpedoArcPercentNear=90,
		SpreadArcPercent=60)
	TT.place(target, 0.5, 30.0)
	assert FT.tscore(AF, ship, torps, target) > 0.0


def test_pulse_unchanged():
	# Pulse weapons ignore the spread window: 20 km at speed 150 = 0.76 s over a 0.5 s limit.
	App, AF, core, ship, target, pul, S = FT.pulse(PulseFlightTimeLimit=0.5,
		SpreadFlightTimeMin=0.1, SpreadFlightTimeMax=0)
	TP.place(target, 0.1, 20.0)
	assert FT.pscore(AF, ship, pul, target) == 0.0


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
