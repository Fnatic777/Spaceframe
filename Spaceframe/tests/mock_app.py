"""Minimal mocks of the Bridge Commander 'App' API for off-game tests (Python 3).

Load game modules with load_module(): it reads the CRLF Python 1.5 source,
swaps dict.has_key for __contains__ and runs it against these mocks.
"""
import os
import re
import sys
import types

GAME = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts", "Custom", "Spaceframe")


class Recorder:
	def __init__(self):
		self.calls = []

	def log(self, *a):
		self.calls.append(a)

	def count(self, name):
		n = 0
		for c in self.calls:
			if c[0] == name:
				n = n + 1
		return n


# --- keyboard / events ---------------------------------------------------
class KeyboardBinding:
	GET_EVENT = 0
	GET_INT_EVENT = 1
	GET_BOOL_EVENT = 2
	GET_FLOAT_EVENT = 3

	def __init__(self):
		self.binds = {}

	def BindKey(self, iKey, iState, eType, iKind, fValue):
		self.binds[(iKey, iState)] = eType

	def ClearBinding(self, iKey, iState):
		if (iKey, iState) in self.binds:
			del self.binds[(iKey, iState)]


class TGKeyboardEvent:
	KS_NORMAL = 0
	KS_KEYDOWN = 1
	KS_KEYUP = 2


class EventManager:
	def __init__(self):
		self.handlers = []

	def AddBroadcastPythonFuncHandler(self, eType, pObj, sFunc):
		self.handlers.append((eType, pObj, sFunc))

	def RemoveBroadcastHandler(self, eType, pObj, sFunc):
		if (eType, pObj, sFunc) in self.handlers:
			self.handlers.remove((eType, pObj, sFunc))

	def count(self, eType):
		n = 0
		for h in self.handlers:
			if h[0] == eType:
				n = n + 1
		return n


class Event:
	def __init__(self, eType=0, bValue=0, pDest=None):
		self.eType = eType
		self.bValue = bValue
		self.pDest = pDest

	def GetBool(self):
		return self.bValue

	def GetEventType(self):
		return self.eType

	def GetDestination(self):
		return self.pDest

	def SetEventType(self, e):
		self.eType = e

	def SetDestination(self, d):
		self.pDest = d

	def SetInt(self, i):
		self.i = i


# --- UI -----------------------------------------------------------------
class Button:
	def __init__(self, sName, pEvent):
		self.sName = sName
		self.pEvent = pEvent
		self.bChosen = 0

	def SetChosen(self, b):
		self.bChosen = b

	def IsChosen(self):
		return self.bChosen

	def __getattr__(self, name):
		# colour setters etc.
		return lambda *a: None


class Menu:
	def __init__(self):
		self.children = []
		self.handlers = []

	def AddChild(self, p, *a):
		self.children.append(p)

	def DeleteChild(self, p):
		if p in self.children:
			self.children.remove(p)

	def AddPythonFuncHandlerForInstance(self, eType, sFunc):
		self.handlers.append((eType, sFunc))

	def RemoveHandlerForInstance(self, eType, sFunc):
		if (eType, sFunc) in self.handlers:
			self.handlers.remove((eType, sFunc))


class KeyEvent:
	def __init__(self, iChar, iState):
		self.iChar = iChar
		self.iState = iState
		self.handled = 0
		self.passed = 0

	def GetUnicode(self):
		return self.iChar

	def GetKeyState(self):
		return self.iState

	def GetEventType(self):
		return 9100

	def SetHandled(self):
		self.handled = 1


class TopWindow(Menu):
	def CallNextHandler(self, pEvent):
		pEvent.passed = 1


class TGString:
	def __init__(self, s=""):
		self.s = s

	def __eq__(self, other):
		return isinstance(other, TGString) and other.s == self.s


class Freed(Exception):
	pass


TOUCHED = []	# destroyed objects the code touched (a crash in the game)


class Text:
	def __init__(self, s):
		self.__dict__["dead"] = 0
		self.s = s
		self.this = "_%x_p_TGParagraph" % id(self)

	def __getattribute__(self, name):
		# A text the game already destroyed: touching it crashes the game.
		if (not name.startswith("__")) and object.__getattribute__(self, "dead"):
			TOUCHED.append(name)
			raise Freed("used a destroyed text")
		return object.__getattribute__(self, name)
		self.color = None
		self.visible = 1
		self.left = 0.0
		self.top = 0.0

	def SetString(self, s):
		self.s = s

	def SetColor(self, c):
		self.color = c

	def RecalcBounds(self):
		pass

	def GetWidth(self):
		return 0.01 * len(self.s)

	def GetHeight(self):
		return 0.02

	def GetLeft(self):
		return self.left

	def GetTop(self):
		return self.top

	def SetPosition(self, x, y, i=0):
		self.left = x
		self.top = y

	def IsVisible(self):
		return self.visible

	def SetVisible(self, i=0):
		self.visible = 1

	def SetNotVisible(self, i=0):
		self.visible = 0


class Color:
	def SetRGBA(self, r, g, b, a):
		self.rgba = (r, g, b, a)


class Proxy:
	def __init__(self, target):
		self.__dict__["_t"] = target

	def __getattr__(self, name):
		return getattr(self._t, name)


class ChildRef:
	# The game hands out generic UI objects for children, with the same
	# pointer string ("this") but a different type suffix.
	def __init__(self, c):
		self.this = c.this.replace("_p_TGParagraph", "_p_TGUIObject")


class WeaponsPane:
	def __init__(self):
		self.children = []
		self.layouts = 0

	def Layout(self):
		self.layouts = self.layouts + 1

	def AddChild(self, c, x=0.0, y=0.0, i=0):
		c.left = x
		c.top = y
		self.children.append(c)

	def DeleteChild(self, c):
		if c.__dict__.get("dead"):
			TOUCHED.append("DeleteChild")
			raise Freed("deleted a destroyed text")
		self.children.remove(c)

	def KillChildren(self):
		# What WeaponsDisplay.Create does when the player's ship changes.
		for c in self.children:
			c.__dict__["dead"] = 1
		self.children = []

	def GetFirstChild(self):
		if self.children:
			return ChildRef(self.children[0])
		return None

	def GetNextChild(self, pChild):
		lThis = [c.this for c in self.children]
		i = lThis.index(pChild.this)
		if i + 1 < len(self.children):
			return ChildRef(self.children[i + 1])
		return None

	def GetWidth(self):
		return 0.2

	def GetMaximumInteriorWidth(self):
		return 0.18


class Paragraph:
	def __init__(self, s):
		self.s = s

	def SetStringW(self, s):
		self.s = s


class Display:
	def __init__(self, sName="Shields"):
		self.name = TGString(sName)
		self.layouts = 0
		self.paragraph = Paragraph(self.name)

	def GetNameParagraph(self):
		return self.paragraph

	def GetName(self):
		return self.name

	def SetName(self, n):
		self.name = n

	def Layout(self):
		self.layouts = self.layouts + 1


class TCW:
	def __init__(self):
		self.menu = Menu()
		self.ship_display = Display("Shields")
		self.weapons_display = WeaponsPane()

	def GetWeaponsDisplay(self):
		# Like SWIG: a new wrapper object for the same pane on every call.
		return Proxy(self.weapons_display)

	def GetTacticalMenu(self):
		return self.menu

	def GetShipDisplay(self):
		return self.ship_display


# --- ships ----------------------------------------------------------------
SHIPS = {}


class Point:
	def __init__(self, x=0.0, y=0.0, z=0.0):
		self.x = x
		self.y = y
		self.z = z

	def SetXYZ(self, x, y, z):
		self.x = x
		self.y = y
		self.z = z

	def GetX(self):
		return self.x

	def GetY(self):
		return self.y

	def GetZ(self):
		return self.z

	def Subtract(self, o):
		self.x = self.x - o.x
		self.y = self.y - o.y
		self.z = self.z - o.z

	def Length(self):
		return (self.x * self.x + self.y * self.y + self.z * self.z) ** 0.5

	def Set(self, o):
		if not isinstance(o, Point):
			raise TypeError("Type error. Expected _p_TGPoint3")
		self.x = o.x
		self.y = o.y
		self.z = o.z

	def Add(self, o):
		self.x = self.x + o.x
		self.y = self.y + o.y
		self.z = self.z + o.z

	def Scale(self, f):
		self.x = self.x * f
		self.y = self.y * f
		self.z = self.z * f

	def Dot(self, o):
		return self.x * o.x + self.y * o.y + self.z * o.z

	def Unitize(self):
		f = self.Length()
		if f > 0:
			self.Scale(1.0 / f)
		return f

	def MultMatrixLeft(self, m):
		# m: None (no rotation) or a 3x3 list of rows; self = m * self.
		if m is None:
			return
		x = m[0][0] * self.x + m[0][1] * self.y + m[0][2] * self.z
		y = m[1][0] * self.x + m[1][1] * self.y + m[1][2] * self.z
		z = m[2][0] * self.x + m[2][1] * self.y + m[2][2] * self.z
		self.x = x
		self.y = y
		self.z = z


class Alien:
	"""A vector of another wrapper class (NiPoint3-like): only x_get/y_get/z_get."""
	def __init__(self, x=0.0, y=0.0, z=0.0):
		self.v = (x, y, z)

	def x_get(self):
		return self.v[0]

	def y_get(self):
		return self.v[1]

	def z_get(self):
		return self.v[2]


class Bank:
	"""A phaser bank: in arc, max damage distance, charge 0..1."""
	def __init__(self, fMax=100.0, fCharge=1.0, iArc=1, pPos=None):
		self.fMax = fMax
		self.fCharge = fCharge
		self.iArc = iArc
		self.pPos = pPos or Point()

	def CanHit(self, pPoint):
		return self.iArc

	def GetMaxDamageDistance(self):
		return self.fMax

	def GetChargePercentage(self):
		return self.fCharge

	def GetWorldLocation(self):
		return Point(self.pPos.x, self.pPos.y, self.pPos.z)


class Ammo:
	def __init__(self, fSpeed=100.0, sScript="Tactical.Projectiles.Photon1"):
		self.fSpeed = fSpeed
		self.sScript = sScript

	def GetLaunchSpeed(self):
		return self.fSpeed

	def GetTorpedoScript(self):
		return self.sScript


class Tube:
	def __init__(self, vDir=None, iReady=1, pPos=None):
		self.vDir = vDir or Point(1.0, 0.0, 0.0)
		self.iReady = iReady
		self.pPos = pPos or Point()

	def GetNumReady(self):
		return self.iReady

	def CalculateRoughDirection(self):
		return Point(self.vDir.x, self.vDir.y, self.vDir.z)

	def GetWorldLocation(self):
		return Point(self.pPos.x, self.pPos.y, self.pPos.z)

	# Torpedo arc: a fixed cone of +-fLim rad on two axes (identity ship
	# rotation). pPos is the tube's world point, vLocal its ship-local offset
	# (default: same as pPos). iUpSign picks the game's Up = sign * cross(Right, Dir).
	vRight = None
	vLocal = None
	fLim = 0.523598
	iUpSign = 1
	vCanHit = None	# None = same as IsInArc; "raise" = the call fails
	iArc = None	# None = the cone model; 1/0 = fixed; "raise" = fails

	def GetDirection(self):
		return Point(self.vDir.x, self.vDir.y, self.vDir.z)

	def GetRight(self):
		v = self.vRight or Point(0.0, 1.0, 0.0)
		return Point(v.x, v.y, v.z)

	def GetPosition(self):
		v = self.vLocal or self.pPos
		return Point(v.x, v.y, v.z)

	def IsInArc(self, pPoint):
		import math
		if self.iArc == "raise":
			raise TypeError("IsInArc")
		if self.iArc is not None:
			return self.iArc
		d = Point(pPoint.x - self.pPos.x, pPoint.y - self.pPos.y, pPoint.z - self.pPos.z)
		f = Point(self.vDir.x, self.vDir.y, self.vDir.z)
		v = self.vRight or Point(0.0, 1.0, 0.0)
		r = Point(v.x, v.y, v.z)
		u = Point(r.y * f.z - r.z * f.y, r.z * f.x - r.x * f.z, r.x * f.y - r.y * f.x)
		u.Scale(float(self.iUpSign))
		df = d.Dot(f)
		if df <= 0.0:
			return 0
		return int(abs(math.atan2(d.Dot(r), df)) <= self.fLim and abs(math.atan2(d.Dot(u), df)) <= self.fLim)

	def CanHit(self, pPoint):
		if self.vCanHit == "raise":
			raise TypeError("CanHit")
		if self.vCanHit is not None:
			return self.vCanHit
		return self.IsInArc(pPoint)


class Pulse:
	def __init__(self, fCharge=5.0, fMin=2.0, iArc=1, fSpeed=150.0, sModule="Tactical.Projectiles.Disruptor1"):
		self.fCharge = fCharge
		self.fMin = fMin
		self.iArc = iArc
		self.fSpeed = fSpeed
		self.sModule = sModule
		self.pPos = Point()
		self.arcPoints = []
		# Arc box for ArcDepth (radians) and its axes in ship space; "raise" in
		# limits/axes simulates the accessors failing.
		self.limits = (-0.5, 0.5, -0.5, 0.5)
		self.axes = (Point(1.0, 0.0, 0.0), Point(0.0, 1.0, 0.0), Point(0.0, 0.0, 1.0))
		Pulse.counter = Pulse.counter + 1
		self.iID = Pulse.counter

	counter = 5000

	def GetObjID(self):
		return self.iID

	def GetPosition(self):
		return Point(self.pPos.x, self.pPos.y, self.pPos.z)

	def _limit(self, i):
		if self.limits == "raise":
			raise TypeError("limits")
		return self.limits[i]

	def GetArcWidthAngleMin(self):
		return self._limit(0)

	def GetArcWidthAngleMax(self):
		return self._limit(1)

	def GetArcHeightAngleMin(self):
		return self._limit(2)

	def GetArcHeightAngleMax(self):
		return self._limit(3)

	def GetChargeLevel(self):
		return self.fCharge

	def GetMinFiringCharge(self):
		return self.fMin

	def IsInArc(self, pPoint):
		# iArc: 1/0 result, or "raise" to simulate the call failing.
		self.arcPoints.append(pPoint)
		if self.iArc == "raise":
			raise TypeError("IsInArc")
		return self.iArc

	def GetLaunchSpeed(self):
		return self.fSpeed

	def GetWorldLocation(self):
		return Point(self.pPos.x, self.pPos.y, self.pPos.z)

	def CalculateRoughDirection(self):
		return Point(1.0, 0.0, 0.0)

	def GetProperty(self):
		w = self

		class Prop:
			def GetModuleName(self):
				return w.sModule

			def _axis(self, i):
				if w.axes == "raise":
					raise TypeError("axes")
				return w.axes[i]

			def GetOrientationForward(self):
				return self._axis(0)

			def GetOrientationRight(self):
				return self._axis(1)

			def GetOrientationUp(self):
				return self._axis(2)
		return Prop()


class WeaponGroup:
	def __init__(self, lChildren):
		self.lChildren = lChildren
		self.calls = []
		self.forced = []
		self.firing = 0
		self.ammo = Ammo()
		self.available = 100
		self.torpedo = 0
		self.chains = 1
		self.pulse = 0
		self.chain = 0
		self.chain_sets = 0

	def IsFiring(self):
		return self.firing

	def GameStop(self):
		# The game stopping the group by itself (not through Auto Fire).
		self.firing = 0

	def GetNumChildSubsystems(self):
		return len(self.lChildren)

	def GetChildSubsystem(self, i):
		return self.lChildren[i]

	def StartFiring(self, pTarget, vOffset):
		self.calls.append(("start", pTarget))
		self.firing = 1

	def StopFiring(self):
		self.calls.append(("stop",))
		self.firing = 0

	def SetForceUpdate(self, i):
		# Records len(calls) at call time (not in calls: tests compare it).
		self.forced.append(len(self.calls))

	def GetNumFiringChains(self):
		return self.chains

	def GetFiringChainMode(self):
		return self.chain

	def SetFiringChainMode(self, i):
		self.chain = i
		self.chain_sets = self.chain_sets + 1

	def GetCurrentAmmoType(self):
		return self.ammo

	def GetCurrentAmmoTypeNumber(self):
		return 0

	def GetNumAvailableTorpsToType(self, i):
		return self.available

	def starts(self):
		return len([c for c in self.calls if c[0] == "start"])

	def stops(self):
		return len([c for c in self.calls if c[0] == "stop"])


class Process:
	live = []

	def __init__(self):
		self.inst = None
		Process.live.append(self)

	def SetInstance(self, i):
		self.inst = i

	def SetFunction(self, f):
		self.func = f

	def SetPriority(self, p):
		pass

	def SetDelayUsesGameTime(self, i):
		pass

	def SetDelay(self, f):
		self.delay = f


class Ship:
	RED_ALERT = 2
	YELLOW_ALERT = 1
	GREEN_ALERT = 0
	WG_PRIMARY = 0
	WG_SECONDARY = 1
	WG_TERTIARY = 2

	def __init__(self, sName="Galaxy", iID=1):
		self.sName = sName
		self.iID = iID
		SHIPS[iID] = self
		self.dead = 0
		self.alert = 2
		self.cloaked = 0
		self.target = None
		self.groups = {}
		self.pos = Point()
		self.radius = 1.0
		self.vel = Point()
		self.accel = 0.0
		self.predict = 1

	def GetObjID(self):
		return self.iID

	def GetName(self):
		return self.sName

	def IsDead(self):
		return self.dead

	def IsDying(self):
		return 0

	def GetAlertLevel(self):
		return self.alert

	def IsCloaked(self):
		return self.cloaked

	def GetTarget(self):
		return self.target

	def GetWeaponSystemGroup(self, e):
		return self.groups.get(e)

	def GetWorldLocation(self):
		return Point(self.pos.x, self.pos.y, self.pos.z)

	def GetRadius(self):
		return self.radius

	def GetVelocityTG(self):
		return Point(self.vel.x, self.vel.y, self.vel.z)

	def GetAccelerationTG(self):
		return Point()

	def GetPredictedPosition(self, p, v, a, t):
		if not self.predict:
			raise AttributeError("GetPredictedPosition")
		return Point(p.x + v.x * t, p.y + v.y * t, p.z + v.z * t)

	def GetWorldRotation(self):
		return getattr(self, "rot", None)

	def GetImpulseEngineSubsystem(self):
		ship = self

		class Engines:
			def GetMaxAccel(self):
				return ship.accel
		return Engines()

	def GetTargetOffsetTG(self):
		return Point()

	def GetContainingSet(self):
		return "set"

	def SetTarget(self, sName):
		self.target = None
		for o in SHIPS.values():
			if o.GetName() == sName:
				self.target = o


class Group:
	def __init__(self, lShips):
		self.lShips = lShips

	def GetActiveObjectTupleInSet(self, pSet):
		return tuple(self.lShips)

	def IsNameInGroup(self, sName):
		for o in self.lShips:
			if o.GetName() == sName:
				return 1
		return 0


class Mission:
	def __init__(self, lEnemies=None, lFriends=None):
		self.enemies = Group(lEnemies or [])
		self.friends = Group(lFriends or [])

	def GetEnemyGroup(self):
		return self.enemies

	def GetFriendlyGroup(self):
		return self.friends


class Core:
	"""Stand-in for Custom.Spaceframe.Spaceframe as seen by modules."""

	def __init__(self):
		self.techs = {}		# ship name -> {tech: value}
		self.modules = {}
		self.logs = []
		self.g_pMission = object()
		self.interval = 0.25
		self.ships = []

	def GetShipTech(self, pShip, sTech, pDefault=0):
		d = self.techs.get(pShip.GetName(), {})
		return d.get(sTech, pDefault)

	def GetModule(self, sName):
		return self.modules.get(sName)

	def Log(self, sModule, sText):
		self.logs.append((sModule, sText))

	def GetConfigValue(self, sName, pDefault):
		return pDefault

	# Added for the characterization tests (AblativeArmor, MVShields).
	def GetShipFileName(self, pShip):
		return pShip.GetName()

	def GetInterval(self):
		return self.interval

	def GetShipsInPlay(self):
		return [], self.ships


def make_app():
	App = types.ModuleType("App")
	App.KeyboardBinding = KeyboardBinding
	App.TGKeyboardEvent = TGKeyboardEvent
	App.g_kKeyboardBinding = KeyboardBinding()
	App.g_kEventManager = EventManager()
	App.ShipClass = Ship
	App.TGString = TGString

	class Utopia:
		def ConvertKilometersToGameUnits(self, f):
			return f / 0.175
	App.g_kUtopiaModule = Utopia()
	App.ET_KEYBOARD = 9100
	App._top = TopWindow()
	App.TopWindow_GetTopWindow = lambda: App._top
	App.TGParagraph_Create = lambda s: Text(s)
	App.TGColorA = Color
	App.PhaserBank_Cast = lambda o: (isinstance(o, Bank) and o) or None
	App.TorpedoTube_Cast = lambda o: (isinstance(o, Tube) and o) or None
	App.PulseWeapon_Cast = lambda o: (isinstance(o, Pulse) and o) or None
	App.PulseWeaponProperty_Cast = lambda o: o
	App.PulseWeaponSystem_Cast =lambda o: (isinstance(o, WeaponGroup) and o.pulse and o) or None
	App.TorpedoSystem_Cast = lambda o: (isinstance(o, WeaponGroup) and o.torpedo and o) or None
	App.PhysicsObjectClass_Cast = lambda o: o
	App.TGPoint3 = Point
	App.PI = 3.141592653589793
	App.PythonMethodProcess = Process
	SHIPS.clear()
	del TOUCHED[:]
	App.ShipClass_GetObjectByID = lambda pSet, iID: SHIPS.get(iID)
	Process.live = []

	class TSP:
		LOW = 1
	App.TimeSliceProcess = TSP
	App.NULL_ID = 0
	App.ET_INPUT_FIRE_PRIMARY = 9001
	App.ET_INPUT_FIRE_SECONDARY = 9002
	App.ET_INPUT_FIRE_TERTIARY = 9003
	App.ET_WEAPON_FIRED = 9201
	App.Weapon_Cast = lambda o: o
	App.ET_ST_BUTTON_CLICKED = 9100
	counter = [10000]

	def next_type():
		counter[0] = counter[0] + 1
		return counter[0]
	App.Game_GetNextEventType = next_type
	App._tcw = TCW()
	App.TacticalControlWindow_GetTacticalControlWindow = lambda: App._tcw
	App.TGIntEvent_Create = lambda: Event()
	App.STButton_CreateW = lambda n, e, *a: Button(n, e)
	App.STButton_Create = lambda n, e, *a: Button(n, e)
	App.STButton_Cast = lambda b: b
	App.ShipClass_Cast = lambda p: p
	App._player = [None]
	App.Game_GetCurrentPlayer = lambda: App._player[0]

	class Dbg:
		def Print(self, s):
			pass
	App.CPyDebug = lambda *a: Dbg()
	return App


def install(App):
	sys.modules["App"] = App
	ml = types.ModuleType("MissionLib")
	ml.GetPlayer = lambda: App._player[0]
	sys.modules["MissionLib"] = ml
	bu = types.ModuleType("Bridge.BridgeUtils")

	def create_button(pName, eType, iSub, pDest):
		e = Event(eType, 0, pDest)
		return Button(pName, e)
	bu.CreateBridgeMenuButton = create_button
	br = types.ModuleType("Bridge")
	br.BridgeUtils = bu
	sys.modules["Bridge"] = br
	sys.modules["Bridge.BridgeUtils"] = bu


def load_module(relpath, name):
	src = open(GAME + "/" + relpath, "rb").read().decode("ascii")
	src = src.replace("\r\n", "\n").replace(".has_key(", ".__contains__(")
	# Python 1.5 keys() is a list snapshot: allow deleting while looping over it.
	src = re.sub(r"\bin ([\w\.]+)\.keys\(\):", r"in list(\1.keys()):", src)
	mod = types.ModuleType(name)
	mod.__file__ = relpath
	sys.modules[name] = mod
	exec(compile(src, relpath, "exec"), mod.__dict__)
	return mod
