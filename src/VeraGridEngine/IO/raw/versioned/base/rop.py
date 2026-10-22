# SPDX-License-Identifier: MPL-2.0
"""OPF records and nested framing; POM 33 §14.9 / DataFormats 34–36.

A zero closes a reserve/interface/equation member list before another zero can
close its section. Piecewise curves consume NPAIRS points, not a zero sentinel.
"""
from __future__ import annotations
from enum import Enum
from VeraGridEngine.IO.raw.psse_auxiliary import PsseToken, PsseVersion
from VeraGridEngine.IO.raw.psse_data import DataMarker, DataReader, DataRow, RawDataFile
from VeraGridEngine.IO.raw.versioned.base.auxiliary import RecordStatus
from VeraGridEngine.IO.raw.versioned.base.rop_records import (
    RopEntry, RopVariable, RopBusVoltage, RopAdjustableShunt, RopBusLoad,
    RopLoadTable, RopGeneratorDispatch, RopActiveDispatch, RopGenerationReserve,
    RopReactiveCapability, RopBranchReactance, RopPolynomialCost,
    RopPeriodReserve, RopBranchFlow, RopInterfaceFlow, RopLinearDependency,
    RopReserveMember, RopInterfaceMember,
)


class RopSection(Enum):
    """The sixteen OPF sections in the documented order."""
    BUS_VOLTAGE = 'bus_voltage'
    ADJUSTABLE_SHUNT = 'adjustable_shunt'
    BUS_LOAD = 'bus_load'
    LOAD_TABLE = 'load_table'
    GENERATOR_DISPATCH = 'generator_dispatch'
    ACTIVE_DISPATCH = 'active_dispatch'
    GENERATION_RESERVE = 'generation_reserve'
    REACTIVE_CAPABILITY = 'reactive_capability'
    BRANCH_REACTANCE = 'branch_reactance'
    LINEAR_COST = 'linear_cost'
    QUADRATIC_COST = 'quadratic_cost'
    POLYNOMIAL_COST = 'polynomial_cost'
    PERIOD_RESERVE = 'period_reserve'
    BRANCH_FLOW = 'branch_flow'
    INTERFACE_FLOW = 'interface_flow'
    LINEAR_DEPENDENCY = 'linear_dependency'


class RopPoint:
    """One explicit cost curve point in the file's units."""
    __slots__ = ('x', 'y')

    def __init__(self, x: float | None, y: float | None) -> None:
        """Retain checked numeric point values.

        :param x: Independent variable.
        :param y: Cost ordinate.
        """
        self.x: float | None = x
        self.y: float | None = y


class RopCostCurve(RopEntry):
    """Counted, optionally continued linear or quadratic cost table."""
    __slots__ = ('table', 'label', 'constant', 'count', 'points', 'rows')

    def __init__(self, reader: DataReader, quadratic: bool) -> None:
        """Read only the curve header before assembling its point payload.

        :param reader: Checked cursor.
        :param quadratic: Whether the constant COST precedes NPAIRS.
        """
        super().__init__(reader.row)
        self.table: int | None = reader.positive_integer()
        self.label: str | None = reader.text(maximum=12)
        self.constant: float | None = reader.real() if quadratic else None
        self.count: int | None = reader.integer()
        self.points: tuple[RopPoint, ...] = ()
        self.rows: tuple[DataRow, ...] = ()
        if self.count is None and reader.valid:
            self.count = 0
        elif self.count is not None and self.count < 0:
            reader.fail('Cost point count must be nonnegative')
        else:
            pass


class RopCoefficient(RopEntry):
    """Linear term with explicit variable-specific identifiers and coefficient."""
    __slots__ = ('variable', 'reference', 'to_bus', 'equipment_id', 'flow_id', 'coefficient', 'third_bus')

    def __init__(self, reader: DataReader) -> None:
        """Read IDs in the order required by VTYP, including trailing KBUS.

        :param reader: Checked member cursor.
        """
        super().__init__(reader.row)
        self.variable: RopVariable | None = None
        self.reference: int | None = None
        self.to_bus: int | None = None
        self.equipment_id: str | None = None
        self.flow_id: str | None = None
        self.coefficient: float | None = None
        self.third_bus: int | None = None
        code: int | None = reader.integer(required=True)
        try:
            self.variable = RopVariable(code)
        except (ValueError, TypeError):
            reader.fail('Unknown linear-dependency VTYP')
        if self.variable is not None:
            self.reference = reader.positive_integer()
            if self.variable in (RopVariable.TRANSFORMER_TAP, RopVariable.BRANCH_FLOW):
                self.to_bus = reader.positive_integer()
                self.equipment_id = reader.text(default='1', maximum=2)
            elif self.variable in (RopVariable.REACTIVE_GENERATION, RopVariable.ADJUSTABLE_SHUNT):
                self.equipment_id = reader.text(default='1', maximum=2)
            else:
                pass
            if self.variable == RopVariable.BRANCH_FLOW:
                self.flow_id = reader.text(default='1', maximum=1)
            else:
                pass
            self.coefficient = reader.real()
            if self.coefficient is None and reader.valid:
                self.coefficient = 1.0
            else:
                pass
            if self.variable in (RopVariable.TRANSFORMER_TAP, RopVariable.BRANCH_FLOW):
                self.third_bus = reader.positive_integer(required=False, allow_zero=True)
            else:
                pass
        else:
            pass
        if not reader.finish():
            self.validity = RecordStatus.INVALID
        else:
            pass


class RopRecord:
    """Section-tagged OPF entry, with typed nested records on its data object."""
    __slots__ = ('section', 'data')

    def __init__(self, section: RopSection, data: RopEntry) -> None:
        """Associate section and payload.

        :param section: Current OPF section.
        :param data: Parsed payload.
        """
        self.section: RopSection = section
        self.data: RopEntry = data


class RawRop(RawDataFile):
    """Section framing with an explicit version-owned shunt layout."""
    __slots__ = ('sections', 'status_before_cost', 'records')

    def __init__(self, source: str = '<rop>', version: int | PsseVersion = PsseVersion.V36) -> None:
        """Initialize a standalone OPF result.

        :param source: Diagnostic source label.
        :param version: Selected major revision.
        """
        super().__init__(source, version)
        self.sections: tuple[RopSection, ...] = tuple(RopSection)
        self.status_before_cost: bool = False
        self.records: tuple[RopRecord, ...] = ()

    def parse(self, text: str) -> None:
        """Consume all ordered sections or an early Q termination.

        :param text: Complete OPF data file.
        """
        self.records = ()
        if not self.load_rows(text):
            return
        else:
            pass
        if not self.read_change_header(revision=False):
            self.unsupported = self.rows
            return
        else:
            pass
        records: list[RopRecord] = list()
        section_index: int = 0
        index: int = 1
        while index < len(self.rows) and not self.ended:
            row: DataRow = self.rows[index]
            if row.marker == DataMarker.QUIT:
                self.finish_input(index)
                index += 1
            elif row.marker == DataMarker.ZERO:
                section_index += 1
                index += 1
                if section_index == len(self.sections):
                    if index < len(self.rows) and self.rows[index].marker == DataMarker.QUIT:
                        self.finish_input(index)
                    else:
                        self.finish_input(index - 1)
                else:
                    pass
            else:
                section: RopSection = self.sections[section_index]
                entry: RopEntry
                if section in (RopSection.LINEAR_COST, RopSection.QUADRATIC_COST):
                    entry, index = self.read_curve(index, section == RopSection.QUADRATIC_COST)
                else:
                    entry = self.read_record(row, section)
                    index += 1
                    if section in (RopSection.PERIOD_RESERVE, RopSection.INTERFACE_FLOW, RopSection.LINEAR_DEPENDENCY):
                        index = self.read_members(entry, index, section)
                    else:
                        pass
                records.append(RopRecord(section, entry))
        self.records = tuple(records)
        if not self.ended:
            self.logger.add_error('ROP input ended before section termination', device=self.source)
        else:
            pass

    def read_record(self, row: DataRow, section: RopSection) -> RopEntry:
        """Construct the section's named record class.

        :param row: Physical record.
        :param section: Semantic section identity.
        :return: Checked record, preserving invalid values.
        """
        reader: DataReader = DataReader(row, self.logger, self.source)
        if section == RopSection.BUS_VOLTAGE:
            return RopBusVoltage(reader)
        elif section == RopSection.ADJUSTABLE_SHUNT:
            return RopAdjustableShunt(reader, self.status_before_cost)
        elif section == RopSection.BUS_LOAD:
            return RopBusLoad(reader)
        elif section == RopSection.LOAD_TABLE:
            return RopLoadTable(reader)
        elif section == RopSection.GENERATOR_DISPATCH:
            return RopGeneratorDispatch(reader)
        elif section == RopSection.ACTIVE_DISPATCH:
            return RopActiveDispatch(reader)
        elif section == RopSection.GENERATION_RESERVE:
            return RopGenerationReserve(reader)
        elif section == RopSection.REACTIVE_CAPABILITY:
            return RopReactiveCapability(reader)
        elif section == RopSection.BRANCH_REACTANCE:
            return RopBranchReactance(reader)
        elif section == RopSection.POLYNOMIAL_COST:
            return RopPolynomialCost(reader)
        elif section == RopSection.PERIOD_RESERVE:
            return RopPeriodReserve(reader)
        elif section == RopSection.BRANCH_FLOW:
            return RopBranchFlow(reader)
        elif section == RopSection.INTERFACE_FLOW:
            return RopInterfaceFlow(reader)
        elif section == RopSection.LINEAR_DEPENDENCY:
            return RopLinearDependency(reader)
        else:
            reader.fail('Unsupported OPF section')
            return RopEntry(row)

    def read_members(self, entry: RopEntry, index: int, section: RopSection) -> int:
        """Consume the inner zero terminator, leaving outer termination to parse.

        :param entry: Owning header record.
        :param index: First child index.
        :param section: Current nested section.
        :return: Index following the inner terminator, or the unconsumed Q/EOF.
        """
        members: list[RopEntry] = list()
        terminated: bool = False
        while index < len(self.rows) and not terminated:
            row: DataRow = self.rows[index]
            if row.marker == DataMarker.QUIT:
                break
            elif row.marker == DataMarker.ZERO:
                terminated = True
                index += 1
            else:
                reader: DataReader = DataReader(row, self.logger, self.source)
                member: RopEntry
                if section == RopSection.PERIOD_RESERVE:
                    member = RopReserveMember(reader)
                elif section == RopSection.INTERFACE_FLOW:
                    member = RopInterfaceMember(reader)
                else:
                    member = RopCoefficient(reader)
                members.append(member)
                if member.validity != RecordStatus.VALID:
                    entry.validity = RecordStatus.INVALID
                else:
                    pass
                index += 1
        entry.members = tuple(members)
        if not terminated:
            entry.validity = RecordStatus.INVALID
            self.logger.add_error('Missing OPF member-list terminator', device=self.source, value=entry.row.line_number)
        else:
            pass
        return index

    def read_curve(self, index: int, quadratic: bool) -> tuple[RopCostCurve, int]:
        """Read counted points while retaining physical source lines.

        :param index: Header row index.
        :param quadratic: Whether COST precedes the point count.
        :return: Curve and index of the next unconsumed row.
        """
        reader: DataReader = DataReader(self.rows[index], self.logger, self.source)
        result: RopCostCurve = RopCostCurve(reader, quadratic)
        rows: list[DataRow] = [self.rows[index]]
        fields: list[PsseToken] = list(reader.row.tokens[reader.position:])
        target: int = max(result.count or 0, 0) * 2
        index += 1
        while len(fields) < target and index < len(self.rows):
            row: DataRow = self.rows[index]
            if row.marker == DataMarker.QUIT or row.marker == DataMarker.ZERO and len(row.tokens) == 1:
                break
            else:
                fields.extend(row.tokens)
                rows.append(row)
                index += 1
        payload: DataRow = DataRow(tuple(fields), result.row.line_number, result.row.text,
                                   all(row.status == RecordStatus.VALID for row in rows))
        point_reader: DataReader = DataReader(payload, self.logger, self.source)
        points: list[RopPoint] = list()
        # Bound work by actual input even when the declared count is corrupt.
        while point_reader.position < len(fields):
            points.append(RopPoint(point_reader.real(required=True), point_reader.real(required=True)))
        if len(fields) != target:
            point_reader.fail('Cost table payload does not match NPAIRS')
        else:
            pass
        for previous, current in zip(points, points[1:]):
            if previous.x is not None and current.x is not None and current.x <= previous.x:
                point_reader.fail('Cost abscissas must strictly increase')
            else:
                pass
        result.points = tuple(points)
        result.rows = tuple(rows)
        if not reader.valid or not point_reader.finish():
            result.validity = RecordStatus.INVALID
        else:
            pass
        return result, index
