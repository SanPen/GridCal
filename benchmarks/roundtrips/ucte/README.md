# UCTE Roundtrip Benchmark

Fixture copied from `src/tests/data/grids/ucte/IEEE 14 bus.uct`.

Run:

```bash
python3 benchmarks/roundtrips/ucte/run_ucte_roundtrip.py
```

This imports IEEE14, exports it back to UCTE, re-imports it, and checks power-flow voltage and branch-flow preservation.
