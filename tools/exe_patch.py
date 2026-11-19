"""exe_patch.py - apply/revert the "one bank per target" patch to stbc.exe (py3 tool, not game code).

Needs: capstone, pefile, keystone. status/verify never write to the exe.

Usage (repo root):
  python tools/exe_patch.py status   [--exe PATH]         sha256, known build?, original|patched|modified-unknown
  python tools/exe_patch.py apply    [--exe PATH] [--yes]  prints the plan, asks to type 'yes' (or --yes);
                                                           backup <exe>.orig-<sha8> made once, never overwritten
  python tools/exe_patch.py revert   [--exe PATH]          restores hook + zeroes cave, checks original sha256
  python tools/exe_patch.py verify   [--exe PATH]          capstone listing of hook + cave
  python tools/exe_patch.py selftest                       runs on a COPY of the exe in a temp dir

Patch = list of sites (SITES). Site 1: hook at 0x584f24 jumps to a cave in .text slack at 0x8879f2;
the cave rejects a candidate target when another bank of the system already targets it.
"""
import sys, os, hashlib, shutil, struct, tempfile

try:
	import pefile
	from capstone import Cs, CS_ARCH_X86, CS_MODE_32
	from keystone import Ks, KS_ARCH_X86, KS_MODE_32
except ImportError:
	print("needs: pip install capstone pefile keystone-engine")
	sys.exit(1)

EXE = r"D:\GOG Games\Star Trek Bridge Commander\stbc.exe"
SHA = "2d2ead6719ba3a2825fcce403fcbedebab2a19519e8490da173781da48b86bc4"
BASE = 0x400000

HOOK_VA = 0x584f24
CAVE_VA = 0x8879f2
RET_REJECT = 0x584f58
RET_OK = 0x584f2a
GETTER = 0x56c570

CAVE_HEX = ("85c00f845ed5cfff538b4c24088b591c4b782b8b4c240853e8614bceff85c074ef39f874eb"
	"80b8880000000175e28b0e39888c00000075d85be928d5cfff5b8b16e9f2d4cfff")
CAVE = bytes.fromhex(CAVE_HEX)
HOOK_ORIG = bytes.fromhex("85c074308b16")

CAVE_ASM = """
	test eax, eax
	je 0x%x
	push ebx
	mov ecx, [esp+8]
	mov ebx, [ecx+0x1c]
loop_:
	dec ebx
	js ok_
	mov ecx, [esp+8]
	push ebx
	call 0x%x
	test eax, eax
	je loop_
	cmp eax, edi
	je loop_
	cmp byte ptr [eax+0x88], 1
	jne loop_
	mov ecx, [esi]
	cmp [eax+0x8c], ecx
	jne loop_
	pop ebx
	jmp 0x%x
ok_:
	pop ebx
	mov edx, [esi]
	jmp 0x%x
""" % (RET_REJECT, GETTER, RET_REJECT, RET_OK)


def assemble_cave():
	ks = Ks(KS_ARCH_X86, KS_MODE_32)
	enc, _ = ks.asm(CAVE_ASM, CAVE_VA)
	return bytes(enc)


def hook_new():
	rel = CAVE_VA - (HOOK_VA + 5)
	return b"\xe9" + struct.pack("<i", rel) + b"\x90"


# name, VA, original bytes, new bytes. Add the "sticky" path hook here later (placeholder).
SITES = [
	("hook", HOOK_VA, HOOK_ORIG, hook_new()),
	("cave", CAVE_VA, b"\x00" * len(CAVE), CAVE),
	# ("sticky", VA, orig, new),  # TODO: sticky path hook
]


def sha_of(data):
	return hashlib.sha256(data).hexdigest()


def file_off(pe, va):
	"""File offset of va via section mapping; returns (off, section) or (None, None)."""
	rva = va - BASE
	for s in pe.sections:
		size = s.Misc_VirtualSize
		if s.VirtualAddress <= rva < s.VirtualAddress + max(size, s.SizeOfRawData):
			off = rva - s.VirtualAddress + s.PointerToRawData
			return off, s
	return None, None


def check_sites(pe, data):
	"""Returns (state, problems). state in original|patched|modified-unknown."""
	probs = []
	states = []
	for name, va, orig, new in SITES:
		off, sec = file_off(pe, va)
		end, sec2 = file_off(pe, va + len(orig) - 1)
		if off is None or sec2 is None or sec is not sec2:
			probs.append("%s: VA 0x%x not inside one mapped section" % (name, va))
			states.append("?")
			continue
		if not (sec.Characteristics & 0x20000000):
			probs.append("%s: section %s not executable" % (name, sec.Name.rstrip(b"\0").decode()))
		if off + len(orig) > sec.PointerToRawData + sec.SizeOfRawData:
			probs.append("%s: range beyond raw data" % name)
		cur = data[off:off + len(orig)]
		if cur == orig:
			states.append("original")
		elif cur == new:
			states.append("patched")
		else:
			states.append("?")
	if "?" in states:
		return "modified-unknown", probs
	if states and all(x == "original" for x in states):
		return "original", probs
	if states and all(x == "patched" for x in states):
		return "patched", probs
	return "modified-unknown", probs


def load(path):
	with open(path, "rb") as f:
		data = f.read()
	pe = pefile.PE(data=data, fast_load=True)
	return data, pe


def self_check():
	"""Assert the cave source reproduces CAVE and that instructions are not split."""
	got = assemble_cave()
	if got != CAVE:
		print("CAVE MISMATCH\n asm: %s\n exp: %s" % (got.hex(), CAVE.hex()))
		sys.exit(2)
	md = Cs(CS_ARCH_X86, CS_MODE_32)
	md.detail = True
	hk = list(md.disasm(HOOK_ORIG, HOOK_VA))
	assert sum(i.size for i in hk) == 6 and hk[-1].address + hk[-1].size == HOOK_VA + 6
	nh = list(md.disasm(hook_new(), HOOK_VA))
	assert len(nh) == 2 and nh[0].mnemonic == "jmp" and nh[0].operands[0].imm == CAVE_VA
	assert nh[1].mnemonic == "nop" and nh[1].address + 1 == HOOK_VA + 6
	cv = list(md.disasm(CAVE, CAVE_VA))
	assert sum(i.size for i in cv) == len(CAVE)
	targets = {}
	for i in cv:
		if i.mnemonic.startswith("j") or i.mnemonic == "call":
			targets[i.address] = i.operands[0].imm
	vals = sorted(targets.values())
	assert RET_REJECT in vals and RET_OK in vals and GETTER in vals
	starts = [i.address for i in cv]
	for a, t in targets.items():
		if CAVE_VA <= t < CAVE_VA + len(CAVE):
			assert t in starts, "jump into middle of instruction"
	return True


def cmd_status(path):
	data, pe = load(path)
	h = sha_of(data)
	print("exe: %s" % path)
	print("sha256: %s (%s)" % (h, "known build" if h == SHA else "patched/unknown or other build"))
	state, probs = check_sites(pe, data)
	if h != SHA and state == "original":
		state = "original-bytes-but-other-sha"
	print("state: %s" % state)
	for name, va, orig, new in SITES:
		off, sec = file_off(pe, va)
		if sec is not None:
			print("  %s va=0x%x off=0x%x section=%s exec=%s" % (name, va, off,
				sec.Name.rstrip(b"\0").decode(), bool(sec.Characteristics & 0x20000000)))
	for p in probs:
		print("  PROBLEM: " + p)
	return state


def backup_path(path):
	return "%s.orig-%s" % (path, SHA[:8])


def cmd_apply(path, yes):
	data, pe = load(path)
	h = sha_of(data)
	if h != SHA:
		print("REFUSED: sha256 %s != expected build" % h)
		return 1
	state, probs = check_sites(pe, data)
	if probs or state != "original":
		print("REFUSED: state=%s %s" % (state, "; ".join(probs)))
		print("  if an earlier apply was interrupted, restore the backup: %s" % backup_path(path))
		return 1
	print("Plan for %s:" % path)
	for name, va, orig, new in SITES:
		off, _ = file_off(pe, va)
		print("  %s: off 0x%x  %s -> %s" % (name, off, orig.hex()[:24], new.hex()[:24]))
	bk = backup_path(path)
	print("  backup: %s (%s)" % (bk, "exists, kept" if os.path.exists(bk) else "will be created"))
	if not yes:
		if input("type 'yes' to apply: ").strip() != "yes":
			print("aborted")
			return 1
	made = 0
	if not os.path.exists(bk):
		shutil.copyfile(path, bk)
		made = 1
	with open(bk, "rb") as f:
		if sha_of(f.read()) != SHA:
			print("backup hash mismatch, aborting (exe untouched)")
			if made:
				os.remove(bk)
			else:
				print("  existing backup is not the original build: %s" % bk)
			return 1
	buf = bytearray(data)
	order = [s for s in SITES if s[0] != "hook"] + [s for s in SITES if s[0] == "hook"]
	with open(path, "r+b") as f:
		for name, va, orig, new in order:  # cave first, hook last
			off, _ = file_off(pe, va)
			f.seek(off)
			f.write(new)
			buf[off:off + len(new)] = new
	data2, pe2 = load(path)
	state, probs = check_sites(pe2, data2)
	if state != "patched":
		print("VERIFY FAILED: state=%s" % state)
		return 1
	print("applied; sha256 now %s" % sha_of(data2))
	return 0


def cmd_revert(path):
	data, pe = load(path)
	state, probs = check_sites(pe, data)
	if state == "original":
		print("already original; sha256 %s" % sha_of(data))
		return 0 if sha_of(data) == SHA else 1
	if state != "patched":
		print("REFUSED: state=%s; restore the backup %s manually" % (state, backup_path(path)))
		return 1
	with open(path, "r+b") as f:
		for name, va, orig, new in [s for s in SITES if s[0] == "hook"] + [s for s in SITES if s[0] != "hook"]:
			off, _ = file_off(pe, va)
			f.seek(off)
			f.write(orig)
	data2, _ = load(path)
	h = sha_of(data2)
	print("reverted; sha256 %s (%s)" % (h, "OK original" if h == SHA else "MISMATCH"))
	return 0 if h == SHA else 1


def cmd_verify(path):
	self_check()
	data, pe = load(path)
	md = Cs(CS_ARCH_X86, CS_MODE_32)
	for name, va, orig, new in SITES:
		off, _ = file_off(pe, va)
		cur = data[off:off + len(orig)]
		print("[%s] 0x%x (%s)" % (name, va, "patched" if cur == new else "original" if cur == orig else "UNKNOWN"))
		for i in md.disasm(cur, va):
			print("  %x: %s %s" % (i.address, i.mnemonic, i.op_str))
	print("cave source reproduces %d bytes: OK" % len(CAVE))
	return 0


def cmd_selftest(src):
	tmp = tempfile.mkdtemp(prefix="exepatch_")
	exe = os.path.join(tmp, "stbc.exe")
	shutil.copyfile(src, exe)
	d0, pe0 = load(exe)
	if check_sites(pe0, d0)[0] == "patched":
		cmd_revert(exe)  # the source exe is already patched: test from its original state
	ok = True
	def expect(c, msg):
		nonlocal ok
		print(("PASS " if c else "FAIL ") + msg)
		ok = ok and c
	expect(cmd_apply(exe, True) == 0, "apply --yes on copy")
	expect(os.path.exists(backup_path(exe)), "backup created")
	expect(cmd_status(exe) == "patched", "status = patched")
	cmd_verify(exe)
	expect(cmd_apply(exe, True) == 1, "second apply refused")
	expect(cmd_revert(exe) == 0, "revert")
	with open(exe, "rb") as f:
		expect(sha_of(f.read()) == SHA, "sha256 back to original")
	# negative: corrupt one hook byte
	d, pe = load(exe)
	off, _ = file_off(pe, HOOK_VA)
	with open(exe, "r+b") as f:
		f.seek(off + 2)
		f.write(b"\x75")
	expect(cmd_apply(exe, True) == 1, "apply refused on corrupted hook byte")
	d, _ = load(exe)
	expect(d[off + 2] == 0x75, "corrupted exe left untouched")
	shutil.rmtree(tmp, ignore_errors=True)
	print("SELFTEST " + ("OK" if ok else "FAILED"))
	return 0 if ok else 1


def main(argv):
	if len(argv) < 2:
		print(__doc__)
		return 1
	cmd = argv[1]
	path = EXE
	if "--exe" in argv:
		path = argv[argv.index("--exe") + 1]
	yes = "--yes" in argv
	self_check()
	if cmd == "status":
		cmd_status(path)
		return 0
	if cmd == "apply":
		return cmd_apply(path, yes)
	if cmd == "revert":
		return cmd_revert(path)
	if cmd == "verify":
		return cmd_verify(path)
	if cmd == "selftest":
		return cmd_selftest(path)
	print(__doc__)
	return 1


if __name__ == "__main__":
	sys.exit(main(sys.argv))
