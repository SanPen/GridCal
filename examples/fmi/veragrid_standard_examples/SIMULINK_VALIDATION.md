# Simulink replay of the standard FMI examples

This recipe is for a Windows machine with licensed MATLAB/Simulink R2025b and
the FMU Import block. It consumes the 18 published `win64` FMUs (GENSAL,
TGOV1, ESDC2A; FMI 1/2/3; CS/ME). The repository owns the inputs, expected
outputs, scripts, and acceptance criteria. The generated Simulink models,
traces, receipts, and figures are evidence, not source files.

Run `prepare_simulink_matrix.py` from the repository checkout, specifying a
**nonexistent external output directory**. The receipt records the current Git
HEAD and any uncommitted or untracked comparison files; for a truly clean
checkout the catalog and scripts must first be published together. Transfer
the execution
bundle to the licensed Windows host. In MATLAB R2025b, set the current folder
to the bundle and run `build_simulink_matrix`, then `run_simulink_matrix`.
Return the entire bundle with its receipts and traces; do not edit CSVs.
Run `validate_simulink_matrix.py` and `plot_simulink_matrix.py` against that
bundle on a machine with Python, FMPy, NumPy, and Matplotlib. Keep the original
bundle, Git commit/tree identity, manifest and SHA256SUMS hashes, MATLAB
release/license receipt, and generated hashes together. The execution bundle
is deliberately outside Git and must not contain credentials or license files.

The 1 ms input lattice is right-continuous at every specified event. The
published FMPy reference is sampled at 10 ms. Validation requires an exact
10 ms lattice in the raw Simulink trace and compares each nonzero sample,
including the event sample, with the reference for the **same FMU and
interface**. Both maximum absolute error and error divided by
`max(1, reference peak-to-peak range)` must be at most 0.005. The raw `t=0`
difference is reported separately; the first `t=0.01` sample is gated. Within
each family/interface, FMI 1 and FMI 3 are additionally compared with FMI 2.
Event neighbours are reported but do not replace the event-sample gate.

The run also makes single-input pulses on each input. A channel is observable
only when its output response exceeds 0.01; distinct channel signatures must
be separated by more than 0.01 and the matched Simulink/FMPy discrepancy must
be at most 0.005 and half that separation. ESDC2A's `UPss`, `UUel`, and
`UsRef` are a structural equivalence class and are identified by exact FMU
mask labels and `PortNumber`, never by their response alone. A failed or
unmeasured channel is INCONCLUSIVE, not PASS.

All 18 cells must pass before claiming commercial interoperability. Missing
cells, mismatched hashes, skipped channels, malformed time grids, or absent
plots remain explicitly incomplete. This recipe does not certify an official
FMI tool listing or PowerFactory interoperability.

## Retained execution result

The authenticated R2025b Update 1 replay executed all 18 cells and passed all
pointwise, version-consistency and input-identification gates. The maximum
physical-wave absolute and normalized error was 0.002880763429 (limit 0.005),
the maximum pulse-signature discrepancy was 0.002831148144, the smallest
observable response was 0.01185778113, and the smallest required signature
separation was 0.01428571429. The external evidence bundle contains 18 raw
traces, per-input signatures, 18 comparison CSVs, model/run/validation
receipts, and 12 trajectory/error figures in both PNG and PDF (24 files).
