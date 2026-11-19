"""SecondaryTarget v0.2 tests: toggle (key, button, StartEnabled) and the
single-fire lift for as long as the toggle is ON."""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mock_app
import test_secondary_cycle as T

LOG = T.LOG


def groups(ship):
	# primary = phaser (original single-fire 1), secondary = pulse (original 0),
	# tertiary = torpedo (original 1; never touched).
	g0 = T.ListGroup([T.ReachBank([20.0, 30.0])], "g0")
	g1 = T.ListGroup([mock_app.Pulse()], "g1", 1)
	g1.pProp.iSingle = 0
	g2 = T.ListGroup([], "g2")
	g2.torpedo = 1
	ship.groups[0] = g0
	ship.groups[1] = g1
	ship.groups[2] = g2
	return g0, g1, g2


def started(bStart=1, iTech=-1, **kw):
	kw["StartEnabled"] = bStart
	App, ST, core, ship = T.setup(iTech, **kw)
	main, b, c, pSys = T.scene(core, ship)
	g0, g1, g2 = groups(ship)
	ST.Start(core)
	return App, ST, core, ship, (main, b, c), (g0, g1, g2)


def key(App, iChar, iState=None):
	if iState == None:
		iState = App.TGKeyboardEvent.KS_KEYDOWN
	return mock_app.KeyEvent(iChar, iState)


def test_start_enabled_lifts_masked_groups_and_records_originals():
	App, ST, core, ship, tg, gs = started(1)
	assert ST.IsEnabled() == 1
	assert gs[0].pProp.iSingle == 0 and gs[1].pProp.iSingle == 0
	assert gs[2].pProp.iSingle == 1
	# only the phaser group is lifted and recorded; the pulse group is never touched
	assert ST.g_dLifted == {1: {0: 1}}
	assert [t for t in T.calls("single") if t[1] == "g1"] == []
	ST.Stop()


def test_start_enabled_zero_lifts_nothing_until_toggled():
	App, ST, core, ship, tg, gs = started(0)
	ST.Cycle()
	assert ST.IsEnabled() == 0
	assert T.calls("single") == [] and ST.g_dLifted == {}
	assert gs[0].pProp.iSingle == 1
	ST.Toggle()
	assert gs[0].pProp.iSingle == 0
	assert ST.g_dLifted == {1: {0: 1}}
	ST.Stop()


def test_toggle_on_respects_mask():
	# mask 4 = pulse only: pulse is never lifted, phasers are masked out
	App, ST, core, ship, tg, gs = started(0, iTech=4)
	ST.Toggle()
	assert ST.g_dLifted == {}
	assert T.calls("single") == []
	assert gs[0].pProp.iSingle == 1
	ST.Stop()


def test_pulse_single_fire_never_touched():
	# pulse original 0 (multi) and original 1 (single): both stay as they are
	for iOrig in (0, 1):
		App, ST, core, ship, tg, gs = started(0)
		gs[1].pProp.iSingle = iOrig
		del LOG[:]
		ST.Toggle()
		ST.Cycle()
		assert gs[1].pProp.iSingle == iOrig
		assert [t for t in T.calls("single") if t[1] == "g1"] == []
		assert ST.g_dLifted == {1: {0: 1}}
		ST.Toggle()
		assert gs[1].pProp.iSingle == iOrig
		assert [t for t in T.calls("single") if t[1] == "g1"] == []
		assert ST.g_dLifted == {}
		ST.Stop()


def test_toggle_off_restores_and_removes_secondaries():
	App, ST, core, ship, tg, gs = started(1)
	main, b, c = tg
	gs[0].Press(main)
	ST.Cycle()
	assert gs[0].ids() == [2, 3, 4]
	ST.Toggle()
	assert ST.IsEnabled() == 0
	assert gs[0].ids() == [2]
	assert gs[0].pProp.iSingle == 1 and gs[1].pProp.iSingle == 0
	assert ST.g_dLifted == {} and ST.g_dAdded == {}
	assert ST.g_pTimer == None
	ST.Stop()


def test_double_on_keeps_first_original():
	App, ST, core, ship, tg, gs = started(0)
	ST.SetEnabled(1)
	ST.SetEnabled(1)
	ST.Cycle()
	assert ST.g_dLifted == {1: {0: 1}}
	assert T.calls("single") == [("single", "g0", 0)]
	ST.SetEnabled(0)
	ST.SetEnabled(0)
	assert gs[0].pProp.iSingle == 1 and gs[1].pProp.iSingle == 0
	ST.Stop()


def test_ship_change_restores_old_only_if_live_and_lifts_new():
	App, ST, core, ship, tg, gs = started(1)
	other = mock_app.Ship("Galaxy", 7)
	o0 = T.ListGroup([T.ReachBank([20.0])], "o0")
	other.groups[0] = o0
	App._player[0] = other
	ST.Cycle()
	assert gs[0].pProp.iSingle == 1
	assert o0.pProp.iSingle == 0
	assert ST.g_dLifted == {7: {0: 1}}
	# the new ship is gone (not live): nothing is asked of it, just forgotten
	del mock_app.SHIPS[7]
	App._player[0] = ship
	del LOG[:]
	ST.Cycle()
	assert o0.pProp.iSingle == 0
	assert [t for t in LOG if t[1] == "o0"] == []
	assert 7 not in ST.g_dLifted
	ST.Stop()


def test_ship_dead_restores_if_live():
	App, ST, core, ship, tg, gs = started(1)
	ship.dead = 1
	ST.Cycle()
	assert gs[0].pProp.iSingle == 1
	assert ST.g_dLifted == {}
	ST.Stop()


def test_tech_lost_restores():
	App, ST, core, ship, tg, gs = started(1)
	core.techs["Galaxy"] = {"SecondaryTarget": 0}
	ST.Cycle()
	assert gs[0].pProp.iSingle == 1
	assert ST.g_dLifted == {}
	ST.Stop()


def test_stop_touches_no_ship_and_forgets():
	App, ST, core, ship, tg, gs = started(1)
	del LOG[:]
	del mock_app.TOUCHED[:]
	ST.Stop()
	assert LOG == [] and mock_app.TOUCHED == []
	assert ST.g_dLifted == {} and ST.g_dAdded == {}
	assert gs[0].pProp.iSingle == 0	# left as it is: the ships are going away


def test_second_start_no_double_lift_or_handlers():
	App, ST, core, ship, tg, gs = started(1)
	ST.Start(core)
	assert len(App.g_kEventManager.handlers) == 3
	assert len(App._tcw.menu.children) == 1
	# the second Start saw the lifted value (0) as the "original": Stop forgot
	# the first record, so nothing is restored by it either way
	assert ST.g_dLifted == {1: {0: 0}}
	ST.Stop()


def test_key_toggles_and_is_kept_from_game():
	App, ST, core, ship, tg, gs = started(0)
	ev = key(App, 106)
	ST.OnKeyboard(App._top, ev)
	assert ST.IsEnabled() == 1 and ev.handled == 1 and ev.passed == 0
	ST.OnKeyboard(App._top, key(App, 74))	# Shift+J or Caps Lock
	assert ST.IsEnabled() == 0
	assert gs[0].pProp.iSingle == 1
	ev = key(App, 107)
	ST.OnKeyboard(App._top, ev)
	assert ev.passed == 1 and ev.handled == 0
	ev = key(App, 106, App.TGKeyboardEvent.KS_KEYUP)
	ST.OnKeyboard(App._top, ev)
	assert ev.passed == 1 and ST.IsEnabled() == 0
	ST.Stop()


def test_key_without_tech_does_nothing():
	App, ST, core, ship, tg, gs = started(0, iTech=None)
	ev = key(App, 106)
	ST.OnKeyboard(App._top, ev)
	assert ev.passed == 1 and ev.handled == 0
	assert ST.IsEnabled() == 0 and ST.g_iOn == 0
	assert T.calls("single") == [] and ST.g_dLifted == {}
	ST.Stop()


def test_button_toggles_and_shows_state():
	App, ST, core, ship, tg, gs = started(0)
	menu = App._tcw.menu
	button = menu.children[0]
	assert getattr(button.sName, "s", button.sName) == "Secondary Target" and button.IsChosen() == 0
	ST.OnMenuButton(menu, mock_app.Event(button.pEvent.eType, 0, menu))
	assert ST.IsEnabled() == 1 and button.IsChosen() == 1
	assert gs[0].pProp.iSingle == 0
	ST.Toggle()
	assert button.IsChosen() == 0 and gs[0].pProp.iSingle == 1
	ST.Stop()


def test_start_enabled_button_chosen():
	App, ST, core, ship, tg, gs = started(1)
	assert App._tcw.menu.children[0].IsChosen() == 1
	ST.Stop()


def test_start_enabled_without_tech_lifts_after_ship_change():
	App, ST, core, ship, tg, gs = started(1, iTech=None)
	assert ST.IsEnabled() == 0 and ST.g_dLifted == {}
	other = mock_app.Ship("Galaxy", 7)
	core.techs["Galaxy"] = {"SecondaryTarget": -1}
	o0 = T.ListGroup([T.ReachBank([20.0])], "o0")
	other.groups[0] = o0
	App._player[0] = other
	ST.Cycle()
	assert o0.pProp.iSingle == 0 and ST.g_dLifted == {7: {0: 1}}
	ST.Stop()


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
