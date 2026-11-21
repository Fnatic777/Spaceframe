"""AutoFire optimizations: settings cached at Start, Debug guards."""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mock_app
import test_autofire_base as base
import test_autofire_phasers as ph


def test_defaults_cached_at_start():
	App, AF, core, ship = base.setup()
	assert AF.g_iTargetMode == 0 and AF.g_fPhaserMinCharge == 50.0
	assert AF.g_fPhaserRange == 100.0 and AF.g_iTorpedoReserve == 0
	assert AF.g_iTorpedoRule == 2
	assert AF.g_fSpreadMinSolution == 85.0 and AF.g_fSpreadMinDistance == 0.0
	assert AF.g_iPulseRule == 2
	assert AF.g_iTapFire == 1 and AF.g_bDebug == 0


def test_custom_cached_at_start():
	App, AF, core, ship = base.setup(TargetMode=2, PhaserMinCharge=30, PhaserRange=80,
		TorpedoReserve=3, TorpedoRule=1, SpreadMinSolution=90,
		SpreadMinDistance=4, PulseRule=1, TapFire=0)
	assert AF.g_iTargetMode == 2 and AF.g_fPhaserMinCharge == 30.0
	assert AF.g_fPhaserRange == 80.0 and AF.g_iTorpedoReserve == 3
	assert AF.g_iTorpedoRule == 1
	assert AF.g_fSpreadMinSolution == 90.0 and AF.g_fSpreadMinDistance == 4.0
	assert AF.g_iPulseRule == 1
	assert AF.g_iTapFire == 0


def test_restart_reloads_settings():
	App, AF, core, ship = base.setup()
	AF.GetConfig().TapFire = 0
	AF.Start(core)
	assert AF.g_iTapFire == 0


def test_debug_off_no_log_no_probe():
	App, AF, ship, target, primary = ph.setup(80.0)
	assert AF.g_bDebug == 0
	AF.g_dScore[App.ShipClass.WG_PRIMARY] = 55.0
	AF.FireCycle()
	assert primary.starts() == 1
	assert [l for l in AF.g_pCore.logs if l[1].find("Group") >= 0 or l[1].find("GetPredictedPosition") >= 0] == []


def test_debug_on_logs_and_probes():
	App, AF, core, ship = base.setup()
	core.GetConfigValue = lambda sName, pDefault: 1
	AF.Start(core)
	assert AF.g_bDebug == 1
	assert [l for l in core.logs if l[1].find("GetPredictedPosition") >= 0] != []
	AF.g_dScore[App.ShipClass.WG_PRIMARY] = 55.0
	AF.FireGroup(ship, App.ShipClass.WG_PRIMARY, mock_app.Ship("Bug", 9), 0)
	ship.groups[App.ShipClass.WG_PRIMARY] = mock_app.WeaponGroup([])
	AF.FireGroup(ship, App.ShipClass.WG_PRIMARY, mock_app.Ship("Bug", 9), 1)
	assert ("AutoFire", "Group %d fires, solution 55" % App.ShipClass.WG_PRIMARY) in core.logs


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
	print("%d/%d passed" % (len(names) - failed, len(names)))
	return failed


if __name__ == "__main__":
	sys.exit(run())
