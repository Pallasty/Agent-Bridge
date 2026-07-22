#!/usr/bin/env bash
set -euo pipefail

CRG_VERSION="${CRG_VERSION:-2.3.7}"
CRG_PYTHON="${CRG_PYTHON:-3.13}"
REPO=""
BASE="HEAD~1"
OUT=""
KEEP_DATA=""

usage() {
  cat <<'EOF'
Usage: scripts/eval/code-review-graph-probe.sh [options]

Run a pinned, isolated code-review-graph evaluation without installing MCP
configuration or registering the repository globally.

Options:
  --repo PATH       Repository to inspect (default: current directory)
  --base REF        Git diff base for detect-changes (default: HEAD~1)
  --out DIR         Report directory (default: target/code-review-graph-eval/<UTC>)
  --keep-data DIR   Move the generated graph database to DIR after the run
  -h, --help        Show this help

Environment:
  CRG_VERSION       Pinned package version (default: 2.3.7)
  CRG_PYTHON        Isolated Python version selected by uv (default: 3.13)
  UV_CACHE_DIR      Optional shared uv download cache
EOF
}

while (($#)); do
  case "$1" in
    --repo)
      REPO="${2:?--repo requires a path}"
      shift 2
      ;;
    --base)
      BASE="${2:?--base requires a ref}"
      shift 2
      ;;
    --out)
      OUT="${2:?--out requires a directory}"
      shift 2
      ;;
    --keep-data)
      KEEP_DATA="${2:?--keep-data requires a directory}"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      printf 'unknown option: %s\n' "$1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

command -v git >/dev/null 2>&1 || {
  printf 'git is required\n' >&2
  exit 127
}
command -v uvx >/dev/null 2>&1 || {
  printf 'uvx is required; install uv before running this optional probe\n' >&2
  exit 127
}

REPO="${REPO:-$(pwd)}"
REPO="$(cd "$REPO" && pwd -P)"
git -C "$REPO" rev-parse --is-inside-work-tree >/dev/null
git -C "$REPO" rev-parse --verify "$BASE^{commit}" >/dev/null

STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
OUT="${OUT:-$REPO/target/code-review-graph-eval/$STAMP}"
mkdir -p "$OUT"
OUT="$(cd "$OUT" && pwd -P)"

RUN_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/ab-crg-probe.XXXXXX")"
ISOLATED_HOME="$RUN_ROOT/home"
DATA_DIR="$RUN_ROOT/data"
mkdir -p "$ISOLATED_HOME" "$DATA_DIR"

cleanup() {
  find "$RUN_ROOT" -depth -delete 2>/dev/null || true
}
trap cleanup EXIT INT TERM

UV_CACHE_DIR="${UV_CACHE_DIR:-${HOME}/.cache/uv}"
CRG=(uvx --python "$CRG_PYTHON" --from "code-review-graph==$CRG_VERSION" code-review-graph)

run_crg() {
  env \
    HOME="$ISOLATED_HOME" \
    CRG_DATA_DIR="$DATA_DIR" \
    UV_CACHE_DIR="$UV_CACHE_DIR" \
    "${CRG[@]}" "$@"
}

cat >"$OUT/manifest.txt" <<EOF
schema=agent_bridge.code_review_graph_probe.v0
package=code-review-graph
version=$CRG_VERSION
python=$CRG_PYTHON
repo=$REPO
base=$BASE
head=$(git -C "$REPO" rev-parse HEAD)
started_at=$STAMP
isolation=temporary_home_and_data_dir
mcp_config_modified=false
global_registry_modified=false
EOF

printf 'Building isolated graph for %s\n' "$REPO"
{
  time run_crg build --repo "$REPO"
} >"$OUT/build.log" 2>&1

run_crg status --repo "$REPO" --json >"$OUT/status.json"
run_crg detect-changes --repo "$REPO" --base "$BASE" --brief \
  >"$OUT/detect-brief.txt"
run_crg detect-changes --repo "$REPO" --base "$BASE" \
  >"$OUT/detect-full.json"
run_crg architecture --repo "$REPO" --detail-level minimal \
  >"$OUT/architecture.json"

if [[ -n "$KEEP_DATA" ]]; then
  mkdir -p "$(dirname "$KEEP_DATA")"
  if [[ -e "$KEEP_DATA" ]]; then
    printf 'refusing to overwrite --keep-data destination: %s\n' "$KEEP_DATA" >&2
    exit 3
  fi
  mv "$DATA_DIR" "$KEEP_DATA"
  printf 'graph_data=%s\n' "$KEEP_DATA" >>"$OUT/manifest.txt"
else
  printf 'graph_data=discarded\n' >>"$OUT/manifest.txt"
fi

printf 'Reports: %s\n' "$OUT"
cat "$OUT/detect-brief.txt"
