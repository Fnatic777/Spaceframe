"""Task 4 tests: automatic torpedo spread."""
import os
import sys
import types
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mock_app
import test_autofire_base as base


def setup(score=90.0, chains=3, player_mode=0, km=10.0, min_km=3.0):
	App, AF, core, ship = base.setup(SpreadMinSolution=75, SpreadMinDistance=min_km)
	S = types.ModuleType("Custom.Spaceframe.Modules.AutoFire.Solution")
	S.score = score
	base.fake_arc_score(AF, lambda pTarget: S.score)
	S.GetProjectileInfo = lambda w, s: (100.0, 0.1, 10.0, 0.0)
	sys.modules["Custom.Spaceframe.Modules.AutoFire.Solution"] = S
	sys.modules["Custom.Spaceframe.Modules.AutoFire"].Solution = S
	target = mock_app.Ship("Bug", 7)
	target.pos = mock_app.Point(km / 0.175 + target.radius, 0.0, 0.0)
	ship.target = target
	core.g_pMission = mock_app.Mission([target])	# the target is an enemy
	torps = mock_app.WeaponGroup([mock_app.Tube()])
	torps.torpedo = 1
	torps.chains = chains
	torps.chain = player_mode
	ship.groups[App.ShipClass.WG_SECONDARY] = torps
	AF.Toggle()
	return App, AF, core, ship, torps, S


def test_spread_high_score():
	App, AF, core, ship, torps, S = setup(90.0, 3)
	AF.FireCycle()
	assert torps.chain == 2 and torps.starts() == 1


def test_single_mid_score():
	App, AF, core, ship, torps, S = setup(60.0, 3, player_mode=2)
	AF.FireCycle()
	assert torps.chain == 0 and torps.starts() == 1


def test_no_change_when_holding_fire():
	# No tube reaches the target (score 0): nothing is fired, the spread is left alone.
	App, AF, core, ship, torps, S = setup(0.0, 3, player_mode=1)
	AF.FireCycle()
	assert torps.chain == 1 and torps.chain_sets == 0


def test_spread_only_single():
	App, AF, core, ship, torps, S = setup(95.0, 1)
	AF.FireCycle()
	assert torps.chain == 0


def test_no_resetting_every_cycle():
	App, AF, core, ship, torps, S = setup(90.0, 3)
	AF.FireCycle()
	AF.FireCycle()
	AF.FireCycle()
	assert torps.chain_sets == 1


def test_restore_on_disable():
	App, AF, core, ship, torps, S = setup(90.0, 3, player_mode=1)
	AF.FireCycle()
	assert torps.chain == 2
	AF.Toggle()
	assert torps.chain == 1


def test_restore_on_manual():
	App, AF, core, ship, torps, S = setup(90.0, 3, player_mode=1)
	AF.FireCycle()
	AF.OnManualFire(None, mock_app.Event(App.ET_INPUT_FIRE_SECONDARY, 1))
	assert torps.chain == 1
	AF.FireCycle()
	assert torps.chain == 1	# hands off while the player fires


def test_player_changes_spread_while_on():
	# The player picks a spread while Auto Fire is on: that becomes the
	# spread to go back to.
	App, AF, core, ship, torps, S = setup(90.0, 3, player_mode=0)
	AF.FireCycle()
	torps.chain = 1
	AF.FireCycle()
	AF.Toggle()
	assert torps.chain == 1


def test_stop_does_not_touch_spread():
	# Stop runs while the game destroys the ships: nothing is asked of them.
	App, AF, core, ship, torps, S = setup(90.0, 3, player_mode=1)
	AF.FireCycle()
	n = torps.chain_sets
	AF.Stop()
	assert torps.chain_sets == n


def test_spread_too_close():
	# Spread torpedoes fly apart before they turn to the target: too close
	# and they miss, so Single there.
	App, AF, core, ship, torps, S = setup(95.0, 3, km=2.0, min_km=3.0)
	AF.FireCycle()
	assert torps.chain == 0 and torps.starts() == 1


def test_spread_far_enough():
	App, AF, core, ship, torps, S = setup(95.0, 3, km=4.0, min_km=3.0)
	AF.FireCycle()
	assert torps.chain == 2


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
