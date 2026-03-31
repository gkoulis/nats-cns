# CNS Benchmark Summary

## Q1. Latency overhead

| path | payload_size | messages | mean_us | median_us | p95_us | p99_us |
| --- | --- | --- | --- | --- | --- | --- |
| local_only | 256 | 3000 | 27.691848666666665 | 24.195 | 46.58774999999992 | 93.7775799999995 |
| distributed_only | 256 | 3000 | 1107.557484 | 1065.5575 | 1445.7215999999996 | 1687.3308499999978 |
| hybrid_bridge | 256 | 3000 | 1547.101076 | 1465.8605 | 2088.7805999999996 | 2584.97153 |

## Q2. Throughput

| path | payload_size | messages | elapsed_s | throughput_msgs_per_s |
| --- | --- | --- | --- | --- |
| local_only | 256 | 50000 | 1.244447642 | 40178.46819143236 |
| distributed_only | 256 | 50000 | 7.221820546 | 6923.461983238263 |
| hybrid_bridge | 256 | 50000 | 42.223870379 | 1184.1643021163559 |

## Q3. Validation and serialization

| case | payload_size | messages | latency_mean_us | latency_p95_us | throughput_msgs_per_s |
| --- | --- | --- | --- | --- | --- |
| pickle_with_validation | 256 | 3000 | 1242.7957866666666 | 1749.2712999999997 | 6737.327654302113 |
| pickle_without_validation | 256 | 3000 | 1242.364994 | 1734.30275 | 6935.927655111775 |
| json_with_validation | 256 | 3000 | 1336.7396669999998 | 1898.9435499999997 | 5844.200328387175 |

## Q4. Graceful stop

| path | payload_size | attempted_messages | sent_before_stop | received_before_join | lost_estimate | completion_rate |
| --- | --- | --- | --- | --- | --- | --- |
| hybrid_bridge | 256 | 100000 | 100000 | 1220 | 98780 | 0.0122 |
