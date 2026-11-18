"""exe_probe.py - compact static probe of stbc.exe (x86, stripped) via SWIG wrappers.

Needs: capstone, pefile. Read-only on the exe. Output is kept small on purpose.

Usage (repo root):
  python tools/exe_probe.py wrap  <Name> [N]   SWIG wrapper(s) whose Python name contains <Name>
                                                (e.g. Weapon_StopFiring); shows format string,
                                                wrapper addr, the C++ call it forwards to
                                                (direct target or vtable slot) and N lines of it
  python tools/exe_probe.py dis   <addr> [N] [-a]  trimmed listing of the function at addr
                                                (default: calls, field offsets [reg+off],
                                                constants, branches; -a = every instruction)
  python tools/exe_probe.py xref  <addr>        callers (call/jmp rel32) and dword refs
                                                (vtables, function tables) of addr
  python tools/exe_probe.py vt    <addr> [N]    dump N dword slots of a vtable at addr, slot
                                                index, target, known name
  python tools/exe_probe.py vtof  <func>        vtables containing func, with slot index
  python tools/exe_probe.py str   <substr>      strings containing substr and their code xrefs
  python tools/exe_probe.py names <substr>      list SWIG method names containing substr
  python tools/exe_probe.py field <off> <f1,f2,..>  which of the given functions touch [reg+off]

Names: functions are labelled by the SWIG wrappers that call them ("~Weapon_StopFiring"),
by the wrapper name itself ("Weapon_StopFiring") and by imports. Addresses in hex (0x...).
The {name, value} scan also catches SWIG constant tables, so event IDs stored as immediates
show up labelled (e.g. "0x800083 ; ET_PHASER_STOPPED_FIRING"). Facts found: docs/api/exe-weapons.md.
"""
import sys, struct, re

EXE = r"D:\GOG Games\Star Trek Bridge Commander\stbc.exe"

try:
	import pefile
	from capstone import Cs, CS_ARCH_X86, CS_MODE_32
except ImportError:
	print("needs: pip install capstone pefile")
	sys.exit(1)

_pe = pefile.PE(EXE, fast_load=True)
_pe.parse_data_directories(directories=[pefile.DIRECTORY_ENTRY["IMAGE_DIRECTORY_ENTRY_IMPORT"]])
BASE = _pe.OPTIONAL_HEADER.ImageBase
IMG = _pe.get_memory_mapped_image()
TEXT = [s for s in _pe.sections if s.Name.startswith(b".text")][0]
T0 = BASE + TEXT.VirtualAddress
T1 = T0 + TEXT.Misc_VirtualSize
MD = Cs(CS_ARCH_X86, CS_MODE_32)
MD.detail = False

IMPORTS = {}
for e in getattr(_pe, "DIRECTORY_ENTRY_IMPORT", []):
	for i in e.imports:
		if i.name:
			IMPORTS[i.address] = i.name.decode("ascii", "replace")


def rd(va, n):
	o = va - BASE
	return IMG[o:o + n]


def d32(va):
	return struct.unpack("<I", rd(va, 4))[0]


def cstr(va, n=120):
	b = rd(va, n)
	z = b.find(b"\0")
	if z < 0:
		return None
	s = b[:z]
	if len(s) < 3 or any(c < 32 or c > 126 for c in s):
		return None
	return s.decode("ascii")


def in_text(va):
	return T0 <= va < T1


# ---------------------------------------------------------------- method tables
_methods = None


def methods():
	"""All PyMethodDef entries {name, func, flags, doc} whose name is a C string."""
	global _methods
	if _methods is not None:
		return _methods
	_methods = {}
	data = IMG
	for s in _pe.sections:
		if not (s.Name.startswith(b".data") or s.Name.startswith(b".rdata")):
			continue
		a = s.VirtualAddress
		end = a + s.Misc_VirtualSize - 16
		while a < end:
			nm, fn = struct.unpack_from("<II", data, a)
			if in_text(fn) and BASE + 0x1000 < nm < BASE + len(data):
				name = cstr(nm, 80)
				if name and re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", name):
					_methods.setdefault(name, fn)
			a += 4
	return _methods


_names = None


def names():
	global _names
	if _names is not None:
		return _names
	_names = {}
	for n, f in methods().items():
		_names.setdefault(f, n)
	return _names


def label(va):
	if va in IMPORTS:
		return IMPORTS[va]
	n = names().get(va)
	if n:
		return n
	return _callee_label.get(va)


_callee_label = {}


# ---------------------------------------------------------------- disassembly
def func_insns(va, maxn=1500):
	"""Linear sweep until a ret/jmp past every forward branch target."""
	out = []
	far = va
	code = rd(va, 0x4000)
	for ins in MD.disasm(code, va):
		out.append(ins)
		if ins.mnemonic.startswith("j") or ins.mnemonic == "call":
			m = re.match(r"^0x([0-9a-f]+)$", ins.op_str)
			if m and ins.mnemonic != "call":
				t = int(m.group(1), 16)
				if va <= t < va + 0x4000 and t > far:
					far = t
		if ins.mnemonic in ("ret", "jmp") and ins.address >= far:
			if ins.mnemonic == "ret" or not re.match(r"^0x", ins.op_str) or True:
				break
		if ins.mnemonic == "int3" and ins.address >= far:
			break
		if len(out) >= maxn:
			break
	return out


def annotate(ins):
	s = "%s %s" % (ins.mnemonic, ins.op_str)
	note = []
	for m in re.finditer(r"0x([0-9a-f]{6,8})", ins.op_str):
		v = int(m.group(1), 16)
		if v in IMPORTS:
			note.append(IMPORTS[v])
			continue
		l = label(v)
		if l:
			note.append(l)
			continue
		if BASE < v < BASE + len(IMG) and not in_text(v):
			st = cstr(v)
			if st:
				note.append('"%s"' % st[:50])
			elif ins.mnemonic in ("mov", "push", "lea", "fld", "fmul", "fadd", "fcomp", "fsub", "fdiv", "fcom", "fdivr", "fsubr"):
				raw = rd(v, 4)
				fv = struct.unpack("<f", raw)[0]
				if 1e-6 < abs(fv) < 1e7:
					note.append("[%g]" % fv)
	if ins.mnemonic in ("push", "mov") and re.search(r", 0x([0-9a-f]{8})$|^0x([0-9a-f]{8})$", ins.op_str):
		m = re.search(r"0x([0-9a-f]{8})$", ins.op_str)
		v = int(m.group(1), 16)
		if 0x3a000000 < v < 0x48000000 and not (BASE < v < BASE + len(IMG)):
			note.append("f=%g" % struct.unpack("<f", struct.pack("<I", v))[0])
	if note:
		s += "   ; " + " ".join(note)
	return s


INTEREST = re.compile(r"\[(e[a-z]{2})\s*\+\s*0x[0-9a-f]+\]|^0x|call|ret")


def listing(va, maxl=80, full=False):
	ins = func_insns(va)
	lines = []
	for i in ins:
		m = i.mnemonic
		keep = full or m == "call" or m.startswith("j") or m == "ret" or \
			re.search(r"\[e[a-z]{2} \+ 0x[0-9a-f]+\]", i.op_str) or \
			re.search(r"0x[0-9a-f]{3,}", i.op_str) or m.startswith("f") or \
			(m in ("cmp", "test", "mov", "push") and re.search(r"\b0x[0-9a-f]+\b|\b\d\b", i.op_str) and m != "push") or \
			m == "push" and re.search(r"0x|^\d", i.op_str)
		if keep:
			lines.append("%08x  %s" % (i.address, annotate(i)))
	print("func %08x  %d insns, %d shown%s" % (va, len(ins), min(len(lines), maxl),
		"" if len(lines) <= maxl else " (truncated, %d more)" % (len(lines) - maxl)))
	for l in lines[:maxl]:
		print(l)


def calls_in(va):
	r = []
	for i in func_insns(va):
		if i.mnemonic in ("call", "jmp"):
			m = re.match(r"^0x([0-9a-f]+)$", i.op_str)
			if m:
				r.append((i.address, int(m.group(1), 16), None))
			else:
				m = re.match(r"^dword ptr \[(e[a-z]{2})(?: \+ 0x([0-9a-f]+))?\]$", i.op_str)
				if m:
					r.append((i.address, None, int(m.group(2) or "0", 16)))
	return r


# ---------------------------------------------------------------- xrefs
_rel = None


def rel_index():
	"""target -> [call/jmp sites] for E8/E9 rel32 in .text (byte scan, may hit misaligned)."""
	global _rel
	if _rel is not None:
		return _rel
	_rel = {}
	t = rd(T0, T1 - T0)
	n = len(t) - 5
	i = 0
	while True:
		i = _next_e8e9(t, i, n)
		if i < 0:
			break
		d = struct.unpack_from("<i", t, i + 1)[0]
		tgt = T0 + i + 5 + d
		if in_text(tgt):
			_rel.setdefault(tgt, []).append(T0 + i)
		i += 1
	return _rel


def _next_e8e9(t, i, n):
	a = t.find(b"\xe8", i, n)
	b = t.find(b"\xe9", i, n)
	if a < 0:
		return b
	if b < 0:
		return a
	return min(a, b)


def dword_refs(v):
	pat = struct.pack("<I", v)
	r = []
	i = IMG.find(pat)
	while i >= 0:
		r.append(BASE + i)
		i = IMG.find(pat, i + 1)
	return r


def containing_func(site):
	"""Best guess of function start: scan back for common prologue after int3/ret padding."""
	a = site
	while a > site - 0x3000:
		b = rd(a - 1, 1)[0]
		if b in (0xcc, 0x90, 0xc3) and rd(a, 1)[0] in (0x55, 0x83, 0x8b, 0x6a, 0x51, 0x53, 0x56, 0x57, 0x64, 0xa1, 0xd9, 0x81, 0x33, 0xb8, 0x8a, 0xe9):
			if a in rel_index() or a % 16 == 0:
				return a
		a -= 1
	return None


# ---------------------------------------------------------------- wrappers
def wrapper_target(fn):
	"""Find the C++ call a SWIG wrapper forwards to: last direct call or vtable call after
	the SWIG_GetPtr, skipping Python API helpers."""
	fmt = None
	res = []
	for i in func_insns(fn):
		if i.mnemonic == "push":
			m = re.match(r"^0x([0-9a-f]{6,8})$", i.op_str)
			if m:
				s = cstr(int(m.group(1), 16))
				if s and ":" in s and fmt is None:
					fmt = s
		if i.mnemonic == "call":
			m = re.match(r"^0x([0-9a-f]+)$", i.op_str)
			if m:
				res.append(("d", int(m.group(1), 16), i.address))
			else:
				m = re.match(r"^dword ptr \[(e[a-z]{2})(?: \+ 0x([0-9a-f]+))?\]$", i.op_str)
				if m:
					res.append(("v", int(m.group(2) or "0", 16), i.address))
	return fmt, res


def _common_helpers():
	"""Callees called by very many wrappers = Python/SWIG helpers."""
	cnt = {}
	ms = list(methods().values())
	for fn in ms[:400]:
		seen = set()
		for k, t, a in wrapper_target(fn)[1]:
			if k == "d" and t not in seen:
				seen.add(t)
				cnt[t] = cnt.get(t, 0) + 1
	return set(t for t, c in cnt.items() if c > 15)


def cmd_wrap(sub, n=40):
	helpers = _common_helpers()
	hits = sorted((k, v) for k, v in methods().items() if sub in k)
	for name, fn in hits[:60]:
		fmt, res = wrapper_target(fn)
		tg = [r for r in res if not (r[0] == "d" and r[1] in helpers)]
		desc = []
		for k, t, a in tg:
			desc.append(("call %08x" % t) if k == "d" else ("vcall slot +0x%x (#%d)" % (t, t // 4)))
		print("%-40s wrap=%08x fmt=%r -> %s" % (name, fn, fmt, "; ".join(desc) or "-"))
		if len(hits) == 1 or n:
			for k, t, a in tg:
				if k == "d":
					_callee_label.setdefault(t, "~" + name)
		if len(hits) <= 2 and n:
			for k, t, a in tg:
				if k == "d":
					listing(t, n)
	if len(hits) > 60:
		print("... %d more" % (len(hits) - 60))


def cmd_xref(v):
	r = rel_index().get(v, [])
	print("rel32 callers of %08x: %d" % (v, len(r)))
	for s in r[:30]:
		f = containing_func(s)
		print("  %08x in %s %s" % (s, ("%08x" % f) if f else "?", label(f) or "" if f else ""))
	d = dword_refs(v)
	print("dword refs: %d" % len(d))
	for s in d[:20]:
		print("  %08x" % s)


def cmd_vt(v, n=40):
	for k in range(n):
		t = d32(v + 4 * k)
		if not in_text(t):
			print("  #%d +0x%x %08x (not code, end)" % (k, 4 * k, t))
			break
		print("  #%-3d +0x%-3x %08x %s" % (k, 4 * k, t, label(t) or ""))


def cmd_vtof(f):
	for r in dword_refs(f):
		# walk back to vtable start: previous dword not a code pointer
		a = r
		while in_text(d32(a - 4)) and r - a < 0x800:
			a -= 4
		print("ref %08x: vtable? start %08x slot #%d (+0x%x)" % (r, a, (r - a) // 4, r - a))


def cmd_str(sub):
	b = sub.encode()
	i = IMG.find(b)
	k = 0
	while i >= 0 and k < 15:
		# string start
		s = i
		while s > 0 and 32 <= IMG[s - 1] < 127:
			s -= 1
		va = BASE + s
		print('%08x "%s"' % (va, cstr(va, 100)))
		for r in dword_refs(va)[:6]:
			f = containing_func(r) if in_text(r) else None
			print("   ref %08x %s" % (r, ("func %08x %s" % (f, label(f) or "")) if f else ""))
		i = IMG.find(b, i + 1)
		k += 1


def cmd_field(off, funcs):
	pat = re.compile(r"\[e[a-z]{2} \+ 0x%x\]" % off)
	for f in funcs:
		hits = [i for i in func_insns(f) if pat.search(i.op_str)]
		print("%08x: %s" % (f, "; ".join("%s %s" % (i.mnemonic, i.op_str) for i in hits[:6]) or "-"))


def main(a):
	if len(a) < 2:
		print(__doc__)
		return
	c = a[1]
	h = lambda x: int(x, 16)
	if c == "wrap":
		cmd_wrap(a[2], int(a[3]) if len(a) > 3 else 40)
	elif c == "dis":
		listing(h(a[2]), int(a[3]) if len(a) > 3 and a[3] != "-a" else 80, "-a" in a)
	elif c == "xref":
		cmd_xref(h(a[2]))
	elif c == "vt":
		cmd_vt(h(a[2]), int(a[3]) if len(a) > 3 else 40)
	elif c == "vtof":
		cmd_vtof(h(a[2]))
	elif c == "str":
		cmd_str(a[2])
	elif c == "names":
		for k in sorted(k for k in methods() if a[2] in k):
			print(k)
	elif c == "field":
		cmd_field(h(a[2]), [h(x) for x in a[3].split(",")])
	else:
		print(__doc__)


if __name__ == "__main__":
	main(sys.argv)
