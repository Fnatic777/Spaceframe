###############################################################################
#	Status HUD
#	Spaceframe module, version 0.12
#
#	Adds a status line to the ship panels of the tactical HUD, right above
#	the hull bar:
#	  - "Hull NN%" on the right, for every ship;
#	  - for ships with ablative armor (AblativeArmor module): "Armor NN%" on
#	    the left, and a white armor bar over the hull bar.
#	It works on two panels:
#	  - the player's panel ("Shields"): grows upwards; the other panels of
#	    the same row grow with it, so the row keeps an even top edge;
#	  - the target's panel ("Target Shields"): grows downwards and pushes
#	    the panels below it (the "Targets" list) down if they would overlap.
#	The game moves these panels itself (crew menus): the module follows
#	where the game puts them and only adds its extra height.
#	While the AutoFire module is on, "AUTO" shows in the top right corner
#	of the weapons panel.
#	Each panel grows by a fixed amount (one line, partly taken from the
#	space the game already leaves there) for the whole battle, the same
#	with or without armor and with or without a target, and goes back to
#	its original size at the end of the battle.
#
#	Written for Python 1.5.2 (Bridge Commander's interpreter):
#	no "+=", no list comprehensions, no True/False, and no "continue"
#	inside a "try" block.
###############################################################################
import App
import sys

NAME = "StatusHUD"
ICON_SOLID = 200	# solid LCARS icon, the same one the power bars use
EPSILON = 0.0005	# smallest size or position change worth applying
MOVE_TOLERANCE = 0.003	# a pane further than this from where we left it
			# was moved by the game

g_pCore = None		# the Spaceframe core, set in Start()
g_pPlayerPanel = None	# HUD for the player's ship display
g_pTargetPanel = None	# HUD for the target's ship display
g_pAutoText = None	# "AUTO" on the weapons panel while Auto Fire is on
g_pAutoPane = None	# the weapons panel holding it
g_iAutoShown = 0	# 1 while "AUTO" is shown
g_sAutoPointer = ""	# its address, to find it on the panel (IsChildOf)
g_iAutoShipID = None	# player ship it was made for (if no address)
AUTOFIRE_TAG = "AUTO"
AUTOFIRE_COLOR = (0.1, 0.85, 0.2)	# the green of the weapons panel
AUTOFIRE_MARGIN = 0.003

g_iShowHull = 1
g_iShowArmor = 1
g_iShowTarget = 1
g_iExpand = 1
g_iExpandRow = 1
g_fPlayerLineSpace = 1.3
g_fTargetLineSpace = 1.5
g_fBarHeight = 1.0


###############################################################################
#	Helpers
###############################################################################
def GetConfig():
	import Custom.Spaceframe.Modules.StatusHUD.Config
	return Custom.Spaceframe.Modules.StatusHUD.Config


def GetWhite():
	kWhite = App.TGColorA()
	kWhite.SetRGBA(1.0, 1.0, 1.0, 1.0)
	return kWhite


def SetPaneSize(pPane, fWidth, fHeight):
	# Window panes use SetFixedSize; plain panes use Resize.
	try:
		pPane.SetFixedSize(fWidth, fHeight, 0)
	except:
		pPane.Resize(fWidth, fHeight, 0)
	try:
		pPane.InteriorChangedSize()
	except:
		pass


def PlaceText(pText, fLeft, fTop):
	# Moves and shows a text only when needed (touching it every cycle can
	# make it flicker).
	if (abs(pText.GetLeft() - fLeft) > EPSILON) or (abs(pText.GetTop() - fTop) > EPSILON):
		pText.SetPosition(fLeft, fTop, 0)
	try:
		if not pText.IsVisible():
			pText.SetVisible(0)
	except:
		pText.SetVisible(0)


def GetTCW():
	return App.TacticalControlWindow_GetTacticalControlWindow()


def GetArmorInfo(pShip):
	# (armor now, armor capacity, armor subsystem or None), or None.
	pArmorModule = g_pCore.GetModule("AblativeArmor")
	if pArmorModule == None:
		return None
	try:
		return pArmorModule.GetArmorInfo(pShip)
	except:
		return None


###############################################################################
#	A pane we resize or move, following the game when the game moves it
###############################################################################
class Tracked:
	def __init__(self, pPane, iAnchorBottom):
		self.pPane = pPane
		self.iAnchorBottom = iAnchorBottom	# 1 = bottom edge stays, 0 = top edge
		self.lSet = None	# [height, top] we last set, None = untouched
		self.ReadNatural()

	def ReadNatural(self):
		pPane = self.pPane
		self.fWidth = pPane.GetWidth()
		self.fHeight = pPane.GetHeight()
		self.fTop = pPane.GetTop()
		self.fBottom = self.fTop + self.fHeight

	def Sync(self):
		# If the game changed the pane since we last set it, take the game's
		# size and position as the new natural ones.
		pPane = self.pPane
		if self.lSet == None:
			self.ReadNatural()
			return
		fHeight = pPane.GetHeight()
		fTop = pPane.GetTop()
		if abs(fHeight - self.lSet[0]) > MOVE_TOLERANCE:
			self.fHeight = fHeight
			self.lSet[0] = fHeight
		if abs(fTop - self.lSet[1]) > MOVE_TOLERANCE:
			self.fTop = fTop
			self.fBottom = fTop + fHeight
			if self.iAnchorBottom:
				self.fTop = self.fBottom - self.fHeight
			else:
				self.fBottom = self.fTop + self.fHeight
			self.lSet[1] = fTop
		self.fWidth = pPane.GetWidth()

	def Apply(self, fExtraHeight, fShift):
		# Natural height + fExtraHeight; top edge shifted down by fShift (or
		# moved up to keep the bottom edge). Returns 1 if anything changed.
		pPane = self.pPane
		fHeight = self.fHeight + fExtraHeight
		if self.iAnchorBottom:
			fTop = self.fBottom - fHeight
		else:
			fTop = self.fTop + fShift
		iChanged = 0
		if abs(pPane.GetHeight() - fHeight) > EPSILON:
			SetPaneSize(pPane, self.fWidth, fHeight)
			iChanged = 1
		if abs(pPane.GetTop() - fTop) > EPSILON:
			pPane.SetPosition(pPane.GetLeft(), fTop, 0)
			iChanged = 1
		self.lSet = [pPane.GetHeight(), pPane.GetTop()]
		return iChanged

	def Restore(self):
		self.Sync()
		if self.lSet != None:
			self.Apply(0.0, 0.0)
		self.lSet = None


###############################################################################
#	One ship panel (the player's or the target's)
###############################################################################
class Panel:
	def __init__(self, sGetter, iGrowUp):
		self.sGetter = sGetter	# TacticalControlWindow method for the display
		self.iGrowUp = iGrowUp	# 1 = grow upwards, 0 = grow downwards
		self.pDisplay = None	# the ship display we changed
		self.pTracked = None	# Tracked for the ship display
		self.pGaugeTracked = None	# Tracked for its hull bar
		self.lOthers = []	# Tracked for the other panels we resize or push
		self.pBar = None	# armor bar (gauge or icon)
		self.iBarObject = None	# ObjID of the armor subsystem the gauge shows
		self.lBarGeom = None	# bar size and position currently set
		self.pArmorText = None
		self.pHullText = None
		self.dTexts = {}	# label -> text currently shown
		self.sShown = None	# what was last drawn (see Redraw)

	def GetDisplay(self):
		try:
			return getattr(GetTCW(), self.sGetter)()
		except:
			return None

	# --- texts -----------------------------------------------------------
	def NewText(self):
		pText = App.TGParagraph_Create("")
		try:
			pText.SetColor(GetWhite())
		except:
			pass
		self.pDisplay.AddChild(pText, 0.0, 0.0, 0)
		return pText

	def SetText(self, pText, sLabel, fFraction):
		iPercent = int(fFraction * 100.0 + 0.5)
		if iPercent < 0:
			iPercent = 0
		if iPercent > 100:
			iPercent = 100
		sText = sLabel + " " + str(iPercent) + "%"
		# Only touch the text when it actually changes.
		if self.dTexts.get(sLabel) == sText:
			return
		self.dTexts[sLabel] = sText
		pText.SetString(sText)
		try:
			pText.RecalcBounds()
		except:
			pass

	# --- layout ----------------------------------------------------------
	def FindOthers(self, pDisplay):
		# Player panel: panels in the same row (same bottom edge), which grow
		# with it. Target panel: the panels of the left column that may sit
		# below it (the "Targets" list, the radar), pushed down if needed.
		lOthers = []
		pTCW = GetTCW()
		fBottom = pDisplay.GetTop() + pDisplay.GetHeight()
		if self.iGrowUp:
			if not g_iExpandRow:
				return lOthers
			lGetters = ("GetWeaponsControl", "GetWeaponsDisplay")
		else:
			lGetters = ("GetTargetMenu", "GetRadarDisplay", "GetRadarToggle")
		for sGetter in lGetters:
			if sGetter != self.sGetter:
				try:
					pPane = getattr(pTCW, sGetter)()
					if pPane != None:
						bMatch = 1
						if self.iGrowUp:
							bMatch = (abs(pPane.GetTop() + pPane.GetHeight() - fBottom) < 0.005)
						if bMatch:
							lOthers.append(Tracked(pPane, self.iGrowUp))
				except:
					pass
		return lOthers

	def Layout(self, pGauge, fAbove, fBelow):
		# Grows the panel by fAbove (space above the hull bar, for the
		# status line) plus fBelow (space below it; currently always 0),
		# and places the hull bar.
		# The game moves these panels itself (for example when a crew menu
		# opens), so nothing is kept at a fixed place: each pane remembers
		# only its natural size and its anchor edge, and follows the game
		# whenever the game moves it.
		pDisplay = self.pDisplay
		if self.pTracked == None:
			self.pTracked = Tracked(pDisplay, self.iGrowUp)
			self.lOthers = self.FindOthers(pDisplay)
		if self.pGaugeTracked == None:
			self.pGaugeTracked = Tracked(pGauge, 0)
		fExtra = fAbove + fBelow
		if not g_iExpand:
			fExtra = 0.0
			fAbove = 0.0

		pTracked = self.pTracked
		pTracked.Sync()
		pTracked.Apply(fExtra, 0.0)

		if self.iGrowUp:
			# Same row: grow by the same amount, upwards.
			for pOther in self.lOthers:
				try:
					pOther.Sync()
					pOther.Apply(fExtra, 0.0)
				except:
					pass
		else:
			# Panes below the target panel: pushed down only as far as needed
			# not to overlap it (or each other), from where the game put them.
			fDisplayTop = pDisplay.GetTop()
			fLeft = pDisplay.GetLeft()
			fRight = fLeft + pDisplay.GetWidth()
			fFloor = fDisplayTop + pDisplay.GetHeight()
			fMiddle = fDisplayTop + pTracked.fHeight * 0.5
			lBelow = []
			for pOther in self.lOthers:
				try:
					pOther.Sync()
					pPane = pOther.pPane
					bBelow = (pOther.fTop >= fMiddle) and (pPane.GetLeft() < fRight) and (pPane.GetLeft() + pPane.GetWidth() > fLeft)
					if bBelow:
						lBelow.append((pOther.fTop, len(lBelow), pOther))
					else:
						pOther.Apply(0.0, 0.0)
				except:
					pass
			lBelow.sort()
			for tEntry in lBelow:
				pOther = tEntry[2]
				fPush = fFloor - pOther.fTop
				if fPush < 0.0:
					fPush = 0.0
				try:
					pOther.Apply(0.0, fPush)
					fFloor = pOther.fTop + fPush + pOther.fHeight
				except:
					pass

		pGaugeTracked = self.pGaugeTracked
		pGaugeTracked.Sync()
		if pGaugeTracked.Apply(0.0, fAbove):
			try:
				pDisplay.Layout()
			except:
				pass

	def Restore(self):
		# Gives every pane back its natural size, where the game has it now.
		lTracked = []
		if self.pGaugeTracked != None:
			lTracked.append(self.pGaugeTracked)
		if self.pTracked != None:
			lTracked.append(self.pTracked)
		lTracked = lTracked + self.lOthers
		for pTracked in lTracked:
			try:
				pTracked.Restore()
			except:
				pass
		if self.pDisplay != None:
			try:
				self.pDisplay.Layout()
			except:
				pass
		self.pTracked = None
		self.pGaugeTracked = None
		self.lOthers = []

	# --- armor bar -------------------------------------------------------
	def UpdateBar(self, pGauge, tArmor):
		pDisplay = self.pDisplay
		fNow, fMax, pArmor = tArmor
		if pArmor != None:
			# Subsystem mode: a game gauge bound to the armor subsystem,
			# updated live by the game.
			if (self.pBar != None) and (self.iBarObject == None):
				self.DeleteBar()
			if self.pBar == None:
				self.pBar = App.STFillGauge_Create()
				self.pBar.SetFillColor(GetWhite())
				kClear = App.TGColorA()
				kClear.SetRGBA(0.0, 0.0, 0.0, 0.0)
				self.pBar.SetEmptyColor(kClear)
				pDisplay.AddChild(self.pBar, 0.0, 0.0, 0)
				try:
					pDisplay.MoveToFront(self.pBar)
				except:
					pass
			iID = pArmor.GetObjID()
			if self.iBarObject != iID:
				self.pBar.SetObject(pArmor)
				self.iBarObject = iID
			fWidth = pGauge.GetWidth()
		else:
			# Internal armor: a plain white icon sized to the armor level.
			if (self.pBar != None) and (self.iBarObject != None):
				self.DeleteBar()
			if self.pBar == None:
				pMode = App.GraphicsModeInfo_GetCurrentMode()
				self.pBar = App.TGIcon_Create(pMode.GetLcarsString(), ICON_SOLID, GetWhite())
				pDisplay.AddChild(self.pBar, 0.0, 0.0, 0)
				try:
					pDisplay.MoveToFront(self.pBar)
				except:
					pass
			fWidth = pGauge.GetWidth() * fNow / fMax

		if fNow <= 0.0:
			self.pBar.SetNotVisible(0)
			return
		lGeom = [fWidth, pGauge.GetHeight() * g_fBarHeight, pGauge.GetLeft(), pGauge.GetTop()]
		if lGeom != self.lBarGeom:
			self.lBarGeom = lGeom
			self.pBar.Resize(lGeom[0], lGeom[1], 0)
			self.pBar.SetPosition(lGeom[2], lGeom[3], 0)
			if pArmor == None:
				try:
					pDisplay.Layout()
				except:
					pass
		self.pBar.SetVisible(0)

	def DeleteBar(self):
		self.DeleteChild(self.pBar)
		self.pBar = None
		self.iBarObject = None
		self.lBarGeom = None

	def DeleteChild(self, pChild):
		if (pChild != None) and (self.pDisplay != None):
			try:
				self.pDisplay.DeleteChild(pChild)
			except:
				try:
					pChild.SetNotVisible(0)
				except:
					pass

	# --- main ------------------------------------------------------------
	def LineSpace(self, pText):
		# How much the panel grows: one line, partly taken from the empty
		# space the game leaves between the ship picture and the hull bar,
		# which is not the same on both panels.
		fSpace = g_fTargetLineSpace
		if self.iGrowUp:
			fSpace = g_fPlayerLineSpace
		fAbove = pText.GetHeight() * fSpace
		if fAbove < 0.0:
			fAbove = 0.0
		return fAbove

	def Redraw(self, sShown):
		# The game redraws a ship panel only when something of its own
		# changes (a target change, hull damage, a screen change), so lines
		# we add or show could stay invisible for a while. When the ship or
		# the lines shown change (not their numbers, which the game draws
		# on its own), ask the panel to lay itself out again. Kept to those
		# moments: laying a panel out too often makes its texts flicker.
		if sShown == self.sShown:
			return
		self.sShown = sShown
		pDisplay = self.pDisplay
		if pDisplay == None:
			return
		try:
			pDisplay.Layout()
		except:
			pass

	def HideAll(self, pGauge):
		# No ship to show (no target, for example): the texts and the bar
		# are hidden, but the panel keeps its size, so it never jumps.
		if self.pHullText == None:
			# Only used to measure the line height.
			self.pHullText = self.NewText()
			self.SetText(self.pHullText, "Hull", 1.0)
		self.pHullText.SetNotVisible(0)
		if self.pArmorText != None:
			self.pArmorText.SetNotVisible(0)
		if self.pBar != None:
			self.pBar.SetNotVisible(0)
		self.Layout(pGauge, self.LineSpace(self.pHullText), 0.0)
		self.Redraw("")

	def Update(self, pShip):
		pDisplay = self.GetDisplay()
		if pDisplay == None:
			self.Clear()
			return
		self.pDisplay = pDisplay
		pGauge = pDisplay.GetHealthGauge()
		if pGauge == None:
			return
		if pShip == None:
			self.HideAll(pGauge)
			return

		tArmor = None
		if g_iShowArmor:
			tArmor = GetArmorInfo(pShip)
			if (tArmor != None) and (tArmor[1] <= 0.0):
				tArmor = None

		if (tArmor == None) and (not g_iShowHull):
			self.HideAll(pGauge)
			return

		# One status line right above the hull bar: "Armor NN%" on the left
		# (armored ships only) and "Hull NN%" on the right. The panel grows
		# by the same amount for every ship, so its size never changes
		# while the line is shown.
		pLineText = None
		if tArmor != None:
			if self.pArmorText == None:
				self.pArmorText = self.NewText()
			self.SetText(self.pArmorText, "Armor", tArmor[0] / tArmor[1])
			pLineText = self.pArmorText
		elif self.pArmorText != None:
			self.pArmorText.SetNotVisible(0)
		if g_iShowHull:
			if self.pHullText == None:
				self.pHullText = self.NewText()
			fHull = 0.0
			try:
				fHull = pShip.GetHull().GetConditionPercentage()
			except:
				pass
			self.SetText(self.pHullText, "Hull", fHull)
			pLineText = self.pHullText

		self.Layout(pGauge, self.LineSpace(pLineText), 0.0)

		fLeft = pGauge.GetLeft()
		fRight = fLeft + pGauge.GetWidth()
		if tArmor != None:
			PlaceText(self.pArmorText, fLeft, pGauge.GetTop() - self.pArmorText.GetHeight())
		if g_iShowHull:
			PlaceText(self.pHullText, fRight - self.pHullText.GetWidth(), pGauge.GetTop() - self.pHullText.GetHeight())

		if tArmor != None:
			self.UpdateBar(pGauge, tArmor)
		elif self.pBar != None:
			self.pBar.SetNotVisible(0)

		# Which ship and which lines, not the numbers.
		sShown = str(pShip.GetObjID())
		if tArmor != None:
			sShown = sShown + "|armor"
		if g_iShowHull:
			sShown = sShown + "|hull"
		self.Redraw(sShown)

	def Clear(self):
		# Removes everything we added and restores the panels.
		self.DeleteChild(self.pArmorText)
		self.DeleteChild(self.pHullText)
		self.DeleteBar()
		self.Restore()
		self.pArmorText = None
		self.pHullText = None
		self.dTexts = {}
		self.sShown = None
		self.pDisplay = None


###############################################################################
#	Ships shown on each panel
###############################################################################
def GetPlayerTarget(pPlayer):
	# The player's current target, as soon as it is selected, like the
	# picture on the game's target panel. (The sensors are not checked:
	# the panel shows the target before the sensors identify it.)
	try:
		pTarget = App.ShipClass_Cast(pPlayer.GetTarget())
		if pTarget == None:
			return None
		if pTarget.IsDead() or pTarget.IsDying():
			return None
		return pTarget
	except:
		return None


def GetAutoFireOn():
	try:
		pModule = g_pCore.GetModule("AutoFire")
		if pModule != None:
			return pModule.IsEnabled()
	except:
		pass
	return 0


def GetPointer(pObject):
	# The game object's address, from the Python wrapper ("_1a2b3c_p_Type"
	# -> "_1a2b3c"): two wrappers of the same object give the same address.
	sThis = str(getattr(pObject, "this", ""))
	for i in range(1, len(sThis) - 2):
		if sThis[i:i + 3] == "_p_":
			return sThis[:i]
	return sThis


def IsChildOf(sText, pPane):
	# 1 if the text is still on the panel. The game destroys every child
	# of the weapons panel when it rebuilds it (a new player ship, or the
	# end of the battle); using a destroyed text crashes the game, so it
	# is looked for, by its address (taken when it was made), among the
	# panel's children (only the live panel is asked) before it is touched.
	if sText == "":
		return 0
	pChild = pPane.GetFirstChild()
	while pChild != None:
		if GetPointer(pChild) == sText:
			return 1
		pChild = pPane.GetNextChild(pChild)
	return 0


def GetPlayerID():
	try:
		import MissionLib
		return MissionLib.GetPlayer().GetObjID()
	except:
		return None


def TagAlive(pPane):
	# 1 if the "AUTO" text is still on the weapons panel. Without the
	# game's addresses, the panel is taken as rebuilt when the player's
	# ship changes (that is when the game rebuilds it).
	if g_sAutoPointer != "":
		return IsChildOf(g_sAutoPointer, pPane)
	return GetPlayerID() == g_iAutoShipID


def UpdateAutoFireTag():
	# While Auto Fire is on, "AUTO" shows in the top right corner of the
	# weapons panel (the one titled with the speed).
	global g_pAutoText, g_pAutoPane, g_iAutoShown, g_sAutoPointer, g_iAutoShipID
	iOn = GetAutoFireOn()
	if (not iOn) and (g_pAutoText == None):
		return
	pPane = GetTCW().GetWeaponsDisplay()
	if pPane == None:
		return
	if (g_pAutoText != None) and (not TagAlive(pPane)):
		# The game rebuilt the panel and destroyed the text: forget it.
		g_pAutoText = None
		g_pAutoPane = None
		g_iAutoShown = 0
		g_sAutoPointer = ""
		if not iOn:
			return
	# Created once per battle (Stop deletes it). The game hands out a new
	# Python object for the same panel on every call, so panels must not
	# be compared: that would rebuild the text every cycle and make it
	# flicker.
	if g_pAutoText == None:
		pText = App.TGParagraph_Create(AUTOFIRE_TAG)
		try:
			kGreen = App.TGColorA()
			kGreen.SetRGBA(AUTOFIRE_COLOR[0], AUTOFIRE_COLOR[1], AUTOFIRE_COLOR[2], 1.0)
			pText.SetColor(kGreen)
		except:
			pass
		pPane.AddChild(pText, 0.0, 0.0, 0)
		g_pAutoText = pText
		g_pAutoPane = pPane
		g_sAutoPointer = GetPointer(pText)
		g_iAutoShipID = GetPlayerID()
	if iOn:
		try:
			fWidth = pPane.GetMaximumInteriorWidth()
		except:
			fWidth = pPane.GetWidth()
		PlaceText(g_pAutoText, fWidth - g_pAutoText.GetWidth() - AUTOFIRE_MARGIN, 0.0)
	elif g_pAutoText.IsVisible():
		g_pAutoText.SetNotVisible(0)
	# The panel only redraws on its own changes: redraw it when the text
	# appears or disappears (only then, or the texts flicker).
	if iOn != g_iAutoShown:
		g_iAutoShown = iOn
		try:
			pPane.Layout()
		except:
			pass


def DeleteAutoFireTag():
	# Deletes the text only if it is still on the panel (see IsChildOf).
	global g_pAutoText, g_pAutoPane, g_iAutoShown, g_sAutoPointer, g_iAutoShipID
	if g_pAutoText != None:
		try:
			pPane = GetTCW().GetWeaponsDisplay()
			if (pPane != None) and (g_sAutoPointer != "") and IsChildOf(g_sAutoPointer, pPane):
				pPane.DeleteChild(g_pAutoText)
		except:
			pass
	g_pAutoText = None
	g_pAutoPane = None
	g_iAutoShown = 0
	g_sAutoPointer = ""
	g_iAutoShipID = None


###############################################################################
#	Spaceframe module interface
###############################################################################
def Start(pCore):
	global g_pCore, g_pPlayerPanel, g_pTargetPanel
	global g_iShowHull, g_iShowArmor, g_iShowTarget, g_iExpand, g_iExpandRow, g_fPlayerLineSpace, g_fTargetLineSpace, g_fBarHeight
	g_pCore = pCore
	import Custom.Spaceframe.Modules.StatusHUD.Config
	reload(Custom.Spaceframe.Modules.StatusHUD.Config)
	pConfig = GetConfig()
	g_iShowHull = getattr(pConfig, "ShowHull", 1)
	g_iShowArmor = getattr(pConfig, "ShowArmor", 1)
	g_iShowTarget = getattr(pConfig, "ShowTarget", 1)
	g_iExpand = getattr(pConfig, "ExpandDisplay", 1)
	g_iExpandRow = getattr(pConfig, "ExpandRow", 1)
	# Percentages in the config, fractions here.
	g_fPlayerLineSpace = float(getattr(pConfig, "PlayerLineSpace", 130)) / 100.0
	g_fTargetLineSpace = float(getattr(pConfig, "TargetLineSpace", 150)) / 100.0
	g_fBarHeight = float(getattr(pConfig, "HudBarHeight", 100)) / 100.0
	Stop()
	g_pPlayerPanel = Panel("GetShipDisplay", 1)
	g_pTargetPanel = Panel("GetEnemyShipDisplay", 0)


def Stop():
	global g_pPlayerPanel, g_pTargetPanel
	DeleteAutoFireTag()
	if g_pPlayerPanel != None:
		g_pPlayerPanel.Clear()
	if g_pTargetPanel != None:
		g_pTargetPanel.Clear()
	g_pPlayerPanel = None
	g_pTargetPanel = None


def Tick(lShips):
	if g_pPlayerPanel == None:
		return
	import MissionLib
	pPlayer = MissionLib.GetPlayer()
	if (pPlayer != None) and (pPlayer.IsDead() or pPlayer.IsDying()):
		pPlayer = None
	try:
		g_pPlayerPanel.Update(pPlayer)
	except:
		g_pCore.Log(NAME, "Player panel error: " + str(sys.exc_info()[1]))
	try:
		if g_iShowTarget:
			pTarget = None
			if pPlayer != None:
				pTarget = GetPlayerTarget(pPlayer)
			g_pTargetPanel.Update(pTarget)
		else:
			g_pTargetPanel.Clear()
	except:
		g_pCore.Log(NAME, "Target panel error: " + str(sys.exc_info()[1]))
	try:
		UpdateAutoFireTag()
	except:
		g_pCore.Log(NAME, "Auto Fire tag error: " + str(sys.exc_info()[1]))


def Diag():
	for pPanel in (g_pPlayerPanel, g_pTargetPanel):
		if pPanel != None:
			sBase = "None"
			if pPanel.pTracked != None:
				sBase = str([pPanel.pTracked.fHeight, pPanel.pTracked.fTop, pPanel.pTracked.lSet])
			print ("  " + pPanel.sGetter + ": natural/set = " + sBase + ", texts = " + str(pPanel.dTexts) + ", others = " + str(len(pPanel.lOthers)))
