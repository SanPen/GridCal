## UndergroundCableType

An `UndergroundCableType` is a reusable construction for one single-core underground cable. It describes two conducting layers, the core and its metallic sheath, separated by main insulation and surrounded by outer insulation. It does not define a route, burial depth, circuit arrangement or line length. Those belong to an [underground cable system](modelling.md#undergroundlinetype) and its network line.

All construction inputs are scalars: core and sheath properties have separate fields. The catalogue tables display Python property names with spaces instead of underscores. Unless marked otherwise below, these fields are editable. Defaults describe an initial construction, not a validated manufacturer's cable or a calculated current rating.

### Identification and rating

| Python property | Description | Unit | Default | Meaning and role |
| --- | --- | --- | --- | --- |
| `name` | Catalogue name | — | `Underground cable` | Editable label used when selecting and positioning this construction. |
| `idtag` | Persistent identifier | — | Automatically generated | Identifies the object and its references; normally leave the generated identifier unchanged. |
| `code` | User code | — | Empty | Optional catalogue or equipment identifier; does not affect the calculation. |
| `comment` | User comment | — | Empty | Optional description or modelling notes; does not affect the calculation. |
| `nominal_voltage` | Rated cable voltage | kV | 1.0 | Editable catalogue rating; not an input to the geometric impedance/admittance calculation. Set the system voltage separately using `UndergroundLineType.Vnom`. |

### Dimensions

| Python property | Description | Unit | Default | Meaning and role |
| --- | --- | --- | --- | --- |
| `core_diameter` | Core outer diameter | mm | 10.0 | Outside diameter of the conducting core; used in the electrical geometry. |
| `core_internal_diameter` | Core inner diameter | mm | 0.0 | Stored and editable, but currently has no effect on the calculated matrices. The implemented core impedance model is solid-core; leave this value at zero. |
| `main_insulation_thickness` | Main insulation thickness | mm | 5.0 | Radial insulation thickness between the core surface and the inside of the metallic sheath. |
| `sheath_thickness` | Metallic sheath thickness | mm | 1.0 | Radial thickness of the conducting sheath, outside the main insulation. |
| `cable_diameter` | Overall cable diameter | mm | 30.0 | Outside diameter including the outer insulation; determines the outer insulation thickness. |

Outer insulation thickness is derived, not entered separately:

```text
outer thickness = (cable_diameter - core_diameter) / 2
                  - main_insulation_thickness - sheath_thickness
```

All quantities in this expression are in mm. The default dimensions give 4 mm of outer insulation. The main and outer insulation thicknesses must both be positive for a valid layered construction.

### Conducting materials and correction factors

Choose **resistance input** in either the **Cable** database table or the cable-system builder:

- **Resistivity and filling factor** (default): enter `core_resistivity`, `core_filling_factor`,
  `sheath_resistivity` and `sheath_filling_factor`. Both `core_dc_resistance` and `sheath_dc_resistance`
  are calculated, read-only results that update with the material inputs and geometry.
- **DC resistance**: enter positive `core_dc_resistance` and `sheath_dc_resistance` values in Ω/km at **20 °C**.
  All four resistivity/filling-factor fields are greyed out and cannot be edited. Their retained values are
  inactive; they are not additional constraints on the resistances or inputs to the calculation in this mode.

There is **one selector shared by the core and sheath**. Switching modes in either GUI table converts the
active inputs to preserve both resistances before further edits. Only the selected representation governs
the impedances of both conducting layers.

| Python property | Description | Unit | Default | Meaning and role |
| --- | --- | --- | --- | --- |
| `resistance_input` | Shared resistance input method | — | `Resistivity and filling factor` | `CableResistanceInput.Resistivity` or `CableResistanceInput.DcResistance`; selects the inputs for both core and sheath. |
| `core_resistivity` | Core material resistivity | μΩ·cm | 1.7241 | Resistivity at 20 °C; editable and used only in resistivity mode. |
| `sheath_resistivity` | Sheath material resistivity | μΩ·cm | 1.7241 | Resistivity at 20 °C; editable and used only in resistivity mode. |
| `core_filling_factor` | Core conducting filling factor | % | 100.0 | Editable and used only in resistivity mode. Percentage of the modelled core section occupied by conducting material; this is not a capacitance. |
| `sheath_filling_factor` | Sheath conducting filling factor | % | 100.0 | Editable and used only in resistivity mode. Conducting fraction of the annular sheath section. |
| `core_relative_permeability` | Core relative magnetic permeability | — | 1.0 | Dimensionless permeability relative to vacuum, used in the core internal impedance. |
| `sheath_relative_permeability` | Sheath relative magnetic permeability | — | 1.0 | Dimensionless permeability used in the sheath internal impedance. |
| `skin_effect_factor` | Core skin-effect factor | — | 1.0 | Factor used in the frequency-dependent core internal impedance calculation. |
| `core_dc_resistance` | Core DC resistance at 20 °C | Ω/km | ≈0.219519, derived | Calculated and read-only in resistivity mode; editable and used by the impedance calculation in DC resistance mode. |
| `sheath_dc_resistance` | Sheath DC resistance at 20 °C | Ω/km | Derived from material and geometry | Calculated and read-only in resistivity mode; editable and used by the tubular sheath impedance calculation in DC resistance mode. |
| `proximity_effect_factor` | Reference proximity-effect factor | — | 1.0 | Informational, read-only in the catalogue tables; not used by the current calculation. |

Use positive material resistivities and relative permeabilities. Filling factors are percentages, with physically meaningful values greater than zero and no greater than 100. There is no construction-temperature input: these material values are not automatically converted to another operating temperature by the geometric cable calculation.

For either conducting layer, using its geometric section $A$ in m², the two parameterisations are:

$$
R_{\mathrm{dc}}=\frac{1000\,\rho_{\mathrm{material}}}{A(C_f/100)}\quad[\Omega/\mathrm{km}],
\qquad
\rho_{\mathrm{effective}}=\frac{R_{\mathrm{dc}} A}{1000}\quad[\Omega\,\mathrm m].
$$

The core uses $A_c=\pi r_c^2$. The sheath uses its **annular** area $A_s=\pi(r_{so}^2-r_{si}^2)$,
where $r_{si}=d_c/2+t_i$ and $r_{so}=r_{si}+t_s$ (dimensions converted to metres).
The insulation and core are not part of the sheath's conducting section.

DC resistance mode supplies each layer's effective resistivity and a 100% effective filling factor to the
existing Bessel-function calculations. It therefore affects both the core and tubular sheath impedances,
including the resulting reduced system matrix. This does not infer a manufacturer's material or actual
packing fraction. The same geometry and electromagnetic model apply in both modes.

For direct resistance input through Python, select the mode explicitly:

```python
from VeraGridEngine.Devices.Branches.underground_cable_type import UndergroundCableType
from VeraGridEngine.enumerations import CableResistanceInput

cable = UndergroundCableType(
    name="Cable specified by resistance",
    core_diameter=10.0,
    resistance_input=CableResistanceInput.DcResistance,
    core_dc_resistance=0.25,  # Ohm/km at 20 degrees Celsius
    sheath_dc_resistance=0.8,
)
```

Setting either DC resistance alone does not select its mode. Supply both positive values when constructing
a cable with `resistance_input=CableResistanceInput.DcResistance`. The constructor and snapshot setters restore
the explicitly supplied inputs; GUI edits through `set_value()` additionally convert values when changing mode.
Native files store the single selector and both active resistances. Files without a selector, and current PowerFactory DGS
`TypCab` imports, use **Resistivity and filling factor**, preserving their previous impedance calculation.
An old imported `rpha` value is not a competing input in that mode: the displayed/saved resistance is derived
from the active material data. The PowerFactory input-method option shown in its UI is not part of the currently
mapped DGS cable fields.

The earlier `core_resistance_input` name is accepted as a compatibility alias, not a second selector.
Native JSON files saved with that core-only selector and no sheath resistance retain their core input and
derive the sheath resistance from the saved sheath materials and annular geometry during loading. They then
use the common selector. The old constructor keyword also derives an omitted sheath resistance from its
material inputs. New files and examples use `resistance_input` and explicit DC values for both layers.

### Insulation materials

| Python property | Description | Unit | Default | Meaning and role |
| --- | --- | --- | --- | --- |
| `main_insulation_permittivity` | Main insulation relative permittivity | — | 2.3 | Dimensionless dielectric permittivity between core and sheath; determines the main insulation capacitance. |
| `outer_insulation_permittivity` | Outer insulation relative permittivity | — | 2.5 | Dimensionless dielectric permittivity between the sheath and the cable exterior. |
| `main_insulation_loss_tangent` | Main insulation loss tangent | — | 0.0 | Dielectric loss tangent, tan δ, between core and sheath. Enter a fraction, not a percentage; zero represents lossless insulation. |
| `outer_insulation_loss_tangent` | Outer insulation loss tangent | — | 0.0 | Corresponding loss tangent for the outer insulation. |

The two outer-insulation material fields affect the primitive shunt matrix. With the implemented ideal-grounded-sheath reduction they do not affect the reduced core shunt matrix. See the [underground line model](modelling.md#underground-lines) for the matrix definitions and grounding assumptions.

### Supported scope and catalogue reuse

The construction model supports a solid core and one metallic sheath, not a third conducting layer such as armour or a separate additional screen. An unsupported layer must not be interpreted as another editable core or sheath parameter.

The GUI and Python API use the same construction objects. Editing a catalogue construction changes that shared object for every system referencing it; it does not create an independent copy. Recalculate each affected system and reapply its template to the affected network lines before solving. The cable builder recalculates the system currently being edited, but does not automatically update every other system that uses the same construction.

## UndergroundLineType

![img.png](img.png)An `UndergroundLineType` is a reusable underground line template. It can be defined either from positioned [cable constructions](modelling.md#undergroundcabletype), or directly from per-kilometre sequence parameters. Both AC `Line` and DC `DcLine` use this common **Cable System** catalogue. The branch supplies its buses and length; an AC line selects a circuit, and a DC line selects a conductor.

### System identification, environment and rating

| Python property | Description | Unit | Default | Meaning and role |
| --- | --- | --- | --- | --- |
| `name` | System name | — | `UndergroundLine` | Editable template name displayed in the catalogue and cable builder. |
| `idtag` | Persistent identifier | — | Automatically generated | Identifies the template and its references; normally leave unchanged. |
| `code` | User code | — | Empty | Optional inherited identifier; assign after construction if needed. It is not a constructor argument for this class. |
| `comment` | User comment | — | Empty | Optional description or installation notes; does not affect the calculation. |
| `Vnom` | System rated voltage | kV | 1.0 | System voltage rating, distinct from a construction's `nominal_voltage`. Used as the voltage base when no connected-bus voltage is supplied. |
| `Imax` | Rated current | kA | 1.0 | User-supplied current rating, not calculated from cable dimensions or soil data. AC application converts this to a power rating. DC application preserves the existing branch rating; set that rating in the DC line editor. |
| `freq` | Calculation frequency | Hz | 50.0 | Frequency used in physical impedance and admittance calculations and capacitance-to-susceptance conversion. |
| `earth_resistivity` | Earth resistivity | Ω·m | 100.0 | Soil resistivity for the earth-return impedance calculation; use a positive value. |
| `cables_in_system` | Physical composition | — | Empty | Collection of construction references and positions. Use the builder or `add_cable_relationship()` rather than editing this as a single table cell. |
| `n_circuits` | Number of circuits | — | 1 | Stored circuit count, recomputed from global phase numbers when a physical system is calculated. It is not an independent geometry input. |
| `capex` | Capital expenditure | currency/km | 0.0 | Optional economic data; does not change the electrical matrices. |
| `opex` | Operating expenditure | currency/MWh | 0.0 | Optional economic data; does not change the electrical matrices. |

The builder's top controls edit the system name, voltage, frequency, earth resistivity and rated current. Its construction table edits shared catalogue entries, while its composition table edits their positions and phase ordering.

### Positioned cable inputs

Each composition entry is a `CableInSystem` relationship, created through `system.add_cable_relationship(cable=..., xpos=..., ypos=..., phase=...)`.

| Python property | Builder column | Unit | API default | Meaning and role |
| --- | --- | --- | --- | --- |
| `cable` | Cable | — | Required | Reference to an `UndergroundCableType`, not a copy of its parameters. Select a catalogue row and press `+` to add it in the builder. |
| `xpos` | X | m | 0.0 | Horizontal coordinate of the cable centre. Editable in the composition table. |
| `ypos` | Depth | m | 1.0 | Positive burial depth of the cable centre below ground. Editable in the composition table. |
| `phase` | Phase | — | 1 | Global, one-based phase number controlling matrix order. Editable in the composition table. |
| `circuit_index` | Circuit index | — | Derived | One-based circuit number calculated from `phase`; read-only in the composition table. |
| `phase_type` | Phase name | — | Derived | A, B or C within the circuit, calculated from `phase`; read-only in the composition table. |

Global phases 1, 2 and 3 mean circuit 1 phases A, B and C; 4, 5 and 6 mean circuit 2 phases A, B and C, and so on. For `n` positioned cables, the global phase numbers must be exactly 1 through `n`, without gaps or duplicates. A one- or two-cable composition is supported even though it has no complete three-phase sequence representation.

The builder initially places newly added cables at 1 m depth and horizontal coordinates 0.0, 0.1, 0.2 m, and so on. These are editing defaults, not a prescribed cable arrangement. Position and phase changes recalculate the currently edited system. If removing a cable leaves a gap in phase numbering, renumber the remaining entries.

### Sequence-only inputs and calculated results

Leave the physical composition empty to define an existing cable directly by its sequence parameters. All the following values default to zero and are per kilometre, not per-unit branch quantities.

| Python property | Description | Unit | Default | Role |
| --- | --- | --- | --- | --- |
| `R` | Positive-sequence series resistance | Ω/km | 0.0 | Input in sequence-only mode; calculated from the first circuit in complete physical mode. |
| `X` | Positive-sequence series reactance | Ω/km | 0.0 | Input in sequence-only mode; calculated from the first circuit in complete physical mode. |
| `B` | Positive-sequence shunt susceptance | μS/km | 0.0 | Input in sequence-only mode; calculated from the first circuit in complete physical mode. |
| `C` | Positive-sequence shunt capacitance | μF/km | 0.0 | Alternative representation of `B`; calculated in complete physical mode. |
| `R0` | Zero-sequence series resistance | Ω/km | 0.0 | Input in sequence-only mode; calculated from the first circuit in complete physical mode. |
| `X0` | Zero-sequence series reactance | Ω/km | 0.0 | Input in sequence-only mode; calculated from the first circuit in complete physical mode. |
| `B0` | Zero-sequence shunt susceptance | μS/km | 0.0 | Input in sequence-only mode; calculated from the first circuit in complete physical mode. |
| `C0` | Zero-sequence shunt capacitance | μF/km | 0.0 | Alternative representation of `B0`; calculated in complete physical mode. |

Keep each capacitance/susceptance pair consistent: with these units, `B = 2 * pi * freq * C`, and likewise for `B0` and `C0`. Assigning `C` or `C0` through its property updates the corresponding susceptance when automatic updates are enabled. Constructor arguments are stored separately, so do not supply inconsistent pairs or assume that a nonzero constructor `C` also initializes `B`.

In physical mode, call `compute()` to obtain the primitive core-and-sheath matrices and the reduced phase matrices. Their impedance units are Ω/km and their admittance units are S/km in the API; the builder displays admittances in μS/km. Sequence matrices are available when the phase count forms complete three-phase circuit blocks. They are results, not additional material inputs. For incomplete blocks, use the phase matrices rather than interpreting the scalar sequence fields as calculated equivalents.

The matrix choices and physical reduction are explained in the [underground line model](modelling.md#underground-lines).

| Read-only result | Meaning in physical mode | Unit |
| --- | --- | --- |
| `z_primitive`, `y_primitive` | Full core-then-sheath matrices, each of size `2n × 2n` for `n` cables. | Ω/km, S/km |
| `z_nabc`, `y_nabc` | Reduced core phase matrices, each of size `n × n`. Despite the names, these do not contain an explicit sheath or neutral row. | Ω/km, S/km |
| `z_phases_nabc`, `y_phases_nabc` | Global phase numbers identifying the rows and columns of the phase matrices. | — |
| `z_seq`, `y_seq` | Zero-, positive- and negative-sequence matrices for complete ABC circuit blocks; otherwise `None`. | Ω/km, S/km |

Without a physical composition, the phase matrices are reconstructed from the scalar sequence values, assuming
negative sequence equals positive sequence. Physical primitive matrices are not available in this mode.

### Validation and applying a template

A physical calculation requires at least one construction, consecutive unique phases, distinct cable-centre positions, positive burial depths, positive core diameters, main insulation and sheath thicknesses, overall diameters larger than the core diameters, and a finite positive sheath annular area. The selected inputs of both layers must be finite: either two positive DC resistances, or positive resistivities and filling factors greater than zero and at most 100%. Inactive material inputs do not participate in validation. The current checks do not enforce every physical constraint: also ensure positive outer insulation thickness, sensible permeabilities, positive frequency and soil resistivity, and a non-overlapping cable arrangement. Successful input conversion in a table cell is not a full geometry validation.

The Python workflow is:

1. Create the construction entries and register them with `grid.add_underground_cable()`.
2. Create the `UndergroundLineType`, add its cable relationships, and call `system.compute(logger=logger)`. Check its return value and validation log.
3. Register the template with `grid.add_underground_line()` and create a network `Line` with its connected buses, length in km and one-based `circuit_idx`.
4. Apply the calculated template using `line.apply_template(obj=system, Sbase=grid.Sbase, freq=grid.fBase, logger=logger)`.

The system's own `freq` controls its physical calculation. Set it consistently with the network frequency; the `freq` argument to `Line.apply_template()` does not replace it for an underground template.

Assigning `line.template` alone does not calculate or copy the electrical parameters. Recompute the system after changing construction, positions or environmental inputs, then reapply it to each affected line. Reapply the template after changing line length as well, so both scalar parameters and phase matrices correspond to the new length. Line length and circuit selection belong to the network branch, not to the reusable construction or system.


### Applying Cable System to a DC line

The **Cable** and **Cable System** creation workflow is shared by AC and DC:

1. Define the physical Cable, including the shared core/sheath resistance-input selector.
2. Position the required cables in the Cable System builder and calculate its matrices at a positive reference frequency (50 Hz by default).
3. Create a `DcLine` between DC buses. In its design tab, choose the Cable System and press **Load template values**.
4. Select **Cable System conductor**, enter the installed length and branch current rating, then apply the design.

The conductor number is the builder's global **Phase** number (1, 2, ...), reused as a conductor identifier for DC. A one- or two-cable layout is valid; a complete ABC circuit is unnecessary. In the design tab, **Use Cable System** keeps resistance derived from the template. Clear it to enter a resistance manually and remove the template association. This manual branch has no stored L/C evidence.

For a physical system and selected conductor `i`:

- `Rdc` is the selected Cable's `core_dc_resistance` in Ω/km, from its active resistance input method. It is not the real part of the AC impedance matrix.
- `L = Im(Z[i, i]) / (2*pi*freq)` in H/km.
- `C = Im(Y[i, i]) / (2*pi*freq)` in F/km.

These use the existing sheath-reduced phase matrices at the reference frequency. Each scalar `DcLine` represents one selected conductor; it does not retain mutual coupling with other DC branches, automatically combine an outgoing and return conductor, or introduce a new sheath-bonding model. Represent a metallic return as a separate DC branch where required. The material-based resistance is at 20 °C; the existing branch temperature correction remains controlled by the simulation options.

For an equivalent imported without geometry, `get_dc_parameters()` returns `R`, `X/(2*pi*freq)` and `C*1e-6`. If `C` is zero it uses `B*1e-6/(2*pi*freq)`. Only conductor 1 is available for this scalar equivalent. **Cable System C is always in µF/km**, including imported DC systems; the DC parameter API returns F/km.

With length `ell` in km and `Zbase = Vnom**2/Sbase`, application retains the previous DC conversions:

```text
Rpu = Rdc * ell / Zbase
Lpu_seconds = L * ell / Zbase
Cpu_seconds = C * ell * Zbase
```

`DcLine.apply_template()` copies R into the branch and preserves its existing rating. Dynamic consumers request L/C through `get_applied_dynamic_values_pu_seconds()`; this catalogue change does not add new dynamic models or mutual-coupling equations. The catalogue can reference AC or DC dynamic templates, but application only copies a template compatible with the receiving branch (or a generic template); an incompatible AC/DC model is skipped with a warning. Assign separate dynamic models on the branches when a system is shared across both domains. Reapply the system after changing Cable data, geometry or the selected conductor.

The following standalone example creates a physical cable system and applies it
to a DC branch. Its construction defaults illustrate the workflow; replace them
with the cable's actual dimensions and material data for a network study.

```python
from VeraGridEngine.basic_structures import Logger
from VeraGridEngine.Devices.Branches.dc_line import DcLine
from VeraGridEngine.Devices.Branches.underground_cable_type import UndergroundCableType
from VeraGridEngine.Devices.Branches.underground_line_type import UndergroundLineType
from VeraGridEngine.Devices.Substation.bus import Bus
from VeraGridEngine.Devices.multi_circuit import MultiCircuit

grid = MultiCircuit(Sbase=100.0)
logger = Logger()

cable = UndergroundCableType(name="Example cable", nominal_voltage=15.0)
grid.add_underground_cable(cable)
system = UndergroundLineType(name="Example system", Vnom=15.0, freq=50.0)
system.add_cable_relationship(cable=cable, xpos=0.0, ypos=1.0, phase=1)
grid.add_underground_line(system)

dc_bus_1 = Bus(name="DC from", Vnom=15.0, is_dc=True)
dc_bus_2 = Bus(name="DC to", Vnom=15.0, is_dc=True)
grid.add_bus(dc_bus_1)
grid.add_bus(dc_bus_2)

dc_line = DcLine(bus_from=dc_bus_1, bus_to=dc_bus_2,
                 length=2.5, rate=30.0, dc_conductor=1)
grid.add_dc_line(dc_line)
dc_line.apply_template(obj=system, Sbase=grid.Sbase, logger=logger)
if logger.has_errors():
    raise ValueError(str(logger))
r_ohm_km, l_h_km, c_f_km = system.get_dc_parameters(conductor=1)
```

### PowerFactory and legacy DC catalogue compatibility

DC `TypLne` import retains its existing classification, completeness checks and conversions: `L = xline/(2*pi*frnom)`, and C from `cline` or `bline/(2*pi*frnom)`, with direct capacitance taking precedence. Values are now stored in a parameter-only Cable System; missing construction data is not invented. Incomplete or unclassified types keep the existing resistive-line fallback. DGS export emits a DC equivalent for each system/conductor used by a DC line.

Older `.veragrid` DC catalogue records migrate to Cable System before line references are resolved. Identifiers and dynamic associations are retained; old H/km and F/km values are converted to the common X and µF/km fields. New files save only the common catalogue. The separate **DC cable type** GUI category has been removed.

For Python migration, prefer `UndergroundLineType` and `grid.add_underground_line()`. The deprecated `DcCableType(R=..., L=..., C=...)` constructor still accepts its old H/km and F/km arguments, but produces a common Cable System whose **C property uses µF/km**. Read DC quantities with `get_dc_parameters()` or `get_dc_values()` instead of the old `.L`/`.C`/`get_values()` interface. The old `dc_cable_types` collection and add/delete methods are compatibility aliases for the common AC/DC catalogue, not a filtered DC list.
