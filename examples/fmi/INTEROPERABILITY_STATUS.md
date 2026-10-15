# FMI interoperability status

This is the master inventory of FMI validation campaigns maintained by
VeraGrid. It separates executable recipes from authenticated executions and
distinguishes VeraGrid acting as exporter, importer, orchestrator or observer.
The detailed reproduction commands remain in [README.md](README.md) and the
linked subpackages.

## Status vocabulary

| Status | Meaning |
| --- | --- |
| `PASS` | Exact authenticated execution evidence is available in the stated evidence envelope. |
| `COMPLETED_WITH_FINDINGS` | The campaign completed and retained one or more limitations or failing cells. |

`Currency` is independent from status. `Historical lineage` identifies an
authenticated prior run that is not proof of a replay from the current
checkout. `Profile` separates standard FMUs from tool-specific compatibility
derivatives. A runner's presence alone never implies `PASS`.

## Master campaign table

| Campaign | Ecosystem | VeraGrid role / other tool role | FMI | Interface | Model or purpose | Status | Currency / profile | Evidence and limit |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| VDMCheck matrix | Open-source | FMPy and VDMCheck static validators | 2.0, 3.0 | CS, ME | Reference FMUs | `COMPLETED_WITH_FINDINGS` | Recorded / standard | [VDMCheck section](README.md#vdmcheck-static-validation-matrix): four FMPy passes, four VDMCheck failures and five retained findings. |
| PathSim-FMI orchestration | Open-source | PathSim-FMI/FMPy wrapper imports Reference FMUs | 2.0, 3.0 | CS, ME | BouncingBall and Stair | `COMPLETED_WITH_FINDINGS` | Recorded / standard | [PathSim section](README.md#pathsim-fmi-orchestration-comparison): four BouncingBall cells pass; four Stair cells retain Integer/Int32 output limitations. |
| FMUGym orchestration | Open-source | FMUGym/FMPy wrapper compared with direct FMPy | 2.0, 3.0 | CS | SMIB and Feedthrough | `COMPLETED_WITH_FINDINGS` | Recorded / standard | [FMUGym section](README.md#fmugym-orchestration-comparison): numerical cells pass; finite-horizon time behavior remains a finding. |
| train_fmu_gym | Open-source | Learning wrapper compared with direct core execution | 2.0, 3.0 | CS | Packaged learning environments | `COMPLETED_WITH_FINDINGS` | Recorded / standard | [train_fmu_gym section](README.md#train_fmu_gym-learning-comparison): direct core passes; public CLI child-interpreter behavior remains a finding. |
| Archived commercial-exporter importer cross-check | Commercial | Dymola, FMI Toolbox for MATLAB and MWorks exporters; VeraGrid importer | 2.0 | CS | Three pinned FMUs per exporter | `COMPLETED_WITH_FINDINGS` | Authenticated local replay / win64 | [`importer_cross_check.py`](importer_cross_check.py) executed all nine hash-pinned FMUs through VeraGrid: Dymola 2019FD01 3/3 PASS, FMI Toolbox for MATLAB 2.3 3/3 PASS, and MWorks 2021 2/3 PASS. MWorks BouncingBall executed but its pinned FMU starts `y=10` while its pinned reference starts `y=20`; direct FMPy reproduces the same comparator rejection. Receipt SHA-256 `028dbc3b8f570d4d5deae341c06b39f3f60f3e109dddeb9825410df835eac94b`; manifest and reproduction command are documented in [README.md](README.md#commercial-exporter-importer-cross-check). |
| Simulink commercial replay | Commercial | VeraGrid exporter; Simulink importer | 1.0, 2.0, 3.0 | CS, ME | Normalized first-order fixture | `PASS` | Historical lineage / standard | [`validated_run.json`](simulink_first_order/validated_run.json) records 6/6 cells under MATLAB/Simulink R2025b Update 1. It explicitly is not a current-checkout replay. |
| PowerFactory commercial replay | Commercial | VeraGrid exporter; PowerFactory importer | 2.0, 3.0 | CS, ME | Normalized first-order fixture | `PASS` | Retained authenticated replay / standard plus PF-specific FMI 3 derivative | [PowerFactory recipe](powerfactory_first_order/README.md). FMI 2 uses standard FMUs. The unmodified FMI 3 archives failed `ComInc`; the passing FMI 3 cells use documented PowerFactory-specific derivatives. FMI 1 is `NOT_APPLICABLE` for PowerFactory 2025 SP4. |
| Six-cell local generation | Open-source toolchain | VeraGrid exporter; local FMPy execution | 1.0, 2.0, 3.0 | CS, ME | Normalized first-order fixture | `PASS` | Authenticated commit `95a156461`; standard | External manifest SHA-256 `67a5cc0bfac3b1d6b9ec2db85c32451990f3d7b5918233b64792e41e42b0c798`; 6/6 cells passed. This is not a new licensed replay. |
| Standard electrical example catalog | Open-source toolchain | VeraGrid exporter; local FMPy execution | 1.0, 2.0, 3.0 | CS, ME | GENSAL, TGOV1, ESDC2A — three distinct physical families | `PASS` | Committed in `e47b0b537`; win64 standard | [Catalog manifest](veragrid_standard_examples/published/win64/manifest.json) and [recipe](veragrid_standard_examples/generate_standard_examples.py): 18/18 local cells, phase-aware pointwise comparisons, 94/94 file hashes and MPL/source notices verified. The exact catalog was subsequently executed by Simulink and its twelve applicable FMI 2/3 cells by PowerFactory. |
| Standard electrical Simulink replay | Commercial | VeraGrid exporter; licensed Simulink importer | 1.0, 2.0, 3.0 | CS, ME | GENSAL, TGOV1, ESDC2A | `PASS` | Authenticated R2025b Update 1 replay / current worktree recipe | [Reproducible R2025b harness](veragrid_standard_examples/SIMULINK_VALIDATION.md) executed the exact 18 win64 hashes: 18/18 pointwise cells and all channel-identification gates passed. Maximum physical-wave absolute/normalized error was 0.002880763429; maximum signature error 0.002831148144; minimum observable response 0.01185778113; minimum required separation 0.01428571429. Generated external evidence contains the build/run/validation receipts, 18 comparison CSVs and 12 PNG plus 12 PDF figures. |
| Standard electrical PowerFactory import | Commercial | VeraGrid exporter; licensed PowerFactory importer | 2.0, 3.0 | CS, ME | GENSAL, TGOV1, ESDC2A | `PASS` | Authenticated PowerFactory 2025 SP4 replay / exact canonical hashes plus bounded importer-only derivatives | [Reproducible PowerFactory harness](veragrid_standard_examples/POWERFACTORY_VALIDATION.md) completed 24/24 isolated jobs. All 12 applicable cells and all 6 FMI 2/3 same-interface consistency comparisons passed; 24 immutable-trace views and exactly 8 evidence-bound delayed input transitions were retained. Numerical receipt SHA-256 `1d4bd41c7cf37b561e98d65007d4e8b120ca97e169ac0d8400c4c826ac9cead9`; figure receipt SHA-256 `40dbba58a7abd8e5e4490f4508603d83864419c26b9deef85dd4d74eefc8d75a`. FMI 1 is not applicable in PowerFactory 2025 SP4. |
| Native operating-system execution | Local Woodpecker agents | VeraGrid exporter and FMPy execution on matching hosts | 1.0, 2.0, 3.0 | CS, ME | GENSAL, TGOV1, ESDC2A | `PASS` | Authenticated pipeline 64 / current commit `4cc5fabf8` | Windows 18/18, Linux 18/18 and macOS 18/18 passed, for 54/54 cells. Each host generated and executed its native artifact. macOS numerical digests differ from Windows/Linux while remaining inside the same acceptance gates, so no bit-identity claim is made. Evidence JSON SHA-256 `3c6a8d639a77c7fc148f9e21fe7f5881ef13426a15473ce5f7a9dc101b7bfe9b`. |

The two plotting entry points for Reference FMUs and VDMCheck are renderers,
not additional simulation campaigns, and are intentionally excluded from the
campaign count.

The locally executed exporter catalog now covers four distinct model families
when the prior normalized first-order fixture is included. Commercial exporter
evidence now covers all four families in licensed Simulink. PowerFactory
covers the three electrical families for all twelve applicable FMI 2/3 CS/ME
cells. The catalog and reproduction sources are committed in `e47b0b537`;
public example availability begins after CTO integration into the public
default branch.

## Native platform execution

Pipeline 64 closes the previously separate native-execution gate. On each of
Windows, Linux and macOS, the matching host generated and executed the complete
18-cell standard electrical matrix. The result supports the three operating-
system labels in the prospective tools entry. It does not mean that the
committed downloadable sample package contains all three binary variants, and
it does not establish cross-platform byte or numerical-digest identity.

Publishing additional Linux and macOS example archives is optional hardening.
It is not a remaining interoperability or tools-list admission blocker in the
current bounded scope.

## Separate dependency-resolution observation

The [local toolchain platform evidence](TOOLCHAIN_PLATFORM_EVIDENCE.md) records
a successful Windows, Linux, and macOS dependency-resolution observation from
local Forgejo/Woodpecker pipeline 10. It is intentionally not a row in the
campaign table: its status is `OBSERVED_NOT_APPROVED`, it is bound only to
Forgejo commit `0e6148ec5cb5d571f5e045b02dcdcd20782b0fec`, and it did not
execute an FMU. It therefore proves neither numerical FMI interoperability,
release-platform support, dependency approval, nor official certification or
tools-list acceptance.

## Repository qualification evidence

The campaign count is separate from the product regression suite. The retained
verification receipt for commit `95a156461` has SHA-256
`303121cba9e586c8de49e92a722404c93be802ce23fe91c3ef492d94f9a65f70`
and records:

- complete `src/tests/FMI`: 633 passed, 4 skipped, 0 failed;
- focused compiler lifecycle tests: 44 passed, 1 skipped, 0 failed;
- first-order FMI 1/2/3 CS/ME matrix: 6 passed, 0 failed;
- PowerFactory reproducibility recipe: 14 passed, 0 failed; and
- no new licensed Simulink or PowerFactory execution in that qualification run.

## What this proves

The Simulink and PowerFactory rows prove VeraGrid **exporter**
interoperability because those tools imported VeraGrid-generated FMUs. The
archived 3-by-3 row independently exercises VeraGrid as an **importer** with
FMUs exported by Dymola 2019FD01, FMI Toolbox for MATLAB 2.3, and MWorks 2021.
It records eight official comparison passes and retains the exact MWorks
BouncingBall source-reference inconsistency instead of promoting it to PASS.
Wrapper-based lanes remain labelled as such so they are not mistaken for
independent low-level FMI runtimes.

This inventory is engineering evidence, not an official FMI certification or
an entry in the FMI tools list.
