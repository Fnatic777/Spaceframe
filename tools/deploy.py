"""deploy - install a mod from this repo into the Bridge Commander folder.

The repo is the source of truth. Each mod is a top-level folder with a
scripts/ tree mirrored into <game>/scripts/ and an optional README.txt
installed as "<game>/<Mod> - README.txt".

Usage (from the repo root):
    python tools/deploy.py status  [Mod]   what would change (default command)
    python tools/deploy.py install [Mod]   copy changed files, verify byte by byte
    python tools/deploy.py pull    [Mod]   copy files edited in the game back into the repo
    python tools/deploy.py backup  [Mod]   "<game>/<Mod> Backups/<Mod> vX.Y - DATE/" + .zip
Options: --force (install over files edited in the game), --game "D:/path".

Safety: the content last installed is remembered (.deploy-state.json, local).
A game file that differs from both the repo and that record was edited by the
user (typically Ships.py / Config.py); install refuses to overwrite it unless
--force, and "pull" brings those edits into the repo. Files that exist only in
the game are reported, never deleted. .pyc files are never touched. Copies get
a fresh mtime so the game recompiles the .pyc.
"""
import datetime
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import zipfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_GAME = r"D:\GOG Games\Star Trek Bridge Commander"
STATE = os.path.join(REPO, ".deploy-state.json")
# Vanilla files a mod patches with marked blocks; included in backups.
PATCHED = {"Spaceframe": [r"scripts\QuickBattle\QuickBattle.py"]}


def sha(path):
	return hashlib.sha256(open(path, "rb").read()).hexdigest()


def load_state():
	if os.path.exists(STATE):
		return json.load(open(STATE))
	return {}


def save_state(st):
	json.dump(st, open(STATE, "w"), indent=1, sort_keys=True)


def mods():
	res = []
	for n in sorted(os.listdir(REPO)):
		if os.path.isdir(os.path.join(REPO, n, "scripts")):
			res.append(n)
	return res


def mapping(mod, game):
	"""List of (repo_path, game_path, key)."""
	base = os.path.join(REPO, mod)
	out = []
	for root, dirs, files in os.walk(os.path.join(base, "scripts")):
		dirs[:] = [d for d in dirs if d != "__pycache__"]
		for f in sorted(files):
			if f.endswith((".pyc", ".pyo")):
				continue
			src = os.path.join(root, f)
			rel = os.path.relpath(src, base)
			out.append((src, os.path.join(game, rel), rel))
	readme = os.path.join(base, "README.txt")
	if os.path.exists(readme):
		out.append((readme, os.path.join(game, mod + " - README.txt"), "README.txt"))
	return out


def committed_sha(src):
	"""sha256 of src as committed at HEAD, with checkout filters (CRLF) applied; None if absent."""
	rel = os.path.relpath(src, REPO).replace(os.sep, "/")
	try:
		r = subprocess.run(["git", "-C", REPO, "cat-file", "--filters", "HEAD:" + rel], capture_output=True)
	except OSError:
		return None
	if r.returncode:
		return None
	return hashlib.sha256(r.stdout).hexdigest()


def classify(mod, game, st):
	"""Yield (state, src, dst, key). state: same|new|changed|edited.

	The game copy is ours (safe to overwrite) when it matches what we last
	installed OR what is committed at HEAD - so a lost/absent
	.deploy-state.json does not turn every repo change into a false "edited".
	"""
	rec = st.get(mod, {})
	for src, dst, key in mapping(mod, game):
		if not os.path.exists(dst):
			yield "new", src, dst, key
			continue
		hs, hd = sha(src), sha(dst)
		if hs == hd:
			yield "same", src, dst, key
		elif rec.get(key) == hd or committed_sha(src) == hd:
			yield "changed", src, dst, key  # game holds a known version of ours
		else:
			yield "edited", src, dst, key  # game copy changed outside the repo


def orphans(mod, game):
	"""Files in the game under the mod's own Custom/<Mod> folders but not in the repo."""
	known = set(os.path.normcase(d) for s, d, k in mapping(mod, game))
	res = []
	roots = set()
	for s, d, k in mapping(mod, game):
		if k.startswith("scripts" + os.sep + "Custom" + os.sep):
			parts = k.split(os.sep)
			roots.add(os.path.join(game, *parts[:3]))
	for r in sorted(roots):
		for root, dirs, files in os.walk(r):
			for f in files:
				p = os.path.join(root, f)
				if f.endswith((".pyc", ".pyo")) or os.path.normcase(p) in known:
					continue
				res.append(p)
	return res


def cmd_status(mod, game, st, force):
	n = 0
	for state, src, dst, key in classify(mod, game, st):
		if state != "same":
			n = n + 1
			print("%-8s %s" % (state, key))
	for p in orphans(mod, game):
		print("%-8s %s" % ("game-only", os.path.relpath(p, game)))
	if not n:
		print("%s: game is up to date" % mod)
	return 0


def cmd_install(mod, game, st, force):
	rec = st.setdefault(mod, {})
	todo = []
	blocked = []
	for state, src, dst, key in classify(mod, game, st):
		if state == "same":
			rec[key] = sha(dst)
		elif state == "edited" and not force:
			blocked.append(key)
		else:
			todo.append((state, src, dst, key))
	if blocked:
		print("REFUSED: edited in the game since the last install (run 'pull', merge, or use --force):")
		for k in blocked:
			print("  " + k)
		save_state(st)
		return 2
	bad = 0
	code_changed = 0
	for state, src, dst, key in todo:
		d = os.path.dirname(dst)
		if not os.path.isdir(d):
			os.makedirs(d)
		shutil.copyfile(src, dst)  # fresh mtime -> game rebuilds the .pyc
		if open(src, "rb").read() != open(dst, "rb").read():
			print("VERIFY FAILED " + key)
			bad = bad + 1
			continue
		rec[key] = sha(dst)
		print("installed %-8s %s" % (state, key))
		base = os.path.basename(key)
		if key.endswith(".py") and base not in ("Ships.py", "Config.py"):
			code_changed = 1
	save_state(st)
	if not todo:
		print("%s: nothing to install" % mod)
	elif code_changed:
		print("-> code changed: restart the game (scripts load once per launch)")
	else:
		print("-> only Ships.py/Config.py/README changed: they reload at the next Quick Battle")
	return 1 if bad else 0


def cmd_pull(mod, game, st, force):
	rec = st.setdefault(mod, {})
	n = 0
	for state, src, dst, key in classify(mod, game, st):
		if state == "edited":
			shutil.copyfile(dst, src)
			rec[key] = sha(dst)
			print("pulled " + key)
			n = n + 1
	save_state(st)
	if not n:
		print("%s: no game-side edits to pull" % mod)
	else:
		print("-> review with 'git diff' before committing")
	return 0


def version(mod):
	p = os.path.join(REPO, mod, "scripts", "Custom", mod, mod + ".py")
	if os.path.exists(p):
		m = re.search(r'^VERSION\s*=\s*"([^"]+)"', open(p).read(), re.M)
		if m:
			return m.group(1)
	return "0"


def cmd_backup(mod, game, st, force):
	"""Back up what is INSTALLED (includes the user's own config edits)."""
	stamp = datetime.date.today().isoformat()
	broot = os.path.join(game, mod + " Backups")
	name = "%s v%s - %s" % (mod, version(mod), stamp)
	dest = os.path.join(broot, name)
	i = 2
	while os.path.exists(dest) or os.path.exists(dest + ".zip"):
		dest = os.path.join(broot, "%s (%d)" % (name, i))
		i = i + 1
	files = []
	for src, dst, key in mapping(mod, game):
		if os.path.exists(dst):
			files.append((dst, key if key != "README.txt" else mod + " - README.txt"))
	for rel in PATCHED.get(mod, []):
		p = os.path.join(game, rel)
		if os.path.exists(p):
			files.append((p, rel))
	if not os.path.isdir(broot):
		os.makedirs(broot)
	z = zipfile.ZipFile(dest + ".zip", "w", zipfile.ZIP_DEFLATED)
	for p, rel in files:
		out = os.path.join(dest, rel)
		if not os.path.isdir(os.path.dirname(out)):
			os.makedirs(os.path.dirname(out))
		shutil.copyfile(p, out)
		z.write(p, rel)
	z.close()
	z = zipfile.ZipFile(dest + ".zip")
	bad = 0
	for p, rel in files:
		data = open(p, "rb").read()
		if z.read(rel.replace(os.sep, "/")) != data or open(os.path.join(dest, rel), "rb").read() != data:
			print("VERIFY FAILED " + rel)
			bad = bad + 1
	z.close()
	print("backup: %s (+ .zip), %d files%s" % (dest, len(files), bad and ", ERRORS" or ", verified"))
	return 1 if bad else 0


def main(argv):
	force = "--force" in argv
	game = DEFAULT_GAME
	args = []
	i = 0
	while i < len(argv):
		if argv[i] == "--game":
			game = argv[i + 1]
			i = i + 2
			continue
		if not argv[i].startswith("--"):
			args.append(argv[i])
		i = i + 1
	cmd = args[0] if args else "status"
	targets = args[1:] or mods()
	fn = {"status": cmd_status, "install": cmd_install, "pull": cmd_pull, "backup": cmd_backup}.get(cmd)
	if not fn:
		print(__doc__)
		return 2
	if not os.path.isdir(os.path.join(game, "scripts")):
		print("game folder not found: " + game)
		return 2
	st = load_state()
	rc = 0
	for m in targets:
		rc = max(rc, fn(m, game, st, force))
	return rc


if __name__ == "__main__":
	sys.exit(main(sys.argv[1:]))
