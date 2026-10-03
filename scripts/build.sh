#!/usr/bin/env bash
# build.sh — lock-driven Docker build driver.
#
# Reads upstream.lock (+ an explicit --apps-json input), resolves every
# build input, generates pins.list, and invokes docker build with all
# values passed explicitly. Fail-closed: any missing/invalid input aborts
# before Docker runs. --dry-run resolves and prints everything without
# invoking Docker, writing images, or touching the lock.
#
# Usage:
#   scripts/build.sh --apps-json PATH --tag TAG [--lock PATH]
#                    [--containerfile PATH] [--dry-run]
#
# Exit 0: resolved (dry-run) / build launched. Exit 1: input/policy error.
# Exit 2: usage error.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APPS_JSON=""
LOCK_FILE="$REPO_ROOT/upstream.lock"
IMAGE_TAG=""
CONTAINERFILE="$REPO_ROOT/images/layered/Containerfile"
DRY_RUN=0

usage() {
  cat >&2 <<'EOF'
usage: scripts/build.sh --apps-json PATH --tag TAG [--lock PATH] [--containerfile PATH] [--dry-run]
  --apps-json PATH : explicit build input (never implicit; the dev example is refused)
  --tag TAG        : resulting image tag (explicit, no default)
  --lock PATH      : lock file (default: upstream.lock)
  --containerfile  : Dockerfile path (default: images/layered/Containerfile)
  --dry-run        : resolve + print only; never invoke Docker
EOF
  exit 2
}

while [ $# -gt 0 ]; do
  case "$1" in
    --apps-json) APPS_JSON="${2:-}"; shift 2 ;;
    --lock) LOCK_FILE="${2:-}"; shift 2 ;;
    --tag) IMAGE_TAG="${2:-}"; shift 2 ;;
    --containerfile) CONTAINERFILE="${2:-}"; shift 2 ;;
    --dry-run) DRY_RUN=1; shift ;;
    -h | --help) usage ;;
    *) echo "ERROR: unknown arg: $1" >&2; usage ;;
  esac
done

[ -n "$APPS_JSON" ] || { echo "ERROR: --apps-json PATH is required" >&2; usage; }
[ -n "$IMAGE_TAG" ] || { echo "ERROR: --tag TAG is required" >&2; usage; }

# The dev example must never be a production input (resolved-path compare).
if [ "$(realpath -m "$APPS_JSON")" = "$REPO_ROOT/development/apps-example.json" ]; then
  echo "ERROR: development/apps-example.json is refused as a build input" >&2
  exit 1
fi

# --- resolve everything from the lock (python3 stdlib only) ---
RESOLVED="$(python3 - "$LOCK_FILE" "$APPS_JSON" <<'PYEOF'
import json, re, sys

lock_path, apps_path = sys.argv[1], sys.argv[2]
HEX40 = re.compile(r"^[0-9a-f]{40}$", re.IGNORECASE)
TAG_RE = re.compile(r"^v[0-9]+\.[0-9]+\.[0-9]+$")
NAME_RE = re.compile(r"^[A-Za-z0-9_.-]+$")
REF_RE = re.compile(r"^[A-Za-z0-9_.:/-]+$")

def fail(msg):
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(1)

try:
    lock = json.load(open(lock_path, encoding="utf-8"))
except Exception as exc:
    fail(f"lock unreadable: {lock_path}: {exc}")
if lock.get("schema") != 1:
    fail("lock schema must be 1")

sources = lock.get("sources", {})
if not isinstance(sources, dict) or not sources:
    fail("lock sources must be a non-empty object")
for name, spec in sources.items():
    if not isinstance(spec, dict):
        fail(f"sources.{name}: must be an object")
    if "tag" in spec:
        fail(f"sources.{name}: tag is not allowed; use ref")
    url = spec.get("repo", "")
    if not (isinstance(url, str) and url.strip() and " " not in url):
        fail(f"sources.{name}: repo must be a non-empty URL without spaces")
    ref = spec.get("ref", "")
    if not (isinstance(ref, str) and REF_RE.fullmatch(ref)):
        fail(f"sources.{name}: ref must match {REF_RE.pattern}")
    sha = spec.get("sha", "")
    if not (isinstance(sha, str) and HEX40.fullmatch(sha)):
        fail(f"sources.{name}: sha must be full 40-hex")
    if spec.get("pinned") is not True:
        fail(f"sources.{name}: pinned must be true for a build")

try:
    raw = open(apps_path, encoding="utf-8").read()
    data = json.loads(raw)
except Exception as exc:
    fail(f"apps.json unreadable: {apps_path}: {exc}")

names = []
if isinstance(data, dict):
    for k, v in data.items():
        if not isinstance(k, str) or not NAME_RE.match(k) or not isinstance(v, dict):
            fail(f"apps.json: invalid entry: {k!r}")
        names.append(k)
elif isinstance(data, list):
    for entry in data:
        if not isinstance(entry, dict):
            fail("apps.json: list entries must be objects")
        url = entry.get("url", "")
        if not isinstance(url, str) or not url:
            fail("apps.json: list entry missing url")
        base = url.rstrip("/").rsplit("/", 1)[-1]
        if base.endswith(".git"):
            base = base[:-4]
        if not NAME_RE.match(base):
            fail(f"apps.json: invalid app name from url: {url!r}")
        names.append(base)
else:
    fail("apps.json: unsupported top-level type")
if sorted(set(names)) == [] or len(set(names)) != len(names):
    fail("apps.json: empty or duplicated app names")

custom_lock = [n for n in sources if n not in ("frappe", "erpnext")]
if sorted(set(names) - {"frappe", "erpnext"}) != sorted(custom_lock):
    fail(f"apps.json/lock name mismatch: apps={sorted(set(names))} lock-custom={sorted(custom_lock)}")

def kind_of(ref):
    return "tag" if TAG_RE.match(ref) else "branch"

out = []
out.append(f"FRAPPE_REF={sources['frappe']['ref']}")
out.append(f"FRAPPE_SHA={sources['frappe']['sha']}")
out.append(f"ERPNEXT_REF={sources['erpnext']['ref']}")
out.append(f"ERPNEXT_SHA={sources['erpnext']['sha']}")
pins = []
for n in custom_lock:
    r = sources[n]["ref"]
    pins.append(f"{n} {sources[n]['sha']} {kind_of(r)} {r}")
# BUST order is canonical: lock sources insertion order (frappe, erpnext,
# then customs as stored). Any reorder changes the value by design.
out.append("BUST=" + "".join(sources[n]["sha"][:8] for n in sources))
bi = lock.get("build", {}).get("base_images", {})
for key, var in (("frappe_build", "FRAPPE_BUILD_IMAGE"), ("frappe_base", "FRAPPE_BASE_IMAGE")):
    ent = bi.get(key, {}) or {}
    ref = ent.get("ref", "")
    digest = ent.get("digest")
    if not (isinstance(ref, str) and ref.strip()):
        fail(f"build.base_images.{key}.ref missing")
    out.append(f"{var}={ref + '@' + digest if digest else ref}")
    if not digest:
        print(f"WARNING: base image {key} unpinned (digest null)", file=sys.stderr)
print("\n".join(out))
PYEOF
)"
eval "$RESOLVED"

# --- pre-flight guards (fail fast, before Docker) ---
[ -n "${FRAPPE_BUILD_IMAGE:-}" ] || { echo "missing FRAPPE_BUILD_IMAGE" >&2; exit 1; }
[ -n "${FRAPPE_BASE_IMAGE:-}" ] || { echo "missing FRAPPE_BASE_IMAGE" >&2; exit 1; }
[ -n "${FRAPPE_REF:-}" ] || { echo "missing FRAPPE_REF" >&2; exit 1; }
[ -n "${FRAPPE_SHA:-}" ] || { echo "missing FRAPPE_SHA" >&2; exit 1; }
[ -n "${ERPNEXT_REF:-}" ] || { echo "missing ERPNEXT_REF" >&2; exit 1; }
[ -n "${ERPNEXT_SHA:-}" ] || { echo "missing ERPNEXT_SHA" >&2; exit 1; }
[ -n "${BUST:-}" ] || { echo "missing BUST" >&2; exit 1; }

PINS_FILE="$(mktemp /tmp/pins.list.XXXXXX)"
trap 'rm -f -- "$PINS_FILE"' EXIT

# --- pins.list: all six sources, five fields, generated only ---
python3 - "$LOCK_FILE" "$PINS_FILE" <<'PYEOF'
import json, re, sys
lock_path, out_path = sys.argv[1], sys.argv[2]
lock = json.load(open(lock_path, encoding="utf-8"))
TAG_RE = re.compile(r"^v[0-9]+\.[0-9]+\.[0-9]+$")
NAME_RE = re.compile(r"^[A-Za-z0-9_.-]+$")
lines = []
for n, spec in lock["sources"].items():
    r = spec["ref"]
    kind = "tag" if TAG_RE.match(r) else "branch"
    if not NAME_RE.match(n):
        sys.exit(f"ERROR: bad app name: {n!r}")
    url = spec["repo"]
    if " " in url:
        sys.exit(f"ERROR: bad repo url for {n!r}")
    lines.append(f"{n} {url} {spec['sha']} {kind} {r}")
open(out_path, "w", encoding="utf-8").write("\n".join(lines) + "\n")
PYEOF

if [ "$DRY_RUN" = "1" ]; then
  echo "--- resolved build inputs (dry-run, nothing executed) ---"
  echo "FRAPPE_BUILD_IMAGE=$FRAPPE_BUILD_IMAGE"
  echo "FRAPPE_BASE_IMAGE=$FRAPPE_BASE_IMAGE"
  echo "FRAPPE_REF=$FRAPPE_REF"
  echo "FRAPPE_SHA=$FRAPPE_SHA"
  echo "ERPNEXT_REF=$ERPNEXT_REF"
  echo "ERPNEXT_SHA=$ERPNEXT_SHA"
  echo "BUST=$BUST (len ${#BUST})"
  echo "pins: generated $(wc -l < "$PINS_FILE") entries (sha256 $(sha256sum "$PINS_FILE" | cut -d' ' -f1))"
  exit 0
fi

# --- real mode only below this line ---
if [ "${DOCKER_BUILDKIT:-0}" != "1" ] && ! docker buildx version >/dev/null 2>&1; then
  echo "ERROR: BuildKit required (DOCKER_BUILDKIT=1 or buildx)" >&2
  exit 1
fi

docker build \
  --build-arg "FRAPPE_BUILD_IMAGE=$FRAPPE_BUILD_IMAGE" \
  --build-arg "FRAPPE_BASE_IMAGE=$FRAPPE_BASE_IMAGE" \
  --build-arg "FRAPPE_REF=$FRAPPE_REF" \
  --build-arg "FRAPPE_SHA=$FRAPPE_SHA" \
  --build-arg "ERPNEXT_REF=$ERPNEXT_REF" \
  --build-arg "ERPNEXT_SHA=$ERPNEXT_SHA" \
  --build-arg "CACHE_BUST=$BUST" \
  --secret "id=pins,src=$PINS_FILE" \
  --secret "id=apps_json,src=$APPS_JSON" \
  --tag "$IMAGE_TAG" \
  --file "$CONTAINERFILE" \
  "$REPO_ROOT"
