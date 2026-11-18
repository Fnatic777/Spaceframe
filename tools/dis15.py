"""dis15 - disassemble Python 1.5.2 .pyc files from Bridge Commander.

The game's interpreter is Python 1.5.2 and many vanilla modules ship as .pyc
only. Python 3's marshal cannot read 1.5 code objects, so this tool carries
its own unmarshaller and the 1.5 opcode table. It prints per-function
instruction listings (line numbers, resolved names/constants, jump targets)
and the calls each function makes (e.g. App.ShipClass_Cast(pObj),
pShip.GetTarget()), reconstructed by a small symbolic stack.

Usage:
  python tools/dis15.py <file.pyc|dir> [...] [--func Name] [--calls-only]
    --func Name    only functions whose name or Class.name matches (repeatable)
    --calls-only   grep-friendly "path:func:line: call" lines
  Directories are scanned recursively for *.pyc.

Line numbers come from SET_LINENO, i.e. where the 1.5 compiler put them: for a
simple statement spanning several lines that is its LAST line; for a compound
header (for/if/while) it is the header's first line. A .pyc older than the .py
beside it (common in this install) can disagree with that .py.
Call args are reconstructed: "<expr>" = arithmetic/other, "f()" = a call result.

Example:
  python tools/dis15.py --calls-only "D:/GOG Games/Star Trek Bridge Commander/scripts/QuickBattle" | grep GetTarget
"""
import os
import struct
import sys

MAGIC_15 = 20121  # 0x4E99, bytes 99 4E 0D 0A

CO_VARARGS = 0x4
CO_VARKEYWORDS = 0x8

# Python 1.5.2 Include/opcode.h
OPNAMES = {
	0: "STOP_CODE", 1: "POP_TOP", 2: "ROT_TWO", 3: "ROT_THREE", 4: "DUP_TOP",
	10: "UNARY_POSITIVE", 11: "UNARY_NEGATIVE", 12: "UNARY_NOT", 13: "UNARY_CONVERT",
	15: "UNARY_INVERT",
	19: "BINARY_POWER", 20: "BINARY_MULTIPLY", 21: "BINARY_DIVIDE", 22: "BINARY_MODULO",
	23: "BINARY_ADD", 24: "BINARY_SUBTRACT", 25: "BINARY_SUBSCR",
	30: "SLICE+0", 31: "SLICE+1", 32: "SLICE+2", 33: "SLICE+3",
	40: "STORE_SLICE+0", 41: "STORE_SLICE+1", 42: "STORE_SLICE+2", 43: "STORE_SLICE+3",
	50: "DELETE_SLICE+0", 51: "DELETE_SLICE+1", 52: "DELETE_SLICE+2", 53: "DELETE_SLICE+3",
	60: "STORE_SUBSCR", 61: "DELETE_SUBSCR",
	62: "BINARY_LSHIFT", 63: "BINARY_RSHIFT", 64: "BINARY_AND", 65: "BINARY_XOR", 66: "BINARY_OR",
	71: "PRINT_ITEM", 72: "PRINT_NEWLINE",
	80: "BREAK_LOOP", 82: "LOAD_LOCALS", 83: "RETURN_VALUE", 85: "EXEC_STMT",
	87: "POP_BLOCK", 88: "END_FINALLY", 89: "BUILD_CLASS",
	90: "STORE_NAME", 91: "DELETE_NAME", 92: "UNPACK_TUPLE", 93: "UNPACK_LIST",
	95: "STORE_ATTR", 96: "DELETE_ATTR", 97: "STORE_GLOBAL", 98: "DELETE_GLOBAL",
	100: "LOAD_CONST", 101: "LOAD_NAME", 102: "BUILD_TUPLE", 103: "BUILD_LIST",
	104: "BUILD_MAP", 105: "LOAD_ATTR", 106: "COMPARE_OP", 107: "IMPORT_NAME",
	108: "IMPORT_FROM",
	110: "JUMP_FORWARD", 111: "JUMP_IF_FALSE", 112: "JUMP_IF_TRUE", 113: "JUMP_ABSOLUTE",
	114: "FOR_LOOP", 116: "LOAD_GLOBAL",
	120: "SETUP_LOOP", 121: "SETUP_EXCEPT", 122: "SETUP_FINALLY",
	124: "LOAD_FAST", 125: "STORE_FAST", 126: "DELETE_FAST", 127: "SET_LINENO",
	130: "RAISE_VARARGS", 131: "CALL_FUNCTION", 132: "MAKE_FUNCTION", 133: "BUILD_SLICE",
}
HAVE_ARGUMENT = 90
NAME_OPS = (90, 91, 95, 96, 97, 98, 101, 105, 107, 108, 116)
LOCAL_OPS = (124, 125, 126)
REL_JUMPS = (110, 111, 112, 114, 120, 121, 122)
ABS_JUMPS = (113,)
CMP_OPS = ("<", "<=", "==", "!=", ">", ">=", "in", "not in", "is", "is not",
	"exception match", "BAD")

BINOPS = {19: "**", 20: "*", 21: "/", 22: "%", 23: "+", 24: "-", 62: "<<", 63: ">>",
	64: "&", 65: "^", 66: "|"}


class Code:
	pass


class Reader:
	"""Python 1.5 marshal format (Python/marshal.c, r_object)."""

	def __init__(self, data, pos=0):
		self.d = data
		self.p = pos

	def byte(self):
		b = self.d[self.p]
		self.p = self.p + 1
		return b

	def short(self):
		v = struct.unpack("<h", self.d[self.p:self.p + 2])[0]
		self.p = self.p + 2
		return v

	def long(self):
		v = struct.unpack("<i", self.d[self.p:self.p + 4])[0]
		self.p = self.p + 4
		return v

	def raw(self, n):
		if n < 0 or self.p + n > len(self.d):
			raise ValueError("bad length %d at offset %d" % (n, self.p))
		v = self.d[self.p:self.p + n]
		self.p = self.p + n
		return v

	def obj(self):
		at = self.p
		t = chr(self.byte())
		if t == "0":
			return None  # NULL (dict terminator)
		if t == "N":
			return None
		if t == ".":
			return Ellipsis
		if t == "i":
			return self.long()
		if t == "I":
			return struct.unpack("<q", self.raw(8))[0]
		if t == "l":
			n = self.long()
			v = 0
			for i in range(abs(n)):
				v = v | (struct.unpack("<H", self.raw(2))[0] << (15 * i))
			return -v if n < 0 else v
		if t == "f":
			return float(self.raw(self.byte()).decode("ascii"))
		if t == "x":
			re_ = float(self.raw(self.byte()).decode("ascii"))
			im = float(self.raw(self.byte()).decode("ascii"))
			return complex(re_, im)
		if t == "s":
			return self.raw(self.long()).decode("latin-1")
		if t == "(":
			return tuple([self.obj() for i in range(self.long())])
		if t == "[":
			return [self.obj() for i in range(self.long())]
		if t == "{":
			d = {}
			while 1:
				k = self.obj_or_end()
				if k is StopIteration:
					return d
				d[k] = self.obj()
		if t == "c":
			c = Code()
			c.argcount = self.short()
			c.nlocals = self.short()
			c.stacksize = self.short()
			c.flags = self.short()
			c.code = self.obj().encode("latin-1")
			c.consts = self.obj()
			c.names = self.obj()
			c.varnames = self.obj()
			c.filename = self.obj()
			c.name = self.obj()
			c.firstlineno = self.short()
			c.lnotab = self.obj().encode("latin-1")
			return c
		raise ValueError("unknown marshal type %r at offset %d" % (t, at))

	def obj_or_end(self):
		if self.d[self.p] == 0x30:  # '0'
			self.p = self.p + 1
			return StopIteration
		return self.obj()


def load_pyc(path):
	f = open(path, "rb")
	data = f.read()
	f.close()
	if len(data) < 9:
		raise ValueError("too short")
	magic = struct.unpack("<H", data[:2])[0]
	if data[2:4] != b"\r\n" or magic != MAGIC_15:
		raise ValueError("not a Python 1.5 .pyc (magic %d)" % magic)
	co = Reader(data, 8).obj()
	if not isinstance(co, Code):
		raise ValueError("top object is not a code object")
	return co


def lnotab_lines(co):
	"""offset -> line from co_lnotab (used when SET_LINENO is absent, i.e. -O)."""
	res = []
	line = co.firstlineno
	addr = 0
	t = co.lnotab
	for i in range(0, len(t) - 1, 2):
		addr = addr + t[i]
		line = line + t[i + 1]
		res.append((addr, line))
	return res


def decode(co):
	"""List of (offset, opcode, arg or None)."""
	b = co.code
	out = []
	i = 0
	n = len(b)
	while i < n:
		op = b[i]
		if op >= HAVE_ARGUMENT:
			if i + 2 >= n:
				arg = None
			else:
				arg = b[i + 1] | (b[i + 2] << 8)
			out.append((i, op, arg))
			i = i + 3
		else:
			out.append((i, op, None))
			i = i + 1
	return out


def short_repr(v, lim=40):
	if isinstance(v, Code):
		return "<code %s>" % v.name
	r = repr(v)
	if len(r) > lim:
		r = r[:lim - 3] + "..."
	return r


def signature(co, ndefaults=0):
	args = list(co.varnames[:co.argcount])
	if ndefaults:
		for i in range(len(args) - ndefaults, len(args)):
			args[i] = args[i] + "=.."
	k = co.argcount
	if co.flags & CO_VARARGS:
		args.append("*" + co.varnames[k])
		k = k + 1
	if co.flags & CO_VARKEYWORDS:
		args.append("**" + co.varnames[k])
	return "(" + ", ".join(args) + ")"


class Func:
	def __init__(self, co, qual, kind, ndefaults):
		self.co = co
		self.qual = qual
		self.kind = kind  # module / def / class
		self.ndefaults = ndefaults
		self.ins = decode(co)
		self.lines = {}
		self.calls = []  # (line, text)
		self.unknown = []


def analyze(f):
	"""Assign lines to offsets and rebuild calls with a symbolic stack."""
	co = f.co
	tab = lnotab_lines(co)
	ti = 0
	line = co.firstlineno
	stack = []

	def pop(n=1):
		res = []
		for i in range(n):
			res.insert(0, stack.pop() if stack else "?")
		return res

	children = []  # (code, ndefaults, storename)
	pending_fn = None
	for off, op, arg in f.ins:
		while ti < len(tab) and tab[ti][0] <= off:
			line = tab[ti][1]
			ti = ti + 1
		if op == 127:
			line = arg
		f.lines[off] = line
		if op not in OPNAMES:
			f.unknown.append((off, op))
			continue
		if op == 100:
			v = co.consts[arg]
			stack.append(v if isinstance(v, Code) else short_repr(v, 24))
		elif op in (101, 116):
			stack.append(co.names[arg])
		elif op == 124:
			stack.append(co.varnames[arg])
		elif op == 105:
			stack.append("%s.%s" % (pop()[0], co.names[arg]))
		elif op == 107:
			stack.append(co.names[arg])
		elif op == 108:
			stack.append(co.names[arg])
		elif op == 131:
			npos = arg & 0xFF
			nkw = arg >> 8
			kw = pop(2 * nkw)
			args = pop(npos)
			fn = pop()[0]
			parts = [str(a) for a in args]
			for i in range(0, len(kw), 2):
				parts.append("%s=%s" % (str(kw[i]).strip("'"), kw[i + 1]))
			fname = fn if isinstance(fn, str) else "<expr>"
			text = "%s(%s)" % (fname, ", ".join(parts))
			if len(text) > 120:
				text = text[:117] + "..."
			f.calls.append((line, text))
			stack.append(fname + "()")
		elif op == 132:
			c = pop()[0]  # code object is on top, defaults below it
			pop(arg)
			pending_fn = (c, arg)
			stack.append("<function>")
		elif op == 89:
			pop(3)
			stack.append("<class>")
		elif op in (90, 97, 125):
			name = co.names[arg] if op != 125 else co.varnames[arg]
			v = pop()[0]
			if pending_fn and v == "<function>":
				children.append((pending_fn[0], pending_fn[1], name, "def"))
				pending_fn = None
		elif op == 95:
			pop(2)
		elif op == 4:
			stack.append(stack[-1] if stack else "?")
		elif op == 2:
			a, b = pop(2)
			stack.append(b)
			stack.append(a)
		elif op == 3:
			a, b, c = pop(3)
			stack.append(c)
			stack.append(a)
			stack.append(b)
		elif op in BINOPS:
			a, b = pop(2)
			stack.append("<expr>")
		elif op == 25:
			a, b = pop(2)
			stack.append("%s[%s]" % (a, b))
		elif op == 106:
			pop(2)
			stack.append("<cmp>")
		elif op in (102, 103):
			items = pop(arg)
			stack.append(("(%s)" if op == 102 else "[%s]") % ", ".join([str(x) for x in items]))
		elif op == 104:
			stack.append("{}")
		elif op in (92, 93):
			pop()
			for i in range(arg):
				stack.append("?")
		elif op in (10, 11, 12, 13, 15):
			pop()
			stack.append("<expr>")
		elif op in (30, 31, 32, 33):
			pop(1 + {30: 0, 31: 1, 32: 1, 33: 2}[op])
			stack.append("<slice>")
		elif op in (40, 41, 42, 43):
			pop(2 + {40: 0, 41: 1, 42: 1, 43: 2}[op])
		elif op in (50, 51, 52, 53):
			pop(1 + {50: 0, 51: 1, 52: 1, 53: 2}[op])
		elif op == 60:
			pop(3)
		elif op == 61:
			pop(2)
		elif op in (1, 71, 83, 96):
			pop()
		elif op == 85:
			pop(3)
		elif op == 130:
			pop(arg)
		elif op == 133:
			pop(arg)
			stack.append("<slice>")
		elif op == 114:  # FOR_LOOP: seq, idx -> seq, idx+1, item
			stack.append("<item>")
		elif op == 82:
			stack.append("<locals>")
		elif op in (111, 112):
			pass  # value stays on the stack
		elif op == 127:
			pass
		# Statement boundary: drop junk so errors do not leak far.
		if op in (1, 83) and len(stack) > 4:
			del stack[:-4]
	return children


def classes_from(f):
	"""Find 'class X' code objects: LOAD_CONST code, MAKE_FUNCTION, CALL, BUILD_CLASS, STORE."""
	res = []
	ins = f.ins
	for i in range(len(ins)):
		off, op, arg = ins[i]
		if op == 89:
			# walk back to the MAKE_FUNCTION's LOAD_CONST
			j = i - 1
			while j >= 0 and ins[j][1] != 132:
				j = j - 1
			k = j - 1
			while k >= 0 and not (ins[k][1] == 100 and isinstance(f.co.consts[ins[k][2]], Code)):
				k = k - 1
			name = None
			if i + 1 < len(ins) and ins[i + 1][1] in (90, 97, 125):
				o = ins[i + 1]
				name = f.co.varnames[o[2]] if o[1] == 125 else f.co.names[o[2]]
			if k >= 0:
				res.append((f.co.consts[ins[k][2]], name))
	return res


def collect(co):
	"""Walk every code object; returns Funcs in source order with qualified names."""
	out = []

	def walk(c, qual, kind, ndef):
		fn = Func(c, qual, kind, ndef)
		children = analyze(fn)
		out.append(fn)
		named = {}
		for sub, nd, store, k in children:
			if isinstance(sub, Code):
				named[id(sub)] = (store, nd, "def")
		for sub, store in classes_from(fn):
			named[id(sub)] = (store or sub.name, 0, "class")
		for k in c.consts:
			if isinstance(k, Code):
				store, nd, kd = named.get(id(k), (k.name, 0, "def"))
				prefix = "" if kind == "module" else qual + "."
				walk(k, prefix + (k.name if k.name != "?" else store), kd, nd)

	walk(co, "<module>", "module", 0)
	return out


def fmt_arg(co, off, op, arg):
	if arg is None:
		return ""
	if op == 100:
		return short_repr(co.consts[arg], 60)
	if op in NAME_OPS:
		return co.names[arg] if arg < len(co.names) else "#%d?" % arg
	if op in LOCAL_OPS:
		return co.varnames[arg] if arg < len(co.varnames) else "#%d?" % arg
	if op == 106:
		return CMP_OPS[arg] if arg < len(CMP_OPS) else str(arg)
	if op in REL_JUMPS:
		return "-> %d" % (off + 3 + arg)
	if op in ABS_JUMPS:
		return "-> %d" % arg
	if op == 131:
		return "%d pos, %d kw" % (arg & 0xFF, arg >> 8) if arg >> 8 else str(arg & 0xFF)
	return str(arg)


def jump_targets(f):
	t = set()
	for off, op, arg in f.ins:
		if op in REL_JUMPS:
			t.add(off + 3 + arg)
		elif op in ABS_JUMPS:
			t.add(arg)
	return t


def header(f):
	co = f.co
	if f.kind == "module":
		return "== module %s (%s)" % (co.filename, co.name)
	if f.kind == "class":
		return "\nclass %s  line %d" % (f.qual, co.firstlineno)
	return "\ndef %s%s  line %d" % (f.qual, signature(co, f.ndefaults), co.firstlineno)


def matches(f, wanted):
	if not wanted:
		return 1
	for w in wanted:
		if f.qual == w or f.qual.split(".")[-1] == w or f.qual.endswith("." + w):
			return 1
	return 0


def show(path, funcs, wanted, calls_only, out):
	for f in funcs:
		if not matches(f, wanted):
			continue
		if calls_only:
			for line, text in f.calls:
				out.write("%s:%s:%d: %s\n" % (path, f.qual, line, text))
			continue
		out.write(header(f) + "\n")
		targets = jump_targets(f)
		last = None
		for off, op, arg in f.ins:
			if op == 127:
				continue
			ln = f.lines.get(off)
			lcol = ("%5d" % ln) if ln != last else "     "
			last = ln
			mark = ">>" if off in targets else "  "
			name = OPNAMES.get(op, "<op %d>" % op)
			a = fmt_arg(f.co, off, op, arg)
			out.write(("%s %s %5d %-16s %s" % (lcol, mark, off, name, a)).rstrip() + "\n")
		if f.calls:
			out.write("  calls: " + "; ".join(["%d %s" % c for c in f.calls]) + "\n")


def iter_files(args):
	for a in args:
		if os.path.isdir(a):
			for root, dirs, files in os.walk(a):
				dirs.sort()
				for n in sorted(files):
					if n.lower().endswith(".pyc"):
						yield os.path.join(root, n)
		else:
			yield a


def main(argv):
	wanted = []
	calls_only = 0
	paths = []
	i = 0
	while i < len(argv):
		a = argv[i]
		if a == "--func" and i + 1 < len(argv):
			wanted.append(argv[i + 1])
			i = i + 1
		elif a == "--calls-only":
			calls_only = 1
		elif a in ("-h", "--help"):
			print(__doc__)
			return 0
		else:
			paths.append(a)
		i = i + 1
	if not paths:
		print(__doc__)
		return 2
	rc = 0
	out = sys.stdout
	for p in iter_files(paths):
		try:
			funcs = collect(load_pyc(p))
		except Exception as e:
			sys.stderr.write("%s: cannot decode: %s\n" % (p, e))
			rc = 1
			continue
		bad = []
		for f in funcs:
			for off, op in f.unknown:
				bad.append("%s@%d op %d" % (f.qual, off, op))
		if bad:
			sys.stderr.write("%s: unknown opcodes: %s\n" % (p, ", ".join(bad[:10])))
			rc = 1
		show(p, funcs, wanted, calls_only, out)
	return rc


if __name__ == "__main__":
	try:
		sys.exit(main(sys.argv[1:]))
	except (BrokenPipeError, OSError):
		# Output pipe closed early (e.g. "| head" on Windows).
		try:
			sys.stdout = None
		except Exception:
			pass
		os._exit(0)
