# PowerFactory replay of the standard electrical FMUs

This recipe replays the exact standard GENSAL, TGOV1 and ESDC2A win64 FMUs
in licensed DIgSILENT PowerFactory 2025 SP4. PowerFactory imports FMI 2 and
FMI 3, CS and ME: twelve applicable standard cells. FMI 1 is
`NOT_APPLICABLE` in this lane and remains covered by FMPy and Simulink.

The campaign was executed while the catalog was authenticated current-worktree
evidence, so its immutable receipts correctly record
`CURRENT_UNTRACKED_WORKTREE`. The complete catalog, sources, scripts and
documentation were subsequently committed together in `e47b0b537`; that
historical receipt label must not be rewritten after the fact.

The runner authenticates every original standard FMU hash and leaves the
canonical catalog byte-identical. Because PowerFactory 2025 SP4 calls FMI 3
Configuration Mode even though these FMUs declare no structural parameters,
the supervisor deterministically regenerates each of the six FMI 3 source
closures with its canonical `instantiationToken`, compares two regenerations
and every deterministic pre-patch FMU member, and builds six external
PowerFactory-only derivatives through the existing reviewed two-callback
compatibility profile. Exactly `resources/export_model.json` and
`resources/snapshot.json` are retained by raw hash and size for both
regenerations, but they are non-executable debug snapshots with fresh graph
identities and are not used to claim semantic equivalence. No wildcard or
third exclusion is permitted. Generated source, `modelDescription.xml`, all
other deterministic resources and the PE-timestamp-normalized DLL must match
exactly. Every final derivative copies all canonical non-binary members byte
for byte.

PowerFactory also reads CS input `start` values during initialization before
the owned `t=0` events take effect. The canonical TGOV1 and ESDC2A CS FMUs
declare zero starts, while their authenticated physical schedules begin at
`OmegaPu_TGOV1=1`, `PRefPu_TGOV1=0.5`, `UsPu_ESDC2A=1` and
`UsRefPu_ESDC2A=1.0125`. The runner therefore creates four additional
PowerFactory-only initialization derivatives. For FMI 2 TGOV1/ESDC2A CS,
only `modelDescription.xml` differs from the canonical FMU. For FMI 3
TGOV1/ESDC2A CS, only the reviewed callback DLL and
`modelDescription.xml` differ. Exactly two `start` attributes change in each
of the four cells, for eight changes total; GENSAL, every ME XML, every other
archive member and every canonical FMU remain unchanged. The build receipt
records canonical, intermediate and final hashes plus the exact member and
input-coordinate differences. These derivatives remove an importer-specific
startup transient without excluding startup samples or relaxing the 0.005
criterion.

PowerFactory port ordering is treated as vendor-owned. Exact
unique name sets are required, `inputInitFmu` must remain empty, and an owned,
active parameter event at `t=0` initializes every named input from the first
published schedule row. Later schedule changes use the same named-event path,
and result columns address named outputs. This avoids the reproducible native
`ComInc` crash caused by populating `inputInitFmu` in PowerFactory 2025 SP4.

Run from the repository root with Python 3.11 and `-B`, using a new short
external output path:

```text
<python311> -B -m examples.fmi.veragrid_standard_examples.supervise_powerfactory_matrix \
  --catalog-root <repository>/examples/fmi/veragrid_standard_examples/published/win64 \
  --repository-root <repository> \
  --powerfactory-root "C:/Program Files/DIgSILENT/PowerFactory 2025 SP4" \
  --binding "C:/Program Files/DIgSILENT/PowerFactory 2025 SP4/Python/3.11/powerfactory.pyd" \
  --output-dir <new-external-directory>
```

The supervisor executes exactly 24 sequential jobs. Every job has its own
spawned worker, nonce, PID, directory and unique current-user project. The
worker refuses a pre-existing native PowerFactory session, journals every
mutation, checks ancestry before each mutation, and deletes only that exact
project to the PowerFactory recycle bin; it never clears the recycle bin.
After cleanup it atomically publishes one-observation `child-checkpoint.json`
and waits at most 30 seconds for the parent checkpoint acknowledgement. The
child validates the nonce/PID/job/hash-bound acknowledgement, publishes
`worker-ack-validated.json`, and only then exits through `os._exit(0)`. The
parent requires exit code zero and complete process absence before starting
the next job. No failed job is silently retried.

CS uses a 1 ms communication/integration step. ME is retained at internal
steps of 0.125, 0.0625 and 0.03125 ms; these three levels are sensitivity
diagnostics, not an unsupported analytic convergence claim. Only the finest
ME trace contributes to the cell verdict. All raw named inputs and outputs are
retained at 1 ms.

Validate without importing the licensed API:

```text
<python> -B -m examples.fmi.veragrid_standard_examples.validate_powerfactory_matrix \
  --execution-dir <external-directory> \
  --output-dir <new-external-validation-directory> \
  --catalog-root <repository>/examples/fmi/veragrid_standard_examples/published/win64
```

The execution directory is immutable input. Validation refuses a pre-existing
or overlapping output directory and writes all validator views, comparisons
and the distinct `numerical-receipt-rev16.json` only below the new output
directory. The receipt binds the source release checkpoint, the predecessor
numerical receipt, the corrected validator source, every raw trace and every
derived artifact by SHA-256.

Each of the 24 immutable raw traces records the PowerFactory pre-event input
vector at its zero-time row. The validator therefore writes 24 separately
named, atomically published views whose only permitted edits are the named
input coordinates at that row. It retains both hashes, every rewritten
coordinate and every actual numerical difference; outputs and all
positive-time samples must be bytewise equivalent as numeric arrays. The
first positive sample must already prove the declared `t=0` event. The exact
1 ms lattice is derived from the authenticated published reference horizon:
GENSAL and TGOV1 contain 2001 ticks through 2.0 s, while ESDC2A contains 1501
ticks through 1.5 s. Both coarse/fine ME sensitivity comparisons consume
authenticated views, never immutable raw traces directly.

Every later changed-input event must contain the complete new vector on its
exact sample. The sole evidence-bound exception is `UPssPu_ESDC2A` at 1.1 s:
PowerFactory retains the complete old vector at that sample and applies the
complete new vector at 1.101 s in all eight audited FMI 2/3 CS/ME runs. The
validator rejects this timing for every other tuple, as well as intermediate,
mixed, reversed, partial, adjacent-pending or longer-delayed transitions. The
numerical receipt retains every accepted delayed transition and requires
exactly the eight instances present in the complete authenticated audit.

The validator requires exactly one row at non-event ticks. At events, changed
inputs may contain only their declared old/new values, transition at most once
without reversal, and end at the complete new vector. Every canonical named
input must equal the right-continuous schedule at every 1 ms tick. It then
selects exact 10 ms rows, without interpolation, because the published FMPy
references use a 10 ms lattice. The per-output absolute and normalized limits
are 0.005; event samples use the declared previous/current envelope and raw
`t=0` is reported separately.

After numerical validation, figures can be rendered solely from retained
comparison CSVs:

```text
<python> -B -m examples.fmi.veragrid_standard_examples.plot_powerfactory_matrix \
  --execution-dir <new-external-validation-directory> \
  --catalog-root <repository>/examples/fmi/veragrid_standard_examples/published/win64
```

This campaign is commercial importer interoperability evidence for the
recorded PowerFactory release. It is not official FMI certification and does
not cover PowerFactory as an FMU exporter. All external callback and
initialization derivatives are strictly importer-compatibility artifacts for
this campaign; they are not published as canonical VeraGrid FMUs.

## Authenticated outcome

The licensed PowerFactory 2025 SP4 execution completed 24/24 isolated jobs:
one CS job and three ME sensitivity jobs for every GENSAL, TGOV1 and ESDC2A
FMI 2/3 tuple. Numerical validation passed all 12 applicable cells and all six
FMI 2-versus-3 same-interface comparisons. It retained 24 authenticated
validator views and accepted exactly eight documented one-tick ESDC2A input
transitions. The 0.005 absolute and normalized limits were not relaxed.

The final numerical receipt has SHA-256
`1d4bd41c7cf37b561e98d65007d4e8b120ca97e169ac0d8400c4c826ac9cead9`.
The figure receipt has SHA-256
`40dbba58a7abd8e5e4490f4508603d83864419c26b9deef85dd4d74eefc8d75a`
and binds six PNG plus six vector PDF figures. The predecessor numerical
receipt remained bound by SHA-256
`cd9567e23f84160db03a7503a8ef884a529786e2d6d2c3d99eb19e3ea57c7beb`.
