# EMT fault

<!-- veragrid-block-introduction:start -->
**EMT fault** inserts a switchable low-impedance path at an internal node of a
composed EMT branch model. Its algebraic equations preserve the series voltage
path and split the through current from the selected fault current.

## Typical use

- Insert it inside an EMT line or other explicitly composed branch model.
- Select a phase mask consistent with the requested fault topology.
- Keep all resistance and conductance settings on the parent EMT per-unit base.
<!-- veragrid-block-introduction:end -->

The **EMT fault** is an internal branch-composition block for inserting a
switchable low-impedance path at a three-phase EMT node. It is available from
the dynamic editor library under **Faults** only while the editor is in EMT
mode. It is not an RMS model and it is not mapped directly to a network device;
it must be wired inside a parent EMT branch model, such as a line composition.

## Supported topologies

| Topology | Required phases | Electrical representation |
| --- | --- | --- |
| `LG` | Exactly one of A, B or C | Selected phase to ground through `fault_rg` |
| `LL` | Exactly two phases | One phase-to-phase path through `fault_r` |
| `LLG` | Exactly two phases | Each phase to a common node through `fault_r`, then the node to ground through `fault_rg` |
| `LLL` | A, B and C | Three equal paths through `fault_r` to one floating common node |
| `LLLG` | A, B and C | Each phase independently to ground through `fault_rg` |

An invalid phase/topology combination is rejected when the template is built.

## Series-insertion interface

For every selected phase `X`, the block exposes four ports:

| Direction | Port | Meaning | Units |
| --- | --- | --- | --- |
| Input | `v_outer_X` | Voltage arriving from the outer/upstream segment | p.u. |
| Input | `i_inner_X` | Current arriving from the inner/downstream segment | p.u. |
| Output | `v_inner_X` | Voltage passed to the inner/downstream segment | p.u. |
| Output | `i_outer_X` | Current returned to the outer/upstream segment | p.u. |

The block owns both equations needed at its split node:

$$
v_{inner,X} - v_{outer,X} = 0
$$

$$
i_{outer,X} - i_{inner,X} - i_{fault,X} = 0
$$

Consequently, the parent composition only connects these explicit ports; it
must not add a second voltage-continuity equation.

## Fault paths and switching

The binary mode `fault_closed_mode` selects the effective conductance. For a
phase path and a ground path respectively,

$$
G_f = m\frac{1}{R_f} + (1-m)G_{open}
$$

$$
G_g = m\frac{1}{R_g} + (1-m)G_{open}
$$

where `m` is `fault_closed_mode`, `R_f` is `fault_r`, `R_g` is `fault_rg`, and
`G_open` is `fault_open_g`. All resistance and conductance values are per-unit
on the parent EMT model base; the block performs no SI/base conversion.

For `LLG`, positive phase currents enter the common node and the ground current
leaves it, so the common-node equation is

$$
i_{AN} + i_{BN} - G_g v_N = 0.
$$

## Control and parameters

| Setting | Meaning | Units/default |
| --- | --- | --- |
| `initial_closed` | Initial value of `fault_closed_mode` | `False` |
| `fault_resistance` | Closed phase-path resistance `R_f` | `0.01 p.u.` |
| `ground_resistance` | Closed ground-path resistance `R_g` | `0.01 p.u.` |
| `open_conductance` | Leakage conductance while open | `1e-8 p.u.` |
| `signal_controlled` | Adds the `fault_cmd` input and sampled mode update | `False` |
| `command_threshold` | Fault closes when `fault_cmd >= threshold` | `0.5` |
| `fault_time_constant` | Saved compatibility parameter; not used by the present algebraic model | `1e-4 s` |

Resistances and the compatibility time constant must be finite and positive;
the open conductance must be finite and non-negative.

When signal control is disabled, events may change `fault_closed_mode`
directly. When it is enabled, the procedural logic samples `fault_cmd` and
writes the mode according to `command_threshold`.

## Placement side

`FromSide` and `ToSide` describe where the user intends to place the fault in a
composed branch. The setting is retained in the internal editor projection and
is restored after saving and reopening. It does not automatically discover or
rewire a neighbouring line block: the outer and inner ports remain explicit,
so the parent model author controls the actual connection.

The internal diagram mirrors the selected topology, including the series port
path, phase-to-phase link, floating common node, or grounded common node as
applicable.
