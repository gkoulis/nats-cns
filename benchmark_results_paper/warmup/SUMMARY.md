# CNS Benchmark Summary

## Q1. Latency overhead

| path | payload_size | messages | mean_us | median_us | p95_us | p99_us |
| --- | --- | --- | --- | --- | --- | --- |
| local_only | 256 | 500 | 31.774262 | 26.016 | 54.67309999999999 | 99.24853999999989 |
| distributed_only | 256 | 500 | 1080.071118 | 1060.9075 | 1326.3616 | 1598.438359999999 |
| hybrid_bridge | 256 | 500 | 1603.4205160000001 | 1522.132 | 2304.583099999995 | 2842.79924 |

## Q2. Throughput

| path | payload_size | messages | elapsed_s | throughput_msgs_per_s |
| --- | --- | --- | --- | --- |
| local_only | 256 | 5000 | 0.163772941 | 30530.07395159375 |
| distributed_only | 256 | 5000 | 0.728845418 | 6860.165237397431 |
| hybrid_bridge | 256 | 5000 | 3.747189257 | 1334.3334582473158 |

## Q3. Validation and serialization

| case | payload_size | messages | latency_mean_us | latency_p95_us | throughput_msgs_per_s |
| --- | --- | --- | --- | --- | --- |
| pickle_with_validation | 256 | 500 | 2345.796644 | 3058.465999999999 | 6998.839130548772 |
| pickle_without_validation | 256 | 500 | 1082.4740800000002 | 1313.078099999999 | 6964.682554435506 |
| json_with_validation | 256 | 500 | 1175.313508 | 1610.9595999999997 | 5918.441298466722 |

## Q4. Graceful stop

| path | payload_size | attempted_messages | sent_before_stop | received_before_join | lost_estimate | completion_rate |
| --- | --- | --- | --- | --- | --- | --- |
| hybrid_bridge | 256 | 20000 | 20000 | 504 | 19496 | 0.0252 |
