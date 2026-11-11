#!/usr/bin/env bash
# Attack Ladder model executor
# Usage: run_model.sh <input_network_json> <scenario_id> <output_dir> <sampler_path> <n_samples>

set -euo pipefail

INPUT_JSON="$1"
SCENARIO_ID="$2"
OUTPUT_DIR="$3"
SAMPLER_PATH="$4"
N_SAMPLES="${5:-1000}"

mkdir -p "$OUTPUT_DIR"

SAMPLES_OUT="$OUTPUT_DIR/samples_${SCENARIO_ID}.json"
SUMMARY_OUT="$OUTPUT_DIR/summary_${SCENARIO_ID}.json"

node "$SAMPLER_PATH" \
    "$INPUT_JSON" \
    "$N_SAMPLES" \
    "NA" \
    "$SAMPLES_OUT" \
    "$SUMMARY_OUT"
