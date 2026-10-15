# VeraGrid Roundtrip Benchmarks

This folder is the practical compatibility story for VeraGrid.

It shows that the same grid can be imported, exported, re-imported, and solved again across the file formats that matter in real interchange work. Instead of a vague "supports format X" claim, these benchmarks keep concrete fixtures, runnable commands, and generated outputs in one place.

Current benchmark groups:

- `cim/opendss`: plain CIM cases focused on OpenDSS-style interoperability
- `raw/psse`: PSS/E RAW and RAWX roundtrips
- `matpower`: MATPOWER roundtrips
- `ucte`: UCTE roundtrip
- `cgmes`: CGMES 2.4.15 roundtrip with boundary set
- `pandapower`: native `pandapower` JSON/SQLite/Pickle roundtrips plus CGMES -> `pandapower` interop
- `pypowsybl`: native XIIDM/IIDM container roundtrips plus CGMES -> XIIDM interop

## Why this folder exists

- It is regression coverage you can run locally.
- It is a compatibility demo you can show to users, partners, and customers.
- It keeps the fixture, the runner, and the exported artifact side by side, so failures are easy to inspect.

## What "pass" means here

The pass criterion is intentionally format-specific:

- `cim/opendss`: VeraGrid power-flow roundtrip compatibility on committed plain CIM fixtures
- `matpower` and `ucte`: bus-voltage and branch-flow preservation after export and re-import
- `raw/psse` and `cgmes`: numerical-circuit equivalence after export and re-import
- `pandapower` and `pypowsybl` native formats: bus-voltage and branch-flow preservation after native reserialization
- `pandapower` and `pypowsybl` CGMES interop cases: external tool must load VeraGrid's CGMES export, write its own native format, VeraGrid must re-import that file, and the resulting model must solve

Some runners print structural comparison noise because identifiers or metadata can be regenerated during export. The benchmark still passes only when the electrical model stays equivalent by the criterion above.

## Quick start

Run everything from the repository root:

```bash
cd /home/santi/Git/eRoots/VeraGrid
python3 benchmarks/roundtrips/run_all.py
```

Run one family:

```bash
python3 benchmarks/roundtrips/cim/opendss/run_all.py
python3 benchmarks/roundtrips/raw/psse/run_raw_roundtrip.py
python3 benchmarks/roundtrips/matpower/run_matpower_roundtrip.py
python3 benchmarks/roundtrips/ucte/run_ucte_roundtrip.py
python3 benchmarks/roundtrips/cgmes/run_cgmes_roundtrip.py
python3 benchmarks/roundtrips/pandapower/run_pandapower_roundtrip.py
python3 benchmarks/roundtrips/pypowsybl/run_pypowsybl_roundtrip.py
```

## Environment

Use the same Python environment you already use for `VeraGridEngine`.

Required:

- `python3`
- VeraGrid dependencies installed
- execution from the repository root

Optional:

- `wine`, only if you want to regenerate upstream OpenDSS-exported fixtures instead of using the committed benchmark inputs

## Benchmark layout

- `cim/opendss/`: OpenDSS-facing plain CIM roundtrips and fixture notes
- `raw/psse/`: RAW and RAWX roundtrip cases, including a more detailed v35/HVDC fixture
- `matpower/`: native MATPOWER cases, currently IEEE 14 and IEEE 30
- `ucte/`: stable UCTE roundtrip case
- `cgmes/`: public micro-grid CGMES case plus boundary set
- `pandapower/`: committed `pandapower` fixtures plus generated JSON/SQLite/Pickle roundtrip artifacts
- `pypowsybl/`: committed XIIDM fixture plus generated XIIDM/IIDM roundtrip artifacts

Generated export artifacts are kept next to each benchmark on purpose. This makes the folder useful both as a test suite and as an inspection/demo bundle.
