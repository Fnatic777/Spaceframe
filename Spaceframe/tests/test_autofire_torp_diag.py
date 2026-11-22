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


class _P:
	def __init__(self, x, y, z):
		self.v = (x, y, z)


class _PSol:
	def Triple(self, v):
		return v.v

	def Dot3(self, a, b):
		return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]

	def LeadPoint(self, pTarget, vOffset, vFrom, fSpeed):
		return _P(20.0, 0.0, 0.0)	# the predicted arrival point, fixed for the test


def prediction_scene():
	App, AF, core = scene(1)
	AF.GetSolution = lambda: _PSol()
	App.g_kUtopiaModule.ConvertKilometersToGameUnits = lambda k: k
	clock = [0.0]
	App.g_kUtopiaModule.GetGameTime = lambda: clock[0]
	pT = FakeTorp(7, 5)
	pT.GetObjID = lambda: 70
	pT.pos = [0.0, 0.0, 0.0]
	pT.GetWorldLocation = lambda: _P(pT.pos[0], pT.pos[1], pT.pos[2])
	pT.GetVelocityTG = lambda: _P(10.0, 0.0, 0.0)
	pTarget = _P(0, 0, 0)
	pTarget.pos = [20.0, 0.0, 0.0]
	pTarget.vel = [0.0, 1.0, 0.0]
	pTarget.GetWorldLocation = lambda: _P(pTarget.pos[0], pTarget.pos[1], pTarget.pos[2])
	pTarget.GetVelocityTG = lambda: _P(pTarget.vel[0], pTarget.vel[1], pTarget.vel[2])
	App.ShipClass_GetObjectByID = lambda n, i: pTarget
	App.Torpedo_GetObjectByID = lambda n, i: pT
	return App, AF, core, clock, pT, pTarget


def test_prediction_stored_at_launch():
	App, AF, core, clock, pT, pTarget = prediction_scene()
	tP = AF.TorpPrediction(pT)
	assert tP[0] == (20.0, 0.0, 0.0) and abs(tP[1] - 2.0) < 1e-9 and tP[2] == (0.0, 1.0, 0.0), tP
	AF.OnTorpedoLaunched(FakeObj(), FakeEvent(pT))
	e = AF.g_lTorpWatch[0]
	assert len(e) == 16 and e[15] == None and e[11] == (20.0, 0.0, 0.0) and e[14] == None
	App.ShipClass_GetObjectByID = lambda n, i: None
	assert AF.TorpPrediction(pT) == None


def test_sample_closest_to_predicted_arrival_in_summary():
	App, AF, core, clock, pT, pTarget = prediction_scene()
	AF.OnTorpedoLaunched(FakeObj(), FakeEvent(pT))
	clock[0] = 1.0
	pTarget.pos = [20.0, 1.0, 0.0]
	pT.pos = [10.0, 0.0, 0.0]
	AF.TorpFollowUp()
	clock[0] = 2.0	# the predicted arrival: target 3 km off the point, velocity turned 90 deg
	pTarget.pos = [20.0, 3.0, 0.0]
	pTarget.vel = [1.0, 0.0, 0.0]
	pT.pos = [19.0, 0.0, 0.0]
	AF.TorpFollowUp()
	clock[0] = 2.5	# later samples do not replace it
	pTarget.pos = [25.0, 9.0, 0.0]
	AF.TorpFollowUp()
	App.Torpedo_GetObjectByID = lambda n, i: None
	clock[0] = 2.6
	AF.TorpFollowUp()
	l = [x[1] for x in core.logs if x[1].startswith("Torpedo 70 ended")]
	assert len(l) == 1, l
	assert "predicted arrival 2.0 s (sampled 0.00 s off): target 3.00 km from the predicted point" in l[0], l
	assert "torpedo 1.00 km from it" in l[0] and "velocity changed 1.41 km/s, turned 90.0 deg" in l[0], l


def test_no_sample_when_the_torpedo_ends_first():
	App, AF, core, clock, pT, pTarget = prediction_scene()
	AF.OnTorpedoLaunched(FakeObj(), FakeEvent(pT))
	App.Torpedo_GetObjectByID = lambda n, i: None
	clock[0] = 0.5
	AF.TorpFollowUp()
	l = [x[1] for x in core.logs if x[1].startswith("Torpedo 70 ended")]
	assert len(l) == 1 and "no sample at the predicted arrival (2.0 s)" in l[0], l


def test_summary_without_prediction_unchanged():
	App, AF, core, clock, pT, pTarget = prediction_scene()
	App.ShipClass_GetObjectByID = lambda n, i: None
	AF.OnTorpedoLaunched(FakeObj(), FakeEvent(pT))
	App.Torpedo_GetObjectByID = lambda n, i: None
	clock[0] = 0.5
	AF.TorpFollowUp()
	l = [x[1] for x in core.logs if x[1].startswith("Torpedo 70 ended")]
	assert len(l) == 1 and l[0].find("predicted") < 0, l


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


class _GSol(_PSol):
	def GetScriptInfo(self, sMod):
		if sMod == "Bolt":
			return (0.0, 0.0, 5.0)
		return (6.0, 1.0, 20.0)


def test_non_guided_projectile_ignored():
	App, AF, core, clock, pT, pTarget = prediction_scene()
	AF.GetSolution = lambda: _GSol()
	pT.GetModuleName = lambda: "Bolt"
	AF.OnTorpedoLaunched(FakeObj(), FakeEvent(pT))
	assert [x for x in core.logs if x[1].startswith("Torpedo launched")] == []
	assert AF.g_lTorpWatch == []
	pT.GetModuleName = lambda: "Photon"
	AF.OnTorpedoLaunched(FakeObj(), FakeEvent(pT))
	l = [x[1] for x in core.logs if x[1].startswith("Torpedo launched")]
	assert len(l) == 1 and "toward-point 0.0 deg" in l[0], l
	assert len(AF.g_lTorpWatch) == 1


def test_toward_point_angle():
	App, AF, core, clock, pT, pTarget = prediction_scene()
	assert AF.TorpPointAngle(pT, (20.0, 0.0, 0.0)) == " toward-point 0.0 deg"
	assert AF.TorpPointAngle(pT, (0.0, 5.0, 0.0)) == " toward-point 90.0 deg"
	assert AF.TorpPointAngle(pT, (0.0, 0.0, 0.0)) == " toward-point ?"
	App.ShipClass_GetObjectByID = lambda n, i: None
	AF.OnTorpedoLaunched(FakeObj(), FakeEvent(pT))
	l = [x[1] for x in core.logs if x[1].startswith("Torpedo launched")]
	assert len(l) == 1 and l[0].endswith(" toward-point ? rel-point ? own-shift ? tube-h ? tube-v ? tube-ang ? eng-ang ? tubes [] decision none"), l


def ship_angles_scene(tTorpVel, tShipVel):
	App, AF, core, clock, pT, pTarget = prediction_scene()
	pT.GetVelocityTG = lambda: _P(tTorpVel[0], tTorpVel[1], tTorpVel[2])
	pOwn = _P(0, 0, 0)
	pOwn.GetVelocityTG = lambda: _P(tShipVel[0], tShipVel[1], tShipVel[2])
	App.ShipClass_GetObjectByID = lambda n, i: pOwn if i == 7 else pTarget
	return App, AF, core, pT


def test_ship_angles_zero_ship_velocity():
	App, AF, core, pT = ship_angles_scene((10.0, 0.0, 0.0), (0.0, 0.0, 0.0))
	assert AF.TorpShipAngles(pT, (20.0, 0.0, 0.0)) == " rel-point 0.0 deg own-shift 0.0 deg"
	assert AF.TorpPointAngle(pT, (20.0, 0.0, 0.0)) == " toward-point 0.0 deg"
	assert AF.TorpShipAngles(pT, (0.0, 5.0, 0.0)) == " rel-point 90.0 deg own-shift 0.0 deg"


def test_ship_angles_inherited_velocity():
	# the torpedo flies (17, 1.7, 0): the tube direction (17, 0, 0) plus the ship's (0, 1.7, 0)
	App, AF, core, pT = ship_angles_scene((17.0, 1.7, 0.0), (0.0, 1.7, 0.0))
	sRel = AF.TorpShipAngles(pT, (20.0, 0.0, 0.0))
	assert sRel == " rel-point 0.0 deg own-shift 5.7 deg", sRel
	assert AF.TorpPointAngle(pT, (20.0, 0.0, 0.0)) == " toward-point 5.7 deg"
	AF.OnTorpedoLaunched(FakeObj(), FakeEvent(pT))
	l = [x[1] for x in core.logs if x[1].startswith("Torpedo launched")]
	assert len(l) == 1 and l[0].endswith(" toward-point 5.7 deg rel-point 0.0 deg own-shift 5.7 deg tube-h ? tube-v ? tube-ang ? eng-ang ? tubes [] decision none"), l


def test_ship_angles_unavailable():
	App, AF, core, pT = ship_angles_scene((10.0, 0.0, 0.0), (10.0, 0.0, 0.0))
	# torpedo velocity equals the ship's: no relative velocity, no shift
	assert AF.TorpShipAngles(pT, (20.0, 0.0, 0.0)) == " rel-point ? own-shift ?"
	App.ShipClass_GetObjectByID = lambda n, i: None
	assert AF.TorpShipAngles(pT, (20.0, 0.0, 0.0)) == " rel-point ? own-shift ?"
	App, AF, core, pT = ship_angles_scene((10.0, 0.0, 0.0), (0.0, 1.0, 0.0))
	assert AF.TorpShipAngles(pT, (0.0, 0.0, 0.0)) == " rel-point ? own-shift 5.7 deg"
	assert AF.TorpShipAngles(pT, None).startswith(" rel-point ? own-shift ")


class _Tube:
	# a tube or pulse weapon: world position, forward and right (up = right x forward is given)
	def __init__(self, tPos, tFwd, tRight, tUp):
		self.pos = tPos
		self.f = tFwd
		self.r = tRight
		self.u = tUp

	def GetWorldLocation(self):
		return _P(self.pos[0], self.pos[1], self.pos[2])


class _System:
	def __init__(self, lKids):
		self.k = lKids

	def GetNumChildSubsystems(self):
		return len(self.k)

	def GetChildSubsystem(self, i):
		return self.k[i]


class _TSol(_PSol):
	def TubeFrame(self, pShip, pTube):
		return (pTube.pos, pTube.f, pTube.r, pTube.u)

	def ArcAxes(self, pShip, pWeapon):
		return (_P(*pWeapon.f), _P(*pWeapon.r), _P(*pWeapon.u))


X = (1.0, 0.0, 0.0)
Y = (0.0, 1.0, 0.0)
Z = (0.0, 0.0, 1.0)


def tube_scene(lTubes, lPulse):
	App, AF, core, clock, pT, pTarget = prediction_scene()
	AF.GetSolution = lambda: _TSol()
	pOwn = _P(0, 0, 0)
	pOwn.GetTorpedoSystem = lambda: _System(lTubes)
	pOwn.GetPulseWeaponSystem = lambda: _System(lPulse)
	pOwn.GetVelocityTG = lambda: _P(0.0, 0.0, 0.0)
	App.ShipClass_GetObjectByID = lambda n, i: pOwn if i == 7 else pTarget
	App.TorpedoTube_Cast = lambda o: o
	App.PulseWeapon_Cast = lambda o: o
	AF.g_dPulseLast = {}
	AF.g_iPulseLines = 0
	return App, AF, core, clock, pT, pTarget


def test_tube_box_angles():
	import math
	fT = math.tan(math.radians(20.0))
	App, AF, core, clock, pT, pTarget = tube_scene([_Tube((0.0, 0.0, 0.0), X, Y, Z)], [])
	s = AF.TorpTubeAngles(pT, (20.0, 20.0 * fT, 20.0 * fT))
	fAng = math.degrees(math.atan(math.sqrt(2.0) * fT))
	assert s == " tube-h 20.0 tube-v 20.0 tube-ang %.1f" % fAng, s
	assert s.endswith("27.2"), s	# atan(sqrt(2) * tan 20) = 27.2
	s = AF.TorpTubeAngles(pT, (20.0, -20.0 * fT, 0.0))
	assert s == " tube-h -20.0 tube-v 0.0 tube-ang 20.0", s


def test_nearest_tube_selected():
	lT = [_Tube((50.0, 0.0, 0.0), X, Y, Z), _Tube((1.0, 0.0, 0.0), Y, Z, X)]
	App, AF, core, clock, pT, pTarget = tube_scene(lT, [])
	pT.pos = [2.0, 0.0, 0.0]
	# the second tube (nearest) looks along +y: a point on +y is dead ahead for it
	s = AF.TorpTubeAngles(pT, (1.0, 10.0, 0.0))
	assert s == " tube-h 0.0 tube-v 0.0 tube-ang 0.0", s
	pT.pos = [49.0, 0.0, 0.0]
	s = AF.TorpTubeAngles(pT, (100.0, 0.0, 0.0))
	assert s == " tube-h 0.0 tube-v 0.0 tube-ang 0.0", s


def test_tube_angles_unavailable():
	App, AF, core, clock, pT, pTarget = tube_scene([], [])
	q = " tube-h ? tube-v ? tube-ang ?"
	assert AF.TorpTubeAngles(pT, (20.0, 0.0, 0.0)) == q
	App, AF, core, clock, pT, pTarget = tube_scene([_Tube((0.0, 0.0, 0.0), X, Y, Z)], [])
	assert AF.TorpTubeAngles(pT, None) == q
	assert AF.TorpTubeAngles(pT, (0.0, 0.0, 0.0)) == q
	App.ShipClass_GetObjectByID = lambda n, i: None
	assert AF.TorpTubeAngles(pT, (20.0, 0.0, 0.0)) == q


def test_launch_line_ends_with_tube_angles():
	App, AF, core, clock, pT, pTarget = tube_scene([_Tube((0.0, 0.0, 0.0), X, Y, Z)], [])
	AF.OnTorpedoLaunched(FakeObj(), FakeEvent(pT))
	l = [x[1] for x in core.logs if x[1].startswith("Torpedo launched")]
	assert len(l) == 1 and l[0].endswith(" tube-h 0.0 tube-v 0.0 tube-ang 0.0 eng-ang ? tubes [0*:0.0/?/?] decision none"), l


class _CTube(_Tube):
	# a tube with a load state and a CanHit answer (a value, or an exception class to raise)
	def __init__(self, tPos, tFwd, iReady, vHit):
		_Tube.__init__(self, tPos, tFwd, Y, Z)
		self.n = iReady
		self.h = vHit

	def GetNumReady(self):
		return self.n

	def CanHit(self, vPoint):
		assert vPoint.v == (20.0, 0.0, 0.0), vPoint.v	# the target's world location
		if self.h == "raise":
			raise RuntimeError("boom")
		return self.h


def diag_scene(lTubes):
	App, AF, core, clock, pT, pTarget = tube_scene(lTubes, [])
	pOwn = App.ShipClass_GetObjectByID(None, 7)
	pOwn.GetWorldLocation = lambda: _P(0.0, 0.0, 0.0)
	return App, AF, core, pT, pTarget


def test_tube_list_fired_ready_and_canhit():
	import math
	lT = [_CTube((0.0, 0.0, 0.0), X, 0, 1), _CTube((1.0, 0.0, 0.0), X, 1, 1),
		_CTube((50.0, 0.0, 0.0), Y, 1, 0), _CTube((60.0, 0.0, 0.0), Y, 1, "raise"),
		_CTube((70.0, 0.0, 0.0), Y, 1, None)]
	App, AF, core, pT, pTarget = diag_scene(lT)
	pT.pos = [2.0, 0.0, 0.0]
	s = AF.TorpTubeDiag(pT, (20.0, 0.0, 0.0))
	fEng = math.degrees(math.atan(20.0 / 11.0 / 19.0))	# P' = (20, 20/11, 0) seen from (1, 0, 0)
	sEng = "%.1f" % fEng
	fY = 20.0 / 11.0
	l = []
	for fX in (50.0, 60.0, 70.0):
		l.append("%.1f" % math.degrees(math.acos(fY / math.sqrt((20.0 - fX) ** 2 + fY * fY))))
	assert s == " eng-ang " + sEng + " tubes [1*:0.0/1/" + sEng + " 2:90.0/0/" + l[0] + " 3:90.0/?/" + l[1] + " 4:90.0/?/" + l[2] + "]", s


def test_tube_list_zero_target_velocity_eng_equals_ang():
	lT = [_CTube((1.0, 0.0, 0.0), Y, 1, 1)]
	App, AF, core, pT, pTarget = diag_scene(lT)
	pTarget.vel = [0.0, 0.0, 0.0]
	pT.pos = [1.0, 0.0, 0.0]
	s = AF.TorpTubeDiag(pT, (20.0, 0.0, 0.0))
	assert s == " eng-ang 90.0 tubes [0*:90.0/1/90.0]", s
	lT[0].f = X
	s = AF.TorpTubeDiag(pT, (20.0, 0.0, 0.0))
	assert s == " eng-ang 0.0 tubes [0*:0.0/1/0.0]", s


def test_tube_list_capped_at_16_keeping_fired():
	lT = []
	for i in range(20):
		lT.append(_CTube((float(i), 0.0, 0.0), X, 1, 1))
	App, AF, core, pT, pTarget = diag_scene(lT)
	pT.pos = [19.0, 0.0, 0.0]
	s = AF.TorpTubeDiag(pT, (20.0, 0.0, 0.0))
	l = s[s.find("[") + 1:s.find("]")].split(" ")
	assert len(l) == 16 and l[0].startswith("0:") and l[14].startswith("14:") and l[15].startswith("19*:"), l


def test_tube_list_unavailable_is_question_marks():
	lT = [_CTube((1.0, 0.0, 0.0), X, 1, 1)]
	App, AF, core, pT, pTarget = diag_scene(lT)
	s = AF.TorpTubeDiag(pT, None)
	assert s.startswith(" eng-ang ") and "tubes [0*:?/1/" in s, s
	pTarget.GetVelocityTG = lambda: 5	# unusable: no engine point
	s = AF.TorpTubeDiag(pT, (20.0, 0.0, 0.0))
	assert s == " eng-ang ? tubes [0*:0.0/1/?]", s
	App.ShipClass_GetObjectByID = lambda n, i: None
	assert AF.TorpTubeDiag(pT, (20.0, 0.0, 0.0)) == " eng-ang ? tubes []"
	AF.GetSolution = lambda: None
	assert AF.TorpTubeDiag(pT, (20.0, 0.0, 0.0)) == " eng-ang ? tubes []"


class _BSol(_TSol):
	def GetScriptInfo(self, sMod):
		return (0.0, 0.0, 5.0)


def pulse_scene():
	lW = [_Tube((0.0, 0.0, 0.0), X, Y, Z), _Tube((100.0, 0.0, 0.0), Y, Z, X)]
	App, AF, core, clock, pT, pTarget = tube_scene([], lW)
	AF.GetSolution = lambda: _BSol()
	pT.GetModuleName = lambda: "Tactical.Projectiles.PulsePhaser"
	pT.GetVelocityTG = lambda: _P(10.0, 0.0, 0.0)
	return App, AF, core, clock, pT, pTarget


def pulse_lines(core):
	return [x[1] for x in core.logs if x[1].startswith("Pulse launched")]


def test_pulse_line_for_unguided():
	App, AF, core, clock, pT, pTarget = pulse_scene()
	AF.OnTorpedoLaunched(FakeObj(), FakeEvent(pT))
	l = pulse_lines(core)
	assert len(l) == 1, l
	assert l[0] == "Pulse launched: mod PulsePhaser dist 20.00 km vel-target 0.0 deg vel-point 0.0 deg weapon-target 0.0 deg vel-weapon 0.0 deg w-h 0.0 deg w-v 0.0 deg", l
	assert [x for x in core.logs if x[1].startswith("Torpedo launched")] == []
	assert AF.g_lTorpWatch == []


def test_pulse_line_offset_target_and_unavailable():
	App, AF, core, clock, pT, pTarget = pulse_scene()
	pTarget.pos = [20.0, 20.0, 0.0]
	pT.GetVelocityTG = lambda: _P(0.0, 10.0, 0.0)
	AF.OnTorpedoLaunched(FakeObj(), FakeEvent(pT))
	l = pulse_lines(core)
	assert len(l) == 1 and "vel-target 45.0 deg" in l[0] and "vel-weapon 90.0 deg" in l[0] and "weapon-target 45.0 deg" in l[0], l
	App, AF, core, clock, pT, pTarget = pulse_scene()
	App.ShipClass_GetObjectByID = lambda n, i: None
	AF.OnTorpedoLaunched(FakeObj(), FakeEvent(pT))
	l = pulse_lines(core)
	assert len(l) == 1 and l[0].endswith("dist ? km vel-target ? deg vel-point ? deg weapon-target ? deg vel-weapon ? deg w-h ? deg w-v ? deg"), l


def test_pulse_line_rate_limited_per_module():
	App, AF, core, clock, pT, pTarget = pulse_scene()
	AF.OnTorpedoLaunched(FakeObj(), FakeEvent(pT))
	clock[0] = 0.5
	AF.OnTorpedoLaunched(FakeObj(), FakeEvent(pT))
	assert len(pulse_lines(core)) == 1
	pT.GetModuleName = lambda: "Tactical.Projectiles.ScimitarPulse"
	AF.OnTorpedoLaunched(FakeObj(), FakeEvent(pT))
	assert len(pulse_lines(core)) == 2
	clock[0] = 1.2
	pT.GetModuleName = lambda: "Tactical.Projectiles.PulsePhaser"
	AF.OnTorpedoLaunched(FakeObj(), FakeEvent(pT))
	assert len(pulse_lines(core)) == 3


def test_pulse_line_session_cap():
	App, AF, core, clock, pT, pTarget = pulse_scene()
	for i in range(100):
		clock[0] = i * 2.0
		AF.OnTorpedoLaunched(FakeObj(), FakeEvent(pT))
	assert len(pulse_lines(core)) == 80


def test_pulse_line_absent_when_debug_off():
	App, AF, core, clock, pT, pTarget = pulse_scene()
	AF.g_bDebug = 0
	AF.OnTorpedoLaunched(FakeObj(), FakeEvent(pT))
	assert pulse_lines(core) == []


def test_pulse_line_foreign_projectile_ignored():
	App, AF, core, clock, pT, pTarget = pulse_scene()
	pT.p = 99
	AF.OnTorpedoLaunched(FakeObj(), FakeEvent(pT))
	assert pulse_lines(core) == []


def Dist(l):
	return ((l[0] - 20.0) ** 2 + l[1] ** 2 + l[2] ** 2) ** 0.5


def test_closest_time_in_summary():
	App, AF, core, clock, pT, pTarget = prediction_scene()
	# the mock points have no Subtract/Length: measure the distance to (20, 0, 0) here
	AF.TorpMeasure = lambda p: (5, Dist(pT.pos), 1.0)
	AF.OnTorpedoLaunched(FakeObj(), FakeEvent(pT))
	clock[0] = 1.0
	pT.pos = [10.0, 0.0, 0.0]
	AF.TorpFollowUp()
	clock[0] = 2.0
	pT.pos = [19.0, 0.0, 0.0]
	AF.TorpFollowUp()
	clock[0] = 2.5
	pT.pos = [19.0, 4.0, 0.0]	# moving away: the closest time stays 2.0
	AF.TorpFollowUp()
	App.Torpedo_GetObjectByID = lambda n, i: None
	clock[0] = 2.6
	AF.TorpFollowUp()
	l = [x[1] for x in core.logs if x[1].startswith("Torpedo 70 ended")]
	assert len(l) == 1, l
	assert " at 2.0 s (predicted arrival 2.0 s)" in l[0], l


def test_summary_with_15_field_entry():
	App, AF, core, clock, pT, pTarget = prediction_scene()
	lE = [70, 5, 0.0, 1.0, 1.0, 0.0, 0, 5, None, "m", None, None, 0.0, None, None]
	s = AF.TorpSummary(lE, 1.0)
	assert "closest 1.00 km" in s and "closest 1.00 km at" not in s and "(predicted arrival" not in s, s


def decision_scene(bDebug=1):
	import test_torpedo_arc as TT
	App, AF, core, ship, target, torps, S = TT.rule3(TorpedoArcHysteresis=0)
	AF.g_bDebug = bDebug
	AF.g_tTorpDecision = None
	clock = [5.0]
	App.g_kUtopiaModule.GetGameTime = lambda: clock[0]
	return TT, AF, core, ship, target, torps, clock


def score(AF, ship, torps, target, bSec=0):
	return AF.ArcScore(ship, torps, torps.lChildren[0], target, None, "torpedo", 1, None, None, bSec)


def test_decision_stored_for_allowed_tube():
	TT, AF, core, ship, target, torps, clock = decision_scene()
	TT.place(target, 0.4, 40.0)	# 12 degrees to the side, far band 50 percent
	assert score(AF, ship, torps, target, 1) > 0.0
	t = AF.g_tTorpDecision
	assert t != None and t[0] == 5.0 and t[1] == target.GetObjID() and t[7] == 1, t
	assert abs(t[2] - 40.0) < 0.5 and t[3] == 50.0, t
	assert abs(t[4] - 12.0) < 0.2 and abs(abs(t[5]) - 12.0) < 0.2 and abs(t[6]) < 0.2, t


def test_decision_not_stored_when_not_allowed_or_blocked():
	TT, AF, core, ship, target, torps, clock = decision_scene()
	TT.place(target, 0.8, 40.0)	# 80 percent > 50
	assert score(AF, ship, torps, target) == 0.0
	assert AF.g_tTorpDecision == None
	TT.place(target, 0.4, 40.0)
	AF.FlightBlocked = lambda *a: 1
	assert score(AF, ship, torps, target) == 0.0
	assert AF.g_tTorpDecision == None


def test_decision_not_stored_when_debug_off():
	TT, AF, core, ship, target, torps, clock = decision_scene(0)
	TT.place(target, 0.4, 40.0)
	assert score(AF, ship, torps, target) > 0.0
	assert AF.g_tTorpDecision == None


def test_decision_same_instant_keeps_larger_angle():
	TT, AF, core, ship, target, torps, clock = decision_scene()
	TT.place(target, 0.4, 40.0)
	score(AF, ship, torps, target)
	TT.place(target, 0.2, 40.0)
	score(AF, ship, torps, target)
	assert abs(AF.g_tTorpDecision[4] - 12.0) < 0.2, AF.g_tTorpDecision
	clock[0] = 5.5
	score(AF, ship, torps, target)
	assert AF.g_tTorpDecision[0] == 5.5 and abs(AF.g_tTorpDecision[4] - 6.0) < 0.2, AF.g_tTorpDecision


def test_launch_line_decision_text():
	App, AF, core, clock, pT, pTarget = tube_scene([_Tube((0.0, 0.0, 0.0), X, Y, Z)], [])
	clock[0] = 10.0
	AF.g_tTorpDecision = (9.5, 5, 55.0, 90.0, 28.4, 20.0, -10.0, 1)
	AF.OnTorpedoLaunched(FakeObj(), FakeEvent(pT))
	l = [x[1] for x in core.logs if x[1].startswith("Torpedo launched")]
	assert len(l) == 1 and l[0].endswith(" decision 0.50 s ago ang 28.4 h 20.0 v -10.0 depth 55.0% allowed 90.0% tgt 5 sec 1"), l
	AF.g_tTorpDecision = None
	AF.OnTorpedoLaunched(FakeObj(), FakeEvent(pT))
	l = [x[1] for x in core.logs if x[1].startswith("Torpedo launched")]
	assert len(l) == 2 and l[1].endswith(" decision none"), l


def test_stop_clears_decision():
	App, AF, core, ship = base.setup()
	AF.g_tTorpDecision = (1.0, 5, 55.0, 90.0, 28.4, 20.0, -10.0, 0)
	AF.Stop()
	assert AF.g_tTorpDecision == None


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
