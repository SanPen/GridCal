# FMI comparison

The concise evidence views are:

- [Interoperability status](INTEROPERABILITY_STATUS.md): the master inventory
  of open-source and commercial test campaigns, including direction, evidence
  currency, result and known limits.
- [Local toolchain platform evidence](TOOLCHAIN_PLATFORM_EVIDENCE.md): a
  commit-scoped Windows, Linux, and macOS dependency-resolution observation,
  kept separate from FMI execution and release-platform claims.

These views are indexes over the detailed recipes below. They do not replace
the original manifests and receipts, and they do not claim official FMI
certification or listing.

This package owns reproducible FMI examples and interoperability evidence under
the repository's public `examples/fmi` tree. It remains outside
`VeraGridEngine` because benchmark evidence is not part of the runtime API.

## Commercial-exporter importer cross-check

The declarative [case manifest](importer_cross_check_cases.json) pins three FMI
2.0 Co-Simulation win64 FMUs from each of Dymola 2019FD01, FMI Toolbox for
MATLAB 2.3, and MWorks 2021 at archived `fmi-cross-check` commit
`55c6704bbcaed3e0f4f788a02af0aba08b7faa4a`. Every FMU, reference CSV,
option file, README, and the one optional input CSV has an exact SHA-256.

After obtaining that exact corpus, run all nine cases through VeraGrid's
existing importer:

```text
python -m examples.fmi.importer_cross_check ^
  --manifest examples/fmi/importer_cross_check_cases.json ^
  --corpus-root <fmi-cross-check>/fmus/2.0/cs/win64 ^
  --output <new-output-directory>
```

The retained campaign executed all nine FMUs to their declared stop times.
Eight passed `fmpy.cross_check.validate_result`: all three Dymola cases, all
three FMI Toolbox cases, and MWorks MixtureGases and Rectifier. MWorks
BouncingBall is `COMPLETED_WITH_FINDINGS` because its pinned FMU starts output
`y` at 10 while its pinned reference starts `y` at 20; direct FMPy reproduces
the same rejection. The closed receipt has SHA-256
`028dbc3b8f570d4d5deae341c06b39f3f60f3e109dddeb9825410df835eac94b`.
This is bounded importer evidence, not certification or universal
compatibility.

## Standard electrical FMU examples (local preflight)

The [win64 catalog](veragrid_standard_examples/published/win64/README.md)
publishes three distinct existing VeraGrid RMS model families: GENSAL, TGOV1,
and ESDC2A. Each has FMI 1/2/3 Co-Simulation and Model Exchange archives, for
18 FMUs total. The catalog includes the exact input trajectories, raw FMPy
reference CSVs, comparison options, MPL-2.0 and corresponding-source notices,
per-file SHA-256 hashes, and a [manifest](veragrid_standard_examples/published/win64/manifest.json).
The [typed generator](veragrid_standard_examples/generate_standard_examples.py)
rebuilds the package from a clean checkout with explicit repository, Git,
external work-directory, publication-root, expected-HEAD, and source-tree
digest arguments. The final `published/win64` directory must be absent before
rebuilding; compilation and all checks occur outside the checkout, followed by
one verified, atomic catalog publication.

All 18 cells passed local VeraGrid export and FMPy execution on the recorded
Windows host. Their traces are compared pointwise on a 0.01 s grid against FMI
2 of the same interface; CS/ME comparison retains the causal event phase, gates
every non-boundary sample and each event against a pre/post ME envelope, and
reports the raw initial CS visibility separately. This local preflight is
separate from the later licensed Simulink and PowerFactory replays of these
exact families. The historical manifest remains bound to the original local
preflight, while the authenticated interoperability evidence records Simulink
18/18 and PowerFactory 12/12 applicable cells as `PASS`. PowerFactory FMI 2 uses
the standard FMUs, while its passing FMI 3 cells use the documented bounded
importer-only derivatives. None of these campaigns is official FMI
certification. The catalog is ready for public use after its stable
`examplesURL` becomes active in the public default branch.

The committed sample archives currently contain native `win64` binaries only;
they do not contain an FMI `sources/` payload. VeraGrid's exporter separately
supports host-native Windows, Linux, Intel macOS, and Apple Silicon macOS
targets, and VeraGrid itself is an MPL-2.0 open-source project. The prospective
tools entry uses the operating-system platform labels only; source availability
is documented in the vendor compatibility page. Matching-host generation and
execution passed 18/18 cells on each of Windows, Linux, and macOS. The committed
Windows catalog must still not be presented as containing cross-platform
binaries or as proof of bit-identical host results.

Commercial first-order replays are maintained beside the open-source lanes.
The [PowerFactory FMI 2/3 CS/ME recipe](powerfactory_first_order/README.md)
reuses the same `0.1 dx/dt=u-x` fixture and retained Simulink lineage, keeps
licensed/runtime artifacts outside Git, and records FMI 1 as not applicable to
the installed PowerFactory 2025 SP4 importer.

The device runner exports and executes four native cases through the public
product interfaces:

- RMS FMI 2.0 Co-Simulation
- RMS FMI 2.0 Model Exchange
- EMT FMI 2.0 Co-Simulation
- EMT FMI 2.0 Model Exchange

Run it from the repository root in an environment where VeraGridEngine and
FMPy are installed:

```text
python -m examples.fmi.run_device_examples --output-dir <output-directory>
```

The RMS comparison runner executes VeraGrid, direct FMPy, and an independent
OMSimulator process against the exact same generated FMU archive for each mode.
It then publishes the complete evidence package atomically:

```text
python -m examples.fmi.run_rms_comparison \
  --output-dir <new-package-directory> \
  --source-revision <revision> \
  --source-tree-sha256 <lowercase-sha256> \
  --omsimulator-executable <absolute-path-to-OMSimulator.exe>
```

Schema v3 retains exactly 32 declared artifacts: the two combined comparison
CSVs, two direct-FMPy raw CSVs, six raw OMSimulator artifacts per mode,
one FMU and one RMS report per mode, and twelve fixed PDF/SVG/PNG figures.
The manifest writer and verifier remain local to this `examples/fmi` benchmark package;
no manifest or manifest handler is part of `src` or the product runtime.

The caller owns the revision and tree digest because the benchmark never invokes
Git or infers provenance. Generated FMUs, reports, tables, manifests, and plots
belong in caller-selected output directories and are not versioned in this
package.

The RMS comparison applies a physical active-power step to a separate native
load. The event boundary is retained at 0.1 s with the old value and the first
post-event sample is 0.101 s. Both the Co-Simulation and Model Exchange FMUs
capture the actual initial voltage as `x(0)=u(0)`, retain `x'=0`, and express
the response through `u-x`; no network-specific initial voltage is hardcoded.
Direct FMPy replays the exact retained bus-voltage samples. The voltage response
first appears at 0.101 s. Model Exchange can expose direct feedthrough at that
sample; the causal Co-Simulation FMU consumes the new input over the following
communication interval and its P/Q response therefore appears at 0.102 s.
The package publishes raw overlaid trajectories plus separate
absolute-error figures as PDF, editable SVG, and 300 dpi PNG files. CSV rows and
the manifest retain the event phase, shared input, equations, response checks,
and per-sample acceptance budgets; the figures are not the acceptance oracle.

The comparison is engineering evidence, not a certification claim. FMPy is both
the direct public consumer and VeraGrid's FMI 2 runtime backend in this lane;
OMSimulator supplies the independent runtime path. The package records that
backend relationship, the exact process arguments, runtime identities, raw
input/output and logs, pairwise errors, and derived budgets. The result supports
an FMI 2 CS/ME orchestration and coupled-response claim for this retained
zero-derivative fixture on the recorded Windows host. It does not claim solver
accuracy, FMI-native internal time-event export, or cross-platform coverage.

## OpenModelica SMIB dynamic comparison

`run_smib_comparison` builds the maintained Modelica single-machine infinite-bus
plant with OpenModelica, exports one FMI 2.0 Co-Simulation archive, and executes
that exact archive through VeraGrid, direct FMPy, and OMSimulator. OpenModelica's
native DASSL result is retained as the independent model-fidelity reference.

All executable paths, versions, sizes, and SHA-256 identities are explicit
arguments. The runner does not search `PATH` or mutate the process environment.
It uses a 4 s horizon, a 0.002 s retained output grid, fault boundaries at
1.001 s and 1.151 s, and a 0.000125 s communication step for the three FMU
runtimes. A separate five-level VeraGrid refinement study uses steps from
0.002 s down to 0.000125 s.

```text
python -m examples.fmi.run_smib_comparison \
  --source-path <smib_network_plant.mo> \
  --source-size-bytes <bytes> \
  --source-sha256 <lowercase-sha256> \
  --omc-executable <absolute-path-to-omc.exe> \
  --omc-version <exact-version> \
  --omc-size-bytes <bytes> \
  --omc-sha256 <lowercase-sha256> \
  --build-output-dir <new-build-package-directory> \
  --omsimulator-executable <absolute-path-to-OMSimulator.exe> \
  --omsimulator-version <exact-version> \
  --omsimulator-size-bytes <bytes> \
  --omsimulator-sha256 <lowercase-sha256> \
  --fmpy-version 0.3.31 \
  --fmpy-distribution-sha256 <lowercase-sha256> \
  --comparison-output-dir <new-comparison-package-directory>
```

Acceptance has two independent numerical oracles. First, every pair among
VeraGrid, FMPy, and OMSimulator must agree on the exact common lattice within
`1e-12 + 1e-11 * scale`. Second, each FMU result must remain within normalized
maximum and RMS bounds of 0.01 and 0.005 against the native DASSL trajectory.
The refinement series must also decrease monotonically with every adjacent ratio
in the closed interval [1.8, 2.2]. These metrics are recomputed from the retained
raw CSV files and compared
exactly with the manifest before atomic publication.

The comparison package retains raw traces, process logs, and three sober figures
as PDF, editable SVG, and 300 dpi PNG: overlaid trajectories with event markers,
native-reference
errors, and convergence. The figures are review aids; the CSV recomputation is
the acceptance oracle. This evidence supports only the recorded FMI 2.0 CS SMIB
execution on the recorded Windows host. It is not FMI certification,
multiplatform evidence, or evidence for FMI 1.0, FMI 3.0, or Model Exchange. The
separate caller-selected build directory owns OpenModelica's generated FMU and
native outputs; the comparison manifest binds their identities without copying
the maintained Modelica source or Lua driver into the evidence package.

Product integration tests live under `src/tests/FMI` and deliberately use
their own fixtures. Production modules must not import or invoke this examples
package, and tests must not add it to their import path implicitly.
## Reference FMU corpus

reference_fmu_catalog.json pins the official Reference FMUs v0.0.41
BouncingBall and Stair models for FMI 2.0 and FMI 3.0. Each retained FMU
declares both Co-Simulation and Model Exchange. The catalog is a sealed
benchmark identity: changing its release, case order, hash, scalar type, event
oracle, or termination semantics requires a reviewed catalog revision.

The catalog loader validates strict JSON, portable archive paths, exact release
and asset identities, complete time lattices, event intervals, and cross-field
oracle invariants. Schema v2 owns a separate oracle for Co-Simulation and Model
Exchange because communication samples and solver-located roots are different
observations of the same FMU semantics. Asset validation reads one explicit
local `.fmu` once and
returns the exact immutable bytes whose size and SHA-256 match the selected
case. It does not download, extract, load, compile, or execute native code.

The maintained event evidence now covers three distinct mechanisms:

- the existing RMS prescribed input discontinuity;
- Stair time events, including Integer in FMI 2.0 and Int32 in FMI 3.0;
- BouncingBall state events, including the final zero velocity sustained from
  the last impact through the configured stop.

Stair ends because the FMU requests termination at 9 s. BouncingBall does not
request termination and instead reaches the configured stop at 3 s. Keeping
those causes separate prevents a matching final timestamp from concealing
different lifecycle behavior.

The FMU archives remain external evidence and are never committed by this
package. A caller obtains the exact upstream release separately and supplies
the selected file path to the validator. Loading the catalog or validating its
bytes is corpus-readiness evidence only: it is not an interoperability PASS,
platform-support claim, or FMI certification claim. Those conclusions require
the separately controlled execution and comparison runners.

## Reference FMU execution matrix

`run_reference_fmu_execution` executes exactly sixteen current-host Windows
x86_64 cells: four pinned Reference FMUs, both CS and ME interfaces, and both
FMPy and official `fmusim`. All inputs are explicit; the runner does not search
Git, `PATH`, environment variables, tools, or corpus files.

```text
python -m examples.fmi.run_reference_fmu_execution \
  --output-dir <new-package-directory> \
  --source-branch devel_dynamics_rebuild \
  --source-revision <40-character-commit> \
  --source-tree-sha256 <64-character-tree-digest> \
  --catalog-path <reference_fmu_catalog.json> \
  --corpus-root <extracted-Reference-FMUs-v0.0.41-root> \
  --fmpy-version 0.3.31 \
  --fmpy-distribution-sha256 39eb2d78370dd241001e5724734f79caf2afcaafc968ba8f93afc597a0337e85 \
  --fmusim-executable <absolute-path-to-fmusim.exe> \
  --fmusim-size-bytes 6743040 \
  --fmusim-sha256 e25529b1a52d441a2c9f284193ba135a418b66a5ef26cc82754bd479c98ba874 \
  --fmusim-version "fmusim 0.10.0"
```

Co-Simulation is accepted against the official CSV embedded in each FMU with
absolute and relative tolerances of `1e-9`. Model Exchange is accepted by
cross-checking FMPy and fmusim at `1e-6`, while each raw event trace must also
satisfy its independent catalog oracle. BouncingBall ME therefore validates
eleven analytically bounded state-event roots. Stair ME validates eight visible
counter transitions and the ninth termination boundary; the semantic counter
reaches 10, but public output ends with 9 before the terminating event can
serialize the new value.

The runner retains all raw rows, including duplicate or native event rows. Its
regular views select existing samples only: they never insert, interpolate, or
synthesize data. A successful run atomically publishes `manifest.json` and 32
artifacts under `raw/cell-00` through `raw/cell-15`: one `trace.csv` per cell,
plus `stdout.log` and `stderr.log` for each fmusim process. Runtime FMU and tool
copies are removed before publication. This package deliberately produces no
plots.

The resulting package is evidence only for execution of the exact Reference
FMUs v0.0.41 with FMPy 0.3.31 and fmusim 0.10.0 on the recorded host. It is not
evidence of VeraGrid runtime behavior, FMI 1 support, another operating system,
multiplatform support, or FMI certification.

## VDMCheck static validation matrix

`run_vdmcheck_validation` validates the same four authenticated Reference FMUs
once per file with two independent static validators: FMPy 0.3.31 and VDMCheck
1.1.3. Each FMU declares both Co-Simulation and Model Exchange, but static
validation is intentionally file-level rather than repeated per interface.

The caller supplies the complete JRE root, both complete version-specific
VDMCheck distribution roots, the Reference FMU corpus, and every expected tree
identity. The adapter derives `bin/java.exe`, `vdmcheck2.jar`, and
`vdmcheck3.jar` only inside authenticated roots. Each copied validator tree is
authenticated before and after every operation that can consume it. It never
searches `PATH`, reads environment variables, downloads tools, or retains a
runtime in the published package.

Each file validation uses VDMCheck's documented `-v` option with Python's
non-configurable `os.devnull` path. This prevents generated VDM source from
being written beside the staged JAR while preserving the exact validator
output. The version probe does not use `-v`, and every staged tree must remain
byte-identical before and after each Java process.

```text
python -m examples.fmi.run_vdmcheck_validation \
  --output-dir <new-package-directory> \
  --source-branch devel_dynamics_rebuild \
  --source-revision <40-character-commit> \
  --source-tree-sha256 <64-character-tree-digest> \
  --catalog-path <reference_fmu_catalog.json> \
  --corpus-root <extracted-Reference-FMUs-v0.0.41-root> \
  --fmpy-version 0.3.31 \
  --fmpy-distribution-sha256 39eb2d78370dd241001e5724734f79caf2afcaafc968ba8f93afc597a0337e85 \
  --java-runtime-root <authenticated-jre-root> \
  --java-runtime-file-count <files> \
  --java-runtime-size-bytes <bytes> \
  --java-runtime-tree-sha256 <lowercase-sha256> \
  --java-version <exact-runtime-version-line> \
  --vdmcheck-two-root <complete-vdmcheck2-distribution> \
  --vdmcheck-two-file-count 55 \
  --vdmcheck-two-size-bytes 3155146 \
  --vdmcheck-two-tree-sha256 36facab758b6c2f45de5cde45a93ddec02f5efc37eaaecb962eaad0ca925bd1f \
  --vdmcheck-two-version <exact-version> \
  --vdmcheck-three-root <complete-vdmcheck3-distribution> \
  --vdmcheck-three-file-count 56 \
  --vdmcheck-three-size-bytes 3760225 \
  --vdmcheck-three-tree-sha256 26c80b20d52febb7041aaf4bbd38767b1b9a76311a63e0ae20a97cd64606d2cc \
  --vdmcheck-three-version <exact-version> \
  --process-timeout-seconds 30 \
  --stream-limit-bytes 1048576
```

The current pinned corpus is expected to produce four FMPy PASS verdicts and
four VDMCheck FAIL verdicts containing five findings. That is a completed,
reproducible `COMPLETED_WITH_FINDINGS` result, not a rewritten PASS. Exit code
one is accepted as a validator result only when its native output follows the
exact documented finding grammar; timeouts, excessive output, identity drift,
unexpected exits, nonempty stderr, or malformed text abort publication.

The atomically published package contains one manifest and exactly eight raw
logs. Static XML validation has no numerical trajectory, so this lane correctly
produces no figure. Event and overlaid-trajectory PNG/PDF/SVG evidence belongs
to the Reference FMU execution and SMIB comparison packages described above.
This result is not FMI certification, VeraGrid runtime evidence, FMI 1 evidence,
or multiplatform evidence.

## libcosim composed co-simulation

`run_libcosim_comparison` executes the authenticated Linux libcosim command-line
bundle through an explicitly identified WSL distribution. It composes the SMIB
plant and governor FMUs with a delayed feedback connection, runs the native
master from 0.0 s through 4.0 s with a 0.002 s communication step, and compares
the resulting 2,001-row trajectory against the sealed VeraGrid reference.

The scenario contains two related network-reactance events: the fault is applied
at 1.001 s and cleared at 1.151 s. The comparison covers rotor angle, speed,
electrical power, effective reactance, plant mechanical input, controller speed
input, and controller action. Passing requires exact event-boundary values and
agreement of all 14,007 signal values after six-significant-digit
serialization; it also reports maximum and RMS absolute errors without using
interpolation or synthetic samples.

```text
python -m examples.fmi.run_libcosim_comparison \
  --output-dir <new-package-directory> \
  --source-branch devel_dynamics_rebuild \
  --source-revision <40-character-commit> \
  --source-tree-sha256 <64-character-tree-digest> \
  --wsl-executable <absolute-path-to-wsl.exe> \
  --wsl-executable-size-bytes <bytes> \
  --wsl-executable-sha256 <lowercase-sha256> \
  --wsl-version <exact-version> \
  --wsl-distribution <distribution-name> \
  --wsl-distribution-pretty-name <exact-pretty-name> \
  --wsl-distribution-version-id <exact-version-id> \
  --wsl-architecture <exact-architecture> \
  --wsl-kernel <exact-kernel> \
  --wsl-glibc-version <exact-glibc-version> \
  --libcosim-bundle <authenticated-zip> \
  --libcosim-bundle-size-bytes <bytes> \
  --libcosim-bundle-sha256 <lowercase-sha256> \
  --cosim-version <exact-cli-version> \
  --libcosim-version <exact-library-version> \
  --reference-manifest <sealed-reference-manifest> \
  --reference-manifest-size-bytes <bytes> \
  --reference-manifest-sha256 <lowercase-sha256> \
  --plant-fmu <authenticated-plant-fmu> \
  --plant-fmu-size-bytes <bytes> \
  --plant-fmu-sha256 <lowercase-sha256> \
  --governor-fmu <authenticated-governor-fmu> \
  --governor-fmu-size-bytes <bytes> \
  --governor-fmu-sha256 <lowercase-sha256> \
  --process-timeout-seconds <positive-seconds> \
  --stream-limit-bytes <positive-byte-limit>
```

The runner does not search `PATH`, read environment variables, download tools,
or publish runtime binaries. It verifies the WSL host, the complete extracted
libcosim tree, both FMUs, and the reference evidence before and after native
execution. A successful run atomically publishes exactly fifteen files: the two
native input documents, four process logs, four canonical native result files,
the copied VeraGrid reference CSV, three scientific figures, and `manifest.json`.

This lane proves the recorded FMI 2.0 Co-Simulation composition on the recorded
Windows/WSL host with the authenticated libcosim distribution. It is not by
itself FMI certification, FMI 1 or FMI 3 evidence, Model Exchange evidence, or
proof of another operating system.

## FMI.jl independent runtime comparison

`run_fmi_jl_comparison` executes the same authenticated SMIB plant and governor
FMUs with FMI.jl 0.15.2 on Julia 1.12.6. FMI.jl is used here as an independent
low-level FMI runtime, not presented as a native composition master. The small
Julia runner performs explicit Jacobi boundary exchange between the two FMUs;
the Python adapter owns authentication, process bounds, comparison, figures and
atomic evidence publication.

The Julia project and complete package resolution are pinned by `Project.toml`
and `Manifest.toml`. Before execution, the adapter authenticates the WSL host,
its Python interpreter, the Julia archive and runtime tree, and the complete
FMI.jl source depot. It then creates a private depot copy with write permission
removed from every entry, rejects symlinks that escape that copy, and places a
new writable overlay in front of it. Julia runs through `/usr/bin/env -i` with
absolute paths, the isolated depot pair and precompilation disabled. The shared
source depot is never exposed to Julia and is authenticated again after the run;
the private workspace is removed on success and on handled failure. This avoids
host-environment discovery, package installation and mutation of shared inputs.

```text
python -m examples.fmi.run_fmi_jl_comparison \
  --output-dir <new-package-directory> \
  --source-branch devel_dynamics_rebuild \
  --source-revision <40-character-commit> \
  --source-tree-sha256 <64-character-tree-digest> \
  --wsl-executable <absolute-path-to-wsl.exe> \
  --wsl-executable-size-bytes <bytes> \
  --wsl-executable-sha256 <lowercase-sha256> \
  --wsl-distribution Ubuntu \
  --wsl-version 2.6.3.0 \
  --wsl-distribution-pretty-name "Ubuntu 24.04.4 LTS" \
  --wsl-distribution-version-id 24.04 \
  --wsl-architecture x86_64 \
  --wsl-kernel 6.6.87.2-microsoft-standard-WSL2 \
  --wsl-glibc-version 2.39 \
  --wsl-python-executable <absolute-wsl-unc-python-path> \
  --wsl-python-executable-size-bytes <bytes> \
  --wsl-python-executable-sha256 <lowercase-sha256> \
  --wsl-python-version 3.12.3 \
  --julia-archive <authenticated-julia-release-archive> \
  --julia-archive-size-bytes <bytes> \
  --julia-archive-sha256 <lowercase-sha256> \
  --julia-executable <absolute-wsl-unc-path> \
  --julia-executable-size-bytes <bytes> \
  --julia-executable-sha256 <lowercase-sha256> \
  --julia-runtime-entry-count <entries> \
  --julia-runtime-regular-bytes <bytes> \
  --julia-runtime-tree-sha256 <lowercase-sha256> \
  --julia-project <absolute-wsl-unc-project-path> \
  --julia-project-size-bytes <bytes> \
  --julia-project-sha256 <lowercase-sha256> \
  --julia-manifest <absolute-wsl-unc-manifest-path> \
  --julia-manifest-size-bytes <bytes> \
  --julia-manifest-sha256 <lowercase-sha256> \
  --julia-depot <absolute-wsl-unc-depot-path> \
  --julia-depot-entry-count <entries> \
  --julia-depot-regular-bytes <bytes> \
  --julia-depot-tree-sha256 <lowercase-sha256> \
  --wsl-home <absolute-linux-home> \
  --julia-version 1.12.6 \
  --fmi-jl-version 0.15.2 \
  --runner <fmi_jl_runner.jl> \
  --runner-size-bytes <bytes> \
  --runner-sha256 <lowercase-sha256> \
  --plant-fmu <authenticated-plant-fmu> \
  --plant-fmu-size-bytes <bytes> \
  --plant-fmu-sha256 <lowercase-sha256> \
  --governor-fmu <authenticated-governor-fmu> \
  --governor-fmu-size-bytes <bytes> \
  --governor-fmu-sha256 <lowercase-sha256> \
  --reference-manifest <sealed-reference-manifest> \
  --reference-manifest-size-bytes <bytes> \
  --reference-manifest-sha256 <lowercase-sha256> \
  --process-timeout-seconds 120 \
  --stream-limit-bytes 1048576
```

Passing requires exact fault-insertion and fault-clearing boundary samples plus
agreement with VeraGrid for all 14,007 values at an absolute tolerance of
`1e-12`. The verified package contains exactly nine files: the Julia runner,
three process/trajectory logs, the copied VeraGrid trace, three scientific
figure formats, and `manifest.json`. The figures overlay rotor angle, speed,
electrical power and governor command so the event response is directly visible.

This lane proves the recorded FMI 2.0 Co-Simulation runtime behavior only. It
does not claim FMI.jl composition-master conformance, FMI 1.0, FMI 3.0, Model
Exchange, another operating system, or FMI certification.

## PathSim-FMI orchestration comparison

`run_pathsim_comparison` executes the authenticated Reference FMUs v0.0.41
BouncingBall and Stair cases through PathSim 0.25.0 and PathSim-FMI 0.1.1. The
matrix attempts FMI 2.0 and 3.0, Co-Simulation and Model Exchange, with both a
state-event and a time-event family. PathSim-FMI is FMPy-backed, so this lane
measures high-level orchestration behavior and does not count as an independent
low-level FMI runtime.

Each of the eight cells runs in a fresh Python 3.11.9 process with an absolute
interpreter, `-B -I`, no shell and a child environment limited to
`PROCESSOR_ARCHITECTURE`, `SystemRoot`, `TEMP` and `TMP`. The architecture is
explicitly fixed to `AMD64`; no inherited `PATH`, `PYTHONPATH` or user state is
available to the worker. The runtime tree, interpreter, catalog, release archive, FMU,
accepted FMPy trace and staged worker are authenticated around execution. Model
Exchange follows the upstream RKBS32 example with `dt=dt_max=0.01`, relative
tolerance `1e-6`, absolute tolerance `1e-9` and event tolerance `1e-10`.

```text
python -m examples.fmi.run_pathsim_comparison \
  --output <new-package-directory> \
  --source-branch devel_dynamics_rebuild \
  --source-revision <40-character-commit> \
  --source-tree-sha256 <64-character-tree-digest> \
  --runtime-root <authenticated-python-environment> \
  --python <authenticated-python.exe> \
  --system-root <absolute-windows-system-root> \
  --processor-architecture AMD64 \
  --catalog <reference_fmu_catalog.json> \
  --archive <Reference-FMUs.zip> \
  --fmi2-bouncing-ball <authenticated-fmu> \
  --fmi2-stair <authenticated-fmu> \
  --fmi3-bouncing-ball <authenticated-fmu> \
  --fmi3-stair <authenticated-fmu> \
  --reference-manifest <accepted-reference-execution-manifest>
```

The expected result is deliberately `COMPLETED_WITH_FINDINGS`: all four
BouncingBall cells must pass their state-event and trajectory oracles, while
the four Stair cells retain PathSim-FMI 0.1.1's current Integer/Int32 output
limitation (`fmi2GetReal` or `fmi3GetFloat64`, status 3). The runner never
patches the external tool or substitutes an easier FMU. It publishes exactly
35 files, including raw results and logs, successful traces, a four-panel
PathSim/FMPy overlay, a complete capability matrix and a closed manifest. This
is interoperability evidence, not FMI certification.

## FMUGym orchestration comparison

`run_fmugym_comparison` evaluates FMUGym 0.2.0 as an FMPy-backed Gymnasium
wrapper. The FMI 2.0 cell runs the dynamic SMIB plant through mechanical-input
changes and two network events; the FMI 3.0 cell runs the Reference FMUs
Feedthrough model with a sinusoidal action. A direct FMPy process repeats the
same action and actual communication-time sequence for each case. FMUGym's
single-precision observations must equal the exact `float32` projection of the
direct result, while the native difference remains within four single-precision
rounding units.

Every engine/case cell runs in a fresh Python 3.11.9 process with `-B -I`, no
shell, and only `PROCESSOR_ARCHITECTURE`, `SystemRoot`, `TEMP` and `TMP` in the
child environment. The complete external runtime, FMUGym wheel, interpreter,
FMUs and staged worker are authenticated before use. Python is derived from the
authenticated runtime root rather than discovered through `PATH`.

```text
python -m examples.fmi.run_fmugym_comparison \
  --output <new-package-directory> \
  --source-branch devel_dynamics_rebuild \
  --source-revision <40-character-commit> \
  --source-tree-sha256 <64-character-tree-digest> \
  --runtime-root <authenticated-fmugym-environment> \
  --wheel <authenticated-fmugym-wheel> \
  --system-root <absolute-windows-system-root> \
  --processor-architecture AMD64 \
  --fmi2-smib <authenticated-smib-fmu> \
  --fmi3-feedthrough <authenticated-feedthrough-fmu>
```

The package status is `COMPLETED_WITH_FINDINGS` even when both numerical cells
pass. FMUGym accumulates binary floating-point time, checks the finite horizon
before the step, resets after the horizon is exceeded, and still advances in
the terminating call. The manifest retains this behavior and the measured
drift from the ideal lattice instead of rewriting external runtime state. The
closed package contains exactly 20 files: four run directories with a result,
trace and two process logs, one scientific figure in PNG, SVG and PDF, and one
manifest. This lane demonstrates Windows AMD64 FMI 2.0 and 3.0 Co-Simulation
wrapper interoperability; it is not an independent solver, Model Exchange,
multiplatform, or FMI certification claim.
## train_fmu_gym learning comparison

`run_train_fmu_gym_comparison` evaluates the official DLR
`train_fmu_gym` 0.8.1 environments with their packaged FMI 2.0 and FMI 3.0
Co-Simulation FMUs. Two isolated direct-core cells train Stable Baselines3 A2C
for 128 steps and evaluate it for 256 deterministic steps with seed 938. The
oracle requires all 739 policy parameters, finite observations, actions and
rewards, and a non-zero parameter change. Two additional cells exercise the
public `tfg train` path without patching upstream behavior.

The accepted package retains four worker results and logs, the two successful
evaluation traces, one manifest, and a 7.2 by 6.0 inch scientific figure in
PNG, SVG and PDF. Its current status is `COMPLETED_WITH_FINDINGS`: the public
CLI launches a child interpreter that is not bound to the selected environment
and does not propagate that child's `ModuleNotFoundError`, despite returning
zero. The direct training core passes for both FMI versions. This proves
CS-backed A2C training on the recorded Windows runtime, not CLI completion,
solver independence, multiplatform support or certification.

## EnergyPlusToFMU export comparison

`run_energyplus_to_fmu_comparison` starts from the official EnergyPlusToFMU
3.1.0 source and reproduces the EnergyPlus 9.4 Schedule model as one Windows
x86_64 FMI 1.0 Co-Simulation FMU. The authenticated compatibility patch removes
one invalid RunPeriod access and uses the numeric IPv4 loopback address for the
local EnergyPlus socket. The patch does not change the model equations or the
FMI interface. The runner starts from an explicit minimal environment, calls
the authenticated `VsDevCmd.bat`, rejects environment keys outside its
allowlist, resolves the selected `cl.exe` and `link.exe`, and runs the derived
exporter in an isolated process. Archive inspection rejects path traversal and
requires exactly seven members, including the declared EPW weather resource,
input `Q`, output `TRooMea`, and zero FMPy 0.3.31 static findings.

Runtime instantiation is a separate worker. It calls FMI 1
`fmiInstantiateSlave` first and stops immediately on a null component; no
initialize, set, get or step call may follow a failed instantiation. The PASS
oracle requires a complete 24-hour trajectory with 96 communication steps,
four heat-flow plateaus, three transitions, finite output and a non-zero zone
temperature response. The package verifier reopens the raw trace, recomputes
its statistics and regenerates byte-identical PNG, SVG and PDF figures. No
partial cell can be published as PASS. The EnergyPlus 9.4 executable and build
toolchain are authenticated external prerequisites and are never copied into
VeraGrid or into the evidence package. This lane proves the recorded Windows
FMI 1.0 CS path; it does not claim unmodified-upstream runtime, certification,
multiplatform support or numerical equivalence with VeraGrid.

## Simulink first-order commercial replay

`simulink_first_order` owns the maintained licensed Simulink replay for the
normalized first-order fixture across FMI 1.0, 2.0, and 3.0, Co-Simulation and
Model Exchange. Its Python and MATLAB recipes are tracked here; every FMU,
Simulink model, trace, receipt, and figure is generated in a caller-selected
external directory. See `simulink_first_order/README.md` for the authenticated
end-to-end procedure and the distinction between historical lineage and a
fresh replay.
## Standard electrical examples in licensed Simulink

The [18-cell standard-example catalog and replay recipe](veragrid_standard_examples/SIMULINK_VALIDATION.md)
extends the retained first-order commercial evidence with GENSAL, TGOV1 and
ESDC2A. Its version/interface variants are distinct cells, not distinct model
families. The published FMUs, `_in.csv`, `_ref.csv`, manifest, hash list,
builder, runner, validator and plotter all live under
`examples/fmi/veragrid_standard_examples`. Generated MATLAB
models and execution evidence belong outside Git. The authenticated R2025b
Update 1 replay passed 18/18 licensed cells, with a maximum pointwise wave
error of 0.002880763429 against the 0.005 limit and 12 trajectory/error plots
in both PNG and PDF. See the recipe for the exact acceptance and evidence
boundary; this is not an official FMI certification claim.
