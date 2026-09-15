#!/usr/bin/env bash
# Rotate the test credentials exposed in plaintext by the prior bench-argv
# leak incident (values remain readable in old ~/.zsh_history and bench.log
# entries -- those artifacts cannot be "unexposed" by this script).
#
# Accounts covered (test/throwaway only -- rotation is OPTIONAL and left to
# the operator's discretion):
#   - abdo22@gmail.com (test customer account)
#   - Administrator (site admin account)
#
# SAFETY DESIGN -- read before running:
# - The new passwords are NEVER passed as CLI arguments and NEVER read from
#   environment variables expanded into arguments (both would reintroduce the
#   exact leak this rotates away from: bench logs its full argv into
#   bench.log, and the shell logs the full command into history).
# - Each bench invocation below OMITS the password argument on purpose, so
#   bench prompts securely via getpass (nothing on the command line).
# - This script is NOT runnable unattended, by design: it aborts unless
#   stdin is an interactive TTY, so the operator must be present to type
#   each new password when prompted.
#
# Usage (run by hand at a TTY; NOT executed by any automation):
#   SITE=development.localhost bash scripts/rotate-exposed-test-credentials.sh
#   (default site: development.localhost; BENCH_DIR may also be overridden the
#   same way, but normally needs no override)
#
# PREPARED BUT NOT EXECUTED -- run it yourself when/if you choose to rotate.
set -euo pipefail

# Resolve locations from this script's own path -- never from the caller's
# current directory. bench commands are context-sensitive and only work when
# run from inside the bench directory; launching this script from the repo
# root (or anywhere else) must not change that.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
BENCH_DIR="${BENCH_DIR:-$REPO_ROOT/development/frappe-bench}"
SITE="${SITE:-development.localhost}"

if [ ! -d "$BENCH_DIR/apps" ] || [ ! -d "$BENCH_DIR/sites" ]; then
	echo "ERROR: invalid bench directory: $BENCH_DIR" >&2
	echo "(expected both 'apps/' and 'sites/' underneath it)" >&2
	exit 1
fi

echo "Using bench directory: $BENCH_DIR"
echo "Using site: $SITE"
echo "Password will be requested interactively and will not be passed as a CLI argument."

if [ ! -t 0 ]; then
	echo "ERROR: this script requires an interactive TTY (it types nothing for you;" >&2
	echo "bench will prompt securely via getpass for each new password)." >&2
	exit 1
fi

cd "$BENCH_DIR"

echo "Rotating test customer account password (type the NEW password at the prompt):"
bench --site "$SITE" set-password abdo22@gmail.com

echo "Rotating Administrator password (type the NEW password at the prompt):"
bench --site "$SITE" set-admin-password

echo "Done. Verify by logging in manually with the new passwords."
echo "Note: the previously exposed values are still present in old shell-history"
echo "and bench.log entries -- treat those old values as compromised and do not reuse them."
