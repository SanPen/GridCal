# PowerFactory first-order FMI replay

This directory is the reproducible `examples/fmi` owner for the commercial
PowerFactory comparison. It uses the same normalized first-order fixture as the
retained Simulink lane:

- `0.1 dx/dt = u - x`, with `x(0)=0`;
- right-continuous `u=1/-0.5/0.25` at `0.2/0.5/0.8 s`;
- output lattice `0..1.2 s` at `1 ms`;
- FMI 2 and FMI 3, Co-Simulation and Model Exchange.

PowerFactory 2025 SP4 documents import for FMI 2/3, not FMI 1. Therefore FMI 1
is `NOT_APPLICABLE` in this commercial lane; its open-source and Simulink
evidence remains in the preceding method/toolchain phases.

## Why FMI 3 has an explicit derivative

The unmodified VeraGrid FMI 3 CS and ME archives remain authoritative. On this
PowerFactory build both reached import but failed `ComInc` with code 2 because
the importer calls the optional empty configuration-mode cycle. The runner
copies only the authenticated 15-file generated source closure per interface,
changes only guarded `fmi3EnterConfigurationMode` and
`fmi3ExitConfigurationMode`, and compiles through VeraGrid's public
`compile_fmu_shared_library`. Compiler discovery remains owned by VeraGrid's public shared
`Compiler` interface; this example never imports or inspects private
subpackages. Standard and derivative FMU hashes are retained separately. This opt-in compatibility profile is PowerFactory-specific; it is
not a change to the product exporter or the FMI conformance claim.

## Reproduce

Run from the repository root with Python 3.11 and `-B`. Use a short, new output
path because Windows command-line length can be exceeded by the reviewed Clang
toolchain extraction. No FMU, DLL, PowerFactory project/database, raw CSV,
credential, or licence material belongs in Git.

```text
<python.exe> -B -m examples.fmi.powerfactory_first_order.supervise_powerfactory_first_order \
  --manifest <fresh-six-cell-directory>/first-order-fmu-manifest.json \
  --powerfactory-root <PowerFactory-2025-SP4-root> \
  --binding <PowerFactory-2025-SP4-root>/Python/3.11/powerfactory.pyd \
  --output-dir <new-short-external-directory>
```

The parent supervisor creates a per-run nonce, spawns one sequential
`GetApplicationExt` worker, and completes the receipt if native PowerFactory
release ends that worker before Python returns. The worker rejects an existing
native session, creates only one uniquely named current-user project, and
deletes that exact project to PowerFactory's recycle bin. It never clears the
recycle bin. CS runs at a 1 ms communication step. ME runs at fixed internal
steps of 0.125, 0.0625, and 0.03125 ms while retaining the common 1 ms output
lattice. Before native release, an atomic checkpoint authenticates the cleanup,
the exact 30-line normalized source closure, and all eight raw traces.

Validate outside the licensed API:

```text
<python.exe> -B -m examples.fmi.powerfactory_first_order.validate_powerfactory_first_order \
  --execution-dir <external-PowerFactory-directory> \
  --generator-manifest <fresh-six-cell-directory>/first-order-fmu-manifest.json \
  --simulink-dir <retained-Simulink-execution-directory>
```

The validator preserves raw CSV, never interpolates, canonicalizes only the
declared single or old/new/new event rows, and checks all 1201 state samples
with `rtol=0`. CS uses the indexed backward-Euler oracle; ME uses the continuous
analytic oracle and the three-level all-sample convergence test. FMPy executes
the exact PowerFactory-selected FMU hashes. Simulink is authenticated
same-fixture historical lineage, not a same-binary claim.

After a numerical `PASS`, render the fixed waveform, event-window, and
pointwise-error figures:

```text
<python.exe> -B -m examples.fmi.powerfactory_first_order.plot_powerfactory_first_order \
  --execution-dir <external-PowerFactory-directory>
```

The three PNG/PDF pairs are generated only from the authenticated combined CSV
and numerical receipt. The figures are review aids; the retained samples and
receipts are the acceptance evidence.

## Claim boundary

A completed run supports this normalized fixture on the recorded licensed
PowerFactory host. It does not claim official FMI tool certification,
device-specific physical validation, another PowerFactory version, another
operating system, or standard FMI 3 behavior for the explicit compatibility
derivative. The official FMI tools-list preparation is a later phase.
