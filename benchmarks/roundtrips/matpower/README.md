# MATPOWER Roundtrip Benchmark

Fixtures copied from `src/tests/data/grids/Matpower`:

- `case14.matpower`
- `case_ieee30.matpower`

Run:

```bash
python3 benchmarks/roundtrips/matpower/run_matpower_roundtrip.py
```

This imports each case, exports it back to MATPOWER, re-imports it, and checks power-flow voltage and branch-flow preservation.
