"""Task 2 tests: fire cycle and phasers."""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mock_app
import test_autofire_base as base


def setup(dist=80.0, charge=0.6, arc=1, **kw):
	App, AF, core, ship = base.setup(PhaserRange=100, PhaserMinCharge=50, **kw)
	target = mock_app.Ship("Bug", 7)
	target.pos = mock_app.Point(dist + target.radius, 0.0, 0.0)
	ship.target = target
	core.g_pMission = mock_app.Mission([target])	# the target is an enemy
	primary = mock_app.WeaponGroup([mock_app.Bank(100.0, charge, arc)])
	ship.groups[App.ShipClass.WG_PRIMARY] = primary
	AF.Toggle()
	return App, AF, ship, target, primary


def test_phaser_fires_in_range():
	App, AF, ship, target, primary = setup(80.0)
	AF.FireCycle()
	assert primary.starts() == 1 and primary.calls[0][1] is target


def test_phaser_out_of_range():
	App, AF, ship, target, primary = setup(80.0)
	AF.FireCycle()
	target.pos = mock_app.Point(120.0 + target.radius, 0.0, 0.0)
	AF.FireCycle()
	assert primary.stops() == 1


def test_phaser_not_in_arc():
	App, AF, ship, target, primary = setup(80.0, arc=0)
	AF.FireCycle()
	assert primary.starts() == 0


def test_phaser_low_charge():
	App, AF, ship, target, primary = setup(80.0, charge=0.4)
	AF.FireCycle()
	assert primary.starts() == 0


def test_phaser_range_setting():
	App, AF, ship, target, primary = setup(80.0)
	AF.GetConfig().PhaserRange = 50
	AF.LoadConfig()	# settings are cached at Start
	AF.FireCycle()
	assert primary.starts() == 0


class CountBank(mock_app.Bank):
	def __init__(self, *a):
		mock_app.Bank.__init__(self, *a)
		self.n = {"charge": 0, "max": 0}

	def GetChargePercentage(self):
		self.n["charge"] = self.n["charge"] + 1
		return self.fCharge

	def GetMaxDamageDistance(self):
		self.n["max"] = self.n["max"] + 1
		return self.fMax


def ready(AF, target, **kw):
	cfg = AF.GetConfig()
	for k in kw:
		setattr(cfg, k, kw[k])
	AF.LoadConfig()
	return AF.PhaserReady


def test_range_zero_skips_range_check():
	App, AF, ship, target, primary = setup(80.0)
	pBank = CountBank(100.0, 1.0, 1)
	target.pos = mock_app.Point(5000.0, 0.0, 0.0)	# far beyond 5x max damage distance
	fn = ready(AF, target, PhaserRange=0)
	assert fn(pBank, target) == 1
	assert pBank.n["max"] == 0
	# not in arc: still not ready
	assert fn(CountBank(100.0, 1.0, 0), target) == 0


def test_min_charge_zero_skips_charge_check():
	App, AF, ship, target, primary = setup(80.0)
	pBank = CountBank(100.0, 0.0, 1)
	fn = ready(AF, target, PhaserMinCharge=0)
	assert fn(pBank, target) == 1
	assert pBank.n["charge"] == 0


def test_positive_values_boundaries():
	App, AF, ship, target, primary = setup(80.0)
	fn = ready(AF, target, PhaserRange=100, PhaserMinCharge=50)
	assert fn(CountBank(100.0, 0.5, 1), target) == 1	# charge exactly 50
	assert fn(CountBank(100.0, 0.49, 1), target) == 0
	target.pos = mock_app.Point(100.0 + target.radius, 0.0, 0.0)	# exactly at range
	assert fn(CountBank(100.0, 1.0, 1), target) == 1
	target.pos = mock_app.Point(100.5 + target.radius, 0.0, 0.0)
	assert fn(CountBank(100.0, 1.0, 1), target) == 0


def test_manual_priority():
	App, AF, ship, target, primary = setup(80.0)
	AF.g_dManual[App.ShipClass.WG_PRIMARY] = 1
	AF.FireCycle()
	target.pos = mock_app.Point(500.0, 0.0, 0.0)
	AF.FireCycle()
	assert primary.calls == []


def test_cloaked():
	App, AF, ship, target, primary = setup(80.0)
	ship.cloaked = 1
	AF.FireCycle()
	assert primary.starts() == 0


def test_not_red_alert():
	App, AF, ship, target, primary = setup(80.0)
	AF.FireCycle()
	ship.alert = App.ShipClass.YELLOW_ALERT
	AF.FireCycle()
	assert primary.stops() == 1
	AF.FireCycle()
	assert primary.stops() == 1 and primary.starts() == 1


def test_target_destroyed():
	App, AF, ship, target, primary = setup(80.0)
	AF.FireCycle()
	target.dead = 1
	AF.FireCycle()
	assert primary.stops() == 1


def test_no_target():
	App, AF, ship, target, primary = setup(80.0)
	AF.FireCycle()
	ship.target = None
	AF.FireCycle()
	assert primary.stops() == 1


def test_missing_group():
	App, AF, ship, target, primary = setup(80.0)
	assert ship.GetWeaponSystemGroup(App.ShipClass.WG_SECONDARY) is None
	AF.FireCycle()
	assert primary.starts() == 1


def test_no_restart_while_firing():
	App, AF, ship, target, primary = setup(80.0)
	AF.FireCycle()
	AF.FireCycle()
	AF.FireCycle()
	assert primary.starts() == 1


def test_disable_stops_all():
	App, AF, ship, target, primary = setup(80.0)
	assert AF.g_pTimer != None
	AF.FireCycle()
	AF.Toggle()
	assert primary.stops() == 1
	assert AF.g_pTimer == None


def test_ship_changed_stops():
	App, AF, ship, target, primary = setup(80.0)
	AF.FireCycle()
	App._player[0] = mock_app.Ship("Galaxy", 2)
	AF.FireCycle()
	assert primary.stops() == 1
	assert AF.g_pTimer == None


def test_timer_calls_cycle():
	App, AF, ship, target, primary = setup(80.0)
	AF.g_pTimer.Update(0.1)
	assert primary.starts() == 1
	assert AF.g_pTimer.pProcess.delay == 0.1


def test_stop_does_not_touch_ships():
	# The battle ends (ships being destroyed): Stop only forgets.
	App, AF, ship, target, primary = setup(80.0)
	AF.FireCycle()
	AF.Stop()
	assert primary.stops() == 0
	assert AF.g_pTimer == None


def test_fire_key_release_rearms():
	# A click in the menus goes through the fire input: on release the game
	# stops the group itself. Auto Fire must start it again.
	App, AF, ship, target, primary = setup(80.0)
	AF.FireCycle()
	AF.OnManualFire(None, mock_app.Event(App.ET_INPUT_FIRE_PRIMARY, 1))
	AF.OnManualFire(None, mock_app.Event(App.ET_INPUT_FIRE_PRIMARY, 0))
	primary.GameStop()
	AF.FireCycle()
	assert primary.starts() == 2


def test_stopped_by_game_restarts():
	# Stopped some other way by the game: noticed and started again.
	App, AF, ship, target, primary = setup(80.0)
	AF.FireCycle()
	primary.GameStop()
	AF.FireCycle()
	assert primary.starts() == 2


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
