#!/usr/bin/env bash
# Thin wrapper kept for backward compatibility.
# The real check now lives in tests/check_password_argv_leak.py (AST-based
# subprocess-argv tracing plus a separate kwargs-payload check). All
# arguments are forwarded unchanged:
#
#   bash tests/check_password_argv_leak.sh [PATH ...]
#   printf '%s' "$SECRET_UNDER_TEST" | bash tests/check_password_argv_leak.sh --check-bench-log path/to/bench.log
#
set -euo pipefail
exec python3 "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/check_password_argv_leak.py" "$@"
