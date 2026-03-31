# CNS Artifact Benchmark Harness

This directory contains a runnable benchmark harness for the CNS prototype.
It is designed to answer the five evaluation questions from the paper draft:

1. Latency overhead of local vs distributed vs hybrid bridge paths.
2. Throughput under the same paths.
3. Cost of validation and serialization.
4. Graceful-stop behavior for the hybrid bridge.
5. Event taxonomy usability via a git-diff based change-footprint proxy.

## What this harness assumes

- Your CNS code is importable as `nats_cns.base`.
- You run the script from your repository root, or you set `PYTHONPATH` so that import works.
- You have a reachable NATS server.
- Python 3.10+ is recommended.

## Quick start

### 1. Create a virtual environment

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Start NATS locally

With Docker:

```bash
docker run -p 4222:4222 -ti nats:latest
```

### 3. Run the benchmark suite

From the repository root:

```bash
python benchmarks/run_benchmarks.py \
  --nats-url nats://127.0.0.1:4222 \
  --payload-size 256 \
  --latency-messages 500 \
  --throughput-messages 5000 \
  --stop-messages 20000 \
  --output-dir benchmark_results
```

The script writes:

- `benchmark_results/results.json`
- `benchmark_results/SUMMARY.md`
- `benchmark_results/q1_latency.csv`
- `benchmark_results/q2_throughput.csv`
- `benchmark_results/q3_validation_serialization.csv`
- `benchmark_results/q4_graceful_stop.csv`
- optionally `benchmark_results/q5_taxonomy_usability.csv`

## Running each question separately

### Q1 and Q2 and Q3 and Q4 together

The main runner executes all four runtime questions in a single pass:

```bash
python benchmarks/run_benchmarks.py --output-dir benchmark_results
```

Tune intensity with:

- `--payload-size`
- `--latency-messages`
- `--throughput-messages`
- `--stop-messages`
- `--stop-after-s`
- `--stop-producer-sleep-s`

## Q5: event taxonomy usability proxy

The runtime cannot directly measure "usability" as a human factor, so this harness uses a code-change footprint proxy.

Recommended workflow:

1. Create a branch that adds one new event family to the CNS registry.
2. Commit it.
3. Compare that branch against `main`.

Example:

```bash
python benchmarks/taxonomy_diff.py \
  --base-ref main \
  --target-ref feature/add-new-event \
  --paths path1 path2
```

This reports:

- files changed
- added and deleted LOC
- registry entries added
- event dataclasses added
- CNS-related files touched
- a simple touchpoint score

## Notes on interpretation

### Q1. Latency overhead

- `local_only` is an in-process queue loopback baseline.
- `distributed_only` uses NATS directly through `NATSAsyncContext`.
- `hybrid_bridge` uses your `IPrivateSharedLocalContext` bridge path.

### Q2. Throughput

This is measured as total messages divided by wall-clock time for each path.

### Q3. Validation and serialization

The harness compares:

- default serializer path with validation
- default serializer path without validation
- JSON serializer path with validation

You can add more cases by editing the `cases` list in `run_benchmarks.py`.

### Q4. Graceful stop

The current result is a practical benchmark, not a formal proof. It estimates completion rate and message loss under a controlled stop.

### Q5. Usability proxy

This is best treated as a maintainability indicator, not a full human-subject usability study.

## Suggested first run

```bash
python benchmarks/run_benchmarks.py \
  --payload-size 256 \
  --latency-messages 200 \
  --throughput-messages 2000 \
  --stop-messages 10000 \
  --output-dir benchmark_results_smoke
```

Then scale up once the smoke test passes.
