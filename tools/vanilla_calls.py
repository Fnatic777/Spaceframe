"""vanilla_calls - grep every call made by the game's own .pyc code, fast.

Builds (once, and again when any game .pyc is newer) .cache/vanilla-calls.txt
from "dis15.py --calls-only" over <game>/scripts, one line per call:
    path/relative/to/scripts.pyc:function:line: call
Then searches it (this repo's own Custom/<Mod> code is left out: read its source), so a lookup costs ~1 s instead of disassembling 2885 files.

Usage (from the repo root):
    python tools/vanilla_calls.py REGEX [--max N] [--files]   matches (default max 40)
    python tools/vanilla_calls.py --rebuild                   force a rebuild
  --files   one line per matching file with its match count, instead of the lines
The cache is local (gitignored). Lines are SET_LINENO: a multi-line statement
reports its last line, and a stale .pyc may differ from its .py.
"""
import os
import re
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GAME = r"D:\GOG Games\Star Trek Bridge Commander"
CACHE = os.path.join(REPO, ".cache", "vanilla-calls.txt")


def own_mods():
	"""Custom/<Mod> folders that come from this repo: skipped (their source is in the repo,
	and the game rebuilds their .pyc at every launch, which would force a rebuild)."""
	res = []
	for n in os.listdir(REPO):
		if os.path.isdir(os.path.join(REPO, n, "scripts", "Custom", n)):
			res.append("Custom/" + n + "/")
	return res


def newest_pyc(root):
	m = 0.0
	skip = [os.path.normcase(os.path.join(root, *p.strip("/").split("/"))) for p in own_mods()]
	for dp, dn, fn in os.walk(root):
		if [s for s in skip if os.path.normcase(dp).startswith(s)]:
			continue
		for f in fn:
			if f.endswith(".pyc"):
				t = os.path.getmtime(os.path.join(dp, f))
				if t > m:
					m = t
	return m


def build(scripts):
	r = subprocess.run([sys.executable, os.path.join(REPO, "tools", "dis15.py"), "--calls-only", scripts],
		capture_output=True, text=True, errors="replace")
	if r.returncode and not r.stdout:
		print("dis15 failed: " + r.stderr[-500:])
		sys.exit(2)
	pre = [scripts.replace("\\", "/").rstrip("/") + "/", scripts.rstrip("\\/") + "\\"]
	os.makedirs(os.path.dirname(CACHE), exist_ok=True)
	n = 0
	skip = own_mods()
	out = open(CACHE, "w", encoding="ascii", errors="replace", newline="\n")
	for ln in r.stdout.splitlines():
		for p in pre:
			if ln.startswith(p):
				ln = ln[len(p):]
				break
		ln = ln.replace("\\", "/")
		if [s for s in skip if ln.startswith(s)]:
			continue
		out.write(ln + "\n")
		n = n + 1
	out.close()
	print("built %s: %d calls" % (os.path.relpath(CACHE, REPO), n), file=sys.stderr)


def main(argv):
	scripts = os.path.join(GAME, "scripts")
	if "--rebuild" in argv or not os.path.exists(CACHE) or newest_pyc(scripts) > os.path.getmtime(CACHE):
		build(scripts)
	args = [a for i, a in enumerate(argv) if not a.startswith("--") and (i == 0 or argv[i - 1] != "--max")]
	if not args:
		if "--rebuild" not in argv:
			print(__doc__)
		return 0
	rx = re.compile(args[0])
	mx = 40
	if "--max" in argv:
		mx = int(argv[argv.index("--max") + 1])
	files = {}
	hits = []
	for ln in open(CACHE, encoding="ascii", errors="replace"):
		if rx.search(ln):
			f = ln.split(":", 1)[0]
			files[f] = files.get(f, 0) + 1
			if len(hits) < mx:
				hits.append(ln.rstrip("\n"))
	total = sum(files.values())
	if "--files" in argv:
		for f, n in sorted(files.items(), key=lambda kv: -kv[1])[:mx]:
			print("%5d  %s" % (n, f))
	else:
		for h in hits:
			print(h[:240])
	print("-- %d matches in %d files%s" % (total, len(files), total > mx and " (showing %d; --max N or --files)" % mx or ""))
	return 0 if total else 1


if __name__ == "__main__":
	sys.exit(main(sys.argv[1:]))
