# Simulink first-order FMI replay

This package reproduces the licensed Simulink comparison from VeraGrid without
placing generated or licensed-runtime artifacts in Git. It covers
`0.1 dx/dt = u - x`, `x(0)=0`, `h=0.001 s`, and right-continuous events
`u=1`, `-0.5`, and `0.25` at `0.2`, `0.5`, and `0.8 s`.

The matrix contains FMI 1/2/3 Co-Simulation and Model Exchange. CS is checked
against `x_BE[n+1]=(x_BE[n]+0.01*u[n])/1.01` at `2e-10` and against the
analytic trajectory at `0.004`. ME uses fixed-step Simulink `ode4` and is
checked against the analytic trajectory at `1e-7`. Versions within one
interface must agree point by point at `1e-12`; every comparison uses `rtol=0`.

`validated_run.json` is historical lineage for the closed R2025b Update 1 run,
not proof for a later checkout. A current PASS requires the fresh replay below.

## Repository boundary

Only source, documentation, style, and historical lineage are tracked. FMU,
DLL, SLX, CSV, JSON receipt, log, PNG, and PDF files belong in a new external
work directory. Every Python invocation uses `-B`; syntax is parsed in memory,
never with `py_compile`. Inventory all existing `__pycache__` and `.pyc` paths,
sizes, and hashes before the first command and prove that inventory is identical
after generation, validation, and plotting.

## 1. Generate six current FMUs

Run from the repository root with explicit executable, source, and output
paths. The maintained assets are:

- `build_first_order_matrix.m`: 11234 bytes,
  `a6fcd29a69637681897b2b3001e4309c87e149d72db8c40cb357e65a7bac3260`
- `run_first_order_matrix.m`: 10724 bytes,
  `31a1c70422c01b8c4da06a6c0ce3fbf06851efd3c886abc52c8f8604a00d6252`
- `sober-scientific.mplstyle`: 1085 bytes,
  `8e8036d09b98c3e47b3dc275b07b5b1bc9f6f9ce667c839456e3919b99cca375`

```text
<python.exe> -B -m examples.fmi.simulink_first_order.generate_first_order_matrix \
  --repository-root <absolute-repository-root> \
  --git-executable <absolute-git.exe> \
  --expected-head <40-character-HEAD> \
  --expected-tree <40-character-HEAD-tree> \
  --output-dir <new-external-work-directory> \
  --build-script-size-bytes 11234 \
  --build-script-sha256 a6fcd29a69637681897b2b3001e4309c87e149d72db8c40cb357e65a7bac3260 \
  --run-script-size-bytes 10724 \
  --run-script-sha256 31a1c70422c01b8c4da06a6c0ce3fbf06851efd3c886abc52c8f8604a00d6252 \
  --style-size-bytes 1085 \
  --style-sha256 8e8036d09b98c3e47b3dc275b07b5b1bc9f6f9ce667c839456e3919b99cca375
```

The generator rejects a wrong HEAD/tree, staged or out-of-scope changes,
imports outside `<repository>/src/VeraGridEngine`, and output inside the
checkout. It exports, inspects, smoke-runs, and hashes exactly six current FMUs.
That fresh manifest, rather than this README or the historical projection,
drives MATLAB.

## 2. Execute licensed Simulink

Transfer the complete external directory using explicit `ssh.exe`/`scp.exe`
paths to one fresh directory such as
`C:/SimulinkManager/Projects/VeraGridFirstOrderReplay_<source-token>`. SSH
credentials, license material, host secrets, and scheduled-task definitions
must remain external.

```text
<matlab.exe> -batch "cd('<remote-work-directory>'); run('build_first_order_matrix.m'); run('run_first_order_matrix.m')"
```

The builder authenticates the six FMUs from the current manifest and records
six isolated model hashes. The runner reauthenticates each FMU and model before
execution, retains exactly 1201 samples per cell, and records old/new/new input
values at every event. Retrieve the complete directory. If a temporary
scheduled task was needed, remove only that task and retain external evidence
that it no longer exists.

## 3. Validate and plot the retrieved evidence

```text
<python.exe> -B -m examples.fmi.simulink_first_order.validate_first_order_matrix --execution-dir <retrieved-external-work-directory>
<python.exe> -B -m examples.fmi.simulink_first_order.plot_first_order_matrix --execution-dir <retrieved-external-work-directory>
```

The CSV is the acceptance oracle. Receipts report error maxima and sample times,
grid and finite checks, inherited event state, and every version delta. The
plotter never simulates, interpolates, resamples, smooths, clips, or normalizes;
it produces paired PNG/PDF outputs for trajectory agreement, event continuity,
and pointwise residuals.

## Claim boundary

Open-source/toolchain and method evidence precede this commercial phase. A
fresh PASS here supports only this normalized fixture on the recorded licensed
host. It is not an FMI certification-authority result, physical-device
validation, bit-identical cross-toolchain reproduction, multiplatform evidence,
or evidence for PowerFactory, Modelica, or PSCAD. PowerFactory is maintained
as a separate commercial lane in `../powerfactory_first_order`.
