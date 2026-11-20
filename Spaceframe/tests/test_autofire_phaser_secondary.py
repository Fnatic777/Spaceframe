"""Phaser secondaries under Auto Fire: a phaser group whose banks cannot reach the
main target starts at a secondary a ready bank reaches (SecondaryTarget supplies
the candidates through PhaserCandidates, Auto Fire decides)."""
import os
import sys
import types
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mock_app
import test_autofire_base as base

PKG = "Custom.Spaceframe.Modules.SecondaryTarget"
GROUP = 0	# WG_PRIMARY


class ReachBank(mock_app.Bank):
	"""A bank that reaches only the points whose x is in lReach."""
	def __init__(self, lReach, fCharge=1.0, fMax=100.0):
		mock_app.Bank.__init__(self, fMax, fCharge)
		self.lReach = lReach

	def CanHit(self, pPoint):
		return pPoint.x in self.lReach


def load_st(core, **kw):
	cfg = types.ModuleType(PKG + ".Config")
	cfg.Weapons = 7
	cfg.Interval = 0.2
	cfg.MaxCandidates = 4
	cfg.SecondaryRange = 100
	cfg.SecondaryTorpedoRange = 30
	cfg.Debug = 0
	for k in kw:
		setattr(cfg, k, kw[k])
	if PKG not in sys.modules:
		sys.modules[PKG] = types.ModuleType(PKG)
	sys.modules["Custom.Spaceframe.Modules"].SecondaryTarget = sys.modules[PKG]
	sys.modules[PKG + ".Config"] = cfg
	sys.modules[PKG].Config = cfg
	ST = mock_app.load_module("Modules/SecondaryTarget/SecondaryTarget.py", PKG + ".SecondaryTarget")
	ST.g_pCore = core
	ST.LoadConfig()
	ST.g_iOn = 1
	return ST


def setup(reach=(20.0,), charge=1.0, mask=7, st=1, stOn=1, friendly=0, secx=20.0, cfg=None, **kw):
	"""Player at the origin; main (7) at x=10; secondaries 8 at secx and 9 at x=30.
	One bank (fMax 100) that reaches only the x values in `reach`."""
	dKw = {"PhaserRange": 100, "PhaserMinCharge": 50}
	for k in kw:
		dKw[k] = kw[k]
	App, AF, core, ship = base.setup(**dKw)
	sys.modules["Custom.Spaceframe.Modules.AutoFire"].AutoFire = AF	# SecondaryTarget imports it
	main = mock_app.Ship("Main", 7)
	main.pos = mock_app.Point(10.0, 0.0, 0.0)
	sec = mock_app.Ship("Sec", 8)
	sec.pos = mock_app.Point(secx, 0.0, 0.0)
	sec2 = mock_app.Ship("Sec2", 9)
	sec2.pos = mock_app.Point(30.0, 0.0, 0.0)
	ship.target = main
	if friendly:
		core.g_pMission = mock_app.Mission([main], [sec, sec2])
	else:
		core.g_pMission = mock_app.Mission([main, sec, sec2])
	core.techs["Galaxy"] = {"AutoFire": -1, "SecondaryTarget": mask}
	bank = ReachBank(list(reach), charge)
	grp = mock_app.WeaponGroup([bank])
	ship.groups[GROUP] = grp
	ST = None
	if st:
		ST = load_st(core, **(cfg or {}))
		ST.g_iOn = stOn
		core.modules["SecondaryTarget"] = ST
	AF.Toggle()
	return AF, ST, core, ship, main, sec, sec2, bank, grp


def started(grp):
	return [c[1].GetObjID() for c in grp.calls if c[0] == "start"]


def seq(grp):
	l = []
	for c in grp.calls:
		if c[0] == "start":
			l.append("start" + str(c[1].GetObjID()))
		else:
			l.append(c[0])
	return l


def test_main_unreachable_secondary_reachable_starts_at_secondary():
	AF, ST, core, ship, main, sec, sec2, bank, grp = setup()
	AF.g_bDebug = 1
	AF.FireCycle()
	assert seq(grp) == ["start8"]
	assert grp.forced != []
	assert AF.g_dSecHead[GROUP] == 8
	assert [l for l in core.logs if l[1].find("plan: main - sec 8 head sec") >= 0] != []
	assert [l for l in core.logs if l[1].find("fires at secondary 8") >= 0] != []


def test_main_reachable_unchanged():
	AF, ST, core, ship, main, sec, sec2, bank, grp = setup(reach=(10.0, 20.0))
	AF.g_bDebug = 1
	AF.FireCycle()
	AF.FireCycle()
	assert seq(grp) == ["start7"]
	assert AF.g_dSecHead.get(GROUP) is None
	assert [l for l in core.logs if l[1].find("plan:") >= 0] == []


def test_extra_ready_candidates_follow_the_head():
	AF, ST, core, ship, main, sec, sec2, bank, grp = setup(reach=(20.0, 30.0))
	AF.FireCycle()
	assert seq(grp) == ["start8", "start9"]


def test_head_kept_while_held_no_flapping():
	AF, ST, core, ship, main, sec, sec2, bank, grp = setup()
	for i in range(5):
		AF.FireCycle()
	assert seq(grp) == ["start8"]
	assert AF.g_dSecHead[GROUP] == 8


def test_main_becomes_reachable_restarts_at_main():
	AF, ST, core, ship, main, sec, sec2, bank, grp = setup()
	AF.FireCycle()
	bank.lReach = [10.0, 20.0]
	AF.FireCycle()
	assert seq(grp) == ["start8", "stop", "start7"]
	assert AF.g_dSecHead.get(GROUP) is None
	AF.FireCycle()
	assert seq(grp) == ["start8", "stop", "start7"]


def test_head_unreachable_moves_to_next_secondary():
	AF, ST, core, ship, main, sec, sec2, bank, grp = setup(reach=(20.0, 30.0))
	AF.FireCycle()
	bank.lReach = [30.0]
	AF.FireCycle()
	assert seq(grp) == ["start8", "start9", "stop", "start9"]
	assert AF.g_dSecHead[GROUP] == 9


def test_head_unreachable_nothing_else_stops_group():
	AF, ST, core, ship, main, sec, sec2, bank, grp = setup()
	AF.FireCycle()
	bank.lReach = []
	AF.FireCycle()
	assert seq(grp) == ["start8", "stop"]
	assert AF.g_dSecHead.get(GROUP) is None
	AF.FireCycle()
	assert seq(grp) == ["start8", "stop"]


def test_game_stopped_group_restarts_at_head():
	AF, ST, core, ship, main, sec, sec2, bank, grp = setup()
	AF.FireCycle()
	grp.GameStop()
	AF.FireCycle()
	assert seq(grp) == ["start8", "start8"]


def test_secondary_phasers_off_is_todays_behavior():
	AF, ST, core, ship, main, sec, sec2, bank, grp = setup(SecondaryPhasers=0)
	AF.FireCycle()
	assert grp.calls == []


def test_secondary_target_absent_nothing_fires():
	AF, ST, core, ship, main, sec, sec2, bank, grp = setup(st=0)
	AF.FireCycle()
	assert grp.calls == []


def test_secondary_target_toggle_off_nothing_fires():
	AF, ST, core, ship, main, sec, sec2, bank, grp = setup(stOn=0)
	AF.FireCycle()
	assert grp.calls == []


def test_phaser_bit_missing_nothing_fires():
	AF, ST, core, ship, main, sec, sec2, bank, grp = setup(mask=6)
	AF.FireCycle()
	assert grp.calls == []


def test_secondary_beyond_secondary_range_ignored():
	AF, ST, core, ship, main, sec, sec2, bank, grp = setup(reach=(150.0,), secx=150.0, cfg={"SecondaryRange": 100})
	AF.FireCycle()
	assert grp.calls == []


def test_zero_range_settings_plan_works_far_away():
	# SecondaryRange 0 and PhaserRange 0 (and PhaserMinCharge 0): a far secondary
	# with an empty bank is still taken.
	AF, ST, core, ship, main, sec, sec2, bank, grp = setup(reach=(900.0,), secx=900.0, charge=0.0, PhaserRange=0, PhaserMinCharge=0, cfg={"SecondaryRange": 0})
	AF.FireCycle()
	assert seq(grp) == ["start8"]
	assert ST.PhaserCandidates(ship, grp, main) == [9, 8]	# nearest first


def test_friendly_secondary_ignored():
	AF, ST, core, ship, main, sec, sec2, bank, grp = setup(friendly=1)
	AF.FireCycle()
	assert grp.calls == []


def test_low_charge_not_ready():
	AF, ST, core, ship, main, sec, sec2, bank, grp = setup(charge=0.4)
	AF.FireCycle()
	assert grp.calls == []


def test_manual_key_hands_off():
	AF, ST, core, ship, main, sec, sec2, bank, grp = setup()
	AF.g_dManual[GROUP] = 1
	AF.FireCycle()
	assert grp.calls == []


def test_stop_clears_state():
	AF, ST, core, ship, main, sec, sec2, bank, grp = setup()
	AF.g_bDebug = 1
	AF.FireCycle()
	assert AF.g_dSecHead[GROUP] == 8
	assert AF.g_dPlanNote != {}
	AF.Stop()
	assert AF.g_dSecHead == {}
	assert AF.g_dPlanNote == {}
	assert grp.stops() == 0


def test_plan_error_is_contained():
	AF, ST, core, ship, main, sec, sec2, bank, grp = setup()
	def boom(a, b, c):
		raise TypeError("PhaserCandidates")
	ST.PhaserCandidates = boom
	AF.FireCycle()
	assert grp.calls == []


# --- SecondaryTarget.PhaserCandidates ---

def test_candidates_nearest_first():
	AF, ST, core, ship, main, sec, sec2, bank, grp = setup()
	assert ST.PhaserCandidates(ship, grp, main) == [8, 9]


def test_candidates_toggle_off_empty():
	AF, ST, core, ship, main, sec, sec2, bank, grp = setup(stOn=0)
	assert ST.PhaserCandidates(ship, grp, main) == []


def test_candidates_phaser_bit_missing_empty():
	AF, ST, core, ship, main, sec, sec2, bank, grp = setup(mask=6)
	assert ST.PhaserCandidates(ship, grp, main) == []


def test_candidates_max_candidates():
	AF, ST, core, ship, main, sec, sec2, bank, grp = setup(cfg={"MaxCandidates": 1})
	assert ST.PhaserCandidates(ship, grp, main) == [8]


def test_candidates_not_player_ship_empty():
	AF, ST, core, ship, main, sec, sec2, bank, grp = setup()
	other = mock_app.Ship("Other", 5)
	assert ST.PhaserCandidates(other, grp, main) == []


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
