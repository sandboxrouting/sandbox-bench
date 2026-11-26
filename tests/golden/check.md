**alpha (vm)**, run `r1`

| Probe                 | Verified | Outcome | Median      |
|-----------------------|----------|---------|-------------|
| create-exec           | 5/5      | pass    | Start 1.2 s |
| file-roundtrip        | 5/5      | pass    |             |
| internet              | 5/5      | pass    |             |
| egress-block          | 4/5      | fail    |             |
| exposed-port          | -        | not run |             |
| pause-keeps-files     | -        | n/a     |             |
| pause-keeps-memory    | -        | n/a     |             |
| snapshot-keeps-files  | -        | not run |             |
| snapshot-keeps-memory | -        | n/a     |             |
| fork-keeps-memory     | -        | n/a     |             |
| fork-isolation-x3     | -        | n/a     |             |

- **alpha** `egress-block` verified 4/5. Last failure: run `r1`, all attempt 4 (2026-11-20): AssertionError: hash mismatch. Evidence: `{"actual": "xyz", "expected": "abc"}`. Reproduce: `sbx check alpha --probe egress-block`

Raw counts from this run. The leaderboard counts a probe as passing at 9 of its last 10 attempts. 1 excluded (our errors, see the run log).
