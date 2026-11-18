"""SecondaryTarget: fast limit timer (LimitInterval) and HoldMode."""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mock_app
import test_secondary_cycle as T

ORDER = []	# (call, bank name) in the order the engine received them


class FireBank(T.ReachBank):
	def __init__(self, sName, iTarget, fCharge=1.0):
		T.ReachBank.__init__(self, [20.0, 30.0])
		self.sName = sName
		self.iTarget = iTarget
		self.fCharge = fCharge
		self.bFire = 1

	def IsFiring(self):
		return self.bFire

	def GetTargetID(self):
		return self.iTarget

	def StopFiring(self):
		ORDER.append(("stop", self.sName))
		self.bFire = 0

	def SetFiring(self, i):
		ORDER.append(("set" + str(i), self.sName))


def build(**kw):
	del ORDER[:]
	if "PhaserPerTarget" not in kw:
		kw["PhaserPerTarget"] = 1
	App, ST, core, ship = T.setup(**kw)
	main, b, c, pSys = T.scene(core, ship)
	lBanks = [FireBank("a", 3, 0.2), FireBank("b", 3, 0.9)]
	pSys = T.ListGroup(lBanks, "g0")
	ship.groups[0] = pSys
	pSys.Press(main)
	return App, ST, core, ship, pSys, main, lBanks


def fast(ST):
	return ST.g_pFastTimer != None and ST.g_pFastTimer.bActive


def test_fast_timer_starts_only_when_lifted_and_enabled():
	App, ST, core, ship, pSys, main, l = build()
	assert not fast(ST)
	ST.Cycle()
	assert fast(ST)
	assert ST.g_pFastTimer.pProcess.delay == 0.05
	# PhaserPerTarget 0: never a fast timer
	App, ST, core, ship, pSys, main, l = build(PhaserPerTarget=0)
	ST.Cycle()
	assert ST.g_dLifted != {} and not fast(ST)
	# nothing lifted (no reachable secondary): no fast timer
	App, ST, core, ship, pSys, main, l = build()
	for bank in l:
		bank.lReach = [10.0]
	ST.Cycle()
	assert ST.g_dLifted == {} and not fast(ST)


def test_fast_tick_drives_limit_without_cycle():
	App, ST, core, ship, pSys, main, l = build()
	ST.Cycle()
	assert ORDER == [("stop", "a")]
	l[0].bFire = 1
	del ORDER[:]
	ST.g_pFastTimer.Update(0.0)
	assert ORDER == [("stop", "a")]


def test_fast_timer_stopped_on_restore():
	App, ST, core, ship, pSys, main, l = build()
	ST.Cycle()
	assert fast(ST)
	pOld = ST.g_pFastTimer
	ship.target.dead = 1
	ST.Cycle()
	assert not fast(ST) and ST.g_pFastTimer == None
	assert not pOld.bActive
	del ORDER[:]
	pOld.Update(0.0)
	assert ORDER == []


def test_fast_timer_stopped_on_forget_all_and_stop():
	App, ST, core, ship, pSys, main, l = build()
	ST.Cycle()
	ST.ForgetAll()
	assert ST.g_pFastTimer == None
	ST.Cycle()
	assert fast(ST)
	ST.Stop()
	assert ST.g_pFastTimer == None


def test_fast_timer_stopped_on_ship_change():
	App, ST, core, ship, pSys, main, l = build()
	ST.Cycle()
	assert fast(ST)
	other = mock_app.Ship("Galaxy", 7)
	other.groups = T.CountDict()
	App._player[0] = other
	ST.Cycle()
	assert not fast(ST)
	assert ST.g_dPhaser == {}


def test_fast_tick_stops_when_ship_gone_or_dying():
	App, ST, core, ship, pSys, main, l = build()
	ST.Cycle()
	pT = ST.g_pFastTimer
	App._player[0] = None
	ST.g_pFastTimer.Update(0.0)
	# only flagged dead: object and process stay until the next Cycle
	assert ST.g_pFastTimer is pT and not pT.bActive and pT.pProcess != None
	ST.Cycle()
	assert ST.g_pFastTimer == None
	App, ST, core, ship, pSys, main, l = build()
	ST.Cycle()
	ship.dead = 1
	ST.g_pFastTimer.Update(0.0)
	assert ST.g_pFastTimer != None and not ST.g_pFastTimer.bActive
	# a Cycle while dying releases it and does not restart it
	ST.Cycle()
	assert ST.g_pFastTimer == None


def test_fast_tick_only_flags_and_sync_releases():
	App, ST, core, ship, pSys, main, l = build()
	ST.Cycle()
	pT = ST.g_pFastTimer
	pProc = pT.pProcess
	lCalls = []
	fOrig = ST.StopFastTimer
	def spy():
		lCalls.append(1)
		fOrig()
	ST.StopFastTimer = spy
	ST.g_dPhaser.clear()	# FastTick finds nothing to do: ends its lift
	pT.Update(0.0)
	assert lCalls == []
	assert ST.g_pFastTimer is pT and pT.pProcess is pProc and not pT.bActive
	ST.SyncFastTimer()
	assert lCalls != [] and ST.g_pFastTimer == None and pT.pProcess == None


def test_dead_timer_replaced_when_lift_starts_again():
	App, ST, core, ship, pSys, main, l = build()
	ST.Cycle()
	pOld = ST.g_pFastTimer
	pOld.bActive = 0	# as FastTick leaves it
	ST.StartFastTimer()
	assert ST.g_pFastTimer is not pOld and ST.g_pFastTimer.bActive
	assert pOld.pProcess == None
	# and through a Cycle with a lift still active
	pNew = ST.g_pFastTimer
	pNew.bActive = 0
	ST.Cycle()
	assert fast(ST) and ST.g_pFastTimer is not pNew


def test_hold_mode_0_stop_only_and_1_stop_then_set():
	App, ST, core, ship, pSys, main, l = build(HoldMode=0)
	ST.Cycle()
	assert ORDER == [("stop", "a")]
	App, ST, core, ship, pSys, main, l = build(HoldMode=1)
	ST.Cycle()
	assert ORDER == [("stop", "a"), ("set0", "a")]
	# the kept (highest charge) bank is never touched
	assert ("stop", "b") not in ORDER


def test_stop_touches_no_ship():
	App, ST, core, ship, pSys, main, l = build()
	ST.Start(core)
	ST.Cycle()
	assert fast(ST)
	del mock_app.TOUCHED[:]
	ST.Stop()
	assert mock_app.TOUCHED == []
	assert ST.g_pFastTimer == None


def test_limit_interval_clamp():
	App, ST, core, ship, pSys, main, l = build(LimitInterval=0.001)
	assert ST.g_fLimitInterval == 0.02
	App, ST, core, ship, pSys, main, l = build(LimitInterval=0.03)
	assert ST.g_fLimitInterval == 0.03
	ST.Cycle()
	assert ST.g_pFastTimer.pProcess.delay == 0.03


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
