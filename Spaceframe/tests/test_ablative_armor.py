"""AblativeArmor characterization tests: they pin the CURRENT behavior.

Numbers used everywhere unless stated: hull 1000, Phasers 100, armor 50% of
hull = 500, hull cost 1.0, subsystem cost 0.5, bleed 50/50, complexity 2.0.
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mock_app
import fake_ships
from fake_ships import near

MOD = "Custom.Spaceframe.Modules.AblativeArmor.AblativeArmor"


def setup(iCreate=0, vTech=-1, sShip="Galaxy", iID=1, **kw):
	App = mock_app.make_app()
	mock_app.install(App)
	fake_ships.install_armor_api(App)
	d = {"DefaultArmor": 50, "ArmorComplexity": 200, "BleedStart": 50, "BleedMax": 50,
		"SubsystemDamageCost": 50, "CreateSubsystem": iCreate, "Targetable": 1}
	d.update(kw)
	fake_ships.register_config("AblativeArmor", **d)
	AA = mock_app.load_module("Modules/AblativeArmor/AblativeArmor.py", MOD)
	core = mock_app.Core()
	if vTech != None:
		core.techs[sShip] = {"AblativeArmor": vTech}
	AA.Start(core)
	ship = fake_ships.FakeShip(sShip, iID, 1000.0, [("Phasers", 100.0)])
	return App, AA, core, ship


class Event:
	def __init__(self, bHull):
		self.bHull = bHull

	def IsHullHit(self):
		return self.bHull


# --- GetBleed -------------------------------------------------------------
def test_bleed_curve():
	App, AA, core, ship = setup()
	assert AA.GetBleed(500.0, 500.0) == 0.0
	assert AA.GetBleed(250.0, 500.0) == 0.0		# exactly BleedStart: still nothing
	assert near(AA.GetBleed(249.0, 500.0), 0.5 * (1.0 - 0.498 / 0.5))
	assert near(AA.GetBleed(125.0, 500.0), 0.25)
	assert near(AA.GetBleed(0.0, 500.0), 0.5)


def test_bleed_guards():
	App, AA, core, ship = setup()
	assert AA.GetBleed(10.0, 0.0) == 0.0		# no capacity
	AA.g_fBleedMax = 0.0
	assert AA.GetBleed(0.0, 500.0) == 0.0
	AA.g_fBleedMax = 0.5
	AA.g_fBleedStart = 0.0
	assert AA.GetBleed(0.0, 500.0) == 0.0


def test_start_config_clamps():
	App, AA, core, ship = setup(BleedMax=150, ArmorComplexity=0)
	assert AA.g_fBleedMax == 1.0
	assert AA.g_fArmorComplexity == 0.01
	App, AA, core, ship = setup(BleedStart=30, SubsystemDamageCost=25)
	assert near(AA.g_fBleedStart, 0.3) and near(AA.g_fSubsystemCost, 0.25)


# --- records ----------------------------------------------------------------
def test_internal_record():
	App, AA, core, ship = setup()
	rec = AA.GetRecord(ship)
	assert rec[AA.REC_ARMOR] == 500.0 and rec[AA.REC_MAX] == 500.0
	assert rec[AA.REC_SUB] == None and rec[AA.REC_LAST] == None
	assert rec[AA.REC_COMPLEXITY] == 2.0		# hull 1.0 * ArmorComplexity 2.0
	assert len(rec[AA.REC_ENTRIES]) == 2
	assert rec[AA.REC_ENTRIES][0][2] == 1.0		# hull cost
	assert rec[AA.REC_ENTRIES][1][2] == 0.5		# subsystem cost
	assert len(ship.Armors()) == 0


def test_subsystem_record():
	App, AA, core, ship = setup(iCreate=1)
	rec = AA.GetRecord(ship)
	pArmor = rec[AA.REC_SUB]
	assert pArmor != None and pArmor.sName == "Ablative Armor"
	assert pArmor.fMax == 500.0 and pArmor.fCond == 500.0
	assert ship.Armors() == [pArmor]
	assert ship.repair.added == [pArmor]
	assert len(rec[AA.REC_ENTRIES]) == 2		# the armor itself is not tracked
	assert AA.GetArmor(rec) == 499.0			# MIN_ARMOR is subtracted


def test_no_armor_ship_record_is_none():
	App, AA, core, ship = setup(vTech=None)
	assert AA.GetRecord(ship) == None
	assert AA.g_dShips[1] == None


# --- GetArmorPercent ----------------------------------------------------------
def test_percent_def_uses_default_armor():
	App, AA, core, ship = setup(DefaultArmor=40)
	assert AA.GetArmorPercent(ship) == 40.0


def test_percent_explicit_and_absent():
	App, AA, core, ship = setup(vTech=80)
	assert AA.GetArmorPercent(ship) == 80.0
	App, AA, core, ship = setup(vTech=None)
	assert AA.GetArmorPercent(ship) == 0.0


def test_percent_is_cached_per_ship_file():
	App, AA, core, ship = setup(vTech=80)
	assert AA.GetArmorPercent(ship) == 80.0
	core.techs["Galaxy"] = {"AblativeArmor": 10}
	assert AA.GetArmorPercent(ship) == 80.0		# cached until Start/Stop
	AA.Stop()
	assert AA.GetArmorPercent(ship) == 10.0


def test_percent_legacy_config_ships():
	App, AA, core, ship = setup(vTech=None, Ships={"Galaxy": 30})
	assert AA.GetArmorPercent(ship) == 30.0


def test_percent_zero_overridden_by_legacy_list():
	# FIXED: an explicit 0 from Ships.py ("switch off") stays 0; the legacy
	# Config.Ships list only applies to ships with no entry at all.
	App, AA, core, ship = setup(vTech=0, Ships={"Galaxy": 30})
	assert AA.GetArmorPercent(ship) == 0.0


def test_percent_negative_becomes_zero():
	App, AA, core, ship = setup(vTech=-5)
	assert AA.GetArmorPercent(ship) == 0.0


# --- Absorb -------------------------------------------------------------------
def test_absorb_hull_loss_costs_one_to_one():
	App, AA, core, ship = setup()
	rec = AA.GetRecord(ship)
	ship.hull.fCond = 900.0
	AA.Absorb(ship, rec)
	assert ship.hull.fCond == 1000.0
	assert near(rec[AA.REC_ARMOR], 400.0)


def test_absorb_subsystem_loss_costs_subsystem_factor():
	App, AA, core, ship = setup()
	rec = AA.GetRecord(ship)
	ship.Sub("Phasers").fCond = 80.0
	AA.Absorb(ship, rec)
	assert ship.Sub("Phasers").fCond == 100.0
	assert near(rec[AA.REC_ARMOR], 490.0)		# 20 * 0.5


def test_absorb_mixed_losses_add_up():
	App, AA, core, ship = setup()
	rec = AA.GetRecord(ship)
	ship.hull.fCond = 900.0
	ship.Sub("Phasers").fCond = 80.0
	AA.Absorb(ship, rec)
	assert ship.hull.fCond == 1000.0 and ship.Sub("Phasers").fCond == 100.0
	assert near(rec[AA.REC_ARMOR], 390.0)


def test_absorb_empty_armor_lets_loss_stay():
	App, AA, core, ship = setup()
	rec = AA.GetRecord(ship)
	rec[AA.REC_ARMOR] = 0.0
	ship.hull.fCond = 900.0
	AA.Absorb(ship, rec)
	assert ship.hull.fCond == 900.0
	assert rec[AA.REC_ENTRIES][0][1] == 900.0		# new value remembered
	rec[AA.REC_ARMOR] = 500.0
	AA.Absorb(ship, rec)							# the old loss is not restored later
	assert ship.hull.fCond == 900.0 and rec[AA.REC_ARMOR] == 500.0


def test_absorb_insufficient_armor_restores_partial_fraction():
	App, AA, core, ship = setup()
	rec = AA.GetRecord(ship)
	rec[AA.REC_ARMOR] = 50.0		# level 10%: bleed 0.4 -> fraction 0.6, costs 60 > 50
	ship.hull.fCond = 900.0
	AA.Absorb(ship, rec)
	assert near(ship.hull.fCond, 950.0)		# fraction 50/100
	assert near(rec[AA.REC_ARMOR], 0.0)


def test_absorb_bleed_through_when_worn():
	App, AA, core, ship = setup()
	rec = AA.GetRecord(ship)
	rec[AA.REC_ARMOR] = 125.0		# level 25%: bleed 0.25
	ship.hull.fCond = 900.0
	AA.Absorb(ship, rec)
	assert near(ship.hull.fCond, 975.0)
	assert near(rec[AA.REC_ARMOR], 50.0)
	assert near(rec[AA.REC_ENTRIES][0][1], 975.0)	# the bled 25 is not retried


def test_absorb_restored_value_capped_at_max_condition():
	# The remembered value can be above the max (e.g. the max was lowered);
	# the restore never goes over the max, but the armor still pays the full loss.
	App, AA, core, ship = setup()
	rec = AA.GetRecord(ship)
	rec[AA.REC_ENTRIES][0][1] = 1200.0
	ship.hull.fCond = 900.0
	AA.Absorb(ship, rec)
	assert ship.hull.fCond == 1000.0
	assert near(rec[AA.REC_ARMOR], 200.0)


def test_absorb_repaired_subsystem_only_updates_memory():
	App, AA, core, ship = setup()
	rec = AA.GetRecord(ship)
	pPhasers = ship.Sub("Phasers")
	rec[AA.REC_ENTRIES][1][1] = 80.0
	AA.Absorb(ship, rec)
	assert rec[AA.REC_ENTRIES][1][1] == 100.0
	assert rec[AA.REC_ARMOR] == 500.0 and pPhasers.sets == []


def test_absorb_subsystem_mode_charges_armor_subsystem():
	App, AA, core, ship = setup(iCreate=1)
	rec = AA.GetRecord(ship)
	pArmor = rec[AA.REC_SUB]
	ship.hull.fCond = 900.0
	AA.Absorb(ship, rec)
	assert ship.hull.fCond == 1000.0
	assert near(pArmor.fCond, 400.0) and near(rec[AA.REC_LAST], 400.0)
	assert ship.repair.listed == [pArmor]


def test_absorb_subsystem_mode_never_below_min_armor():
	App, AA, core, ship = setup(iCreate=1)
	rec = AA.GetRecord(ship)
	pArmor = rec[AA.REC_SUB]
	pArmor.fCond = 21.0		# 20 of armor left (level 4%): bleed 0.46
	ship.hull.fCond = 900.0
	AA.Absorb(ship, rec)
	assert near(ship.hull.fCond, 920.0)
	assert pArmor.fCond == 1.0


# --- Regenerate -----------------------------------------------------------------
def test_regen_rate_formula_internal():
	App, AA, core, ship = setup()
	rec = AA.GetRecord(ship)
	rec[AA.REC_ARMOR] = 400.0
	AA.Regenerate(ship, rec, 4.0)		# 10 points * 0.5 / complexity 2.0 = 2.5/s
	assert near(rec[AA.REC_REGEN], 2.5)
	assert near(rec[AA.REC_ARMOR], 410.0)


def test_regen_capped_at_max():
	App, AA, core, ship = setup()
	rec = AA.GetRecord(ship)
	rec[AA.REC_ARMOR] = 499.0
	AA.Regenerate(ship, rec, 4.0)
	assert rec[AA.REC_ARMOR] == 500.0


def test_regen_waits_while_hull_damaged():
	App, AA, core, ship = setup()
	rec = AA.GetRecord(ship)
	rec[AA.REC_ARMOR] = 400.0
	rec[AA.REC_REGEN] = 2.5
	ship.hull.fCond = 900.0
	AA.Regenerate(ship, rec, 4.0)
	assert rec[AA.REC_ARMOR] == 400.0 and rec[AA.REC_REGEN] == 0.0
	ship.hull.fCond = 999.6		# within 0.5 of full counts as repaired
	AA.Regenerate(ship, rec, 4.0)
	assert near(rec[AA.REC_ARMOR], 410.0)


def test_regen_without_repair_system_does_nothing():
	App, AA, core, ship = setup()
	ship.repair = None
	rec = AA.GetRecord(ship)
	rec[AA.REC_ARMOR] = 400.0
	AA.Regenerate(ship, rec, 4.0)
	assert rec[AA.REC_ARMOR] == 400.0 and rec[AA.REC_REGEN] == 0.0


def test_regen_full_armor_leaves_rate_alone():
	App, AA, core, ship = setup()
	rec = AA.GetRecord(ship)
	rec[AA.REC_REGEN] = 7.0
	AA.Regenerate(ship, rec, 4.0)
	assert rec[AA.REC_REGEN] == 7.0 and rec[AA.REC_ARMOR] == 500.0


def test_regen_subsystem_mode_and_game_repair_skip():
	App, AA, core, ship = setup(iCreate=1)
	rec = AA.GetRecord(ship)
	pArmor = rec[AA.REC_SUB]
	pArmor.fCond = 100.0
	AA.Regenerate(ship, rec, 4.0)		# first call: nothing remembered, module regenerates
	assert near(pArmor.fCond, 110.0) and near(rec[AA.REC_LAST], 110.0)
	pArmor.fCond = 200.0				# the game's repair teams raised it
	AA.Regenerate(ship, rec, 4.0)
	assert pArmor.fCond == 200.0 and rec[AA.REC_REGEN] == 0.0 and rec[AA.REC_LAST] == 200.0
	AA.Regenerate(ship, rec, 4.0)		# nobody raised it this time: module regenerates
	assert near(pArmor.fCond, 210.0)


def test_regen_subsystem_mode_capped_and_full():
	App, AA, core, ship = setup(iCreate=1)
	rec = AA.GetRecord(ship)
	pArmor = rec[AA.REC_SUB]
	pArmor.fCond = 499.0
	AA.Regenerate(ship, rec, 4.0)
	assert pArmor.fCond == 500.0
	n = len(pArmor.sets)
	AA.Regenerate(ship, rec, 4.0)		# full: untouched
	assert len(pArmor.sets) == n


# --- Tick / WeaponHit -------------------------------------------------------------
def test_tick_absorbs_and_regenerates():
	App, AA, core, ship = setup()
	core.interval = 4.0
	rec = AA.GetRecord(ship)
	ship.hull.fCond = 900.0
	AA.Tick([ship])
	assert ship.hull.fCond == 1000.0
	# Absorb leaves 400; the hull is full again, so Regenerate adds 4 s * 2.5 in the same cycle.
	assert near(rec[AA.REC_ARMOR], 410.0)


def test_tick_drops_records_of_ships_not_in_list():
	App, AA, core, ship = setup()
	core.techs["Defiant"] = {"AblativeArmor": -1}
	other = fake_ships.FakeShip("Defiant", 2, 1000.0, [("Phasers", 100.0)])
	plain = fake_ships.FakeShip("Plain", 3)
	AA.Tick([ship, other, plain])
	assert sorted(AA.g_dShips.keys()) == [1, 2, 3]
	assert AA.g_dShips[3] == None
	AA.Tick([ship])
	assert list(AA.g_dShips.keys()) == [1]


def test_ship_leaving_and_returning_recreates_record():
	# CURRENT BEHAVIOR: a ship missing from one Tick list loses its record;
	# when it comes back NewRecord runs again and the armor is full again.
	App, AA, core, ship = setup()
	calls = [0]
	fOrig = AA.NewRecord

	def counting(pShip, fPercent):
		calls[0] = calls[0] + 1
		return fOrig(pShip, fPercent)
	AA.NewRecord = counting
	AA.Tick([ship])
	AA.g_dShips[1][AA.REC_ARMOR] = 100.0
	AA.Tick([])
	assert 1 not in AA.g_dShips
	AA.Tick([ship])
	assert calls[0] == 2
	assert AA.g_dShips[1][AA.REC_ARMOR] == 500.0		# refilled for free


def test_ship_leaving_and_returning_duplicates_armor_subsystem():
	# FIXED: the existing "Ablative Armor" subsystem is reused (condition kept,
	# not refilled) and is not tracked as an ordinary subsystem.
	App, AA, core, ship = setup(iCreate=1)
	AA.Tick([ship])
	assert len(ship.Armors()) == 1
	pArmor = ship.Armors()[0]
	pArmor.fCond = 100.0
	AA.Tick([])
	AA.Tick([ship])
	assert len(ship.Armors()) == 1
	rec = AA.g_dShips[1]
	assert rec[AA.REC_SUB] is pArmor
	assert pArmor.fCond >= 100.0 and pArmor.fCond < 200.0		# kept (plus a little regeneration)
	assert len(rec[AA.REC_ENTRIES]) == 2		# hull and phasers only
	assert pArmor not in [e[0] for e in rec[AA.REC_ENTRIES]]
	# The reused armor is not added to the repair system a second time.
	assert ship.repair.added.count(pArmor) == 1


def test_ship_leaving_and_returning_internal_mode_refills_armor():
	# Pinned, unchanged: internal mode has no subsystem to reuse, the armor is full again.
	App, AA, core, ship = setup(iCreate=0)
	AA.Tick([ship])
	AA.g_dShips[1][AA.REC_ARMOR] = 100.0
	AA.Tick([])
	AA.Tick([ship])
	assert len(ship.Armors()) == 0
	assert AA.g_dShips[1][AA.REC_ARMOR] == 500.0


def test_weaponhit_ignores_non_hull_hits():
	App, AA, core, ship = setup()
	rec = AA.GetRecord(ship)
	ship.hull.fCond = 900.0
	AA.WeaponHit(ship, Event(0))
	assert ship.hull.fCond == 900.0
	AA.WeaponHit(ship, Event(1))
	assert ship.hull.fCond == 1000.0 and near(rec[AA.REC_ARMOR], 400.0)


def test_weaponhit_event_without_ishullhit_counts_as_hull_hit():
	App, AA, core, ship = setup()
	AA.GetRecord(ship)
	ship.hull.fCond = 900.0
	AA.WeaponHit(ship, object())
	assert ship.hull.fCond == 1000.0


def test_weaponhit_skips_dead_and_dying_ships():
	App, AA, core, ship = setup()
	AA.GetRecord(ship)
	ship.hull.fCond = 900.0
	ship.dead = 1
	AA.WeaponHit(ship, Event(1))
	assert ship.hull.fCond == 900.0
	ship.dead = 0
	ship.dying = 1
	AA.WeaponHit(ship, Event(1))
	assert ship.hull.fCond == 900.0


def test_weaponhit_creates_record_for_armored_ship_only():
	App, AA, core, ship = setup()
	AA.WeaponHit(ship, Event(1))
	assert AA.g_dShips[1] != None
	plain = fake_ships.FakeShip("Plain", 5)
	AA.WeaponHit(plain, Event(1))
	assert AA.g_dShips[5] == None


def run():
	return fake_ships.run(globals())


if __name__ == "__main__":
	sys.exit(run())
