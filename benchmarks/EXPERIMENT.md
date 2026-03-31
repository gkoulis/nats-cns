# Bigger experiment plan for the draft paper

This plan upgrades the single-run benchmark into a small experimental matrix.

## Why this is better than one huge run

A paper usually needs:
- multiple payload sizes
- repeated runs to smooth variance
- a warm-up pass
- one consistent parameter set across runs

## Recommended matrix

- Payload sizes: 256 B, 1 KiB, 4 KiB
- Repetitions per payload: 5
- Latency messages per run: 5,000
- Throughput messages per run: 100,000
- Graceful-stop messages per run: 200,000
- Stop trigger: 2.0 s

This yields 15 measured runs plus 1 warm-up run.

## One-off bigger command

If you only want a single bigger run:

```bash
python benchmarks/run_benchmarks.py \
  --nats-url nats://127.0.0.1:4222 \
  --payload-size 1024 \
  --latency-messages 5000 \
  --throughput-messages 100000 \
  --stop-messages 200000 \
  --stop-after-s 2.0 \
  --stop-producer-sleep-s 0.0 \
  --output-dir benchmark_results_paper_single
```

## Full paper-oriented run

```bash
bash benchmarks/run_paper_experiments.sh benchmark_results_paper_experiment
```

## Lighter laptop preset

If your PC is modest, set:

```bash
REPEATS=3 LATENCY_MESSAGES=3000 THROUGHPUT_MESSAGES=50000 STOP_MESSAGES=100000 \
  bash benchmarks/run_paper_experiments.sh paper_benchmark_results_light
```

## What to report in the paper

- For Q1/Q3: mean, median, p95, p99 across repetitions
- For Q2: throughput distribution across repetitions
- For Q4: completion rate and estimated loss across repetitions
- For Q5: one separate code-change experiment using `taxonomy_diff.py`
