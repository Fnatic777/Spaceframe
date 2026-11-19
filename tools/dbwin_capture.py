"""Capture OutputDebugString output (DBWIN protocol) from stbc.exe into a log.

Usage (py3, Windows, stdlib only):
    python tools/dbwin_capture.py [--match TEXT] [--out PATH] [--all] [--pid N]

Start it BEFORE the game, leave it running, Ctrl+C when done. Only one
DBWIN listener can own the buffer at a time (close DebugView first).
Default log: logs/stbc_debug.log under the repo root (appended, never
truncated). Line format: <ISO time.ms> pid<N> <text>.
Run `--selftest` to verify the capture loop in-process.
"""
import argparse
import ctypes
import datetime
import os
import struct
import sys
import threading
import time
from ctypes import wintypes

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_OUT = os.path.join(REPO, "logs", "stbc_debug.log")

PAGE_READWRITE = 0x04
FILE_MAP_READ = 0x0004
WAIT_OBJECT_0 = 0
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
BUF_SIZE = 4096

k32 = None


def _init_api():
    global k32
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.CreateEventW.restype = wintypes.HANDLE
    k32.CreateEventW.argtypes = [ctypes.c_void_p, wintypes.BOOL,
                                 wintypes.BOOL, wintypes.LPCWSTR]
    k32.CreateFileMappingW.restype = wintypes.HANDLE
    k32.CreateFileMappingW.argtypes = [wintypes.HANDLE, ctypes.c_void_p,
                                       wintypes.DWORD, wintypes.DWORD,
                                       wintypes.DWORD, wintypes.LPCWSTR]
    k32.MapViewOfFile.restype = ctypes.c_void_p
    k32.MapViewOfFile.argtypes = [wintypes.HANDLE, wintypes.DWORD,
                                  wintypes.DWORD, wintypes.DWORD,
                                  ctypes.c_size_t]
    k32.UnmapViewOfFile.argtypes = [ctypes.c_void_p]
    k32.SetEvent.argtypes = [wintypes.HANDLE]
    k32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    k32.CloseHandle.argtypes = [wintypes.HANDLE]
    k32.OpenProcess.restype = wintypes.HANDLE
    k32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    k32.QueryFullProcessImageNameW.argtypes = [
        wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR,
        ctypes.POINTER(wintypes.DWORD)]
    k32.OutputDebugStringA.argtypes = [ctypes.c_char_p]


class Listener(object):
    """Owns the DBWIN kernel objects."""

    def __init__(self):
        self.ev_buf = None
        self.ev_data = None
        self.hmap = None
        self.view = None
        self.prefix = None

    def open(self):
        last = 0
        for prefix in ("Global\\", ""):
            self._close()
            ctypes.set_last_error(0)
            eb = k32.CreateEventW(None, False, False,
                                  prefix + "DBWIN_BUFFER_READY")
            if not eb:
                last = ctypes.get_last_error()
                continue
            ed = k32.CreateEventW(None, False, False,
                                  prefix + "DBWIN_DATA_READY")
            if not ed:
                last = ctypes.get_last_error()
                k32.CloseHandle(eb)
                continue
            hm = k32.CreateFileMappingW(wintypes.HANDLE(-1), None,
                                        PAGE_READWRITE, 0, BUF_SIZE,
                                        prefix + "DBWIN_BUFFER")
            if not hm:
                last = ctypes.get_last_error()
                k32.CloseHandle(eb)
                k32.CloseHandle(ed)
                continue
            vw = k32.MapViewOfFile(hm, FILE_MAP_READ, 0, 0, BUF_SIZE)
            if not vw:
                last = ctypes.get_last_error()
                k32.CloseHandle(eb)
                k32.CloseHandle(ed)
                k32.CloseHandle(hm)
                continue
            self.ev_buf, self.ev_data, self.hmap, self.view = eb, ed, hm, vw
            self.prefix = prefix
            return True
        self.last_error = last
        return False

    def _close(self):
        if self.view:
            k32.UnmapViewOfFile(self.view)
        for h in (self.hmap, self.ev_data, self.ev_buf):
            if h:
                k32.CloseHandle(h)
        self.view = self.hmap = self.ev_data = self.ev_buf = None

    def close(self):
        self._close()

    def poll(self, timeout_ms=500):
        """Return (pid, text) or None on timeout."""
        k32.SetEvent(self.ev_buf)
        if k32.WaitForSingleObject(self.ev_data, timeout_ms) != WAIT_OBJECT_0:
            return None
        raw = ctypes.string_at(self.view, BUF_SIZE)
        pid = struct.unpack("<I", raw[:4])[0]
        data = raw[4:]
        n = data.find(b"\0")
        if n >= 0:
            data = data[:n]
        return pid, data.decode("cp1252", "replace")


class ProcNames(object):
    def __init__(self):
        self.cache = {}

    def name(self, pid):
        if pid in self.cache:
            return self.cache[pid]
        res = None
        try:
            h = k32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
            if h:
                buf = ctypes.create_unicode_buffer(1024)
                sz = wintypes.DWORD(1024)
                if k32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(sz)):
                    res = os.path.basename(buf.value).lower()
                k32.CloseHandle(h)
        except Exception:
            res = None
        # Only cache successes: a pid may not be resolvable yet / be reused.
        if res is not None:
            self.cache[pid] = res
        return res


def now_iso():
    return datetime.datetime.now().isoformat(sep=" ", timespec="milliseconds")


class Capture(object):
    def __init__(self, listener, out, keep_all, pid, matches, echo):
        self.lis = listener
        self.out = out
        self.keep_all = keep_all
        self.pid = pid
        self.matches = [m.lower() for m in (matches or [])]
        self.echo = echo
        self.names = ProcNames()
        self.stop = threading.Event()
        self.count = 0

    def accept(self, pid):
        """Return the label to use, or None to drop."""
        if self.pid is not None:
            return "pid%d" % pid if pid == self.pid else None
        nm = self.names.name(pid)
        if nm is None:
            # Unresolvable: never drop silently, keep only with --all.
            return "pid%d?" % pid if self.keep_all else None
        if self.keep_all or nm == "stbc.exe":
            return "pid%d" % pid
        return None

    def handle(self, pid, text):
        label = self.accept(pid)
        if label is None:
            return
        for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
            if not line.strip() and not line:
                continue
            if self.matches:
                low = line.lower()
                ok = 0
                for m in self.matches:
                    if m in low:
                        ok = 1
                        break
                if not ok:
                    continue
            s = "%s %s %s" % (now_iso(), label, line.rstrip())
            self.out.write(s + "\n")
            self.out.flush()
            self.count += 1
            if self.echo:
                try:
                    print(s)
                except Exception:
                    print(s.encode("ascii", "replace").decode("ascii"))

    def run(self):
        while not self.stop.is_set():
            r = self.lis.poll(500)
            if r is not None:
                self.handle(r[0], r[1])


def open_listener():
    lis = Listener()
    if not lis.open():
        print("ERROR: could not create DBWIN objects (Win32 error %s). "
              "Run the terminal as administrator only if neither the Global\\ "
              "nor the session-local names worked."
              % getattr(lis, "last_error", "?"))
        return None
    return lis


def selftest():
    import io
    lis = open_listener()
    if lis is None:
        print("FAIL: cannot open listener")
        return 1
    out = io.StringIO()
    cap = Capture(lis, out, True, None, None, False)
    th = threading.Thread(target=cap.run)
    th.start()
    time.sleep(0.5)
    k32.OutputDebugStringA(b"dbwin selftest line 1\nline 2\n")
    deadline = time.time() + 3.0
    while time.time() < deadline and cap.count < 2:
        time.sleep(0.05)
    cap.stop.set()
    th.join()
    lis.close()
    text = out.getvalue()
    pidtag = "pid%d" % os.getpid()
    ok = (cap.count == 2 and "dbwin selftest line 1" in text
          and text.count(pidtag) == 2 and "line 2" in text)
    print("listener names: %r" % lis.prefix)
    print(text)
    if ok:
        print("PASS")
        return 0
    if cap.count == 0:
        print("FAIL: nothing received. Another DBWIN listener (DebugView, "
              "a debugger) probably owns the buffer; close it and retry.")
    else:
        print("FAIL: captured %d line(s), expected 2" % cap.count)
    return 1


def main(argv):
    ap = argparse.ArgumentParser(
        description="Capture OutputDebugString output of stbc.exe into a log "
                    "(DBWIN protocol). Start before the game; Ctrl+C when done.")
    ap.add_argument("--out", default=DEFAULT_OUT,
                    help="log file (appended); default logs/stbc_debug.log")
    ap.add_argument("--all", action="store_true",
                    help="keep messages from every process (default: stbc.exe)")
    ap.add_argument("--pid", type=int, default=None, help="keep only this pid")
    ap.add_argument("--match", action="append", default=[], metavar="TEXT",
                    help="keep only lines containing TEXT (case-insensitive, "
                         "repeatable)")
    ap.add_argument("--no-echo", dest="echo", action="store_false",
                    help="do not print to the terminal (echo is on by default)")
    ap.add_argument("--echo", dest="echo", action="store_true",
                    help=argparse.SUPPRESS)
    ap.add_argument("--append", action="store_true", default=True,
                    help="append to the log (always; never truncates)")
    ap.add_argument("--selftest", action="store_true",
                    help="in-process capture test")
    ap.set_defaults(echo=True)
    args = ap.parse_args(argv)

    if sys.platform != "win32":
        print("ERROR: Windows only")
        return 2
    _init_api()
    if args.selftest:
        return selftest()

    lis = open_listener()
    if lis is None:
        return 2
    d = os.path.dirname(os.path.abspath(args.out))
    if not os.path.isdir(d):
        os.makedirs(d)
    out = open(args.out, "a", encoding="utf-8", errors="replace")
    out.write("==== session %s ====\n" % now_iso())
    out.flush()
    if args.pid is not None:
        flt = "pid == %d" % args.pid
    elif args.all:
        flt = "all processes"
    else:
        flt = "process stbc.exe only"
    if args.match:
        flt += "; lines containing any of %r" % (args.match,)
    print("dbwin_capture: log = %s" % os.path.abspath(args.out))
    print("dbwin_capture: filter = %s (names: %sDBWIN_*)"
          % (flt, lis.prefix))
    print("Start this before the game; leave it running; Ctrl+C when done.")
    cap = Capture(lis, out, args.all, args.pid, args.match, args.echo)
    try:
        cap.run()
    except KeyboardInterrupt:
        pass
    finally:
        lis.close()
        out.write("==== end ====\n")
        out.flush()
        out.close()
        print("dbwin_capture: stopped, %d line(s) written" % cap.count)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
