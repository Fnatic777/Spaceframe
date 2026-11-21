"""Arc-percent rule: separate band for SECONDARY targets (TorpedoArc*Secondary /
PulseArc*Secondary). The main target keeps the main band."""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mock_app
import test_torpedo_arc as TT
import test_autofire_arc as TP
import test_secondary_cycle as TS


def torp_score(AF, ship, torps, target, bSec):
	tube = torps.lChildren[0]
	return AF.ArcScore(ship, torps, tube, target, None, "torpedo", 1, None, None, bSec)


def pulse_score(AF, ship, pulse, target, bSec):
	w = pulse.lChildren[0]
	return AF.ArcScore(ship, pulse, w, target, None, "pulse", 1, None, None, bSec)


# --- torpedo -----------------------------------------------------------------
def test_torpedo_secondary_band_stricter():
	App, AF, core, ship, target, torps, S = TT.rule3(TorpedoArcPercentFar=50, TorpedoArcPercentFarSecondary=30,
		TorpedoArcHysteresis=0)
	TT.place(target, 0.4, 40.0)
	assert torp_score(AF, ship, torps, target, 0) > 0.0	# main: 40 <= 50
	assert torp_score(AF, ship, torps, target, 1) == 0.0	# secondary: 40 > 30
	TT.place(target, 0.25, 40.0)
	assert torp_score(AF, ship, torps, target, 1) > 0.0


def test_torpedo_secondary_band_looser():
	App, AF, core, ship, target, torps, S = TT.rule3(TorpedoArcPercentFar=30, TorpedoArcPercentFarSecondary=80,
		TorpedoArcHysteresis=0)
	TT.place(target, 0.6, 40.0)
	assert torp_score(AF, ship, torps, target, 0) == 0.0
	assert torp_score(AF, ship, torps, target, 1) > 0.0


def test_torpedo_secondary_distance_band():
	App, AF, core, ship, target, torps, S = TT.rule3(TorpedoArcPercentFar=50, TorpedoArcPercentNear=90,
		TorpedoArcFarDistanceSecondary=100, TorpedoArcNearDistanceSecondary=50, TorpedoArcHysteresis=0)
	tMain = AF.ArcBand("torpedo")[0]
	tSec = AF.ArcBand("torpedo", 1)[0]
	assert abs(tSec[2] - 100 / 0.175) < 1e-6 and abs(tSec[3] - 50 / 0.175) < 1e-6
	assert abs(tMain[2] - 30 / 0.175) < 1e-6


def test_torpedo_main_target_path_unaffected():
	# BestTorpedoScore (main target) ignores the secondary band.
	App, AF, core, ship, target, torps, S = TT.rule3(TorpedoArcPercentFar=50, TorpedoArcPercentFarSecondary=10,
		TorpedoArcHysteresis=0)
	TT.place(target, 0.4, 40.0)
	assert AF.BestTorpedoScore(ship, torps, target) > 0.0


def test_torpedo_tubescore_passes_secondary():
	App, AF, core, ship, target, torps, S = TT.rule3(TorpedoArcPercentFar=50, TorpedoArcPercentFarSecondary=30,
		TorpedoArcHysteresis=0)
	TT.place(target, 0.4, 40.0)
	tube = torps.lChildren[0]
	assert AF.TubeScore(ship, torps, tube, target, None, None, None) > 0.0
	assert AF.TubeScore(ship, torps, tube, target, None, None, None, 1) == 0.0


# --- pulse -------------------------------------------------------------------
def test_pulse_secondary_band_differs():
	App, AF, core, ship, target, pulse, S = TP.rule3(PulseArcPercentFar=50, PulseArcPercentFarSecondary=30,
		PulseArcHysteresis=0)
	TP.place(target, 0.4, 40.0)
	assert pulse_score(AF, ship, pulse, target, 0) > 0.0
	assert pulse_score(AF, ship, pulse, target, 1) == 0.0
	assert AF.PulseArcScore(ship, pulse, pulse.lChildren[0], target, None) > 0.0	# main path


def test_pulse_secondary_band_looser():
	App, AF, core, ship, target, pulse, S = TP.rule3(PulseArcPercentFar=30, PulseArcPercentFarSecondary=80,
		PulseArcHysteresis=0)
	TP.place(target, 0.6, 40.0)
	assert pulse_score(AF, ship, pulse, target, 0) == 0.0
	assert pulse_score(AF, ship, pulse, target, 1) > 0.0


# --- manual filter -----------------------------------------------------------
def test_arc_reaches_default_is_main_band():
	App, AF, core, ship, target, torps, S = TT.rule3(TorpedoArcPercentFar=50, TorpedoArcPercentFarSecondary=30,
		TorpedoArcHysteresis=0)
	tube = torps.lChildren[0]
	TT.place(target, 0.4, 40.0)
	assert AF.ArcReaches(ship, torps, tube, target, "torpedo") == 1
	assert AF.ArcReaches(ship, torps, tube, target, "torpedo", 1) == 0


def test_arc_reaches_pulse_secondary():
	App, AF, core, ship, target, pulse, S = TP.rule3(PulseArcPercentFar=50, PulseArcPercentFarSecondary=30,
		PulseArcHysteresis=0)
	w = pulse.lChildren[0]
	TP.place(target, 0.4, 40.0)
	assert AF.ArcReaches(ship, pulse, w, target, "pulse") == 1
	assert AF.ArcReaches(ship, pulse, w, target, "pulse", 1) == 0


def test_secondary_target_asks_with_secondary_flag():
	App, ST, core, ship = TS.setup()
	main, b, c, pSys = TS.pulse_scene(core, ship)
	lAsked = []
	TS.arc_rule(ST, "pulse", lambda pShip, pSys_, pWeapon, pCand, s, bSec=0: lAsked.append(bSec) or 1)
	ST.WantedTargets(ship, pSys, main, "pulse")
	assert len(lAsked) > 0 and lAsked[0] == 1


# --- config ------------------------------------------------------------------
def test_config_defines_secondary_settings():
	import types
	import importlib.util
	sPath = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
		"scripts", "Custom", "Spaceframe", "Modules", "AutoFire", "Config.py")
	spec = importlib.util.spec_from_file_location("af_cfg_real", sPath)
	cfg = importlib.util.module_from_spec(spec)
	spec.loader.exec_module(cfg)
	for sKind in ("Pulse", "Torpedo"):
		for sName in ("PercentFar", "PercentNear", "FarDistance", "NearDistance"):
			sMain = sKind + "Arc" + sName
			sSec = sMain + "Secondary"
			assert hasattr(cfg, sMain) and hasattr(cfg, sSec), sSec


def test_missing_secondary_falls_back_to_main():
	App, AF, core, ship = TT.base.setup(TorpedoArcPercentFar=44, TorpedoArcPercentNear=77, TorpedoArcFarDistance=20,
		TorpedoArcNearDistance=2, PulseArcPercentFar=33, PulseArcPercentNear=66, PulseArcFarDistance=25,
		PulseArcNearDistance=3)
	assert AF.g_fTorpArcFarSec == 44.0 and AF.g_fTorpArcNearSec == 77.0
	assert abs(AF.g_fTorpArcFarDistanceSec - 20 / 0.175) < 1e-6 and abs(AF.g_fTorpArcNearDistanceSec - 2 / 0.175) < 1e-6
	assert AF.g_fArcFarSec == 33.0 and AF.g_fArcNearSec == 66.0
	assert abs(AF.g_fArcFarDistanceSec - 25 / 0.175) < 1e-6 and abs(AF.g_fArcNearDistanceSec - 3 / 0.175) < 1e-6


def test_secondary_config_read():
	App, AF, core, ship = TT.base.setup(TorpedoArcPercentFarSecondary=11, TorpedoArcPercentNearSecondary=22,
		TorpedoArcFarDistanceSecondary=40, TorpedoArcNearDistanceSecondary=4, PulseArcPercentFarSecondary=12,
		PulseArcPercentNearSecondary=23, PulseArcFarDistanceSecondary=41, PulseArcNearDistanceSecondary=6)
	assert AF.g_fTorpArcFarSec == 11.0 and AF.g_fTorpArcNearSec == 22.0
	assert abs(AF.g_fTorpArcFarDistanceSec - 40 / 0.175) < 1e-6 and abs(AF.g_fTorpArcNearDistanceSec - 4 / 0.175) < 1e-6
	assert AF.g_fArcFarSec == 12.0 and AF.g_fArcNearSec == 23.0
	assert abs(AF.g_fArcFarDistanceSec - 41 / 0.175) < 1e-6 and abs(AF.g_fArcNearDistanceSec - 6 / 0.175) < 1e-6


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
