"""Task 1 tests: state, toggle key, menu button, manual fire flags, HUD title."""
import builtins
import sys
import types
sys.path.insert(0, "/mnt/user-data/outputs/Spaceframe/tests")
import mock_app

builtins.reload = lambda m: m
builtins.apply = lambda f, a: f(*a)


def make_config(**kw):
	c = types.ModuleType("Custom.Spaceframe.Modules.AutoFire.Config")
	c.ToggleKey = "L"
	c.StartEnabled = 0
	c.FireInterval = 0.1
	for k in kw:
		setattr(c, k, kw[k])
	return c


def register_packages(cfg):
	names = ["Custom", "Custom.Spaceframe", "Custom.Spaceframe.Modules",
		"Custom.Spaceframe.Modules.AutoFire"]
	for n in names:
		if n not in sys.modules:
			sys.modules[n] = types.ModuleType(n)
	sys.modules["Custom"].Spaceframe = sys.modules["Custom.Spaceframe"]
	sys.modules["Custom.Spaceframe"].Modules = sys.modules["Custom.Spaceframe.Modules"]
	sys.modules["Custom.Spaceframe.Modules"].AutoFire = sys.modules["Custom.Spaceframe.Modules.AutoFire"]
	sys.modules["Custom.Spaceframe.Modules.AutoFire.Config"] = cfg
	sys.modules["Custom.Spaceframe.Modules.AutoFire"].Config = cfg


def setup(tech=1, **kw):
	App = mock_app.make_app()
	mock_app.install(App)
	register_packages(make_config(**kw))
	AF = mock_app.load_module("Modules/AutoFire/AutoFire.py", "Custom.Spaceframe.Modules.AutoFire.AutoFire")
	core = mock_app.Core()
	ship = mock_app.Ship("Galaxy", 1)
	if tech:
		core.techs["Galaxy"] = {"AutoFire": -1}
	App._player[0] = ship
	AF.Start(core)
	return App, AF, core, ship


def test_starts_disabled():
	App, AF, core, ship = setup()
	assert AF.IsEnabled() == 0


def test_start_enabled_config():
	App, AF, core, ship = setup(StartEnabled=1)
	assert AF.IsEnabled() == 1


def test_toggle_on_off():
	App, AF, core, ship = setup()
	AF.Toggle()
	assert AF.IsEnabled() == 1
	AF.Toggle()
	assert AF.IsEnabled() == 0


def test_toggle_without_tech():
	App, AF, core, ship = setup(tech=0)
	AF.Toggle()
	assert AF.IsEnabled() == 0


def test_player_ship_changed():
	App, AF, core, ship = setup()
	AF.Toggle()
	other = mock_app.Ship("Galaxy", 2)
	App._player[0] = other
	assert AF.IsEnabled() == 0


def key(App, iChar, iState=None):
	if iState == None:
		iState = App.TGKeyboardEvent.KS_KEYDOWN
	return mock_app.KeyEvent(iChar, iState)


def test_key_handler_on_top_window():
	# Like the game's BridgeUtils.ModalKeyboardHandler: the top window sees
	# every key, whatever has the focus (a clicked menu, for instance).
	App, AF, core, ship = setup()
	assert (App.ET_KEYBOARD, AF.KEY_HANDLER) in App._top.handlers


def test_key_l_toggles():
	App, AF, core, ship = setup()
	ev = key(App, 108)
	AF.OnKeyboard(App._top, ev)
	assert AF.IsEnabled() == 1 and ev.handled == 1 and ev.passed == 0
	AF.OnKeyboard(App._top, key(App, 76))	# Shift+L or Caps Lock
	assert AF.IsEnabled() == 0


def test_other_keys_pass_on():
	App, AF, core, ship = setup()
	ev = key(App, 107)
	AF.OnKeyboard(App._top, ev)
	assert AF.IsEnabled() == 0 and ev.passed == 1 and ev.handled == 0
	ev = key(App, 108, App.TGKeyboardEvent.KS_KEYUP)
	AF.OnKeyboard(App._top, ev)
	assert AF.IsEnabled() == 0 and ev.passed == 1


def test_key_without_tech_passes_on():
	# A ship without Auto Fire: L keeps whatever meaning the game gives it.
	App, AF, core, ship = setup()
	core.techs["Galaxy"] = {}
	ev = key(App, 108)
	AF.OnKeyboard(App._top, ev)
	assert ev.passed == 1 and ev.handled == 0


def test_menu_button_created_and_toggles():
	App, AF, core, ship = setup()
	menu = App._tcw.menu
	assert len(menu.children) == 1
	button = menu.children[0]
	AF.OnMenuButton(menu, mock_app.Event(button.pEvent.eType, 0, menu))
	assert AF.IsEnabled() == 1
	assert button.IsChosen() == 1
	AF.Toggle()
	assert button.IsChosen() == 0


def test_restart_no_duplicates():
	App, AF, core, ship = setup()
	AF.Toggle()
	AF.Stop()
	assert len(App._tcw.menu.children) == 0
	assert App._top.handlers == []
	AF.Start(core)
	assert len(App._tcw.menu.children) == 1
	assert App._top.handlers == [(App.ET_KEYBOARD, AF.KEY_HANDLER)]
	assert AF.IsEnabled() == 0
	assert App.g_kEventManager.count(App.ET_INPUT_FIRE_PRIMARY) == 1


def test_manual_flags():
	App, AF, core, ship = setup()
	AF.OnManualFire(None, mock_app.Event(App.ET_INPUT_FIRE_SECONDARY, 1))
	assert AF.g_dManual[App.ShipClass.WG_SECONDARY] == 1
	AF.OnManualFire(None, mock_app.Event(App.ET_INPUT_FIRE_SECONDARY, 0))
	assert AF.g_dManual[App.ShipClass.WG_SECONDARY] == 0


def test_hud_auto_tag():
	App, AF, core, ship = setup()
	core.modules["AutoFire"] = AF
	cfg = types.ModuleType("Custom.Spaceframe.Modules.StatusHUD.Config")
	sys.modules["Custom.Spaceframe.Modules.StatusHUD"] = types.ModuleType("Custom.Spaceframe.Modules.StatusHUD")
	sys.modules["Custom.Spaceframe.Modules"].StatusHUD = sys.modules["Custom.Spaceframe.Modules.StatusHUD"]
	sys.modules["Custom.Spaceframe.Modules.StatusHUD.Config"] = cfg
	sys.modules["Custom.Spaceframe.Modules.StatusHUD"].Config = cfg
	HUD = mock_app.load_module("Modules/StatusHUD/StatusHUD.py", "Custom.Spaceframe.Modules.StatusHUD.StatusHUD")
	HUD.g_pCore = core
	pane = App._tcw.weapons_display
	HUD.UpdateAutoFireTag()
	assert [c for c in pane.children if c.visible] == []
	AF.Toggle()
	HUD.UpdateAutoFireTag()
	shown = [c for c in pane.children if c.visible]
	assert len(shown) == 1 and shown[0].s == "AUTO"
	tag = shown[0]
	HUD.UpdateAutoFireTag()
	HUD.UpdateAutoFireTag()
	assert pane.children == [tag] and tag.visible == 1
	assert pane.layouts == 1	# redrawn once when shown, not every cycle
	assert abs(tag.left + tag.GetWidth() - 0.18) < 0.01 and tag.top < 0.01
	g = tag.color.rgba
	assert g[1] > g[0] and g[1] > g[2]
	AF.Toggle()
	HUD.UpdateAutoFireTag()
	HUD.UpdateAutoFireTag()
	assert tag.visible == 0
	assert pane.layouts == 2	# and once when hidden
	AF.Toggle()
	HUD.UpdateAutoFireTag()
	assert len(pane.children) == 1
	HUD.Stop()
	assert pane.children == []


def hud_setup():
	App, AF, core, ship = setup()
	core.modules["AutoFire"] = AF
	cfg = types.ModuleType("Custom.Spaceframe.Modules.StatusHUD.Config")
	sys.modules["Custom.Spaceframe.Modules.StatusHUD"] = types.ModuleType("Custom.Spaceframe.Modules.StatusHUD")
	sys.modules["Custom.Spaceframe.Modules"].StatusHUD = sys.modules["Custom.Spaceframe.Modules.StatusHUD"]
	sys.modules["Custom.Spaceframe.Modules.StatusHUD.Config"] = cfg
	sys.modules["Custom.Spaceframe.Modules.StatusHUD"].Config = cfg
	HUD = mock_app.load_module("Modules/StatusHUD/StatusHUD.py", "Custom.Spaceframe.Modules.StatusHUD.StatusHUD")
	HUD.g_pCore = core
	return App, AF, core, ship, HUD


def test_hud_tag_panel_rebuilt_then_stop():
	# Battle ends with Auto Fire on: the game rebuilds the weapons panel
	# (destroying the text), then Spaceframe stops. Must not touch the text.
	App, AF, core, ship, HUD = hud_setup()
	pane = App._tcw.weapons_display
	AF.Toggle()
	HUD.UpdateAutoFireTag()
	pane.KillChildren()
	HUD.Stop()
	assert mock_app.TOUCHED == []
	assert HUD.g_pAutoText is None


def test_hud_tag_panel_rebuilt_in_battle():
	# Panel rebuilt mid-battle: the tag is made again, the old one untouched.
	App, AF, core, ship, HUD = hud_setup()
	pane = App._tcw.weapons_display
	AF.Toggle()
	HUD.UpdateAutoFireTag()
	pane.KillChildren()
	HUD.UpdateAutoFireTag()
	assert len(pane.children) == 1 and pane.children[0].s == "AUTO"
	assert pane.children[0].visible == 1
	assert mock_app.TOUCHED == []


def test_hud_tag_without_pointer():
	# If the game's wrappers have no "this", the tag is kept while the
	# player's ship stays the same, and made again when it changes.
	App, AF, core, ship, HUD = hud_setup()
	pane = App._tcw.weapons_display
	AF.Toggle()
	HUD.GetPointer = lambda p: ""
	HUD.UpdateAutoFireTag()
	HUD.UpdateAutoFireTag()
	HUD.UpdateAutoFireTag()
	assert len(pane.children) == 1 and pane.layouts == 1
	pane.KillChildren()
	App._player[0] = mock_app.Ship("Galaxy", 3)
	core.techs["Galaxy"] = {"AutoFire": -1}
	AF.g_iShipID = 3
	HUD.UpdateAutoFireTag()
	assert mock_app.TOUCHED == []
	assert len(pane.children) == 1


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
