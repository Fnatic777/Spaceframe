"""Debug levels (0 off, 1 log, 2 log and banners) and the toggle banners."""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mock_app
from test_core_lifecycle import load_core
import test_autofire_base as base


def core_with(iDebug):
	C, App = load_core([], Debug=iDebug)
	lShown = []
	sys.modules["MissionLib"].TextBanner = lambda *a: lShown.append((a[1].s, a[3], a[4]))
	return C, lShown


def test_debug_level_values():
	for iIn, iOut in ((0, 0), (1, 1), (2, 2), (-1, 0)):
		C, l = core_with(iIn)
		assert C.DebugLevel() == iOut


def test_debug_notice_only_at_level_2():
	for iLevel, iCount in ((0, 0), (1, 0), (2, 1)):
		C, lShown = core_with(iLevel)
		C.DebugNotice("hello")
		assert len(lShown) == iCount


def test_show_notice_always():
	C, lShown = core_with(0)
	C.ShowNotice("Auto Fire ON", 0.12, 2.5)
	assert lShown == [("Auto Fire ON", 0.12, 2.5)]


def test_autofire_toggle_banner():
	App, AF, core, ship = base.setup()
	lShown = []
	core.ShowNotice = lambda s, y=0.2, d=3.0: lShown.append(s)
	AF.Toggle()
	AF.Toggle()
	assert lShown == ["Auto Fire OFF", "Auto Fire ON"] or lShown == ["Auto Fire ON", "Auto Fire OFF"]


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
