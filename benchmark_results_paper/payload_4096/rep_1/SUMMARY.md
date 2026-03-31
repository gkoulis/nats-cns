# CNS Benchmark Summary

## Q1. Latency overhead

| path | payload_size | messages | mean_us | median_us | p95_us | p99_us |
| --- | --- | --- | --- | --- | --- | --- |
| local_only | 4096 | 3000 | 27.89243833333333 | 24.1015 | 40.24599999999998 | 95.83937999999931 |
| distributed_only | 4096 | 3000 | 1361.2254206666667 | 1291.8375 | 1823.1086499999994 | 2483.006119999984 |
| hybrid_bridge | 4096 | 3000 | 1716.8407106666668 | 1596.515 | 2156.245249999998 | 4134.356699999983 |

## Q2. Throughput

| path | payload_size | messages | elapsed_s | throughput_msgs_per_s |
| --- | --- | --- | --- | --- |
| local_only | 4096 | 50000 | 1.243401727 | 40212.26520300627 |
| distributed_only | 4096 | 50000 | 10.895444963 | 4589.073706470524 |
| hybrid_bridge | 4096 | 50000 | 41.353514228 | 1209.087085666484 |

## Q3. Validation and serialization

| case | payload_size | messages | latency_mean_us | latency_p95_us | throughput_msgs_per_s |
| --- | --- | --- | --- | --- | --- |
| pickle_with_validation | 4096 | 3000 | 1232.37029 | 1552.4732999999997 | 5160.711834529757 |
| pickle_without_validation | 4096 | 3000 | 1207.1703666666667 | 1493.0510999999995 | 4839.289236942615 |
| json_with_validation | 4096 | 3000 | 1344.8098566666667 | 1735.4100999999996 | 4257.809272824508 |

## Q4. Graceful stop

| path | payload_size | attempted_messages | sent_before_stop | received_before_join | lost_estimate | completion_rate |
| --- | --- | --- | --- | --- | --- | --- |
| hybrid_bridge | 4096 | 100000 | 100000 | 1238 | 98762 | 0.01238 |
