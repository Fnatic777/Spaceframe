"""AutoFire target size: the flight-time limit stretches for targets that are
large or hard to move (TargetSize.py), never below the configured limit."""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mock_app
import test_autofire_base as base
import test_flight_time as FT
import test_torpedo_arc as TT

KM = 1.0 / 0.175	# game units per km


def engines(target, fAccel):
	# fAccel None = no impulse subsystem
	class E:
		def GetCurMaxAccel(self):
			return fAccel
	pEngines = None
	if fAccel is not None:
		pEngines = E()
	target.GetImpulseEngineSubsystem = lambda: pEngines


def make(fKm, fAccel, **kw):
	dCfg = {"TargetSizeAllowance": 100, "TargetSizeFlightTimeMax": 5.0}
	dCfg.update(kw)
	App, AF, core, ship = base.setup(**dCfg)
	target = mock_app.Ship("Bug", 7)
	target.radius = fKm * KM
	engines(target, fAccel)
	return AF, AF.GetTargetSize(), target


def limit(fKm, fAccel, fBase, **kw):
	AF, TS, target = make(fKm, fAccel, **kw)
	return TS.Extend(target, fBase)[0]


def near(a, b):
	return abs(a - b) < 0.001


# --- settings ------------------------------------------------------------------
def test_config_read_and_default_off():
	AF, TS, target = make(2.5, 1.75)
	assert AF.g_fSizeAllowance == 100.0 and AF.g_fSizeFtMax == 5.0
	App, AF, core, ship = base.setup()
	assert AF.g_fSizeAllowance == 0.0 and AF.g_fSizeFtMax == 0.0
	assert AF.GetTargetSize().Extend(target, 1.5) == (1.5, None, None)


# --- the calculation -----------------------------------------------------------
def test_spec_examples():
	assert limit(0.11, 6.0, 1.5) == 1.5
	assert limit(0.11, 6.0, 1.0) == 1.0
	assert limit(0.3, 2.5, 1.5) == 1.5
	assert near(limit(0.3, 2.5, 1.0), 1.1711)
	assert near(limit(0.65, 1.75, 1.5), 2.0603)
	assert near(limit(2.5, 1.75, 1.5), 4.0406)


def test_allowance_scales_the_time():
	assert near(limit(0.65, 1.75, 1.5, TargetSizeAllowance=200), 2.9137)


def test_no_engines_or_no_accel_gets_the_cap():
	for fAccel in (None, 0.0, 0.005):
		assert limit(0.3, fAccel, 1.5) == 5.0


def test_cap_applies():
	assert limit(2.5, 0.875, 1.5) == 5.0


def test_cap_below_base_keeps_base():
	assert limit(2.5, 1.75, 1.5, TargetSizeFlightTimeMax=1.0) == 1.5


def test_zero_or_negative_settings_are_off():
	assert limit(2.5, 1.75, 1.5, TargetSizeAllowance=0) == 1.5
	assert limit(2.5, 1.75, 1.5, TargetSizeAllowance=-50) == 1.5
	assert limit(2.5, None, 1.5, TargetSizeFlightTimeMax=0) == 1.5


def test_bad_radius_keeps_base_even_without_engines():
	for fKm in (0.0, -1.0):
		assert limit(fKm, None, 1.5) == 1.5


def test_read_errors_keep_base():
	AF, TS, target = make(2.5, 1.75)

	def boom():
		raise RuntimeError("x")
	target.GetImpulseEngineSubsystem = boom
	assert TS.Extend(target, 1.5) == (1.5, None, None)
	engines(target, 1.75)
	target.GetRadius = boom
	assert TS.Extend(target, 1.5) == (1.5, None, None)


def test_return_carries_radius_and_accel():
	AF, TS, target = make(2.5, 1.75)
	tSize = TS.Extend(target, 1.5)
	assert near(tSize[1], 2.5 * KM) and tSize[2] == 1.75
	engines(target, None)
	assert TS.Extend(target, 1.5)[2] is None


# --- the flight-time filter ------------------------------------------------------
SIZE = {"TargetSizeAllowance": 100, "TargetSizeFlightTimeMax": 5.0}


def setup_torp(fKm, fAccel, **kw):
	dCfg = dict(SIZE)
	dCfg.update(kw)
	App, AF, core, ship, target, torps, S = FT.torp(**dCfg)
	target.radius = fKm * KM
	engines(target, fAccel)
	return App, AF, core, ship, target, torps


def blocked(AF, target, fSeconds, bSec=0, fLifetime=0.0):
	# speed 100, guidance 0.1 s
	return AF.FlightBlocked("torpedo", bSec, fSeconds * 100.0, 100.0, 7, 0.1, fLifetime, target)


def test_extended_limit_adds_guidance():
	App, AF, core, ship, target, torps = setup_torp(0.65, 1.75, TorpedoFlightTimeLimit=1.5)
	assert blocked(AF, target, 2.15) == 0
	assert blocked(AF, target, 2.18) == 1
	assert AF.FlightBlocked("torpedo", 0, 215.0, 100.0, 7, 0.1, 0.0) == 1	# no target


def test_lifetime_still_caps():
	App, AF, core, ship, target, torps = setup_torp(2.5, 1.75, TorpedoFlightTimeLimit=1.5)
	assert blocked(AF, target, 3.5, 0, 3.0) == 1
	assert blocked(AF, target, 2.9, 0, 3.0) == 0


def test_secondary_uses_its_own_base_and_off_stays_off():
	App, AF, core, ship, target, torps = setup_torp(0.3, 2.5, TorpedoFlightTimeLimit=1.5,
		TorpedoFlightTimeLimitSecondary=1.0)
	assert blocked(AF, target, 1.25, 1) == 0 and blocked(AF, target, 1.30, 1) == 1
	App, AF, core, ship, target, torps = setup_torp(0.11, 6.0, TorpedoFlightTimeLimit=1.5,
		TorpedoFlightTimeLimitSecondary=0)
	assert blocked(AF, target, 9.0, 1) == 0


def test_rule_1_stays_unfiltered():
	App, AF, core, ship, target, torps = setup_torp(0.11, 6.0, TorpedoRule=1, TorpedoFlightTimeLimit=1.5)
	assert blocked(AF, target, 9.0) == 0


def test_score_main_and_secondary_follow_the_target():
	App, AF, core, ship, target, torps = setup_torp(2.5, 1.75, TorpedoFlightTimeLimit=1.5,
		TorpedoFlightTimeLimitSecondary=1.0)
	TT.place(target, 0.1, 50.0)	# 2.86 s: past the spread window
	assert FT.tscore(AF, ship, torps, target) > 0.0
	assert FT.tscore(AF, ship, torps, target, 1) > 0.0
	target.radius = 0.11 * KM
	engines(target, 6.0)
	assert FT.tscore(AF, ship, torps, target) == 0.0
	assert FT.tscore(AF, ship, torps, target, 1) == 0.0


def test_pulse_follows_the_target():
	dCfg = dict(SIZE)
	dCfg["PulseFlightTimeLimit"] = 1.5
	App, AF, core, ship, target, pul, S = FT.pulse(**dCfg)
	target.radius = 2.5 * KM
	engines(target, 1.75)
	FT.TP.place(target, 0.1, 80.0)	# 3.05 s at speed 150
	assert FT.pscore(AF, ship, pul, target) > 0.0
	engines(target, 20.0)
	assert FT.pscore(AF, ship, pul, target) == 0.0


# --- debug log -------------------------------------------------------------------
def log_lines(fKm, fAccel, fBase):
	App, AF, core, ship, target, torps = setup_torp(fKm, fAccel, TorpedoFlightTimeLimit=fBase)
	AF.g_bDebug = 1
	App.g_kUtopiaModule.GetGameTime = lambda: 10.0
	TT.place(target, 0.1, 20.0)
	FT.tscore(AF, ship, torps, target)
	FT.tscore(AF, ship, torps, target)
	return [l[1] for l in core.logs if l[1].find("Flight time filter") >= 0]


HEAD = "Flight time filter: torpedo main est 1.1 s > limit "


def test_log_passed_by_size_once():
	assert log_lines(2.5, 1.75, 1.0) == [HEAD + "1.0 s at 20 km, passed by target size (limit 4.0 s, radius 2.50 km, accel 1.75)"]


def test_log_blocked_shows_extended_limit():
	assert log_lines(0.2, 2.5, 0.5) == [HEAD + "1.0 s at 20 km, target radius 0.20 km accel 2.50"]


def test_log_blocked_without_extension():
	assert log_lines(0.11, 6.0, 1.0) == [HEAD + "1.0 s at 20 km, target radius 0.11 km accel 6.00"]


def test_log_no_engines():
	lLines = log_lines(2.5, None, 1.0)
	assert lLines[0].endswith("passed by target size (limit 5.0 s, radius 2.50 km, accel none)"), lLines


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
