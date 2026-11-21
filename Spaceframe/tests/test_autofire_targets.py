"""Task 6 tests: target modes 0, 1 and 2."""
import os
import sys
import types
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mock_app
import test_autofire_base as base


def enemy(sName, iID, fDist):
	e = mock_app.Ship(sName, iID)
	e.pos = mock_app.Point(fDist + e.radius, 0.0, 0.0)
	return e


def setup(mode, enemies, scores=None, friends=None, **kw):
	App, AF, core, ship = base.setup(TargetMode=mode, PhaserRange=100, PhaserMinCharge=50, **kw)
	core.g_pMission = mock_app.Mission(enemies, friends)
	for e in enemies + (friends or []):
		mock_app.SHIPS[e.GetObjID()] = e	# registry cleared by make_app
	S = types.ModuleType("Custom.Spaceframe.Modules.AutoFire.Solution")
	dScores = scores or {}
	S.GetProjectileInfo = lambda w, s: (100.0, 0.1, 10.0, 0.0)
	sys.modules["Custom.Spaceframe.Modules.AutoFire.Solution"] = S
	sys.modules["Custom.Spaceframe.Modules.AutoFire"].Solution = S
	base.fake_arc_score(AF, lambda pTarget: dScores.get(pTarget.GetName(), 0.0))
	primary = mock_app.WeaponGroup([mock_app.Bank(100.0, 1.0, 1)])
	torps = mock_app.WeaponGroup([mock_app.Tube()])
	torps.torpedo = 1
	ship.groups[App.ShipClass.WG_PRIMARY] = primary
	ship.groups[App.ShipClass.WG_SECONDARY] = torps
	AF.Toggle()
	return App, AF, ship, primary, torps


def test_mode0_no_target_no_fire():
	App, AF, ship, primary, torps = setup(0, [enemy("Bug", 7, 50.0)])
	AF.FireCycle()
	assert primary.starts() == 0 and ship.target is None


def test_mode1_keeps_player_target():
	far = enemy("Far", 8, 90.0)
	App, AF, ship, primary, torps = setup(1, [enemy("Near", 7, 30.0), far])
	ship.target = far
	AF.FireCycle()
	assert ship.target is far and primary.calls[0][1] is far


def test_mode1_nearest_enemy():
	# No target (none chosen, or the last one destroyed): the nearest enemy
	# becomes the player's target.
	near = enemy("Near", 7, 30.0)
	App, AF, ship, primary, torps = setup(1, [enemy("Far", 8, 90.0), near])
	AF.FireCycle()
	assert ship.target is near
	assert primary.calls[0][1] is near


def test_mode1_after_kill():
	near = enemy("Near", 7, 30.0)
	far = enemy("Far", 8, 90.0)
	App, AF, ship, primary, torps = setup(1, [near, far])
	ship.target = near
	AF.FireCycle()
	near.dead = 1
	AF.FireCycle()
	assert ship.target is far


def test_mode1_ignores_dead_and_cloaked():
	dead = enemy("Dead", 7, 10.0)
	dead.dead = 1
	cloaked = enemy("Cloaked", 8, 20.0)
	cloaked.cloaked = 1
	ok = enemy("Ok", 9, 60.0)
	App, AF, ship, primary, torps = setup(1, [dead, cloaked, ok])
	AF.FireCycle()
	assert ship.target is ok


def test_mode1_ignores_friendly():
	# Only the mission's enemy group is looked at.
	App, AF, ship, primary, torps = setup(1, [])
	AF.FireCycle()
	assert ship.target is None and primary.starts() == 0


def test_mode2_best_per_group():
	near = enemy("Near", 7, 30.0)
	far = enemy("Far", 8, 90.0)
	App, AF, ship, primary, torps = setup(2, [near, far], {"Near": 40.0, "Far": 80.0})
	AF.FireCycle()
	assert primary.calls[0][1] is near
	assert torps.calls[0][1] is far
	assert ship.target is None	# the player's selection is left alone


def test_mode2_out_of_range_ignored():
	App, AF, ship, primary, torps = setup(2, [enemy("Far", 8, 150.0)], {"Far": 0.0})
	AF.FireCycle()
	assert primary.starts() == 0 and torps.starts() == 0


def test_mode0_friendly_target_not_fired():
	ally = enemy("Ally", 9, 30.0)
	App, AF, ship, primary, torps = setup(0, [enemy("Bug", 7, 50.0)], friends=[ally])
	ship.target = ally
	AF.FireCycle()
	assert primary.calls == [] and torps.calls == []


def test_mode0_neutral_target_not_fired():
	# Only the mission's enemies are fired at.
	neutral = enemy("Freighter", 9, 30.0)
	mock_app.SHIPS[9] = neutral
	App, AF, ship, primary, torps = setup(0, [enemy("Bug", 7, 50.0)])
	mock_app.SHIPS[9] = neutral
	ship.target = neutral
	AF.FireCycle()
	assert primary.calls == []


def test_mode1_friendly_selected_fires_at_enemy():
	# A friendly selected (to look at it, hail it...) stays selected; Auto
	# Fire carries on with the nearest enemy.
	ally = enemy("Ally", 9, 10.0)
	bug = enemy("Bug", 7, 50.0)
	App, AF, ship, primary, torps = setup(1, [bug], friends=[ally])
	ship.target = ally
	AF.FireCycle()
	assert ship.target is ally
	assert primary.calls[0][1] is bug


def test_mode2_friendly_selected_ignored():
	ally = enemy("Ally", 9, 10.0)
	bug = enemy("Bug", 7, 50.0)
	App, AF, ship, primary, torps = setup(2, [bug], friends=[ally])
	ship.target = ally
	AF.FireCycle()
	assert primary.calls[0][1] is bug


def test_friendly_selected_while_firing_stops():
	bug = enemy("Bug", 7, 50.0)
	ally = enemy("Ally", 9, 30.0)
	App, AF, ship, primary, torps = setup(0, [bug], friends=[ally])
	ship.target = bug
	AF.FireCycle()
	ship.target = ally
	AF.FireCycle()
	assert primary.stops() == 1


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
