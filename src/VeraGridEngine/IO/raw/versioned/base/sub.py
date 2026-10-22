# SPDX-License-Identifier: MPL-2.0
"""Typed SUB grammar: POM 33 section 8.1.2; CheatSheets 35 and DataFormats 36.

Union, intersection, exclusion and participation remain ordered operations.
Evaluation against a network case is intentionally outside this file.
"""
from __future__ import annotations

from enum import Enum

from VeraGridEngine.IO.raw.psse_auxiliary import BusInputMode, PsseAuxiliaryFile, PsseCommand, PsseRecord, PsseVersion
from VeraGridEngine.IO.raw.versioned.base.auxiliary import (
    AuxiliaryEntry, FeatureSupport, Participation, Quantity, RawAuxiliaryData, RecordReader, RecordStatus,
    Selection, ValueUnit, check_feature, parse_participation, parse_selection, parse_unit,
)


class SubOperationKind(Enum):
    """Ordered operations in a subsystem definition."""

    SELECT = 'select'
    JOIN = 'join'
    EXCLUDE = 'exclude'
    PARTICIPATE = 'participate'


class Comparison(Enum):
    """Strict threshold comparisons used by SKIP BUS WITH."""

    LESS = 'LESS'
    GREATER = 'GREATER'


class SubOperation(AuxiliaryEntry):
    """A typed selector, JOIN, SKIP predicate or participation block."""

    __slots__ = ('kind', 'selection', 'children', 'weights', 'quantity', 'comparison',
                 'threshold', 'unit', 'in_service', 'label')

    def __init__(self, record: PsseRecord, kind: SubOperationKind) -> None:
        """Initialize a subsystem operation.

        :param record: Source syntax.
        :param kind: Operation to perform.
        """
        super().__init__(record)
        self.kind: SubOperationKind = kind
        self.selection: Selection | None = None
        self.children: tuple[SubOperation, ...] = ()
        self.weights: tuple[Participation, ...] = ()
        self.quantity: Quantity | None = None
        self.comparison: Comparison | None = None
        self.threshold: float | None = None
        self.unit: ValueUnit | None = None
        self.in_service: bool = False
        self.label: str | None = None


class Subsystem(AuxiliaryEntry):
    """A named subsystem and its complete ordered definition."""

    __slots__ = ('label', 'operations')

    def __init__(self, record: PsseRecord, label: str) -> None:
        """Initialize a subsystem definition.

        :param record: Source block.
        :param label: Explicit or generated subsystem name.
        """
        super().__init__(record)
        self.label: str = label
        self.operations: tuple[SubOperation, ...] = ()


class RawSub(RawAuxiliaryData):
    """Shared typed grammar; concrete versions supply documented limits."""

    __slots__ = ('subsystems', 'label_limit')

    def __init__(self, source: str = '<sub>', bus_mode: BusInputMode = BusInputMode.NUMBERS,
                 version: int | PsseVersion = PsseVersion.V36) -> None:
        """Initialize a SUB document.

        :param source: Source label.
        :param bus_mode: Initial identifier interpretation.
        :param version: Major version selected by the concrete object.
        """
        super().__init__(source, bus_mode, version)
        self.subsystems: tuple[Subsystem, ...] = ()
        self.label_limit: int | None = None

    def parse(self, syntax: PsseAuxiliaryFile) -> None:
        """Parse checked values and validate block placement and operation order.

        :param syntax: Lexical tree of a SUB file.
        """
        self.subsystems = ()
        if not self.load_syntax(syntax):
            return
        else:
            pass
        subsystems: list[Subsystem] = list()
        unsupported: list[PsseRecord] = list(self.unsupported)
        labels: set[str] = set()
        for record in self.content_records(self.records):
            if record.command == PsseCommand.SUBSYSTEM:
                reader: RecordReader = RecordReader(record, self.logger, self.source)
                label: str | None = reader.text() if reader.position < len(record.tokens) else 'UNNAMED ' + str(len(subsystems) + 1)
                subsystem: Subsystem = Subsystem(record, label if label is not None else '')
                if self.label_limit is not None and len(subsystem.label) > self.label_limit:
                    reader.fail('Subsystem label exceeds the documented version limit')
                elif subsystem.label in labels:
                    reader.fail('Duplicate subsystem label')
                else:
                    labels.add(subsystem.label)
                if self.label_limit is None and len(subsystem.label) > 12:
                    check_feature(FeatureSupport.UNVERIFIED, 'expanded subsystem label length',
                                  subsystem, self.logger, self.source)
                else:
                    pass
                operations: list[SubOperation] = list()
                phase: SubOperationKind = SubOperationKind.SELECT
                for child in self.content_records(record.children):
                    operation: SubOperation | None = self.parse_operation(child)
                    if operation is None:
                        unsupported.append(child)
                        if subsystem.status == RecordStatus.VALID:
                            subsystem.status = RecordStatus.UNSUPPORTED
                        else:
                            pass
                    else:
                        if (phase == SubOperationKind.PARTICIPATE
                                or (phase == SubOperationKind.EXCLUDE
                                    and operation.kind in (SubOperationKind.SELECT, SubOperationKind.JOIN))):
                            reader.fail('SKIP must follow selectors; PARTICIPATE must be last')
                        else:
                            pass
                        phase = operation.kind
                        operations.append(operation)
                        if (operation.status == RecordStatus.INVALID
                                or (operation.status == RecordStatus.UNSUPPORTED and subsystem.status == RecordStatus.VALID)):
                            subsystem.status = operation.status
                        else:
                            pass
                subsystem.operations = tuple(operations)
                if not reader.finish():
                    subsystem.status = RecordStatus.INVALID
                else:
                    pass
                self.inherit_directive_status(subsystem)
                subsystems.append(subsystem)
            else:
                unsupported.append(record)
                self.logger.add_error('Expected a SUBSYSTEM block or file directive', device=self.source, value=record.line_number)
        self.subsystems = tuple(subsystems)
        self.unsupported = tuple(unsupported)

    def parse_operation(self, record: PsseRecord) -> SubOperation | None:
        """Parse one operation; JOIN accepts simple selectors only.

        :param record: Source operation.
        :return: Typed operation or None for unsupported syntax.
        """
        reader: RecordReader = RecordReader(record, self.logger, self.source)
        operation: SubOperation
        if record.command == PsseCommand.JOIN:
            operation = SubOperation(record, SubOperationKind.JOIN)
            if reader.position < len(record.tokens):
                operation.label = reader.text()
            else:
                pass
            children: list[SubOperation] = list()
            for child in self.content_records(record.children):
                child_reader: RecordReader = RecordReader(child, self.logger, self.source, start=0)
                child_operation: SubOperation = SubOperation(child, SubOperationKind.SELECT)
                child_operation.selection = parse_selection(child_reader)
                if child.command not in (PsseCommand.BUS, PsseCommand.BUSES, PsseCommand.AREA, PsseCommand.AREAS,
                                          PsseCommand.ZONE, PsseCommand.ZONES, PsseCommand.OWNER, PsseCommand.OWNERS,
                                          PsseCommand.KV, PsseCommand.KVRANGE):
                    child_reader.fail('JOIN only accepts simple selection criteria')
                else:
                    pass
                if not child_reader.finish():
                    child_operation.status = RecordStatus.INVALID
                    reader.valid = False
                else:
                    pass
                children.append(child_operation)
            operation.children = tuple(children)
            if len(children) < 2:
                reader.fail('JOIN requires at least two selection criteria')
            else:
                pass
        elif record.command == PsseCommand.PARTICIPATE:
            operation = SubOperation(record, SubOperationKind.PARTICIPATE)
            weights: list[Participation] = list()
            for child in self.content_records(record.children):
                weight: Participation | None = parse_participation(child, self.logger, self.source, positive=False)
                if weight is not None:
                    weights.append(weight)
                else:
                    reader.valid = False
            operation.weights = tuple(weights)
            if sum(weight.factor for weight in weights) <= 0:
                reader.fail('Participation weights must have a positive sum')
            else:
                pass
        elif record.command == PsseCommand.SKIP:
            operation = SubOperation(record, SubOperationKind.EXCLUDE)
            reader.expect(('BUS',))
            if reader.peek() == 'WITH':
                reader.position += 1
                if reader.peek() == 'IN-SERVICE':
                    operation.in_service = True
                    reader.position += 1
                else:
                    pass
                operation.quantity = Quantity.__members__.get(reader.peek(), None)
                if operation.quantity is not None:
                    reader.position += 1
                else:
                    reader.fail('Unknown SKIP quantity')
                operation.comparison = Comparison.__members__.get(reader.peek(), None)
                if operation.comparison is not None:
                    reader.position += 1
                else:
                    reader.fail('Expected LESS or GREATER')
                threshold: int | float | None = reader.number()
                operation.threshold = float(threshold) if threshold is not None else None
                operation.unit = parse_unit(reader)
                if operation.unit not in (ValueUnit.MW, ValueUnit.MVAR, ValueUnit.MVA):
                    reader.fail('SKIP requires MW, MVAR or MVA')
                else:
                    pass
            else:
                reader.position -= 1
                operation.selection = parse_selection(reader)
        else:
            operation = SubOperation(record, SubOperationKind.SELECT)
            reader.position = 0
            operation.selection = parse_selection(reader)
            if record.command not in (PsseCommand.BUS, PsseCommand.BUSES, PsseCommand.AREA, PsseCommand.AREAS,
                                       PsseCommand.ZONE, PsseCommand.ZONES, PsseCommand.OWNER, PsseCommand.OWNERS,
                                       PsseCommand.KV, PsseCommand.KVRANGE):
                reader.fail('Unsupported SUB selection criterion')
            else:
                pass
            if operation.selection is None:
                return None
            else:
                pass
        if not reader.finish():
            operation.status = RecordStatus.INVALID
        else:
            pass
        self.inherit_directive_status(operation)
        return operation
