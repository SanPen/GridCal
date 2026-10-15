# VeraGrid FMI tools-page publication candidate

This vendor-maintained compatibility view is ready for CTO integration in
preparation for a future VeraGrid entry in the FMI tools list. It is **not** an
official FMI certification or an accepted tools-list entry. The
machine-readable status is `READY_FOR_CTO_INTEGRATION`; the selected public
location becomes active only after this tree is integrated into the public
default branch.

The vendor identity is confirmed as **eRoots Analytics**. The public tool URL
is `https://github.com/SanPen/VeraGrid`, and the public vendor URL is
`https://eroots.tech/`. The candidate includes the official eRoots Analytics
logo, whose display was explicitly authorized. A later pull request still
requires separate explicit authorization.

## Proposed tool entry

[`tools-list-entry.candidate.json`](tools-list-entry.candidate.json) contains
only fields accepted by the pinned upstream `tools.json` format. Its
`examplesURL` selects the durable `examples/fmi` location on the public default
branch; URL activation remains gated on CTO integration. The confirmed platform
labels are `macOS`, `Linux`, and `Windows`, matching the values documented by
the pinned upstream guide. VeraGrid itself is an open-source project under
MPL-2.0; source availability is stated here rather than encoded as a platform.

The candidate references [`eroots-analytics.svg`](eroots-analytics.svg), the
official full-colour eRoots Analytics mark.

The final local Woodpecker campaign at commit
`4cc5fabf8891e41f96f2124419e63d2ba06e7955` generated, executed, and attested
all 18 FMI 1/2/3 CS/ME cells independently on Windows, Linux, and macOS:
54/54 cells passed. The macOS numerical digest is not identical to the other
hosts, so this is an execution-equivalence result, not a cross-platform byte-
or digest-identity claim. The earlier
[`TOOLCHAIN_PLATFORM_EVIDENCE.md`](../../TOOLCHAIN_PLATFORM_EVIDENCE.md)
remains a dependency-resolution observation only.

## Published example binary coverage

The current 18 downloadable example FMUs contain `win64` binaries only and no
FMI `sources/` directory. VeraGrid's maintained source distribution is public,
but it is not represented as an extra platform value or as source embedded in
these archives. Matching-host native generation and execution have passed on
Windows, Linux, and macOS; publishing additional native example archives is
optional hardening, not a tools-list submission gate. The only unresolved gate
in [`submission-gates.json`](submission-gates.json) is activation of the stable
public `examplesURL` after integration.

## VeraGrid as an exporting tool

The canonical [`published/win64`](../published/win64/README.md) tree contains three physical model
families—GENSAL, TGOV1, and ESDC2A—each exported as FMI 1.0, 2.0, and 3.0 for
Co-Simulation and Model Exchange, for a total of 18 FMUs. Every FMU retains
the byte identity from the canonical catalog.

The exact FMUs were imported and simulated successfully by:

- MATLAB/Simulink R2025b Update 1: 18/18 FMI 1/2/3 CS/ME cells passed.
- DIgSILENT PowerFactory 2025 SP4: 12/12 applicable FMI 2/3 CS/ME cells
  passed; FMI 1.0 is not supported by that importer lane.
- FMPy in the canonical local preflight: 18/18 cells passed.

The reproduction recipes and numerical criteria are documented in
[`SIMULINK_VALIDATION.md`](../SIMULINK_VALIDATION.md) and
[`POWERFACTORY_VALIDATION.md`](../POWERFACTORY_VALIDATION.md). PowerFactory's
bounded importer-only FMI 3 derivatives are documented there and are not
silently represented as changes to the canonical FMUs.

## VeraGrid as an importing tool

The reproducible [commercial-exporter cross-check](../../README.md#commercial-exporter-importer-cross-check)
executes nine hash-pinned FMI 2.0 Co-Simulation win64 FMUs through VeraGrid:

- Dymola 2019FD01: MixtureGases, Rectifier, and fullRobot — 3/3 PASS.
- FMI Toolbox for MATLAB 2.3: Continuous, EmbeddedCode, and IntegrateSignal —
  3/3 PASS.
- MWorks 2021: MixtureGases and Rectifier pass; BouncingBall executes but is
  `COMPLETED_WITH_FINDINGS` because the pinned FMU starts `y=10` while its
  pinned reference starts `y=20`. Direct FMPy reproduces the same rejection.

The authenticated campaign receipt is retained with the reproducibility
evidence. The full [interoperability table](../../INTEROPERABILITY_STATUS.md) separates
this importer evidence from VeraGrid-exporter, wrapper, static-validation, and
native-platform campaigns. No 9/9 PASS, certification, or universal
compatibility claim is made.

## Provenance and reproducibility

`published/win64` is the single downloadable catalog. Its generator writes the
required `Readme.txt` files and quoted CSV headers directly, preserves repeated
event timestamps and numerical rows, records source provenance, and closes the
complete package with `SHA256SUMS`. No parallel publication tree is maintained.
