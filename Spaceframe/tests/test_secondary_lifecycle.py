"""Task 1 tests: SecondaryTarget skeleton - config, mask, handlers, timer."""
import builtins
import os
import sys
import types
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mock_app

builtins.reload = lambda m: m
builtins.apply = lambda f, a: f(*a)

PKG = "Custom.Spaceframe.Modules.SecondaryTarget"


def make_config(**kw):
	c = types.ModuleType(PKG + ".Config")
	c.Weapons = 7
	c.Interval = 0.2
	c.MaxCandidates = 4
	c.SecondaryRange = 100
	c.SecondaryTorpedoMinSolution = 70
	c.Debug = 0
	c.ToggleKey = "J"
	c.StartEnabled = 1
	for k in kw:
		setattr(c, k, kw[k])
	return c


def register_packages(cfg):
	names = ["Custom", "Custom.Spaceframe", "Custom.Spaceframe.Modules", PKG]
	for n in names:
		if n not in sys.modules:
			sys.modules[n] = types.ModuleType(n)
	sys.modules["Custom"].Spaceframe = sys.modules["Custom.Spaceframe"]
	sys.modules["Custom.Spaceframe"].Modules = sys.modules["Custom.Spaceframe.Modules"]
	sys.modules["Custom.Spaceframe.Modules"].SecondaryTarget = sys.modules[PKG]
	sys.modules[PKG + ".Config"] = cfg
	sys.modules[PKG].Config = cfg


def setup(tech=-1, **kw):
	App = mock_app.make_app()
	mock_app.install(App)
	register_packages(make_config(**kw))
	ST = mock_app.load_module("Modules/SecondaryTarget/SecondaryTarget.py", PKG + ".SecondaryTarget")
	core = mock_app.Core()
	ship = mock_app.Ship("Galaxy", 1)
	if tech != None:
		core.techs["Galaxy"] = {"SecondaryTarget": tech}
	App._player[0] = ship
	return App, ST, core, ship


def active_timers():
	n = 0
	for p in mock_app.Process.live:
		if p.inst != None and p.inst.bActive:
			n = n + 1
	return n


def test_start_twice_then_stop_registers_once():
	App, ST, core, ship = setup()
	ST.Start(core)
	ST.Start(core)
	assert len(App.g_kEventManager.handlers) == 3
	assert active_timers() == 1
	assert App._top.handlers == [(App.ET_KEYBOARD, ST.KEY_HANDLER)]
	assert len(App._tcw.menu.children) == 1
	assert len(App._tcw.menu.handlers) == 1
	ST.Stop()
	assert len(App.g_kEventManager.handlers) == 0
	assert active_timers() == 0
	assert App._top.handlers == []
	assert App._tcw.menu.children == []
	assert App._tcw.menu.handlers == []
	assert ST.g_iOn == 0 and ST.g_pButton == None and ST.g_iKey == None


def test_stop_touches_no_ship():
	App, ST, core, ship = setup()
	ST.Start(core)
	del mock_app.TOUCHED[:]
	ST.Stop()
	assert mock_app.TOUCHED == []


def test_mask_def_uses_config():
	App, ST, core, ship = setup(tech=-1)
	ST.Start(core)
	assert ST.GetMask(ship) == 7
	core.techs["Galaxy"] = {"SecondaryTarget": 0}
	assert ST.GetMask(ship) == 0
	core.techs["Galaxy"] = {"SecondaryTarget": 5}
	assert ST.GetMask(ship) == 5
	ST.Stop()


def test_mask_def_follows_config_weapons():
	App, ST, core, ship = setup(tech=-1, Weapons=1)
	ST.Start(core)
	assert ST.GetMask(ship) == 1
	ST.Stop()


def test_start_enabled_zero_no_timer_until_toggled():
	App, ST, core, ship = setup(StartEnabled=0)
	ST.Start(core)
	assert active_timers() == 0
	assert ST.IsEnabled() == 0
	assert ST.g_dLifted == {}
	ST.Toggle()
	assert ST.IsEnabled() == 1
	assert active_timers() == 1
	ST.Toggle()
	assert active_timers() == 0
	ST.Stop()


def test_config_read_at_start():
	App, ST, core, ship = setup(Interval=0.5, MaxCandidates=2)
	ST.Start(core)
	assert ST.g_fInterval == 0.5 and ST.g_iMaxCandidates == 2
	assert mock_app.Process.live[0].delay == 0.5
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
