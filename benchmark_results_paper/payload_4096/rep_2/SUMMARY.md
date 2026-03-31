# CNS Benchmark Summary

## Q1. Latency overhead

| path | payload_size | messages | mean_us | median_us | p95_us | p99_us |
| --- | --- | --- | --- | --- | --- | --- |
| local_only | 4096 | 3000 | 26.89626133333333 | 23.9635 | 41.209499999999935 | 69.25784999999983 |
| distributed_only | 4096 | 3000 | 1334.8411680000002 | 1267.048 | 1689.9926999999993 | 3065.9650999999935 |
| hybrid_bridge | 4096 | 3000 | 1934.554686 | 1659.1785 | 5092.319699999995 | 6058.990749999995 |

## Q2. Throughput

| path | payload_size | messages | elapsed_s | throughput_msgs_per_s |
| --- | --- | --- | --- | --- |
| local_only | 4096 | 50000 | 1.313063112 | 38078.900810671774 |
| distributed_only | 4096 | 50000 | 10.57048006 | 4730.154138335322 |
| hybrid_bridge | 4096 | 50000 | 40.609671011 | 1231.2338109426305 |

## Q3. Validation and serialization

| case | payload_size | messages | latency_mean_us | latency_p95_us | throughput_msgs_per_s |
| --- | --- | --- | --- | --- | --- |
| pickle_with_validation | 4096 | 3000 | 1246.7453189999999 | 1587.4735499999997 | 5164.069440401743 |
| pickle_without_validation | 4096 | 3000 | 1242.5575606666666 | 1489.0602999999999 | 5065.394487663131 |
| json_with_validation | 4096 | 3000 | 1371.3566166666667 | 1707.05945 | 4091.7848946880476 |

## Q4. Graceful stop

| path | payload_size | attempted_messages | sent_before_stop | received_before_join | lost_estimate | completion_rate |
| --- | --- | --- | --- | --- | --- | --- |
| hybrid_bridge | 4096 | 100000 | 100000 | 1166 | 98834 | 0.01166 |
