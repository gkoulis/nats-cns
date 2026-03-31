#!/usr/bin/env python3

"""
Benchmark harness for the CNS prototype.

This script measures the five evaluation questions from the draft paper:
Q1. Latency overhead of local vs distributed vs hybrid bridge paths.
Q2. Throughput under different paths and payload sizes.
Q3. Cost of validation and serialization.
Q4. Graceful-stop behavior for the hybrid bridge.
Q5. Usability proxy for the event taxonomy, via a git-diff based change-footprint analysis.

Assumptions:
- The user's CNS code is importable from the current repository or PYTHONPATH.
- A NATS server is reachable at the given URL.

Author: Dimitris Gkoulis
Created on: Tuesday 31 March 2026
"""

import argparse
import asyncio
import csv
import json
import os
import queue
import signal
import statistics
import subprocess
import sys
import threading
import time
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional

# ####################################################################################################
# Import CNS implementation
# ####################################################################################################


ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from nats_cns.base import (
        Event,
        EventTypeKey,
        EventTypeSerDe,
        IPrivateSharedLocalContext,
        NATSAsyncContext,
        PubSubContext,
        simple_type_validator_factory,
    )
except Exception as ex:  # pragma: no cover - this is the user-facing import check.
    raise SystemExit(
        "Could not import your CNS package. Run this script from your repository root or set PYTHONPATH so that "
        "'nats_cns.base' is importable. Original import error:\n"
        f"{type(ex).__name__}: {ex}"
    )


# ####################################################################################################
# Benchmark event definitions.
# ####################################################################################################


@dataclass
class BenchmarkEvent:
    seq: int
    sent_ns: int
    body: str


@dataclass
class JsonBenchmarkEvent:
    seq: int
    sent_ns: int
    body: str


BENCH_GROUP = EventTypeKey(
    space="bench",
    super_family="artifact",
    family="runtime",
    name="root",
    qualifiers=["root"],
)

DEFAULT_BASE = EventTypeKey(
    space="bench",
    super_family="artifact",
    family="runtime",
    name="ping",
    qualifiers=["root"],
)

JSON_BASE = EventTypeKey(
    space="bench",
    super_family="artifact",
    family="runtime",
    name="jsonping",
    qualifiers=["root"],
)

NO_VALIDATE_BASE = EventTypeKey(
    space="bench",
    super_family="artifact",
    family="runtime",
    name="novalidate",
    qualifiers=["root"],
)


def make_full_key(base: EventTypeKey, qualifier: str) -> EventTypeKey:
    return EventTypeKey(
        space=base.space,
        super_family=base.super_family,
        family=base.family,
        name=base.name,
        qualifiers=[qualifier],
    )


# ####################################################################################################
# Serializers / deserializers.
# ####################################################################################################


def json_serializer(obj: JsonBenchmarkEvent) -> bytes:
    return json.dumps(asdict(obj), separators=(",", ":")).encode("utf-8")


def json_deserializer(data: bytes) -> JsonBenchmarkEvent:
    payload = json.loads(data.decode("utf-8"))
    return JsonBenchmarkEvent(**payload)


DEFAULT_SERDE = EventTypeSerDe(
    etk=DEFAULT_BASE,
    serializer=None,
    deserializer=None,
    validator=simple_type_validator_factory(BenchmarkEvent),
)

JSON_SERDE = EventTypeSerDe(
    etk=JSON_BASE,
    serializer=json_serializer,
    deserializer=json_deserializer,
    validator=simple_type_validator_factory(JsonBenchmarkEvent),
)

NO_VALIDATE_SERDE = EventTypeSerDe(
    etk=NO_VALIDATE_BASE,
    serializer=None,
    deserializer=None,
    validator=None,
)


# ####################################################################################################
# Utility helpers.
# ####################################################################################################


def now_ns() -> int:
    return time.perf_counter_ns()


def percentile(values: List[int], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return float(ordered[0])
    rank = (len(ordered) - 1) * pct
    low = int(rank)
    high = min(low + 1, len(ordered) - 1)
    weight = rank - low
    return ordered[low] * (1.0 - weight) + ordered[high] * weight


def summarize_latencies_ns(samples: List[int]) -> Dict[str, float]:
    if not samples:
        return {
            "count": 0,
            "min_us": 0.0,
            "mean_us": 0.0,
            "median_us": 0.0,
            "p95_us": 0.0,
            "p99_us": 0.0,
            "max_us": 0.0,
        }
    return {
        "count": len(samples),
        "min_us": min(samples) / 1_000.0,
        "mean_us": statistics.fmean(samples) / 1_000.0,
        "median_us": statistics.median(samples) / 1_000.0,
        "p95_us": percentile(samples, 0.95) / 1_000.0,
        "p99_us": percentile(samples, 0.99) / 1_000.0,
        "max_us": max(samples) / 1_000.0,
    }


def random_body(size_bytes: int) -> str:
    if size_bytes <= 0:
        return ""
    chunk = "x" * min(size_bytes, 1024)
    repeats = (size_bytes + len(chunk) - 1) // len(chunk)
    return (chunk * repeats)[:size_bytes]


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def append_csv(path: Path, row: Dict[str, Any], header: Optional[List[str]] = None) -> None:
    exists = path.exists()
    with path.open("a", newline="", encoding="utf-8") as f:
        if header is None:
            header = list(row.keys())
        writer = csv.DictWriter(f, fieldnames=header)
        if not exists:
            writer.writeheader()
        writer.writerow(row)


# ####################################################################################################
# Local-only benchmark.
# ####################################################################################################


class LocalLoopbackWorker:
    def __init__(self, ctx: PubSubContext):
        self.ctx = ctx
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, name="LocalLoopbackWorker", daemon=True)

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._thread.join(timeout=5.0)

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                event = self.ctx.publish_queue.get(timeout=0.05)
            except queue.Empty:
                continue
            self.ctx.on_new_event(event)
            self.ctx.publish_queue.task_done()


def setup_local_context(full_key: str) -> tuple[PubSubContext, LocalLoopbackWorker]:
    ctx = PubSubContext()
    ctx.subscribe(full_key, handler=None)
    worker = LocalLoopbackWorker(ctx)
    worker.start()
    return ctx, worker


def benchmark_local_latency(num_messages: int, payload_size: int) -> Dict[str, Any]:
    key = make_full_key(DEFAULT_BASE, "local")
    ctx, worker = setup_local_context(key.full_key)
    latencies: List[int] = []
    try:
        body = random_body(payload_size)
        for i in range(num_messages):
            sent = now_ns()
            event = Event(key=key, data=BenchmarkEvent(seq=i, sent_ns=sent, body=body))
            ctx.publish(event)
            received = ctx.subscribe_queue.get(timeout=5.0)
            latency = now_ns() - received.data.sent_ns
            latencies.append(latency)
    finally:
        worker.stop()

    return {
        "path": "local_only",
        "payload_size": payload_size,
        "messages": num_messages,
        **summarize_latencies_ns(latencies),
    }


def benchmark_local_throughput(num_messages: int, payload_size: int) -> Dict[str, Any]:
    key = make_full_key(DEFAULT_BASE, "local")
    ctx, worker = setup_local_context(key.full_key)
    body = random_body(payload_size)
    start = now_ns()
    try:
        for i in range(num_messages):
            sent = now_ns()
            ctx.publish(Event(key=key, data=BenchmarkEvent(seq=i, sent_ns=sent, body=body)))
        for _ in range(num_messages):
            _ = ctx.subscribe_queue.get(timeout=10.0)
    finally:
        worker.stop()
    elapsed_s = (now_ns() - start) / 1_000_000_000.0
    return {
        "path": "local_only",
        "payload_size": payload_size,
        "messages": num_messages,
        "elapsed_s": elapsed_s,
        "throughput_msgs_per_s": num_messages / elapsed_s if elapsed_s > 0 else 0.0,
    }


# ####################################################################################################
# Distributed-only benchmark.
# ####################################################################################################


async def setup_nats_context(servers: List[str], serde: EventTypeSerDe, full_key: str, name: str) -> NATSAsyncContext:
    ctx = NATSAsyncContext(servers=servers, name=name, default_timeout=2.0)
    await ctx.start()
    await ctx.register_event_type(serde)
    await ctx.subscribe(full_key)
    return ctx


async def benchmark_distributed_latency(
    servers: List[str],
    serde: EventTypeSerDe,
    base: EventTypeKey,
    num_messages: int,
    payload_size: int,
) -> Dict[str, Any]:
    key = make_full_key(base, "distributed")
    ctx = await setup_nats_context(servers, serde, key.full_key, name=f"dist-lat-{uuid.uuid4()}")
    latencies: List[int] = []
    try:
        body = random_body(payload_size)
        for i in range(num_messages):
            sent = now_ns()
            if serde.etk.base_key == JSON_BASE.base_key:
                data = JsonBenchmarkEvent(seq=i, sent_ns=sent, body=body)
            elif serde.etk.base_key == NO_VALIDATE_BASE.base_key:
                data = BenchmarkEvent(seq=i, sent_ns=sent, body=body)
            else:
                data = BenchmarkEvent(seq=i, sent_ns=sent, body=body)
            await ctx.publish(Event(key=key, data=data))
            received = await asyncio.wait_for(ctx.queue.get(), timeout=5.0)
            ctx.queue.task_done()
            latencies.append(now_ns() - received.data.sent_ns)
    finally:
        await ctx.graceful_stop()

    return {
        "path": "distributed_only",
        "serializer": serde.etk.name,
        "payload_size": payload_size,
        "messages": num_messages,
        **summarize_latencies_ns(latencies),
    }


async def benchmark_distributed_throughput(
    servers: List[str],
    serde: EventTypeSerDe,
    base: EventTypeKey,
    num_messages: int,
    payload_size: int,
) -> Dict[str, Any]:
    key = make_full_key(base, "distributed")
    ctx = await setup_nats_context(servers, serde, key.full_key, name=f"dist-tp-{uuid.uuid4()}")
    body = random_body(payload_size)
    start = now_ns()
    try:
        for i in range(num_messages):
            sent = now_ns()
            if serde.etk.base_key == JSON_BASE.base_key:
                data = JsonBenchmarkEvent(seq=i, sent_ns=sent, body=body)
            else:
                data = BenchmarkEvent(seq=i, sent_ns=sent, body=body)
            await ctx.publish(Event(key=key, data=data))
        for _ in range(num_messages):
            _ = await asyncio.wait_for(ctx.queue.get(), timeout=20.0)
            ctx.queue.task_done()
    finally:
        await ctx.graceful_stop()
    elapsed_s = (now_ns() - start) / 1_000_000_000.0
    return {
        "path": "distributed_only",
        "serializer": serde.etk.name,
        "payload_size": payload_size,
        "messages": num_messages,
        "elapsed_s": elapsed_s,
        "throughput_msgs_per_s": num_messages / elapsed_s if elapsed_s > 0 else 0.0,
    }


# ####################################################################################################
# Hybrid benchmark using the bridge.
# ####################################################################################################


class BenchmarkPSLC(IPrivateSharedLocalContext):
    def __init__(self, full_key: str, serde: EventTypeSerDe) -> None:
        super().__init__()
        self._full_key = full_key
        self._serde = serde

    async def _asynchronous_setup__post(self) -> None:
        await self.nc_a_ctx.register_event_type(self._serde)
        await self.nc_a_ctx.subscribe(self._full_key)

    def _synchronous_setup__post(self) -> None:
        self.ps_ctx.subscribe(self._full_key, handler=None)

    def stop_and_join(self, join_timeout: float = 10.0) -> None:
        self.active_state = False
        if self.thread1 is not None:
            self.thread1.join(timeout=join_timeout)
        if self.thread_pool_executor1 is not None:
            self.thread_pool_executor1.shutdown(wait=True, cancel_futures=False)


def setup_hybrid_context(servers: List[str], serde: EventTypeSerDe, base: EventTypeKey) -> tuple[BenchmarkPSLC, EventTypeKey]:
    key = make_full_key(base, "hybrid")
    pslc = BenchmarkPSLC(full_key=key.full_key, serde=serde)
    pslc.set_parameters(
        servers=servers,
        name=f"hybrid-{uuid.uuid4()}",
        default_timeout=2.0,
        queue_ops_timeout=0.05,
        enable_pub=True,
        enable_sub=True,
        max_workers=2,
    )
    pslc.synchronous_setup()
    pslc.invoke_asynchronous_context_runnable()
    # Give the async loop a brief moment to subscribe before the first publication.
    time.sleep(0.35)
    return pslc, key


def benchmark_hybrid_latency(servers: List[str], num_messages: int, payload_size: int) -> Dict[str, Any]:
    pslc, key = setup_hybrid_context(servers, DEFAULT_SERDE, DEFAULT_BASE)
    latencies: List[int] = []
    body = random_body(payload_size)
    try:
        for i in range(num_messages):
            sent = now_ns()
            pslc.ps_ctx.publish(Event(key=key, data=BenchmarkEvent(seq=i, sent_ns=sent, body=body)))
            received = pslc.get_all_until_now_or_block_with_timeout(max_size=1, timeout=5.0)
            if not received:
                raise TimeoutError("Timed out waiting for hybrid latency event")
            latencies.append(now_ns() - received[0].data.sent_ns)
    finally:
        pslc.stop_and_join()

    return {
        "path": "hybrid_bridge",
        "payload_size": payload_size,
        "messages": num_messages,
        **summarize_latencies_ns(latencies),
    }


def benchmark_hybrid_throughput(servers: List[str], num_messages: int, payload_size: int) -> Dict[str, Any]:
    pslc, key = setup_hybrid_context(servers, DEFAULT_SERDE, DEFAULT_BASE)
    body = random_body(payload_size)
    start = now_ns()
    try:
        for i in range(num_messages):
            sent = now_ns()
            pslc.ps_ctx.publish(Event(key=key, data=BenchmarkEvent(seq=i, sent_ns=sent, body=body)))
        received = 0
        while received < num_messages:
            batch = pslc.get_all_until_now_or_block_with_timeout(max_size=1000, timeout=5.0)
            received += len(batch)
    finally:
        pslc.stop_and_join()
    elapsed_s = (now_ns() - start) / 1_000_000_000.0
    return {
        "path": "hybrid_bridge",
        "payload_size": payload_size,
        "messages": num_messages,
        "elapsed_s": elapsed_s,
        "throughput_msgs_per_s": num_messages / elapsed_s if elapsed_s > 0 else 0.0,
    }


# ####################################################################################################
# Q3: validation and serialization cost.
# ####################################################################################################


async def benchmark_validation_and_serialization(
    servers: List[str],
    num_messages: int,
    payload_size: int,
) -> List[Dict[str, Any]]:
    cases = [
        ("pickle_with_validation", DEFAULT_SERDE, DEFAULT_BASE),
        ("pickle_without_validation", NO_VALIDATE_SERDE, NO_VALIDATE_BASE),
        ("json_with_validation", JSON_SERDE, JSON_BASE),
    ]
    results: List[Dict[str, Any]] = []
    for case_name, serde, base in cases:
        latency = await benchmark_distributed_latency(servers, serde, base, num_messages, payload_size)
        throughput = await benchmark_distributed_throughput(servers, serde, base, num_messages, payload_size)
        results.append(
            {
                "case": case_name,
                "payload_size": payload_size,
                "messages": num_messages,
                "latency_mean_us": latency["mean_us"],
                "latency_p95_us": latency["p95_us"],
                "throughput_msgs_per_s": throughput["throughput_msgs_per_s"],
            }
        )
    return results


# ####################################################################################################
# Q4: graceful stop.
# ####################################################################################################


class ProducerThread:
    def __init__(self, publish_fn: Callable[[int], None], total_messages: int, sleep_s: float = 0.0):
        self.publish_fn = publish_fn
        self.total_messages = total_messages
        self.sleep_s = sleep_s
        self.sent = 0
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, name="BenchmarkProducer", daemon=True)

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._thread.join(timeout=5.0)

    def _run(self) -> None:
        for i in range(self.total_messages):
            if self._stop.is_set():
                break
            self.publish_fn(i)
            self.sent += 1
            if self.sleep_s > 0:
                time.sleep(self.sleep_s)


def benchmark_graceful_stop(
    servers: List[str],
    total_messages: int,
    payload_size: int,
    run_before_stop_s: float,
    producer_sleep_s: float,
) -> Dict[str, Any]:
    pslc, key = setup_hybrid_context(servers, DEFAULT_SERDE, DEFAULT_BASE)
    body = random_body(payload_size)

    def publish_one(i: int) -> None:
        pslc.ps_ctx.publish(Event(key=key, data=BenchmarkEvent(seq=i, sent_ns=now_ns(), body=body)))

    producer = ProducerThread(publish_fn=publish_one, total_messages=total_messages, sleep_s=producer_sleep_s)
    producer.start()
    time.sleep(run_before_stop_s)
    pslc.active_state = False
    producer.stop()

    # Allow any final loop iteration to complete.
    time.sleep(max(0.2, pslc._queue_ops_timeout * 2))

    received_events = pslc.get_all_until_now(max_size=0)
    pslc.stop_and_join()
    received_count = len(received_events)
    sent_count = producer.sent
    lost = max(sent_count - received_count, 0)

    return {
        "path": "hybrid_bridge",
        "payload_size": payload_size,
        "attempted_messages": total_messages,
        "sent_before_stop": sent_count,
        "received_before_join": received_count,
        "lost_estimate": lost,
        "completion_rate": (received_count / sent_count) if sent_count > 0 else 0.0,
        "run_before_stop_s": run_before_stop_s,
        "producer_sleep_s": producer_sleep_s,
    }


# ####################################################################################################
# Q5: taxonomy usability proxy.
# ####################################################################################################


def run_git_diff(base_ref: str, target_ref: str, paths: Optional[List[str]]) -> str:
    cmd = ["git", "diff", "--unified=0", f"{base_ref}...{target_ref}"]
    if paths:
        cmd.extend(paths)
    proc = subprocess.run(cmd, check=True, capture_output=True, text=True)
    return proc.stdout


def analyze_taxonomy_diff(base_ref: str, target_ref: str, paths: Optional[List[str]]) -> Dict[str, Any]:
    diff = run_git_diff(base_ref, target_ref, paths)
    files_changed = 0
    added_loc = 0
    deleted_loc = 0
    registry_entries_added = 0
    event_dataclasses_added = 0
    context_touch_files: set[str] = set()
    current_file = ""

    for line in diff.splitlines():
        if line.startswith("diff --git "):
            files_changed += 1
        elif line.startswith("+++ b/"):
            current_file = line.removeprefix("+++ b/")
        elif line.startswith("+") and not line.startswith("+++"):
            added_loc += 1
            if "LightweightEventDefinition(" in line or "EventTypeSerDe(" in line:
                registry_entries_added += 1
            if line.strip().startswith("class ") and line.strip().endswith(":") and "CNSE" in line:
                event_dataclasses_added += 1
            if any(token in current_file for token in ["central_nervous_system", "constructs/cns", "_domain"]):
                context_touch_files.add(current_file)
        elif line.startswith("-") and not line.startswith("---"):
            deleted_loc += 1

    touchpoint_score = files_changed + len(context_touch_files) + registry_entries_added + event_dataclasses_added
    interpretation = (
        f"Changed {files_changed} files, added {added_loc} LOC, removed {deleted_loc} LOC, "
        f"added {registry_entries_added} registry entries, added {event_dataclasses_added} event dataclasses, "
        f"and touched {len(context_touch_files)} CNS-related files."
    )

    return {
        "question": "Q5_event_taxonomy_usability_proxy",
        "base_ref": base_ref,
        "target_ref": target_ref,
        "paths": paths or [],
        "files_changed": files_changed,
        "added_loc": added_loc,
        "deleted_loc": deleted_loc,
        "registry_entries_added": registry_entries_added,
        "event_dataclasses_added": event_dataclasses_added,
        "cns_related_files_touched": sorted(context_touch_files),
        "touchpoint_score": touchpoint_score,
        "interpretation": interpretation,
    }


# ####################################################################################################
# Markdown reporting.
# ####################################################################################################


def markdown_table(rows: Iterable[Dict[str, Any]], columns: List[str]) -> str:
    rows = list(rows)
    header = "| " + " | ".join(columns) + " |"
    sep = "| " + " | ".join(["---"] * len(columns)) + " |"
    body = ["| " + " | ".join(str(row.get(c, "")) for c in columns) + " |" for row in rows]
    return "\n".join([header, sep, *body])


def build_summary_markdown(results: Dict[str, Any]) -> str:
    lines: List[str] = []
    lines.append("# CNS Benchmark Summary")
    lines.append("")
    lines.append("## Q1. Latency overhead")
    lines.append("")
    lines.append(
        markdown_table(
            results["q1_latency"],
            ["path", "payload_size", "messages", "mean_us", "median_us", "p95_us", "p99_us"],
        )
    )
    lines.append("")
    lines.append("## Q2. Throughput")
    lines.append("")
    lines.append(
        markdown_table(
            results["q2_throughput"],
            ["path", "payload_size", "messages", "elapsed_s", "throughput_msgs_per_s"],
        )
    )
    lines.append("")
    lines.append("## Q3. Validation and serialization")
    lines.append("")
    lines.append(
        markdown_table(
            results["q3_validation_serialization"],
            ["case", "payload_size", "messages", "latency_mean_us", "latency_p95_us", "throughput_msgs_per_s"],
        )
    )
    lines.append("")
    lines.append("## Q4. Graceful stop")
    lines.append("")
    lines.append(
        markdown_table(
            [results["q4_graceful_stop"]],
            [
                "path",
                "payload_size",
                "attempted_messages",
                "sent_before_stop",
                "received_before_join",
                "lost_estimate",
                "completion_rate",
            ],
        )
    )
    if results.get("q5_taxonomy_usability"):
        lines.append("")
        lines.append("## Q5. Event taxonomy usability proxy")
        lines.append("")
        q5 = results["q5_taxonomy_usability"]
        lines.append(f"- Base ref: `{q5['base_ref']}`")
        lines.append(f"- Target ref: `{q5['target_ref']}`")
        lines.append(f"- Files changed: {q5['files_changed']}")
        lines.append(f"- Added LOC: {q5['added_loc']}")
        lines.append(f"- Deleted LOC: {q5['deleted_loc']}")
        lines.append(f"- Registry entries added: {q5['registry_entries_added']}")
        lines.append(f"- Event dataclasses added: {q5['event_dataclasses_added']}")
        lines.append(f"- Touchpoint score: {q5['touchpoint_score']}")
        lines.append(f"- Interpretation: {q5['interpretation']}")
    lines.append("")
    return "\n".join(lines)


# ####################################################################################################
# CLI.
# ####################################################################################################


async def run_runtime_questions(args: argparse.Namespace) -> Dict[str, Any]:
    servers = [args.nats_url]
    results: Dict[str, Any] = {}

    # Q1: Latency.
    q1 = [
        benchmark_local_latency(args.latency_messages, args.payload_size),
        await benchmark_distributed_latency(servers, DEFAULT_SERDE, DEFAULT_BASE, args.latency_messages, args.payload_size),
        benchmark_hybrid_latency(servers, args.latency_messages, args.payload_size),
    ]
    results["q1_latency"] = q1

    # Q2: Throughput.
    q2 = [
        benchmark_local_throughput(args.throughput_messages, args.payload_size),
        await benchmark_distributed_throughput(servers, DEFAULT_SERDE, DEFAULT_BASE, args.throughput_messages, args.payload_size),
        benchmark_hybrid_throughput(servers, args.throughput_messages, args.payload_size),
    ]
    results["q2_throughput"] = q2

    # Q3: Validation and serialization.
    q3 = await benchmark_validation_and_serialization(servers, args.latency_messages, args.payload_size)
    results["q3_validation_serialization"] = q3

    # Q4: Graceful stop.
    q4 = benchmark_graceful_stop(
        servers,
        total_messages=args.stop_messages,
        payload_size=args.payload_size,
        run_before_stop_s=args.stop_after_s,
        producer_sleep_s=args.stop_producer_sleep_s,
    )
    results["q4_graceful_stop"] = q4

    # Q5: Optional usability proxy.
    if args.base_ref and args.target_ref:
        results["q5_taxonomy_usability"] = analyze_taxonomy_diff(args.base_ref, args.target_ref, args.paths)

    return results


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run CNS artifact benchmarks.")
    parser.add_argument("--nats-url", default=os.getenv("NATS_URL", "nats://127.0.0.1:4222"))
    parser.add_argument("--payload-size", type=int, default=256)
    parser.add_argument("--latency-messages", type=int, default=500)
    parser.add_argument("--throughput-messages", type=int, default=5000)
    parser.add_argument("--stop-messages", type=int, default=20000)
    parser.add_argument("--stop-after-s", type=float, default=0.75)
    parser.add_argument("--stop-producer-sleep-s", type=float, default=0.0)
    parser.add_argument("--output-dir", default="benchmark_results")
    parser.add_argument("--base-ref", default=None, help="Git base ref for Q5, e.g. main")
    parser.add_argument("--target-ref", default=None, help="Git target ref for Q5, e.g. feature/add-new-event")
    parser.add_argument("--paths", nargs="*", default=None, help="Optional path filters for Q5 git diff")
    return parser.parse_args()


async def main_async() -> int:
    args = parse_args()
    outdir = Path(args.output_dir)
    ensure_dir(outdir)

    results = await run_runtime_questions(args)

    json_path = outdir / "results.json"
    md_path = outdir / "SUMMARY.md"
    write_json(json_path, results)
    md_path.write_text(build_summary_markdown(results), encoding="utf-8")

    for row in results["q1_latency"]:
        append_csv(outdir / "q1_latency.csv", row)
    for row in results["q2_throughput"]:
        append_csv(outdir / "q2_throughput.csv", row)
    for row in results["q3_validation_serialization"]:
        append_csv(outdir / "q3_validation_serialization.csv", row)
    append_csv(outdir / "q4_graceful_stop.csv", results["q4_graceful_stop"])
    if results.get("q5_taxonomy_usability"):
        append_csv(outdir / "q5_taxonomy_usability.csv", results["q5_taxonomy_usability"])

    print(f"Wrote results to: {outdir}")
    print(f"- {json_path}")
    print(f"- {md_path}")
    return 0


if __name__ == "__main__":
    # Keep Ctrl+C friendly during long runs.
    signal.signal(signal.SIGINT, signal.default_int_handler)
    raise SystemExit(asyncio.run(main_async()))
