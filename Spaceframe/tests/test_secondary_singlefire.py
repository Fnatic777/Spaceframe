"""Task 2 tests: SecondaryTarget single-fire lift and restore."""
import builtins
import os
import sys
import types
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mock_app

builtins.reload = lambda m: m
builtins.apply = lambda f, a: f(*a)

PKG = "Custom.Spaceframe.Modules.SecondaryTarget"
CALLS = []	# every engine call made on a property: (ship id, group, value)


class FakeProp:
	def __init__(self, iID, eGroup, iSingle, bFailSet=0):
		self.iID = iID
		self.eGroup = eGroup
		self.iSingle = iSingle
		self.bFailSet = bFailSet

	def IsSingleFire(self):
		return self.iSingle

	def SetSingleFire(self, i):
		CALLS.append((self.iID, self.eGroup, i))
		if self.bFailSet:
			raise RuntimeError("set failed")
		self.iSingle = i


class FakeSystem:
	def __init__(self, pProp):
		self.pProp = pProp

	def GetProperty(self):
		return self.pProp


class FakeShip:
	def __init__(self, iID, dOrig, bDying=0):
		self.iID = iID
		self.bDying = bDying
		self.dSys = {}
		for e in dOrig.keys():
			self.dSys[e] = FakeSystem(FakeProp(iID, e, dOrig[e]))

	def GetObjID(self):
		return self.iID

	def IsDying(self):
		return self.bDying

	def GetWeaponSystemGroup(self, e):
		return self.dSys.get(e)


def setup():
	App = mock_app.make_app()
	mock_app.install(App)
	App.WeaponSystemProperty_Cast = lambda o: o
	ST = mock_app.load_module("Modules/SecondaryTarget/SecondaryTarget.py", PKG + ".SecondaryTarget")
	del CALLS[:]
	return App, ST


def add(pShip):
	mock_app.SHIPS[pShip.iID] = pShip
	return pShip


def test_lift_records_original_and_sets_zero():
	App, ST = setup()
	ship = add(FakeShip(5, {1: 1, 2: 1}))
	assert ST.LiftSingleFire(ship, ship.dSys[1], 1) == 1
	assert ship.dSys[1].pProp.iSingle == 0
	assert ship.dSys[2].pProp.iSingle == 1
	assert ST.g_dLifted == {5: {1: 1}}


def test_restore_writes_original_not_one():
	App, ST = setup()
	ship = add(FakeShip(5, {1: 0, 2: 1}))
	ST.LiftSingleFire(ship, ship.dSys[1], 1)
	ST.LiftSingleFire(ship, ship.dSys[2], 2)
	assert ship.dSys[2].pProp.iSingle == 0
	assert ST.RestoreSingleFire(ship) == 2
	assert ship.dSys[1].pProp.iSingle == 0
	assert ship.dSys[2].pProp.iSingle == 1
	assert ST.g_dLifted == {}


def test_restore_skipped_when_ship_gone():
	App, ST = setup()
	ship = add(FakeShip(5, {1: 1}))
	ST.LiftSingleFire(ship, ship.dSys[1], 1)
	del CALLS[:]
	del mock_app.SHIPS[5]
	assert ST.ReleaseShipID(5) == 0
	assert CALLS == []
	assert ST.g_dLifted == {}
	# nothing recorded: nothing asked either
	assert ST.RestoreSingleFire(None) == 0


def test_lift_twice_keeps_first_original():
	App, ST = setup()
	ship = add(FakeShip(5, {1: 1}))
	ST.LiftSingleFire(ship, ship.dSys[1], 1)
	ST.LiftSingleFire(ship, ship.dSys[1], 1)
	assert ST.g_dLifted == {5: {1: 1}}
	ST.RestoreSingleFire(ship)
	assert ship.dSys[1].pProp.iSingle == 1


def test_error_in_lift_still_recorded():
	App, ST = setup()
	ship = add(FakeShip(5, {1: 1}))
	ship.dSys[1].pProp.bFailSet = 1
	assert ST.LiftSingleFire(ship, ship.dSys[1], 1) == 0
	assert ST.g_dLifted == {5: {1: 1}}
	ship.dSys[1].pProp.bFailSet = 0
	ship.dSys[1].pProp.iSingle = 0
	assert ST.RestoreSingleFire(ship) == 1
	assert ship.dSys[1].pProp.iSingle == 1


def test_dying_ship_still_restored():
	App, ST = setup()
	ship = add(FakeShip(5, {1: 1}, bDying=1))
	ST.LiftSingleFire(ship, ship.dSys[1], 1)
	assert ST.ReleaseShipID(5) == 1
	assert ship.dSys[1].pProp.iSingle == 1


def test_stop_forgets_without_touching_ships():
	App, ST = setup()
	ship = add(FakeShip(5, {1: 1}))
	ST.LiftSingleFire(ship, ship.dSys[1], 1)
	del CALLS[:]
	ST.Stop()
	assert ST.g_dLifted == {}
	assert CALLS == []


def test_raw_property_fallback_when_cast_fails():
	App, ST = setup()
	App.WeaponSystemProperty_Cast = lambda o: 1 / 0
	ship = add(FakeShip(5, {1: 1}))
	assert ST.LiftSingleFire(ship, ship.dSys[1], 1) == 1
	assert ship.dSys[1].pProp.iSingle == 0


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
