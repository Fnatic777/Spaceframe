"""exe_patch.py - apply/revert independent named patches to stbc.exe (py3 tool, not game code).

Needs: capstone, pefile, keystone. status/verify never write to the exe.

Patches (independent, any combination): onebank (default when no name is given), fileio.

Usage (repo root):
  python tools/exe_patch.py status   [--exe PATH]         sha256 + state of BOTH patches
  python tools/exe_patch.py apply    [--exe PATH] [--patch NAME] [--yes]
                                                          prints the plan, asks to type 'yes' (or --yes);
                                                          backup <exe>.orig-<sha8> made once (by the first apply
                                                          of any patch), never overwritten; refused if the exe
                                                          already carries a patch and no backup exists
  python tools/exe_patch.py upgrade  [--exe PATH] [--yes]  onebank only: patched-v1 -> revert -> apply v2
  python tools/exe_patch.py revert   [--exe PATH] [--patch NAME]   restores that patch only, other one untouched
  python tools/exe_patch.py revert   [--exe PATH] --all    reverts every patch, checks sha256 == original
  python tools/exe_patch.py verify   [--exe PATH] [--patch NAME]   capstone listing of the patch sites
  python tools/exe_patch.py selftest                       runs on a COPY of the exe in a temp dir
NAME in onebank|fileio; no --patch = onebank.

Build check: the bytes of EVERY known site of EVERY patch (all variants) are virtually restored to the
original and the result is hashed; it must equal the original build sha256 (so patches can be applied
and reverted independently).

onebank states: original|patched|patched-v1|partial-cave|modified-unknown.
  Hook at 0x584f24 (6 bytes) jumping to a cave in .text slack at 0x8879f2.
  v2 (current): the cave rejects a candidate target when another bank of the system already targets it,
    ONLY when the system is a PhaserSystem (IsA 0x801f); other systems behave as the original.
  v1 (LEGACY): same rule for every system. Kept so it can be detected, reverted and upgraded.
fileio states: original|patched|modified-unknown (no variants).
  Python builtin open (VA 0x7551e0) refuses file IO ('Securelevel prevents file IO.') when 0x74bc10()
  (= [0x99ee38] > 0) is true. Site VA 0x7551fa: je 0x755268 (74 6c) -> jmp 0x755268 (eb 6c).
"""
import sys, os, hashlib, shutil, struct, tempfile, io, contextlib

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

HOOK_ORIG = bytes.fromhex("85c074308b16")

# ---- v1 (LEGACY, 70 bytes) ----
CAVE1_HEX = ("85c00f845ed5cfff538b4c24088b591c4b782b8b4c240853e8614bceff85c074ef39f874eb"
	"80b8880000000175e28b0e39888c00000075d85be928d5cfff5b8b16e9f2d4cfff")
CAVE1 = bytes.fromhex(CAVE1_HEX)

CAVE1_ASM = """
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

# ---- v2 (current, 88 bytes): rule only for PhaserSystem ----
CAVE2_HEX = ("85c00f845ed5cfff8b4c24048b11681f800000ff520884c07437538b4c24088b591c4b782b8b4c24"
	"0853e84f4bceff85c074ef39f874eb80b8880000000175e28b0e39888c00000075d85be916d5cfff5b8b16e9e0d4cfff")
CAVE2 = bytes.fromhex(CAVE2_HEX)

CAVE2_ASM = """
	test eax, eax
	je 0x%x
	mov ecx, [esp+4]
	mov edx, [ecx]
	push 0x801f
	call dword ptr [edx+8]
	test al, al
	je nonph_
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
nonph_:
	mov edx, [esi]
	jmp 0x%x
""" % (RET_REJECT, GETTER, RET_REJECT, RET_OK)

CAVE_LEN = len(CAVE2)  # the cave area is always this long (v1 is zero-padded to it)
assert CAVE_LEN == 88 and len(CAVE1) == 70
CAVE_END = CAVE_VA + CAVE_LEN  # exclusive: 0x887a4a

# variant -> (state name, cave bytes padded to CAVE_LEN, asm, raw bytes)
VARIANTS = {
	"v1": ("patched-v1", CAVE1 + b"\x00" * (CAVE_LEN - len(CAVE1)), CAVE1_ASM, CAVE1),
	"v2": ("patched", CAVE2, CAVE2_ASM, CAVE2),
}


def assemble(asm):
	ks = Ks(KS_ARCH_X86, KS_MODE_32)
	enc, _ = ks.asm(asm, CAVE_VA)
	return bytes(enc)


def hook_new():
	rel = CAVE_VA - (HOOK_VA + 5)
	return b"\xe9" + struct.pack("<i", rel) + b"\x90"


def sites_for(variant):
	"""name, VA, original bytes, new bytes. Add the "sticky" path hook here later (placeholder)."""
	return [
		("hook", HOOK_VA, HOOK_ORIG, hook_new()),
		("cave", CAVE_VA, b"\x00" * CAVE_LEN, VARIANTS[variant][1]),
		# ("sticky", VA, orig, new),  # TODO: sticky path hook
	]


SITES = sites_for("v2")  # current onebank patch

# ---- fileio: open() always allowed (je -> jmp, same target) ----
FILEIO_VA = 0x7551fa
FILEIO_TARGET = 0x755268
FILEIO_SITES = [("site", FILEIO_VA, bytes.fromhex("746c"), bytes.fromhex("eb6c"))]

PATCHES = ("onebank", "fileio")


def all_known_sites():
	"""(VA, original bytes) of every site of every patch and variant (original bytes are shared)."""
	out = []
	for var in ("v1", "v2"):
		for name, va, orig, new in sites_for(var):
			if (va, orig) not in out:
				out.append((va, orig))
	for name, va, orig, new in FILEIO_SITES:
		out.append((va, orig))
	return out


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


def check_sites(pe, data, sites):
	"""Returns (state, problems) for one site list. state in original|patched|modified-unknown."""
	probs = []
	states = []
	for name, va, orig, new in sites:
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


def detect(pe, data):
	"""Returns (state, problems, variant). state: original|patched|patched-v1|partial-cave|modified-unknown."""
	st, probs = check_sites(pe, data, sites_for("v2"))
	if st == "original":
		return "original", probs, None
	if st == "patched":
		return "patched", probs, "v2"
	st1, probs1 = check_sites(pe, data, sites_for("v1"))
	if st1 == "patched":
		return "patched-v1", probs1, "v1"
	# interrupted write (cave first, hook last): hook original, cave not all zero (complete cave = unreachable)
	hoff, _ = file_off(pe, HOOK_VA)
	coff, _ = file_off(pe, CAVE_VA)
	if hoff is not None and coff is not None and data[hoff:hoff + len(HOOK_ORIG)] == HOOK_ORIG \
			and data[coff:coff + CAVE_LEN] != b"\x00" * CAVE_LEN:
		return "partial-cave", probs, None
	return "modified-unknown", probs, None


def detect_fileio(pe, data):
	"""Returns (state, problems). state: original|patched|modified-unknown."""
	return check_sites(pe, data, FILEIO_SITES)


def detect_patch(pe, data, patch):
	"""State string of one named patch."""
	if patch == "fileio":
		return detect_fileio(pe, data)[0]
	return detect(pe, data)[0]


def base_sha(pe, data):
	"""sha256 of the file with every known site of every patch virtually restored to the original."""
	buf = bytearray(data)
	for va, orig in all_known_sites():
		off, sec = file_off(pe, va)
		if off is not None and off + len(orig) <= len(buf):
			buf[off:off + len(orig)] = orig
	return sha_of(bytes(buf))


def load(path):
	with open(path, "rb") as f:
		data = f.read()
	pe = pefile.PE(data=data, fast_load=True)
	return data, pe


def self_check():
	"""Assert each cave source reproduces its bytes and that instructions are not split."""
	for key in ("v1", "v2"):
		raw = VARIANTS[key][3]
		got = assemble(VARIANTS[key][2])
		if got != raw:
			print("CAVE %s MISMATCH (len asm=%d exp=%d)\n asm: %s\n exp: %s" % (key, len(got), len(raw), got.hex(), raw.hex()))
			for n in range(min(len(got), len(raw))):
				if got[n] != raw[n]:
					print(" first diff at byte %d: asm %02x exp %02x" % (n, got[n], raw[n]))
					break
			sys.exit(2)
	md = Cs(CS_ARCH_X86, CS_MODE_32)
	md.detail = True
	hk = list(md.disasm(HOOK_ORIG, HOOK_VA))
	assert sum(i.size for i in hk) == 6 and hk[-1].address + hk[-1].size == HOOK_VA + 6
	nh = list(md.disasm(hook_new(), HOOK_VA))
	assert len(nh) == 2 and nh[0].mnemonic == "jmp" and nh[0].operands[0].imm == CAVE_VA
	assert nh[1].mnemonic == "nop" and nh[1].address + 1 == HOOK_VA + 6
	for key in ("v1", "v2"):
		raw = VARIANTS[key][3]
		cv = list(md.disasm(raw, CAVE_VA))
		assert sum(i.size for i in cv) == len(raw)
		targets = {}
		for i in cv:
			if (i.mnemonic.startswith("j") or i.mnemonic == "call") and i.operands[0].type == 2:
				targets[i.address] = i.operands[0].imm
		vals = sorted(targets.values())
		assert RET_REJECT in vals and RET_OK in vals and GETTER in vals
		starts = [i.address for i in cv]
		for a, t in targets.items():
			if CAVE_VA <= t < CAVE_VA + len(raw):
				assert t in starts, "jump into middle of instruction"
	fo = list(md.disasm(FILEIO_SITES[0][2], FILEIO_VA))
	fn = list(md.disasm(FILEIO_SITES[0][3], FILEIO_VA))
	assert len(fo) == 1 and fo[0].mnemonic == "je" and fo[0].operands[0].imm == FILEIO_TARGET
	assert len(fn) == 1 and fn[0].mnemonic == "jmp" and fn[0].operands[0].imm == FILEIO_TARGET
	assert fo[0].size == fn[0].size == 2
	return True


def print_header(path, data, pe):
	h = sha_of(data)
	b = base_sha(pe, data)
	print("exe: %s" % path)
	if h == SHA:
		note = "known build, original"
	elif b == SHA:
		note = "known build with patches applied (original sha256 %s)" % SHA
	else:
		note = "other build or modified outside the known sites"
	print("sha256: %s (%s)" % (h, note))
	return b


def cmd_status(path, patch=None):
	"""patch None: print both patches, return the onebank state. Else print/return that patch only."""
	data, pe = load(path)
	b = print_header(path, data, pe)
	if patch in (None, "fileio"):
		fst, fprobs = detect_fileio(pe, data)
		if b != SHA and fst == "original":
			fst = "original-bytes-but-other-sha"
		print("patch fileio: %s" % fst)
		for name, va, orig, new in FILEIO_SITES:
			off, sec = file_off(pe, va)
			if sec is not None:
				print("  %s va=0x%x off=0x%x section=%s exec=%s" % (name, va, off,
					sec.Name.rstrip(b"\0").decode(), bool(sec.Characteristics & 0x20000000)))
		for p in fprobs:
			print("  PROBLEM: " + p)
		if patch == "fileio":
			return fst
	state, probs, var = detect(pe, data)
	if b != SHA and state == "original":
		state = "original-bytes-but-other-sha"
	print("patch onebank: %s" % state)
	print("state: %s" % state)
	if state == "patched-v1":
		print("  LEGACY cave v1 (rule applies to every system): run 'upgrade' (or 'revert' then 'apply')")
	elif state == "patched":
		print("  cave v2 (PhaserSystem only), ends at 0x%x" % CAVE_END)
	elif state == "partial-cave":
		print("  hook is original but the cave area holds bytes (interrupted write, unreachable): 'revert' cleans it")
	elif state == "modified-unknown":
		print("  unknown bytes: restore the backup %s" % backup_path(path))
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


def cmd_apply(path, yes, patch="onebank"):
	data, pe = load(path)
	h = sha_of(data)
	b = base_sha(pe, data)
	if patch == "fileio":
		state, probs = detect_fileio(pe, data)
		var = None
		sites = FILEIO_SITES
		if state == "patched":
			print("REFUSED: already patched (fileio)")
			return 1
	else:
		state, probs, var = detect(pe, data)
		sites = SITES
		if state == "patched-v1":
			print("REFUSED: legacy cave v1 is installed; run 'revert' first (or 'upgrade')")
			return 1
		if state == "patched":
			print("REFUSED: already patched (cave v2)")
			return 1
		if state == "partial-cave":
			print("REFUSED: partial cave bytes from an interrupted write; run revert first")
			return 1
	if b != SHA:
		print("REFUSED: build sha256 %s (known sites restored) != expected build" % b)
		return 1
	if probs or state != "original":
		print("REFUSED: state=%s %s" % (state, "; ".join(probs)))
		print("  if an earlier apply was interrupted, restore the backup: %s" % backup_path(path))
		return 1
	# the other patches must be in a clean state too (original or fully patched)
	for other in PATCHES:
		if other != patch:
			ost = detect_patch(pe, data, other)
			if ost not in ("original", "patched", "patched-v1"):
				print("REFUSED: patch %s is in state %s; fix it first (revert --patch %s)" % (other, ost, other))
				return 1
	bk = backup_path(path)
	if not os.path.exists(bk) and h != SHA:
		print("REFUSED: the exe already carries a patch and no backup exists (%s)." % bk)
		print("  create the backup from a verified original first (revert --all, check sha256, then apply)")
		return 1
	print("Plan for %s (patch %s%s):" % (path, patch, ", cave v2, ends at 0x%x" % CAVE_END if patch == "onebank" else ""))
	for name, va, orig, new in sites:
		off, _ = file_off(pe, va)
		print("  %s: off 0x%x  %s -> %s" % (name, off, orig.hex()[:24], new.hex()[:24]))
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
	order = [s for s in sites if s[0] != "hook"] + [s for s in sites if s[0] == "hook"]
	with open(path, "r+b") as f:
		for name, va, orig, new in order:  # cave first, hook last
			off, _ = file_off(pe, va)
			f.seek(off)
			f.write(new)
	data2, pe2 = load(path)
	state = detect_patch(pe2, data2, patch)
	if state != "patched":
		print("VERIFY FAILED: state=%s" % state)
		return 1
	print("applied %s; sha256 now %s" % (patch, sha_of(data2)))
	return 0


def revert_report(path, what, data2, pe2):
	"""Prints the result of a revert; ok when the build sha is the original (and the file sha too if no patch is left)."""
	h = sha_of(data2)
	b = base_sha(pe2, data2)
	left = [p for p in PATCHES if detect_patch(pe2, data2, p) != "original"]
	if h == SHA:
		print("reverted %s; sha256 %s (OK original)" % (what, h))
		return 0
	if b == SHA and left:
		print("reverted %s; sha256 %s (OK, still patched: %s)" % (what, h, ", ".join(left)))
		return 0
	print("reverted %s; sha256 %s (MISMATCH)" % (what, h))
	return 1


def cmd_revert(path, patch="onebank"):
	data, pe = load(path)
	if patch == "fileio":
		state, probs = detect_fileio(pe, data)
		if state == "original":
			print("already original (fileio); sha256 %s" % sha_of(data))
			return 0 if base_sha(pe, data) == SHA else 1
		if state != "patched":
			print("REFUSED: fileio state=%s; restore the backup %s manually" % (state, backup_path(path)))
			return 1
		with open(path, "r+b") as f:
			for name, va, orig, new in FILEIO_SITES:
				off, _ = file_off(pe, va)
				f.seek(off)
				f.write(orig)
		data2, pe2 = load(path)
		return revert_report(path, "fileio", data2, pe2)
	state, probs, var = detect(pe, data)
	if state == "original":
		print("already original; sha256 %s" % sha_of(data))
		return 0 if base_sha(pe, data) == SHA else 1
	if state == "partial-cave":
		coff, _ = file_off(pe, CAVE_VA)
		with open(path, "r+b") as f:
			f.seek(coff)
			f.write(b"\x00" * CAVE_LEN)
		data2, pe2 = load(path)
		if base_sha(pe2, data2) == SHA:
			print("partial cave cleaned; sha256 %s" % sha_of(data2))
			return 0
		print("partial cave zeroed but build sha256 != original: the exe differs from the known build elsewhere; restore the backup %s" % backup_path(path))
		return 1
	if state not in ("patched", "patched-v1"):
		print("REFUSED: state=%s; restore the backup %s manually" % (state, backup_path(path)))
		return 1
	sites = sites_for(var)
	with open(path, "r+b") as f:
		for name, va, orig, new in [s for s in sites if s[0] == "hook"] + [s for s in sites if s[0] != "hook"]:
			off, _ = file_off(pe, va)
			f.seek(off)
			f.write(orig)
	data2, pe2 = load(path)
	return revert_report(path, var, data2, pe2)


def cmd_revert_all(path):
	"""Reverts every patch (fileio first), then requires the file sha256 == original."""
	for p in ("fileio", "onebank"):
		if cmd_revert(path, p) != 0:
			print("REVERT --ALL STOPPED at patch %s" % p)
			return 1
	data, pe = load(path)
	h = sha_of(data)
	print("revert --all: sha256 %s (%s)" % (h, "OK original" if h == SHA else "MISMATCH"))
	return 0 if h == SHA else 1


def cmd_upgrade(path, yes):
	data, pe = load(path)
	state, probs, var = detect(pe, data)
	if state != "patched-v1":
		print("REFUSED: upgrade needs state patched-v1, found %s" % state)
		return 1
	bk = backup_path(path)
	if os.path.exists(bk):
		with open(bk, "rb") as f:
			if sha_of(f.read()) != SHA:
				print("REFUSED: existing backup is not the original build: %s" % bk)
				return 1
	print("Upgrade plan for %s: revert cave v1 (sha256 must return to original), then apply cave v2 (ends at 0x%x)" % (path, CAVE_END))
	if not yes:
		if input("type 'yes' to upgrade: ").strip() != "yes":
			print("aborted")
			return 1
	if cmd_revert(path) != 0:
		print("UPGRADE STOPPED: revert did not give the original sha256")
		return 1
	return cmd_apply(path, True)


def cmd_verify(path, patch="onebank"):
	self_check()
	data, pe = load(path)
	md = Cs(CS_ARCH_X86, CS_MODE_32)
	if patch == "fileio":
		state, probs = detect_fileio(pe, data)
		print("fileio: %s" % state)
		for name, va, orig, new in FILEIO_SITES:
			off, _ = file_off(pe, va)
			cur = data[off:off + len(orig)]
			shown = "patched" if cur == new else "original" if cur == orig else "UNKNOWN"
			print("[%s] 0x%x off 0x%x (%s)" % (name, va, off, shown))
			for i in md.disasm(cur, va):
				print("  %x: %s %s" % (i.address, i.mnemonic, i.op_str))
		for p in probs:
			print("  PROBLEM: " + p)
		return 1 if (state == "modified-unknown" or probs) else 0
	state, probs, var = detect(pe, data)
	if state == "patched-v1":
		print("NOTE: legacy cave v1 is present (rule applies to every system); 'upgrade' installs v2")
	for name, va, orig, new in SITES:
		off, _ = file_off(pe, va)
		cur = data[off:off + len(orig)]
		if state == "patched-v1":
			cur1 = data[off:off + len(sites_for("v1")[[s[0] for s in SITES].index(name)][3])]
			shown = "patched-v1" if cur == cur1 else "UNKNOWN"
		else:
			shown = "patched" if cur == new else "original" if cur == orig else "UNKNOWN"
		print("[%s] 0x%x (%s)" % (name, va, shown))
		shown_bytes = new if state != "patched-v1" and cur == orig else cur
		if state == "patched-v1" and name == "cave":
			shown_bytes = cur[:len(CAVE1)]  # real v1 length only, not the zero padding
		for i in md.disasm(shown_bytes, va):
			print("  %x: %s %s" % (i.address, i.mnemonic, i.op_str))
	print("cave v2 source reproduces %d bytes (0x%x..0x%x): OK" % (len(CAVE2), CAVE_VA, CAVE_END))
	return 0


def write_variant(path, variant):
	"""Selftest helper: write hook + cave of a variant directly (synthetic install)."""
	data, pe = load(path)
	with open(path, "r+b") as f:
		for name, va, orig, new in sites_for(variant):
			off, _ = file_off(pe, va)
			f.seek(off)
			f.write(new)


def cmd_selftest(src):
	tmp = tempfile.mkdtemp(prefix="exepatch_")
	exe = os.path.join(tmp, "stbc.exe")
	shutil.copyfile(src, exe)
	cmd_revert_all(exe)  # the source exe may already carry patches: test from its original state
	ok = True
	res = [True]
	def expect(c, msg):
		print(("PASS " if c else "FAIL ") + msg)
		res[0] = res[0] and bool(c)
	def capture(fn, *args):
		buf = io.StringIO()
		with contextlib.redirect_stdout(buf):
			rc = fn(*args)
		print(buf.getvalue(), end="")
		return rc, buf.getvalue()
	def sha_now():
		with open(exe, "rb") as f:
			return sha_of(f.read())
	expect(sha_now() == SHA, "copy normalised to original")
	# v2 cycle
	expect(cmd_apply(exe, True) == 0, "apply v2 --yes on copy")
	expect(os.path.exists(backup_path(exe)), "backup created")
	expect(cmd_status(exe) == "patched", "status = patched (v2)")
	expect(cmd_verify(exe) == 0, "verify v2")
	rc, out = capture(cmd_apply, exe, True)
	expect(rc == 1 and "already patched (cave v2)" in out, "apply on v2 -> 'already patched' text")
	expect(cmd_revert(exe) == 0, "revert v2")
	expect(sha_now() == SHA, "sha256 back to original after v2")
	# synthetic v1
	write_variant(exe, "v1")
	expect(cmd_status(exe) == "patched-v1", "status = patched-v1")
	rc, out = capture(cmd_verify, exe)
	expect(rc == 0, "verify with v1 present")
	expect("add byte ptr [eax], al" not in out and "add [eax], al" not in out, "verify v1: no zero-padding disassembly")
	expect(cmd_apply(exe, True) == 1, "apply refused on patched-v1")
	expect(cmd_revert(exe) == 0, "revert v1")
	expect(sha_now() == SHA, "sha256 back to original after v1")
	# upgrade
	write_variant(exe, "v1")
	expect(cmd_upgrade(exe, True) == 0, "upgrade v1 -> v2")
	expect(cmd_status(exe) == "patched", "status = patched after upgrade")
	expect(cmd_upgrade(exe, True) == 1, "upgrade refused on v2")
	expect(cmd_revert(exe) == 0 and sha_now() == SHA, "revert after upgrade -> original")
	# partial-cave: cave written, hook original (full v2 cave, and a half cave)
	for label, part in (("full v2 cave", CAVE2), ("half cave (40 bytes)", CAVE2[:40])):
		d, pe = load(exe)
		coff, _ = file_off(pe, CAVE_VA)
		with open(exe, "r+b") as f:
			f.seek(coff)
			f.write(part)
		expect(cmd_status(exe) == "partial-cave", "status = partial-cave (%s)" % label)
		rc, out = capture(cmd_apply, exe, True)
		expect(rc == 1 and "run revert first" in out, "apply refused on partial-cave (%s)" % label)
		expect(cmd_revert(exe) == 0 and sha_now() == SHA, "revert cleans partial-cave (%s) -> original" % label)
	bk = backup_path(exe)
	def bk_stat():
		with open(bk, "rb") as f:
			return sha_of(f.read()), os.stat(bk).st_mtime_ns
	bk0 = bk_stat()
	expect(bk0[0] == SHA, "backup is the pristine original")
	# fileio alone
	expect(cmd_apply(exe, True, "fileio") == 0, "fileio apply --yes")
	expect(cmd_status(exe, "fileio") == "patched", "fileio status = patched")
	expect(cmd_status(exe) == "original", "onebank untouched by fileio apply")
	expect(cmd_verify(exe, "fileio") == 0, "fileio verify")
	rc, out = capture(cmd_apply, exe, True, "fileio")
	expect(rc == 1 and "already patched (fileio)" in out, "fileio second apply refused")
	expect(cmd_revert(exe, "fileio") == 0 and sha_now() == SHA, "fileio revert -> original sha")
	expect(cmd_status(exe, "fileio") == "original", "fileio status = original")
	# both, in both orders; revert one keeps the other
	for first, second in (("onebank", "fileio"), ("fileio", "onebank")):
		expect(cmd_apply(exe, True, first) == 0 and cmd_apply(exe, True, second) == 0, "apply %s then %s" % (first, second))
		expect(cmd_status(exe) == "patched" and cmd_status(exe, "fileio") == "patched", "both patched (%s first)" % first)
		expect(cmd_verify(exe) == 0 and cmd_verify(exe, "fileio") == 0, "verify both (%s first)" % first)
		expect(cmd_revert(exe, first) == 0, "revert %s only" % first)
		expect(cmd_status(exe, second) == "patched" and cmd_status(exe, first) == "original", "%s kept after reverting %s" % (second, first))
		expect(cmd_revert(exe, second) == 0 and sha_now() == SHA, "revert %s -> original sha" % second)
	expect(cmd_apply(exe, True) == 0 and cmd_apply(exe, True, "fileio") == 0, "apply both for revert --all")
	expect(cmd_revert_all(exe) == 0 and sha_now() == SHA, "revert --all -> original sha")
	expect(bk_stat() == bk0, "backup created once and unchanged")
	# patched exe and no backup: apply refused
	expect(cmd_apply(exe, True) == 0, "apply onebank (for no-backup test)")
	os.remove(bk)
	rc, out = capture(cmd_apply, exe, True, "fileio")
	expect(rc == 1 and "no backup exists" in out and not os.path.exists(bk), "apply refused on patched exe without backup")
	expect(cmd_revert_all(exe) == 0 and sha_now() == SHA, "revert --all after refusal -> original")
	# corrupted fileio site byte
	d, pe = load(exe)
	foff, _ = file_off(pe, FILEIO_VA)
	with open(exe, "r+b") as f:
		f.seek(foff)
		f.write(b"\x75")
	expect(cmd_status(exe, "fileio") == "modified-unknown", "corrupted fileio site -> modified-unknown")
	expect(cmd_apply(exe, True, "fileio") == 1, "fileio apply refused on corrupted site")
	expect(cmd_apply(exe, True) == 1, "onebank apply refused while fileio site is corrupted")
	d, _ = load(exe)
	expect(d[foff] == 0x75, "corrupted fileio exe left untouched")
	with open(exe, "r+b") as f:
		f.seek(foff)
		f.write(FILEIO_SITES[0][2][:1])
	expect(sha_now() == SHA, "fileio site repaired")
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
	ok = res[0]
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
	patch = "onebank"
	if "--patch" in argv:
		i = argv.index("--patch")
		patch = argv[i + 1] if i + 1 < len(argv) else ""
		if patch not in PATCHES:
			print("unknown patch %r; use one of: %s" % (patch, ", ".join(PATCHES)))
			return 1
	self_check()
	if cmd == "status":
		cmd_status(path)
		return 0
	if cmd == "apply":
		return cmd_apply(path, yes, patch)
	if cmd == "upgrade":
		if patch != "onebank":
			print("upgrade only exists for onebank")
			return 1
		return cmd_upgrade(path, yes)
	if cmd == "revert":
		if "--all" in argv:
			return cmd_revert_all(path)
		return cmd_revert(path, patch)
	if cmd == "verify":
		return cmd_verify(path, patch)
	if cmd == "selftest":
		return cmd_selftest(path)
	print(__doc__)
	return 1


if __name__ == "__main__":
	sys.exit(main(sys.argv))
