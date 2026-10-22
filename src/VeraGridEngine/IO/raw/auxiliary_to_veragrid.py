# SPDX-License-Identifier: MPL-2.0
"""Apply source-owned auxiliary data after RAW devices exist.

Only explicit native equivalents are applied. Unrepresented semantics remain in
PsseCircuit.conversion_report with source records and diagnostics.
"""
from __future__ import annotations
from copy import copy
import numpy as np
from VeraGridEngine import Devices as dev
from VeraGridEngine.Devices.multi_circuit import MultiCircuit
from VeraGridEngine.Devices.Parents.editable_device import EditableDevice
from VeraGridEngine.Devices.Diagrams.schematic_diagram import SchematicDiagram
from VeraGridEngine.Devices.Diagrams.graphic_location import GraphicLocation
from VeraGridEngine.IO.raw.psse_circuit import PsseCircuit
from VeraGridEngine.IO.raw.psse_file_type import PsseFileType
from VeraGridEngine.IO.raw.psse_data import ChangeMode
from VeraGridEngine.IO.raw.raw_types import RawGeneratorLike, RawTransformerLike, RawNodeLike
from VeraGridEngine.IO.raw.psse_conversion_report import (
    PsseConversionEntry, PsseConversionStatus, PsseImportReport, PsseResolvedSubsystem,
)
from VeraGridEngine.IO.raw.versioned.base.auxiliary import (
    BusIdentifier, BranchReference, Selection, SelectionKind, RecordStatus,
    EquipmentKind,
)
from VeraGridEngine.IO.raw.versioned.base.sub import SubOperation, SubOperationKind
from VeraGridEngine.IO.raw.versioned.base.mon import MonitoringDefinition, MonitorKind
from VeraGridEngine.IO.raw.versioned.base.con_ import Contingency, ContingencyEvent, EventAction, AutomaticContingency, AutomaticKind, ContingencySkip, ContingencyCategory
from VeraGridEngine.IO.raw.versioned.base.seq_records import SequenceEntry, SequenceGenerator, SequenceBranch, SequenceFixedShunt, SequenceTransformer
from VeraGridEngine.IO.raw.versioned.base.rop_records import (
    RopEntry, RopBusVoltage, RopGeneratorDispatch, RopActiveDispatch, RopPolynomialCost,
)
from VeraGridEngine.IO.raw.versioned.base.loc import CoordinateSystem, LocationKind, BranchLocationLayout, LocationPoint
from VeraGridEngine.basic_structures import Logger
from VeraGridEngine.enumerations import ContingencyOperationTypes, WindingsConnection


class PsseAuxiliaryConverter:
    """Exact RAW identity lookups and a source-located conversion ledger."""
    __slots__ = ('source', 'grid', 'logger', 'buses', 'names', 'generators', 'raw_generators',
                 'branches', 'subsystems', 'entries', 'resolved_subsystems')

    def __init__(self, source: PsseCircuit, grid: MultiCircuit,
                 buses: dict[int, dev.Bus], logger: Logger) -> None:
        """Index canonical native objects, rejecting ambiguous textual identities.

        :param source: Parsed PSS/E network and auxiliary documents.
        :param grid: Completed native network.
        :param buses: Existing RAW bus-number to native bus mapping.
        :param logger: Conversion diagnostic destination.
        """
        self.source: PsseCircuit = source
        self.grid: MultiCircuit = grid
        self.logger: Logger = logger
        self.buses: dict[int, dev.Bus] = buses
        self.names: dict[str, list[int]] = dict()
        self.generators: dict[tuple[int, str], dev.Generator] = dict()
        self.raw_generators: dict[tuple[int, str], RawGeneratorLike] = dict()
        self.branches: dict[tuple[int, int, str], list[EditableDevice]] = dict()
        self.subsystems: dict[str, set[int]] = dict()
        self.entries: list[PsseConversionEntry] = list()
        self.resolved_subsystems: list[PsseResolvedSubsystem] = list()
        for bus in source.buses:
            for name in (bus.NAME.strip(), f'{bus.NAME.strip()} {bus.BASKV:g}'):
                candidates: list[int] | None = self.names.get(name, None)
                if candidates is None:
                    self.names[name] = [bus.I]
                elif bus.I not in candidates:
                    candidates.append(bus.I)
                else:
                    pass
        # RAW conversion generates this exact code, including leading-zero IDs.
        by_code: dict[str, list[dev.Generator]] = dict()
        for generator in grid.generators:
            by_code.setdefault(generator.code, list()).append(generator)
        for raw in source.generators:
            code: str = str(raw.I) + '_' + str(raw.ID).replace("'", '')
            matches: list[dev.Generator] = by_code.get(code, list())
            if len(matches) == 1:
                key: tuple[int, str] = (raw.I, str(raw.ID).replace("'", '').strip())
                if key not in self.generators:
                    self.generators[key] = matches[0]
                    self.raw_generators[key] = raw
                else:
                    self.generators.pop(key, None)
                    self.raw_generators.pop(key, None)
                    logger.add_error('Ambiguous PSS/E machine identity', device=code)
            else:
                logger.add_error('Cannot resolve PSS/E machine to native generator', device=code)
        native_by_id: dict[str, EditableDevice] = dict((item.idtag, item) for item in grid.get_branches(add_hvdc=True))
        for collection in (source.branches, source.transformers, source.switches):
            for raw_branch in collection:
                native: EditableDevice | None = native_by_id.get(raw_branch.idtag, None)
                if native is not None:
                    branch_key: tuple[int, int, str] = (raw_branch.I, raw_branch.J, str(raw_branch.CKT).replace("'", '').strip())
                    self.branches.setdefault(branch_key, list()).append(native)
                else:
                    pass

    def record(self, source: str, line: int, file_type: PsseFileType,
               status: PsseConversionStatus, targets: tuple[EditableDevice, ...], message: str) -> None:
        """Retain a conversion outcome and report unapplied semantics.

        :param source: Input file label.
        :param line: Source line.
        :param file_type: Source grammar.
        :param status: Conversion outcome.
        :param targets: Canonical native objects affected.
        :param message: Mapping or limitation.
        """
        self.entries.append(PsseConversionEntry(source, line, file_type, status,
                                                tuple(item.idtag for item in targets), message))
        if status != PsseConversionStatus.CONVERTED:
            self.logger.add_warning(message, device=source, value=line, device_class=file_type.name)
        else:
            pass

    def bus_number(self, reference: BusIdentifier | None) -> int | None:
        """Resolve a bus reference without arbitrarily selecting duplicate names.

        :param reference: Numeric or extended-name reference.
        :return: Unique existing RAW bus number, or None.
        """
        if reference is None:
            return None
        elif reference.number is not None:
            return reference.number if reference.number in self.buses else None
        else:
            candidates: list[int] = self.names.get(reference.name or '', list())
            return candidates[0] if len(candidates) == 1 else None

    def branch(self, reference: BranchReference | None) -> EditableDevice | None:
        """Resolve an unoriented two-terminal reference, preserving parallel IDs.

        :param reference: Parsed branch terminals and identifier.
        :return: Unique native branch; three-winding references remain unsupported.
        """
        if reference is None or len(reference.buses) != 2 or reference.substation is not None:
            return None
        else:
            first: int | None = self.bus_number(reference.buses[0])
            second: int | None = self.bus_number(reference.buses[1])
            if first is None or second is None:
                return None
            else:
                matches: list[EditableDevice] = list(self.branches.get((first, second, reference.circuit.strip()), list()))
                if first != second:
                    matches.extend(self.branches.get((second, first, reference.circuit.strip()), list()))
                else:
                    pass
                return matches[0] if len(matches) == 1 else None

    def select(self, selection: Selection | None) -> set[int] | None:
        """Evaluate a documented bus selector in the original RAW numbering.

        :param selection: Parsed selection.
        :return: Matching numbers, or None for unresolved/unsupported selection.
        """
        if selection is None:
            return None
        elif selection.kind == SelectionKind.SUBSYSTEM:
            found: set[int] | None = self.subsystems.get(selection.label or '', None)
            return set(found) if found is not None else None
        elif selection.kind == SelectionKind.ALL_BUSES:
            return set(self.buses)
        elif selection.kind == SelectionKind.ALL_NODES:
            return None  # Node selectors require the substation topology, not the RAW bus set.
        elif selection.kind == SelectionKind.BUS:
            first: int | None = self.bus_number(selection.bus)
            last: int | None = self.bus_number(selection.last_bus) if selection.last_bus is not None else first
            if first is None or last is None:
                return None
            else:
                return set(number for number in self.buses if min(first, last) <= number <= max(first, last))
        else:
            members: set[int] = set()
            low: float | int | None = selection.first
            high: float | int | None = selection.last if selection.last is not None else low
            if low is None or high is None:
                return None
            else:
                for raw in self.source.buses:
                    value: float | int | None = None
                    if selection.kind == SelectionKind.AREA:
                        value = raw.AREA
                    elif selection.kind == SelectionKind.ZONE:
                        value = raw.ZONE
                    elif selection.kind == SelectionKind.OWNER:
                        value = raw.OWNER
                    elif selection.kind == SelectionKind.KV:
                        value = raw.BASKV
                    else:
                        return None
                    if low <= value <= high and raw.I in self.buses:
                        members.add(raw.I)
                    else:
                        pass
                return members

    def subsystem_operations(self, operations: tuple[SubOperation, ...]) -> set[int] | None:
        """Apply ordered union, JOIN intersection and exclusion.

        :param operations: Ordered source subsystem operations.
        :return: Complete bus membership, or None if any criterion is unsupported.
        """
        result: set[int] = set()
        for operation in operations:
            members: set[int] | None
            if operation.kind == SubOperationKind.PARTICIPATE:
                members = set()
            elif operation.kind == SubOperationKind.JOIN:
                members = set(self.buses)
                for child in operation.children:
                    child_members: set[int] | None = self.select(child.selection)
                    if child_members is None:
                        return None
                    else:
                        members.intersection_update(child_members)
            elif operation.kind == SubOperationKind.EXCLUDE and operation.quantity is not None:
                return None  # Power-dependent SKIP needs a separately reviewed aggregation rule.
            else:
                members = self.select(operation.selection)
            if members is None:
                return None
            elif operation.kind == SubOperationKind.EXCLUDE:
                result.difference_update(members)
            else:
                result.update(members)
        return result

    def convert_subsystems(self) -> None:
        """Resolve named source selections while preserving native area/zone membership."""
        for document in self.source.sub_files:
            for subsystem in document.subsystems:
                members: set[int] | None = self.subsystem_operations(subsystem.operations) if subsystem.status == RecordStatus.VALID else None
                if members is None:
                    self.record(document.source, subsystem.record.line_number, PsseFileType.SUB,
                                PsseConversionStatus.UNRESOLVED, (), 'Subsystem contains invalid or unresolved selection criteria')
                else:
                    self.subsystems[subsystem.label] = members
                    weights: dict[int, float] = dict()
                    unresolved_weights: bool = False
                    for operation in subsystem.operations:
                        if operation.kind == SubOperationKind.PARTICIPATE:
                            for weight in operation.weights:
                                number: int | None = self.bus_number(weight.bus)
                                if number is not None and number in members:
                                    weights[number] = weight.factor
                                else:
                                    unresolved_weights = True
                        else:
                            pass
                    ordered: tuple[int, ...] = tuple(number for number in self.buses if number in members)
                    self.resolved_subsystems.append(PsseResolvedSubsystem(subsystem.label,
                        tuple(self.buses[number].idtag for number in ordered),
                        tuple(weights.get(number, 0.0) for number in ordered) if weights else ()))
                    self.record(document.source, subsystem.record.line_number, PsseFileType.SUB,
                                PsseConversionStatus.PARTIAL if unresolved_weights else PsseConversionStatus.CONVERTED,
                                tuple(self.buses[number] for number in ordered),
                                'Resolved subsystem membership; unresolved/outside participation bus retained' if unresolved_weights else 'Resolved subsystem membership')

    def convert_sequences(self) -> None:
        """Apply native sequence fields on system base, retaining unmatched network models."""
        neutrals: dict[tuple[int, str], complex] = dict()
        grounded_paths: set[tuple[int, str]] = set()
        for document in self.source.seq_files:
            if document.change == ChangeMode.REPLACE:
                neutrals.clear()
                grounded_paths.clear()
                for key, generator in self.generators.items():
                    raw: RawGeneratorLike = self.raw_generators[key]
                    if raw.MBASE > 0 and not raw.XT:
                        generator.R1 = generator.R2 = generator.R0 = raw.ZR * self.grid.Sbase / raw.MBASE
                        generator.X1 = generator.X2 = generator.X0 = raw.ZX * self.grid.Sbase / raw.MBASE
                    else:
                        pass
                for line in self.grid.lines:
                    line.R0 = line.X0 = line.B0 = line.G0 = 0.0
                for shunt in self.grid.shunts:
                    shunt.G0 = shunt.B0 = 0.0
                for transformer in self.grid.transformers2w:
                    transformer.conn = WindingsConnection.DD
                    transformer.R0 = transformer.X0 = 0.0
            else:
                pass
            for record in document.records:
                entry: SequenceEntry = record.data
                target: EditableDevice | None = None
                status: PsseConversionStatus = PsseConversionStatus.UNSUPPORTED
                message: str = 'Sequence record has no reviewed native equivalent'
                if entry.status != RecordStatus.VALID:
                    status = PsseConversionStatus.INVALID
                    message = 'Invalid sequence record retained without application'
                elif isinstance(entry, SequenceGenerator):
                    key: tuple[int | None, str] = (entry.bus, (entry.machine_id or '1').strip())
                    generator: dev.Generator | None = self.generators.get(key, None)
                    raw = self.raw_generators.get(key, None)
                    if generator is not None and raw is not None and raw.MBASE > 0 and not raw.XT and (entry.grounding_code != 2 or self.buses[entry.bus].Vnom > 0):
                        target = generator
                        factor: float = self.grid.Sbase / raw.MBASE
                        initial: bool = document.change == ChangeMode.REPLACE
                        previous_neutral: complex = neutrals.get(key, 0j)
                        # R0/X0 are total terminal impedance in the native model.
                        if key in grounded_paths:
                            generator.R0 -= 3.0 * previous_neutral.real
                            generator.X0 -= 3.0 * previous_neutral.imag
                        else:
                            pass
                        r: float = entry.r_positive if entry.r_positive is not None else raw.ZR
                        x: float = entry.x_subtransient if entry.x_subtransient is not None else raw.ZX
                        if initial or entry.r_positive is not None:
                            generator.R1 = r * factor
                        else:
                            pass
                        if initial or entry.x_subtransient is not None:
                            generator.X1 = x * factor
                        else:
                            pass
                        if initial or entry.r_negative is not None:
                            generator.R2 = (entry.r_negative if entry.r_negative is not None else r) * factor
                        else:
                            pass
                        if initial or entry.x_negative is not None:
                            generator.X2 = (entry.x_negative if entry.x_negative is not None else x) * factor
                        else:
                            pass
                        if initial or entry.r_zero is not None:
                            generator.R0 = (entry.r_zero if entry.r_zero is not None else r) * factor
                        else:
                            pass
                        if initial or entry.x_zero is not None:
                            generator.X0 = (entry.x_zero if entry.x_zero is not None else x) * factor
                        else:
                            pass
                        ground_factor: float = factor
                        if entry.grounding_code == 2:
                            bus: dev.Bus = self.buses[entry.bus]
                            ground_factor = self.grid.Sbase / bus.Vnom ** 2
                        else:
                            pass
                        next_neutral: complex = complex(entry.r_ground * ground_factor if entry.r_ground is not None else previous_neutral.real,
                                                        entry.x_ground * ground_factor if entry.x_ground is not None else previous_neutral.imag)
                        neutrals[key] = next_neutral
                        if generator.R0 != 0 or generator.X0 != 0:
                            generator.R0 += 3.0 * next_neutral.real
                            generator.X0 += 3.0 * next_neutral.imag
                            grounded_paths.add(key)
                        else:
                            grounded_paths.discard(key)
                        status = PsseConversionStatus.PARTIAL if entry.x_transient is not None or entry.x_synchronous is not None or entry.reference_angle is not None else PsseConversionStatus.CONVERTED
                        message = 'Applied machine sequence impedance on system MVA base; extra fault parameters retained' if status == PsseConversionStatus.PARTIAL else 'Applied machine sequence impedance on system MVA base'
                    else:
                        status = PsseConversionStatus.UNRESOLVED
                        message = 'Sequence machine missing, has invalid MBASE, or includes an unrepresented GSU transformer'
                elif isinstance(entry, SequenceBranch):
                    reference: BranchReference = BranchReference()
                    reference.buses = (BusIdentifier(entry.from_bus, None), BusIdentifier(entry.to_bus, None))
                    reference.circuit = entry.circuit or '1'
                    branch: EditableDevice | None = self.branch(reference)
                    if isinstance(branch, dev.Line):
                        target = branch
                        if entry.r_zero is not None or document.change == ChangeMode.REPLACE:
                            branch.R0 = entry.r_zero or 0.0
                        else:
                            pass
                        if entry.x_zero is not None or document.change == ChangeMode.REPLACE:
                            branch.X0 = entry.x_zero or 0.0
                        else:
                            pass
                        if entry.b_zero is not None or document.change == ChangeMode.REPLACE:
                            branch.B0 = entry.b_zero or 0.0
                        else:
                            pass
                        status = PsseConversionStatus.PARTIAL if any((entry.g_from, entry.b_from, entry.g_to, entry.b_to, entry.short_circuit_type)) else PsseConversionStatus.CONVERTED
                        message = 'Applied line zero-sequence series impedance and charging; terminal shunts/MOV data retained' if status == PsseConversionStatus.PARTIAL else 'Applied line zero-sequence parameters'
                    else:
                        status = PsseConversionStatus.UNRESOLVED
                        message = 'Sequence branch does not resolve to one native line'
                elif isinstance(entry, SequenceTransformer) and entry.third_bus in (None,0):
                    reference = BranchReference()
                    reference.buses = (BusIdentifier(entry.from_bus,None),BusIdentifier(entry.to_bus,None))
                    reference.circuit = entry.circuit or '1'
                    transformer: EditableDevice | None = self.branch(reference)
                    raw_matches: list[RawTransformerLike] = [item for item in self.source.transformers if item.I == entry.from_bus and item.J == entry.to_bus and str(item.CKT).strip() == reference.circuit and not item.K]
                    connections: dict[int,WindingsConnection] = dict([(1,WindingsConnection.GG),(11,WindingsConnection.GG),
                        (2,WindingsConnection.GD),(12,WindingsConnection.GD),
                        (4,WindingsConnection.DD),(14,WindingsConnection.DD)])
                    connection: WindingsConnection | None = connections.get(entry.connection_code if entry.connection_code is not None else 14,None)
                    if isinstance(transformer,dev.Transformer2W) and len(raw_matches) == 1 and connection is not None and not any((entry.r_ground_1,entry.x_ground_1,entry.r_ground_2,entry.x_ground_2,entry.r_zero_2,entry.x_zero_2,entry.r_neutral,entry.x_neutral)):
                        raw_transformer: RawTransformerLike = raw_matches[0]
                        voltage: float = raw_transformer.NOMV1 or self.buses[entry.from_bus].Vnom
                        base: float = self.grid.Sbase if entry.impedance_code in (None,1) else raw_transformer.SBASE1_2
                        if base > 0 and self.buses[entry.from_bus].Vnom > 0:
                            factor = self.grid.Sbase/base*(voltage/self.buses[entry.from_bus].Vnom)**2
                            if entry.r_zero_1 is not None:
                                transformer.R0 = entry.r_zero_1*factor
                            else:
                                pass
                            if entry.x_zero_1 is not None:
                                transformer.X0 = entry.x_zero_1*factor
                            else:
                                pass
                            if entry.connection_code is not None or document.change == ChangeMode.REPLACE:
                                transformer.conn = connection
                            else:
                                pass
                            target = transformer
                            status = PsseConversionStatus.CONVERTED
                            message = 'Applied simple two-winding zero-sequence topology and winding impedance'
                        else:
                            status = PsseConversionStatus.UNRESOLVED
                            message = 'Transformer sequence MVA/voltage base is invalid'
                    else:
                        message = 'Transformer sequence connection/neutral network needs a native multi-impedance equivalent'
                elif isinstance(entry, SequenceFixedShunt):
                    candidates: list[dev.Shunt] = [shunt for shunt in self.grid.shunts if shunt.code == f'{entry.bus}_{entry.shunt_id}']
                    if len(candidates) == 1:
                        shunt: dev.Shunt = candidates[0]
                        target = shunt
                        if entry.g_zero is not None or document.change == ChangeMode.REPLACE:
                            shunt.G0 = entry.g_zero or 0.0
                        else:
                            pass
                        if entry.b_zero is not None or document.change == ChangeMode.REPLACE:
                            shunt.B0 = entry.b_zero or 0.0
                        else:
                            pass
                        status = PsseConversionStatus.CONVERTED
                        message = 'Applied fixed-shunt zero-sequence admittance'
                    else:
                        status = PsseConversionStatus.UNRESOLVED
                        message = 'Sequence fixed shunt not uniquely resolved'
                else:
                    pass
                self.record(document.source, entry.row.line_number, PsseFileType.SEQ, status,
                            (target,) if target is not None else (), message)

    def convert_capabilities(self) -> None:
        """Install ordered native Q curves, including the documented legacy origin."""
        for document in self.source.gcp_files:
            if document.change == ChangeMode.REPLACE:
                for generator in self.generators.values():
                    generator.q_curve.make_default_q_curve(generator.Snom, generator.qmin_set, generator.qmax_set, n=1)
                    generator.use_reactive_power_curve = False
            else:
                pass
            for curve in document.curves:
                target: dev.Generator | None = self.generators.get((curve.bus, (curve.machine_id or '1').strip()), None)
                if curve.status != RecordStatus.VALID:
                    self.record(document.source, curve.row.line_number, PsseFileType.GCP, PsseConversionStatus.INVALID, (), 'Invalid capability curve retained')
                elif target is None:
                    self.record(document.source, curve.row.line_number, PsseFileType.GCP, PsseConversionStatus.UNRESOLVED, (), 'Capability machine not uniquely resolved')
                elif document.change == ChangeMode.UPDATE and any(point.q_min is None or point.q_max is None for point in curve.points):
                    self.record(document.source, curve.row.line_number, PsseFileType.GCP, PsseConversionStatus.UNSUPPORTED, (target,), 'GCP update with omitted Q fields needs PSS/E point-index update semantics')
                else:
                    points: list[tuple[float, float, float]] = list()
                    for point in curve.points:
                        if point.p is not None:
                            points.append((point.p, point.q_min or 0.0, point.q_max or 0.0))
                        else:
                            pass
                    if curve.implicit_origin and points:
                        points.insert(0, (0.0, points[0][1], points[0][2]))
                    else:
                        pass
                    array: np.ndarray = np.asarray(points, dtype=float)
                    array = array[np.argsort(array[:, 0])]
                    target.q_curve.set(array)
                    raw: RawGeneratorLike = self.raw_generators[(curve.bus, (curve.machine_id or '1').strip())]
                    target.use_reactive_power_curve = raw.WMOD <= 1
                    self.record(document.source, curve.row.line_number, PsseFileType.GCP, PsseConversionStatus.CONVERTED, (target,), 'Applied native generator P/Q capability curve in MW/Mvar')

    def convert_locations(self) -> None:
        """Apply geographic bus/path coordinates without confusing diagram inches with pixels."""
        for document in self.source.loc_files:
            # A declared drawing transform keeps inches out of geographic fields.
            pixels_per_inch: float = 96.0
            diagram: SchematicDiagram = SchematicDiagram(name='PSS/E locations: '+document.source)
            node_diagrams: dict[int, SchematicDiagram] = dict()
            diagram_used: bool = False
            for entry in document.records:
                targets: tuple[EditableDevice, ...] = ()
                status: PsseConversionStatus = PsseConversionStatus.UNSUPPORTED
                message: str = 'Cartesian/node-offset LOC requires a diagram with declared units; source retained'
                if entry.status != RecordStatus.VALID:
                    status = PsseConversionStatus.INVALID
                    message = 'Invalid location record retained'
                elif entry.format.system == CoordinateSystem.CARTESIAN or entry.kind == LocationKind.NODE:
                    point: LocationPoint = entry.points[0]
                    if entry.kind == LocationKind.BUS:
                        number = self.bus_number(entry.bus)
                        bus = self.buses.get(number, None)
                        if bus is not None and point.x is not None and point.y is not None:
                            diagram.set_point(bus, GraphicLocation(bus, x=point.x*pixels_per_inch,
                                y=point.y*pixels_per_inch, w=(entry.length or 0.0)*pixels_per_inch,
                                h=10.0, r=entry.rotation or 0.0))
                            diagram_used = True
                            targets = (bus,)
                            status = PsseConversionStatus.PARTIAL if entry.format.scale is not None else PsseConversionStatus.CONVERTED
                            message = 'Created schematic bus position at 96 scene units/inch; physical SCALE retained in source'
                        else:
                            status = PsseConversionStatus.UNRESOLVED
                            message = 'Cartesian LOC bus not uniquely resolved'
                    elif entry.kind == LocationKind.NODE:
                        nodes: list[RawNodeLike] = [node for node in self.source.nodes if node.ISUB == entry.substation and node.NI == entry.node]
                        matches: list[dev.Bus] = [bus for bus in self.grid.buses if len(nodes) == 1 and bus.code == f'{nodes[0].I}:{nodes[0].NI}']
                        if len(matches) == 1 and point.x is not None and point.y is not None and entry.substation is not None:
                            node_diagram: SchematicDiagram | None = node_diagrams.get(entry.substation, None)
                            if node_diagram is None:
                                node_diagram = SchematicDiagram(name=f'PSS/E station {entry.substation} relative offsets')
                                node_diagrams[entry.substation] = node_diagram
                            else:
                                pass
                            node_diagram.set_point(matches[0], GraphicLocation(matches[0], x=point.x*pixels_per_inch,
                                y=point.y*pixels_per_inch, w=(entry.length or 0.0)*pixels_per_inch,
                                h=10.0, r=entry.rotation or 0.0))
                            targets = (matches[0],)
                            status = PsseConversionStatus.CONVERTED
                            message = 'Created station-local node-offset schematic at 96 scene units/inch'
                        else:
                            status = PsseConversionStatus.UNRESOLVED
                            message = 'LOC substation/node identity not uniquely resolved'
                    else:
                        reference = BranchReference()
                        reference.buses = (entry.bus, entry.to_bus)
                        reference.circuit = entry.circuit or '1'
                        branch = self.branch(reference)
                        if branch is not None:
                            diagram.set_point(branch, GraphicLocation(branch,
                                poly_line=[(point.x*pixels_per_inch, point.y*pixels_per_inch) for point in entry.points if point.x is not None and point.y is not None]))
                            diagram_used = True
                            targets = (branch,)
                            status = PsseConversionStatus.PARTIAL if entry.branch_layout == BranchLocationLayout.OPTIONAL_ENDPOINTS else PsseConversionStatus.CONVERTED
                            message = 'Created Cartesian branch polyline; legacy optional endpoint roles retained in source'
                        else:
                            status = PsseConversionStatus.UNRESOLVED
                            message = 'Cartesian LOC branch not uniquely resolved'
                elif entry.format.system == CoordinateSystem.GEOPHYSICAL and entry.kind != LocationKind.NODE:
                    points: list[tuple[float, float]] = list()
                    for point in entry.points:
                        if point.x is not None and point.y is not None:
                            points.append((point.y, point.x) if not entry.format.latitude_first else (point.x, point.y))
                        else:
                            pass
                    if entry.kind == LocationKind.BUS:
                        number: int | None = self.bus_number(entry.bus)
                        bus: dev.Bus | None = self.buses.get(number, None)
                        if bus is not None and len(points) == 1:
                            bus.latitude, bus.longitude = points[0]
                            targets = (bus,)
                            status = PsseConversionStatus.PARTIAL if entry.rotation or entry.length else PsseConversionStatus.CONVERTED
                            message = 'Applied bus GIS coordinates; rotation/length retained for diagram import' if status == PsseConversionStatus.PARTIAL else 'Applied bus GIS coordinates'
                        else:
                            status = PsseConversionStatus.UNRESOLVED
                            message = 'LOC bus not uniquely resolved'
                    else:
                        reference: BranchReference = BranchReference()
                        reference.buses = (entry.bus, entry.to_bus)
                        reference.circuit = entry.circuit or '1'
                        branch: EditableDevice | None = self.branch(reference)
                        if isinstance(branch, dev.Line) and entry.branch_layout == BranchLocationLayout.REQUIRED_ENDPOINTS:
                            data: np.ndarray = np.zeros((len(points), 3), dtype=float)
                            data[:, :2] = points
                            branch.locations.set(data)
                            targets = (branch,)
                            status = PsseConversionStatus.CONVERTED
                            message = 'Applied geographic branch path, including endpoints'
                        else:
                            status = PsseConversionStatus.UNSUPPORTED
                            message = 'Legacy optional branch endpoints cannot be distinguished from knee points'
                else:
                    pass
                self.record(document.source, entry.row.line_number, PsseFileType.LOC, status, targets, message)
            if diagram_used:
                self.grid.add_diagram(diagram)
            else:
                pass
            for node_diagram in node_diagrams.values():
                self.grid.add_diagram(node_diagram)

    def monitor_targets(self, entry: MonitoringDefinition) -> list[EditableDevice] | None:
        """Resolve explicit branches and endpoint-based monitor selections.

        :param entry: Checked monitor definition.
        :return: Complete native target list, or None for unsupported semantics.
        """
        if (entry.status != RecordStatus.VALID or entry.nodes or entry.line_owner is not None
                or entry.kv_range is not None or entry.three_winding_low_voltage
                or entry.equipment != EquipmentKind.BRANCH):
            return None
        elif entry.reference is not None:
            target: EditableDevice | None = self.branch(entry.reference)
            return [target] if target is not None else None
        elif entry.members:
            targets: list[EditableDevice] = list()
            for member in entry.members:
                members: list[EditableDevice] | None = self.monitor_targets(member)
                if members is None:
                    return None
                else:
                    targets.extend(members)
            return targets
        else:
            first: set[int] | None = self.select(entry.selection)
            second: set[int] | None = self.select(entry.to_selection) if entry.to_selection is not None else None
            if first is None or (entry.to_selection is not None and second is None) or any(item.K for item in self.source.transformers):
                return None
            else:
                targets = list()
                for key, matches in self.branches.items():
                    within: bool = key[0] in first and key[1] in first
                    if entry.kind == MonitorKind.CONNECTED:
                        within = key[0] in first or key[1] in first
                    elif entry.kind == MonitorKind.TIES:
                        within = ((key[0] in first and key[1] in second) or (key[1] in first and key[0] in second)) if second is not None else (key[0] in first) != (key[1] in first)
                    else:
                        pass
                    if within:
                        targets.extend(matches)
                    else:
                        pass
                return targets

    def convert_monitors(self) -> None:
        """Set native loading monitors without inventing aggregate interface constraints."""
        selected: set[EditableDevice] = set()
        has_selection: bool = False
        for document in self.source.mon_files:
            for entry in document.definitions:
                targets: list[EditableDevice] | None = None
                status: PsseConversionStatus = PsseConversionStatus.UNSUPPORTED
                message: str = 'Monitor requires native aggregate/voltage-deviation semantics not represented by loading flags'
                if entry.kind in (MonitorKind.BRANCH, MonitorKind.GROUP, MonitorKind.CONNECTED, MonitorKind.TIES, MonitorKind.SKIP):
                    targets = self.monitor_targets(entry)
                    if targets is not None:
                        has_selection = True
                        if entry.kind == MonitorKind.SKIP:
                            selected.difference_update(targets)
                        else:
                            selected.update(targets)
                        status = PsseConversionStatus.CONVERTED
                        message = 'Resolved branch loading monitoring selection'
                    else:
                        status = PsseConversionStatus.UNRESOLVED
                        message = 'Monitor selection could not be completely resolved'
                else:
                    pass
                self.record(document.source, entry.record.line_number, PsseFileType.MON, status,
                            tuple(targets) if targets is not None else (), message)
        if has_selection:
            for branch in self.grid.get_branches():
                if isinstance(branch, (dev.Line, dev.Transformer2W)):
                    branch.monitor_loading = branch in selected
                else:
                    pass
        else:
            pass

    def contingency_targets(self, event: ContingencyEvent) -> list[EditableDevice] | None:
        """Resolve supported outage/switching events without changing the base case.

        :param event: Parsed contingency event.
        :return: Complete target set, or None for unsupported event semantics.
        """
        if event.status != RecordStatus.VALID or event.action not in (EventAction.OPEN, EventAction.CLOSE):
            return None
        elif event.branch is not None:
            target: EditableDevice | None = self.branch(event.branch)
            return [target] if target is not None else None
        else:
            number: int | None = self.bus_number(event.bus)
            if number is None:
                return None
            elif event.equipment == EquipmentKind.MACHINE:
                generator: dev.Generator | None = self.generators.get((number, (event.device_id or '1').strip()), None)
                return [generator] if generator is not None else None
            elif event.equipment == EquipmentKind.BUS:
                targets: list[EditableDevice] = list()
                for key, branches in self.branches.items():
                    if number in key[:2]:
                        targets.extend(branches)
                    else:
                        pass
                for key, generator in self.generators.items():
                    if key[0] == number:
                        targets.append(generator)
                    else:
                        pass
                # Bus outages also remove load/shunt injections; native contingency
                # operations cannot represent these atomically as one bus switch.
                if any(load.bus is self.buses[number] for load in self.grid.loads) or any(shunt.bus is self.buses[number] for shunt in self.grid.shunts):
                    return None
                else:
                    return targets
            else:
                return None

    def convert_contingencies(self) -> None:
        """Build native groups atomically; never install part of a source contingency."""
        for document in self.source.con_files:
            excluded: set[EditableDevice] = set()
            categories: tuple[str, ...] = ()
            automatic_safe: bool = True
            for operation in document.operations:
                if isinstance(operation, Contingency):
                    actions: list[tuple[EditableDevice, float]] = list()
                    valid: bool = operation.status == RecordStatus.VALID
                    for event in operation.events:
                        targets: list[EditableDevice] | None = self.contingency_targets(event)
                        if targets is None:
                            valid = False
                        else:
                            for target in targets:
                                actions.append((target, 0.0 if event.action == EventAction.OPEN else 1.0))
                    if valid and actions:
                        group: dev.ContingencyGroup = dev.ContingencyGroup(name=operation.label, category=', '.join(operation.categories))
                        self.grid.add_contingency_group(group)
                        for target, value in actions:
                            self.grid.add_contingency(dev.Contingency(device=target, name=operation.label + ': ' + target.name,
                                prop=ContingencyOperationTypes.Active, value=value, group=group))
                        status: PsseConversionStatus = PsseConversionStatus.PARTIAL if operation.frequency is not None or operation.duration is not None else PsseConversionStatus.CONVERTED
                        self.record(document.source, operation.record.line_number, PsseFileType.CON, status,
                                    tuple(target for target, _ in actions), 'Created atomic native contingency group; source reliability metadata retained')
                    else:
                        self.record(document.source, operation.record.line_number, PsseFileType.CON,
                                    PsseConversionStatus.UNSUPPORTED, (), 'Contingency not installed: at least one event has no complete native equivalent')
                elif isinstance(operation, ContingencyCategory):
                    categories = operation.values
                    self.record(document.source,operation.record.line_number,PsseFileType.CON,PsseConversionStatus.CONVERTED,(), 'Applied default contingency categories')
                elif isinstance(operation, ContingencySkip):
                    skipped: list[EditableDevice] = list()
                    for reference in operation.branches:
                        branch: EditableDevice | None = self.branch(reference)
                        if branch is None:
                            automatic_safe = False
                        else:
                            skipped.append(branch)
                    excluded.update(skipped)
                    self.record(document.source,operation.record.line_number,PsseFileType.CON,
                                PsseConversionStatus.CONVERTED if automatic_safe else PsseConversionStatus.UNRESOLVED,
                                tuple(skipped),'Applied branch exclusions for later automatic contingencies')
                elif isinstance(operation, AutomaticContingency) and automatic_safe and operation.kind == AutomaticKind.SINGLE and operation.status == RecordStatus.VALID and operation.equipment == EquipmentKind.BRANCH and operation.action == EventAction.OPEN and not operation.ties and operation.to_selection is None and operation.line_owner is None and not operation.three_winding_low_voltage and not any(item.K for item in self.source.transformers):
                    members: set[int] | None = set(self.buses) if operation.all_elements else self.select(operation.selection)
                    if members is not None:
                        for key, targets in self.branches.items():
                            if key[0] in members and key[1] in members:
                                for target in targets:
                                    if target not in excluded:
                                        group = dev.ContingencyGroup(name=f'SINGLE {target.name}',category=', '.join(categories))
                                        self.grid.add_contingency_group(group)
                                        self.grid.add_contingency(dev.Contingency(device=target, name=group.name, group=group, value=0.0))
                                    else:
                                        pass
                            else:
                                pass
                        self.record(document.source, operation.record.line_number, PsseFileType.CON, PsseConversionStatus.CONVERTED, (), 'Expanded automatic single branch outages')
                    else:
                        self.record(document.source, operation.record.line_number, PsseFileType.CON, PsseConversionStatus.UNRESOLVED, (), 'Automatic outage subsystem not resolved')
                else:
                    self.record(document.source, operation.record.line_number, PsseFileType.CON, PsseConversionStatus.UNSUPPORTED, (), 'Contingency directive retained without generation of approximated events')

    def convert_opf(self) -> None:
        """Resolve dispatch/cost tables and native hard bus-voltage constraints."""
        dispatch: dict[int, RopActiveDispatch] = dict()
        costs: dict[int, RopPolynomialCost] = dict()
        machine_tables: dict[tuple[int,str],int] = dict()
        machine_fractions: dict[tuple[int,str],float] = dict()
        for document in self.source.rop_files:
            if document.change == ChangeMode.REPLACE:
                dispatch.clear()
                costs.clear()
                machine_tables.clear()
                machine_fractions.clear()
                for key, generator in self.generators.items():
                    raw: RawGeneratorLike = self.raw_generators[key]
                    generator.Pmax = raw.PT
                    generator.Pmin = raw.PB
                    generator.Cost0 = generator.Cost2 = 0.0
                    generator.Cost = 1.0
            else:
                pass
            for record in document.records:
                if isinstance(record.data, RopActiveDispatch) and record.data.validity == RecordStatus.VALID and record.data.table is not None:
                    previous: RopActiveDispatch | None = dispatch.get(record.data.table,None)
                    updated: RopActiveDispatch = copy(record.data)
                    if previous is not None and document.change == ChangeMode.UPDATE:
                        updated.p_max = previous.p_max if updated.p_max is None else updated.p_max
                        updated.p_min = previous.p_min if updated.p_min is None else updated.p_min
                        updated.fuel_cost = previous.fuel_cost if updated.fuel_cost is None else updated.fuel_cost
                        updated.cost_type = previous.cost_type if updated.cost_type is None else updated.cost_type
                        updated.status = previous.status if updated.status is None else updated.status
                        updated.cost_table = previous.cost_table if updated.cost_table is None else updated.cost_table
                    else:
                        pass
                    dispatch[record.data.table] = updated
                elif isinstance(record.data, RopPolynomialCost) and record.data.validity == RecordStatus.VALID and record.data.table is not None:
                    previous_cost: RopPolynomialCost | None = costs.get(record.data.table,None)
                    updated_cost: RopPolynomialCost = copy(record.data)
                    if previous_cost is not None and document.change == ChangeMode.UPDATE:
                        updated_cost.constant = previous_cost.constant if updated_cost.constant is None else updated_cost.constant
                        updated_cost.linear = previous_cost.linear if updated_cost.linear is None else updated_cost.linear
                        updated_cost.quadratic = previous_cost.quadratic if updated_cost.quadratic is None else updated_cost.quadratic
                        updated_cost.exponential = previous_cost.exponential if updated_cost.exponential is None else updated_cost.exponential
                        updated_cost.exponent = previous_cost.exponent if updated_cost.exponent is None else updated_cost.exponent
                    else:
                        pass
                    costs[record.data.table] = updated_cost
                elif isinstance(record.data, RopGeneratorDispatch) and record.data.validity == RecordStatus.VALID:
                    machine_key: tuple[int,str] = (record.data.bus, (record.data.machine_id or '1').strip())
                    machine_tables[machine_key] = record.data.dispatch_table if record.data.dispatch_table is not None else machine_tables.get(machine_key,1)
                    machine_fractions[machine_key] = record.data.dispatch if record.data.dispatch is not None else machine_fractions.get(machine_key,1.0)
                else:
                    pass
            # Apply only after referenced tables in this file have been indexed.
            for record in document.records:
                entry: RopEntry = record.data
                target: EditableDevice | None = None
                status: PsseConversionStatus = PsseConversionStatus.UNSUPPORTED
                message: str = 'OPF record retained: native optimizer has no exact equivalent'
                if entry.validity != RecordStatus.VALID:
                    status = PsseConversionStatus.INVALID
                    message = 'Invalid OPF record retained'
                elif isinstance(entry, RopBusVoltage) and entry.limit_type in (None, 1):
                    bus: dev.Bus | None = self.buses.get(entry.bus, None)
                    if bus is not None:
                        target = bus
                        if entry.v_normal_max is not None:
                            bus.Vmax = entry.v_normal_max
                        else:
                            pass
                        if entry.v_normal_min is not None:
                            bus.Vmin = entry.v_normal_min
                        else:
                            pass
                        status = PsseConversionStatus.PARTIAL if entry.v_emergency_max is not None or entry.v_emergency_min is not None else PsseConversionStatus.CONVERTED
                        message = 'Applied hard bus voltage bounds; separate emergency bounds retained'
                    else:
                        status = PsseConversionStatus.UNRESOLVED
                        message = 'OPF bus not found'
                elif isinstance(entry, RopGeneratorDispatch):
                    dispatch_key: tuple[int | None,str] = (entry.bus, (entry.machine_id or '1').strip())
                    generator: dev.Generator | None = self.generators.get(dispatch_key, None)
                    table_id: int = machine_tables.get(dispatch_key,1)
                    table: RopActiveDispatch | None = dispatch.get(table_id, None)
                    # Omitted machine records retain the documented default table 1.
                    users: int = sum(1 for candidate in self.generators if machine_tables.get(candidate,1) == table_id)
                    if generator is not None and (table_id == 0 or table is not None and users == 1) and machine_fractions.get(dispatch_key,1.0) == 1.0:
                        target = generator
                        generator.enabled_dispatch = table_id != 0 and table is not None and table.status != 0 and table.cost_table not in (None,0)
                        if table is not None:
                            if table.p_max is not None:
                                generator.Pmax = table.p_max
                            else:
                                pass
                            if table.p_min is not None:
                                generator.Pmin = table.p_min
                            else:
                                pass
                            cost: RopPolynomialCost | None = costs.get(table.cost_table or 0, None)
                            if table.cost_type in (None, 1) and cost is not None and not cost.exponential:
                                multiplier: float = table.fuel_cost if table.fuel_cost is not None else 1.0
                                generator.Cost0 = (cost.constant or 0.0) * multiplier
                                generator.Cost = (cost.linear or 0.0) * multiplier
                                generator.Cost2 = (cost.quadratic or 0.0) * multiplier
                                status = PsseConversionStatus.CONVERTED
                                message = 'Applied independent generator dispatch limits and quadratic fuel cost'
                            else:
                                status = PsseConversionStatus.PARTIAL
                                message = 'Applied independent dispatch limits; non-polynomial or unresolved cost retained'
                        else:
                            status = PsseConversionStatus.CONVERTED
                            message = 'Disabled generator OPF dispatch'
                    else:
                        status = PsseConversionStatus.UNSUPPORTED
                        message = 'Dispatch target/table unresolved or shared dispatch coupling cannot be represented independently'
                elif isinstance(entry, (RopActiveDispatch, RopPolynomialCost)):
                    status = PsseConversionStatus.PARTIAL
                    message = 'Indexed OPF table; linked independent dispatch records apply supported fields'
                else:
                    pass
                self.record(document.source, entry.row.line_number, PsseFileType.ROP, status,
                            (target,) if target is not None else (), message)

    def convert(self) -> PsseImportReport:
        """Apply supported mappings and retain every source document and outcome.

        :return: Conversion report retained on the source PSS/E circuit.
        """
        self.convert_subsystems()
        self.convert_monitors()
        self.convert_contingencies()
        self.convert_sequences()
        self.convert_capabilities()
        self.convert_opf()
        self.convert_locations()
        if self.source.dyr_files:
            from VeraGridEngine.IO.raw.dyr_to_veragrid import convert_dynamics
            convert_dynamics(self)
        else:
            pass
        report: PsseImportReport = PsseImportReport(self.source.get_auxiliary_documents(), tuple(self.entries), tuple(self.resolved_subsystems))
        self.source.conversion_report = report
        return report
