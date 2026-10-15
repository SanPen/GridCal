# CGMES Roundtrip Benchmark

Fixtures copied from `src/tests/data/grids/CGMES_2_4_15`:

- `micro_grid_NL_T1.zip`
- `micro_grid_BD.zip`

Run:

```bash
python3 benchmarks/roundtrips/cgmes/run_cgmes_roundtrip.py
```

This imports the public micro-grid CGMES case with its boundary set, exports it back to CGMES, re-imports it, and checks numerical-circuit equivalence.

The script may print a long structural comparison logger. That is expected for regenerated identifiers and profile metadata. The benchmark passes only when the numerical circuit comparison still ends with `ok`.
