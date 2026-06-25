#!/usr/bin/env bash
set -euo pipefail

# Fetch the local ONNX asset bundle used by AGENT_BRIDGE_ONNX_MODEL=gte.
#
# This script writes only model files under the local ONNX cache directory. It
# does not touch state.db, reindex embeddings, deploy binaries, or change any
# running agent-bridge process environment.

model_name="${AGENT_BRIDGE_GTE_MODEL_NAME:-gte-multilingual-base}"
model_base="${AGENT_BRIDGE_ONNX_MODEL_DIR:-$HOME/.cache/agent-bridge/onnx-models}"
repo="${GTE_HF_REPO:-onnx-community/gte-multilingual-base}"
revision="${GTE_HF_REVISION:-2edbf5e672aab465f9ed4c154a8b61791c082c69}"
variant="full"
force=false
dry_run=false

usage() {
    cat <<'USAGE'
usage: scripts/fetch-gte-768-model-assets.sh [flags]

Flags:
  --model-name NAME    Local backend/cache label. Default: gte-multilingual-base
  --model-dir PATH     Base dir containing <model-name>/. Default:
                       $AGENT_BRIDGE_ONNX_MODEL_DIR or ~/.cache/agent-bridge/onnx-models
  --repo REPO          Hugging Face repo. Default: onnx-community/gte-multilingual-base
  --revision SHA       Exact model revision to fetch. Defaults to the verified
                       2024-10-08 onnx-community commit.
  --variant NAME       ONNX variant: full, fp16, int8, quantized. Default: full.
                       The chosen variant is stored locally as model.onnx.
  --force              Re-download files even when local targets already exist.
  --dry-run            Print the planned downloads without writing files.
  -h, --help           Show this help.

Read-only runtime contract:
  - no live DB writes;
  - no reindex;
  - no binary deploy;
  - no environment changes;
  - no memory/forum writes.
USAGE
}

while [ "$#" -gt 0 ]; do
    case "$1" in
        --model-name)
            model_name="${2:-}"
            shift 2
            ;;
        --model-dir)
            model_base="${2:-}"
            shift 2
            ;;
        --repo)
            repo="${2:-}"
            shift 2
            ;;
        --revision)
            revision="${2:-}"
            shift 2
            ;;
        --variant)
            variant="${2:-}"
            shift 2
            ;;
        --force)
            force=true
            shift
            ;;
        --dry-run)
            dry_run=true
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo "unknown flag: $1" >&2
            usage >&2
            exit 2
            ;;
    esac
done

case "$variant" in
    full) model_source="onnx/model.onnx" ;;
    fp16) model_source="onnx/model_fp16.onnx" ;;
    int8) model_source="onnx/model_int8.onnx" ;;
    quantized) model_source="onnx/model_quantized.onnx" ;;
    *)
        echo "unknown --variant: $variant" >&2
        usage >&2
        exit 2
        ;;
esac

command -v curl >/dev/null 2>&1 || { echo "curl is required" >&2; exit 2; }
command -v sha256sum >/dev/null 2>&1 || { echo "sha256sum is required" >&2; exit 2; }

target_dir="$model_base/$model_name"
base_url="https://huggingface.co/$repo/resolve/$revision"

declare -a sources=(
    "config.json:config.json"
    "special_tokens_map.json:special_tokens_map.json"
    "tokenizer.json:tokenizer.json"
    "tokenizer_config.json:tokenizer_config.json"
    "$model_source:model.onnx"
)

echo "# fetch GTE 768 model assets"
echo "repo:       $repo"
echo "revision:   $revision"
echo "variant:    $variant ($model_source -> model.onnx)"
echo "target_dir: $target_dir"

if [ "$dry_run" = true ]; then
    for pair in "${sources[@]}"; do
        source_path="${pair%%:*}"
        target_name="${pair##*:}"
        echo "DRY $base_url/$source_path -> $target_dir/$target_name"
    done
    exit 0
fi

mkdir -p "$target_dir"

download_one() {
    local source_path="$1"
    local target_name="$2"
    local target="$target_dir/$target_name"
    local part="$target.part"
    local url="$base_url/$source_path"

    if [ -s "$target" ] && [ "$force" = false ]; then
        echo "SKIP $target_name already exists ($(wc -c < "$target" | tr -d '[:space:]') bytes)"
        return
    fi

    echo "GET  $source_path -> $target_name"
    curl --fail --location --retry 5 --retry-delay 2 --continue-at - \
        --output "$part" "$url"
    mv "$part" "$target"
    echo "OK   $target_name ($(wc -c < "$target" | tr -d '[:space:]') bytes)"
}

for pair in "${sources[@]}"; do
    download_one "${pair%%:*}" "${pair##*:}"
done

manifest="$target_dir/asset-manifest.txt"
{
    echo "repo=$repo"
    echo "revision=$revision"
    echo "model_name=$model_name"
    echo "variant=$variant"
    echo "model_source=$model_source"
    echo "fetched_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    echo
    for pair in "${sources[@]}"; do
        target_name="${pair##*:}"
        printf '%s  %s\n' "$(sha256sum "$target_dir/$target_name" | awk '{print $1}')" "$target_name"
    done
} > "$manifest"

echo "manifest: $manifest"
echo "done"
