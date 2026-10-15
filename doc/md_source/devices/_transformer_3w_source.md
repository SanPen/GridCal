## Transformer3W

A `Transformer3W` retains three `Winding` branches connected to its existing internal
bus. ABC power flow compiles each branch into four 4-by-4 NABC admittance blocks,
using the same network assembly and solver as other three-phase branches.
The internal bus is a mathematical star-equivalent node, not a shared physical neutral.

### Sequence impedances and connections

The existing positive-sequence conversion from pairwise tests is unchanged.
On a common system base, the three equivalent leg impedances are
`zH = (zHM + zHL - zML)/2`, `zM = (zHM + zML - zHL)/2` and
`zL = (zHL + zML - zHM)/2`. Individual equivalent legs may have negative resistance
or reactance; they must not be clipped independently.

Set zero-sequence data in the existing `R0`/`X0` fields of each winding, or use
`Transformer3W.fill_zero_sequence(z12, z23, z31)` with pairwise complex impedances
in system p.u. These values are independent of the positive-sequence design data
and persist with the winding objects. Missing or near-zero required `Z0` produces
a diagnostic identifying the winding. It is not replaced with `Z1`.

For the passive transformer model, an unspecified negative-sequence impedance
uses `Z2 = Z1`, as in PowerFactory. Explicit finite `R2`/`X2` values on a winding
are used by ABC power flow.

The external connection is `conn_f`; the internal star is `conn_t` for the default
external-to-internal branch orientation. Grounded star carries zero-sequence
current. Floating star blocks it. Delta blocks external zero-sequence current
but retains its internal circulating path, including when the tertiary has no load.
`NeutralStar` with phase N included represents an explicit neutral terminal.
Older native DGS imports with the external connection stored at the internal end
are interpreted compatibly during compilation and DGS export.

Each winding's `vector_group_number` gives its terminal lag relative to the common
internal reference, in multiples of 30 degrees. Terminal-to-terminal displacements
are the differences between these clocks; negative sequence rotates oppositely.
Zero clocks introduce no additional displacement for star or delta windings.
Tap modules, tap phases and virtual voltage ratios remain separate.

This extension covers the leakage-star equivalent with star and delta windings.
It does not add a galvanic autotransformer model, zigzag winding primitives, or a
common zero-sequence magnetising branch. Existing positive-sequence treatment of
no-load losses is unchanged. An out-of-service winding removes its branch; a
disconnected delta that must remain physically present requires a separate model
of its internal circulating path.

### PowerFactory DGS

Export `TypTr3.uk0hm`, `uk0ml`, `uk0hl`, `ur0hm`, `ur0ml` and `ur0hl`, alongside
the existing winding ratings, connections and clocks. Percentages use the smaller
rating of each winding pair and are converted to the network power base before
forming the star equivalent. DGS export reconstructs these pairwise tests from
the winding `R0`/`X0` values. DGS has no independent negative-sequence test here;
the imported passive model uses `Z2 = Z1`.

See [DGS conversion assumptions](file_operations.md#dgs) for the export workflow.
