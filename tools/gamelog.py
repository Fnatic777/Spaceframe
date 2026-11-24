"""gamelog - read Spaceframe_debug.log without flooding the context.

The game appends one "==== Spaceframe session <date> ====" block per launch,
lines are "<game time> <Module>: <text>". Default = summary of the LAST session.

Usage (from the repo root):
    python tools/gamelog.py [summary]              last session: duration, lines per module,
                                                   most repeated messages, problem lines
    python tools/gamelog.py show [filters]         the lines themselves (repeats collapsed)
    python tools/gamelog.py sessions               one line per session in the file
    python tools/gamelog.py rotate [--keep N]      move all but the last N sessions (default 1)
                                                   to Spaceframe_debug.old.log
Filters: --module NAME  --grep REGEX  --from T  --to T (game seconds)
         --session K (1 = last, 2 = the one before; default 1)  --max N (default 80)
         --raw (do not collapse repeats)  --log PATH
"""
import os
import re
import sys
import time

DEFAULT_LOG = r"D:\GOG Games\Star Trek Bridge Commander\Spaceframe_debug.log"
HEADER = "==== Spaceframe session "
LINE = re.compile(r"^(\d+\.\d+) ([A-Za-z0-9_]+): ?(.*)$")
PROBLEM = re.compile(r"ERR|Error|error|Traceback|failed|FAILED|exception|Exception|capped")
NUM = re.compile(r"-?\d+(\.\d+)?")


def read_sessions(path):
	"""List of (header, [lines]) in file order."""
	res = []
	cur = None
	f = open(path, "r", encoding="ascii", errors="replace")
	for ln in f:
		ln = ln.rstrip("\r\n")
		if ln.startswith(HEADER):
			cur = (ln.strip("= ").replace("Spaceframe session ", ""), [])
			res.append(cur)
		elif cur is None:
			cur = ("(before first header)", [ln])
			res.append(cur)
		else:
			cur[1].append(ln)
	f.close()
	return res


def parse(ln):
	"""(time or None, module or '', text)."""
	m = LINE.match(ln)
	if m:
		return float(m.group(1)), m.group(2), m.group(3)
	return None, "", ln


def shape(text):
	"""Message with numbers replaced, to group repeats."""
	return NUM.sub("#", text)


def opt(argv, name, default=None):
	if name in argv:
		i = argv.index(name)
		if i + 1 < len(argv):
			return argv[i + 1]
	return default


def pick(sessions, argv):
	k = int(opt(argv, "--session", "1"))
	if k < 1 or k > len(sessions):
		print("no session %d (file has %d)" % (k, len(sessions)))
		sys.exit(2)
	return sessions[-k]


def cmd_sessions(sessions, argv):
	for i, (hdr, lines) in enumerate(sessions):
		times = [t for t, m, x in map(parse, lines) if t is not None]
		span = (times[-1] - times[0]) if len(times) > 1 else 0.0
		print("%3d  %-26s %6d lines  %7.1f s" % (len(sessions) - i, hdr, len(lines), span))


def cmd_summary(sessions, argv):
	hdr, lines = pick(sessions, argv)
	parsed = [parse(l) for l in lines]
	times = [t for t, m, x in parsed if t is not None]
	print("session %s: %d lines, game time %.2f-%.2f" % (hdr, len(lines), times[0] if times else 0, times[-1] if times else 0))
	per = {}
	for t, m, x in parsed:
		per[m or "(other)"] = per.get(m or "(other)", 0) + 1
	print("per module: " + ", ".join("%s %d" % kv for kv in sorted(per.items(), key=lambda kv: -kv[1])))
	groups = {}
	first = {}
	for t, m, x in parsed:
		key = m + ": " + shape(x)
		groups[key] = groups.get(key, 0) + 1
		if key not in first:
			first[key] = (t, m, x)
	top = sorted(groups.items(), key=lambda kv: -kv[1])[:15]
	print("most repeated (numbers as #; first example):")
	for key, n in top:
		t, m, x = first[key]
		print("  %5dx  %s: %s" % (n, m, x[:150]))
	probs = [(t, m, x) for t, m, x in parsed if PROBLEM.search(x)]
	print("problem lines: %d" % len(probs))
	seen = {}
	shown = 0
	for t, m, x in probs:
		key = m + shape(x)
		if key in seen:
			seen[key] = seen[key] + 1
			continue
		seen[key] = 1
		if shown < 12:
			print("  %s %s: %s" % (t, m, x[:160]))
			shown = shown + 1
	print("(show --module NAME / --grep REGEX for details)")


def cmd_show(sessions, argv):
	hdr, lines = pick(sessions, argv)
	mod = opt(argv, "--module")
	rx = opt(argv, "--grep")
	rx = re.compile(rx) if rx else None
	t0 = opt(argv, "--from")
	t1 = opt(argv, "--to")
	mx = int(opt(argv, "--max", "80"))
	raw = "--raw" in argv
	out = []
	last_key = None
	for ln in lines:
		t, m, x = parse(ln)
		if mod and m.lower() != mod.lower():
			continue
		if rx and not rx.search(ln):
			continue
		if t0 and (t is None or t < float(t0)):
			continue
		if t1 and (t is None or t > float(t1)):
			continue
		key = m + shape(x)
		if not raw and out and key == last_key:
			out[-1][1] = out[-1][1] + 1
			continue
		last_key = key
		out.append([ln, 1])
	print("session %s: %d matching entries" % (hdr, len(out)))
	for ln, n in out[:mx]:
		print(ln[:220] + ("   (x%d)" % n if n > 1 else ""))
	if len(out) > mx:
		print("... %d more (narrow the filters or raise --max)" % (len(out) - mx))


def cmd_rotate(path, sessions, argv):
	keep = int(opt(argv, "--keep", "1"))
	if time.time() - os.path.getmtime(path) < 30:
		print("log written in the last 30 s - is the game running? close it and retry")
		return 2
	if len(sessions) <= keep:
		print("nothing to rotate (%d session(s))" % len(sessions))
		return 0
	old = os.path.join(os.path.dirname(path), "Spaceframe_debug.old.log")
	f = open(old, "w", newline="\n")
	for hdr, lines in sessions[:-keep]:
		f.write("==== Spaceframe session " + hdr + " ====\n")
		for l in lines:
			f.write(l + "\n")
	f.close()
	f = open(path, "w", newline="\n")
	for hdr, lines in sessions[-keep:]:
		f.write("==== Spaceframe session " + hdr + " ====\n")
		for l in lines:
			f.write(l + "\n")
	f.close()
	print("rotated %d session(s) to %s, kept %d" % (len(sessions) - keep, old, keep))
	return 0


def main(argv):
	path = opt(argv, "--log", DEFAULT_LOG)
	args = [a for i, a in enumerate(argv) if not a.startswith("--") and (i == 0 or not argv[i - 1].startswith("--"))]
	cmd = args[0] if args else "summary"
	if cmd in ("-h", "help"):
		print(__doc__)
		return 0
	if not os.path.exists(path):
		print("no log at %s (Debug = 0, or the fileio exe patch is not applied)" % path)
		return 2
	sessions = read_sessions(path)
	if not sessions:
		print("log is empty")
		return 0
	if cmd == "summary":
		cmd_summary(sessions, argv)
	elif cmd == "show":
		cmd_show(sessions, argv)
	elif cmd == "sessions":
		cmd_sessions(sessions, argv)
	elif cmd == "rotate":
		return cmd_rotate(path, sessions, argv)
	else:
		print(__doc__)
		return 2
	return 0


if __name__ == "__main__":
	sys.exit(main(sys.argv[1:]))
