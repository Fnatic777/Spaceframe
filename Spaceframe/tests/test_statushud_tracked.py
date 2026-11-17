"""StatusHUD characterization tests: Tracked (pane layout math), Panel.LineSpace
and Panel.SetText. They pin the CURRENT behavior."""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mock_app
import fake_ships
from fake_ships import near

MOD = "Custom.Spaceframe.Modules.StatusHUD.StatusHUD"


def load():
	App = mock_app.make_app()
	mock_app.install(App)
	return mock_app.load_module("Modules/StatusHUD/StatusHUD.py", MOD)


class Pane:
	"""A window pane: size and position, SetFixedSize like the game's panes."""
	def __init__(self, fTop=0.5, fHeight=0.2, fLeft=0.1, fWidth=0.3):
		self.fTop = fTop
		self.fHeight = fHeight
		self.fLeft = fLeft
		self.fWidth = fWidth
		self.writes = 0

	def GetTop(self):
		return self.fTop

	def GetHeight(self):
		return self.fHeight

	def GetLeft(self):
		return self.fLeft

	def GetWidth(self):
		return self.fWidth

	def SetFixedSize(self, w, h, i=0):
		self.fWidth = w
		self.fHeight = h
		self.writes = self.writes + 1

	def SetPosition(self, x, y, i=0):
		self.fLeft = x
		self.fTop = y
		self.writes = self.writes + 1


class ResizePane(Pane):
	"""A plain pane: Resize only (no SetFixedSize)."""
	def __getattribute__(self, name):
		if name == "SetFixedSize":
			raise AttributeError(name)
		return object.__getattribute__(self, name)

	def Resize(self, w, h, i=0):
		self.fWidth = w
		self.fHeight = h


# --- Tracked.Apply -------------------------------------------------------------------
def test_natural_values_read_on_creation():
	H = load()
	t = H.Tracked(Pane(0.5, 0.2), 1)
	assert near(t.fHeight, 0.2) and near(t.fTop, 0.5) and near(t.fBottom, 0.7)
	assert t.lSet == None


def test_apply_anchor_top_grows_down():
	H = load()
	p = Pane(0.5, 0.2)
	t = H.Tracked(p, 0)
	assert t.Apply(0.05, 0.0) == 1
	assert near(p.fHeight, 0.25) and near(p.fTop, 0.5)
	assert near(t.lSet[0], 0.25) and near(t.lSet[1], 0.5)
	assert t.Apply(0.05, 0.0) == 0		# nothing left to change
	assert t.Apply(0.0, 0.1) == 1		# shift moves the top edge
	assert near(p.fHeight, 0.2) and near(p.fTop, 0.6)


def test_apply_anchor_bottom_grows_up():
	H = load()
	p = Pane(0.5, 0.2)
	t = H.Tracked(p, 1)
	assert t.Apply(0.05, 0.0) == 1
	assert near(p.fHeight, 0.25) and near(p.fTop, 0.45)
	assert near(p.fTop + p.fHeight, 0.7)		# bottom edge stays
	assert t.Apply(0.05, 0.0) == 0


def test_apply_anchor_bottom_ignores_shift():
	H = load()
	p = Pane(0.5, 0.2)
	t = H.Tracked(p, 1)
	t.Apply(0.0, 0.3)
	assert near(p.fTop, 0.5)


def test_apply_noop_still_records_what_is_set():
	H = load()
	t = H.Tracked(Pane(0.5, 0.2), 0)
	assert t.Apply(0.0, 0.0) == 0
	assert t.lSet != None and near(t.lSet[0], 0.2) and near(t.lSet[1], 0.5)


def test_apply_uses_resize_on_plain_panes():
	H = load()
	p = ResizePane(0.5, 0.2)
	t = H.Tracked(p, 0)
	assert t.Apply(0.05, 0.0) == 1
	assert near(p.fHeight, 0.25)


# --- Tracked.Sync ------------------------------------------------------------------------
def test_sync_before_apply_adopts_current_state():
	H = load()
	p = Pane(0.5, 0.2)
	t = H.Tracked(p, 0)
	p.fTop = 0.9
	p.fHeight = 0.4
	t.Sync()
	assert near(t.fTop, 0.9) and near(t.fHeight, 0.4)


def test_sync_ignores_our_own_changes():
	H = load()
	p = Pane(0.5, 0.2)
	for iAnchor in (0, 1):
		p = Pane(0.5, 0.2)
		t = H.Tracked(p, iAnchor)
		t.Apply(0.05, 0.0)
		t.Sync()
		assert near(t.fHeight, 0.2)		# still the natural height
		t.Apply(0.05, 0.0)
		assert near(p.fHeight, 0.25)


def test_sync_ignores_moves_within_tolerance():
	H = load()
	p = Pane(0.5, 0.2)
	t = H.Tracked(p, 0)
	t.Apply(0.05, 0.0)
	p.fTop = p.fTop + 0.002		# below MOVE_TOLERANCE (0.003)
	t.Sync()
	assert near(t.fTop, 0.5)
	p.fTop = 0.5 + 0.004
	t.Sync()
	assert near(t.fTop, 0.504)


def test_sync_adopts_game_move_anchor_top():
	H = load()
	p = Pane(0.5, 0.2)
	t = H.Tracked(p, 0)
	t.Apply(0.05, 0.0)
	p.fTop = 0.8		# the game moved it (a crew menu opened, for example)
	t.Sync()
	assert near(t.fTop, 0.8) and near(t.fBottom, 1.0)		# natural bottom = top + natural height
	t.Apply(0.05, 0.0)
	assert near(p.fTop, 0.8) and near(p.fHeight, 0.25)


def test_sync_adopts_game_move_anchor_bottom():
	H = load()
	p = Pane(0.5, 0.2)
	t = H.Tracked(p, 1)
	t.Apply(0.05, 0.0)		# top .45, height .25, bottom .7
	p.fTop = 0.8		# the game moved the pane; its bottom edge is now 1.05
	t.Sync()
	assert near(t.fBottom, 1.05) and near(t.fTop, 0.85)
	t.Apply(0.05, 0.0)
	assert near(p.fTop, 0.8) and near(p.fTop + p.fHeight, 1.05)


def test_sync_adopts_game_resize():
	H = load()
	p = Pane(0.5, 0.2)
	t = H.Tracked(p, 0)
	t.Apply(0.05, 0.0)
	p.fHeight = 0.4		# the game resized it
	t.Sync()
	assert near(t.fHeight, 0.4)
	t.Apply(0.05, 0.0)
	assert near(p.fHeight, 0.45)


def test_sync_follows_width():
	H = load()
	p = Pane(0.5, 0.2, 0.1, 0.3)
	t = H.Tracked(p, 0)
	t.Apply(0.05, 0.0)
	p.fWidth = 0.5
	t.Sync()
	assert near(t.fWidth, 0.5)


# --- Tracked.Restore --------------------------------------------------------------------
def test_restore_returns_natural_size_anchor_top():
	H = load()
	p = Pane(0.5, 0.2)
	t = H.Tracked(p, 0)
	t.Apply(0.05, 0.1)
	t.Restore()
	assert near(p.fHeight, 0.2) and near(p.fTop, 0.5)
	assert t.lSet == None


def test_restore_returns_natural_size_anchor_bottom():
	H = load()
	p = Pane(0.5, 0.2)
	t = H.Tracked(p, 1)
	t.Apply(0.05, 0.0)
	t.Restore()
	assert near(p.fHeight, 0.2) and near(p.fTop, 0.5)


def test_restore_after_game_move_restores_where_the_game_put_it():
	H = load()
	p = Pane(0.5, 0.2)
	t = H.Tracked(p, 0)
	t.Apply(0.05, 0.0)
	p.fTop = 0.8
	t.Restore()
	assert near(p.fTop, 0.8) and near(p.fHeight, 0.2)


def test_restore_without_apply_leaves_pane_alone():
	H = load()
	p = Pane(0.5, 0.2)
	t = H.Tracked(p, 1)
	t.Restore()
	assert p.writes == 0 and t.lSet == None


# --- Panel.LineSpace / SetText ------------------------------------------------------------
def test_linespace_player_and_target():
	H = load()
	t = mock_app.Text("Hull")		# GetHeight() == 0.02
	assert near(H.Panel("GetShipDisplay", 1).LineSpace(t), 0.02 * 1.3)
	assert near(H.Panel("GetTargetDisplay", 0).LineSpace(t), 0.02 * 1.5)


def test_linespace_never_negative_and_follows_globals():
	H = load()
	t = mock_app.Text("Hull")
	H.g_fPlayerLineSpace = -2.0
	assert H.Panel("GetShipDisplay", 1).LineSpace(t) == 0.0
	H.g_fTargetLineSpace = 2.0
	assert near(H.Panel("GetTargetDisplay", 0).LineSpace(t), 0.04)


class CountingText(mock_app.Text):
	def __init__(self, s=""):
		mock_app.Text.__init__(self, s)
		self.nSet = 0
		self.nRecalc = 0

	def SetString(self, s):
		self.nSet = self.nSet + 1
		mock_app.Text.SetString(self, s)

	def RecalcBounds(self):
		self.nRecalc = self.nRecalc + 1


def test_settext_only_touches_text_when_it_changes():
	H = load()
	pPanel = H.Panel("GetShipDisplay", 1)
	t = CountingText()
	pPanel.SetText(t, "Armor", 0.456)
	assert t.s == "Armor 46%" and t.nSet == 1 and t.nRecalc == 1
	pPanel.SetText(t, "Armor", 0.456)
	pPanel.SetText(t, "Armor", 0.459)		# still 46%
	assert t.nSet == 1 and t.nRecalc == 1
	pPanel.SetText(t, "Armor", 0.5)
	assert t.s == "Armor 50%" and t.nSet == 2 and t.nRecalc == 2


def test_settext_clamps_and_rounds():
	H = load()
	pPanel = H.Panel("GetShipDisplay", 1)
	t = CountingText()
	pPanel.SetText(t, "Hull", 1.7)
	assert t.s == "Hull 100%"
	pPanel.SetText(t, "Hull", -0.3)
	assert t.s == "Hull 0%"
	pPanel.SetText(t, "Hull", 0.005)		# 0.5% rounds up
	assert t.s == "Hull 1%"
	pPanel.SetText(t, "Hull", 0.004)
	assert t.s == "Hull 0%"


def test_settext_remembers_each_label_separately():
	H = load()
	pPanel = H.Panel("GetShipDisplay", 1)
	tA = CountingText()
	tH = CountingText()
	pPanel.SetText(tA, "Armor", 1.0)
	pPanel.SetText(tH, "Hull", 1.0)
	assert tA.nSet == 1 and tH.nSet == 1
	assert pPanel.dTexts == {"Armor": "Armor 100%", "Hull": "Hull 100%"}


def run():
	return fake_ships.run(globals())


if __name__ == "__main__":
	sys.exit(run())
