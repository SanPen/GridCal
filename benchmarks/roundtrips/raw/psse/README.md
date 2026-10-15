# PSS/E RAW Roundtrip Benchmarks

Fixtures copied from `src/tests/data/grids/RAW`:

- `IEEE 14 bus.raw`
- `IEEE 30 bus.raw`
- `IEEE 14 bus.rawx`
- `IEEE_14_v35_3_nudox_1_hvdc_desf_rates_fs_ss.raw`

Run:

```bash
python3 benchmarks/roundtrips/raw/psse/run_raw_roundtrip.py
```

This imports each case, exports it back to RAW/RAWX, re-imports it, and checks numerical-circuit equivalence. The script also prints the structural logger when metadata changes during export but the numerical model is still preserved.
