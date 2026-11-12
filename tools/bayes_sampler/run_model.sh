#!/usr/bin/env bash
# Bayesian attack network model executor
# Usage: run_model.sh <input_network_json> <scenario_id> <output_dir> [sampler_path] [n_samples]
# An empty sampler_path uses the bundled sampler/headless_sampler.js

set -euo pipefail

INPUT_JSON="$1"
SCENARIO_ID="$2"
OUTPUT_DIR="$3"
SAMPLER_PATH="${4:-}"
N_SAMPLES="${5:-1000}"

# Default to the sampler bundled with this adapter
if [ -z "$SAMPLER_PATH" ]; then
    SAMPLER_PATH="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/sampler/headless_sampler.js"
fi

mkdir -p "$OUTPUT_DIR"

SAMPLES_OUT="$OUTPUT_DIR/samples_${SCENARIO_ID}.json"
SUMMARY_OUT="$OUTPUT_DIR/summary_${SCENARIO_ID}.json"

# Newer headless_sampler.js versions take an extra MITRE attack-group argument:
#   <net> <n> <fixedNodes> <mitreGroup> <samplesOut> <summaryOut>
# Older versions omit it. Detect which one we're calling.
OPTIONAL_ARGS=("NA")
if grep -q "mitreAttackGroupFilePath" "$SAMPLER_PATH"; then
    OPTIONAL_ARGS=("NA" "NA")
fi

node "$SAMPLER_PATH" \
    "$INPUT_JSON" \
    "$N_SAMPLES" \
    "${OPTIONAL_ARGS[@]}" \
    "$SAMPLES_OUT" \
    "$SUMMARY_OUT"
