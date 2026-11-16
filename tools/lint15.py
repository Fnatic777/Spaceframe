"""lint15 - static checker for Star Trek Bridge Commander scripts (Python 1.5.2).

Runs on the host with Python 3. Mod code must stay in the subset that both
Python 1.5.2 and Python 3 can parse (print (x) with parentheses, no
"except X, e", no backticks, no "<>"), so it can be checked with py3's ast.

Usage:
    python tools/lint15.py [paths...]      (default: every */scripts dir in the repo)
    python tools/lint15.py --quiet ...     (errors only)

Exit code 1 when any ERROR is found. WARN lines need a human look.
"""
import ast
import os
import sys

# Builtins that do not exist in Python 1.5.2.
MISSING_BUILTINS = {
	"True", "False", "bool", "dict", "enumerate", "zip", "sum", "sorted",
	"reversed", "set", "frozenset", "any", "all", "iter", "next", "object",
	"property", "staticmethod", "classmethod", "super", "unicode",
	"basestring", "file", "isinstance_tuple", "NotImplemented", "bytes",
	"exec", "print_function",
}

# str methods (1.5 strings have no methods: use the string module).
STR_METHODS_ERR = {
	"format", "startswith", "endswith", "strip", "lstrip", "rstrip", "lower",
	"upper", "split", "rsplit", "join", "splitlines", "zfill", "title",
	"capitalize", "swapcase", "isdigit", "isalpha", "isspace", "encode",
	"decode", "partition", "rpartition", "center", "ljust", "rjust",
}
STR_METHODS_WARN = {"find", "rfind", "replace", "count", "index", "rindex"}
STRING_MODULES = {"string", "strop", "os", "path", "sys"}


def hungarian_dict(node):
	"""Names like dFoo / g_dFoo are dicts by the project's naming rule."""
	if isinstance(node, ast.Name):
		n = node.id
	elif isinstance(node, ast.Attribute):
		n = node.attr
	else:
		return False
	if n.startswith("g_"):
		n = n[2:]
	return len(n) > 1 and n[0] == "d" and n[1].isupper()


class Checker(ast.NodeVisitor):
	def __init__(self, path, tree):
		self.path = path
		self.out = []
		self.defined = set()
		self.module_globals = set()
		for node in ast.walk(tree):
			if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
				self.defined.add(node.name)
			elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
				self.defined.add(node.id)
			elif isinstance(node, ast.alias):
				self.defined.add((node.asname or node.name).split(".")[0])
		for node in tree.body:
			for t in getattr(node, "targets", []):
				if isinstance(t, ast.Name):
					self.module_globals.add(t.id)
		self.func_stack = []
		self.loop_try = []  # per loop: depth of try blocks entered since the loop

	def err(self, node, code, msg):
		self.out.append((getattr(node, "lineno", 0), "ERROR", code, msg))

	def warn(self, node, code, msg):
		self.out.append((getattr(node, "lineno", 0), "WARN", code, msg))

	# --- syntax that 1.5.2 does not have -------------------------------
	def visit_AugAssign(self, node):
		self.err(node, "E01", "augmented assignment (x += y): write x = x + y")
		self.generic_visit(node)

	def _comp(self, node):
		self.err(node, "E02", "comprehension/generator: use a classic for loop")
		self.generic_visit(node)

	visit_ListComp = visit_SetComp = visit_DictComp = visit_GeneratorExp = _comp

	def visit_IfExp(self, node):
		self.err(node, "E03", "conditional expression (a if c else b)")
		self.generic_visit(node)

	def visit_JoinedStr(self, node):
		self.err(node, "E04", "f-string: use '%' formatting")
		self.generic_visit(node)

	def visit_Set(self, node):
		self.err(node, "E05", "set literal")
		self.generic_visit(node)

	def visit_With(self, node):
		self.err(node, "E06", "with statement")
		self.generic_visit(node)

	def visit_Yield(self, node):
		self.err(node, "E07", "yield/generator")
		self.generic_visit(node)

	visit_YieldFrom = visit_Yield

	def visit_Nonlocal(self, node):
		self.err(node, "E08", "nonlocal")

	def visit_Constant(self, node):
		if node.value is True or node.value is False:
			self.err(node, "E09", "True/False: use 1/0")
		if getattr(node, "kind", None) == "u":
			self.err(node, "E10", "unicode literal u''")

	def visit_Import(self, node):
		for a in node.names:
			if a.asname:
				self.err(node, "E11", "import ... as ...: import the module and assign it")
		self.generic_visit(node)

	visit_ImportFrom = visit_Import

	def visit_Try(self, node):
		if node.handlers and node.finalbody:
			self.err(node, "E12", "try/except/finally combined: nest two try blocks")
		for h in node.handlers:
			if h.name:
				self.err(h, "E13", "except X as e: use sys.exc_info()")
		if self.loop_try:
			self.loop_try[-1] = self.loop_try[-1] + 1
		self.generic_visit(node)
		if self.loop_try:
			self.loop_try[-1] = self.loop_try[-1] - 1

	def visit_Raise(self, node):
		if node.cause is not None:
			self.err(node, "E14", "raise ... from ...")
		self.generic_visit(node)

	def visit_Subscript(self, node):
		if isinstance(node.slice, ast.Slice) and node.slice.step is not None:
			self.err(node, "E15", "extended slice a[i:j:k] (not on 1.5 lists/strings)")
		self.generic_visit(node)

	def _loop(self, node):
		# The loop's own test/iter is outside; body gets a fresh counter.
		self.loop_try.append(0)
		for s in node.body:
			self.visit(s)
		self.loop_try.pop()
		for s in node.orelse:
			self.visit(s)

	visit_For = visit_While = _loop

	def visit_Continue(self, node):
		if self.loop_try and self.loop_try[-1] > 0:
			self.err(node, "E16", "continue inside try: SyntaxError in 1.5, the whole module fails to load")

	# --- calls ---------------------------------------------------------
	def visit_Call(self, node):
		if node.keywords:
			self.err(node, "E17", "keyword/** arguments in a call: pass positionally (or use apply)")
		for a in node.args:
			if isinstance(a, ast.Starred):
				self.err(node, "E18", "f(*args) call: use apply(f, args)")
		f = node.func
		if isinstance(f, ast.Attribute):
			base = f.value
			is_mod = isinstance(base, ast.Name) and base.id in STRING_MODULES
			if not is_mod and f.attr in STR_METHODS_ERR:
				self.err(node, "E19", "string method .%s(): use the string module" % f.attr)
			elif not is_mod and f.attr in STR_METHODS_WARN and isinstance(base, (ast.Constant, ast.BinOp)):
				self.err(node, "E19", "string method .%s(): use the string module" % f.attr)
			elif not is_mod and f.attr in STR_METHODS_WARN:
				self.warn(node, "W19", ".%s() - fine on App objects, not on strings" % f.attr)
		if isinstance(f, ast.Name) and f.id == "print" and len(node.args) > 1:
			self.warn(node, "W20", "print (a, b) prints a tuple in 1.5: concatenate instead")
		self.generic_visit(node)

	def visit_Name(self, node):
		if isinstance(node.ctx, ast.Load) and node.id in MISSING_BUILTINS and node.id not in self.defined:
			self.err(node, "E21", "%s does not exist in 1.5.2" % node.id)

	def visit_Compare(self, node):
		for op, right in zip(node.ops, node.comparators):
			if isinstance(op, (ast.In, ast.NotIn)) and hungarian_dict(right):
				self.err(node, "E22", "'in' on a dict: use d.has_key(k)")
		self.generic_visit(node)

	# --- functions -----------------------------------------------------
	def visit_FunctionDef(self, node):
		a = node.args
		if a.kwonlyargs or getattr(a, "posonlyargs", []):
			self.err(node, "E23", "keyword-only/positional-only parameters")
		if node.decorator_list:
			self.err(node, "E24", "decorator")
		if node.returns or any(x.annotation for x in a.args):
			self.err(node, "E25", "annotations")
		self._global_position(node)
		self._missing_global(node)
		if self.func_stack:
			self._nested_scope(node, self.func_stack[-1])
		self.func_stack.append(node)
		saved = self.loop_try
		self.loop_try = []
		self.generic_visit(node)
		self.loop_try = saved
		self.func_stack.pop()

	visit_AsyncFunctionDef = visit_FunctionDef

	def visit_Lambda(self, node):
		if self.func_stack:
			self._nested_scope(node, self.func_stack[-1])
		self.generic_visit(node)

	def visit_ClassDef(self, node):
		if node.keywords:
			self.err(node, "E26", "class keyword arguments (metaclass=...)")
		if node.decorator_list:
			self.err(node, "E24", "decorator")
		saved = self.func_stack
		self.func_stack = []  # methods are not closures over an outer function
		self.generic_visit(node)
		self.func_stack = saved

	def _global_position(self, node):
		body = node.body
		i = 0
		if body and isinstance(body[0], ast.Expr) and isinstance(getattr(body[0], "value", None), ast.Constant) and isinstance(body[0].value.value, str):
			i = 1
		seen_other = False
		for s in body[i:]:
			if isinstance(s, ast.Global):
				if seen_other:
					self.warn(s, "W27", "global not at the top of the function")
			else:
				seen_other = True

	def _missing_global(self, node):
		declared = set()
		for n in ast.walk(node):
			if isinstance(n, ast.Global):
				declared.update(n.names)
		for n in self._own_nodes(node):
			if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store) and n.id.startswith("g_") and n.id not in declared:
				self.err(n, "E28", "assigns module global %s without 'global %s'" % (n.id, n.id))

	def _own_nodes(self, fn):
		"""Nodes of fn's body, not descending into nested defs/lambdas/classes."""
		stack = list(fn.body) if not isinstance(fn, ast.Lambda) else [fn.body]
		while stack:
			n = stack.pop()
			yield n
			if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef)):
				continue
			stack.extend(ast.iter_child_nodes(n))

	def _locals(self, fn):
		names = set()
		a = fn.args
		for x in a.args + a.kwonlyargs:
			names.add(x.arg)
		if a.vararg:
			names.add(a.vararg.arg)
		if a.kwarg:
			names.add(a.kwarg.arg)
		for n in self._own_nodes(fn):
			if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store):
				names.add(n.id)
			elif isinstance(n, (ast.FunctionDef, ast.ClassDef)):
				names.add(n.name)
			elif isinstance(n, ast.alias):
				names.add((n.asname or n.name).split(".")[0])
			elif isinstance(n, ast.Global):
				for g in n.names:
					names.discard(g)
		return names

	def _nested_scope(self, inner, outer):
		outer_locals = self._locals(outer) - self.module_globals
		inner_locals = self._locals(inner)
		for n in self._own_nodes(inner):
			if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load):
				if n.id in outer_locals and n.id not in inner_locals:
					self.err(n, "E29", "no nested scopes in 1.5: '%s' from the enclosing function is invisible here (pass it as a default arg)" % n.id)


def check_bytes(path, data):
	out = []
	if data.startswith(b"\xef\xbb\xbf"):
		out.append((1, "ERROR", "F01", "UTF-8 BOM"))
	lf = data.count(b"\n")
	crlf = data.count(b"\r\n")
	if lf != crlf:
		out.append((1, "ERROR", "F02", "line endings: %d LF, %d CRLF - must be all CRLF" % (lf, crlf)))
	for i, line in enumerate(data.split(b"\n")):
		try:
			line.decode("ascii")
		except UnicodeDecodeError:
			out.append((i + 1, "ERROR", "F03", "non-ASCII character"))
		stripped = line.lstrip(b"\t")
		if stripped.startswith(b" ") and line.startswith(b"\t"):
			out.append((i + 1, "WARN", "F04", "mixed tab/space indentation"))
	return out


def check_file(path):
	data = open(path, "rb").read()
	out = check_bytes(path, data)
	src = data.decode("ascii", "replace").replace("\r\n", "\n")
	try:
		tree = ast.parse(src, path)
		compile(src, path, "exec")
	except SyntaxError as e:
		out.append((e.lineno or 0, "ERROR", "S01", "py3 cannot parse (%s). Keep the dual-parse subset: print (x), no 'except X, e', no backticks, no <>" % e.msg))
		return out
	c = Checker(path, tree)
	c.visit(tree)
	out.extend(c.out)
	return out


def iter_files(paths):
	for p in paths:
		if os.path.isfile(p):
			yield p
			continue
		for root, dirs, files in os.walk(p):
			dirs[:] = [d for d in dirs if d not in ("__pycache__", ".git")]
			for f in sorted(files):
				if f.endswith(".py"):
					yield os.path.join(root, f)


def default_paths():
	repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
	res = []
	for name in sorted(os.listdir(repo)):
		s = os.path.join(repo, name, "scripts")
		if os.path.isdir(s):
			res.append(s)
	return res


def main(argv):
	quiet = "--quiet" in argv
	paths = [a for a in argv if not a.startswith("--")] or default_paths()
	n_err = n_warn = n_files = 0
	for f in iter_files(paths):
		n_files = n_files + 1
		for line, level, code, msg in sorted(check_file(f)):
			if level == "ERROR":
				n_err = n_err + 1
			else:
				n_warn = n_warn + 1
				if quiet:
					continue
			print("%s:%d: %s %s %s" % (f, line, level, code, msg))
	print("lint15: %d files, %d errors, %d warnings" % (n_files, n_err, n_warn))
	return 1 if n_err else 0


if __name__ == "__main__":
	sys.exit(main(sys.argv[1:]))
