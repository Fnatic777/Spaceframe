"""MVShields characterization tests: they pin the CURRENT behavior."""
import os
import sys
import types
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mock_app
import fake_ships
from fake_ships import near, FakeShields, FakeShip

MOD = "Custom.Spaceframe.Modules.MVShields.MVShields"


def setup(vTech=-1, sShip="Galaxy", bMode=1, **kw):
	"""bMode = 0 leaves Mode out of the config (legacy config)."""
	App = mock_app.make_app()
	mock_app.install(App)
	d = {"DefaultEfficiency": 100}
	if bMode:
		d["Mode"] = 3
	d.update(kw)
	fake_ships.register_config("MVShields", **d)
	MV = mock_app.load_module("Modules/MVShields/MVShields.py", MOD)
	core = mock_app.Core()
	if vTech != None:
		core.techs[sShip] = {"MVShields": vTech}
	MV.Start(core)
	return App, MV, core


def ship_with(lCur, lMax=None, iID=1, sName="Galaxy", **kw):
	if lMax == None:
		lMax = [100.0] * 6
	return FakeShip(sName, iID, 1000.0, None, FakeShields(lMax, list(lCur), **kw))


# --- EqualizeShip -----------------------------------------------------------------
def test_equalize_proportional_to_max_and_conserves_total():
	App, MV, core = setup()
	lMax = [100.0, 100.0, 100.0, 100.0, 50.0, 50.0]
	ship = ship_with([100.0, 0.0, 0.0, 0.0, 0.0, 0.0], lMax)
	MV.EqualizeShip(ship, 100)
	lCur = ship.shields.lCur
	for i in range(6):
		assert near(lCur[i], 100.0 * lMax[i] / 500.0), (i, lCur[i])
	assert near(sum(lCur), 100.0)


def test_equalize_efficiency_moves_part_way():
	App, MV, core = setup()
	ship = ship_with([100.0, 0.0, 0.0, 0.0, 0.0, 0.0])
	MV.EqualizeShip(ship, 50)
	lCur = ship.shields.lCur
	assert near(lCur[0], 100.0 + (100.0 / 6 - 100.0) * 0.5)
	assert near(lCur[1], 100.0 / 6 * 0.5)
	assert near(sum(lCur), 100.0)		# still conserved


def test_equalize_caps_facings_at_max():
	# Facings above their max: each target is above the max too, so they are
	# clamped and the total shrinks (the total is only conserved below the cap).
	App, MV, core = setup()
	ship = ship_with([200.0] * 6)
	MV.EqualizeShip(ship, 100)
	assert ship.shields.lCur == [100.0] * 6


def test_equalize_skipped_when_off_or_disabled_or_missing():
	App, MV, core = setup()
	ship = ship_with([100.0, 0.0, 0.0, 0.0, 0.0, 0.0], bOn=0)
	MV.EqualizeShip(ship, 100)
	assert ship.shields.writes == []
	ship = ship_with([100.0, 0.0, 0.0, 0.0, 0.0, 0.0], bDisabled=1)
	MV.EqualizeShip(ship, 100)
	assert ship.shields.writes == []
	ship = FakeShip("Galaxy", 1)		# no shields at all
	MV.EqualizeShip(ship, 100)


def test_equalize_tiny_changes_not_written():
	App, MV, core = setup()
	ship = ship_with([10.0] * 6)
	MV.EqualizeShip(ship, 100)
	assert ship.shields.writes == []
	ship = ship_with([10.005, 9.995, 10.0, 10.0, 10.0, 10.0])
	MV.EqualizeShip(ship, 100)
	assert ship.shields.writes == []		# 0.005 < 0.01
	ship = ship_with([10.02, 9.98, 10.0, 10.0, 10.0, 10.0])
	MV.EqualizeShip(ship, 100)
	assert sorted([w[0] for w in ship.shields.writes]) == [0, 1]	# 0.02 > 0.01


def test_equalize_zero_total_max_and_negative_values():
	App, MV, core = setup()
	ship = ship_with([5.0] * 6, [0.0] * 6)
	MV.EqualizeShip(ship, 100)
	assert ship.shields.writes == []
	ship = ship_with([-50.0, 60.0, 0.0, 0.0, 0.0, 0.0])		# negative charge counts as 0
	MV.EqualizeShip(ship, 100)
	assert near(sum(ship.shields.lCur), 60.0)
	assert near(ship.shields.lCur[0], 10.0)


# --- Mode ----------------------------------------------------------------------------
def run_modes(iMode):
	App, MV, core = setup(Mode=iMode)
	ship = ship_with([100.0, 0.0, 0.0, 0.0, 0.0, 0.0])
	MV.Tick([ship])
	iTick = len(ship.shields.writes)
	ship = ship_with([100.0, 0.0, 0.0, 0.0, 0.0, 0.0])
	MV.WeaponHit(ship, None)
	return iTick > 0, len(ship.shields.writes) > 0


def test_mode_gating():
	assert run_modes(0) == (False, False)
	assert run_modes(1) == (False, True)
	assert run_modes(2) == (True, False)
	assert run_modes(3) == (True, True)


def test_mode_invalid_values_fall_back_to_both():
	for v in (5, -1, "x", None):
		App, MV, core = setup(Mode=v)
		assert MV.g_iMode == 3, v
	App, MV, core = setup(Mode="2")
	assert MV.g_iMode == 2


def test_legacy_react_on_hit():
	App, MV, core = setup(bMode=0, ReactOnHit=1)
	assert MV.g_iMode == 3
	App, MV, core = setup(bMode=0, ReactOnHit=0)
	assert MV.g_iMode == 2
	App, MV, core = setup(bMode=0)		# neither Mode nor ReactOnHit
	assert MV.g_iMode == 3


def test_mode_wins_over_react_on_hit():
	App, MV, core = setup(Mode=1, ReactOnHit=0)
	assert MV.g_iMode == 1


def test_weaponhit_skips_dead_and_dying():
	App, MV, core = setup()
	ship = ship_with([100.0, 0.0, 0.0, 0.0, 0.0, 0.0])
	ship.dead = 1
	MV.WeaponHit(ship, None)
	ship.dead = 0
	ship.dying = 1
	MV.WeaponHit(ship, None)
	assert ship.shields.writes == []
	ship.dying = 0
	MV.WeaponHit(ship, None)
	assert ship.shields.writes != []


def test_tick_only_ships_with_mv():
	App, MV, core = setup()
	core.techs["Defiant"] = {}
	mv = ship_with([100.0, 0.0, 0.0, 0.0, 0.0, 0.0], iID=1)
	plain = ship_with([100.0, 0.0, 0.0, 0.0, 0.0, 0.0], iID=2, sName="Defiant")
	MV.Tick([mv, plain])
	assert mv.shields.writes != [] and plain.shields.writes == []


# --- GetMVValue ------------------------------------------------------------------------
def test_value_def_uses_default_efficiency():
	App, MV, core = setup(DefaultEfficiency=70)
	assert MV.GetMVValue(ship_with([0.0] * 6)) == 70


def test_value_explicit_clamp_and_absent():
	App, MV, core = setup(vTech=40)
	assert MV.GetMVValue(ship_with([0.0] * 6)) == 40
	App, MV, core = setup(vTech=150)
	assert MV.GetMVValue(ship_with([0.0] * 6)) == 100
	App, MV, core = setup(vTech=-5)
	assert MV.GetMVValue(ship_with([0.0] * 6)) == 0
	App, MV, core = setup(DefaultEfficiency=250)
	assert MV.GetMVValue(ship_with([0.0] * 6)) == 100
	App, MV, core = setup(DefaultEfficiency=-3)
	assert MV.GetMVValue(ship_with([0.0] * 6)) == 0
	App, MV, core = setup(vTech=None)
	assert MV.GetMVValue(ship_with([0.0] * 6)) == 0


def test_value_float_is_truncated():
	App, MV, core = setup(vTech=59.9)
	assert MV.GetMVValue(ship_with([0.0] * 6)) == 59


def test_value_cached_until_stop():
	App, MV, core = setup(vTech=40)
	ship = ship_with([0.0] * 6)
	assert MV.GetMVValue(ship) == 40
	core.techs["Galaxy"] = {"MVShields": 10}
	assert MV.GetMVValue(ship) == 40
	MV.Stop()
	assert MV.GetMVValue(ship) == 10


def test_value_legacy_config_ships():
	App, MV, core = setup(vTech=None, Ships={"Galaxy": 55})
	assert MV.GetMVValue(ship_with([0.0] * 6)) == 55


def test_value_zero_overridden_by_legacy_list():
	# FIXED: an explicit 0 from Ships.py ("switch off") stays 0; the legacy
	# Config.Ships list only applies to ships with no entry at all.
	App, MV, core = setup(vTech=0, Ships={"Galaxy": 55})
	assert MV.GetMVValue(ship_with([0.0] * 6)) == 0


def run():
	return fake_ships.run(globals())


if __name__ == "__main__":
	sys.exit(run())
