# CNS Benchmark Summary

## Q1. Latency overhead

| path | payload_size | messages | mean_us | median_us | p95_us | p99_us |
| --- | --- | --- | --- | --- | --- | --- |
| local_only | 256 | 3000 | 28.222206999999997 | 23.962 | 52.494699999999966 | 89.74141999999986 |
| distributed_only | 256 | 3000 | 1389.812351 | 1184.059 | 2306.8116999999984 | 5092.501159999985 |
| hybrid_bridge | 256 | 3000 | 1652.6291716666667 | 1547.407 | 2241.2672999999995 | 3248.578409999983 |

## Q2. Throughput

| path | payload_size | messages | elapsed_s | throughput_msgs_per_s |
| --- | --- | --- | --- | --- |
| local_only | 256 | 50000 | 1.220435183 | 40968.992615480835 |
| distributed_only | 256 | 50000 | 6.97021515 | 7173.379719849824 |
| hybrid_bridge | 256 | 50000 | 40.662920954 | 1229.6214543112283 |

## Q3. Validation and serialization

| case | payload_size | messages | latency_mean_us | latency_p95_us | throughput_msgs_per_s |
| --- | --- | --- | --- | --- | --- |
| pickle_with_validation | 256 | 3000 | 1153.8074016666667 | 1513.07475 | 7369.414237638543 |
| pickle_without_validation | 256 | 3000 | 1112.4708529999998 | 1457.1298000000002 | 7773.677988951785 |
| json_with_validation | 256 | 3000 | 1128.4680273333333 | 1480.7017999999994 | 6586.689993619561 |

## Q4. Graceful stop

| path | payload_size | attempted_messages | sent_before_stop | received_before_join | lost_estimate | completion_rate |
| --- | --- | --- | --- | --- | --- | --- |
| hybrid_bridge | 256 | 100000 | 100000 | 1260 | 98740 | 0.0126 |
