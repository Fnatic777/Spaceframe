"""The torpedo spread window only picks the firing mode: the flight-time limit
(configured, or stretched for the target's size) decides whether a tube may
fire at all, so spread happens only inside both."""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mock_app
import test_autofire_base as base
import test_torpedo_arc as TT
import test_autofire_arc as TP
import test_flight_time as FT
import test_target_size as TS


def torp(**kw):
	# Limit 1.0 s (secondary 0.5 s), spread window 1.5-2.5 s; speed 100, 3 chains.
	dCfg = {"TorpedoFlightTimeLimit": 1.0, "TorpedoFlightTimeLimitSecondary": 0.5,
		"SpreadFlightTimeMin": 1.5, "SpreadFlightTimeMax": 2.5}
	for k in kw:
		dCfg[k] = kw[k]
	App, AF, core, ship, target, torps, S = FT.torp(**dCfg)
	torps.chains = 3
	torps.chain = 0
	return App, AF, core, ship, target, torps, S


def test_window_does_not_pass_the_limit():
	# 30 km = 1.71 s: inside the window but over the 1.0 s limit (secondary 0.5 s).
	App, AF, core, ship, target, torps, S = torp()
	TT.place(target, 0.1, 30.0)
	assert FT.tscore(AF, ship, torps, target) == 0.0
	assert AF.TorpedoTarget(ship, torps, [target], TT.GROUP) == None
	assert AF.TubeScore(ship, torps, torps.lChildren[0], target, None, None, None, 1) == 0.0


def test_spread_inside_limit_and_window_main_and_secondary():
	App, AF, core, ship, target, torps, S = torp(TorpedoFlightTimeLimit=2.0,
		TorpedoFlightTimeLimitSecondary=2.0)
	TT.place(target, 0.1, 30.0)
	assert AF.TorpedoTarget(ship, torps, [target], TT.GROUP) == target
	assert torps.chain == 2
	assert AF.TubeScore(ship, torps, torps.lChildren[0], target, None, None, None, 1) > 0.0


def test_limit_inside_the_window_cuts_it():
	# 40 km = 2.29 s: in the window, over the 2.0 s limit.
	App, AF, core, ship, target, torps, S = torp(TorpedoFlightTimeLimit=2.0)
	TT.place(target, 0.1, 40.0)
	assert FT.tscore(AF, ship, torps, target) == 0.0


def test_size_extended_limit_opens_the_window_only_for_that_target():
	App, AF, core, ship, target, torps, S = torp(TargetSizeAllowance=100, TargetSizeFlightTimeMax=5.0)
	target.radius = 2.5 * FT.KM
	TS.engines(target, 1.75)
	TT.place(target, 0.1, 40.0)	# 2.29 s, limit stretched to 4.0 s
	assert AF.TorpedoTarget(ship, torps, [target], TT.GROUP) == target
	assert torps.chain == 2
	target.radius = 0.11 * FT.KM	# a fighter keeps the 1.0 s limit
	TS.engines(target, 6.0)
	assert AF.TorpedoTarget(ship, torps, [target], TT.GROUP) == None


def test_no_spread_without_spread_chain():
	App, AF, core, ship, target, torps, S = torp(TorpedoFlightTimeLimit=2.0)
	torps.chains = 1
	TT.place(target, 0.1, 30.0)
	assert AF.TorpedoTarget(ship, torps, [target], TT.GROUP) == target
	assert torps.chain == 0


def test_single_below_min():
	# 20 km = 1.14 s < 1.5 s.
	App, AF, core, ship, target, torps, S = torp(TorpedoFlightTimeLimit=2.0)
	TT.place(target, 0.1, 20.0)
	assert AF.TorpedoTarget(ship, torps, [target], TT.GROUP) == target
	assert torps.chain == 0


def test_single_above_max():
	# 60 km = 3.43 s > 2.5 s, inside the 5.0 s limit.
	App, AF, core, ship, target, torps, S = torp(TorpedoFlightTimeLimit=5.0)
	TT.place(target, 0.1, 60.0)
	assert AF.TorpedoTarget(ship, torps, [target], TT.GROUP) == target
	assert torps.chain == 0


def test_max_zero_spreads_any_time_from_min_up_to_the_limit():
	App, AF, core, ship, target, torps, S = torp(SpreadFlightTimeMax=0, TorpedoFlightTimeLimit=5.0)
	TT.place(target, 0.1, 60.0)
	assert AF.TorpedoTarget(ship, torps, [target], TT.GROUP) == target
	assert torps.chain == 2
	TT.place(target, 0.1, 100.0)	# 5.7 s: over the limit
	assert FT.tscore(AF, ship, torps, target) == 0.0


def test_rule_1_and_limit_off_leave_spread_alone():
	for dCfg in ({"TorpedoRule": 1}, {"TorpedoFlightTimeLimit": 0}):
		App, AF, core, ship, target, torps, S = torp(**dCfg)
		TT.place(target, 0.1, 30.0)
		assert AF.TorpedoTarget(ship, torps, [target], TT.GROUP) == target
		assert torps.chain == 2, dCfg


def test_manual_fire_filter_records_no_spread_verdict():
	App, AF, core, ship, target, torps, S = torp(TorpedoFlightTimeLimitSecondary=2.0)
	TT.place(target, 0.1, 30.0)
	assert FT.tscore(AF, ship, torps, target, 1) > 0.0
	assert AF.g_dSpreadOK == {}


def test_unknown_speed_fires_single():
	# Unknown speed: the filter does not block and spread is not allowed.
	App, AF, core, ship, target, torps, S = torp()
	torps.ammo = mock_app.Ammo(0.0)
	TT.place(target, 0.1, 30.0)
	assert FT.tscore(AF, ship, torps, target) > 0.0
	assert AF.TorpedoTarget(ship, torps, [target], TT.GROUP) == target
	assert torps.chain == 0


def test_arc_percent_still_applies_to_spread():
	App, AF, core, ship, target, torps, S = torp(TorpedoArcPercentFar=50, TorpedoArcPercentNear=50,
		TorpedoFlightTimeLimit=2.0)
	TT.place(target, 0.7, 30.0)
	assert FT.tscore(AF, ship, torps, target) == 0.0


def test_blocked_shot_in_the_window_logs_no_spread_pass():
	App, AF, core, ship, target, torps, S = torp()
	AF.g_bDebug = 1
	App.g_kUtopiaModule.GetGameTime = lambda: 10.0
	TT.place(target, 0.1, 30.0)
	FT.tscore(AF, ship, torps, target)
	lLog = [l[1] for l in core.logs if l[1].find("Flight time filter") >= 0]
	assert lLog == ["Flight time filter: torpedo main est 1.7 s > limit 1.0 s at 30 km"], lLog


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
	# Depth 50 in the window, allowed 90: not spread; the 1.0 s limit blocks it.
	App, AF, core, ship, target, torps, S = torp(TorpedoArcPercentFar=90, TorpedoArcPercentNear=90)
	TT.place(target, 0.5, 30.0)
	assert FT.tscore(AF, ship, torps, target) == 0.0
	# Same depth, limit large enough: fires, as Single.
	App, AF, core, ship, target, torps, S = torp(TorpedoArcPercentFar=90, TorpedoArcPercentNear=90,
		TorpedoFlightTimeLimit=2.0)
	TT.place(target, 0.5, 30.0)
	assert AF.TorpedoTarget(ship, torps, [target], TT.GROUP) == target
	assert torps.chain == 0


def test_custom_spread_arc_widens_spread():
	App, AF, core, ship, target, torps, S = torp(TorpedoArcPercentFar=90, TorpedoArcPercentNear=90,
		SpreadArcPercent=60, TorpedoFlightTimeLimit=2.0)
	TT.place(target, 0.5, 30.0)
	assert AF.TorpedoTarget(ship, torps, [target], TT.GROUP) == target
	assert torps.chain == 2


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
