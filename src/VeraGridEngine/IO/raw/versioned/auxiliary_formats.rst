Standalone PSS/E auxiliary data
==============================

Public entry points are parse_seq/read_seq, parse_rop/read_rop, parse_gcp/read_gcp
and parse_loc/read_loc in their separate parser modules. The explicit version
selects concrete objects in v33 through v36. Unsupported revisions and mismatching
SEQ/GCP headers produce diagnostics. ROP and LOC contain no revision, so callers
must supply provenance. Standalone readers do not change RAW objects, generator
limits or diagrams. PsseCircuit can own their results as described below.
No new dependencies are required.

Version evidence
----------------

Manual paths below are relative to trunk/File_formats_docs/PSSE docs.
Update the version profile and boundary tests when new evidence changes a layout.

* 33 SEQ: DOCS 33/POM.pdf (33.10), section 5.5.1.
  Eight sections; generator has no REFDEG, induction has no appended
  transient/negative locked-rotor fields, switched shunts have no ID.
* 34 SEQ: PSSe 34  DataFormats.pdf (34.1), chapter 2.
  Adds system options, generator REFDEG, induction fields and legacy NCS.
  Section 2.12 describes single-record six-point NCS curves.
* 35.0 SEQ: PSSe35 DataFormats.pdf, chapter 3, especially section 3.12.
  Adds switched-shunt IDs. Legacy NCS remains single-record, six-point data.
* 35.2 SEQ: DOCS 35/DataFormats.pdf, sections 3.12 and 3.13.
  Replaces embedded NCS curves with named, continued tables (up to 20 points,
  all-zero triplet terminator), followed by generator/table references.
  Select layout_35=Sequence35Layout.V35_0 for 35.0/35.1; default is V35_2.
  REV=35 cannot identify that minor-release difference. Field counts are not
  used to guess it. 35.1 follows the legacy format identified in 35.2 notes.
* 36 SEQ: PSSe36 DataFormats.pdf (36.5), chapter 4.
  Inherits the documented 35.2 section arrangement.
* ROP: 33 POM sections 14.8.2 and 14.9; 34 DataFormats chapter 3;
  35 DataFormats chapter 4; 36 DataFormats chapter 6.
  Sixteen sections follow ICODE. Adjustable shunts use CTYP,STATUS in 33/34
  and STATUS,CTYP in 35/36. Reserve/interface/equation member lists have inner
  zero terminators; cost tables count NPAIRS points. BFID is a single-character
  string, DISP and PFLAG are real, equation/interface labels allow 32 characters.
  ROP validity is distinct from the numeric OPF status switch.
* GCP: 33 POM section 11.21.1; 35 DataFormats chapter 7;
  36 DataFormats chapter 10. The 33 format is headerless and permits an implied
  origin; 35/36 have IC,REV and require two explicit points.
  34 provisionally inherits 33: no 34-specific GCP specification was found in
  the supplied manuals. Native export validation is needed. Its format_support
  is FeatureSupport.UNVERIFIED; documented profiles expose FeatureSupport.YES.
* LOC: DOCS 33/GUI_guide.pdf (33.9), section 3.6.8;
  DOCS 35/GUI_guide.pdf, section 3.6.8; 36 DataFormats chapter 17.
  GUI 33 permits optional branch endpoints; 36 explicitly requires both.
  34/35 branch layouts provisionally inherit 33. Available 35 GUI text documents
  buses but not the complete branch grammar. Native exports must establish
  these intervening version boundaries. Their branch_layout_support is
  FeatureSupport.UNVERIFIED; 33 and 36 expose FeatureSupport.YES.

Result contract
---------------

Rows retain physical text and one-based source lines. Typed records retain
omissions as None. Logger contains lexical, grammar and domain failures;
invalid records are retained. SEQ records expose status; ROP uses validity
because STATUS is itself an OPF data field. GCP exposes curves; LOC exposes
records with block coordinate metadata. SEQ/ROP expose ordered section-tagged
records. Continued curves retain all contributing source rows.

Parsing does not establish working-case consistency or simulator compatibility.
Numeric defaults requiring a working case are not applied. Units remain those of
the file: no impedance-base conversion, projection, interpolation or OPF-cost
evaluation. GCP implicit origins are marked, not inserted into explicit points.

LOC accepts decimal degrees, hemisphere-qualified DMS (including comma-separated
parts), unit-marked DMS and three whitespace-separated signed components followed
by a coordinate delimiter. Bare comma-separated numbers are ordinary fields;
use units or a hemisphere to disambiguate comma DMS. Node coordinates are
relative offsets and receive no absolute GIS range check. Legacy branch point
roles stay unspecified: optional endpoints cannot be identified separately from
knee points. Cartesian scale is retained without inventing physical units.

PsseCircuit ownership
---------------------

PsseCircuit owns complete versioned documents in eight typed list collections:
sub_files, mon_files, con_files, dyr_files, seq_files, rop_files, gcp_files,
loc_files. Each is registered through LOCAL_PROPERTIES with PsseProperty.file_type
identifying its source grammar. Keeping documents intact retains source records,
unsupported input, change mode, version capabilities and within-file ordering.
Documents of each format are retained in insertion order; files are not merged.

Use circuit.add_auxiliary(document) for parsed data or
circuit.read_auxiliary_file(path) to parse and store it. Both check against REV,
not the inherited RawObject.version default. Revision mismatches are rejected;
accepted documents keep invalid/unsupported records and their own diagnostics.
auxiliary_logger aggregates load/parser diagnostics. Re-adding the same instance
is rejected; distinct files with repeated equipment references remain separate
documents so REPLACE/UPDATE intent is not lost.

Alternatively, read_raw(path, auxiliary_files=paths) loads explicitly selected
files in supplied order after reading RAW and merges diagnostics into the caller's
logger. There is no implicit neighboring-file discovery. Command readers inherit
auxiliary_bus_mode, initially NUMBERS; pass bus_mode explicitly to start another
interpretation. read_raw also accepts bus_mode for the first auxiliary input,
which supports externally selected BUSNAMES mode in 33/34. SEQ 35 uses the
explicit layout_35 parameter described above.

get_properties includes all registered collections; get_auxiliary_properties
selects auxiliary collections. get_class_properties remains the RAW object view
used by primary-key checks and existing network browsers. get_rawx_properties
and get_rawx_dict expose only actual RAWX network fields. RAW and RAWX exporters
report which owned auxiliary files their network-only output excludes, instead
of serializing fictitious RAWX sections or crashing on document objects.
This change does not introduce auxiliary-file writers or a persistence extension.

Conversion to MultiCircuit
--------------------------

psse_to_veragrid applies owned auxiliary documents after creating the native
network. auxiliary_to_veragrid resolves exact RAW identities, including equipment
IDs with leading zeros, and records outcomes in PsseCircuit.conversion_report.
Each outcome includes source, line, format, status, target idtags and explanation.
Original typed documents, invalid records and unsupported fields remain available
in the report. Non-converted outcomes also enter the caller's Logger. The report
belongs exclusively to the source PsseCircuit; native devices and MultiCircuit
contain only converted native data. It is currently in-memory import provenance
and is NOT serialized by native project writers. Save the source files separately.
Converted native fields, contingencies, diagrams and RMS templates use their
ordinary native persistence paths.

The reviewed native mappings are:

* SUB: named bus selections and participation weights in the report; existing RAW
  area and zone membership is preserved. Power-dependent exclusions and node
  selections require further mappings.
* MON: explicit and endpoint-based branch loading selections. Voltage/interface
  monitors, ownership/kV filters and three-winding selections remain reported.
* CON: atomic supported branch/machine/bus switching groups and ordinary SINGLE
  branch outages with exclusions. Unsupported events prevent a smaller, misleading
  contingency from being installed. Bus outages with load/shunt injections are
  unsupported by the current native contingency operation.
* SEQ: machine positive/negative/zero impedances with machine/system MVA and neutral
  impedance conversion, line zero-sequence fields, fixed shunts, and simple
  two-winding connections CC 1/2/4 and 11/12/14 without separate neutral impedances.
  CC 3/13 requires a reverse-grounded native connection that is not available.
  Included machine GSUs, three-winding/core equivalents and other fault models
  remain reported. REPLACE resets reviewed native fields; UPDATE retains omissions.
* GCP: native reactive capability curves, including implicit origins and motor
  ordering. Non-conventional WMOD curves are stored without overriding PF limits.
  UPDATE records with omitted point ordinates remain unsupported.
* ROP: hard normal bus voltage bounds and independent generator dispatch limits
  with polynomial fuel costs. Shared dispatch coupling, soft/emergency bounds,
  non-polynomial costs, interfaces, reserves and other optimizer constraints
  remain reported. Table-only UPDATE files retain source data but require explicit
  generator dispatch rows to reapply limits/costs. This is not a complete PSS/E OPF
  objective/constraint translation.
* LOC: native bus GIS coordinates, explicit geographic line paths, Cartesian
  schematics and station-local node-offset diagrams. Logical inches become 96
  scene units; physical SCALE and ambiguous legacy endpoint roles remain reported.

dyr_to_veragrid binds explicit, named CON fields to existing native RMS equations
for GENCLS, GENROU, GENROE, GENSAL, GENTRA, TGOV1, HYGOV, GAST, IEESGO, IEEEG2, SEXS, EXST1,
EXST2, EXST2A, ESST2A, ESAC8B, ESST3A, EXAC1, SCRX, STAB1, STAB2A, STAB3, STAB4, STABNI, COMP, IEEEVC, REMCMP,
MNLEX1, MNLEX2 and MNLEX3.
The reviewed DC excitation family also includes IEEET1, IEEEX1, ESDC1A, ESDC2A,
EXDC2, IEEET2, IEEEX2 and IEEX2A. Its native structures distinguish additive UEL
from high-value gates, fixed from terminal-voltage-dependent regulator limits,
and field-voltage, regulator-output and exciter-field-current rate feedback.
KE=0 and VRMAX=0 select the documented frozen initialization calibrations.
Zero supported sensing/regulator/phase lags become exact algebraic equations;
reserved Switch fields are reviewed only at zero. The equation authorities are
ModelLibrary 35.2 sheets and PAGV2 section 17.2.4, also checked against 33.10 layouts.
GENROE retains six states and uses power-law resultant-flux saturation on both
magnetic axes; it is not converted with a quadratic characteristic.
GENSAL retains its five-state machine; GENROU uses its six-state template.
GENTRA retains three states and direct-axis transient-flux saturation. Its AF
constant controls source network iteration and is retained in the source record;
it is not a physical parameter in the native simultaneous DAE solution. The
equation and iteration distinction follows PAGV2 35.2 sections 15.4.3 and 15.4.5,
including figure 15.5. EXST2 retains compound-source rectifier loading and field
limits, with algebraic zero-time transducer/regulator stages. Its regulator
output adds to bridge forcing; EXST2A multiplies them and ESST2A adds a high-value
UEL gate. The layouts have thirteen CONs in both supplied 33.10/35.2 libraries;
34 inherits the unchanged layout and 36 is provisional. A zero KI with nonzero KP
requests automatic compounding calibration and is not activated. KP=KI=0 retains
the explicitly documented unit supply. ESAC8B has fifteen CONs and distinct PID
rotating-exciter equations. Zero KE/VRMAX automatic calibration is unreviewed;
explicit coefficients, proportional-only operation and exact zero-time stages
are supported. Source identifiers never select a different physical structure
through an implicit alias. See model_research/EXCITERS.md for equation authorities.
SCRX uses separate live sensed and terminal voltages, independent/bus-fed source
selection and reverse-current crowbar discharge. TE=0 removes the regulator
state; the remaining TB phase-compensation lag must be positive. These equations
are documented in PAGV2 section 17.5.6 and independently by OPAL-RT; see the
equation-level reference ledger in PSSE_FILE_FORMATS.md.
Machine inertia, damping, impedances, governor limits/droop and current signals
are converted to the appropriate machine/system bases. Only the reviewed TA=0
ESST3A structure is activated. Exact supported zero-lag EXST1 cases become
algebraic equations rather than small time-constant approximations. ESST3A
regulator limits are explicitly bound by the adapter. Native brushless winding
equations consume live field current in commutation and demagnetization terms;
the importer does not repair those terms by promoting constant aliases.
Controller inputs and initialization are connected to the host machine; absent
controls hold their power-flow equilibrium values. Unknown, invalid, ambiguous
or unsupported neighboring models block host activation rather than silently
installing an incomplete dynamic assembly. Existing templates are never modified.

Version-specific document classes remain responsible for grammar and model
schemas. A successful parse of another library model does not imply a reviewed
native binding. Extend explicit schemas/bindings and equilibrium tests together;
never infer parameter order from a template name or the number of fields.

Supplementary stabilizers and minimum-excitation limiters feed explicit exciter
ports or summation equations. Local voltage compensation converts machine-base
current phasors; remote sensing uses explicit native network connections that
survive runtime model duplication. The zero-inertia classical machine uses fixed
rotor states with zero derivatives and retains its stator equations. GAST and
IEESGO use new native controller realizations; IEEEG2 reuses its existing native
component with the live speed-difference equation restored. COMPCC and CCOMP4A
have native templates but no activated mixed-header/cross-machine DYR binding.
The current detailed inventory is maintained in ../PSSE_FILE_FORMATS.md.

IEEEST and IEE2ST use explicit ordered integer-header schemas (two and four
ICONs respectively) before their 17 and 16 real constants. The 33.10 and 35.2
model-library sheets agree on these layouts. Native templates implement the
complete polynomial/summed-transducer filtering, phase compensation, reset
variants and compensated-voltage supervision. Reviewed measurements are rotor speed
deviation, machine-base electrical power and local/remote bus voltage. Frequency,
accelerating-power and voltage-derivative selectors remain explicit conversion
gaps. Each remote measurement has a live native network connection; supervision
always uses the host excitation system’s compensated voltage. Exciter reference initialization accounts for a
nonzero steady stabilizer output. Tests exercise versioned 33/34/35/36 parsing;
this does not independently establish a 34 or 36 library inventory.

ESAC5A uses loaded saturation samples, an independent regulator supply and
feedback from the internal exciter field-current equivalent. Its second feedback
lead-lag is bypassed when TF2 is zero, including the TF3 numerator. EXAC4 and
ESAC4A share a ten-constant layout but have different limiter structures: EXAC4
clips outside the amplifier state and offsets both bounds with field current;
ESAC4A has a non-windup amplifier, a fixed lower bound and a UEL high-value gate
after phase compensation. Their layouts and diagrams were checked against both
33.10 and 35.2; versioned parsing, native transfer functions and connected
template/runtime equilibrium are exercised separately.

GENSAE has the same twelve-constant order in the 33.10 and 35.2 model sheets.
PAGV2 35.2 figure 15.3, printed page 131, specifies its two-axis saturation and
single quadrature damper. The native model retains exactly five differential
states; the quadrature flux equation includes the resultant-flux saturation term
scaled by the quadrature/direct mutual-reactance ratio. It does not substitute
direct-axis-only GENSAL or approximate a quadrature transient circuit by a small
time constant. Native winding-equation tests and connected saturated/unsaturated
equilibrium tests cover the implementation.

EXAC1A shares the reviewed seventeen-constant forward-circuit layout with EXAC1,
but its rate feedback senses rectified field voltage. Its memory initializes at
that voltage instead of the internal exciter field-current equivalent. Positive
TR/TB/TA/TE/TF variants are reviewed; the two feedback paths have separate complex
frequency-response tests and connected template/runtime initialization tests.

ESAC1A has nineteen constants in both supplied model-library versions. Its
VAMAX/VAMIN bounds act on the amplifier state, while separate VRMAX/VRMIN bounds
act after cascaded UEL high-value and OEL low-value gates. The native builder
retains these independent locations. An absent limiter connects to its preceding
live demand, rather than a large fixed bypass value. EXAC1A and ESAC1A native
graphs have host-owned open ports, scaled phase-memory initialization and no
unused algebraic diagnostic declarations. Their catalogue initialization tests
do not require an import adapter. No OEL-model conversion is implied by exposing
the native OEL gate.

EXAC2 uses a twenty-three-constant layout shared by the supplied 33.10 and 35.2
sheets. Its direct KH feedback and KL/VLR current override act before KB and
downstream forcing clipping. Amplifier and reference initialization use
Vfe0*(KH+1/KB), while the rate-feedback memory remains at Vfe0. Tests separately
check both feedback-loop transfer functions, finite-gain current limiting and
connected saturated-host initialization. ESAC2A's different field-current stop and takeover gates have a separate
reviewed implementation.

EXAC3 has twenty-two constants in the supplied 33.10 and 35.2 sheets. Its forcing
is KR*Efd*Va and its rate feedback filters a continuous piecewise field-voltage
signal with slopes KF and KN. A minimum-voltage high-value gate precedes the
amplifier. At a positive initial Efd, amplifier demand is Vfe0/(KR*Efd0); feedback
memory initializes to the nonlinear feedback signal. Native transfer-function,
gate, nonzero-commutation and connected-host tests cover these distinctions.
An unexcited black-start reference is not defined by this initialization.

IEET1A has thirteen constants in the supplied 33.10 and 35.2 sheets. Sensed
voltage is instantaneous, TA=0 removes the regulator state algebraically, and
EFDMAX is both output ceiling and upper saturation sample. The field integrator
memory precedes external voltage clipping and feeds the rate-feedback path;
resistive/saturation losses consume the limited output. Tests distinguish this
from a bounded field-memory state, including internal windup and recovery.
Calibration follows PAGV2 section 17.5.1's explicit reference to 17.2.4; table
17.1's overview list omits IEET1A. Both explicit and calibrated source records
are covered by versioned parsing and connected initialization tests.

IEEET4, IEEET5, IEEEX4 and IEET5A have separate native reset mechanisms.
The supplied 33.10/35.2 sheets specify 11, 10, 11 and 13 constants respectively.
IEEET4 integrates a unit deadband relay divided by TRH, IEEET5 integrates
voltage error divided by TRH, and IEEEX4 normalizes its clipped error by the
forcing range and KV. IEEEX4 includes equality in rapid-action thresholds;
the other sheets draw strict inequalities. Their otherwise unspecified equality
case retains slow forcing. IEEET4's reviewed domain is 0 < KR < KV; zero-KR
records remain inspectable without automatic substitution.

IEET5A uses KA/(1+s*TRH) for positive TRH, but KA/s when TRH is zero.
Its rapid-action input is frozen initial sensed voltage minus live sensed
voltage, independent of the biased normal reference and supplementary signals.
Resistive and saturation losses consume raw field voltage before external
EFDMIN/EFDMAX output clipping. These locations differ from IEET1A. All four
models support the automatic capability/resistance calibration described by
PAGV2 sections 17.2.4 and 17.5.4. Independent slopes, transfer functions,
thresholds, reset stops, clipping, persistence and connected-host initialization
are tested. This does not establish source-simulator numerical equivalence.

ESAC2A and ESAC3A each use twenty-two constants in both supplied libraries.
They retain distinct gate units and connections: ESAC2A's UEL/OEL takeover
follows KB*(Va-KH*Vfe), whereas ESAC3A's UEL gate precedes amplifier gain
and its OEL contribution remains additive. Absent takeover limiters follow
their preceding live demand. Both field circuits have directional memory stops;
with reviewed KE > 0 and nonnegative saturation/KD, the implicit upper voltage
ceiling is equivalently detected by Vfe >= VFEMAX. No denominator evaluation or
instantaneous field-memory reset is introduced. ESAC3A also retains its VEMIN
lower stop. Independent transfer functions, gate effects, live-current ceiling
movement, inward recovery, native persistence and coupled host initialization
are covered. Source-simulator trajectory comparisons remain unavailable.

IEEEG3 uses the same fourteen constants in the supplied 33.10 and 35.2 sheets.
Its four-state hydraulic governor separates pilot-valve velocity limits from
gate-position stops and retains permanent/transient gate droop. The turbine
transfer preserves a potentially negative numerator coefficient, rather than
replacing inverse water-column response by a positive first-order lag.

The deadband variant is version-specific: the 33.10 sheet documents a
USRMDL/IEEEG3DU wrapper, while 35.2 documents a direct IEEEG3D assignment with
seventeen constants. Only the 35 schema overrides the inherited parser to
recognize that direct layout; 36 inherits it provisionally. Profiles 33/34 keep
a direct IEEEG3D record unsupported. The profile-33 wrapper has its own
reviewed calling/allocation contract, described below. Native IEEEG3D supports asymmetric continuous
speed deadband. A positive TRATE defines its turbine power base; zero selects
machine MBASE. Both reference initialization and delivered power use that base
exactly once at the network boundary. Independent transfer functions, initial
inverse response, directional stops, deadband thresholds, persistence and
connected template/runtime initialization cover the implementation.

EXBAS has twenty-one constants in both supplied libraries. Its PI controller
precedes the forward phase compensator, and its field-current feedback is shaped
by (1+s*TF1)/(1+s*TF2) before filtered differentiation. Integral memory starts
at Vfe0/KA while corrected voltage error is zero; amplifier saturation does not
silently freeze that upstream memory. The seven-state binding reviews positive
KI/TF2/KE, nonnegative KP/TF1/KF/VRMIN and positive common dynamic times.
Independent closed-loop response, integral-only/PI cases, native persistence and
coupled host initialization are tested. The common brushless amplifier now uses
the directional-stop helper at exact limits, replacing its generated expression
that admitted outward motion at equality. All eight brushless native variants
have upper/lower boundary and inward-recovery regressions.

The shared brushless field circuit has a zero lower memory stop, and two zero
saturation factors remove the saturation fit structurally. The shared rectifier
curve uses a finite inactive square-root argument so both its values and symbolic
Jacobians remain evaluable outside the middle commutation region. Calibrated
native curve coefficients remain consistent with operating-point initialization.

The shared saturated-machine initializer computes current components directly
instead of taking the phase of stator current. This preserves unloaded and
zero-active/reactive-power operating points where current phase is undefined.

Validation limits
-----------------

src/tests/FileFormats/PSSe/test_psse_numeric_auxiliary.py contains manual-derived
fixtures and malformed-input tests. These are not native PSS/E export evidence.
No PSS/E runtime or real-world files for these four formats were available.
Binary SAV/SNP/OUT, scripts, IEC and other file families are outside this change.


Reviewed dual-input and thermal-control additions
------------------------------------------------

PSS2A/PSS2B distinguish their two measurement selector/bus pairs from the final
M/N order ICONs. Reviewed selectors are speed deviation, electrical power and
local/remote AC voltage; unsupported measurements remain reported. The native
ramp tracker allocates M*N states and supports exact optional-stage bypasses.

IEEEG1 headers explicitly declare the secondary machine ID as a character ICON;
leading zeros are preserved without relaxing integer parsing for other fields.
Direct IEEEG1D is reviewed in profile 35 and provisionally inherited by 36;
profile-33 legacy user-model wrappers have separate reviewed contracts below. Single-shaft
bindings require zero secondary bus and zero secondary-shaft fractions. An
unreviewed cross-compound record inhibits both exact machine identities.

LCFB1 is a separate turbine-load-controller role in the source assembly. Enabled
measured-power operation connects to a single-shaft IEEEG1; frequency bias is
optional. Electrical setpoint, mechanical operating point and valve-reference
units remain separate, including nonunit steam fractions. Other hosts and
power-disabled operation remain unsupported. No import provenance is added to
native devices; outcomes remain in PsseCircuit.conversion_report.


GGOV1 and direct-35 GGOV1D
-------------------------

GGOV1 uses two ICONs and 33 constants in both supplied snapshots. RSELECT alone
is declared signed; other integer fields retain their nonnegative constraint.
The converter checks its four explicit feedback choices and binary fuel flag.
GGOV1D adds two asymmetric shaft-speed deadband constants in profile 35;
36 inherits provisionally. Legacy GGOV1DU wrappers remain distinct source records; profile 33 has a separate reviewed contract below.

Reviewed bindings preserve tracked speed/load regulation, fuel-speed scaling,
valve velocity and position stops, finite total-load-PI slew limits, supervisory
power reset and turbine/machine/system base conversion. Zero transport delay and
zero acceleration gain are required. Positive proportional speed gain, positive
load P/I gains and positive load measurement time are required. The load cap is
a fixed construction coefficient. Unsupported configurations inhibit activation
of the complete generator assembly. Native input order is speed, electrical
power, speed/load reference and electrical-power setpoint; persisted old graphs
are not silently rewritten. Research and test evidence live in
trunk/dynamics/model_research/GGOV1.md.


Reviewed profile-33 library user routines
---------------------------------------

UserDynamicModelSchema separates the source subroutine and payload layout from
its complete calling/allocation contract. Profile 33 reviews GGOV1DU (5,0,2,35,10,22),
IEEEG1SDU (5,0,0,23,6,3) and IEEEG3DU (5,0,0,17,4,2). Every field must match;
NS/NV do not consume payload tokens. Known ICON field types and machine-ID width
are checked before activation. Profile 34 explicitly declines inherited wrapper
permission, and 35/36 retain this restriction while reviewing direct built-ins.
Unknown user records remain parsed source data without an implicit native binding.

Original USRMDL keywords, names, headers and tokens remain intact. Only a matching
release-owned schema can select the explicit subroutine binding. Corresponding
physical kernels and base conversions are reused. Source-table discrepancies,
restrictions and test evidence are maintained in LEGACY_WRAPPERS.md.

IC=11 now retains a typed LP bus and exact character unit ID, including unquoted
leading zeros. Unsupported shared-governor records inhibit both named machines;
unrelated units at either bus remain independent. Known exact unsupported machine
targets inhibit their own host, including named-bus records. Other unresolved
records retain the prior conservative bus/source-level behavior.


Gas, steam and nonlinear hydraulic deadband family
------------------------------------------------

Direct 35/36 schemas now include GASTD (12 CON), IEESGOD (14), HYGOVD (15) and
TGOV1D (10). Profile 33 separately reviews GASTDU (5,0,0,12,3,2), IEESGODU
(5,0,0,14,5,2), HYGOVDU (5,0,0,15,4,3) and TGOV1DU (5,0,0,10,2,2).
Source names, payloads and allocation contracts remain intact. Printed URSMDL
and HYDGOVDU examples are documented errors, not automatic parser aliases.

Shared native control deadbands precede the governor loop while mechanical
damping retains raw speed deviation. The corrected HYGOV kernel uses a filtered
PI output with total desired-gate velocity/travel limits, actual-gate feedback,
a separate gate servo and exact head=(flow/gate)^2. Its reference is in speed
units and initializes as R*(Pm0/At+qNL), with positive operating gate required.
Positive TRATE selects turbine base and zero selects machine MVA; the conflicting
TGOV1D footnote and all compatibility decisions are recorded in DEADBAND_GOVERNORS.md.
MODEL_COVERAGE.csv and its update/check script track all 445 source identifiers.

The BBSEX1 source binding uses explicit bounded-regulator feedback and the supplied
zero/nonzero switch routing. Its native builder now exposes separate sensed and
terminal voltage ports; saved declarative graphs are not rewritten. BUDCZT has
release-owned layouts: supplied 33.10 places TA before TE, supplied 35.2 reverses
them. Profile 34 declines this ambiguous model, and 36 inherits 35 provisionally.
Its separate PI-memory, total-PI and field limits are not replaced by a single
limiter. The executable model coverage ledger now includes ordered ICON/CON
field names so equal-sized release layouts cannot hide a changed assignment.

HYGOV2/HYGOV2D and PIDGOV/PIDGOVD use distinct physical hydraulic kernels. Their
profile-33 HYGOV2DU/PIDGOVDU wrappers preserve exact calling/allocation contracts,
including the PID feedback ICON. Direct deadband variants remain profile-35
layouts with provisional 36 inheritance. Parent layouts match the supplied
33.10/35.2 sheets and are inherited by 34. Gate/power characteristic inversion,
independent initial mechanical/electrical power, isochronous references, turbine
ratings and raw-speed damping are explicit. Native PID curve extrapolation uses
the outer linear segments and is documented; source-runtime extrapolation has
not been compared. See model_research/HYDRAULIC_GOVERNORS.md.

PSS2C has an explicit profile-35 six-ICON/twenty-nine-CON layout, with provisional
36 inheritance; its continuous mapping requires PSSON<0 and supported selected
measurements/first washouts. PSS3B matches the supplied four-ICON/seventeen-CON
33/35 layouts and reuses exact quadratic polynomial stages. ESST1A matches both
supplied two-ICON/eighteen-CON layouts and preserves all UEL/VOS signal locations.
IEEET3/IEEEX3 have distinct total-forcing/supply capability locations and a shared
square-root transformer-loading law; their explicit twelve-CON layouts are
reviewed, with source KI=0 calibration still unsupported. Native crossed-field
capability and turbine-curve extrapolation conventions are documented in the
research notes; they are not presented as source-runtime equivalence evidence.

DC1C/DC2C and AC4C have explicit profile-35 ICON layouts with provisional 36
inheritance, without inferring unsupported 33/34 contracts. DC3A has matching
supplied 33/35 twelve-CON layouts. Their physical limiter locations, rheostat
threshold equality and field-memory stops remain explicit; automatic bounded
rotating-exciter calibration and source OEL controllers are still unsupported.

DC4B preserves the matching supplied 33/35 eighteen-CON/two-ICON source layouts,
with profile-34 inheritance and provisional 36 support. Its bounded PID memory,
terminal-scaled amplifier capability, limiter locations and actual terminal-voltage
initialization remain separate from the unlimited ESAC8B PID arrangement.

AC1C/AC2C/AC5C have explicit profile-35 two-ICON layouts with respectively
21/23/19 constants and provisional 36 inheritance. Earlier profiles remain
unsupported. The reviewed source domain and distinct winding-feedback topologies
are documented in the research notes. AC3C's supplied 28-versus-22-CON contract
conflict remains unresolved; no source binding is activated for that model.

ST1C has an explicit profile-35 UEL/VOS/OEL three-ICON/eighteen-CON contract.
ST7B's fourteen-CON/two-ICON contract agrees in supplied 33/35 sheets; ST7C has
an explicit profile-35 fifteen-CON/two-ICON contract. ST7C's firing-control state
and reference/output gate order are preserved rather than inferred as aliases.
Source OEL-controller conversion and extreme crossed-bound runtime conventions
remain unreviewed, as documented in the model-research notes.

ESST4B's seventeen-CON contract agrees in supplied 33/35 sheets and maps to a
reviewed native cascaded-PI compound-source controller. Proportional-only and
pure-integral loop variants and explicit potential-only KI=0 are supported;
automatic rules from other transformer models are not inferred for this model.

IEET1B's eighteen-CON and EXNI's ten-CON layouts agree in supplied 33/35 sheets.
Their profile-34 inheritance is layout-based; 36 is provisional. IEET1B retains
Switch/Xe as constants and its source-specific feedback meaning. EXNI conversion
requires the documented bidirectional R=0 configuration; nonzero reverse-current
logic remains explicitly unsupported. Neither rule is inferred from another
simulator's labels or a similarly named controller.

EXPIC1 has matching supplied 33/35 twenty-four-CON layouts with inherited 34 and
provisional 36 support. Its explicit KP=KI=0 unit supply and TE=0 direct-field
forcing cases are structural alternatives, not borrowed calibration rules.
The separate PI/regulator/field-forcing capabilities remain distinct.

Delayed engine governors
~~~~~~~~~~~~~~~~~~~~~~~

DEGOV and DEGOV1 have matching supplied 33/35 ten/twelve-CON layouts; DEGOV1
adds a throttle/electrical-feedback ICON. Direct DEGOV1D is reviewed in 35,
with DBH/DBL/TRATE appended. The explicit 33 DEGOV1DU user contract has IC=5,
IT=0, NI=1, NC=15, NS=6 and NV=15. Later wrappers remain unreviewed.
The source heading DEGOVIDU is not silently substituted for DEGOV1DU.

Native conversion preserves the electronic control box, three actuator
memories, bounded throttle and combustion transport delay. Mechanical torque
and power are separate; the machine consumes torque. Positive delay uses the
existing held accepted-step history, so numerical resolution depends on time
step. Native zero delay is algebraic; imported sheets require positive TD.
See the delayed-engine research note for equations, limitations and evidence.

Filtered cascaded PI static excitation
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

ST4C has an explicit 35-only schema with five ICONs and twenty-one CONs; 36
inherits it provisionally. Earlier profiles do not receive that modern layout.
The native model separates outer/inner PI limits, bounded firing lag and capped
filtered feedback from VA before field-supply multiplication. Independent
potential is KP. PSS selection 2 adds between the input UEL and OEL gates.

The source's SCL signals are explicitly documented as unused; their valid
selection remains parsed source data. An absent take-over limiter bypasses its
actual moving pre-gate signal. Compatible MNLEX controllers connect at the selected additive or take-over
location; initial gates/capabilities must admit the operating point.
See FILTERED_COMPOUND_PI_EXCITATION.md for equations and validation boundaries.

Bounded PID brushless excitation
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

AC8B uses matching supplied 33/35 twenty-one-CON direct layouts without ICONs;
34 inherits the unchanged contract and 36 remains provisional. The native
implementation separates bounded PID, bounded amplifier, saturated winding and
loaded diode bridge. Initial internal voltage inverts each conducting commutation
branch instead of treating delivered field as winding voltage. Live rotor current
drives both demagnetization and bridge loading. Positive KE and feasible current
ceiling/capabilities are required. Exact rounded commutation transition/gap cases
and vendor transient comparisons remain unverified. See PID_BRUSHLESS_EXCITATION.md.

Parallel-channel static excitation
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

ST5B has matching supplied 33/35 eighteen-CON direct records without ICONs;
34 inherits that contract and 36 remains provisional. Three two-stage bounded
lead-lag channels evolve continuously, with high/low gate activity selecting
the appropriate output. Bounded stage memory tracks clipped output through
its numerator time, following the documented mathematical elementary block.
The final field lag/capability uses actual terminal magnitude, independently
of compensated sensing. Absent limiters bypass moving pre-gate signals;
actual compatible MNLEX signals connect at the take-over point. Initial gate
capabilities must admit the operating point. ST5C additive
channel-activity configurations remain pending. See PARALLEL_CHANNEL_EXCITATION.md.

Rational power damping and speed regulation
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

IVOST/IVOGO have matching supplied 33/35 twenty-one-CON direct layouts; 34
inherits that order and 36 is provisional. The first two rational stages track
bounded output; the last clips unrestricted memory. IVOST uses actual electrical
power and preserves its steady auxiliary bias. IVOGO balances turbine load
backward through stable/integral stages, freezes symbolic initial demands and
exposes separate mechanical power and torque. The machine receives torque after
explicit speed/base conversion. Source zero-origin, free zero-gain integral and
bounded positive-lead PI degenerations remain declined until their source
initialization/anti-windup conventions are reviewed. See RATIONAL_FILTER_CONTROLS.md.

ST5C adds the explicitly reviewed 35 eighteen-CON/two-ICON OEL/UEL layout; 36
inherits provisionally. Each selector chooses signed reference summation or
takeover. Only a strict gate winner activates its dedicated channel. Reference
initialization includes actual summed auxiliary bias. Earlier source profiles
remain unreviewed. Native devices retain no source provenance.

AC8C has an explicit supplied-35 twenty-seven-CON/five-ICON contract; 36 is
provisional and earlier layouts remain unreviewed. Its compound source bridge
is loaded by exciter winding VFE, while the output bridge uses generator IFD.
Limiter gates act before PID or between PID and amplifier. The source-declared
unused SCL signals are not silently connected. See COMPOUND_PID_EXCITATION.md.

DC4C and ST6C use explicit supplied-35 contracts (36 provisional), without
backfilling 33/34. DC4C retains the literal printed KJR integral label separately
from potential KI and declines KE=0 automatic calibration. ST6C names the
duplicated second VMMAX entry VMMIN, supported by the independent firing diagram.
Its four limiter locations and live regulator-current ceiling remain distinct
from ST6B. Depicted source-unused SCL signals are not silently activated.
See COMPOUND_COMMUTATOR_EXCITATION.md and CURRENT_LIMITED_FIELD_EXCITATION.md.

AC7B has matching supplied-33/35 twenty-seven-CON layouts without ICONs; 34
inherits and 36 is provisional. KP=0 explicitly bypasses terminal multiplication
with unity supply. Winding-current rate feedback, mixed voltage/current feedback
and the negative forcing floor remain distinct from AC8B and modern AC7C.
Automatic KE calibration is declined. See CASCADED_BRUSHLESS_EXCITATION.md.

AC7C has an explicit supplied-35 thirty-three-CON/six-ICON schema; earlier
profiles remain unreviewed and 36 is provisional. The direct identifier follows
the literal record, not the AC7CU1 sheet title. Five takeover points and both
compound/live-field power arrangements are explicit. The ambiguous KP=0 source
convention when rectified potential is selected remains declined. No wrapper
header is inferred. See CASCADED_BRUSHLESS_EXCITATION.md.
