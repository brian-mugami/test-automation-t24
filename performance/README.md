# Performance Testing

This folder is separate from the Selenium functional automation.

The default Locust scenario is read-only: it sends GET requests to selected
T24 paths and records response time, throughput, and failures. Use transactional
load only in a dedicated performance environment with approved test data.

Results are written under `performance/results/run-YYYYMMDD-HHMMSS/`.
