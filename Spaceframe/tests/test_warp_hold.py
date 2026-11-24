"""HoldOnWarp / WarpHoldGrace: Auto Fire holds fire (score 0) on a target doing an
in-system warp and for a grace period after it; manual fire is never held."""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mock_app
import test_autofire_base as base
import test_torpedo_arc as TT
import test_autofire_arc as TP

WH = None	# the WarpHold module of the current scene


def clock_at(App, clock):
	App.g_kUtopiaModule.GetGameTime = lambda: clock[0]


def torp(**kw):
	global WH
	dCfg = {"TorpedoRule": 1, "TorpedoArcPercentFar": 100, "TorpedoArcPercentNear": 100,
		"TorpedoArcPercentFarSecondary": 100, "TorpedoArcPercentNearSecondary": 100,
		"TorpedoArcHysteresis": 0}
	for k in kw:
		dCfg[k] = kw[k]
	App, AF, core, ship, target, torps, S = TT.rule3(**dCfg)
	WH = sys.modules["Custom.Spaceframe.Modules.AutoFire.WarpHold"]
	clock = [10.0]
	clock_at(App, clock)
	target.warping = [0]
	target.IsDoingInSystemWarp = lambda: target.warping[0]
	TT.place(target, 0.1, 20.0)
	return App, AF, core, ship, target, torps, clock


def pulse(**kw):
	global WH
	dCfg = {"PulseRule": 1, "PulseArcPercentFar": 100, "PulseArcPercentNear": 100,
		"PulseArcPercentFarSecondary": 100, "PulseArcPercentNearSecondary": 100,
		"PulseArcHysteresis": 0}
	for k in kw:
		dCfg[k] = kw[k]
	App, AF, core, ship, target, pul, S = TP.rule3(**dCfg)
	WH = sys.modules["Custom.Spaceframe.Modules.AutoFire.WarpHold"]
	clock = [10.0]
	clock_at(App, clock)
	target.warping = [0]
	target.IsDoingInSystemWarp = lambda: target.warping[0]
	TP.place(target, 0.1, 20.0)
	return App, AF, core, ship, target, pul, clock


def tmain(AF, ship, torps, target):
	return AF.BestTorpedoScore(ship, torps, target)


def tsec(AF, ship, torps, target):
	return AF.TubeScore(ship, torps, torps.lChildren[0], target, None, None, None, 1)


def pmain(AF, ship, pul, target):
	return AF.PulseArcScore(ship, pul, pul.lChildren[0], target, None)


def psec(AF, ship, pul, target):
	return AF.ArcScore(ship, pul, pul.lChildren[0], target, None, "pulse", 1, None, None, 1)


def test_torpedo_main_and_secondary_held_while_warping():
	App, AF, core, ship, target, torps, clock = torp()
	assert tmain(AF, ship, torps, target) > 0.0 and tsec(AF, ship, torps, target) > 0.0
	target.warping[0] = 1
	assert tmain(AF, ship, torps, target) == 0.0
	assert tsec(AF, ship, torps, target) == 0.0
	assert AF.TorpedoTarget(ship, torps, [target], TT.GROUP) == None


def test_pulse_main_and_secondary_held_while_warping():
	App, AF, core, ship, target, pul, clock = pulse()
	assert pmain(AF, ship, pul, target) > 0.0 and psec(AF, ship, pul, target) > 0.0
	target.warping[0] = 1
	assert pmain(AF, ship, pul, target) == 0.0
	assert psec(AF, ship, pul, target) == 0.0


def test_rule_2_is_held_too():
	App, AF, core, ship, target, torps, clock = torp(TorpedoRule=2)
	target.warping[0] = 1
	assert tmain(AF, ship, torps, target) == 0.0


def test_released_after_the_grace():
	App, AF, core, ship, target, torps, clock = torp(WarpHoldGrace=1.0)
	target.warping[0] = 1
	assert tmain(AF, ship, torps, target) == 0.0
	target.warping[0] = 0
	clock[0] = 10.5
	assert tmain(AF, ship, torps, target) == 0.0	# grace
	clock[0] = 11.1
	assert tmain(AF, ship, torps, target) > 0.0
	assert WH.g_dWarp == {}


def test_grace_zero_releases_at_once():
	App, AF, core, ship, target, torps, clock = torp(WarpHoldGrace=0)
	target.warping[0] = 1
	assert tmain(AF, ship, torps, target) == 0.0
	target.warping[0] = 0
	assert tmain(AF, ship, torps, target) > 0.0


def test_hold_off_disables():
	App, AF, core, ship, target, torps, clock = torp(HoldOnWarp=0)
	target.warping[0] = 1
	assert tmain(AF, ship, torps, target) > 0.0
	App, AF, core, ship, target, pul, clock = pulse(HoldOnWarp=0)
	target.warping[0] = 1
	assert pmain(AF, ship, pul, target) > 0.0


def test_other_target_unaffected():
	App, AF, core, ship, target, torps, clock = torp()
	pOther = mock_app.Ship("Other", 9)
	TT.place(pOther, 0.1, 20.0)
	target.warping[0] = 1
	assert tmain(AF, ship, torps, target) == 0.0
	assert tmain(AF, ship, torps, pOther) > 0.0


def test_missing_or_raising_method_is_not_warping():
	App, AF, core, ship, target, torps, clock = torp()
	del target.IsDoingInSystemWarp
	assert tmain(AF, ship, torps, target) > 0.0

	def boom():
		raise RuntimeError("no")
	target.IsDoingInSystemWarp = boom
	assert tmain(AF, ship, torps, target) > 0.0


def test_manual_fire_filter_unaffected():
	App, AF, core, ship, target, torps, clock = torp()
	target.warping[0] = 1
	assert AF.ArcReaches(ship, torps, torps.lChildren[0], target, "torpedo", 1) == 1
	assert AF.ArcReaches(ship, torps, torps.lChildren[0], target, "torpedo", 0) == 1
	App, AF, core, ship, target, pul, clock = pulse()
	target.warping[0] = 1
	assert AF.ArcReaches(ship, pul, pul.lChildren[0], target, "pulse", 0) == 1


def test_debug_line_rate_limited_with_speed_ratio():
	App, AF, core, ship, target, torps, clock = torp(WarpHoldGrace=5.0)
	AF.g_bDebug = 1
	target.vel = mock_app.Point(30.0, 0.0, 0.0)
	target.GetImpulseEngineSubsystem = lambda: type("E", (), {"GetMaxSpeed": lambda self: 10.0})()
	target.warping[0] = 1
	tmain(AF, ship, torps, target)
	tmain(AF, ship, torps, target)
	l = [x[1] for x in core.logs if x[1].startswith("Warp hold:")]
	assert len(l) == 1 and "target 7 warping" in l[0] and "speed ratio 3.00" in l[0], l
	clock[0] = 13.0
	target.warping[0] = 0
	clock[0] = 12.5
	tmain(AF, ship, torps, target)
	l = [x[1] for x in core.logs if x[1].startswith("Warp hold:")]
	assert len(l) == 2 and "target 7 grace" in l[1], l


def test_state_cleared_on_start_and_stop():
	App, AF, core, ship, target, torps, clock = torp()
	target.warping[0] = 1
	tmain(AF, ship, torps, target)
	assert WH.g_dWarp != {}
	AF.Stop()
	assert WH.g_dWarp == {}


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
