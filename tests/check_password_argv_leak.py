#!/usr/bin/env python3
"""Regression check: no plaintext password may reach a bench subprocess argv.

Background: bench logs its full argv verbatim into bench.log, and the shell
logs the full command into history, so any secret passed as a CLI argument
leaks into both places. bench offers no stdin/file/env alternative for these
flags in unattended use (omitting them falls back to an interactive getpass
prompt, which needs a TTY).

What this checker does (three separate checks, reported separately):

  1. FLAG-ARGV check (AUTO-FAIL): a sensitive flag name appears with a value
     (`--flag=value` or `--flag value`) in text that is actually passed to,
     or built into a command used by, a subprocess sink
     (subprocess.run / Popen / call / check_output / check_call, os.system /
     os.popen). Python files are analysed with `ast` (string constants,
     f-strings, %-format, .format(), concatenation, list .append/.extend and
     variable flow into sinks are all traced); YAML/shell text is scanned
     line-wise, excluding `#` comments.
  2. KWARGS-PAYLOAD check (separate AUTO-FAIL): a secret carried under a
     non-obvious key (`pwd`, `password`, ...) inside a dict/JSON literal or a
     `bench execute ... --kwargs` payload that reaches a subprocess sink --
     i.e. no `--flag` at all, still a leak.
  3. WARNINGS (never fail): other occurrences of sensitive flag names that do
     NOT reach a subprocess sink -- comments, docstrings, error/help messages,
     detection lists, or test fixtures asserting rejection. Listed separately
     for manual review.

Usage:
  python3 tests/check_password_argv_leak.py [PATH ...]
      default paths: pwd.yml development/installer.py (relative to repo root)
  printf '%s' "$SECRET_UNDER_TEST" |
      python3 tests/check_password_argv_leak.py --check-bench-log path/to/bench.log
      bench.log check; the secret comes from STDIN only, never argv.

Exit code: 0 = no failures (warnings allowed), 1 = at least one failure.
Output never echoes source-line content, only file:line + flag/category, so a
failing line's secret value can never be printed by this tool.
"""

import ast
import os
import re
import sys

# Sensitive bench CLI flags. Each entry: (flag spelling, reason it is included).
# `--flag value` and `--flag=value` forms are both checked for every entry.
SENSITIVE_FLAGS = [
    # Explicitly required list:
    ("--admin-password", "frappe new-site/restore/reinstall Administrator secret"),
    ("--db-root-password", "frappe new-site/restore DB root secret"),
    ("--mariadb-root-password", "frappe alias of --db-root-password"),
    ("--db-password", "frappe new-site site DB password"),
    ("--password", "frappe add-user user password"),
    ("--pwd", "shorthand/secret-key convention in kwargs payloads"),
    # Discovered in bench's own source (frappe-bench wheel), same leak vector
    # (bench/cli.py logs the FULL argv of every bench command verbatim):
    ("--mysql-root-password", "frappe-bench 5.31.0 install.py: bench install mariadb"),
    ("--mysql_root_password", "frappe-bench 5.31.0 install.py: explicit underscore alias"),
    ("--mariadb_root_password", "frappe-bench 5.31.0 install.py: explicit underscore alias"),
    ("--root-password", "frappe drop-site DB root secret"),
]

# Dict/JSON keys that carry secrets without any --flag (separate check).
SECRET_KEYS = re.compile(
    r"""["'](pwd|passwd|password|admin_password|db_password|db_root_password"""
    r"""|root_password|mysql_root_password|mariadb_root_password)["']\s*:""",
    re.IGNORECASE,
)

SUBPROCESS_FUNCS = {"run", "Popen", "call", "check_output", "check_call"}

EQ_FORMS = [(flag, re.compile(re.escape(flag) + r"\s*=\s*\S")) for flag, _ in SENSITIVE_FLAGS]
SPACE_FORMS = [(flag, re.compile(re.escape(flag) + r"\s+(?!-)\S")) for flag, _ in SENSITIVE_FLAGS]


def flag_in_text(text):
    """Return the first sensitive flag matched in text (either form), else None."""
    for flag, rx in EQ_FORMS:
        if rx.search(text):
            return flag + " (equals form)"
    for flag, rx in SPACE_FORMS:
        if rx.search(text):
            return flag + " (space form)"
    return None


def flag_name_mentioned(text):
    """Return True if any sensitive flag name appears at all (for warnings)."""
    return any(flag in text for flag, _ in SENSITIVE_FLAGS)


class SubprocessFlowVisitor(ast.NodeVisitor):
    """Collect subprocess sink calls and name->expression bindings per scope."""

    def __init__(self):
        self.sinks = []  # (Call node, scope-id)
        self.bindings = {}  # (scope-id, name) -> [value nodes]
        self.mutations = {}  # (scope-id, name) -> [appended/added value nodes]
        self.scope_stack = ["module"]

    @property
    def scope(self):
        return self.scope_stack[-1]

    def _is_subprocess_sink(self, func):
        if isinstance(func, ast.Attribute) and func.attr in SUBPROCESS_FUNCS:
            val = func.value
            if isinstance(val, ast.Name) and val.id in ("subprocess", "sp"):
                return True
            # os.system / os.popen bonus sinks
            if isinstance(val, ast.Name) and val.id == "os" and func.attr in ("system", "popen"):
                return True
        if isinstance(func, ast.Name) and func.id in SUBPROCESS_FUNCS | {"system", "popen"}:
            return True  # from subprocess/os import ...
        return False

    def visit_FunctionDef(self, node):
        self.scope_stack.append("func:" + node.name)
        self.generic_visit(node)
        self.scope_stack.pop()

    def visit_AsyncFunctionDef(self, node):
        self.visit_FunctionDef(node)

    def visit_Assign(self, node):
        for target in node.targets:
            if isinstance(target, ast.Name):
                self.bindings.setdefault((self.scope, target.id), []).append(node.value)
        self.generic_visit(node)

    def visit_AugAssign(self, node):
        if isinstance(node.target, ast.Name):
            self.mutations.setdefault((self.scope, node.target.id), []).append(node.value)
        self.generic_visit(node)

    def visit_Call(self, node):
        if self._is_subprocess_sink(node.func):
            self.sinks.append((node, self.scope))
        # list.append(x) / list.extend([..]) / list.insert(i, x) mutations
        func = node.func
        if (
            isinstance(func, ast.Attribute)
            and func.attr in ("append", "extend", "insert")
            and isinstance(func.value, ast.Name)
        ):
            args = node.args if func.attr != "insert" else node.args[1:]
            for a in args:
                self.mutations.setdefault((self.scope, func.value.id), []).append(a)
        self.generic_visit(node)


def element_text(node):
    """Best-effort literal text of one argv element (dynamic parts -> <expr>)."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):
        parts = []
        for v in node.values:
            if isinstance(v, ast.Constant) and isinstance(v.value, str):
                parts.append(v.value)
            else:
                parts.append("<expr>")
        return "".join(parts)
    return "<expr>"


def frags(node, bindings, mutations, scope, seen=None, depth=0, reached=None):
    """Yield (kind, lineno, text) string fragments for an expression node,
    following Name bindings (with cycle guard) so variables used as argv
    elements (e.g. ["bench", "new-site", var]) are resolved, not skipped."""
    if seen is None:
        seen = set()
    if depth > 14 or node is None:
        return
    if isinstance(node, ast.Name):
        if reached is not None:
            reached.add((scope, node.id))
        key = (scope, node.id)
        if key in seen:
            return
        seen = seen | {key}
        for alt_scope in (scope, "module"):
            for bound in bindings.get((alt_scope, node.id), []):
                yield from frags(bound, bindings, mutations, scope, seen, depth + 1, reached)
            for mut in mutations.get((alt_scope, node.id), []):
                yield from frags(mut, bindings, mutations, scope, seen, depth + 1, reached)
        return
    if isinstance(node, ast.Starred):
        yield from frags(node.value, bindings, mutations, scope, seen, depth + 1, reached)
        return
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        yield ("const", node.lineno, node.value)
    elif isinstance(node, ast.JoinedStr):
        parts = []
        for v in node.values:
            if isinstance(v, ast.Constant) and isinstance(v.value, str):
                parts.append(v.value)
            else:
                parts.append("<expr>")
        yield ("fstring", getattr(node, "lineno", 0), "".join(parts))
    elif isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Mod)):
        # Yield sides individually AND their concatenation: without the join,
        # a split construction like "--admin-password=" + secret would evade
        # fragment-wise matching (neither side alone carries flag+value).
        yield ("joined", getattr(node, "lineno", 0),
               element_text(node.left) + element_text(node.right))
        yield from frags(node.left, bindings, mutations, scope, seen, depth + 1, reached)
        yield from frags(node.right, bindings, mutations, scope, seen, depth + 1, reached)
    elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
        # "....".format(...) / "...".join(...)
        yield from frags(node.func.value, bindings, mutations, scope, seen, depth + 1, reached)
        for a in node.args:
            yield from frags(a, bindings, mutations, scope, seen, depth + 1, reached)
    elif isinstance(node, (ast.List, ast.Tuple)):
        for e in node.elts:
            yield from frags(e, bindings, mutations, scope, seen, depth + 1, reached)
    elif isinstance(node, ast.Dict):
        for k in node.keys:
            yield from frags(k, bindings, mutations, scope, seen, depth + 1, reached)
        for v in node.values:
            yield from frags(v, bindings, mutations, scope, seen, depth + 1, reached)


def iter_string_fragments(node, depth=0):
    """Shallow fragment extraction without scope bindings (kept for compat)."""
    yield from frags(node, {}, {}, "module", set(), depth, None)


def resolve_to_fragments(expr, bindings, mutations, scope, seen=None, depth=0, reached=None):
    """Resolve an expression to string fragments, following Name bindings."""
    yield from frags(expr, bindings, mutations, scope, seen or set(), depth, reached)


def variable_argv_join(name, scope, bindings, mutations):
    """Space-joined candidate argv for a list-built variable.

    Catches the split-element construction `--flag`, `<value>` as two separate
    appends/elements (e.g. cmd.append("--admin-password"); cmd.append(secret)),
    where no single fragment carries flag+value. Returns (text, def_lineno).
    """
    elements, def_lineno = [], None
    for alt_scope in (scope, "module"):
        for bound in bindings.get((alt_scope, name), []):
            if def_lineno is None:
                def_lineno = getattr(bound, "lineno", 0)
            if isinstance(bound, (ast.List, ast.Tuple)):
                elements.extend(bound.elts)
        for mut in mutations.get((alt_scope, name), []):
            if def_lineno is None:
                def_lineno = getattr(mut, "lineno", 0)
            if isinstance(mut, (ast.List, ast.Tuple)):
                elements.extend(mut.elts)  # from .extend([...])
            else:
                elements.append(mut)  # from .append(x) / += x
    if not elements:
        return None
    return " ".join(element_text(e) for e in elements), def_lineno or 0


def check_python_file(path):
    """Return (failures, warnings); each is a list of (line, detail)."""
    failures, warnings = [], []
    with open(path, encoding="utf-8") as fh:
        source = fh.read()
    tree = ast.parse(source, filename=path)
    visitor = SubprocessFlowVisitor()
    visitor.visit(tree)

    sink_fragments = []  # (sink_lineno, kind, frag_lineno, text)
    reached_names = set()
    for call_node, scope in visitor.sinks:
        if not call_node.args:
            continue
        for frag in resolve_to_fragments(
            call_node.args[0], visitor.bindings, visitor.mutations, scope, reached=reached_names
        ):
            sink_fragments.append((call_node.lineno, frag[0], frag[1], frag[2]))

    failed_lines = set()

    def record_failure(lineno, detail):
        if lineno not in failed_lines:
            failures.append((lineno, detail))
            failed_lines.add(lineno)

    for sink_lineno, kind, frag_lineno, text in sink_fragments:
        hit = flag_in_text(text)
        if hit:
            record_failure(sink_lineno, "FLAG-ARGV: %s reaches subprocess sink" % hit)
            continue
        if SECRET_KEYS.search(text) or ("--kwargs" in text and re.search(r"(?i)\bpwd\b", text)):
            record_failure(
                sink_lineno, "KWARGS-PAYLOAD: secret key in payload reaching subprocess sink"
            )

    # Per-variable argv joins: catches flag and value passed as SEPARATE list
    # elements/appends (e.g. cmd.append("--admin-password"); cmd.append(secret))
    # for variables proven to reach a subprocess sink. Checked once per name.
    checked_joins = set()
    for scope, name in reached_names:
        for alt_scope in (scope, "module"):
            if (alt_scope, name) in checked_joins:
                continue
            checked_joins.add((alt_scope, name))
            joined = variable_argv_join(name, alt_scope, visitor.bindings, visitor.mutations)
            if not joined:
                continue
            text, def_lineno = joined
            hit = flag_in_text(text)
            if hit:
                record_failure(
                    def_lineno or 0,
                    "FLAG-ARGV: %s split across argv elements of sink-reaching variable %r"
                    % (hit, name),
                )

    # Warnings: flag names in string constants / comments that reach NO sink.
    sink_texts = {t for _, _, _, t in sink_fragments}
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            if node.value in sink_texts:
                continue
            if flag_name_mentioned(node.value) and not flag_in_text(node.value):
                warnings.append((node.lineno, "flag name mentioned but not passed with a value"))
    for lineno, line in enumerate(source.splitlines(), 1):
        stripped = line.split("#", 1)
        comment = stripped[1] if len(stripped) > 1 and stripped[0].strip() else ""
        # naive: only treat ' #' as comment start; avoids '#' inside quotes
        idx = line.find(" #")
        comment = line[idx + 1 :] if idx != -1 else ""
        if comment and flag_name_mentioned(comment):
            warnings.append((lineno, "flag name in comment (no value passed)"))

    # de-duplicate warnings; drop any on lines already failed
    seen = set()
    uniq_warnings = []
    for ln, detail in warnings:
        if ln in failed_lines or (ln, detail) in seen:
            continue
        seen.add((ln, detail))
        uniq_warnings.append((ln, detail))
    return failures, uniq_warnings


def strip_yaml_comment(line):
    idx = line.find(" #")
    return line[:idx] if idx != -1 else line


def split_quoted(line):
    """Split a shell/YAML line into (unquoted_text, [quoted_spans])."""
    unquoted, quoted, buf, q = [], [], [], None
    i = 0
    while i < len(line):
        ch = line[i]
        if q is None and ch in ("'", '"'):
            if buf:
                unquoted.append("".join(buf))
                buf = []
            q = ch
            span = [ch]
            i += 1
            while i < len(line) and line[i] != q:
                span.append(line[i])
                i += 1
            if i < len(line):
                span.append(line[i])
                i += 1
            quoted.append("".join(span))
            q = None
        else:
            buf.append(ch)
            i += 1
    if buf:
        unquoted.append("".join(buf))
    return "".join(unquoted), quoted


def check_text_file(path):
    """Line-wise scan for YAML/shell text. Returns (failures, warnings).

    AUTO-FAIL only when flag+value sits in unquoted command position (i.e. it
    would actually become part of the executed argv). The same pattern inside
    a quoted span (typically an echo/help message, as in our fail-fast text)
    is a WARNING for manual review instead. Backslash continuations are
    joined first so split-line leaks are still caught.
    """
    failures, warnings = [], []
    with open(path, encoding="utf-8") as fh:
        raw_lines = fh.read().splitlines()
    # join backslash-continued lines, keeping the starting line number
    logical = []
    buf, start = [], None
    for lineno, line in enumerate(raw_lines, 1):
        if start is None:
            start = lineno
        if line.rstrip().endswith("\\"):
            buf.append(line.rstrip()[:-1])
        else:
            buf.append(line)
            logical.append((start, " ".join(buf)))
            buf, start = [], None
    if buf:
        logical.append((start, " ".join(buf)))

    for lineno, line in logical:
        code = strip_yaml_comment(line)
        bare, quoted_spans = split_quoted(code)
        hit = flag_in_text(bare)
        if hit:
            failures.append((lineno, "FLAG-ARGV: %s in shell/YAML command text" % hit))
            continue
        for span in quoted_spans:
            qhit = flag_in_text(span)
            if qhit:
                warnings.append(
                    (lineno, "flag+value inside quoted string (message or quoted arg?): %s" % qhit)
                )
                break
        else:
            if flag_name_mentioned(code):
                warnings.append((lineno, "flag name mentioned without a value"))
            elif flag_name_mentioned(line) and not flag_name_mentioned(code):
                warnings.append((lineno, "flag name in comment only"))
    return failures, uniq(warnings)


def uniq(pairs):
    seen, out = set(), []
    for item in pairs:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out


def check_path(path):
    if path.endswith(".py"):
        return check_python_file(path)
    return check_text_file(path)


def main(argv):
    # bench.log check: secret arrives on STDIN only, never argv.
    if argv and argv[0] == "--check-bench-log":
        if len(argv) < 2:
            print("usage: check_password_argv_leak.py --check-bench-log <bench.log>", file=sys.stderr)
            return 2
        secret = sys.stdin.read()
        if not secret:
            print("SKIP (b): empty secret on stdin, nothing to search for")
            return 0
        with open(argv[1], encoding="utf-8", errors="replace") as fh:
            found = [(i, None) for i, l in enumerate(fh.read().splitlines(), 1) if secret in l]
        if found:
            print("FAIL (b): test marker found in %s at line(s): %s" % (argv[1], [i for i, _ in found]))
            return 1
        print("PASS (b): test marker absent from %s" % argv[1])
        return 0

    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    targets = argv or ["pwd.yml", "development/installer.py"]
    total_fail, total_warn = [], []
    for t in targets:
        path = t if os.path.isabs(t) else os.path.join(repo_root, t)
        failures, warnings = check_path(path)
        for ln, detail in failures:
            total_fail.append("%s:%d: FAIL: %s" % (t, ln, detail))
        for ln, detail in warnings:
            total_warn.append("%s:%d: warning: %s" % (t, ln, detail))

    for w in sorted(total_warn):
        print(w)
    if total_fail:
        for f in sorted(total_fail):
            print(f)
        print("FAIL: %d password-argv leak(s) detected" % len(total_fail))
        return 1
    print("PASS (a): no password-bearing bench CLI arguments reach a subprocess sink")
    if total_warn:
        print("(%d warning(s) listed above for manual review; warnings do not fail)" % len(total_warn))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
