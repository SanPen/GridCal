# SPDX-License-Identifier: MPL-2.0
"""Typed auxiliary-file primitives, independent of a resolved network case.

Only lexical keyword matching uses strings. Semantic alternatives use enums.
Invalid records retain their source and must never be applied to a network.
"""
from __future__ import annotations

import math
from collections.abc import Iterator
from enum import Enum

from VeraGridEngine.basic_structures import Logger
from VeraGridEngine.IO.raw.psse_auxiliary import (
    BusInputMode, PsseAuxiliaryFile, PsseCommand, PsseRecord, PsseToken, PsseVersion,
)


class RecordStatus(Enum):
    """Whether a record is safe for subsequent semantic processing."""

    VALID = 'valid'
    INVALID = 'invalid'
    UNSUPPORTED = 'unsupported'


class FeatureSupport(Enum):
    """Distinguish documented support from an unavailable version specification."""

    YES = 'yes'
    NO = 'no'
    UNVERIFIED = 'unverified'


class SelectionKind(Enum):
    """Bus selection operations used in all three command languages."""

    BUS = 'bus'
    AREA = 'area'
    ZONE = 'zone'
    OWNER = 'owner'
    KV = 'kv'
    SUBSYSTEM = 'subsystem'
    ALL_BUSES = 'all_buses'
    ALL_NODES = 'all_nodes'
    SUBSTATION = 'substation'


class EquipmentKind(Enum):
    """Equipment types, normalized across documented keyword aliases."""

    BRANCH = 'branch'
    THREE_WINDING = 'three_winding'
    BUS = 'bus'
    MACHINE = 'machine'
    LOAD = 'load'
    SHUNT = 'shunt'
    SWSHUNT = 'swshunt'
    INDUCTION_MACHINE = 'induction_machine'
    TWO_TERMINAL_DC = 'two_terminal_dc'
    MULTI_TERMINAL_DC = 'multi_terminal_dc'
    VSC_DC = 'vsc_dc'
    FACTS = 'facts'
    BREAKER = 'breaker'
    SWITCH = 'switch'
    SWITCHING_DEVICE = 'switching_device'
    TERMINAL = 'terminal'
    SUBSTATION_NODE = 'substation_node'


class Quantity(Enum):
    """Physical quantities addressed by SUB filters and CON events."""

    LOAD = 'LOAD'
    GENERATION = 'GENERATION'
    GENUPLIMIT = 'GENUPLIMIT'
    GENLOWLIMIT = 'GENLOWLIMIT'
    SHUNT = 'SHUNT'
    SWSHUNT = 'SWSHUNT'
    INDUCMACHINE = 'INDUCMACHINE'
    VSCHED = 'VSCHED'
    VMAX = 'VMAX'
    VMIN = 'VMIN'
    ACTIVE = 'ACTIVE'
    REACTIVE = 'REACTIVE'


class ValueUnit(Enum):
    """Units spelled in auxiliary commands, separate from network base units."""

    MW = 'MW'
    MVAR = 'MVAR'
    MVA = 'MVA'
    PERCENT = 'PERCENT'
    PERUNIT = 'PERUNIT'
    KV = 'KV'
    OHMS = 'OHMS'
    AMPS = 'AMPS'
    MWPF = 'MWPF'


def parse_equipment(reader: RecordReader) -> EquipmentKind | None:
    """Consume one equipment keyword and normalize its documented aliases.

    :param reader: Cursor at an equipment type.
    :return: Equipment kind, or None on failure.
    """
    aliases: dict[str, EquipmentKind] = dict(
        BRANCH=EquipmentKind.BRANCH, LINE=EquipmentKind.BRANCH,
        THREEWINDING=EquipmentKind.THREE_WINDING, BUS=EquipmentKind.BUS,
        MACHINE=EquipmentKind.MACHINE, UNIT=EquipmentKind.MACHINE,
        LOAD=EquipmentKind.LOAD, SHUNT=EquipmentKind.SHUNT, SWSHUNT=EquipmentKind.SWSHUNT,
        INDUCMACHINE=EquipmentKind.INDUCTION_MACHINE, TWOTERMDC=EquipmentKind.TWO_TERMINAL_DC,
        MULTITERMDC=EquipmentKind.MULTI_TERMINAL_DC, VSCDC=EquipmentKind.VSC_DC,
        FACTS=EquipmentKind.FACTS, BREAKER=EquipmentKind.BREAKER, SWITCH=EquipmentKind.SWITCH,
        SWD=EquipmentKind.SWITCHING_DEVICE, TERMINAL=EquipmentKind.TERMINAL,
        SUB=EquipmentKind.SUBSTATION_NODE, SUBSTATION=EquipmentKind.SUBSTATION_NODE)
    equipment: EquipmentKind | None = aliases.get(reader.peek(), None)
    if equipment is not None:
        reader.position += 1
    else:
        reader.fail('Unknown equipment keyword')
    return equipment


def parse_unit(reader: RecordReader) -> ValueUnit | None:
    """Consume a documented unit token.

    :param reader: Cursor at a unit.
    :return: Unit enum, or None on failure.
    """
    unit: ValueUnit | None = ValueUnit.__members__.get(reader.peek(), None)
    if unit is not None:
        reader.position += 1
    else:
        reader.fail('Unknown quantity unit')
    return unit


class BusIdentifier:
    """A bus number or an extended name; circuit IDs remain separate strings."""

    __slots__ = ('number', 'name')

    def __init__(self, number: int | None = None, name: str | None = None) -> None:
        """Store an identifier.

        :param number: Numeric bus reference.
        :param name: Extended name, including voltage.
        """
        self.number: int | None = number
        self.name: str | None = name


class Selection:
    """A single selector; compound union/intersection belongs to SUB blocks."""

    __slots__ = ('kind', 'first', 'last', 'bus', 'last_bus', 'label', 'node')

    def __init__(self, kind: SelectionKind) -> None:
        """Initialize an empty selector of a known kind.

        :param kind: Selection operation.
        """
        self.kind: SelectionKind = kind
        self.first: int | float | None = None
        self.last: int | float | None = None
        self.bus: BusIdentifier | None = None
        self.last_bus: BusIdentifier | None = None
        self.label: str | None = None
        self.node: int | None = None


class BranchReference:
    """Ordered terminals, circuit identifier, and optional node-breaker location."""

    __slots__ = ('buses', 'circuit', 'substation', 'from_node', 'to_node')

    def __init__(self) -> None:
        """Initialize the documented default circuit without inventing terminals."""
        self.buses: tuple[BusIdentifier, ...] = ()
        self.circuit: str = '1'
        self.substation: int | None = None
        self.from_node: int | None = None
        self.to_node: int | None = None


class Participation:
    """A bus and its dispatch/transfer participation factor."""

    __slots__ = ('bus', 'factor')

    def __init__(self, bus: BusIdentifier, factor: float) -> None:
        """Store one weight.

        :param bus: Participating bus.
        :param factor: Signed SUB weight or positive contingency weight.
        """
        self.bus: BusIdentifier = bus
        self.factor: float = factor


class AuxiliaryEntry:
    """Every typed operation retains the source record and an explicit status."""

    __slots__ = ('record', 'status')

    def __init__(self, record: PsseRecord) -> None:
        """Attach source context to an operation.

        :param record: Original syntax and source line.
        """
        self.record: PsseRecord = record
        self.status: RecordStatus = RecordStatus.VALID if record.valid else RecordStatus.INVALID


class RawAuxiliaryData(PsseAuxiliaryFile):
    """Shared source ownership; each format supplies its own typed grammar."""

    __slots__ = ('unsupported', 'directives', 'directive_status', 'bus_mode_support')

    def __init__(self, source: str, bus_mode: BusInputMode, version: int | PsseVersion) -> None:
        """Initialize independently owned data and version capabilities.

        :param source: Diagnostic source label.
        :param bus_mode: Initial identifier interpretation.
        :param version: Selected major version.
        """
        super().__init__(source, bus_mode, version)
        self.unsupported: tuple[PsseRecord, ...] = ()
        self.directives: tuple[AuxiliaryEntry, ...] = ()
        self.directive_status: dict[int, RecordStatus] = dict()
        self.bus_mode_support: FeatureSupport = FeatureSupport.UNVERIFIED

    def load_syntax(self, syntax: PsseAuxiliaryFile) -> bool:
        """Adopt a fresh lexical result and validate file-level directives.

        :param syntax: Tokenized file, produced once by the file reader.
        :return: Whether the syntax belongs to this version object.
        """
        self.records = syntax.records
        self.logger = syntax.logger
        self.directives = ()
        self.directive_status = dict()
        self.unsupported = ()
        if syntax.version != self.version:
            self.logger.add_error('Syntax version does not match the concrete data object', device=self.source)
            self.unsupported = syntax.records
            return False
        else:
            pass
        # Recompute context using this version's actual directives. A rejected
        # directive must not reinterpret subsequent equipment identifiers.
        effective_mode: BusInputMode = self.bus_mode
        directives: list[AuxiliaryEntry] = list()
        unsupported: list[PsseRecord] = list()
        pending: list[PsseRecord] = list(reversed(syntax.records))
        while len(pending) > 0:
            record: PsseRecord = pending.pop()
            record.bus_mode = effective_mode
            if record.command in (PsseCommand.BUSNAMES, PsseCommand.BUSNUMBERS,
                                   PsseCommand.ECHO, PsseCommand.TRACE, PsseCommand.INCLUDE):
                directive: AuxiliaryEntry = AuxiliaryEntry(record)
                reader: RecordReader = RecordReader(record, self.logger, self.source)
                if record.command in (PsseCommand.BUSNAMES, PsseCommand.BUSNUMBERS):
                    check_feature(self.bus_mode_support, 'in-file bus mode commands (introduced in 35.2)',
                                  directive, self.logger, self.source)
                    if self.bus_mode_support == FeatureSupport.YES:
                        effective_mode = BusInputMode.NAMES if record.command == PsseCommand.BUSNAMES else BusInputMode.NUMBERS
                        record.bus_mode = effective_mode
                    else:
                        pass
                elif record.command in (PsseCommand.ECHO, PsseCommand.INCLUDE):
                    reader.text()
                    if record.command == PsseCommand.INCLUDE:
                        directive.status = RecordStatus.UNSUPPORTED
                        unsupported.append(record)
                    else:
                        pass
                else:
                    pass
                if not reader.finish():
                    directive.status = RecordStatus.INVALID
                else:
                    pass
                directives.append(directive)
            else:
                pass
            pending.extend(reversed(record.children))
        self.directives = tuple(directives)
        self.directive_status = dict((directive.record.line_number, directive.status) for directive in directives)
        self.unsupported = tuple(unsupported)
        self.bus_mode = effective_mode
        return True

    def inherit_directive_status(self, entry: AuxiliaryEntry) -> None:
        """Propagate unusable directives through their enclosing typed blocks.

        :param entry: Enclosing operation or definition.
        """
        pending: list[PsseRecord] = list(entry.record.children)
        while len(pending) > 0:
            record: PsseRecord = pending.pop()
            status: RecordStatus = self.directive_status.get(record.line_number, RecordStatus.VALID)
            if status == RecordStatus.INVALID or status == RecordStatus.UNSUPPORTED and entry.status == RecordStatus.VALID:
                entry.status = status
            else:
                pass
            pending.extend(record.children)

    def content_records(self, records: tuple[PsseRecord, ...]) -> Iterator[PsseRecord]:
        """Iterate grammar records after directives have been processed once.

        :param records: Ordered syntax at any block level.
        :return: Non-directive records, preserving their input order.
        """
        for record in records:
            if record.line_number not in self.directive_status:
                yield record
            else:
                pass


class RecordReader:
    """Checked field consumption with local diagnostics and no exception recovery."""

    __slots__ = ('record', 'position', 'logger', 'source', 'valid')

    def __init__(self, record: PsseRecord, logger: Logger, source: str, start: int = 1) -> None:
        """Start consuming a record after its command keyword.

        :param record: Input record.
        :param logger: Result diagnostics.
        :param source: Filename or source label.
        :param start: Index of the first argument.
        """
        self.record: PsseRecord = record
        self.position: int = start
        self.logger: Logger = logger
        self.source: str = source
        self.valid: bool = True

    def fail(self, message: str) -> None:
        """Mark the record unusable and report its location.

        :param message: Specific grammar or value failure.
        """
        self.valid = False
        self.logger.add_error(message, device=self.source, value=self.record.line_number)

    def peek(self) -> str:
        """Inspect a keyword without confusing a quoted value with a keyword.

        :return: Uppercase unquoted field, or an empty string.
        """
        if self.position < len(self.record.tokens) and not self.record.tokens[self.position].quoted:
            return self.record.tokens[self.position].text.upper()
        else:
            return ''

    def take(self) -> PsseToken | None:
        """Consume one field, recording missing input.

        :return: Field, or None at the end of the record.
        """
        if self.position < len(self.record.tokens):
            token: PsseToken = self.record.tokens[self.position]
            self.position += 1
            return token
        else:
            self.fail('Missing required field')
            return None

    def expect(self, choices: tuple[str, ...]) -> bool:
        """Consume a required grammar keyword from a documented alias group.

        :param choices: Literal accepted spellings.
        :return: Whether the keyword matched.
        """
        if self.peek() in choices:
            self.position += 1
            return True
        else:
            self.fail('Expected ' + '|'.join(choices))
            return False

    def text(self) -> str | None:
        """Consume an identifier without numeric coercion.

        :return: Nonempty string, or None for invalid input.
        """
        token: PsseToken | None = self.take()
        if token is not None and len(token.text) > 0:
            return token.text
        else:
            self.fail('Expected a nonempty identifier')
            return None

    def number(self, integer: bool = False) -> int | float | None:
        """Consume a finite numeric value; integer fields reject real spellings.

        :param integer: Require an integer token.
        :return: Parsed value, or None with a diagnostic.
        """
        token: PsseToken | None = self.take()
        if token is not None and not token.quoted:
            try:
                value: int | float = int(token.text) if integer else float(token.text.replace('D', 'E').replace('d', 'e'))
                if math.isfinite(value):
                    return value
                else:
                    self.fail('Numeric field must be finite')
            except (ValueError, OverflowError):
                self.fail('Expected an integer' if integer else 'Expected a number')
        else:
            self.fail('Expected an unquoted numeric field')
        return None

    def bus(self) -> BusIdentifier | None:
        """Consume a bus reference using the record's effective input mode.

        :return: Typed reference, or None for invalid input.
        """
        token: PsseToken | None = self.take()
        if token is not None:
            try:
                number: int = int(token.text)
                if number > 0 and not token.quoted:
                    return BusIdentifier(number=number)
                elif self.record.bus_mode == BusInputMode.NAMES and len(token.text) > 0:
                    return BusIdentifier(name=token.text)
                else:
                    self.fail('Bus numbers must be positive unquoted integers')
            except ValueError:
                if self.record.bus_mode == BusInputMode.NAMES and len(token.text) > 0:
                    return BusIdentifier(name=token.text)
                else:
                    self.fail('Bus name requires names input mode')
        else:
            pass
        return None

    def finish(self) -> bool:
        """Reject trailing fields instead of silently losing part of a command.

        :return: Whether the entire record was consumed successfully.
        """
        if self.position != len(self.record.tokens):
            self.fail('Unexpected trailing fields')
        else:
            pass
        return self.valid


def parse_selection(reader: RecordReader) -> Selection | None:
    """Read one selector; consumers apply their version's allowed selector set.

    :param reader: Cursor positioned at BUS, AREA, KV, SYSTEM, etc.
    :return: Typed selector, or None for an unknown selector keyword.
    """
    keyword: str = reader.peek()
    kinds: dict[str, SelectionKind] = dict(
        BUS=SelectionKind.BUS, BUSES=SelectionKind.BUS,
        AREA=SelectionKind.AREA, AREAS=SelectionKind.AREA,
        ZONE=SelectionKind.ZONE, ZONES=SelectionKind.ZONE,
        OWNER=SelectionKind.OWNER, OWNERS=SelectionKind.OWNER,
        KV=SelectionKind.KV, KVRANGE=SelectionKind.KV,
        SYSTEM=SelectionKind.SUBSYSTEM, SUBSYSTEM=SelectionKind.SUBSYSTEM,
        SUB=SelectionKind.SUBSTATION, SUBSTATION=SelectionKind.SUBSTATION)
    kind: SelectionKind | None = kinds.get(keyword, None)
    if keyword == 'ALL':
        reader.position += 1
        all_kind: str = reader.peek()
        reader.expect(('BUSES', 'NODES'))
        return Selection(SelectionKind.ALL_BUSES if all_kind == 'BUSES' else SelectionKind.ALL_NODES)
    elif kind is not None:
        reader.position += 1
        selection: Selection = Selection(kind)
        is_range: bool = keyword in ('BUSES', 'AREAS', 'ZONES', 'OWNERS', 'KVRANGE')
        if kind == SelectionKind.BUS:
            selection.bus = reader.bus()
            if is_range:
                selection.last_bus = reader.bus()
                if (selection.bus is not None and selection.last_bus is not None
                        and selection.bus.number is not None and selection.last_bus.number is not None
                        and selection.last_bus.number > selection.bus.number
                        and reader.record.bus_mode == BusInputMode.NUMBERS):
                    pass
                else:
                    reader.fail('BUSES requires an increasing range of bus numbers')
            else:
                pass
        elif kind == SelectionKind.SUBSYSTEM:
            selection.label = reader.text()
        else:
            selection.first = reader.number(integer=kind != SelectionKind.KV)
            if is_range:
                selection.last = reader.number(integer=kind != SelectionKind.KV)
                if selection.first is not None and selection.last is not None and selection.last <= selection.first:
                    reader.fail('Selection range must be increasing')
                else:
                    pass
            elif kind == SelectionKind.SUBSTATION and reader.peek() == 'NODE':
                reader.position += 1
                node_value: int | float | None = reader.number(integer=True)
                selection.node = int(node_value) if node_value is not None else None
            else:
                pass
        return selection
    else:
        reader.fail('Unknown bus selection keyword')
        return None


def parse_branch_reference(reader: RecordReader, compact: bool = False) -> BranchReference:
    """Read two/three ordered terminals or a substation switching device.

    :param reader: Cursor following the equipment keyword.
    :param compact: Accept positional MON list/interface members.
    :return: Reference, accompanied by reader errors if malformed.
    """
    reference: BranchReference = BranchReference()
    buses: list[BusIdentifier] = list()
    if reader.peek() in ('SUB', 'SUBSTATION'):
        reader.position += 1
        substation: int | float | None = reader.number(integer=True)
        reference.substation = int(substation) if substation is not None else None
        reader.expect(('FROM',))
        reader.expect(('NODE',))
        from_node: int | float | None = reader.number(integer=True)
        reader.expect(('TO',))
        reader.expect(('NODE',))
        to_node: int | float | None = reader.number(integer=True)
        reference.from_node = int(from_node) if from_node is not None else None
        reference.to_node = int(to_node) if to_node is not None else None
    else:
        if not compact:
            reader.expect(('FROM', 'AT'))
            reader.expect(('BUS',))
        else:
            pass
        first: BusIdentifier | None = reader.bus()
        if first is not None:
            buses.append(first)
        else:
            pass
        if not compact or reader.peek() == 'TO':
            reader.expect(('TO',))
            if not compact:
                reader.expect(('BUS',))
            else:
                pass
        else:
            pass
        second: BusIdentifier | None = reader.bus()
        if second is not None:
            buses.append(second)
        else:
            pass
        if reader.peek() == 'TO':
            reader.position += 1
            if not compact:
                reader.expect(('BUS',))
            else:
                pass
            third: BusIdentifier | None = reader.bus()
            if third is not None:
                buses.append(third)
            else:
                pass
        else:
            pass
        reference.buses = tuple(buses)
    if reader.peek() in ('CIRCUIT', 'CKT'):
        reader.position += 1
        circuit: str | None = reader.text()
        reference.circuit = circuit if circuit is not None else ''
    elif compact and reader.position < len(reader.record.tokens):
        circuit = reader.text()
        reference.circuit = circuit if circuit is not None else ''
    else:
        pass
    if not 1 <= len(reference.circuit) <= 2:
        reader.fail('Circuit identifier must contain one or two characters')
    else:
        pass
    return reference


def parse_participation(record: PsseRecord, logger: Logger, source: str,
                        positive: bool) -> Participation | None:
    """Read a checked participation weight in a SUB or DISPATCH block.

    :param record: BUS record.
    :param logger: Result diagnostics.
    :param source: Diagnostic source label.
    :param positive: Require a positive weight for contingency dispatch.
    :return: Weight, or None on failure.
    """
    reader: RecordReader = RecordReader(record, logger, source, start=0)
    reader.expect(('BUS',))
    bus: BusIdentifier | None = reader.bus()
    factor: int | float | None = reader.number()
    if factor is not None and (factor == 0 or (positive and factor < 0)):
        reader.fail('Invalid participation factor')
    else:
        pass
    if reader.finish() and bus is not None and factor is not None:
        return Participation(bus, float(factor))
    else:
        return None


def check_feature(support: FeatureSupport, feature: str, entry: AuxiliaryEntry,
                  logger: Logger, source: str) -> None:
    """Expose unsupported or unverified version syntax without discarding it.

    :param support: Evidence-based version capability.
    :param feature: Human-readable grammar feature.
    :param entry: Operation whose status must be updated.
    :param logger: Result diagnostics.
    :param source: Diagnostic source label.
    """
    if support == FeatureSupport.NO:
        logger.add_error('Unsupported in selected version: ' + feature, device=source, value=entry.record.line_number)
        entry.status = RecordStatus.INVALID
    elif support == FeatureSupport.UNVERIFIED:
        logger.add_warning('Not verified for selected version: ' + feature, device=source, value=entry.record.line_number)
        if entry.status == RecordStatus.VALID:
            entry.status = RecordStatus.UNSUPPORTED
        else:
            pass
    else:
        pass
