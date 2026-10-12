# Dynamic physical network contracts

RMS and EMT dynamic models contain two different kinds of connection:

- **signal connections** join visible block ports and carry controller,
  measurement, and command values;
- **physical connections** join devices to buses and determine which network
  balance equation owns each electrical contribution.

These connections must not be inferred from one another. A signal can be
copied, hidden, or routed through several controller blocks without changing
electrical topology. Conversely, a physical terminal can contribute to the
network even when its power or current is not exposed as a visible signal.

`MultiCircuit` is the only owner of physical topology. A canonical symbolic
`Block` declares *what* electrical quantity belongs to each named terminal,
while the RMS or EMT problem resolves that terminal to a bus from the assigned
VeraGrid device. Dynamic diagrams never create a second electrical graph.

## Declarative contract lifecycle

Physical declarations are stored in the block's `DynamicModelContract`. They
contain typed terminal and variable references, not copied expressions or
references to DGS parser objects. The lifecycle is:

1. Parse and validate the source representation.
2. Build the canonical VeraGrid `Block` as soon as source references permit.
3. Add typed physical declarations to that block.
4. Assign the block to a device in `MultiCircuit`.
5. Validate every declaration before changing a nodal balance.
6. Resolve terminal sides through the device's physical buses and assemble the
   contribution.

The contract is serialized as versioned declarative data. Loading is
fail-closed: missing, extra, mistyped, or incompatible fields are rejected.
Imported models are never persisted as generated Python code, and no parallel
import-stage model graph is retained.

## RMS terminal-power assembly

An `RmsTerminalPowerContribution` selects one of these terminal sides:

| Side | Device topology | Active reference | Reactive reference |
| --- | --- | --- | --- |
| `BUS` | one-terminal device bus | `P` | `Q` or none |
| `FROM` | branch `bus_from` | `Pf` | `Qf` or none |
| `TO` | branch `bus_to` | `Pt` | `Qt` or none |

For `FROM` and `TO`, positive P/Q means power flowing from the connected bus
into the device. The nodal injection is therefore the negative of the declared
value. `BUS` uses the injection convention: positive means power flowing from
the device into the network, so it enters the nodal balance unchanged.

A reactive reference is optional only where the terminal can be DC. Declaring
reactive power on a bus that topology identifies as DC is an error. The
assembler validates the complete device contract before mutating either the
active or reactive balance, preventing partial injection from an invalid
terminal.

### Vectorized RMS invariant

The fully vectorized problem compiles the representative member of each
symbolic equivalence class once. Every other member must declare the same
ordered terminal sides and P/Q references. Members contribute only their own
physical bus indices. Compiled row indices are recorded when their equations
are appended and are shared by residual and Jacobian evaluation.

A transient compatibility layout exists for old, contract-free version-1
models whose established external mappings are unambiguous. It is an in-memory
bridge, is never persisted, and must not be used to guess incomplete new
contracts.

## EMT terminal-current assembly

An `EmtTerminalCurrentContribution` declares a terminal side, a conductor, and
the current reference owned by the canonical block.

| Terminal side | Physical owner | Nodal sign |
| --- | --- | --- |
| `BUS` | one-terminal device bus | positive device injection |
| `FROM` | branch `bus_from` | negative branch current |
| `TO` | branch `bus_to` | negative branch current |

The supported conductors are `DC`, `NEUTRAL`, `PHASE_A`, `PHASE_B`, and
`PHASE_C`. A DC conductor can connect only to a DC bus shell. Neutral and phase
conductors can connect only to an AC NABC shell. The current reference must
also match its conductor (`Idc`/`If_dc`/`It_dc`, or the corresponding N/A/B/C
reference). All declarations are resolved and validated before the first KCL
entry changes.

Grounding inside a composite EMT model is declarative. A child marked with
`emt_internal_grounding_link` closes the model's internal neutral-to-ground
equation and is not assembled as an independent `MultiCircuit` terminal.
Legacy migration recognizes only the established grounding-link structure;
ambiguous blocks remain invalid instead of being classified by a name alone.

## Physical RMS measurements

An `RmsPhysicalMeasurementPoint` records a meter's exact identity and
selection metadata:

- source FID of the native meter or built-in measurement slot;
- target FID of the measured VeraGrid bus or device;
- typed terminal side;
- quantity kind (`VOLTAGE`, `CURRENT`, `POWER`, or
  `PHASE_LOCKED_LOOP`);
- ordered output signal names and their canonical variable UIDs.

The solved expressions remain owned by the meter `Block`. This lets runtime
code index measurements without retaining the DGS parser graph or duplicating
symbolic variables.

PowerFactory terminal ordinals are interpreted against the exact target type:

| Target | DGS ordinal | VeraGrid side |
| --- | --- | --- |
| one-terminal device | `0` | `BUS` |
| ordinary branch | `0` | `FROM` |
| ordinary branch | `1` | `TO` |
| `ElmVsc` | `0` | `TO` (AC terminal) |

Any other ordinal is invalid. Import does not silently redirect it to another
terminal. Voltage and PLL measurements must target a bus. Current and power
meters must resolve an exact device terminal, including the special retained
series-branch resolution used when PowerFactory omits a native valve row. An
ambiguous topology produces no fallback binding.

## Shared Cable System ownership for DC branches

Cable construction belongs to `UndergroundCableType` (**Cable**). Installation
geometry and equivalent parameters belong to `UndergroundLineType` (**Cable
System**), shared by AC `Line` and DC `DcLine`. `DcLine` owns its installed length,
selected `dc_conductor` and applied system reference.

For physical systems, DC resistance comes from the selected core's active DC
resistance representation. L/C come from the diagonal of the existing reduced
Z/Y matrices at the system's reference frequency. This is a scalar equivalent;
mutual coupling between DC branches and a new sheath/return model are outside
this change. See [Applying Cable System to a DC line](modelling.md#applying-cable-system-to-a-dc-line).

DC DGS import still requires explicit, consistent cable classification and
complete R/X/C-or-B/frequency evidence. It preserves the former conversions
and stores a parameter-only Cable System without inventing geometry. `C` in
the shared catalogue uses µF/km; `get_dc_parameters()` supplies F/km and H/km.
`get_dc_values()` retains the former DC per-unit-seconds conversion.

Incomplete source types leave `DcLine` without a cable template. The existing
dynamic fallback reports missing data and may use a resistive reduction; it
does not persist unknown energy parameters as measured zeros. Existing RMS/EMT
model ownership and parameter mapping are unchanged by the catalogue merger.
Legacy DC catalogue records migrate before reference resolution, preserving
identifiers and dynamic associations. New files contain the common catalogue.

## DGS VSC ownership

For an imported VSC, DC active power belongs to `FROM`/`Pf`; AC active and
reactive power belong to `TO`/`Pt` and `TO`/`Qt`. The converter's physical
contract makes those quantities available to the RMS nodal assembler even
when P/Q are hidden from visible signal ports. Hiding them prevents accidental
controller wiring from becoming network ownership; it does not remove the
variables from the model's external mapping.

The DGS adapter binds topology and equipment parameters to one device-specific
copy of the template. Operating-point P/Q/current values come from the solved
power flow before explicit initialization. Imported `m:*` snapshots can
validate the reconstructed state, but they are not an alternative initializer.

## Validation checklist

When adding or importing a physical dynamic model, verify that:

- every network contribution has one typed declaration;
- every declaration references a variable owned by the same canonical block;
- terminal sides agree with the assigned device topology;
- DC and AC quantities are not mixed;
- equivalent vectorized instances declare the same ordered contract;
- visible ports contain only intended signal interfaces;
- meter source and target FIDs are exact and output names pair one-to-one with
  output UIDs;
- invalid or ambiguous topology fails before nodal balances are mutated;
- serialization round-trips the declarative contract without parser objects or
  generated source code.

These invariants keep scalar, vectorized, imported, and persisted models on the
same physical interpretation.
