"""check - one command for the whole gate: lint15 + every off-game test.

Usage: python tools/check.py [Mod ...]     (default: every mod with a tests/ dir)
Prints only failures and one summary line per stage; exit 1 on any failure.
"""
import glob
import os
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main(argv):
	py = sys.executable
	mods = argv or [m for m in sorted(os.listdir(REPO)) if os.path.isdir(os.path.join(REPO, m, "scripts"))]
	rc = 0
	lint = subprocess.run([py, os.path.join(REPO, "tools", "lint15.py"), "--quiet"] + [os.path.join(REPO, m, "scripts") for m in mods], capture_output=True, text=True)
	sys.stdout.write(lint.stdout)
	if lint.returncode:
		rc = 1
	for m in mods:
		tests = sorted(glob.glob(os.path.join(REPO, m, "tests", "test_*.py")))
		total = 0
		failed = 0
		for t in tests:
			r = subprocess.run([py, "-B", t], capture_output=True, text=True, cwd=os.path.dirname(t))
			total = total + 1
			if r.returncode:
				failed = failed + 1
				rc = 1
				lines = [l for l in r.stdout.splitlines() if not l.startswith("PASS ")]
				print("FAIL %s" % os.path.basename(t))
				for l in (lines + r.stderr.splitlines())[-15:]:
					print("  " + l)
		print("tests %s: %d/%d files passed" % (m, total - failed, total))
	return rc


if __name__ == "__main__":
	sys.exit(main(sys.argv[1:]))
