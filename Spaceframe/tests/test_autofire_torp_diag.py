"""AutoFire torpedo launch diagnostic (Debug only): target at birth vs the armed list."""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mock_app
import test_autofire_base as base


class FakeTorp:
	def __init__(self, iParent, iTarget):
		self.p = iParent
		self.t = iTarget

	def GetParentID(self):
		return self.p

	def GetTargetID(self):
		return self.t


class FakeEvent:
	def __init__(self, pTorp):
		self.d = pTorp

	def GetDestination(self):
		return self.d


class FakeObj:
	def CallNextHandler(self, pEvent):
		pass


def scene(bDebug):
	App, AF, core, ship = base.setup()
	AF.g_bDebug = bDebug
	AF.g_iShipID = 7
	AF.g_lTorpList = None
	AF.g_bTorpLookup = 0
	AF.g_lTorpWatch = []
	App.Torpedo_Cast = lambda o: o
	return App, AF, core


def test_logs_target_and_list():
	App, AF, core = scene(1)
	AF.g_lTorpList = [11, [12], 0.0]
	AF.OnTorpedoLaunched(FakeObj(), FakeEvent(FakeTorp(7, 0)))
	l = [x[1] for x in core.logs if x[1].startswith("Torpedo launched")]
	assert len(l) == 1 and "target 0" in l[0] and "head 11" in l[0] and "[12]" in l[0], l


def test_no_list_armed_and_foreign_torpedo():
	App, AF, core = scene(1)
	AF.OnTorpedoLaunched(FakeObj(), FakeEvent(FakeTorp(7, 5)))
	AF.OnTorpedoLaunched(FakeObj(), FakeEvent(FakeTorp(99, 5)))
	l = [x[1] for x in core.logs if x[1].startswith("Torpedo launched")]
	assert len(l) == 1 and "no list armed yet" in l[0]


def test_debug_off_logs_nothing():
	App, AF, core = scene(0)
	AF.OnTorpedoLaunched(FakeObj(), FakeEvent(FakeTorp(7, 5)))
	assert [x for x in core.logs if x[1].startswith("Torpedo launched")] == []


def test_follow_up_summary_when_torpedo_ends():
	App, AF, core = scene(1)
	clock = [0.0]
	App.g_kUtopiaModule.GetGameTime = lambda: clock[0]
	pT = FakeTorp(7, 5)
	pT.GetObjID = lambda: 70
	AF.OnTorpedoLaunched(FakeObj(), FakeEvent(pT))
	assert len(AF.g_lTorpWatch) == 1
	App.Torpedo_GetObjectByID = lambda n, i: pT
	AF.TorpFollowUp()
	assert len(AF.g_lTorpWatch) == 1
	clock[0] = 1.2
	App.Torpedo_GetObjectByID = lambda n, i: None
	AF.TorpFollowUp()
	l = [x[1] for x in core.logs if x[1].startswith("Torpedo 70 ended")]
	assert len(l) == 1 and "flew 1.2 s" in l[0] and "target 5" in l[0], l
	assert AF.g_lTorpWatch == []


def test_follow_up_silent_when_lookup_fails():
	App, AF, core = scene(1)
	App.g_kUtopiaModule.GetGameTime = lambda: 0.0
	pT = FakeTorp(7, 5)
	pT.GetObjID = lambda: 70
	AF.OnTorpedoLaunched(FakeObj(), FakeEvent(pT))

	def boom(n, i):
		raise AttributeError("no")
	App.Torpedo_GetObjectByID = boom
	AF.TorpFollowUp()
	AF.TorpFollowUp()
	assert len([x for x in core.logs if x[1].startswith("Torpedo_GetObjectByID failed")]) == 1
	assert [x for x in core.logs if x[1].find("ended") >= 0] == []


def test_aim_angle_logged():
	App, AF, core = scene(1)

	class P:
		def __init__(self, x, y, z):
			self.v = (x, y, z)
	AF.GetSolution = lambda: _Sol()

	class _Sol:
		def Triple(self, v):
			return v.v

		def Dot3(self, a, b):
			return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]
	pT = FakeTorp(7, 5)
	pT.GetWorldForwardTG = lambda: P(1.0, 0.0, 0.0)
	pT.GetWorldLocation = lambda: P(0.0, 0.0, 0.0)
	pTarget = P(10.0, 0.0, 0.0)
	pTarget.GetWorldLocation = lambda: P(10.0, 5.7735, 0.0)
	App.ShipClass_GetObjectByID = lambda n, i: pTarget
	s = AF.TorpAim(pT)
	assert s.startswith(" aim 30.0 deg (100% of cone)"), s


def test_motion_logged():
	App, AF, core = scene(1)

	class P:
		def __init__(self, x, y, z):
			self.v = (x, y, z)

	class _Sol:
		def Triple(self, v):
			return v.v

		def Dot3(self, a, b):
			return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]
	AF.GetSolution = lambda: _Sol()
	App.g_kUtopiaModule.ConvertKilometersToGameUnits = lambda k: k
	pT = FakeTorp(7, 5)
	pT.GetWorldLocation = lambda: P(0.0, 0.0, 0.0)
	pT.GetVelocityTG = lambda: P(10.0, 0.0, 0.0)
	pTarget = P(0, 0, 0)
	pTarget.GetWorldLocation = lambda: P(20.0, 0.0, 0.0)
	pTarget.GetVelocityTG = lambda: P(-1.0, 3.0, 0.0)
	pOwn = P(0, 0, 0)
	pOwn.GetVelocityTG = lambda: P(1.0, 0.0, 0.0)
	App.ShipClass_GetObjectByID = lambda n, i: pOwn if i == 7 else pTarget
	s = AF.TorpMotion(pT)
	assert "tgt 3.16 km/s" in s and "closing 2.00 km/s" in s and "lateral 3.00 km/s" in s, s
	assert "own 1.00 km/s" in s and "proj 10.0 km/s ft 2.00 s drift 6.00 km" in s, s
	assert s.endswith("vel 0.0 deg"), s
	pT.GetVelocityTG = lambda: P(0.0, 0.0, 0.0)
	assert AF.TorpMotion(pT).endswith(" proj ?")
	App.ShipClass_GetObjectByID = lambda n, i: None
	assert AF.TorpMotion(pT) == ""


def test_target_gone_noted_in_summary():
	App, AF, core = scene(1)
	clock = [0.0]
	App.g_kUtopiaModule.GetGameTime = lambda: clock[0]

	class Ship:
		def __init__(self):
			self.dead = 0

		def IsDead(self):
			return self.dead

		def IsDying(self):
			return 0
	pShip = Ship()
	App.ShipClass_GetObjectByID = lambda n, i: pShip
	pT = FakeTorp(7, 5)
	pT.GetObjID = lambda: 70
	AF.OnTorpedoLaunched(FakeObj(), FakeEvent(pT))
	App.Torpedo_GetObjectByID = lambda n, i: pT
	clock[0] = 0.4
	AF.TorpFollowUp()
	pShip.dead = 1
	clock[0] = 0.6
	AF.TorpFollowUp()
	clock[0] = 1.2
	App.Torpedo_GetObjectByID = lambda n, i: None
	AF.TorpFollowUp()
	l = [x[1] for x in core.logs if x[1].startswith("Torpedo 70 ended")]
	assert len(l) == 1 and "target gone 0.6 s after launch" in l[0], l


def test_target_alive_noted_in_summary():
	App, AF, core = scene(1)
	clock = [0.0]
	App.g_kUtopiaModule.GetGameTime = lambda: clock[0]

	class Ship:
		def IsDead(self):
			return 0

		def IsDying(self):
			return 0
	App.ShipClass_GetObjectByID = lambda n, i: Ship()
	pT = FakeTorp(7, 5)
	pT.GetObjID = lambda: 71
	AF.OnTorpedoLaunched(FakeObj(), FakeEvent(pT))
	clock[0] = 1.0
	App.Torpedo_GetObjectByID = lambda n, i: None
	AF.TorpFollowUp()
	l = [x[1] for x in core.logs if x[1].startswith("Torpedo 71 ended")]
	assert len(l) == 1 and l[0].endswith("target alive"), l


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
