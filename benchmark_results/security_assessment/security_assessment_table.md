# Security Assessment Summary

| Scheme | E2E Mean (ms) | E2E P95 (ms) | Throughput (msg/s) | Expansion (x) | Spoof Block (%) | Replay Block (%) | Tamper Block (%) | Flood Drop (%) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| No Security | 0.002 | 0.002 | 80645.16 | 1.74 | 0.0 | 0.0 | 0.0 | 0.0 |
| RSA Signature Only | 0.713 | 1.696 | 1356.55 | 3.78 | 100.0 | 100.0 | 100.0 | 100.0 |
| Hybrid RSA-AES (Proposed) | 1.301 | 2.869 | 752.13 | 6.15 | 100.0 | 100.0 | 100.0 | 100.0 |
