#!/usr/bin/env bash
set -euo pipefail

# Bigger experiment matrix for the CNS draft paper.
# Run from repository root.
# Requires:
#   - python environment with benchmarks/requirements.txt installed
#   - reachable NATS server at NATS_URL or default nats://127.0.0.1:4222

NATS_URL="${NATS_URL:-nats://127.0.0.1:4222}"
OUT_ROOT="${1:-paper_benchmark_results}"
REPEATS="${REPEATS:-5}"
PAYLOADS=(256 1024 4096)
LATENCY_MESSAGES="${LATENCY_MESSAGES:-5000}"
THROUGHPUT_MESSAGES="${THROUGHPUT_MESSAGES:-100000}"
STOP_MESSAGES="${STOP_MESSAGES:-200000}"
STOP_AFTER_S="${STOP_AFTER_S:-2.0}"
STOP_PRODUCER_SLEEP_S="${STOP_PRODUCER_SLEEP_S:-0.0}"

mkdir -p "$OUT_ROOT"

echo "Warm-up run..."
python benchmarks/run_benchmarks.py \
  --nats-url "$NATS_URL" \
  --payload-size 256 \
  --latency-messages 500 \
  --throughput-messages 5000 \
  --stop-messages 20000 \
  --stop-after-s 0.75 \
  --stop-producer-sleep-s 0.0 \
  --output-dir "$OUT_ROOT/warmup"

for payload in "${PAYLOADS[@]}"; do
  for rep in $(seq 1 "$REPEATS"); do
    out_dir="$OUT_ROOT/payload_${payload}/rep_${rep}"
    mkdir -p "$out_dir"
    echo "Running payload=${payload}, rep=${rep} -> ${out_dir}"
    python benchmarks/run_benchmarks.py \
      --nats-url "$NATS_URL" \
      --payload-size "$payload" \
      --latency-messages "$LATENCY_MESSAGES" \
      --throughput-messages "$THROUGHPUT_MESSAGES" \
      --stop-messages "$STOP_MESSAGES" \
      --stop-after-s "$STOP_AFTER_S" \
      --stop-producer-sleep-s "$STOP_PRODUCER_SLEEP_S" \
      --output-dir "$out_dir"
  done
done

echo "Completed. Results stored under: $OUT_ROOT"
