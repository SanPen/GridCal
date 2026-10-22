# SPDX-License-Identifier: MPL-2.0
"""Sequence data framing (POM 33 §5.5.1; DataFormats 34–36 sequence chapters).

Version 35 defaults to the documented 35.2 layout; Sequence35Layout selects
35.0/35.1 explicitly because REV=35 alone cannot identify the NCS layout.
"""
from __future__ import annotations
from enum import Enum
import re
from VeraGridEngine.IO.raw.psse_auxiliary import PsseToken, PsseVersion
from VeraGridEngine.IO.raw.psse_data import DataMarker, DataReader, DataRow, RawDataFile
from VeraGridEngine.IO.raw.versioned.base.auxiliary import RecordStatus
from VeraGridEngine.IO.raw.versioned.base.seq_records import (
    SequenceEntry, SequenceGenerator, SequenceLoad, SequenceBranch, SequenceMutual,
    SequenceTransformer, SequenceFixedShunt, SequenceInduction, SequenceNcsGenerator,
    FaultCharacteristicKind,
)


class SequenceSection(Enum):
    """Ordered section identities, independent of their version-specific indices."""
    SYSTEM = 'system'
    GENERATOR = 'generator'
    LOAD = 'load'
    BRANCH = 'branch'
    MUTUAL = 'mutual'
    TRANSFORMER = 'transformer'
    SWITCHED_SHUNT = 'switched_shunt'
    FIXED_SHUNT = 'fixed_shunt'
    INDUCTION = 'induction'
    LEGACY_NCS = 'legacy_ncs'
    NCS_CHARACTERISTICS = 'ncs_characteristics'
    NCS_GENERATOR = 'ncs_generator'


class Sequence35Layout(Enum):
    """35.0/35.1 embedded curves versus the 35.2 named-table revision."""
    V35_0 = '35.0/35.1'
    V35_2 = '35.2'


class SequenceSwitchedShunt(SequenceEntry):
    """Zero-sequence block susceptances; block counts belong to the RAW case."""
    __slots__ = ('bus', 'shunt_id', 'susceptances')

    def __init__(self, reader: DataReader, has_id: bool) -> None:
        """Read eight optional block susceptances.

        :param reader: Checked cursor.
        :param has_id: Whether the version includes a shunt identifier.
        """
        super().__init__(reader.row)
        self.bus: int | None = reader.positive_integer()
        self.shunt_id: str | None = reader.text(default='1', maximum=2) if has_id else None
        self.susceptances: tuple[float | None, ...] = tuple(reader.real() for _ in range(8))
        if not reader.finish():
            self.status = RecordStatus.INVALID
        else:
            pass


class SequenceSystemOption(Enum):
    """Documented system-wide short-circuit option names."""
    AMPOUT = 'AMPOUT'
    POLROU = 'POLROU'
    AMPOUTZ = 'AMPOUTZ'
    POLROUZ = 'POLROUZ'
    ITERATIONS = 'ITERATIONS'
    TOLERANCE = 'TOLERANCE'
    MOVALPHA = 'MOVALPHA'
    SCNRML = 'SCNRML'


class SequenceSystemKind(Enum):
    """System option record names."""
    REPORT = 'RPTFORMAT'
    MOV = 'MOV'
    MODEL = 'SCMODEL'


class SequenceOption:
    """One named option, retaining numeric values rather than applying defaults."""
    __slots__ = ('name', 'value')

    def __init__(self, name: SequenceSystemOption, value: float | None) -> None:
        """Store a checked option.

        :param name: Documented option identity.
        :param value: Parsed setting.
        """
        self.name: SequenceSystemOption = name
        self.value: float | None = value


class SequenceSystem(SequenceEntry):
    """Named options in any order, including whitespace around equals signs."""
    __slots__ = ('kind', 'options')

    def __init__(self, reader: DataReader) -> None:
        """Validate named option membership and numeric domains.

        :param reader: Checked source cursor.
        """
        super().__init__(reader.row)
        self.kind: SequenceSystemKind | None = None
        self.options: tuple[SequenceOption, ...] = ()
        name: str | None = reader.text(required=True)
        try:
            self.kind = SequenceSystemKind(name.upper() if name is not None else '')
        except ValueError:
            reader.fail('Unknown sequence system record')
        # Token joining handles both NAME=VALUE and NAME = VALUE without losing source.
        tail: str = ''.join(token.text for token in reader.row.tokens[reader.position:])
        matches: list[re.Match[str]] = list(re.finditer(r'([A-Za-z]+)=([^=]*?)(?=[A-Za-z]+=|$)', tail))
        options: list[SequenceOption] = list()
        seen: set[SequenceSystemOption] = set()
        if ''.join(match.group(0) for match in matches) != tail:
            reader.fail('Expected named sequence options')
        else:
            pass
        for match in matches:
            try:
                option: SequenceSystemOption = SequenceSystemOption(match.group(1).upper())
                allowed: bool = (
                    self.kind == SequenceSystemKind.REPORT and option in (SequenceSystemOption.AMPOUT, SequenceSystemOption.POLROU, SequenceSystemOption.AMPOUTZ, SequenceSystemOption.POLROUZ)
                    or self.kind == SequenceSystemKind.MOV and option in (SequenceSystemOption.ITERATIONS, SequenceSystemOption.TOLERANCE, SequenceSystemOption.MOVALPHA)
                    or self.kind == SequenceSystemKind.MODEL and option == SequenceSystemOption.SCNRML)
                value_row: DataRow = DataRow((PsseToken(match.group(2)),), reader.row.line_number, reader.row.text)
                value_reader: DataReader = DataReader(value_row, reader.logger, reader.source)
                value: float | None = value_reader.real(required=True)
                if not value_reader.valid or not allowed or option in seen:
                    reader.fail('Invalid, misplaced or repeated sequence option')
                else:
                    pass
                if value is not None:
                    if option in (SequenceSystemOption.AMPOUT, SequenceSystemOption.POLROU, SequenceSystemOption.AMPOUTZ, SequenceSystemOption.POLROUZ, SequenceSystemOption.SCNRML) and value not in (0, 1):
                        reader.fail('Sequence flag must be 0 or 1')
                    elif option == SequenceSystemOption.ITERATIONS and (value <= 0 or value != int(value)):
                        reader.fail('MOV iteration count must be a positive integer')
                    elif option in (SequenceSystemOption.TOLERANCE, SequenceSystemOption.MOVALPHA) and value <= 0:
                        reader.fail('MOV setting must be positive')
                    else:
                        pass
                else:
                    pass
                seen.add(option)
                options.append(SequenceOption(option, value))
            except ValueError:
                reader.fail('Unknown sequence system option')
        reader.position = len(reader.row.tokens)
        self.options = tuple(options)
        if not reader.finish():
            self.status = RecordStatus.INVALID
        else:
            pass


class SequenceFaultPoint:
    """Time/voltage abscissa and positive-sequence active/reactive current."""
    __slots__ = ('x', 'active', 'reactive')

    def __init__(self, x: float | None, active: float | None, reactive: float | None) -> None:
        """Store explicit point values.

        :param x: Time in seconds or voltage in pu.
        :param active: Active current in pu.
        :param reactive: Reactive current in pu.
        """
        self.x: float | None = x
        self.active: float | None = active
        self.reactive: float | None = reactive


class SequenceCharacteristic(SequenceEntry):
    """A continued converter characteristic with all contributing source lines."""
    __slots__ = ('bus', 'machine_id', 'name', 'kind', 'points', 'rows')

    def __init__(self, row: DataRow) -> None:
        """Initialize a characteristic before consuming its continuation lines.

        :param row: First physical row.
        """
        super().__init__(row)
        self.bus: int | None = None
        self.machine_id: str | None = None
        self.name: str | None = None
        self.kind: FaultCharacteristicKind | None = None
        self.points: tuple[SequenceFaultPoint, ...] = ()
        self.rows: tuple[DataRow, ...] = ()


class SequenceRecord:
    """A section-tagged typed record for ordered iteration without dictionaries."""
    __slots__ = ('section', 'data')

    def __init__(self, section: SequenceSection, data: SequenceEntry) -> None:
        """Associate a typed record with its section.

        :param section: Section identity.
        :param data: Parsed entry.
        """
        self.section: SequenceSection = section
        self.data: SequenceEntry = data


class RawSeq(RawDataFile):
    """Shared framing; version classes specify section order and field extensions."""
    __slots__ = ('sections', 'records', 'reference_angle', 'expanded_induction', 'shunt_ids')

    def __init__(self, source: str = '<seq>', version: int | PsseVersion = PsseVersion.V36) -> None:
        """Initialize sequence data.

        :param source: Diagnostic source label.
        :param version: Selected major version.
        """
        super().__init__(source, version)
        self.sections: tuple[SequenceSection, ...] = ()
        self.records: tuple[SequenceRecord, ...] = ()
        self.reference_angle: bool = False
        self.expanded_induction: bool = False
        self.shunt_ids: bool = False

    def parse(self, text: str) -> None:
        """Parse sections, retaining invalid and unknown records with diagnostics.

        :param text: Complete SEQ input.
        """
        self.records = ()
        if not self.load_rows(text):
            return
        else:
            pass
        if not self.read_change_header(revision=True):
            self.unsupported = self.rows
            return
        else:
            pass
        records: list[SequenceRecord] = list()
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
            elif section_index >= len(self.sections):
                self.unsupported = self.rows[index:]
                self.logger.add_error('SEQ has no selected section grammar', device=self.source, value=row.line_number)
                break
            else:
                section: SequenceSection = self.sections[section_index]
                if section in (SequenceSection.LEGACY_NCS, SequenceSection.NCS_CHARACTERISTICS):
                    characteristic: SequenceCharacteristic
                    characteristic, index = self.read_characteristic(index, section == SequenceSection.LEGACY_NCS)
                    records.append(SequenceRecord(section, characteristic))
                else:
                    records.append(SequenceRecord(section, self.read_record(row, section)))
                    index += 1
        self.records = tuple(records)
        if not self.ended:
            self.logger.add_error('SEQ input ended before section termination', device=self.source)
        else:
            pass

    def read_record(self, row: DataRow, section: SequenceSection) -> SequenceEntry:
        """Dispatch a fixed record using explicit semantic section identities.

        :param row: Source row.
        :param section: Current section.
        :return: Typed record with checked field consumption.
        """
        reader: DataReader = DataReader(row, self.logger, self.source)
        if section == SequenceSection.SYSTEM:
            return SequenceSystem(reader)
        elif section == SequenceSection.GENERATOR:
            return SequenceGenerator(reader, self.reference_angle)
        elif section == SequenceSection.LOAD:
            return SequenceLoad(reader)
        elif section == SequenceSection.BRANCH:
            return SequenceBranch(reader)
        elif section == SequenceSection.MUTUAL:
            return SequenceMutual(reader)
        elif section == SequenceSection.TRANSFORMER:
            return SequenceTransformer(reader)
        elif section == SequenceSection.SWITCHED_SHUNT:
            return SequenceSwitchedShunt(reader, self.shunt_ids)
        elif section == SequenceSection.FIXED_SHUNT:
            return SequenceFixedShunt(reader)
        elif section == SequenceSection.INDUCTION:
            return SequenceInduction(reader, self.expanded_induction)
        elif section == SequenceSection.NCS_GENERATOR:
            return SequenceNcsGenerator(reader)
        else:
            entry: SequenceEntry = SequenceEntry(row)
            entry.status = RecordStatus.UNSUPPORTED
            reader.fail('Unsupported sequence section')
            return entry

    def read_characteristic(self, index: int, legacy: bool) -> tuple[SequenceCharacteristic, int]:
        """Read triplet continuations without consuming the outer section marker.

        :param index: Index of header row.
        :param legacy: Whether header identifies a machine instead of a table.
        :return: Characteristic and next unconsumed row index.
        """
        result: SequenceCharacteristic = SequenceCharacteristic(self.rows[index])
        reader: DataReader = DataReader(self.rows[index], self.logger, self.source)
        if legacy:
            result.bus = reader.positive_integer()
            result.machine_id = reader.text(default='1', maximum=2)
            result.kind = FaultCharacteristicKind.TIME
        else:
            result.name = reader.text(required=True, maximum=12)
            if not result.name or result.name.startswith('-'):
                reader.fail('Characteristic name must be nonblank and cannot start with minus')
            else:
                pass
            kind: str | None = reader.text(required=True)
            try:
                result.kind = FaultCharacteristicKind(kind.upper() if kind is not None else '')
            except ValueError:
                reader.fail('Characteristic type must be TIM or VLT')
        points: list[SequenceFaultPoint] = list()
        rows: list[DataRow] = list()
        terminated: bool = False
        while index < len(self.rows) and not terminated:
            rows.append(self.rows[index])
            count: int = 0
            while reader.position < len(reader.row.tokens) and not terminated:
                x: float | None = reader.real(required=True)
                active: float | None = reader.real(required=True)
                reactive: float | None = reader.real(required=True)
                if not legacy and x == 0 and active == 0 and reactive == 0:
                    terminated = True
                else:
                    points.append(SequenceFaultPoint(x, active, reactive))
                    count += 1
            if count > 6:
                reader.fail('At most six characteristic points per physical row')
            else:
                pass
            # DataFormats 34 §2.12 and 35.0 §3.12 define one six-point row.
            # Only the named tables introduced in 35.2 have continuation/sentinels.
            if legacy:
                terminated = True
            else:
                pass
            if not reader.finish():
                result.status = RecordStatus.INVALID
            else:
                pass
            index += 1
            if not terminated:
                if index >= len(self.rows) or self.rows[index].marker == DataMarker.QUIT or (self.rows[index].marker == DataMarker.ZERO and len(self.rows[index].tokens) == 1):
                    result.status = RecordStatus.INVALID
                    self.logger.add_error('Missing characteristic zero triplet', device=self.source, value=result.row.line_number)
                    break
                else:
                    reader = DataReader(self.rows[index], self.logger, self.source)
            else:
                pass
        result.points = tuple(points)
        result.rows = tuple(rows)
        if not 1 <= len(points) <= (6 if legacy else 20):
            result.status = RecordStatus.INVALID
            self.logger.add_error('Characteristic point count outside version limits', device=self.source, value=result.row.line_number)
        else:
            pass
        for previous, current in zip(points, points[1:]):
            if previous.x is not None and current.x is not None and current.x <= previous.x:
                result.status = RecordStatus.INVALID
                self.logger.add_error('Characteristic abscissas must increase', device=self.source, value=result.row.line_number)
            else:
                pass
        return result, index
