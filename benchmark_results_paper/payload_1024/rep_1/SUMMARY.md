# CNS Benchmark Summary

## Q1. Latency overhead

| path | payload_size | messages | mean_us | median_us | p95_us | p99_us |
| --- | --- | --- | --- | --- | --- | --- |
| local_only | 1024 | 3000 | 27.541378 | 23.8365 | 44.64789999999998 | 93.29266999999979 |
| distributed_only | 1024 | 3000 | 1281.3113663333334 | 1195.6275 | 1754.9540499999996 | 2318.7096899999656 |
| hybrid_bridge | 1024 | 3000 | 1653.5879436666667 | 1571.363 | 2221.4835999999996 | 2642.567359999998 |

## Q2. Throughput

| path | payload_size | messages | elapsed_s | throughput_msgs_per_s |
| --- | --- | --- | --- | --- |
| local_only | 1024 | 50000 | 1.606491573 | 31123.723796838116 |
| distributed_only | 1024 | 50000 | 8.324616337 | 6006.282809427209 |
| hybrid_bridge | 1024 | 50000 | 43.103018659 | 1160.0115619642313 |

## Q3. Validation and serialization

| case | payload_size | messages | latency_mean_us | latency_p95_us | throughput_msgs_per_s |
| --- | --- | --- | --- | --- | --- |
| pickle_with_validation | 1024 | 3000 | 1354.489061 | 1625.1697499999998 | 5830.030316701783 |
| pickle_without_validation | 1024 | 3000 | 1362.6125226666666 | 1702.2728499999998 | 6493.508587733289 |
| json_with_validation | 1024 | 3000 | 1374.2619476666666 | 1673.92095 | 5857.901222987819 |

## Q4. Graceful stop

| path | payload_size | attempted_messages | sent_before_stop | received_before_join | lost_estimate | completion_rate |
| --- | --- | --- | --- | --- | --- | --- |
| hybrid_bridge | 1024 | 100000 | 100000 | 1185 | 98815 | 0.01185 |
