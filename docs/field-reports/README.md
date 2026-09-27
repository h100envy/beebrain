# field reports

headless runs of the field on live pools. paper money, read only data, the bee starts with an empty memory every run.
each report comes with its raw snapshot, so anyone can recompute it:

```
beebrain report docs/field-reports/2026-09-26-solana.json.gz
```

| date | chain | minutes | pools scored | forward tested | bee | random |
| --- | --- | --- | --- | --- | --- | --- |
| 2026-09-26 | [solana](2026-09-26-solana.md) | 74 | 522 | 516 | -30.3% | -69.8% |
| 2026-09-26 | [base](2026-09-26-base.md) | 80 | 137 | 123 | +1.0% | -16.7% |
| 2026-09-26 | [solana, long](2026-09-26-solana-140m.md) | 140 | 856 | 844 | -49.7% | +28.8% |

all three together: 1,483 forward tested pools. PASS went up 30% of the time (60 pools), the brain's own SKIP 20% (761 pools). the bee beat random in two runs out of three. the long run is the one it lost, and the memory it built there seeds new bees on `/trade`.

one run on each chain is an anecdote, not a result. the point of publishing them is the method.
