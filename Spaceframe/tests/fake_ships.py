"""Fake ships, subsystems and shields shared by the characterization tests
(AblativeArmor, MVShields, core lifecycle). Not a test file itself."""
import builtins
import os
import sys
import types
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mock_app

builtins.reload = lambda m: m
builtins.apply = lambda f, a: f(*a)

g_iNextID = [1000]


def next_id():
	g_iNextID[0] = g_iNextID[0] + 1
	return g_iNextID[0]


class FakeSub:
	"""A ship subsystem with a condition (also used as the hull)."""
	def __init__(self, iID, sName, fMax, fCond=None, fComplexity=1.0):
		self.iID = iID
		self.sName = sName
		self.fMax = fMax
		self.fCond = fMax
		if fCond != None:
			self.fCond = fCond
		self.fComplexity = fComplexity
		self.lChildren = []
		self.bRaise = 0		# GetCondition raises (a broken subsystem)
		self.sets = []		# every SetCondition value
		self.parent = None

	def GetObjID(self):
		return self.iID

	def GetName(self):
		return self.sName

	def GetCondition(self):
		if self.bRaise:
			raise RuntimeError("broken subsystem " + self.sName)
		return self.fCond

	def SetCondition(self, f):
		self.sets.append(f)
		self.fCond = f

	def GetMaxCondition(self):
		return self.fMax

	def GetConditionPercentage(self):
		return self.fCond / self.fMax

	def GetRepairComplexity(self):
		return self.fComplexity

	def GetNumChildSubsystems(self):
		return len(self.lChildren)

	def GetChildSubsystem(self, i):
		return self.lChildren[i]

	def SetParentShip(self, pShip):
		self.parent = pShip

	def GetProperty(self):
		return self

	def GetPosition(self):
		return mock_app.Point(1.0, 2.0, 3.0)

	def GetPosition2D(self):
		return mock_app.Point(10.0, 20.0, 0.0)


class FakeProp:
	"""What App.HullProperty_Create returns: records the setters."""
	def __init__(self, sName):
		self.sName = sName
		self.fMax = 0.0
		self.d = {}

	def SetMaxCondition(self, f):
		self.fMax = f

	def __getattr__(self, name):
		if name.startswith("Set"):
			def setter(*a):
				self.d[name] = a
			return setter
		raise AttributeError(name)


class FakeRepair:
	def __init__(self, fPoints=10.0, fPercent=0.5):
		self.fPoints = fPoints
		self.fPercent = fPercent
		self.added = []
		self.listed = []

	def GetProperty(self):
		return self

	def GetMaxRepairPoints(self):
		return self.fPoints

	def GetConditionPercentage(self):
		return self.fPercent

	def AddSubsystem(self, p):
		self.added.append(p)

	def AddToRepairList(self, p):
		self.listed.append(p)


class FakeShields:
	"""Six shield facings; SetCurShields writes are recorded."""
	def __init__(self, lMax, lCur, bOn=1, bDisabled=0):
		self.lMax = lMax
		self.lCur = lCur
		self.bOn = bOn
		self.bDisabled = bDisabled
		self.writes = []

	def IsOn(self):
		return self.bOn

	def IsDisabled(self):
		return self.bDisabled

	def GetProperty(self):
		return self

	def GetMaxShields(self, i):
		return self.lMax[i]

	def GetCurShields(self, i):
		return self.lCur[i]

	def SetCurShields(self, i, f):
		self.writes.append((i, f))
		self.lCur[i] = f


class FakeShip:
	"""Hull + subsystems [(name, max)] + optional shields and repair system."""
	def __init__(self, sName="Galaxy", iID=1, fHull=1000.0, lSubs=None, shields=None, repair=1):
		self.sName = sName
		self.iID = iID
		self.dead = 0
		self.dying = 0
		self.hull = FakeSub(next_id(), "Hull", fHull)
		self.lSubs = []
		for t in (lSubs or []):
			self.lSubs.append(FakeSub(next_id(), t[0], t[1]))
		self.shields = shields
		self.repair = None
		if repair:
			self.repair = FakeRepair()

	def GetObjID(self):
		return self.iID

	def GetName(self):
		return self.sName

	def GetScript(self):
		return "ships." + self.sName

	def IsDead(self):
		return self.dead

	def IsDying(self):
		return self.dying

	def GetHull(self):
		return self.hull

	def GetShields(self):
		return self.shields

	def GetRepairSubsystem(self):
		return self.repair

	def AddSubsystem(self, p):
		self.lSubs.append(p)

	def StartGetSubsystemMatch(self, iType):
		return list(self.lSubs)

	def GetNextSubsystemMatch(self, kIter):
		if len(kIter) == 0:
			return None
		return kIter.pop(0)

	def EndGetSubsystemMatch(self, kIter):
		pass

	def Sub(self, sName):
		for p in self.lSubs:
			if p.sName == sName:
				return p
		return None

	def Armors(self):
		return [p for p in self.lSubs if p.sName == "Ablative Armor"]


def install_armor_api(App):
	App.CT_SHIP_SUBSYSTEM = 1
	App.HullProperty_Create = lambda sName: FakeProp(sName)
	App.HullClass_Create = lambda p: FakeSub(next_id(), p.sName, p.fMax)


def register_config(sModule, **kw):
	"""Registers Custom.Spaceframe.Modules.<sModule>.Config with the given
	attributes; returns the config module."""
	for n in ("Custom", "Custom.Spaceframe", "Custom.Spaceframe.Modules",
			"Custom.Spaceframe.Modules." + sModule):
		if n not in sys.modules:
			sys.modules[n] = types.ModuleType(n)
	sys.modules["Custom"].Spaceframe = sys.modules["Custom.Spaceframe"]
	sys.modules["Custom.Spaceframe"].Modules = sys.modules["Custom.Spaceframe.Modules"]
	setattr(sys.modules["Custom.Spaceframe.Modules"], sModule, sys.modules["Custom.Spaceframe.Modules." + sModule])
	cfg = types.ModuleType("Custom.Spaceframe.Modules." + sModule + ".Config")
	for k in kw.keys():
		setattr(cfg, k, kw[k])
	sys.modules["Custom.Spaceframe.Modules." + sModule + ".Config"] = cfg
	sys.modules["Custom.Spaceframe.Modules." + sModule].Config = cfg
	return cfg


def run(g):
	"""Runs every test_* function in globals g (see the other test files)."""
	failed = 0
	names = [n for n in sorted(g) if n.startswith("test_")]
	for n in names:
		try:
			g[n]()
			print("PASS " + n)
		except Exception as e:
			failed = failed + 1
			print("FAIL " + n + ": " + type(e).__name__ + " " + str(e)[:160])
	print(str(len(names) - failed) + "/" + str(len(names)) + " passed")
	return failed


def near(a, b, fTol=0.001):
	return abs(a - b) <= fTol
