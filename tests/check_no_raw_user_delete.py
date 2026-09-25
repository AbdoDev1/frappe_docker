#!/usr/bin/env python3
"""Regression check: no raw-SQL deletion of users or password rows in OUR code.

Background (§4-31): frappe.delete_doc("User") always cleans the __Auth row
(delete_doc.py via delete_all_passwords_for), while raw-SQL deletes bypass
it and leave orphan password rows (proven once in the 1a T7 audit). The
standing rule is therefore: user deletions go exclusively through
delete_doc -- never raw SQL.

What this checker does (AUTO-FAIL on any hit):
  1. Raw-SQL check: any DELETE FROM targeting `tabUser` or `__Auth`
     (any quoting/case) in a scanned Python/shell/YAML source.
  2. ORM-bypass check (AST): frappe.db.delete("User" | "__Auth", ...)
     calls -- same bypass class, no delete_doc cascade.

Scope is OUR code only (default paths below, relative to repo root):
vendored framework code is upstream, not gated here (its own
password.py primitives are the blessed cleanup path delete_doc uses).

Usage:
  python3 tests/check_no_raw_user_delete.py [PATH ...]

Exit code: 0 = clean, 1 = at least one violation.
Output prints file:line + matched category only.
"""

import ast
import os
import re
import sys

DEFAULT_PATHS = [
    "development/frappe-bench/apps/biozone_web",
    "scripts",
    "development/installer.py",
    "pwd.yml",
    "tests",
]

RAW_DELETE_RX = re.compile(
    r"delete\s+from\s+[`\"']?(tabUser|__Auth)[`\"']?",
    re.IGNORECASE,
)

SKIP_DIRS = {"__pycache__", ".ruff_cache", ".git", "node_modules"}


def iter_files(paths):
    for p in paths:
        if os.path.isfile(p):
            yield p
        elif os.path.isdir(p):
            for root, dirs, files in os.walk(p):
                dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
                for f in files:
                    if f.endswith((".py", ".sh", ".yml", ".yaml")):
                        yield os.path.join(root, f)


class DbDeleteVisitor(ast.NodeVisitor):
    """Find frappe.db.delete("User"|"__Auth", ...) calls."""

    def __init__(self):
        self.hits = []  # lineno list

    def visit_Call(self, node):  # noqa: N802 (ast convention)
        func = node.func
        is_db_delete = (
            isinstance(func, ast.Attribute)
            and func.attr == "delete"
            and isinstance(func.value, ast.Attribute)
            and func.value.attr == "db"
        )
        if is_db_delete and node.args:
            first = node.args[0]
            if isinstance(first, ast.Constant) and isinstance(first.value, str):
                if first.value.strip().strip("`\"'").lower() in ("user", "tabuser", "__auth"):
                    self.hits.append(node.lineno)
        self.generic_visit(node)


def check_file(path):
    """Return list of (line, category, snippet-note)."""
    hits = []
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            text = fh.read()
    except OSError:
        return hits
    for i, line in enumerate(text.splitlines(), 1):
        stripped = line.split("#", 1)[0]
        m = RAW_DELETE_RX.search(stripped)
        if m:
            hits.append((i, "raw-delete", m.group(1)))
    if path.endswith(".py"):
        try:
            tree = ast.parse(text)
        except SyntaxError:
            return hits
        visitor = DbDeleteVisitor()
        visitor.visit(tree)
        for lineno in visitor.hits:
            hits.append((lineno, "db-delete-bypass", "User/__Auth"))
    return hits


def main(argv):
    paths = argv[1:] or DEFAULT_PATHS
    repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    failures = 0
    for p in paths:
        full = p if os.path.isabs(p) else os.path.join(repo, p)
        for f in iter_files([full]):
            for lineno, category, _note in check_file(f):
                rel = os.path.relpath(f, repo)
                print(f"FAIL {rel}:{lineno} [{category}]")
                failures += 1
    if failures:
        print(f"==== {failures} violation(s) ====")
        return 1
    print("OK: no raw user/password deletes in scoped paths")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
