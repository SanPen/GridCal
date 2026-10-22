# SPDX-License-Identifier: MPL-2.0
"""Typed MON operations (POM 33 section 8.1.3; CheatSheets 35 section 1.3)."""
from __future__ import annotations

from enum import Enum

from VeraGridEngine.IO.raw.psse_auxiliary import BusInputMode, PsseAuxiliaryFile, PsseCommand, PsseRecord, PsseVersion
from VeraGridEngine.IO.raw.versioned.base.auxiliary import (
    AuxiliaryEntry, BranchReference, EquipmentKind, FeatureSupport, RawAuxiliaryData,
    RecordReader, RecordStatus, Selection, SelectionKind, check_feature,
    parse_branch_reference, parse_selection,
)


class MonitorKind(Enum):
    """Monitoring operations, preserving their distinct network semantics."""

    BRANCH = 'branch'
    GROUP = 'group'
    CONNECTED = 'connected'
    TIES = 'ties'
    INTERFACE = 'interface'
    SKIP = 'skip'
    VOLTAGE_RANGE = 'voltage_range'
    VOLTAGE_LIMIT = 'voltage_limit'
    VOLTAGE_DEVIATION = 'voltage_deviation'


class MonitoringDefinition(AuxiliaryEntry):
    """One typed monitor operation; interfaces and skips own typed members."""

    __slots__ = ('kind', 'equipment', 'reference', 'selection', 'to_selection',
                 'kv_range', 'three_winding_low_voltage', 'line_owner', 'label',
                 'ratings', 'lower', 'upper', 'nodes', 'members')

    def __init__(self, record: PsseRecord, kind: MonitorKind) -> None:
        """Initialize a monitor definition.

        :param record: Source syntax.
        :param kind: Monitoring operation.
        """
        super().__init__(record)
        self.kind: MonitorKind = kind
        self.equipment: EquipmentKind = EquipmentKind.BRANCH
        self.reference: BranchReference | None = None
        self.selection: Selection | None = None
        self.to_selection: Selection | None = None
        self.kv_range: tuple[float, float] | None = None
        self.three_winding_low_voltage: bool = False
        self.line_owner: int | None = None
        self.label: str | None = None
        self.ratings: tuple[float, ...] = ()
        self.lower: float | None = None
        self.upper: float | None = None
        self.nodes: bool = False
        self.members: tuple[MonitoringDefinition, ...] = ()


class RawMon(RawAuxiliaryData):
    """Shared monitoring grammar, with capabilities fixed by each version class."""

    __slots__ = ('definitions', 'extended_selectors', 'singular_tie', 'node_support',
                 'rating_limit', 'rating_exact_count')

    def __init__(self, source: str = '<mon>', bus_mode: BusInputMode = BusInputMode.NUMBERS,
                 version: int | PsseVersion = PsseVersion.V36) -> None:
        """Initialize a monitoring document.

        :param source: Diagnostic source label.
        :param bus_mode: Initial bus identifier mode.
        :param version: Version selected by the concrete class.
        """
        super().__init__(source, bus_mode, version)
        self.definitions: tuple[MonitoringDefinition, ...] = ()
        self.extended_selectors: FeatureSupport = FeatureSupport.UNVERIFIED
        self.singular_tie: FeatureSupport = FeatureSupport.UNVERIFIED
        self.node_support: FeatureSupport = FeatureSupport.UNVERIFIED
        self.rating_limit: int | None = None
        self.rating_exact_count: int | None = None

    def parse(self, syntax: PsseAuxiliaryFile) -> None:
        """Build typed monitoring definitions without expanding a network case.

        :param syntax: Lexical monitoring tree.
        """
        self.definitions = ()
        if not self.load_syntax(syntax):
            return
        else:
            pass
        definitions: list[MonitoringDefinition] = list()
        unsupported: list[PsseRecord] = list(self.unsupported)
        for record in self.content_records(self.records):
            definition: MonitoringDefinition | None = self.parse_definition(record)
            if definition is not None:
                definitions.append(definition)
            else:
                unsupported.append(record)
        self.definitions = tuple(definitions)
        self.unsupported = tuple(unsupported)

    def check_selection(self, selection: Selection | None, entry: MonitoringDefinition) -> None:
        """Apply version checks to parsed selectors, never to arbitrary label text.

        :param selection: Selector to check.
        :param entry: Owner of the selector.
        """
        if selection is not None:
            if selection.last is not None or selection.last_bus is not None:
                check_feature(self.extended_selectors, 'MON range selectors (35.2)', entry, self.logger, self.source)
            else:
                pass
            if selection.kind in (SelectionKind.SUBSTATION, SelectionKind.ALL_NODES):
                check_feature(self.node_support, 'node-breaker monitoring', entry, self.logger, self.source)
            else:
                pass
        else:
            pass

    def parse_definition(self, record: PsseRecord, member: bool = False) -> MonitoringDefinition | None:
        """Parse one complete definition; block recursion is limited to members.

        :param record: Monitoring syntax.
        :param member: Whether compact branch syntax is allowed.
        :return: Typed definition, or None with explicit unsupported diagnostics.
        """
        offset: int = 1 if record.tokens[0].text.upper() == 'MONITOR' and not record.tokens[0].quoted else 0
        if offset == len(record.tokens):
            self.logger.add_error('MONITOR requires an equipment or voltage command', device=self.source, value=record.line_number)
            return None
        else:
            pass
        reader: RecordReader = RecordReader(record, self.logger, self.source, start=offset + 1)
        entry: MonitoringDefinition = MonitoringDefinition(record, MonitorKind.BRANCH)
        groups: dict[str, EquipmentKind] = dict(
            BRANCHES=EquipmentKind.BRANCH, LINES=EquipmentKind.BRANCH,
            BREAKERS=EquipmentKind.BREAKER, SWITCHES=EquipmentKind.SWITCH, SWDS=EquipmentKind.SWITCHING_DEVICE)
        keyword: str = record.tokens[offset].text.upper()
        if member and record.command == PsseCommand.MEMBER:
            reader.position = 0
            entry.reference = parse_branch_reference(reader, compact=True)
        elif record.command in (PsseCommand.BRANCH, PsseCommand.BREAKER, PsseCommand.SWITCH, PsseCommand.SWD):
            entry.reference = parse_branch_reference(reader)
            devices: dict[str, EquipmentKind] = dict(BREAKER=EquipmentKind.BREAKER, SWITCH=EquipmentKind.SWITCH,
                                                      SWD=EquipmentKind.SWITCHING_DEVICE)
            entry.equipment = devices.get(keyword, EquipmentKind.BRANCH)
            if entry.reference.substation is not None:
                check_feature(self.node_support, 'node-breaker monitoring', entry, self.logger, self.source)
            else:
                pass
        elif record.command in (PsseCommand.INTERFACE, PsseCommand.SKIP) or (keyword in groups and len(record.children) > 0):
            if member:
                reader.fail('Nested monitoring blocks are not permitted')
            else:
                pass
            entry.kind = MonitorKind.INTERFACE if record.command == PsseCommand.INTERFACE else MonitorKind.SKIP
            if keyword in groups:
                entry.kind = MonitorKind.GROUP
            elif entry.kind == MonitorKind.INTERFACE:
                entry.label = reader.text()
                if entry.label is not None and len(entry.label) > 32:
                    reader.fail('Interface label exceeds 32 characters')
                else:
                    pass
                rating_keyword: str = reader.peek()
                if rating_keyword in ('RATING', 'RATINGS'):
                    reader.position += 1
                    ratings: list[float] = list()
                    while reader.position < len(record.tokens) and reader.peek() != 'MW':
                        value: int | float | None = reader.number()
                        if value is not None:
                            ratings.append(float(value))
                        else:
                            pass
                    if reader.peek() == 'MW':
                        reader.position += 1
                    else:
                        pass
                    if self.rating_limit is None and rating_keyword == 'RATINGS' and len(ratings) != 3:
                        check_feature(FeatureSupport.UNVERIFIED, 'expanded interface ratings', entry, self.logger, self.source)
                    else:
                        pass
                    entry.ratings = tuple(ratings)
                    if rating_keyword == 'RATING' and len(ratings) != 1:
                        reader.fail('RATING requires one value')
                    elif rating_keyword == 'RATINGS' and (
                            len(ratings) == 0 or (self.rating_exact_count is not None and len(ratings) != self.rating_exact_count)
                            or (self.rating_limit is not None and len(ratings) > self.rating_limit)):
                        reader.fail('Invalid interface rating count for the selected version')
                    else:
                        pass
                else:
                    pass
            else:
                pass
            members: list[MonitoringDefinition] = list()
            if not member:
                for child in self.content_records(record.children):
                    parsed: MonitoringDefinition | None = self.parse_definition(child, member=True)
                    if parsed is not None:
                        members.append(parsed)
                        if (parsed.status == RecordStatus.INVALID
                                or (parsed.status == RecordStatus.UNSUPPORTED and entry.status == RecordStatus.VALID)):
                            entry.status = parsed.status
                        else:
                            pass
                    else:
                        if entry.status == RecordStatus.VALID:
                            entry.status = RecordStatus.UNSUPPORTED
                        else:
                            pass
            else:
                pass
            entry.members = tuple(members)
        elif record.command == PsseCommand.VOLTAGE:
            modes: dict[str, MonitorKind] = dict(RANGE=MonitorKind.VOLTAGE_RANGE, LIMIT=MonitorKind.VOLTAGE_LIMIT,
                                                DEVIATION=MonitorKind.VOLTAGE_DEVIATION)
            mode: MonitorKind | None = modes.get(reader.peek(), None)
            if mode is not None:
                entry.kind = mode
                reader.position += 1
            else:
                reader.fail('Expected RANGE, LIMIT or DEVIATION')
            if reader.peek() == 'NODES':
                entry.nodes = True
                reader.position += 1
                reader.expect(('IN',))
                check_feature(self.node_support, 'node voltage monitoring', entry, self.logger, self.source)
            else:
                pass
            entry.selection = parse_selection(reader)
            self.parse_voltage_filter(reader, entry)
            if mode != MonitorKind.VOLTAGE_LIMIT:
                lower: int | float | None = reader.number()
                entry.lower = float(lower) if lower is not None else None
                if reader.position < len(record.tokens):
                    upper: int | float | None = reader.number()
                    entry.upper = float(upper) if upper is not None else None
                else:
                    pass
                if (mode == MonitorKind.VOLTAGE_RANGE and entry.lower is not None
                        and entry.upper is not None and entry.lower > entry.upper):
                    reader.fail('Voltage lower bound exceeds upper bound')
                else:
                    pass
            else:
                pass
        elif record.command == PsseCommand.TIES:
            entry.kind = MonitorKind.TIES
            if keyword == 'TIE':
                check_feature(self.singular_tie, 'singular TIE alias (35.2)', entry, self.logger, self.source)
            else:
                pass
            reader.expect(('FROM',))
            entry.selection = parse_selection(reader)
            if reader.peek() == 'TO':
                reader.position += 1
                entry.to_selection = parse_selection(reader)
            else:
                pass
            self.parse_voltage_filter(reader, entry)
        elif keyword in groups or record.command == PsseCommand.ALL:
            entry.kind = MonitorKind.GROUP
            if record.command == PsseCommand.ALL:
                group_kind: EquipmentKind | None = groups.get(reader.peek(), None)
                if group_kind is not None:
                    entry.equipment = group_kind
                    reader.position += 1
                else:
                    reader.fail('Expected a monitored equipment group')
            else:
                entry.equipment = groups[keyword]
                if reader.peek() in ('IN', 'FROM'):
                    entry.kind = MonitorKind.CONNECTED if reader.peek() == 'FROM' else MonitorKind.GROUP
                    reader.position += 1
                    entry.selection = parse_selection(reader)
                elif reader.peek() == 'WITH':
                    reader.position += 1
                    reader.expect(('LINE',))
                    reader.expect(('OWNER',))
                    owner: int | float | None = reader.number(integer=True)
                    entry.line_owner = int(owner) if owner is not None else None
                else:
                    reader.fail('Expected IN, FROM or WITH for group monitoring')
                if reader.peek() == '3WLOWVOLTAGE':
                    entry.three_winding_low_voltage = True
                    reader.position += 1
                else:
                    pass
                self.parse_voltage_filter(reader, entry)
        else:
            self.logger.add_warning('Monitoring command has no typed schema; retained', device=self.source, value=record.line_number)
            return None
        self.check_selection(entry.selection, entry)
        self.check_selection(entry.to_selection, entry)
        if not reader.finish():
            entry.status = RecordStatus.INVALID
        else:
            pass
        self.inherit_directive_status(entry)
        return entry

    def parse_voltage_filter(self, reader: RecordReader, entry: MonitoringDefinition) -> None:
        """Read the extra KV clause without confusing it with the primary selector.

        :param reader: Cursor after a primary selector.
        :param entry: Definition receiving the filter.
        """
        if reader.peek() == 'IN':
            reader.position += 1
            reader.expect(('KVRANGE',))
            reader.position -= 1
        else:
            pass
        if reader.peek() in ('KV', 'KVRANGE'):
            check_feature(self.extended_selectors, 'additional MON voltage filter (35.2)', entry, self.logger, self.source)
            filter_selection: Selection | None = parse_selection(reader)
            if filter_selection is not None and filter_selection.first is not None:
                entry.kv_range = (float(filter_selection.first), float(filter_selection.last)
                                  if filter_selection.last is not None else float(filter_selection.first))
            else:
                pass
        else:
            pass
