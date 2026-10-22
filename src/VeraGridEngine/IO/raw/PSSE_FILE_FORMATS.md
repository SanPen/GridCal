# PSS/E files: purpose, parsing and conversion

This directory handles the PSS/E network and its auxiliary files. A file being
parsed successfully does **not** mean that every record has an equivalent in
VeraGrid or that the resulting study reproduces PSS/E execution.

The boundary is explicit: PSS/E documents, version information and conversion
diagnostics belong to `PsseCircuit` and the `IO/raw` layer. `MultiCircuit` and
native devices receive native equipment, parameters, contingencies, diagrams
and dynamic templates. They do not carry PSS/E import-report attributes.

## What each file does

| File    | Purpose                                                                                                                                                                    | Relationship to the network                                                                                                         |
|---------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------|-------------------------------------------------------------------------------------------------------------------------------------|
| `.raw`  | Text power-flow network: buses, generators, loads, shunts, branches, transformers, controls and other network equipment.                                                   | Establishes the working case and equipment identities used by auxiliary files.                                                      |
| `.rawx` | JSON representation of PSS/E network data.                                                                                                                                 | Alternative network input/output; it is not a container for the auxiliary documents below.                                          |
| `.sub`  | Named subsystem selections: buses selected by number, area, zone, owner, voltage and other criteria, with unions, intersections, exclusions and participation information. | Supplies reusable selections referenced by monitoring and contingency definitions. It is not a second set of native areas or zones. |
| `.mon`  | Monitored elements, interfaces, voltages and their limits/ratings.                                                                                                         | Defines what the study checks and reports, rather than which equipment fails. Selections can reference `.sub` names.                |
| `.con`  | Explicit contingency events and directives for generating contingencies automatically.                                                                                     | Defines what changes during each scenario. Can reference subsystems rather than listing every affected device.                      |
| `.dyr`  | Dynamic model assignments and model parameters: machines, governors, exciters, stabilizers and other library or user models.                                               | Attaches dynamic behavior to equipment identified in the network. Parameter order and signal conventions are model-specific.        |
| `.seq`  | Sequence and fault-study data, including machine, line, transformer, shunt and converter fault representations.                                                            | Supplements positive-sequence power-flow data for short-circuit calculations. Includes unit/base and connection information.        |
| `.rop`  | Optimal-power-flow data: dispatch groups, limits, costs, adjustable controls, reserves, interfaces and additional constraints.                                             | Describes an optimization problem on top of the working case; it is not simply a list of generator costs.                           |
| `.gcp`  | Generator reactive capability curves relating active power to reactive limits.                                                                                             | Supplements or replaces applicable fixed generator reactive limits according to source operating mode.                              |
| `.loc`  | Bus and branch locations, coordinate conventions, drawing scale and substation/node offsets.                                                                               | Supplies GIS positions or schematic geometry. Cartesian drawing coordinates and node offsets are not geographic coordinates.        |

## SUB, MON and CON form one study definition

For a contingency study, these three files must be interpreted together against
the same network:

1. Resolve `.sub` definitions into equipment/bus selections.
2. Resolve `.con` events and automatic contingency directives using those selections.
3. Resolve `.mon` definitions to determine what is checked, with which limits,
   when the scenarios are evaluated.

For example, a subsystem can select an area, a CON directive can request single
branch outages inside it, and MON can select its tie lines for loading checks.
The monitored set does not have to equal the outaged set.

PSS/E's DFAX activity builds a distribution-factor data file from the SUB, MON
and CON inputs; contingency analysis then uses that study data. See POM 33.10,
chapter 8, especially sections 8.1.2–8.1.5. DFAX construction is not currently
implemented here.

The current converter resolves SUB first, then MON and CON using shared subsystem
lookups. It creates supported native contingencies and branch monitoring flags.
**This is partial study conversion:** a native outage list and loading flags do
not represent every PSS/E interface, voltage criterion or rating override.

## Parsing status

Each auxiliary format has its own `parse_*` and `read_*` entry points:

| Format | Parser module | Parsed representation and boundaries |
| --- | --- | --- |
| SUB | [sub_parser.py](sub_parser.py) | Typed subsystem operations, selections and participation data. Resolution against the network happens later. |
| MON | [mon_parser.py](mon_parser.py) | Typed monitoring definitions, selectors, limits, groups and interfaces. Parsing a criterion does not imply native monitoring support. |
| CON | [con_parser.py](con_parser.py) | Typed events, explicit contingencies, automatic-generation directives, categories and exclusions. Unsupported syntax remains available with diagnostics. |
| DYR | [dyr_parser.py](dyr_parser.py) | Source records, model identities and parameters. Explicit schemas name constants for reviewed standard models; other records remain inspectable without inventing a native binding. |
| SEQ | [seq_parser.py](seq_parser.py) | Ordered, section-tagged fault records, options and converter tables/references. Optional numeric omissions remain distinguishable from zero. |
| ROP | [rop_parser.py](rop_parser.py) | Ordered records across sixteen OPF sections, including referenced tables and continued/member records. Record validity is separate from the OPF `STATUS` field. |
| GCP | [gcp_parser.py](gcp_parser.py) | Capability curves, source points, change mode and legacy implicit-origin information. Parsing does not interpolate or apply limits. |
| LOC | [loc_parser.py](loc_parser.py) | Locations with coordinate-system metadata, scales and branch-layout conventions. Supports decimal and documented DMS forms; does not invent a projection or infer ambiguous endpoint roles. |

The parsers retain source text/locations and diagnostics. Invalid or unsupported
input must not silently become valid native equipment. Network-dependent defaults,
reference matching, impedance-base changes and native object creation belong to
conversion, not lexical parsing.

RAW and RAWX use [raw_parser_writer.py](raw_parser_writer.py) and
[rawx_parser_writer.py](rawx_parser_writer.py). Their network conversion is handled
by [raw_to_veragrid.py](raw_to_veragrid.py) and
[veragrid_to_raw.py](veragrid_to_raw.py).

### Version support and evidence gaps

Auxiliary documents have explicit classes under `versioned/v33`, `v34`, `v35`
and `v36`, with shared grammar/record code under `versioned/base`. Select the
source version explicitly; do not infer it from the number of fields. Owning a
document in `PsseCircuit` checks its version against the network's `REV`.

Important distinctions:

- **SEQ 35 has a minor-version boundary.** 35.0/35.1 use legacy converter fault
  curves; 35.2 uses named tables and references. `REV=35` cannot distinguish them.
  Select `Sequence35Layout.V35_0` for the legacy layout; the default is `V35_2`.
- **ROP changes field order.** Adjustable-shunt `CTYP,STATUS` in 33/34 becomes
  `STATUS,CTYP` in 35/36. Nested member terminators and counted cost points also
  require format-aware parsing.
- **GCP 34 is provisional.** It currently inherits the legacy 33 profile and is
  marked `FeatureSupport.UNVERIFIED`; the supplied manuals did not establish a
  separate 34 specification. Versions 35/36 use a revision/change header and
  explicit points, unlike legacy 33.
- **LOC branch layouts in 34/35 are provisional.** Optional endpoint conventions
  follow the documented legacy layout and are marked unverified. Version 36
  explicitly requires branch endpoints. Parsing points cannot resolve their roles
  when the source layout itself leaves them ambiguous.
- **DYR library coverage is model-specific.** Recognizing a model name or parsing
  its numeric payload does not establish equation equivalence. A native binding
  requires reviewed constant order, units, ports, structural variants and initialization.

The detailed manual paths, version differences and evidence are maintained in
[versioned/auxiliary_formats.rst](versioned/auxiliary_formats.rst). Primary manuals
are under [trunk/File_formats_docs/PSSE docs](../../../../trunk/File_formats_docs/PSSE%20docs).

## Current conversion to native objects

[psse_to_veragrid](raw_to_veragrid.py) builds the native network first, then calls
[PsseAuxiliaryConverter](auxiliary_to_veragrid.py) for owned auxiliary documents.
Equipment matching uses RAW identities, including leading-zero machine IDs,
branch circuit IDs and substation/node identifiers. Ambiguous matches must not
select an arbitrary native device.

| Format | Native conversion implemented | Remaining limits |
| --- | --- | --- |
| SUB | Resolves bus selections for MON/CON; records named membership and participation weights on the source report. Preserves native RAW area/zone membership. | Node selectors, power-dependent exclusions and unresolved participation references need further mappings. Named selections are not fabricated as native areas. |
| MON | Resolves explicit branches and supported endpoint/subsystem selections to native `monitor_loading` flags, including supported exclusions. | No complete interface/voltage-monitor translation. Ownership/kV filters, three-winding selections and source-specific rating semantics are not a complete native study definition. |
| CON | Creates native `ContingencyGroup` and `Contingency` objects for supported branch/machine OPEN/CLOSE operations, representable bus operations and ordinary SINGLE branch outages with exclusions/categories. Leaves base-case equipment state unchanged. | Unsupported events reject the entire explicit group. Bus outages involving loads/shunts, other automatic directives and more complex event semantics need additional mappings. Reliability metadata may remain source-only. |
| DYR | Installs connected native generator RMS assemblies using the reviewed bindings listed below. | No automatic model-name-to-template matching. Unsupported/invalid neighboring models block host activation rather than create an incomplete controlled plant. |
| SEQ | Converts machine sequence impedances and neutral impedances to native bases; applies line zero-sequence fields, fixed-shunt data and supported simple two-winding zero-sequence connections. | Included machine GSUs, complex transformer neutral/core equivalents, three-winding equivalents and additional fault representations remain unsupported/partial. Simple connection codes supported are 1/2/4 and 11/12/14 without separate neutral networks; reverse-grounded 3/13 lacks a native connection representation. |
| ROP | Applies supported hard normal bus voltage bounds, independent generator dispatch limits and polynomial fuel costs with the fuel multiplier. | No full OPF constraint translation: shared dispatch coupling, soft/emergency limits, reserves, interfaces and non-polynomial costs remain reported. Table-only UPDATE records require explicit generator-dispatch rows to reapply the affected native limits/costs. |
| GCP | Populates native reactive capability curves, inserts documented implicit origins and orders motor points for native interpolation. Respects non-conventional operating-mode restrictions on activating curves. | UPDATE points with omitted ordinates are not guessed. A stored curve does not override operating modes whose limits follow another source rule. |
| LOC | Applies bus GIS coordinates and unambiguous geographic line paths; creates native Cartesian schematics and station-local node-offset diagrams. | Drawing inches map to 96 scene units. Physical SCALE remains source information. Ambiguous legacy branch endpoints and missing node identities cannot be turned into invented geographic paths. |

REPLACE/UPDATE behavior is handled only for reviewed mappings; it is not a claim
that every PSS/E working-case default has a native equivalent. In particular,
SEQ/GCP replacements reset their supported native fields, while supported
updates retain omitted values. See the ROP and GCP limits above before relying on
incremental auxiliary files.

### Reviewed DYR bindings

[dyr_to_veragrid.py](dyr_to_veragrid.py) uses existing VeraGrid RMS template
builders and equations. Bindings explicitly map source constants and controller
signals, including machine/system MVA bases. Catalogue templates themselves are
not modified by import.

| Model | Native role | Relevant restrictions/behavior |
| --- | --- | --- |
| GENCLS | Classical synchronous machine | Converts inertia, damping and RAW machine impedance; zero inertia selects a fixed rotor with zero angle/speed derivatives and live stator equations. |
| GENROU | Round-rotor synchronous machine | Uses the native six-state model, with reviewed saturation and reactance conversions. |
| GENROE | Round-rotor machine with power-law saturation | Six states and resultant-flux saturation on both axes. Two positive saturation samples define the exponent; two zeros select an unsaturated structure. Single-zero pairs are rejected. |
| GENTRA | Field-transient salient-pole machine | Three states, direct-axis transient-flux saturation and explicit stator saliency. Saturation requires two positive factors or two zeros; a single-zero pair remains unsupported. `AF` is retained as source network-iteration data; it does not alter the native coupled DAE. |
| GENSAL | Salient-pole synchronous machine | Uses the native five-state machine with an explicit network bridge; it is not replaced by GENROU. |
| GENSAE | Salient-pole machine with two-axis power-law saturation | Five genuine differential states. A single quadrature subtransient-flux state consumes the resultant-flux saturation factor; no quadrature transient circuit or small replacement time constant. Both zeros disable saturation; single-zero pairs are rejected. |
| DEGOV, DEGOV1 | Delayed engine governors | Matching 33/35 records, inherited 34 and provisional 36. Electronic control box, bounded fuel actuator and combustion transport history. Separate throttle/electrical feedback, machine torque output and equilibrium seeds. Positive denominator times and TD required; delay resolution depends on accepted solver steps. |
| DEGOV1D / DEGOV1DU | Deadband engine governors | Direct 35/36 layout versus explicit 33-only USRMDL allocation contract. Continuous asymmetric speed deadband and optional turbine-rating conversion. The 33 heading spelling DEGOVIDU is not invented as a callable alias. See [research](../../../../trunk/dynamics/model_research/DELAYED_ENGINE_GOVERNORS.md). |
| TGOV1 | Turbine governor | Converts droop, power limits and damping to the connected machine/system bases. |
| HYGOV | Nonlinear hydraulic governor | Correct filtered PI output includes proportional and integral rates, with total-demand velocity/travel stops before the gate servo. Exact head=(flow/gate)^2; speed/load reference is in speed units and initializes from loss-adjusted mechanical power. |
| IEEEG3 | Pilot-valve hydraulic governor | Four states, separate velocity/position stops, permanent/transient gate droop and linearized hydraulic inverse response. Reviewed fourteen-constant layout in both supplied libraries. |
| IEEEG3D | Deadband pilot-valve hydraulic governor | Direct seventeen-constant assignment is reviewed in the 35 profile and inherited by 36. Asymmetric continuous deadband and explicit TRATE base conversion; zero rating selects MBASE. The 33.10 USRMDL/IEEEG3DU wrapper is reviewed separately with exact allocation checks; 34 direct layout is unverified and retained as unsupported. |
| HYGOV2 / HYGOV2D / HYGOV2DU | Cascaded-PI hydraulic governor | Explicit speed PI, governor PI, gate-velocity compensation, permanent/transient gate droop, rate/travel stops and linear inverse-response water column. Six states with enabled speed integral gain; zero permanent droop is supported. Direct parent in 33–35; direct deadband variant in 35; exact 33 wrapper allocation is NI=0/NC=19/NS=6/NV=2. Turbine rating/base and actual initial power are explicit. Water constants remain operating-point-specific. |
| PIDGOV / PIDGOVD / PIDGOVDU | Hydraulic PID with calibrated gate/power characteristic | Electrical-power or gate feedback, droop-path transducer, separately filtered PI/derivative, two controller filters, signed gate velocities/travel stops, monotone four-point characteristic/inverse, fixed water-column response and raw-speed damping. Direct parent retains one feedback ICON; 35 deadband variant retains it and adds three CONs; exact 33 wrapper allocation is NI=1/NC=23/NS=7/NV=2. Native curve extends its outer linear segments; runtime equivalence of extrapolation remains unverified. |
| GASTD / IEESGOD / HYGOVD / TGOV1D | Asymmetric-deadband gas, steam and hydro governors | Direct layouts are reviewed in 35 and provisionally inherited by 36; profile-33 GASTDU/IEESGODU/HYGOVDU/TGOV1DU have distinct exact user-allocation contracts. Positive TRATE selects turbine base, zero machine base. Raw-speed damping remains outside control deadbands. See the family note for hydraulic correction and TGOV1D base-footnote interpretation. |
| GGOV1 / GGOV1D | Tracked fuel-valve governor and turbine | Explicit signed droop selection, fuel-speed scaling, PID/tracked load PI, finite valve/load-output slew limits, electrical reset and turbine-base conversion. GGOV1D direct layout is reviewed for 35 and provisionally inherited by 36; older wrappers remain distinct. Zero TENG/KA, positive KPGOV/KPLOAD/KILOAD/TFLOAD, and fixed load cap are required. Unsupported configurations block the complete host. Native builder now exposes four physical inputs; old saved graphs retain their prior equations. |
| IEEEG1 | Multi-stage steam turbine governor | Twenty constants plus an explicit second-machine bus/character-ID header. Valve rate and position stops, exact zero-time steam stages and separate shaft outputs. Import currently requires JBUS=0 and zero second-shaft fractions; cross-compound records inhibit activation of both exact machine identities. |
| IEEEG1D | Steam governor with asymmetric speed deadband | Direct 35 layout adds deadband and turbine rating; 36 inherits this profile provisionally. The 33.10 IEEEG1SDU wrapper is reviewed separately; other wrappers remain unsupported. Same single-shaft restriction; positive TRATE selects turbine MW base, zero selects machine MVA base. |
| GGOV1DU / IEEEG1SDU / IEEEG3DU | Release-owned legacy governor bindings | Profile 33 only: exact USRMDL calling/allocation contracts, named payloads and preserved source headers. Reuses the corresponding physical governor equations with existing rating/base conversions. Unknown native-looking user names and changed allocations never acquire a binding implicitly. Later wrapper profiles remain unreviewed. See the legacy research note for source-table discrepancies and inherited restrictions. |
| PSS2A / PSS2B | Dual-input ramp-tracking stabilizer | Six ICONs include the two measurement pairs and M/N orders. Seventeen/twenty-three CONs, order-dependent memories, exact bypasses and zero initial output. Speed deviation, machine-base electrical power and local/remote AC voltage are reviewed; frequency, accelerating power and voltage differentiation remain unsupported. PSS2B additionally clips raw inputs and has a third output phase stage. |
| LCFB1 | Outer turbine load controller | Seven constants and two flags; measured-power control must be enabled, frequency bias is optional. Currently connects to a field-dynamic machine and single-shaft IEEEG1. Electrical setpoint, mechanical operating point and valve-reference units are initialized separately, including nonunit steam-fraction sums. Power-disabled operation and other governor hosts remain unsupported. |
| SEXS | Simplified exciter | Maps the source lead-lag ratio to the native parameters and connects the voltage reference. |
| EXST1 | Static exciter | Supports reviewed zero-lag cases by using algebraic equations instead of arbitrary small time constants. |
| EXST2 / EXST2A / ESST2A | Distinct compound-source static exciters | EXST2 **adds** bridge forcing to regulator output; EXST2A multiplies them; ESST2A adds a pre-regulator high-value UEL gate to the multiplicative structure. Five-region rectifier loading, bounded field and exact zero-time stages. KP=KI=0 selects unit independent supply; KI=0 with nonzero KP requests unreviewed initialization calibration and blocks activation. |
| BBSEX1 | Static excitation with bounded regulator feedback | Explicit zero/nonzero supplementary routing, positive-feedback realization of regulator lead/lag, fixed internal limits and actual terminal-voltage-scaled field limits. Uses the supplied 33.10/35.2 diagrams; an independent simulator diagram with different routing/filtering is not substituted. Native fresh construction now has an explicit terminal-voltage port; saved graphs retain their own equations. |
| BUDCZT | Independently limited parallel PI excitation | Separate integral/total-PI limits and actuator/exciter states. Explicit release-owned TA/TE orders: 33 J+5=TA/J+6=TE; 35 J+5=TE/J+6=TA. Profile 34 stays unsupported because its order is unverified; 36 provisionally inherits 35. Ordering follows supplied sheets; native export confirmation remains pending. |
| ESST1A | Terminal-fed static excitation with selectable gates | Two explicit UEL/VOS ICONs and eighteen constants match the supplied 33/35 sheets. Three UEL locations, two stabilizer summations, two phase compensators, field-current limiting, delivered-field rate feedback and actual terminal-voltage capability. Source OEL conversion remains pending; an absent gate uses exact bypass. Native crossed-capability convention applies the commutation ceiling last; source-runtime priority in that region is unverified. |
| PSS2C | Four-phase dual-input ramp tracking | Six ICONs and twenty-nine CONs are reviewed in 35, provisionally inherited by 36; earlier layouts remain unsupported. Four phase stages and actual M*N ramp memories. Requires PSSON<0, positive first washouts and reviewed speed/power/voltage selectors; hysteresis and compensated-frequency input remain unsupported. |
| PSS3B | Quadratic dual-input stabilizer | Four ICONs and seventeen CONs match both supplied releases. Independent signed input gains/lags/washouts, optional common washout and two exact quadratic phase ratios. Zero-time bypasses preserve actual constant bias. Uses reviewed selected-measurement infrastructure; other measurement types remain unsupported. |
| DC1C / DC2C | Bounded rotating excitation with selectable limiter routing | Explicit profile-35 seventeen-CON/two-ICON layouts; provisional 36 inheritance, earlier profiles unsupported. Separate field-memory upper/lower stops, quadratic saturation, phase compensation and field-rate feedback. DC2C scales regulator capability with terminal voltage. Either saturation-sample order is accepted for explicit capability. Automatic KE/capability selectors remain unsupported. |
| IVOST | Rational electrical-power stabilizer | Matching supplied 33/35 twenty-one-CON layouts, inherited 34 and provisional 36. System-base PELEC directly feeds tracked first/second rational stages and an externally clipped final stage. Actual steady auxiliary bias is preserved. Ambiguous zero-origin, free zero-gain integral and bounded positive-lead PI source degenerations remain declined. |
| IVOGO | Rational speed governor | Matching supplied 33/35 twenty-one-CON layouts; backward symbolic load balance supports stable stages and load-holding integrators. Mechanical power and shaft torque are separate; source connection converts speed/base exactly once. Shares the explicit rational source-degeneration restrictions. See [research](../../../../trunk/dynamics/model_research/RATIONAL_FILTER_CONTROLS.md). |
| AC7C | Selectable cascaded brushless excitation | Supplied 35 thirty-three-CON/six-ICON layout; 36 provisional, older profiles unreviewed. Compound or live-EFD self-excitation, independent PID/PI limits and five takeover points. Ambiguous source KP=0 rectified-potential semantics are declined. See [research](../../../../trunk/dynamics/model_research/CASCADED_BRUSHLESS_EXCITATION.md). |
| AC7B | Cascaded brushless PID/PI excitation | Matching supplied 33/35 twenty-seven-CON layouts; 34 inherited, 36 provisional. Independent loop limits, mixed field/current feedback, VFE rate feedback, KP=0 unity-supply bypass and negative forcing floor. Actual auxiliary bias and either saturation-sample order are supported. See [research](../../../../trunk/dynamics/model_research/CASCADED_BRUSHLESS_EXCITATION.md). |
| DC4C | Compound-fed commutator PID excitation | Supplied 35 twenty-four-CON/four-ICON schema; 36 provisional. Loaded winding-current supply, post-PID limiter gates, separate fixed amplifier bounds and field-rate feedback. KE=0 automatic calibration remains unreviewed. See [research](../../../../trunk/dynamics/model_research/COMPOUND_COMMUTATOR_EXCITATION.md). |
| ST6C | Current-limited static field regulation | Supplied 35 twenty-five-CON/four-ICON schema; 36 provisional. Live outer PID current capability, pre-supply bridge feedback, four limiter locations and both potential sources. Explicit VMMIN spelling resolves the printed duplicate. See [research](../../../../trunk/dynamics/model_research/CURRENT_LIMITED_FIELD_EXCITATION.md). |
| AC8C | Compound-fed PID rotating excitation | Supplied 35 twenty-seven-CON/five-ICON schema; 36 provisional, earlier layouts unreviewed. Distinct source/output bridge loading, sum/input/post-PID limiter locations and both PSS locations. Reviewed SCL signals are unused by the source implementation. See [research](../../../../trunk/dynamics/model_research/COMPOUND_PID_EXCITATION.md). |
| ST5C | Selectable parallel-channel excitation | Supplied 35 eighteen-CON/two-ICON schema; 36 provisional, earlier profiles unreviewed. Independent summed or takeover limiter locations, actual auxiliary bias initialization and dedicated-channel activation only on strict takeover. See [research](../../../../trunk/dynamics/model_research/PARALLEL_CHANNEL_EXCITATION.md). |
| ST5B | Parallel-channel static excitation | Matching supplied 33/35 eighteen-CON layouts; 34 inherited and 36 provisional. Three continuously evolving two-stage bounded compensators, high/low take-over selection, separate field-current drop and moving terminal capability. Compatible MNLEX signals connect at the actual take-over point; initial capabilities/gates must admit the operating point. Absent gates use exact moving bypass. See [research](../../../../trunk/dynamics/model_research/PARALLEL_CHANNEL_EXCITATION.md). |
| AC8B | Bounded PID brushless excitation | Matching supplied 33/35 twenty-one-CON layouts; 34 inherited and 36 provisional. Independent PID/amplifier non-windup bounds, rotating-field saturation/demagnetization, current-equivalent ceiling and loaded diode bridge. Positive KE required; exact rounded commutation transition/gap cases remain unverified. See [research](../../../../trunk/dynamics/model_research/PID_BRUSHLESS_EXCITATION.md). |
| ST4C | Filtered cascaded-PI static excitation | Modern 35 layout; 36 provisional; 33/34 unreviewed. Two bounded PI loops, separate bounded firing lag, capped filtered VA feedback before supply multiplication, selected PSS/UEL/OEL insertion and terminal/independent potential. Source-unused SCL signals remain unused. Compatible MNLEX signals connect at the selected additive/take-over point; initial gates must admit the actual operating point. Absent controllers use exact moving bypass. See [research](../../../../trunk/dynamics/model_research/FILTERED_COMPOUND_PI_EXCITATION.md). |
| EXPIC1 | PI/compound-source excitation with explicit field forcing | Twenty-four constants match supplied 33/35 layouts. Separate bounded PI demand, two-pole regulator/external clip, bounded-regulator rate feedback and field-forcing limits. KP=KI=0 explicitly selects unit supply; TE=0 explicitly bypasses field resistance/saturation dynamics. Proper zero-pole reductions preserve source positions. |
| IEET1B | Biased two-stage rotating excitation | Eighteen constants match supplied 33/35 layouts. Stator-current-magnitude compensation, clipped voltage error before auxiliary summation, frozen initial regulator bias, limited first amplifier and separate second lag. Switch=0 senses VREG; Switch=1 senses EFD, following supplied diagram/reference guide despite opposite labels in another public table. KE=0/VRMAX=0 automatic calibration remains unsupported. |
| EXNI | Bidirectional controlled-bridge excitation | Ten constants match supplied 33/35 layouts. Reviewed R=0 realization supports terminal/independent supply, externally clipped amplifier with windup, and two-stage rate feedback sensing bounded regulator voltage before terminal multiplication. R!=0 reverse-current logic is explicitly unsupported; it is never discarded. |
| ESST4B | Compound-source cascaded PI excitation | Seventeen constants agree in supplied 33/35 layouts, with matching 34 inheritance and provisional 36 support. Separate bounded voltage/field PI loops, optional regulator lag, compound transformer phase/leakage, loaded rectifier and OEL low gate. Zero proportional/integral gains select supported pure-integral/proportional variants; each loop requires nonzero regulation. Potential-only KI=0 is explicit for this source, without borrowing unrelated calibration rules. |
| ST1C | Static excitation with independently selected maximum/minimum limiters | Explicit profile-35 three-ICON/eighteen-CON layout, provisional 36 inheritance. Three UEL choices, two stabilizer summations and three OEL choices retain their physical locations. Independent regulator/terminal-field capabilities, current limiting and delivered-field feedback. Absent gates bypass exact preceding demand; source OEL controllers remain unreviewed. |
| ST7B / ST7C | Static excitation with output-feedback capability | ST7B fourteen-CON/two-ICON contract agrees in supplied 33/35 sheets; ST7C has explicit profile-35 fifteen-CON/two-ICON layout. Reference additions or takeover and output gates are independent. Measurement/regulator phase shapers, independent KH/KL moving capabilities and KIA/(1+s*TIA) delivered-field feedback. ST7C adds positive firing-control lag; terminal-dependent caps apply immediately. |
| AC1C / AC2C / AC5C | Selectable brushless excitation with field-current ceiling | Release-35 layouts explicitly preserve two OEL/UEL ICONs and 21/23/19 constants; 36 provisional, 33/34 unsupported. AC1C has forward phase compensation, AC2C adds inner field-current feedback, AC5C shapes field-loss feedback and excludes demagnetization from that sensor. Signed additive inputs or downstream high/low gates, independent amplifier/forcing bounds where specified, loaded diode bridge and directional field-current ceiling. Reviewed source domain requires positive physical lags/resistance/loading, VEMIN=0; automatic calibration is not inferred. |
| AC4C | Controlled bridge with selectable limiter routing | Explicit profile-35 ten-CON/two-ICON layout, provisional 36 inheritance. Error clipping precedes phase compensation, then selectable UEL high/OEL low gates. Non-windup amplifier capability is VRMIN to VRMAX-KC*Ifd. Absent gates bypass their exact pre-gate demand; source OEL controllers remain unreviewed. |
| DC4B | Bounded PID rotating excitation | Eighteen constants and OEL/UEL selectors match supplied 33/35 layouts. Limited total PID demand stops only outward integral motion; derivative/proportional paths remain responsive. High/low takeover gates precede terminal-powered non-windup amplification, saturated rotating field, lower field stop and delivered-field washout. Initial actual terminal supply is stored independently from compensated sensing. |
| DC3A | Motor-driven rheostat excitation | Twelve ordered constants agree in supplied 33/35 sheets. Range-normalized bounded rheostat travel and parallel strict-threshold rapid forcing feed a saturated rotating field with a separate VEMIN memory stop. Positive sensing time adds a third state; TR=0 removes sensing memory exactly. |
| IEEET3 / IEEEX3 | Loaded compound-transformer excitation | Twelve constants with explicit KP/KI, the phasor transformer source and square-root field-current loading. IEEET3 clips total forcing; IEEEX3 clips transformer supply before adding regulator forcing. Four states with positive sensing/regulator times; exact zero-time stages, field washout and lower field stop. Source KI=0 requests unreviewed design calibration and remains unsupported. |
| ESAC8B | PID-controlled rotating exciter | Fifteen ordered constants; parallel PID, limited amplifier, saturated nonnegative field circuit, explicit KE/VRMAX only. Zero KE/VRMAX source calibration selectors remain unsupported. PID integral windup is retained; zero KI/KD/TR/TA select exact structural bypasses. This is distinct from native AC8B. |
| SCRX | Controlled-rectifier exciter | Live terminal-bus or independent supply and reverse-current crowbar discharge, with separate sensed/terminal voltages. Zero TE removes the regulator state exactly; TB must remain positive. |
| ESST3A | Static exciter | Only the reviewed `TA=0` structure is activated; the adapter supplies the required regulator limits and current scaling. |
| EXAC1 | AC exciter | Explicitly binds live field-current terms and initialization to the host machine. |
| EXAC1A | AC exciter with output-voltage rate feedback | Reuses the reviewed forward winding/rectifier equations but senses rectified Efd in the stabilizing loop. Its feedback memory initializes to Efd, not the internal exciter field-current equivalent. Positive TR/TB/TA/TE/TF realization only. |
| ESAC1A | AC exciter with separate capability gates | Independent VAMAX/VAMIN amplifier-state bounds, a UEL high-value gate followed by an OEL low-value gate, and downstream VRMAX/VRMIN forcing limits. Absent limiters bypass live preceding demand. Positive TR/TB/TA/TE/TF realization only; no OEL-model binding is implied. |
| ESAC2A | High-response brushless exciter with takeover gates | Proportional KB/KH inner loop, forcing-unit UEL/OEL gates, independent amplifier and forcing limits, and a current-equivalent stop on internal field memory. This is not EXAC2's finite-gain KL/VLR override. |
| ESAC3A | Self-excited brushless exciter with takeover and field stops | Nonlinear rate feedback and KR·Efd self-excitation, a UEL high-value gate before amplifier gain, and internal VEMIN/VFEMAX stops. This is not EXAC3's autonomous minimum-voltage loop. |
| EXAC2 | High-response brushless excitation | Direct inner field-current feedback, a finite-gain current low-value override, high gain KB and separate amplifier/forcing limits. Initializes amplifier demand as Vfe0*(KH+1/KB). Positive TR/TB/KA/TA/TE/TF, KB/KL/VLR and nonnegative KH are reviewed. |
| EXAC3 | Self-excited brushless excitation | Forcing is KR*Efd*Va, with a minimum-voltage gate before the amplifier and continuous piecewise KF/KN field-voltage rate feedback. Initializes amplifier output as Vfe0/(KR*Efd0). Positive initial field voltage, KR, EFDN and sensing/phase/amplifier/field/feedback times are required. |
| EXBAS | PI regulator feeding an independently supplied rotating exciter | Seven states, zero corrected steady voltage error, initialized PI memory, and shaped rate feedback from the internal field-current equivalent. Positive KI/TF2/KE and nonnegative KP/TF1/KF/VRMIN are reviewed; algebraic stages and negative forcing remain outside this binding. The amplifier stop does not freeze upstream integral memory. |
| IEEET1 | DC excitation | Fixed regulator limits; additive UEL; field-voltage rate feedback. No phase compensator. |
| IEEEX1 | Phase-compensated DC excitation | Fixed regulator limits; additive UEL before phase compensation; field-voltage rate feedback. |
| ESDC1A | Gated DC excitation | UEL high-value gate after phase compensation; fixed regulator limits; field-voltage lower stop at zero. |
| ESDC2A | Terminal-fed gated DC excitation | UEL high-value gate; regulator limits scale with actual terminal voltage independently of compensated sensing. |
| EXDC2 | Terminal-fed DC excitation | Terminal-voltage-dependent regulator limits; additive UEL before phase compensation. |
| IEEET2 | DC excitation with regulator feedback | Rate feedback from bounded regulator output followed by a second filter. No phase compensator. |
| IEEEX2 | Compensated excitation with regulator feedback | Phase compensation and two-stage regulator feedback; field voltage has a zero lower stop. |
| IEEX2A | Excitation with exciter-field-current feedback | Feedback senses the excitation machine's internal field-current equivalent, not the main generator's field current; zero lower field-voltage stop. |
| IEET1A | Field-controlled exciter with external output limits | No sensing or phase lag. Internal field memory drives rate feedback before EFDMIN/EFDMAX output clipping; resistive/saturation losses use delivered voltage. EFDMAX also supplies the upper saturation sample. Zero TA is algebraic. |
| IEEET4 | Deadband relay reset and rapid field forcing | Two states; reset rate is ±1/TRH outside KR, rapid forcing outside KV. Reviewed domain is 0 < KR < KV; no zero-KR substitution is inferred. |
| IEEET5 | Continuous error reset and rapid field forcing | Two states; reset integrates voltage error/TRH. Rapid forcing and bounded reset memory are distinct. |
| IEEEX4 | Range-normalized reset with sensing lag | Reset gain is (VRMAX−VRMIN)/(KV·TRH), with input clipping at ±KV. Rapid forcing includes equality at the threshold. Zero TR removes the sensor state exactly. |
| IEET5A | Lag/integral regulation with external field limits | TRH=0 selects KA/s, not instantaneous gain. Rapid forcing compares against frozen initial sensed voltage. Internal field voltage supplies losses before external EFDMIN/EFDMAX clipping. |
| ESAC5A | Brushless excitation | Fixed independent regulator supply, loaded saturation samples and shaped internal exciter-field-current feedback. Zero TF2 disables the TF3 numerator and removes the second feedback stage; field voltage has a zero lower stop. |
| EXAC4 | Alternator-fed controlled bridge | Input voltage-error clipping, phase compensation and unrestricted amplifier memory followed by external field-voltage clipping. Both output limits shift with live generator field current. |
| ESAC4A | Alternator-fed controlled bridge | UEL high-value gate after phase compensation and non-windup amplifier limits. Only the upper capability shifts with field current; a moving bound is enforced immediately at the output. |
| GAST | Gas-turbine governor | Three-state fuel-valve, fuel-flow and exhaust-temperature dynamics; a thermal low-value gate and non-windup valve limits precede mechanical-power output. |
| IEESGO | Steam-turbine governor | Speed compensation and weighted steam-chest/reheater/crossover stages. Reviewed zero-time stages become algebraic. |
| IEEEG2 | Linear hydro governor | Retains speed-reference, droop and the nonminimum-phase water-column response; supports an algebraic zero-T1 speed filter. |
| STAB1 | Speed stabilizer | Washout plus two lead-lag compensators, with explicit K/T and lead/lag ratio semantics. |
| STAB2A | Power stabilizer | Full triple-washout and parallel/output-filter transfer function; uses machine-base electrical power. |
| STAB3 | Power-reference stabilizer | Watt transducer, reference subtraction and filtered negative derivative. |
| STAB4 | Power stabilizer | Derivative reset, two phase compensators, output filters and asymmetric voltage limits. |
| STABNI | Power stabilizer | Double reset and fourth-order shaping; zero transducer time removes that state. |
| IEEEST | Single-input stabilizer | Full quadratic-over-fourth-order input filter, two phase stages, reset or unity-numerator mode, output saturation and compensated-voltage supervision. Reviewed selectors: rotor speed deviation, machine-base electrical power, local/remote bus voltage. |
| IEE2ST | Dual-input stabilizer | Two signed-gain transducers add before reset and three phase stages. Each selector independently supports the reviewed measurements above, including two remote bus voltages. |
| COMP | Reactive voltage compensator | Uses the signed convention `Vc = abs(Vt - j*Xe*It)` with machine-base current. |
| IEEEVC | Complex voltage compensator | Uses the existing rectangular `abs(Vt + (Rc+j*Xc)*It)` component with explicit machine-base current conversion. |
| REMCMP | Remote voltage measurement | Connects to a live native AC-bus voltage; explicit external network connections survive runtime duplication and circuit copying. |
| MNLEX1 | Minimum-excitation limiter | Active-current/field-current characteristic; field-voltage rate feedback is subtracted after the bounded amplifier. |
| MNLEX2 | Minimum-excitation limiter | Voltage-scaled circular P/Q capability characteristic with internal output-rate feedback. Supports zero-TM algebraic feedback. |
| MNLEX3 | Minimum-excitation limiter | Linear current capability characteristic with field-voltage feedback. Rotates live stator currents instead of dividing P/Q by a collapsing voltage. |

The stabilizer and minimum-excitation controllers are connected to the host
exciter, not installed as disconnected generator models. Required exciters and
compatible physical hosts must exist. Their operating-point initialization is
checked on both template graphs and duplicated native runtime graphs. An active
additive limiter and any nonzero steady stabilizer output are included when
initializing the exciter reference. Classical
constant-emf machines cannot host these excitation controllers. The classical
governor assembly currently supports TGOV1; other reviewed governors attach to
the supported field-dynamic machines.

Forty-eight new native templates have physical descriptions of equations, units,
ports, state structure, limits and initialization in their builder docstrings.
They are registered in the native engine catalogue and the dynamic editor. Source
record layouts and identifiers remain in the import layer.

`COMPCC` and `CCOMP4A` now also have native algebraic templates and physical
phasor/sharing tests, but their DYR bindings remain pending: mixed identifier
headers and cross-machine references require additional integration. A native
template existing is not the same status as an activated file-import binding.

The nine DC excitation bindings share native physical stages with explicit
regulator/field/feedback structures. Zero sensing, regulator and supported phase
lags become algebraic equations. `KE=0` selects an operating-point rheostat
calibration frozen during simulation. `VRMAX=0` derives symmetric regulator
capability from the second saturation sample and any positive specified `KE`.
The documented reserved `Switch` field is reviewed only at zero. Missing UEL
high-value gates are bypassed using their live pre-gate demand, rather than a
constant that could unexpectedly become active during a disturbance.

Current DC catalogue builders expose five explicit inputs: compensated voltage,
reference, supplementary voltage, UEL and actual terminal voltage. Their second
output exposes the pre-gate regulator demand. Existing serialized template graphs
retain their saved equations; this work does not rewrite saved native models.
User-model records are data, not permission to execute external model code.

IEEEST and IEE2ST have explicit named integer-header schemas, separately from
their real-valued constants. The 33.10 and 35.2 sheets agree on both layouts and
transfer diagrams; versioned parser/adapter tests also exercise 34 and 36, whose
library inventories remain unverified. Malformed integer headers invalidate the
record. Input selectors for bus frequency, accelerating power and voltage
derivative remain unsupported until their measurement conventions are reviewed;
they prevent partial host activation rather than selecting an approximate signal.
Supervision uses the host excitation system's compensated voltage independently
of remote stabilizer signal selection. Either IEE2ST input can be disabled with
selector zero; a direct IEEEST zero selector is not documented.
The PSS1A sheet specifies an IEEEST parameter correspondence and writes an
IEEEST record; it is not evidence for a direct `PSS1A` record grammar.

### PSS/E library mapping inventory

#### Equation-level evidence and research backlog

Parameter lists establish record layout, not controller behavior. Each activated
binding also needs equations, signal/base conventions, initialization and limit
semantics. Public references below supplement the supplied manuals; a generic
model or an older manufacturer revision does not establish equivalence to a
particular vendor-library identifier. Updated 2026-10-21.

| Reference | Evidence obtained | Consequence for implementation |
| --- | --- | --- |
| Supplied ModelLibrary 35.2 / MODELS 33.10, sections 3.8–3.9; archived PowerWorld diagrams and WECC tuning guide | PSS2A/PSS2B parameterized ramp tracker, distinct raw input clips, two/three output phase stages and six-ICON header. | Independent two-input complex responses and order-dependent state counts verify the native kernel; parser/adapter tests exercise measured-signal selection, exact bypasses, persistence and connected initialization. |
| Supplied ModelLibrary 35.2, sections 7.24–7.25; archived IEEE PES-TR1 turbine-governor report | IEEEG1 steam stages, valve rates/stops, separate shaft fractions and IEEEG1D deadband/rating additions. | Native checks cover individual/total shaft responses, zero steam lags, stops and recovery; source checks preserve character IDs and inhibit both machines in unsupported cross-compound records. |
| Supplied ModelLibrary 35.2, section 8.1; MODELS 33.10 load-controller sheet; archived governor reports and simulator diagrams | LCFB1 measured-power/frequency-biased outer reference correction with separate error and PI-output bounds. | Enabled measured-power operation is connected to single-shaft IEEEG1. Independent native responses and coupled initialization distinguish electrical setpoint from loss-adjusted valve reference and nonunit stage fractions. Disabled-power flag semantics remain unreviewed. |
| Supplied [PAGV2 35.2](../../../../trunk/File_formats_docs/PSSE%20docs/DOCS%2035/PAGV2.pdf), figure 15.5 and sections 15.4.3–15.4.5, printed pp. 133–139 | Field-transient rotor diagram, saturation conventions, GENTRA iteration acceleration, and the network-switch dependence of DC-offset torque. | Supports the three-state GENTRA realization. AF belongs to source iteration rather than native physics. GENDCO requires the pre/post-switch network state; an arbitrary extra torque lag would not reproduce it. |
| Supplied ModelLibrary 35.2, sections 3.2–3.3, printed pp. 53–56; MODELS 33.10, sections 3.2–3.3 | Matching integer selector/remote-bus headers and full single/dual-input stabilizer diagrams. PAGV2 35.2 sections 17.7.2 and 17.7.5 define compensated-voltage blocking and the dual-input zero selector. Section 3.7 describes PSS1A through an IEEEST record. | Supports exact filter reductions and separate live measurement ports. Independent complex transfer tests exercise both dual-input paths; connected-template/runtime tests cover remote sensing and nonzero steady reset output. Unreviewed measurements remain explicit gaps. |
| Supplied ModelLibrary 35.2, section 6.29, printed p. 193; MODELS 33.10, section 6.13; PAGV2 35.2 sections 17.2.4 and 17.5.15 | Matching ESAC5A constant order and brushless-exciter diagram, loaded saturation convention, zero-TF2 bypass and operating-point calibration rules. | Reuses the field-circuit realization with a distinct internal-field-current feedback structure. Tests independently evaluate the complex closed-loop transfer, field lower stop, exact feedback bypass and connected calibrated equilibrium. |
| Supplied ModelLibrary 35.2, sections 6.28 and 6.44, printed pp. 192 and 223; MODELS 33.10, sections 6.12 and 6.28; PAGV2 35.2 section 17.5.11 | Matching EXAC4/ESAC4A constant orders but different limiter diagrams and UEL locations. | Separate native structures preserve external clipping versus internal non-windup regulation, different current-dependent lower limits, and additive versus gated UEL. Frequency-response, windup, commutation-limit and connected equilibrium tests cover both variants. |
| Supplied ModelLibrary 35.2, sections 6.40–6.41, printed pp. 215–218; MODELS 33.10, sections 6.24–6.25; [PowerWorld block diagrams](https://www.powerworld.com/files/Block-Diagrams-17.pdf), EXAC1A sheet | Matching forward circuits and seventeen constants, but EXAC1A returns rectified field voltage to the rate-feedback block. | The native variant changes that measurement and its initialization while retaining field-circuit losses. Independent complex-response tests use KE different from unity to distinguish the two feedback paths; connected tests also exercise nonzero commutation, saturation and additive controls. |
| Supplied ModelLibrary 35.2, section 6.25, printed pp. 186–187; MODELS 33.10, section 6.9 | Matching nineteen-constant ESAC1A layout and separate amplifier/gate/forcing-limit diagram. | Native tests distinguish amplifier bounds from downstream forcing bounds and verify that the OEL low-value gate follows the UEL high-value gate. Direct native-catalogue initialization, parameter-dependent port guesses, persistence and connected import equilibrium are tested independently. |
| Supplied ModelLibrary 35.2, section 6.42, printed pp. 219–220; MODELS 33.10, section 6.26; PAGV2 35.2 section 17.5.9 | Matching twenty-three-constant EXAC2 layout, proportional inner field-current feedback and finite-gain current override before high gain and forcing clipping. | Native amplifier/reference initialization includes KH and 1/KB. Independent complex responses exercise both feedback loops; separate tests cover current-override selection, forcing limits and saturated-host equilibrium. This does not activate the distinct ESAC2A field-voltage-bound implementation. |
| Supplied ModelLibrary 35.2, section 6.43, printed pp. 221–222; MODELS 33.10, section 6.27; PAGV2 35.2 section 17.5.10 | Matching twenty-two-constant EXAC3 layout, regulator power from rectified Efd, minimum-voltage gate and continuous KF/KN feedback characteristic. | Independent responses distinguish both feedback slopes and supply gains; a nonzero-commutation case distinguishes rectified Efd from internal VE. Native and connected initialization use the self-excited amplifier operating point. The zero-field black-start reference remains outside this realization. |
| Supplied ModelLibrary 35.2, section 6.64, printed p. 255; MODELS 33.10, section 6.48; PAGV2 35.2 section 17.5.1 referring to 17.2.4 | Matching thirteen-constant IEET1A layout. The diagram separates internal field integration, externally limited output, pre-limit rate feedback and post-limit field losses. | Native tests distinguish all four signals, including internal windup behind a clipped output. Zero-TA, explicit/calibrated coefficients and connected-host initialization are covered. Zero calibration follows the model-specific section 17.5.1; the overview table 17.1 omits this identifier. |
| Supplied ModelLibrary 35.2 sections 6.58, 6.59, 6.63 and 6.66; MODELS 33.10 sections 6.42, 6.43, 6.47 and 6.50; PAGV2 section 17.5.4 and calibration section 17.2.4 | IEEET4/IEEET5/IEEEX4/IEET5A have distinct reset rates, threshold conventions and quick-action paths. IEET5A explicitly specifies KA/s when TRH=0. PAGV2 text says “IEEEX5” in its normalization comparison; the actual IEEEX4 data-sheet diagram is the authority. | Independent frequency responses, exact threshold tests, directional stops, external field clipping and biased-reference initialization are covered. Versioned parsing and saturated-host template/runtime tests include automatic calibration and zero-time cases. Zero-KR IEEET4 remains unreviewed; no equivalence is inferred from conversion recommendations. |
| Supplied ModelLibrary 35.2 sections 6.26–6.27, printed pp. 188–191; MODELS 33.10 sections 6.10–6.11 | Both ESAC2A/ESAC3A layouts contain 22 constants. Their internal field-voltage ceiling is specified through VFEMAX, generator field current and saturation. | Positive KE and nonnegative saturation/KD permit division-free ceiling detection by Vfe≥VFEMAX. Directional stops retain continuous field memory when current moves the ceiling. Independent transfer functions, gate location/units, stop/recovery, native catalogue initialization, versioned layouts and connected template/runtime equilibria are covered. [Public simulator diagrams](https://www.powerworld.com/files/Block-Diagrams-15.pdf) corroborate the circuit; supplied sheets determine the source-specific port choices. |
| Supplied ModelLibrary 35.2 sections 7.27–7.28, printed pp. 372–374; MODELS 33.10 sections 7.24–7.25 | IEEEG3 has the same fourteen-constant layout in both snapshots. The deadband variant changes from USRMDL/IEEEG3DU in 33.10 to direct IEEEG3D in 35.2. | Explicit version-35 schema override preserves that distinction. Native four-state graphs retain pilot/gate stops, transient droop and the potentially negative hydraulic lead. Independent closed-loop frequency response, inverse initial power response, asymmetric thresholds, persistence, coupled initialization and separate machine/turbine/network bases are tested. The profile-33 wrapper now has a separate exact allocation contract; the contradictory older figure is documented in the legacy research note. |
| Supplied ModelLibrary 35.2 section 6.45, printed pp. 224–225; MODELS 33.10 section 6.29; PAGV2 35.2 section 17.5.19 | EXBAS has matching 21-constant layouts and a PI stage before forward phase compensation. Stabilization applies a lead-lag to Vfe before filtered derivative feedback. | Native seven-state equilibrium, independent closed-loop frequency response, integral-only/PI cases, persistence, versioned parsing and saturated-host initialization are covered. PI memory retains steady forcing while corrected voltage error starts at zero. A focused test also exposed and corrected the common amplifier's exact-boundary directional stop; all eight brushless variants have boundary/recovery regressions. |
| Supplied PAGV2 35.2 sections 15.4.3 and 17.2.4, plus the individual DC-exciter model sheets | Resultant subtransient-flux power-law saturation for GENROE; frozen field-coefficient and symmetric regulator-capability calibration for the rotating exciter family. | Supports the GENROE saturation law and explicit automatic-calibration options in the eight DC bindings and ESAC5A. |
| Supplied PAGV2 35.2 figure 15.3, printed p. 131, and section 15.4.3; ModelLibrary 35.2 section 1.20; MODELS 33.10 section 1.20; [OPAL-RT synchronous-machine documentation](https://opal-rt.atlassian.net/wiki/spaces/PEUD/pages/144536247/Synchronous%2BMachine) | The original rotor diagram explicitly supplies GENSAE's direct-axis winding and single quadrature damper with saturation on both axes. Independent simulator-vendor documentation confirms the five-state/two-axis classification. | Native GENSAE retains shared stator/direct-axis equations and saturated initialization but replaces the round-rotor quadrature circuits with the documented flux equation. Tests verify the independent quadrature RHS, both saturation samples, absence of transient quadrature states/parameters, and connected saturated/unsaturated equilibrium. No direct-axis-only GENSAL alias is used. |
| [PowerWorld GENTRA documentation](https://www.powerworld.com/WebHelp/Content/TransientModels_HTML/Machine%20Model%20GENTRA.htm) | Public simulator-vendor parameter table and linked diagram; AF has no textual explanation. | Cross-check only. Its parameter table alone does not resolve the source iteration behavior. |
| Clark, Miller and Sanchez-Gasca, *Modeling of GE Wind Turbine-Generators for Grid Studies*, revision 4.5, 2010, [author-uploaded manufacturer report](https://www.researchgate.net/publication/267218696_Modeling_of_GE_Wind_Turbine-Generators_for_Grid_Studies_Prepared_by) | Original manufacturer report identified, with revision/date and generator/converter, turbine and control model coverage. | A specification candidate for the GE family. Exact correspondence to each supplied vendor-library revision still needs an equation-by-equation review; no vendor binding is activated from this discovery alone. |
| [NREL/SR-5500-52780, *Dynamic Models for Wind Turbines and Wind Power Plants*](https://docs.nrel.gov/docs/fy12osti/52780.pdf), 2011 | Public laboratory report developing manufacturer-independent wind models and documenting measured-data validation of a doubly-fed model. | Reference for generic wind physics and validation scenarios; not evidence that a proprietary vendor model is interchangeable with a generic template. |
| Eisa, Stone and Wedeward, [*Mathematical analysis of wind turbines dynamics under control limits*](https://doi.org/10.1007/s40435-017-0356-0), 2017 online | Original research identified on time-domain DAEs, control limits and well-posedness; the publisher full text was not accessible during this check. | Research lead for deriving and checking wind-model DAEs. No exact vendor-model compatibility is inferred from the abstract. |
| [OPAL-RT SCRX documentation](https://opal-rt.atlassian.net/wiki/spaces/PDOCHS/pages/149882253), plus supplied PAGV2 35.2 section 17.5.6 | Independent simulator-vendor description of supply selection and the reverse-current crowbar equation; identifies de Mello, Leuzinger and Mills, *Load rejection overvoltages as affected by excitation system control*, DOI [10.1109/T-PAS.1975.31853](https://doi.org/10.1109/T-PAS.1975.31853), as the original research. | Supports live supply and reverse-current terms in the existing native SCRX template. Its imported parameter aliases had replaced these live signals; the native equations now retain them, with branch tests and connected-import equilibrium checks. |

The supplied model-library sheets remain the primary record-layout authority.
The nine GENTRA constants have been checked against both the 33.10 and 35.2
model-library sheets; the 33 application guide also describes its independent
network iteration. Tests exercise this common layout through the versioned
33/34/35/36 document classes. Such tests establish parser/adapter behavior, not
an independently verified 34 or 36 model-library inventory.
Research references and source-specific compatibility decisions stay here in the
import layer; native template docstrings describe the physical model. Missing
equations, ambiguous switching/reset logic, or unverified version differences
remain explicit coverage gaps rather than silently chosen behavior.

This is the mapping backlog, not a list of implemented VeraGrid bindings. It
covers **407 distinct model identifiers in the supplied PSS/E 35.2 main Model
Library**, plus **38 additional legacy identifiers in the supplied 33.10 library**:
**445 identifiers across those two main-library snapshots**. The 118 reviewed
bindings are included in those totals. A native template may already exist for a
pending model; it still needs its PSS/E schema, parameter/base mapping, connections
and validation before moving to the reviewed column.

Sources:

- [PSS/E 35.2 ModelLibrary.pdf](../../../../trunk/File_formats_docs/PSSE%20docs/DOCS%2035/ModelLibrary.pdf), model families/data sheets, excluding the final Model Functions chapter.
- [PSS/E 33.10 MODELS.pdf](../../../../trunk/File_formats_docs/PSSE%20docs/DOCS%2033/MODELS.pdf), including names absent from the 35.2 inventory.
- [PSS/E 35.2 Vendor_Specific_Models.pdf](../../../../trunk/File_formats_docs/PSSE%20docs/DOCS%2035/Vendor_Specific_Models.pdf), listed separately below.

These are versioned documentation inventories, not evidence that every identifier
is available in every installed PSS/E release or license. No 34/36 Model Library
manuals are supplied here, so completeness for those releases remains unverified.
The 35.2 main library also documents supplied user-model interfaces such as
`USRMDL`; inclusion here does not mean the name always appears directly in the
simple `BUS, MODEL, ID, CON...` DYR grammar. Header/ICON layouts must be mapped too.

#### Main library: PSS/E 35.2

“Pending” means no reviewed active import binding, including records that can be
retained by the parser. “Schema only” marks the three additional named constant
schemas already implemented. Comma-separated variants are listed individually;
their different bus/owner/zone/area/all scopes must not be collapsed into one
unconditional per-device assignment.

| Model family | Reviewed bindings | Pending bindings |
| --- | --- | --- |
| Generator Models | `GENCLS`, `GENROE`, `GENROU`, `GENSAE`, `GENSAL`, `GENTRA` | `CBEST`, `CDSMS1`, `CGEN1`, `CIMTR1`, `CIMTR2`, `CIMTR3`, `CIMTR4`, `CSMEST`, `CSTATT`, `CSVGN1`, `CSVGN3`, `CSVGN4`, `CSVGN5`, `CSVGN6`, `FRECHG`, `GENDCO`, `GENTPJ1`, `PLBVF1` |
| Compensator Models | `COMP`, `IEEEVC`, `REMCMP` | `CCOMP4A` (native template; import pending), `COMPCC` (native template; import pending) |
| Stabilizer Models | `IEE2ST`, `IEEEST` (reviewed selectors only), `PSS2A`, `PSS2B` (reviewed selectors only), `STAB1`, `STAB2A`, `STAB3`, `STAB4`, `STABNI`, `PSS2C`, `PSS3B`, `IVOST` | `BEPSST`, `OSTB2T`, `OSTB5T`, `PSS1A` (documented through IEEEST), `PSS4B`, `PSS6C`, `PSS7C`, `PTIST1`, `PTIST3`, `ST2CUT`, `STBSVC`, `SYNAXBU1` |
| Minimum Excitation Limiter Models | `MNLEX1`, `MNLEX2`, `MNLEX3` | `UEL1`, `UEL2`, `UEL2C` |
| Maximum Excitation Limiter Models | — | `BASOELU2`, `MAXEX1`, `MAXEX2`, `OEL2C`, `OEL5CU1` |
| Excitation System Models | `ESAC1A`, `ESAC2A`, `ESAC3A`, `ESAC4A`, `ESAC5A`, `ESDC1A`, `ESDC2A`, `ESST3A`, `EXAC1`, `EXAC1A`, `EXAC2`, `EXAC3`, `EXAC4`, `EXBAS`, `EXDC2`, `EXST1`, `EXST2`, `IEEET1`, `IEEET2`, `IEET1A`, `IEEEX1`, `IEEEX2`, `IEEX2A`, `SCRX`, `SEXS`, `IEEET4`, `IEEET5`, `IEEEX4`, `IEET5A`, `ESAC8B`, `EXST2A`, `ESST2A`, `BBSEX1`, `BUDCZT`, `ESST1A`, `IEEET3`, `IEEEX3`, `DC1C`, `DC2C`, `AC4C`, `DC3A`, `DC4B`, `AC1C`, `AC2C`, `AC5C`, `ST1C`, `ST7B`, `ST7C`, `ESST4B`, `IEET1B`, `EXNI`, `EXPIC1`, `ST4C`, `AC8B`, `ST5B`, `ST5C`, `AC8C`, `DC4C`, `ST6C`, `AC7B`, `AC7C` | `AC3C`, `AC6A`, `AC6C`, `AC6C2`, `AC8BBU2`, `AC9C`, `AC11C`, `CELIN`, `EMAC1T`, `ESAC6A`, `ESURRY`, `EX2000`, `EXELI`, `EXNEBB`, `EXST3`, `IVOEX`, `OEX12T`, `OEX3T`, `REXSY1`, `REXSYS`, `ST6B`, `ST8C`, `ST9C`, `ST10C`, `URHIDT`, `URST5T` |
| Turbine-Governor Models | `IVOGO`, `DEGOV`, `DEGOV1`, `DEGOV1D`, `GASTD`, `IEESGOD`, `HYGOVD`, `TGOV1D`, `GAST`, `GGOV1`, `GGOV1D` (restricted configurations), `HYGOV`, `IEEEG1`, `IEEEG1D`, `IEEEG2`, `IEEEG3`, `IEEEG3D`, `IEESGO`, `TGOV1`, `HYGOV2`, `HYGOV2D`, `PIDGOV`, `PIDGOVD` | `BBGOV1`, `CRCMGV`, `GAST2A`, `GAST2ADU`, `GASTWD`, `GASTWDD`, `GOVSTEAMEUU`, `HYGOVM`, `HYGOVR1`, `HYGOVT`, `HYG3`, `H6E1`, `PWTBD1`, `SGT8HM1`, `SGT8HS1`, `SGT2E1`, `SITGT1`, `SHAF25`, `TGOV2`, `TGOV3`, `TGOV3D`, `TGOV4`, `TGOV5`, `TURCZT`, `TWDM1T`, `TWDM2T`, `URCSCT`, `URGS3T`, `WEHGOV`, `WESGOV`, `WESGOVD`, `WPIDHY`, `WPIDHYDU`, `WSHYDD`, `WSHYGP`, `WSIEG1` |
| Turbine Load Controller Models | `LCFB1` (enabled measured-power loop with single-shaft IEEEG1) | — |
| Load Characteristic Models | — | `ACMTBLU1`, `ACMTOWU1`, `ACMTZNU1`, `ACMTARU1`, `ACMTALU1`, `CIM5BL`, `CIM5OW`, `CIM5ZN`, `CIM5AR`, `CIM5AL`, `CIM6BL`, `CIM6OW`, `CIM6ZN`, `CIM6AR`, `CIM6AL`, `CIMWBL`, `CIMWOW`, `CIMWZN`, `CIMWAR`, `CIMWAL`, `CLODBL`, `CLODOW`, `CLODZN`, `CLODAR`, `CLODAL`, `CMLDBLU2`, `CMLDOWU2`, `CMLDZNU2`, `CMLDARU2`, `CMLDALU2`, `CMLDBLDGU2`, `CMLDOWDGU2`, `CMLDZNDGU2`, `CMLDARDGU2`, `CMLDALDGU2`, `EXTLBL`, `EXTLOW`, `EXTLZN`, `EXTLAR`, `EXTLAL`, `IEELBL`, `IEELOW`, `IEELZN`, `IEELAR`, `IEELAL`, `LDFRBL`, `LDFROW`, `LDFRZN`, `LDFRAR`, `LDFRAL` |
| Load Relay Models | — | `DLSHBL`, `DLSHOW`, `DLSHZN`, `DLSHAR`, `DLSHAL`, `LDS3BL`, `LDS3OW`, `LDS3ZN`, `LDS3AR`, `LDS3AL`, `LDSHBL`, `LDSHOW`, `LDSHZN`, `LDSHAR`, `LDSHAL`, `LDSTBL`, `LDSTOW`, `LDSTZN`, `LDSTAR`, `LDSTAL`, `LVS3BL`, `LVS3OW`, `LVS3ZN`, `LVS3AR`, `LVS3AL`, `LVSHBL`, `LVSHOW`, `LVSHZN`, `LVSHAR`, `LVSHAL`, `UVUFBLU1`, `UVUFOWU1`, `UVUFZNU1`, `UVUFARU1`, `UVUFALU1` |
| Line Relay Model | — | `CIROS1`, `DISTR1`, `DPDTR1`, `RXR1`, `SCGAP2`, `SLLP1`, `SLNOS1`, `SLYPN1`, `TIOCR1` |
| Auxiliary-Signal Models | — | `CHAAUT`, `CPAAUT`, `DCCAUT`, `DCVRFT`, `FCTAXBU1`, `HVDCAT`, `PAUX1T`, `PAUX2T`, `RBKELT`, `RUNBKT`, `SQBAUT` |
| Two-Terminal dc Line Models | — | `CDC1T`, `CDC4T`, `CDC6T`, `CDC6TA`, `CDC7T`, `CDCABT`, `CEEL2T`, `CEELRIT`, `CEELT`, `CHIGATT`, `CHVDC2U1`, `CMDWAST`, `CMDWS2T`, `CMFORDT` |
| Multi-Terminal dc Line Models | — | `MTDC1T`, `MTDC2T`, `MTDC3T` |
| VSC dc Line Models | — | `HVDCPL1`, `VSCDCT` |
| FACTS Device Models | — | `CSTCNT`, `SVSMO3T2` |
| Generic Renewable Generator Models | — | `DERA1`, `PVGU1`, `REGCA1`, `REGCAU2`, `REGCBU1`, `WT1G1`, `WT2G1`, `WT3G1`, `WT3G2`, `WT4G1`, `WT4G2` |
| Generic Renewable Electrical Control Models | — | `PVEU1`, `REECA1`, `REECB1`, `REECC1`, `REECDU1`, `WT2E1`, `WT3E1`, `WT4E1`, `WT4E2` |
| Generic Renewable Drive Train Models | — | `PANELU1`, `WT12T1`, `WT3T1`, `WTDTA1` |
| Generic Renewable Pitch Control Models | — | `IRRADU1`, `WT3P1`, `WTPTA1` |
| Generic Renewable Aerodynamic Models | — | `WT12A1`, `WT12A1U_B`, `WTARA1` |
| Generic Renewable Torque Control Models | — | `WTTQA1` |
| Generic Renewable Plant Control Models | — | `REAX4BU1`, `REAX3BU1`, `REPCA1`, `REPCTA1` |
| Switched Shunt Models | — | `ABBSVC1`, `ABBSVC2`, `CHSVCT`, `CHSVCT2`, `CSSCST`, `SVSMO1T2`, `SVSMO1T3`, `SVSMO2T2`, `SVSMO2T3`, `SWSHNT`, `SWSHNT2` |
| Branch Device Models | — | `CRANIT` |
| Machine and Wind Machine Protection Models | — | `LOEXR1T`, `MCREPWU1`, `NRCGP3U`, `VPERHZU1` |
| Two-winding Transformer Device Models | — | `OLPS1T`, `OLTC1T`, `VFT1` |
| Three-winding Transformer Device Models | — | `OLPS3T`, `OLTC3T` |
| Two-terminal dc Other Models | — | `DCTC1T` |
| Bus Other Models | — | `PLNTBU1`, `GetBusPhsVLTU`, `GetBusSeqVLTU` |
| Switched Shunt Other Models | — | `SWSAXBU1` |
| Miscellaneous Other Models | — | `FRQDCAT`, `FRQTPAT`, `SAT2T`, `SWCAPT`, `VTGDCAT`, `VTGTPAT` |
| Machine Other Models | — | `TSTGOV1`, `GetGenSeqCURU` |
| Branch Other Models | — | `GetBrnSeqCURU` |

The 35.2 composite-load chapter's overview names `CMLDOWDGU2`, while its contents
and some sheet headings repeat `CMLDOWU2` in that DER family. The inventory uses
`CMLDOWDGU2` from the overview and retains `CMLDOWU2` in the ordinary composite-load
family. Confirm the actual accepted spelling from a native export before binding
the DER owner-scoped model; do not silently treat this documentation discrepancy
as an alias.

#### Additional legacy names: PSS/E 33.10

These 38 names do not occur in the 35.2 main-library inventory above. They are
separate source identifiers; nine governor wrappers now have reviewed profile-33 bindings. Similar modern names are not proof of an
alias or identical ICON/CON layout; any rename/equivalence must be established
from the applicable data sheets and source exports.

Reviewed legacy names: `GGOV1DU`, `IEEEG1SDU`, `IEEEG3DU`, `GASTDU`, `IEESGODU`, `HYGOVDU`, `TGOV1DU`, `HYGOV2DU`, `PIDGOVDU` (explicit profile-33 wrappers).

| Model family in 33.10 | Additional pending identifiers |
| --- | --- |
| Generator | `GENTPJU1`, `PLBVFU1` |
| Compensator | `CCOMP4U1` |
| Excitation System | `USAC6AU` |
| Turbine-Governor | `DEGOVIDU`, `GASTWDDU`, `HYGOVRU`, `PWTBDU1`, `TGOV3DU`, `WESGOVDU` |
| Load Characteristic | `CMLDALU1`, `CMLDARU1`, `CMLDBLU1`, `CMLDOWU1`, `CMLDZNU1` |
| VSC dc Line | `HVDCPLU1` |
| FACTS Device | `SVSMO3U2` |
| Generic Wind Generator | `REGCAU1` |
| Generic Wind Electrical | `REECAU1`, `REECBU1`, `REECCU1` |
| Generic Wind Mechanical | `WTDTAU1` |
| Generic Wind Pitch Control | `WTPTAU1` |
| Generic Wind Aerodynamic | `WTARAU1` |
| Generic Wind Auxiliary Control | `REPCAU1`, `REPCTAU1` |
| Switched Shunt | `SVSMO1U2`, `SVSMO2U2` |
| Machine Other Models | `WTTQAU1` |

#### Supplied vendor libraries: PSS/E 35.2

The separate vendor manual documents another **10 model identifiers**, all pending
native import bindings. Keep these distinct from the main-library count and from
arbitrary third-party DLL models. Availability and redistribution of a vendor
library cannot be inferred from a generic PSS/E model name.

| Vendor family | Pending bindings |
| --- | --- |
| General Electric | `GEWTGCU1`, `GEWTECU1`, `GEWTPTU1`, `GEWTARU1`, `GEWT2MU1`, `GEWTGDU1` |
| Vestas | `FCVWTU1`, `VIECPCU1`, `VIECPCU2` |
| AMSC | `CDVAR7U1` |

#### Model functions are a different backlog

Both main-library manuals also describe these **18 functions**: `BSDSCN`, `FLOW`,
`FLOW1`, `FLOW2`, `FLOW3`, `GENTMC`, `GENTMZ`, `GENTRP`, `LINESW`, `LINRCL`,
`LINTRP`, `PTOTOW`, `PTOTZN`, `PTOTAR`, `PTOTAL`, `RELAY2`, `RELAY3`, `VOLMAG`.
They are not additional DYR model bindings. Their channel, measurement, switching
or model-support semantics need separate review where a mapped model uses them.

### How the supplied ANDES checkout imports DYR

The reference inspected is `/home/santi/Descargas/andes-master`. Its relevant
files are [andes/io/psse.py](</home/santi/Descargas/andes-master/andes/io/psse.py>)
and [andes/io/psse-dyr.yaml](</home/santi/Descargas/andes-master/andes/io/psse-dyr.yaml>).
This local checkout has no Git metadata, so the observations refer to the supplied
snapshot rather than a pinned upstream commit.

ANDES separates record reading from explicit model mapping:

1. `_read_dyr_dict` joins slash-terminated records, extracts the quoted model name,
   groups records by model, and constructs numeric parameter data frames.
2. `psse-dyr.yaml` declares each source model's ordered `inputs`, its native
   `destination`, reference lookups in `find`, inherited network/model parameters
   in `get`, and assignments/transforms in `outputs`.
3. `sort_psse_models` orders mappings by their `find` dependencies so a controller
   can resolve a machine that already exists. `read_add` applies the mappings,
   adds native instances, links external parameters and warns about models outside
   the supported mapping set.

For example, GENCLS finds the static generator by `BUS` and `ID`, obtains its
rating/voltage/impedance and active status, and maps `M = 2*H`. Controller mappings
find the synchronous machine through the `SynGen` group. The useful pattern is an
explicit input layout plus dependency and parameter mappings, rather than assuming
that matching PSS/E and native names imply matching data or equations.

The YAML contains **39 PSS/E source-model entries**, plus ANDES-specific `Toggle`
and `Fault` entries. Those two event entries are not part of the PSS/E native
library inventory. The following table accounts for all 39 source mappings:

| Mapping in the supplied ANDES YAML | Source models |
| --- | --- |
| Same-name machine destinations | `GENCLS`, `GENROU` |
| Machine substitution | `GENSAL` → `GENROU` |
| Same-name voltage compensator | `IEEEVC` |
| Same-name excitation destinations | `IEEET3`, `ESST1A`, `ESAC1A`, `AC8B`, `EXAC1`, `EXAC2`, `EXAC4`, `EXDC2`, `IEEEX1`, `SEXS`, `EXST1`, `ESDC1A`, `ESDC2A`, `ESST3A`, `ESST4B`, `IEEET1` |
| Exciter substitutions | `ESAC6A`, `SCRX`, `EXPIC1` → `SEXS` |
| Same-name governor destinations | `GAST`, `TGOV1`, `HYGOV`, `IEESGO`, `IEEEG1` |
| Governor substitution | `GGOV1` → `TGOV1` |
| Same-name stabilizer destinations | `IEEEST`, `ST2CUT` |
| Same-name renewable/control destinations | `REGCA1`, `REECA1`, `REECB1`, `REPCA1`, `WTDTA1`, `WTARA1`, `WTPTA1`, `WTTQA1` |

**A YAML entry is not proof of exact model support.** The snapshot explicitly
marks GENSAL/ESAC6A and other substitutions with TODO comments. GENSAL fills
GENROU quadrature parameters from direct-axis constants; ESAC6A, SCRX and EXPIC1
only attach a SEXS destination to the machine; GGOV1 passes the machine reference
and droop to TGOV1. These mappings discard source-model structure/parameters.
VeraGrid must not copy these substitutions as exact conversions: its GENSAL binding
already uses the actual five-state model, and unsupported models must remain
reported until a reviewed equivalent exists. Same-name destinations also require
equation/initialization checks rather than automatic acceptance.

The ANDES loader evaluates YAML transform expressions with `eval`. Its mapping
structure is a useful reference, but VeraGrid should retain typed, explicit Python
bindings and should not execute expressions supplied by input files. No ANDES
code, dependency or substitution behavior is introduced by this documentation.

## Ownership, API and diagnostics

`PsseCircuit` owns the complete parsed documents in `sub_files`, `mon_files`,
`con_files`, `dyr_files`, `seq_files`, `rop_files`, `gcp_files` and `loc_files`.

- `read_raw(path, auxiliary_files=paths)` loads explicitly selected auxiliary
  files. There is no automatic discovery of neighboring files.
- `PsseCircuit.read_auxiliary_file(path)` parses and owns one auxiliary document.
- `PsseCircuit.add_auxiliary(document)` owns an already parsed document after
  checking its revision. Duplicate instances and revision mismatches are rejected.
- `psse_to_veragrid(psse_circuit, ...)` converts the network and supported auxiliary
  data. Keep the source circuit if the caller needs the conversion report.
- `PsseCircuit.auxiliary_logger` contains auxiliary load/parser diagnostics.
- `PsseCircuit.conversion_report` receives conversion outcomes and resolved
  subsystem membership. It also retains the original typed documents.

An outcome includes source, line, file format, target native idtags, an explanation
and one of `CONVERTED`, `PARTIAL`, `INVALID`, `UNRESOLVED` or `UNSUPPORTED`.
Non-converted outcomes also produce caller logger warnings. The report does not
live on `MultiCircuit` or its devices.

Documents retain insertion order within each format. Conversion applies formats
in dependency order, not arbitrary cross-format input order. Explicit bus-number
versus bus-name interpretation and SEQ minor-version choices remain caller inputs.

### Saving and round trips

RAW/RAWX exporters write network data and warn about auxiliary documents their
output omits. Auxiliary writers have not been implemented. A successful RAW
export therefore does not constitute an auxiliary-data round trip.

Converted native objects use their ordinary native persistence paths. Original
auxiliary documents and `PsseCircuit.conversion_report` are currently in-memory
source information, not a native project persistence extension. Retain the source
files when their unsupported semantics or provenance matter.

## Other PSS/E files to recognize

These are different file families, not alternative spellings of the supported
auxiliary text formats:

| File/family | Purpose | Status in this implementation |
| --- | --- | --- |
| `.sav` | Binary saved working case. | No new binary decoder; export a supported network representation from PSS/E. |
| `.snp` | Dynamic snapshot/restart state. | Not a DYR parameter file; snapshot import is outside this implementation. |
| `.out` / `.outx` | Dynamic simulation channel results. | Output/result handling is outside these network and auxiliary converters. |
| DFAX distribution-factor data | Derived study data built from the network and SUB/MON/CON definitions. | No DFAX builder or binary study-file conversion here. |
| `.sld` | PSS/E single-line diagram data. | No SLD conversion here; LOC is the supported location input. |
| `.idv`, Python scripts | Commands or automation that can change a case or run studies. | Not passive auxiliary documents; no script execution is introduced. |
| Reports and analysis-result files | Results of studies rather than definitions of network equipment. | Do not treat them as RAW or auxiliary input merely because they are text. |

## Validation and maintenance

The tests live in `src/tests/FileFormats/PSSe/`, especially
`test_psse_auxiliary_parsers.py`, `test_psse_versioned_auxiliary.py`,
`test_psse_numeric_auxiliary.py`, `test_psse_circuit_auxiliary.py` and
`test_psse_auxiliary_conversion.py`. They cover grammar boundaries, omissions,
source ownership, native values, atomic contingency handling, base conversions,
versioned common DYR bindings and dynamic equilibrium at a non-flat operating point.

Native behavior tests are in `src/tests/RMS/test_native_turbine_governors.py`,
`test_native_voltage_compensators.py`, `test_native_minimum_excitation.py`,
`test_native_static_exciter.py`, `test_native_rectifier_exciter.py`, `test_native_transient_machine.py`,
`test_native_pi_brushless_exciter.py`, `test_native_hydraulic_governor.py`, `test_native_dc_exciters.py`, `test_native_electromechanical_exciter.py`, `test_native_alternator_rectifier.py`,
`test_native_polynomial_stabilizer.py`, `test_native_power_law_machine.py`,
`test_native_saturated_salient_machine.py` and `test_native_control_persistence.py`.
These check gain/phase responses against
independent transfer functions, compensation signs and phasor invariance,
capability geometry, feedback/limiter placement, zero-time structures and native
JSON graph round trips. Generic symbolic tests check that runtime copying can
preserve explicit remote network edges while isolated editor copies remain
detached. Catalogue tests require every registered model to appear exactly once
in the editor inventory.

Run the parser, conversion, native-equation, persistence and catalogue regressions
together when changing an imported model:

```sh
.venv/bin/python -m pytest -q src/tests/FileFormats/PSSe src/tests/RMS src/tests/Base/test_symbolic.py src/tests/DynamicCatalog/test_international_standards_catalog.py
```

These checks validate the implemented equations and native assembly; they do not
establish equivalence to a source-simulator runtime trace. Provisional version
profiles still require verified source exports and model reference cases.

When extending support, update the relevant version profile or model schema,
the explicit conversion mapping, its boundary/equilibrium tests and this coverage
description together. Never infer equation compatibility from a matching library
model name, and never hide unsupported source semantics inside native devices.

### Downloaded equation research and implementation log

The maintained [research folder](../../../../trunk/dynamics/model_research/README.md)
contains the impact-based backlog, downloaded public technical reports and papers,
checksums, exact URLs, release distinctions and implementation/test evidence.
Current reviewed coverage is 118/445 identifiers; 327 inventory entries remain
pending. Downloaded documents and existing native templates do not count as
reviewed import bindings. Native catalogue size is 155 entries, including models
without reviewed DYR mappings.

Fuel-governor equation derivation and compatibility limits are maintained in the
[GGOV1 research note](../../../../trunk/dynamics/model_research/GGOV1.md), including
why total PI output slew differs from clipping only integral action. The
acceleration override's source time-step operation is not a new physical lag.

The [legacy wrapper review](../../../../trunk/dynamics/model_research/LEGACY_WRAPPERS.md)
records exact IC/IT/NI/NC/NS/NV contracts, profile boundaries and documentation
discrepancies. Unsupported IC=11 records inhibit both exact parsed machine
identities, including named buses and leading-zero LP unit IDs. Unknown user
subroutines are not activated merely because their names match native models.

The [deadband governor family review](../../../../trunk/dynamics/model_research/DEADBAND_GOVERNORS.md)
records eight additional direct/legacy bindings and the corrected nonlinear
hydro-governor equations. The [complete CSV ledger](../../../../trunk/dynamics/model_research/MODEL_COVERAGE.csv)
contains every one of the 445 source identifiers, independent native-catalogue
availability, explicit binding status and all four parser-profile layouts.
Regenerate/check it with the research-folder update_coverage.py script.

The [exciter family research note](../../../../trunk/dynamics/model_research/EXCITERS.md)
records the PID derivation, the corrected additive EXST2 coupling, the two
multiplicative variants, source calibration restrictions and independent checks.

The [cascaded/PID hydraulic family note](../../../../trunk/dynamics/model_research/HYDRAULIC_GOVERNORS.md)
records control-loop equations, source allocation contracts, water-model limits,
curve conventions, power bases and focused verification evidence.
