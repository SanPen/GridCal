# Local toolchain platform evidence

This document is the sole tracked summary of the local dependency-resolution
observation. It is deliberately separate from the FMI execution campaigns in
[`INTEROPERABILITY_STATUS.md`](INTEROPERABILITY_STATUS.md).

## Evidence layers

The repository keeps four claims separate:

1. **Dependency resolution** shows that the reviewed Python requirements can be
   resolved into platform-specific wheel inventories on a named CI revision.
2. **FMI execution** shows that named FMUs were imported or exported and their
   numerical behavior met a stated criterion in a named tool.
3. **Release-platform support** requires an approved release and packaging
   matrix; a green CI runner is not sufficient.
4. **Official certification or listing** requires the applicable external FMI
   process; no local result grants it.

## Observed local pipeline

Local Forgejo/Woodpecker pipeline 10, internal pipeline id 35, completed all
three observer workflows successfully on branch
`ci/fmi-fmu-validation-b2f397b9` at commit
`0e6148ec5cb5d571f5e045b02dcdcd20782b0fec`. Every platform receipt retained
the status `OBSERVED_NOT_APPROVED`.

This evidence applies only to that Forgejo commit. It does **not** demonstrate
that the observed source tree is equivalent to product base
`616ecd07939618bfb1dfea57246802136ea764fb` or to a later checkout.

| Platform | Workflow / observer step | Result | Receipt SHA-256 | Lock SHA-256 | Wheelhouse SHA-256 |
| --- | --- | --- | --- | --- | --- |
| Linux AMD64 | `local-linux` / 206 | success | `cc87db00ad3423fa17143ecc6beb7ef9c3e7446b4d8aee74c37236597f061e08` | `7d99759d9cdf2ce172cfa5212d9f9291d47fcb14ffb0b2cb1cf6a1d78f209d78` | `9e849bfccee1aba1f84123ab0393f95b237c0702f46a4b23b11e618ee6b6898b` |
| macOS | `local-macos` / 208 | success | `a3fe40b0abd825568457d56763e09e38f9ce8ee2c85af4de3232015968b36c40` | Not directly inspected | `b32d200d66af71c62fb9e420b886d9dfee484866fbcc6e6bf678cdfaca6217da` |
| Windows AMD64 | `local-windows` / 210 | success | `616483ac66de3aeecf6ce7ee2dd13449f77c82dfeafd38ad5bc122dc143d7f8c` | `91bd6ef276fba06d764e2a9cda4499ffbde9f6c1b215143b1adb174f0dbe8809` | `f2b566b43791f987d10e579c32d2d39ba690523666c042aa4bc4ccc0dfdd6e5e` |

The macOS step log has SHA-256
`c78f073df09cf49f79bd1b7c1a923428f67db708541c96e9825c6cd607dfe622`.
It records the successful observer command, receipt hash, wheelhouse hash and
status. The full receipt content was not directly inspected because it remains
owned by the `_erootsci` service account. That ACL was not weakened. Exporting
the complete macOS receipt through an authorized service channel remains a
non-blocking requirement for a final external evidence package.

The three platform configurations were observed with these SHA-256 identities:

- Linux AMD64: `2a356614ae34b9ef79e25f852a5a1f81755beff929a67b80b9e83f946fb7fac3`
- macOS: `09fd2605e9bc0a5b1a5f22c233a7f7fb49e4ce9c7f8cb31fc2ac9153d34c89ae`
- Windows AMD64: `0a7cd033c755639588004a2b7469dba4eae342ee00fa944ef6f9e5e20fe35edb`

## Limits

Pipeline 10 did not execute an FMU and is not numerical FMI interoperability
evidence. It does not approve a dependency, promise Windows, Linux or macOS
release packages, authorize FMU distribution, or confer official FMI
certification or tools-list acceptance. Local CI configuration, credentials,
service-owned raw receipts and host paths are intentionally not stored here.
