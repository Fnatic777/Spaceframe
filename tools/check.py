"""check - one command for the whole gate: lint15 + every off-game test.

Usage: python tools/check.py [Mod ...] [--only PATTERN]
  default: every mod with a scripts/ dir; tests run in parallel.
  --only PATTERN   run only test files whose name contains PATTERN (inner loop);
                   lint still covers everything. The full run is the gate.
Output: failures first (last 15 lines each), then always exactly two summary lines:
  lint15: ...
  tests: N/M files passed (...)
Exit 1 on any failure.
"""
import concurrent.futures
import glob
import os
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def run_test(py, t):
	r = subprocess.run([py, "-B", t], capture_output=True, text=True, cwd=os.path.dirname(t))
	return t, r


def main(argv):
	py = sys.executable
	only = None
	if "--only" in argv:
		i = argv.index("--only")
		only = argv[i + 1] if i + 1 < len(argv) else ""
		argv = argv[:i] + argv[i + 2:]
	mods = argv or [m for m in sorted(os.listdir(REPO)) if os.path.isdir(os.path.join(REPO, m, "scripts"))]
	tests = []
	for m in mods:
		for t in sorted(glob.glob(os.path.join(REPO, m, "tests", "test_*.py"))):
			if only is None or only in os.path.basename(t):
				tests.append(t)
	rc = 0
	with concurrent.futures.ThreadPoolExecutor(max_workers=min(8, os.cpu_count() or 4)) as ex:
		lint_f = ex.submit(subprocess.run, [py, os.path.join(REPO, "tools", "lint15.py"), "--quiet"]
			+ [os.path.join(REPO, m, "scripts") for m in mods], capture_output=True, text=True)
		results = list(ex.map(lambda t: run_test(py, t), tests))
		lint = lint_f.result()
	failed = []
	for t, r in results:
		if r.returncode:
			failed.append(os.path.relpath(t, REPO))
			lines = [l for l in r.stdout.splitlines() if not l.startswith("PASS ")]
			print("FAIL %s" % os.path.relpath(t, REPO))
			for l in (lines + r.stderr.splitlines())[-15:]:
				print("  " + l)
	out = lint.stdout.strip().splitlines()
	body, summary = out[:-1], (out[-1] if out else "lint15: no output (exit %d)" % lint.returncode)
	for l in body:
		print(l)
	if lint.returncode:
		rc = 1
	if failed:
		rc = 1
	scope = "only '%s'" % only if only is not None else ", ".join(mods)
	print(summary)
	print("tests: %d/%d files passed (%s)%s" % (len(results) - len(failed), len(results), scope,
		failed and " - FAILED: " + ", ".join(os.path.basename(f) for f in failed) or ""))
	return rc


if __name__ == "__main__":
	sys.exit(main(sys.argv[1:]))
