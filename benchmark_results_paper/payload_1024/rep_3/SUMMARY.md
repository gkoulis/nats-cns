# CNS Benchmark Summary

## Q1. Latency overhead

| path | payload_size | messages | mean_us | median_us | p95_us | p99_us |
| --- | --- | --- | --- | --- | --- | --- |
| local_only | 1024 | 3000 | 35.334559999999996 | 27.79 | 60.99824999999999 | 69.12761999999987 |
| distributed_only | 1024 | 3000 | 1432.3490060000001 | 1365.0695 | 1811.8082499999996 | 2705.830269999974 |
| hybrid_bridge | 1024 | 3000 | 1858.659546 | 1774.2045 | 2272.7976499999995 | 4606.840189999978 |

## Q2. Throughput

| path | payload_size | messages | elapsed_s | throughput_msgs_per_s |
| --- | --- | --- | --- | --- |
| local_only | 1024 | 50000 | 1.658472469 | 30148.224305555235 |
| distributed_only | 1024 | 50000 | 8.865558123 | 5639.802853503891 |
| hybrid_bridge | 1024 | 50000 | 39.938918058 | 1251.9117299920124 |

## Q3. Validation and serialization

| case | payload_size | messages | latency_mean_us | latency_p95_us | throughput_msgs_per_s |
| --- | --- | --- | --- | --- | --- |
| pickle_with_validation | 1024 | 3000 | 1102.2202886666666 | 1387.2382999999993 | 6450.223081287778 |
| pickle_without_validation | 1024 | 3000 | 1106.186161 | 1371.5590999999995 | 7148.752105968755 |
| json_with_validation | 1024 | 3000 | 1135.34573 | 1451.5943999999997 | 6226.788168240692 |

## Q4. Graceful stop

| path | payload_size | attempted_messages | sent_before_stop | received_before_join | lost_estimate | completion_rate |
| --- | --- | --- | --- | --- | --- | --- |
| hybrid_bridge | 1024 | 100000 | 100000 | 1314 | 98686 | 0.01314 |
