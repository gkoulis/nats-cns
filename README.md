# A Lightweight Hybrid Publish/Subscribe Event Fabric for IPC and Modular Distributed Systems

`nats-cns` is a lightweight Python prototype for building **local-first event-driven systems** that need both:

- **fast in-process coordination** inside a node or service, and
- **selective cross-node distribution** through **NATS**.

The project implements the CNS artifact described in the preprint **“A Lightweight Hybrid Publish/Subscribe Event Fabric for IPC and Modular Distributed Systems”** and provides a practical codebase for experimentation, benchmarking, and reuse.

At its core, CNS combines:

- a **typed event routing model**,
- a **local publish/subscribe context** for structured IPC,
- a **NATS-backed asynchronous context** for distributed messaging, and
- an explicit **bridge runtime** that moves events between the local and distributed paths.

The design target is not a general-purpose service mesh. It is a **bounded, inspectable, reusable event fabric** for modular systems developed within a single project boundary, where event families are controlled and fire-and-forget messaging is the dominant interaction pattern.

---

## Why this repository exists

In many modular systems, local coordination and distributed messaging grow as separate mechanisms. One part of the system talks through callbacks or queues, another talks through a broker, and eventually a layer of glue code grows like ivy over the walls.

CNS takes a different route.

It treats **local messaging as a first-class execution path**, not as a reduced version of remote messaging. The same routing vocabulary can be used:

- inside a process,
- across a node boundary,
- and through an explicit bridge between the two.

That keeps event identity, schema handling, and transport boundaries visible in the architecture instead of hiding them behind ad hoc adapters.

---

## What the prototype provides

### 1. Structured event keys

Events are identified by `EventTypeKey`, a typed routing key with the shape:

```text
space.super_family.family.name.qualifier1.qualifier2...
```

This structure gives one shared vocabulary for:

- event identity,
- routing subjects,
- wildcard subscription patterns,
- serializer/deserializer lookup,
- validation registration.

The implementation also exposes derived forms such as:

- `group_key`
- `base_key`
- `qualifiers_key`
- `full_key`

This alignment between routing and schema handling is one of the central ideas of the artifact.

### 2. Local publish/subscribe for IPC

`PubSubContext` is a lightweight in-process publish/subscribe mechanism built around queues and wildcard-aware pattern matching.

It supports two common local execution modes:

- **queued local delivery**, where events are polled from a subscription queue, and
- **handler-based local delivery**, where a matching callback is invoked directly.

This makes it useful for modular applications that want structured internal event movement without paying the cost of distributed transport for every interaction.

### 3. Distributed asynchronous messaging over NATS

`NATSAsyncContext` wraps a NATS client adapter and publishes/subscribes using the same structured subject vocabulary.

For each event family, CNS can register an `EventTypeSerDe` that bundles:

- serializer
- deserializer
- validator

If no custom serializer is registered, the current prototype falls back to Python serialization for convenience. Runtime metadata is propagated through NATS headers so that the receiving side can reconstruct the event and validate it against the declared family.

### 4. Explicit bridge runtime

`IPrivateSharedLocalContext` is the opinionated bridge abstraction used to connect the synchronous local context with the asynchronous distributed context.

The bridge is defined by two transfer loops:

- **local publish queue → distributed publish path**
- **distributed subscription queue → local subscription path**

This keeps message movement between the local and remote worlds explicit, inspectable, and measurable.

### 5. Reproducible benchmark harness

This repository also includes a runnable benchmark harness used to evaluate the prototype across the paper’s core questions:

1. latency across local-only, distributed-only, and hybrid paths,
2. throughput across the same paths,
3. validation and serialization overhead,
4. graceful-stop behavior under backlog,
5. a change-footprint proxy for event-taxonomy usability.

---

## Repository structure

```text
.
├── benchmark_results_paper/   # benchmark outputs used for the paper artifact
├── benchmarks/                # runnable benchmark harness and experiment scripts
├── src/
│   └── nats_cns/
│       ├── __init__.py
│       └── base.py            # core CNS implementation
├── docker-compose.yml         # local NATS server for development/reproduction
├── pyproject.toml             # package metadata
└── requirements.txt           # pinned dependencies
```

---

## Key implementation concepts

The current prototype revolves around a compact set of building blocks:

- `EventTypeKey` for structured event identity
- `Event` for payload + metadata packaging
- `EventTypeSerDe` for per-family serialization / deserialization / validation
- `PubSubContext` for local publish/subscribe
- `NATSAsyncContext` for distributed asynchronous messaging
- `IPrivateSharedLocalContext` for bridging local and distributed flows
- `LightweightEventDefinition` and `LightweightEventDefinitionsGroup` for defining reusable event families

If you want to specialize CNS for a project, the intended pattern is:

1. define your event families,
2. register their serializers / deserializers / validators,
3. instantiate full keys with runtime qualifiers,
4. choose whether each flow remains local, distributed, or bridged.

---

## Installation

### Requirements

- Python **3.10+**
- A reachable **NATS** server for distributed-path experiments

### Create an environment and install the package

```bash
python -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -e .
```

### Or install dependencies directly

```bash
pip install -r requirements.txt
```

Current packaged dependency:

- `nats-py==2.14.0`

---

## Running NATS locally

This repository includes a minimal Docker Compose file for a local NATS server.

```bash
docker compose up -d
```

The provided setup exposes:

- `4222` for the client endpoint
- `8222` for monitoring

You can also run NATS directly with Docker if you prefer:

```bash
docker run -p 4222:4222 -p 8222:8222 --name cns_nats nats:2.12.6
```

---

## Minimal local-only example

The smallest useful starting point is the local publish/subscribe context.

```python
from nats_cns.base import Event, EventTypeKey, PubSubContext

ctx = PubSubContext()

key = EventTypeKey(
    space="fabric",
    super_family="node",
    family="status",
    name="update",
    qualifiers=["node17", "10s"],
)

ctx.subscribe(key.full_key, handler=None)
ctx.publish(Event(key=key, data={"ok": True}))

event = ctx.subscribe_queue.get(timeout=1.0)
print(event.key.full_key)
print(event.data)
```

This exercises the local path only. For distributed delivery, use `NATSAsyncContext` and register the event family with an `EventTypeSerDe`.

---

## Benchmark harness

The `benchmarks/` directory contains a runnable harness for reproducing the paper-style evaluation.

### What it measures

- **Q1**: latency for `local_only`, `distributed_only`, and `hybrid_bridge`
- **Q2**: throughput across the same paths
- **Q3**: validation/serialization comparison
- **Q4**: graceful-stop behavior under controlled shutdown
- **Q5**: event-taxonomy usability proxy through git-diff change footprint

### Quick start

Start a local NATS server first, then run:

```bash
python benchmarks/run_benchmarks.py \
  --nats-url nats://127.0.0.1:4222 \
  --payload-size 256 \
  --latency-messages 500 \
  --throughput-messages 5000 \
  --stop-messages 20000 \
  --output-dir benchmark_results
```

The script writes outputs such as:

- `results.json`
- `SUMMARY.md`
- `q1_latency.csv`
- `q2_throughput.csv`
- `q3_validation_serialization.csv`
- `q4_graceful_stop.csv`
- optionally `q5_taxonomy_usability.csv`

### Smoke-test run

```bash
python benchmarks/run_benchmarks.py \
  --payload-size 256 \
  --latency-messages 200 \
  --throughput-messages 2000 \
  --stop-messages 10000 \
  --output-dir benchmark_results_smoke
```

### Larger paper-style runs

The repository also includes:

- `benchmarks/EXPERIMENT.md`
- `benchmarks/run_paper_experiments.sh`

for running broader experiment matrices with multiple payload sizes and repetitions.

---

## Summary of reported behavior

The preprint positions CNS as a **bounded, operationally legible architecture** rather than a finished high-throughput middleware stack.

In the reported single-machine measurements:

- **local-only delivery** is by far the fastest path,
- **distributed-only delivery** over NATS is slower but still practical,
- the **hybrid bridge** adds measurable overhead on top of the distributed path,
- **validation overhead** is relatively modest compared with transport and serialization costs,
- **graceful-stop under backlog** is currently the weakest part of the prototype.

That is an important design reading of the project: CNS already demonstrates the architectural value of a common routing vocabulary across local and distributed contexts, but the bridge path still needs hardening and optimization.

---

## Intended applicability

CNS is a good fit for systems that are:

- modular,
- event-driven,
- developed under a single project boundary,
- deployed on known or controlled nodes,
- centered on **structured fire-and-forget** communication.

Examples include:

- instrumentation software
- lab or validation rigs
- industrial controller stacks
- bounded edge or mini-node deployments
- modular services that need internal IPC plus selective remote export

It is **less suitable** as-is for:

- open-ended internet-scale middleware,
- systems that require strong durability guarantees,
- high-assurance ordering semantics,
- mature request/reply ergonomics,
- production-grade draining and shutdown under heavy backlog.

---

## Current limitations

The paper and code make the present boundaries fairly clear.

Notable limitations include:

- bridge throughput and tail-latency sensitivity,
- shutdown behavior under backlog,
- limited hardening around queue discipline and backpressure,
- default Python serialization as a convenience path rather than an interoperability-first default,
- request/reply support that exists conceptually but is secondary to the publish/subscribe core.

So this repository is best read as a **research prototype with runnable code**, not as a drop-in replacement for a production messaging platform.

---

## Development notes

The package is configured through `pyproject.toml` and uses a `src/` layout.

Editable install:

```bash
pip install -e .
```

Formatting dependency is listed in `requirements.txt`, and optional development dependencies are declared in `pyproject.toml`.

---

## Citing the work

If you use this repository in academic work, please cite the associated preprint:

```bibtex
@misc{gkoulis2026natscns,
      title={A Lightweight Hybrid Publish/Subscribe Event Fabric for IPC and Modular Distributed Systems}, 
      author={Dimitris Gkoulis},
      year={2026},
      eprint={2603.30030},
      archivePrefix={arXiv},
      primaryClass={cs.DC},
      url={https://arxiv.org/abs/2603.30030}, 
}
```

Preprint:

- arXiv: `2603.30030`

---

## Acknowledgment

This repository contains the prototype implementation, benchmark harness, and benchmark result artifacts associated with the CNS preprint. The code is intended to support inspection, experimentation, reproduction, and further specialization of the design.
