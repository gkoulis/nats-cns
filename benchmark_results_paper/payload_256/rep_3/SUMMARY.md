# CNS Benchmark Summary

## Q1. Latency overhead

| path | payload_size | messages | mean_us | median_us | p95_us | p99_us |
| --- | --- | --- | --- | --- | --- | --- |
| local_only | 256 | 3000 | 34.45780966666667 | 26.101 | 62.611049999999985 | 110.31234999999992 |
| distributed_only | 256 | 3000 | 1274.3157573333333 | 1179.7295 | 1792.0374499999996 | 2197.862699999994 |
| hybrid_bridge | 256 | 3000 | 1727.437638 | 1576.474 | 2351.4545 | 4598.835979999983 |

## Q2. Throughput

| path | payload_size | messages | elapsed_s | throughput_msgs_per_s |
| --- | --- | --- | --- | --- |
| local_only | 256 | 50000 | 1.539186057 | 32484.701750387543 |
| distributed_only | 256 | 50000 | 8.09178406 | 6179.107058375949 |
| hybrid_bridge | 256 | 50000 | 39.588135937 | 1263.0046557273952 |

## Q3. Validation and serialization

| case | payload_size | messages | latency_mean_us | latency_p95_us | throughput_msgs_per_s |
| --- | --- | --- | --- | --- | --- |
| pickle_with_validation | 256 | 3000 | 1132.40969 | 1496.6595999999997 | 6735.653877307195 |
| pickle_without_validation | 256 | 3000 | 1172.7336753333334 | 1652.623049999999 | 7022.485340286805 |
| json_with_validation | 256 | 3000 | 1204.4853323333334 | 1608.393449999999 | 6332.66442454461 |

## Q4. Graceful stop

| path | payload_size | attempted_messages | sent_before_stop | received_before_join | lost_estimate | completion_rate |
| --- | --- | --- | --- | --- | --- | --- |
| hybrid_bridge | 256 | 100000 | 100000 | 1279 | 98721 | 0.01279 |
