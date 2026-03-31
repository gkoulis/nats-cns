# CNS Benchmark Summary

## Q1. Latency overhead

| path | payload_size | messages | mean_us | median_us | p95_us | p99_us |
| --- | --- | --- | --- | --- | --- | --- |
| local_only | 1024 | 3000 | 28.143465 | 27.5235 | 32.3413 | 44.33670999999991 |
| distributed_only | 1024 | 3000 | 1395.8662036666667 | 1367.098 | 1688.6804 | 1992.93824 |
| hybrid_bridge | 1024 | 3000 | 1866.0560976666666 | 1785.526 | 2301.2998999999995 | 4357.414139999985 |

## Q2. Throughput

| path | payload_size | messages | elapsed_s | throughput_msgs_per_s |
| --- | --- | --- | --- | --- |
| local_only | 1024 | 50000 | 1.190973936 | 41982.44687699026 |
| distributed_only | 1024 | 50000 | 8.851719184 | 5648.620224010035 |
| hybrid_bridge | 1024 | 50000 | 42.979413551 | 1163.347655748473 |

## Q3. Validation and serialization

| case | payload_size | messages | latency_mean_us | latency_p95_us | throughput_msgs_per_s |
| --- | --- | --- | --- | --- | --- |
| pickle_with_validation | 1024 | 3000 | 1326.0723030000001 | 1605.71025 | 5173.302548642331 |
| pickle_without_validation | 1024 | 3000 | 1331.6581446666667 | 1686.1500999999994 | 6147.692924845013 |
| json_with_validation | 1024 | 3000 | 1330.9811853333335 | 1636.2578499999997 | 5716.799821288264 |

## Q4. Graceful stop

| path | payload_size | attempted_messages | sent_before_stop | received_before_join | lost_estimate | completion_rate |
| --- | --- | --- | --- | --- | --- | --- |
| hybrid_bridge | 1024 | 100000 | 100000 | 1172 | 98828 | 0.01172 |
