# CNS Benchmark Summary

## Q1. Latency overhead

| path | payload_size | messages | mean_us | median_us | p95_us | p99_us |
| --- | --- | --- | --- | --- | --- | --- |
| local_only | 4096 | 3000 | 33.935330666666665 | 25.9545 | 66.29279999999996 | 121.0265399999994 |
| distributed_only | 4096 | 3000 | 1396.6802673333334 | 1324.377 | 1767.0771999999993 | 2260.945519999997 |
| hybrid_bridge | 4096 | 3000 | 2012.4948166666666 | 1925.908 | 2439.7865 | 4346.563179999987 |

## Q2. Throughput

| path | payload_size | messages | elapsed_s | throughput_msgs_per_s |
| --- | --- | --- | --- | --- |
| local_only | 4096 | 50000 | 1.227397421 | 40736.60180845369 |
| distributed_only | 4096 | 50000 | 11.436757968 | 4371.868333657124 |
| hybrid_bridge | 4096 | 50000 | 40.471338054 | 1235.4422266268073 |

## Q3. Validation and serialization

| case | payload_size | messages | latency_mean_us | latency_p95_us | throughput_msgs_per_s |
| --- | --- | --- | --- | --- | --- |
| pickle_with_validation | 4096 | 3000 | 1239.6008573333331 | 1540.4755499999997 | 4645.084240662025 |
| pickle_without_validation | 4096 | 3000 | 1510.5566916666667 | 2035.0970999999977 | 4558.7034361798505 |
| json_with_validation | 4096 | 3000 | 1347.4358033333333 | 1751.8967999999995 | 4211.590940958295 |

## Q4. Graceful stop

| path | payload_size | attempted_messages | sent_before_stop | received_before_join | lost_estimate | completion_rate |
| --- | --- | --- | --- | --- | --- | --- |
| hybrid_bridge | 4096 | 100000 | 100000 | 1162 | 98838 | 0.01162 |
