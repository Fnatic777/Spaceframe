"""Spaceframe.Log: the optional log file (Debug = 1 only)."""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mock_app
from test_core_lifecycle import load_core


class FakeFile:
	def __init__(self, bFailWrite=0):
		self.lines = []
		self.flushes = 0
		self.closed = 0
		self.bFailWrite = bFailWrite

	def write(self, s):
		if self.bFailWrite and not s.startswith("===="):
			raise IOError("disk")
		self.lines.append(s)

	def flush(self):
		self.flushes = self.flushes + 1

	def close(self):
		self.closed = 1


def make_open(pFile=None, bFail=0):
	calls = []

	def fake_open(sName, sMode):
		calls.append((sName, sMode))
		if bFail:
			raise IOError("Securelevel prevents file IO.")
		return pFile
	return fake_open, calls


def setup(bDebug=1, pFile=None, bFail=0):
	C, App = load_core([], Debug=bDebug)
	fOpen, calls = make_open(pFile, bFail)
	C.g_fOpen = fOpen
	banners = []
	C.ShowProblem = lambda s: banners.append(s)
	prints = []

	class Dbg:
		def Print(self, s):
			prints.append(s)
	App.CPyDebug = lambda *a: Dbg()
	return C, App, calls, banners, prints


def test_debug_off_does_nothing():
	pFile = FakeFile()
	C, App, calls, banners, prints = setup(0, pFile)
	C.Log("Mod", "hello")
	assert calls == [] and prints == [] and banners == []
	assert C.LogFileState() == "off"


def test_debug_on_opens_once_stamps_and_flushes():
	pFile = FakeFile()
	C, App, calls, banners, prints = setup(1, pFile)
	assert C.LogFileState() == "unopened"
	C.Log("Mod", "one")
	C.Log("Mod2", "two")
	assert calls == [("Spaceframe_debug.log", "a")]
	assert pFile.lines[0].startswith("==== Spaceframe session ")
	assert pFile.lines[1].endswith(" Mod: one\n")
	assert pFile.lines[2].endswith(" Mod2: two\n")
	assert pFile.flushes == 2
	assert prints == []
	assert C.LogFileState() == "ok"


def test_game_time_stamp():
	pFile = FakeFile()
	C, App, calls, banners, prints = setup(1, pFile)
	App.g_kUtopiaModule.GetGameTime = lambda: 12.3456
	C.Log("Mod", "x")
	assert pFile.lines[1] == "12.35 Mod: x\n"


def test_open_failure_flag_banner_once_no_retry_and_fallback():
	C, App, calls, banners, prints = setup(1, None, 1)
	C.Log("Mod", "a")
	C.Log("Mod", "b")
	assert len(calls) == 1
	assert banners == ["Spaceframe log file unavailable (file IO blocked by the game)"]
	assert prints == ["Mod: a\n", "Mod: b\n"]
	assert C.LogFileState() == "failed"
	assert C.g_bLogOpenFailed == 1


def test_retry_after_start():
	C, App, calls, banners, prints = setup(1, None, 1)
	C.Log("Mod", "a")
	assert len(calls) == 1
	C.Start(object())	# no modules: returns early, but the session is reset
	C.Log("Mod", "b")
	assert len(calls) == 2


def test_write_error_disables_the_file_logger():
	pFile = FakeFile(1)
	C, App, calls, banners, prints = setup(1, pFile)
	C.Log("Mod", "a")
	C.Log("Mod", "b")
	assert len(calls) == 1
	assert C.LogFileState() == "failed"
	assert pFile.closed == 1
	assert prints == ["Mod: a\n", "Mod: b\n"]


def test_stop_closes_and_next_log_reopens():
	pFile = FakeFile()
	C, App, calls, banners, prints = setup(1, pFile)
	C.Log("Mod", "a")
	C.Stop()
	assert pFile.closed == 1
	assert C.LogFileState() == "unopened"
	C.Log("Mod", "b")
	assert len(calls) == 2


def test_cap_writes_one_final_line_then_silent():
	pFile = FakeFile()
	C, App, calls, banners, prints = setup(1, pFile)
	for i in range(20000):
		C.Log("Mod", "l" + str(i))
	assert len(pFile.lines) == 20001	# header + 20000
	C.Log("Mod", "over1")
	C.Log("Mod", "over2")
	assert len(pFile.lines) == 20002
	assert pFile.lines[-1] == "==== log capped at 20000 lines ====\n"
	assert len(pFile.lines) == 20002	# nothing more reached the file
	C.Start(object())	# new session resets the counter
	C.Log("Mod", "again")
	assert pFile.lines[-1].endswith(" Mod: again\n")


class HeaderFailFile:
	def __init__(self):
		self.closed = 0
		self.n = 0

	def write(self, s):
		self.n = self.n + 1
		if self.n == 1:
			raise IOError("disk")

	def flush(self):
		pass

	def close(self):
		self.closed = self.closed + 1


def test_header_write_failure_closes_handle():
	pFile = HeaderFailFile()
	C, App, calls, banners, prints = setup(1, pFile)
	C.Log("Mod", "a")
	assert pFile.closed == 1
	assert C.LogFileState() == "failed"
	assert len(banners) == 1


def test_no_banner_when_first_failure_is_inside_stop():
	C, App, calls, banners, prints = setup(1, None, 1)
	C.g_lModules = [["X", None, 1, 0]]
	C.CallModules = lambda *a: None
	C.Stop()	# logs "Spaceframe stopped." -> open fails
	assert banners == []
	assert C.LogFileState() == "failed"
	C.Log("Mod", "b")
	assert banners == [] and len(calls) == 1


def test_banner_after_start_resets_stopping():
	C, App, calls, banners, prints = setup(1, None, 1)
	C.Stop()
	C.Start(object())
	C.Log("Mod", "a")
	assert len(banners) == 1


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
