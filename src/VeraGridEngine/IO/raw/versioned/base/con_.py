# SPDX-License-Identifier: MPL-2.0
"""Typed CON grammar (POM 33 section 8.1.4; DataFormats 36 section 12.4).

Automatic requests remain requests until a network is supplied. They must never
be presented as already expanded individual outages.
"""
from __future__ import annotations

from enum import Enum

from VeraGridEngine.IO.raw.psse_auxiliary import BusInputMode, PsseAuxiliaryFile, PsseCommand, PsseRecord, PsseVersion
from VeraGridEngine.IO.raw.versioned.base.auxiliary import (
    AuxiliaryEntry, BranchReference, BusIdentifier, EquipmentKind, FeatureSupport,
    Participation, Quantity, RawAuxiliaryData, RecordReader, RecordStatus, Selection,
    SelectionKind, ValueUnit, check_feature, parse_branch_reference, parse_equipment,
    parse_participation, parse_selection, parse_unit,
)


class EventAction(Enum):
    """Canonical contingency actions; original aliases remain in source tokens."""

    OPEN = 'open'
    CLOSE = 'close'
    BLOCK = 'block'
    SET = 'set'
    CHANGE = 'change'
    INCREASE = 'increase'
    DECREASE = 'decrease'
    ADD = 'add'
    REMOVE = 'remove'
    MOVE = 'move'
    ISOLATE = 'isolate'
    STUCK = 'stuck'


class AutomaticKind(Enum):
    """Combinatorial outage generation requested by a CON record."""

    SINGLE = 'single'
    DOUBLE = 'double'
    BUSDOUBLE = 'busdouble'
    PARALLEL = 'parallel'


class ContingencyEvent(AuxiliaryEntry):
    """A checked event with typed action, target and optional boundary change."""

    __slots__ = ('action', 'equipment', 'branch', 'bus', 'to_bus', 'device_id',
                 'quantity', 'value', 'unit', 'dispatch', 'reactive_to_active')

    def __init__(self, record: PsseRecord) -> None:
        """Initialize an event without guessing equipment or parameter meaning.

        :param record: Source event.
        """
        super().__init__(record)
        self.action: EventAction | None = EventAction.__members__.get(record.command.name, None)
        self.equipment: EquipmentKind | None = None
        self.branch: BranchReference | None = None
        self.bus: BusIdentifier | None = None
        self.to_bus: BusIdentifier | None = None
        self.device_id: str | None = None
        self.quantity: Quantity | None = None
        self.value: float | None = None
        self.unit: ValueUnit | None = None
        self.dispatch: tuple[Participation, ...] = ()
        self.reactive_to_active: bool = False


class Contingency(AuxiliaryEntry):
    """An explicit multi-event contingency with reliability/category metadata."""

    __slots__ = ('label', 'frequency', 'duration', 'categories', 'events')

    def __init__(self, record: PsseRecord) -> None:
        """Initialize a contingency.

        :param record: Source block.
        """
        super().__init__(record)
        self.label: str = ''
        self.frequency: float | None = None
        self.duration: float | None = None
        self.categories: tuple[str, ...] = ()
        self.events: tuple[ContingencyEvent, ...] = ()


class AutomaticContingency(AuxiliaryEntry):
    """A network-dependent request to generate single or paired outages."""

    __slots__ = ('kind', 'equipment', 'selection', 'to_selection', 'all_elements',
                 'line_owner', 'action', 'three_winding_low_voltage', 'ties')

    def __init__(self, record: PsseRecord, kind: AutomaticKind) -> None:
        """Initialize an outage generation request.

        :param record: Source command.
        :param kind: Combination rule.
        """
        super().__init__(record)
        self.kind: AutomaticKind = kind
        self.equipment: EquipmentKind | None = None
        self.selection: Selection | None = None
        self.to_selection: Selection | None = None
        self.all_elements: bool = False
        self.line_owner: int | None = None
        self.action: EventAction = EventAction.OPEN
        self.three_winding_low_voltage: bool = False
        self.ties: bool = False


class ContingencyCategory(AuxiliaryEntry):
    """Default categories applying to subsequent contingencies."""

    __slots__ = ('values',)

    def __init__(self, record: PsseRecord, values: tuple[str, ...]) -> None:
        """Store an ordered category assignment.

        :param record: Source category block.
        :param values: Header and VALUE categories.
        """
        super().__init__(record)
        self.values: tuple[str, ...] = values


class ContingencySkip(AuxiliaryEntry):
    """Branch exclusions applying only to later automatic outage requests."""

    __slots__ = ('branches',)

    def __init__(self, record: PsseRecord) -> None:
        """Initialize an exclusion block.

        :param record: Source SKIP block.
        """
        super().__init__(record)
        self.branches: tuple[BranchReference, ...] = ()


class RawCon(RawAuxiliaryData):
    """Typed contingency document with version-owned capabilities."""

    __slots__ = ('operations', 'contingencies', 'category_support', 'node_support',
                 'swshunt_control', 'extended_isolation')

    def __init__(self, source: str = '<con>', bus_mode: BusInputMode = BusInputMode.NUMBERS,
                 version: int | PsseVersion = PsseVersion.V36) -> None:
        """Initialize an independent contingency document.

        :param source: Diagnostic source label.
        :param bus_mode: Initial bus reference mode.
        :param version: Major version selected by a concrete class.
        """
        super().__init__(source, bus_mode, version)
        self.operations: tuple[AuxiliaryEntry, ...] = ()
        self.contingencies: tuple[Contingency, ...] = ()
        self.category_support: FeatureSupport = FeatureSupport.UNVERIFIED
        self.node_support: FeatureSupport = FeatureSupport.UNVERIFIED
        self.swshunt_control: FeatureSupport = FeatureSupport.UNVERIFIED
        self.extended_isolation: FeatureSupport = FeatureSupport.UNVERIFIED

    def parse(self, syntax: PsseAuxiliaryFile) -> None:
        """Parse complete typed events and retain automatic requests in order.

        :param syntax: Lexical CON tree.
        """
        self.operations = ()
        self.contingencies = ()
        if not self.load_syntax(syntax):
            return
        else:
            pass
        operations: list[AuxiliaryEntry] = list()
        contingencies: list[Contingency] = list()
        unsupported: list[PsseRecord] = list(self.unsupported)
        labels: set[str] = set()
        defaults: tuple[str, ...] = ()
        defaults_status: RecordStatus = RecordStatus.VALID
        for record in self.content_records(self.records):
            if record.command == PsseCommand.CONTINGENCY:
                contingency: Contingency = self.parse_contingency(record, defaults, defaults_status)
                if contingency.label in labels:
                    self.logger.add_error('Duplicate contingency label', device=self.source, value=record.line_number)
                    contingency.status = RecordStatus.INVALID
                else:
                    labels.add(contingency.label)
                contingencies.append(contingency)
                operations.append(contingency)
            elif record.command == PsseCommand.CATEGORY:
                values: list[str] = list()
                category_reader: RecordReader = RecordReader(record, self.logger, self.source)
                category: str | None = category_reader.text()
                if category is not None:
                    values.append(category)
                else:
                    pass
                valid: bool = category_reader.finish()
                for child in self.content_records(record.children):
                    child_reader: RecordReader = RecordReader(child, self.logger, self.source, start=0)
                    child_reader.expect(('VALUE',))
                    value: str | None = child_reader.text()
                    if value is not None:
                        values.append(value)
                    else:
                        pass
                    valid = child_reader.finish() and valid
                category_entry: ContingencyCategory = ContingencyCategory(record, tuple(values))
                check_feature(self.category_support, 'contingency categories', category_entry, self.logger, self.source)
                if not valid:
                    category_entry.status = RecordStatus.INVALID
                else:
                    pass
                self.inherit_directive_status(category_entry)
                defaults = category_entry.values
                defaults_status = category_entry.status
                operations.append(category_entry)
            elif record.command == PsseCommand.SKIP:
                skip: ContingencySkip = ContingencySkip(record)
                skip_reader: RecordReader = RecordReader(record, self.logger, self.source)
                skip_reader.expect(('BRANCH', 'LINE'))
                branches: list[BranchReference] = list()
                for child in self.content_records(record.children):
                    branch_reader: RecordReader = RecordReader(child, self.logger, self.source, start=0)
                    branches.append(parse_branch_reference(branch_reader, compact=True))
                    if not branch_reader.finish():
                        skip.status = RecordStatus.INVALID
                    else:
                        pass
                skip.branches = tuple(branches)
                if not skip_reader.finish():
                    skip.status = RecordStatus.INVALID
                else:
                    pass
                self.inherit_directive_status(skip)
                operations.append(skip)
            elif record.command in (PsseCommand.SINGLE, PsseCommand.DOUBLE, PsseCommand.BUSDOUBLE, PsseCommand.PARALLEL):
                operations.append(self.parse_automatic(record))
            else:
                unsupported.append(record)
                self.logger.add_error('Expected CONTINGENCY, automatic request or file directive',
                                      device=self.source, value=record.line_number)
        self.operations = tuple(operations)
        self.contingencies = tuple(contingencies)
        self.unsupported = tuple(unsupported)

    def parse_contingency(self, record: PsseRecord, defaults: tuple[str, ...],
                          defaults_status: RecordStatus = RecordStatus.VALID) -> Contingency:
        """Parse reliability metadata and all events of one explicit contingency.

        :param record: Source CONTINGENCY block.
        :param defaults: Current default categories.
        :param defaults_status: Whether the inherited category assignment is usable.
        :return: Typed contingency including invalid/unsupported event statuses.
        """
        entry: Contingency = Contingency(record)
        reader: RecordReader = RecordReader(record, self.logger, self.source)
        label: str | None = reader.text()
        entry.label = label if label is not None else ''
        entry.categories = defaults
        explicit_category: bool = False
        if len(entry.label) > 32:
            reader.fail('Contingency label exceeds 32 characters')
        else:
            pass
        # CATEGORY may precede or follow the optional frequency/duration pair.
        while reader.position < len(record.tokens):
            if reader.peek() == 'CATEGORY':
                explicit_category = True
                reader.position += 1
                categories: str | None = reader.text()
                entry.categories = tuple(item.strip() for item in categories.split(',')) if categories is not None else ()
                check_feature(self.category_support, 'contingency categories', entry, self.logger, self.source)
            elif entry.frequency is None:
                frequency: int | float | None = reader.number()
                duration: int | float | None = reader.number()
                entry.frequency = float(frequency) if frequency is not None else None
                entry.duration = float(duration) if duration is not None else None
                if frequency is None or duration is None:
                    reader.position = len(record.tokens)
                elif frequency < 0 or duration < 0:
                    reader.fail('Contingency frequency and duration must be nonnegative')
                else:
                    pass
            else:
                reader.fail('Unexpected contingency header field')
                reader.position = len(record.tokens)
        if not explicit_category and (defaults_status == RecordStatus.INVALID
                                      or defaults_status == RecordStatus.UNSUPPORTED and entry.status == RecordStatus.VALID):
            entry.status = defaults_status
        else:
            pass
        events: list[ContingencyEvent] = list()
        for child in self.content_records(record.children):
            event: ContingencyEvent = self.parse_event(child)
            events.append(event)
            if event.status == RecordStatus.INVALID:
                entry.status = RecordStatus.INVALID
            elif event.status == RecordStatus.UNSUPPORTED and entry.status == RecordStatus.VALID:
                entry.status = RecordStatus.UNSUPPORTED
            else:
                pass
        entry.events = tuple(events)
        if not 1 <= len(events) <= 32:
            reader.fail('Contingency must contain 1 to 32 events')
        else:
            pass
        if not reader.finish():
            entry.status = RecordStatus.INVALID
        else:
            pass
        self.inherit_directive_status(entry)
        return entry

    def parse_event(self, record: PsseRecord) -> ContingencyEvent:
        """Parse switching, boundary changes, transfers and dispatch weights.

        :param record: Source event.
        :return: Typed event with explicit validation status.
        """
        event: ContingencyEvent = ContingencyEvent(record)
        reader: RecordReader = RecordReader(record, self.logger, self.source)
        if event.action is None:
            event.status = RecordStatus.UNSUPPORTED
            self.logger.add_warning('No typed contingency event schema; retained', device=self.source, value=record.line_number)
            if record.command in (PsseCommand.CONTINGENCY, PsseCommand.CATEGORY, PsseCommand.SKIP):
                reader.fail('Nested contingency/category/skip block is not permitted')
                event.status = RecordStatus.INVALID
            else:
                pass
            return event
        else:
            pass
        if event.action == EventAction.MOVE:
            self.parse_move(reader, event)
        else:
            event.equipment = parse_equipment(reader)
            equipment: EquipmentKind | None = event.equipment
            if equipment in (EquipmentKind.BRANCH, EquipmentKind.THREE_WINDING, EquipmentKind.TERMINAL,
                              EquipmentKind.BREAKER, EquipmentKind.SWITCH, EquipmentKind.SWITCHING_DEVICE):
                event.branch = parse_branch_reference(reader)
                if equipment == EquipmentKind.THREE_WINDING and len(event.branch.buses) != 3:
                    reader.fail('THREEWINDING requires three bus references')
                else:
                    pass
            elif equipment == EquipmentKind.BUS:
                event.bus = reader.bus()
                if event.action in (EventAction.SET, EventAction.CHANGE, EventAction.INCREASE, EventAction.DECREASE):
                    event.quantity = Quantity.__members__.get(reader.peek(), None)
                    if event.quantity is not None:
                        reader.position += 1
                    else:
                        reader.fail('Expected a bus quantity')
            elif equipment == EquipmentKind.SUBSTATION_NODE:
                event.branch = BranchReference()
                substation: int | float | None = reader.number(integer=True)
                reader.expect(('NODE',))
                node: int | float | None = reader.number(integer=True)
                event.branch.substation = int(substation) if substation is not None else None
                event.branch.from_node = int(node) if node is not None else None
                if event.action != EventAction.ISOLATE:
                    reader.fail('A substation node requires ISOLATE')
                else:
                    pass
            elif equipment in (EquipmentKind.MACHINE, EquipmentKind.LOAD, EquipmentKind.SHUNT,
                                EquipmentKind.SWSHUNT, EquipmentKind.INDUCTION_MACHINE):
                if equipment == EquipmentKind.SWSHUNT and reader.peek() in ('AT', 'FROM', 'TO'):
                    event.device_id = '1'
                else:
                    event.device_id = reader.text()
                reader.expect(('FROM',) if event.action == EventAction.REMOVE else ('TO',) if event.action == EventAction.ADD else ('AT',))
                reader.expect(('BUS',))
                event.bus = reader.bus()
                if equipment in (EquipmentKind.MACHINE, EquipmentKind.SWSHUNT) and event.action in (
                        EventAction.SET, EventAction.CHANGE, EventAction.INCREASE, EventAction.DECREASE):
                    event.quantity = Quantity.__members__.get(reader.peek(), None)
                    if event.quantity is not None:
                        reader.position += 1
                    else:
                        reader.fail('Expected an equipment quantity')
                else:
                    pass
            elif equipment in (EquipmentKind.TWO_TERMINAL_DC, EquipmentKind.MULTI_TERMINAL_DC,
                                EquipmentKind.VSC_DC, EquipmentKind.FACTS):
                event.device_id = reader.text()
            else:
                reader.fail('Unsupported event target')
            if event.device_id is not None:
                limit: int = 12 if equipment in (EquipmentKind.TWO_TERMINAL_DC, EquipmentKind.MULTI_TERMINAL_DC,
                                                 EquipmentKind.VSC_DC, EquipmentKind.FACTS) else 2
                if not 1 <= len(event.device_id) <= limit:
                    reader.fail('Equipment identifier exceeds its documented length')
                else:
                    pass
            else:
                pass
            self.check_event_target(reader, event)
            if event.action in (EventAction.SET, EventAction.CHANGE, EventAction.INCREASE, EventAction.DECREASE):
                reader.expect(('TO',) if event.action == EventAction.SET else ('BY',))
                if event.quantity == Quantity.REACTIVE and reader.peek() == 'ACTIVE':
                    event.reactive_to_active = True
                    reader.position += 1
                    if event.equipment != EquipmentKind.MACHINE or event.action != EventAction.SET:
                        reader.fail('REACTIVE TO ACTIVE is defined only for SET MACHINE')
                    else:
                        pass
                else:
                    value: int | float | None = reader.number()
                    event.value = float(value) if value is not None else None
                    event.unit = parse_unit(reader)
                    self.check_change_unit(reader, event)
                    if (event.unit == ValueUnit.PERCENT and event.action == EventAction.SET
                            or event.action in (EventAction.INCREASE, EventAction.DECREASE)) and value is not None and value < 0:
                        reader.fail('PERCENT and directional change amounts must be nonnegative')
                    else:
                        pass
            elif event.action == EventAction.CLOSE and equipment in (EquipmentKind.TWO_TERMINAL_DC, EquipmentKind.VSC_DC):
                reader.expect(('AT',))
                value = reader.number()
                event.value = float(value) if value is not None else None
                event.unit = parse_unit(reader)
                if (equipment == EquipmentKind.VSC_DC and event.unit != ValueUnit.MW
                        or equipment == EquipmentKind.TWO_TERMINAL_DC and event.unit not in (ValueUnit.MW, ValueUnit.AMPS)):
                    reader.fail('Invalid DC closing unit')
                else:
                    pass
            else:
                pass
        if reader.peek() == 'DISPATCH':
            reader.position += 1
            if not (event.action in (EventAction.ADD, EventAction.REMOVE)
                    and event.equipment != EquipmentKind.SWSHUNT
                    or event.equipment == EquipmentKind.BUS
                    and event.action in (EventAction.SET, EventAction.CHANGE, EventAction.INCREASE, EventAction.DECREASE)
                    and event.unit in (ValueUnit.MW, ValueUnit.PERCENT)):
                reader.fail('DISPATCH is not defined for this event')
            else:
                pass
            weights: list[Participation] = list()
            for child in self.content_records(record.children):
                weight: Participation | None = parse_participation(child, self.logger, self.source, positive=True)
                if weight is not None:
                    weights.append(weight)
                else:
                    reader.valid = False
            event.dispatch = tuple(weights)
            if len(weights) == 0:
                reader.fail('DISPATCH requires participating buses')
            else:
                pass
        elif len(record.children) > 0:
            reader.fail('Unexpected event block')
        else:
            pass
        if event.action == EventAction.ISOLATE:
            support: FeatureSupport = self.node_support if event.equipment in (
                EquipmentKind.BRANCH, EquipmentKind.BUS, EquipmentKind.THREE_WINDING,
                EquipmentKind.SUBSTATION_NODE, EquipmentKind.BREAKER, EquipmentKind.SWITCH,
                EquipmentKind.SWITCHING_DEVICE) else self.extended_isolation
            check_feature(support, 'isolation contingency', event, self.logger, self.source)
        elif event.equipment == EquipmentKind.SWSHUNT:
            check_feature(self.swshunt_control, 'switched-shunt contingency controls (35.2)', event, self.logger, self.source)
        else:
            pass
        if (event.equipment in (EquipmentKind.TERMINAL, EquipmentKind.BREAKER, EquipmentKind.SWITCH,
                                EquipmentKind.SWITCHING_DEVICE, EquipmentKind.SUBSTATION_NODE)
                or (event.branch is not None and event.branch.substation is not None)):
            check_feature(self.node_support, 'node-breaker contingency target', event, self.logger, self.source)
        else:
            pass
        if not reader.finish():
            event.status = RecordStatus.INVALID
        else:
            pass
        self.inherit_directive_status(event)
        return event

    def check_event_target(self, reader: RecordReader, event: ContingencyEvent) -> None:
        """Reject action/equipment combinations absent from the documented grammar.

        :param reader: Cursor receiving validation errors.
        :param event: Fully identified action and equipment.
        """
        allowed: tuple[EquipmentKind, ...]
        if event.action in (EventAction.OPEN, EventAction.CLOSE):
            allowed = (EquipmentKind.BRANCH, EquipmentKind.THREE_WINDING, EquipmentKind.TERMINAL,
                       EquipmentKind.BREAKER, EquipmentKind.SWITCH, EquipmentKind.SWITCHING_DEVICE)
            if event.equipment == EquipmentKind.BUS and event.action == EventAction.OPEN:
                return
            elif event.equipment in (EquipmentKind.TWO_TERMINAL_DC, EquipmentKind.VSC_DC) and event.action == EventAction.CLOSE:
                return
            else:
                pass
        elif event.action == EventAction.BLOCK:
            allowed = (EquipmentKind.TWO_TERMINAL_DC, EquipmentKind.MULTI_TERMINAL_DC,
                       EquipmentKind.VSC_DC, EquipmentKind.FACTS)
        elif event.action in (EventAction.ADD, EventAction.REMOVE):
            allowed = (EquipmentKind.MACHINE, EquipmentKind.LOAD, EquipmentKind.SHUNT,
                       EquipmentKind.SWSHUNT, EquipmentKind.INDUCTION_MACHINE)
        elif event.action in (EventAction.SET, EventAction.CHANGE, EventAction.INCREASE, EventAction.DECREASE):
            allowed = (EquipmentKind.BUS, EquipmentKind.MACHINE, EquipmentKind.LOAD,
                       EquipmentKind.SHUNT, EquipmentKind.SWSHUNT, EquipmentKind.TWO_TERMINAL_DC, EquipmentKind.VSC_DC)
        elif event.action == EventAction.STUCK:
            allowed = (EquipmentKind.BREAKER,)
            if event.branch is None or event.branch.substation is None:
                reader.fail('STUCK BREAKER requires a substation/node reference')
            else:
                pass
        else:
            return
        if event.equipment not in allowed:
            reader.fail('Action is not defined for this equipment type')
        else:
            pass
        if event.action in (EventAction.SET, EventAction.CHANGE, EventAction.INCREASE, EventAction.DECREASE):
            quantities: tuple[Quantity, ...] = ()
            if event.equipment == EquipmentKind.BUS:
                quantities = (Quantity.GENERATION, Quantity.LOAD, Quantity.SHUNT)
            elif event.equipment == EquipmentKind.MACHINE:
                quantities = (Quantity.VSCHED, Quantity.ACTIVE, Quantity.REACTIVE)
            elif event.equipment == EquipmentKind.SWSHUNT:
                quantities = (Quantity.VSCHED, Quantity.VMAX, Quantity.VMIN, Quantity.REACTIVE)
            else:
                pass
            if len(quantities) > 0 and event.quantity not in quantities:
                reader.fail('Quantity is not defined for this event target')
            else:
                pass
        else:
            pass

    def check_change_unit(self, reader: RecordReader, event: ContingencyEvent) -> None:
        """Check quantity/unit pairs after parsing the command's exact structure.

        :param reader: Cursor receiving errors.
        :param event: Parsed boundary-condition change.
        """
        allowed: tuple[ValueUnit, ...] = (ValueUnit.MW, ValueUnit.PERCENT)
        if event.quantity in (Quantity.VSCHED, Quantity.VMAX, Quantity.VMIN):
            allowed = (ValueUnit.PERUNIT,)
        elif event.quantity == Quantity.REACTIVE:
            allowed = (ValueUnit.MVAR, ValueUnit.PERCENT)
        elif event.equipment == EquipmentKind.SHUNT or event.quantity == Quantity.SHUNT:
            allowed = (ValueUnit.MW, ValueUnit.MVAR, ValueUnit.PERCENT)
        elif event.equipment == EquipmentKind.TWO_TERMINAL_DC:
            allowed = (ValueUnit.MW, ValueUnit.AMPS, ValueUnit.KV, ValueUnit.OHMS)
        elif event.equipment == EquipmentKind.VSC_DC:
            allowed = (ValueUnit.MW, ValueUnit.KV, ValueUnit.OHMS)
        else:
            pass
        if event.unit not in allowed:
            reader.fail('Unit is not defined for this event quantity')
        else:
            pass

    def parse_move(self, reader: RecordReader, event: ContingencyEvent) -> None:
        """Read aggregate or individual equipment transfers without guessing units.

        :param reader: Cursor following MOVE.
        :param event: Transfer receiving the parsed fields.
        """
        if reader.peek() in ('MACHINE', 'UNIT', 'LOAD', 'SHUNT', 'SWSHUNT'):
            event.equipment = parse_equipment(reader)
            event.device_id = reader.text()
        else:
            pass
        value: int | float | None = reader.number()
        event.value = float(value) if value is not None else None
        event.unit = parse_unit(reader)
        if event.equipment is None:
            if reader.peek() in ('ACTIVE', 'REACTIVE'):
                event.quantity = Quantity.__members__.get(reader.peek(), None)
                reader.position += 1
            else:
                pass
            aggregate: str = reader.peek()
            if aggregate == 'GENERATION':
                event.equipment = EquipmentKind.MACHINE
                reader.position += 1
            else:
                event.equipment = parse_equipment(reader)
        else:
            pass
        reader.expect(('FROM',))
        reader.expect(('BUS',))
        event.bus = reader.bus()
        reader.expect(('TO',))
        reader.expect(('BUS',))
        event.to_bus = reader.bus()

    def parse_automatic(self, record: PsseRecord) -> AutomaticContingency:
        """Read an automatic request without generating any outages yet.

        :param record: SINGLE/DOUBLE/BUSDOUBLE/PARALLEL command.
        :return: Typed generation request.
        """
        kind: AutomaticKind = AutomaticKind.__members__[record.command.name]
        entry: AutomaticContingency = AutomaticContingency(record, kind)
        reader: RecordReader = RecordReader(record, self.logger, self.source)
        from_bus: bool = False
        explicit_action: bool = False
        if reader.peek() in ('OPEN', 'CLOSE', 'ISOLATE', 'STUCK'):
            explicit_action = True
            action: EventAction | None = EventAction.__members__.get(reader.peek(), None)
            entry.action = action if action is not None else EventAction.OPEN
            reader.position += 1
        else:
            pass
        if reader.peek() == 'ALL':
            entry.all_elements = True
            reader.position += 1
            reader.fail('ALL is not part of the documented automatic CON grammar')
        else:
            pass
        if reader.peek() in ('TIE', 'TIES'):
            entry.ties = True
            entry.equipment = EquipmentKind.BRANCH
            reader.position += 1
            reader.expect(('FROM',))
            entry.selection = parse_selection(reader)
            reader.expect(('TO',))
            entry.to_selection = parse_selection(reader)
        else:
            entry.equipment = parse_equipment(reader)
            if reader.peek() == 'IN':
                reader.position += 1
                entry.selection = parse_selection(reader)
            elif reader.peek() == 'FROM':
                from_bus = True
                reader.position += 1
                entry.selection = parse_selection(reader)
                if (entry.kind not in (AutomaticKind.SINGLE, AutomaticKind.DOUBLE)
                        or entry.selection is not None and entry.selection.kind != SelectionKind.BUS):
                    reader.fail('FROM BUS automatic outages require SINGLE or DOUBLE')
                else:
                    pass
            elif reader.peek() == 'WITH':
                reader.position += 1
                reader.expect(('LINE',))
                reader.expect(('OWNER',))
                owner: int | float | None = reader.number(integer=True)
                entry.line_owner = int(owner) if owner is not None else None
            elif not entry.all_elements:
                reader.fail('Expected an automatic contingency selector')
            else:
                pass
        if reader.peek() == '3WLOWVOLTAGE':
            entry.three_winding_low_voltage = True
            reader.position += 1
        else:
            pass
        if explicit_action or entry.equipment in (EquipmentKind.TERMINAL, EquipmentKind.SWITCH, EquipmentKind.SWITCHING_DEVICE):
            check_feature(self.node_support, 'automatic node-breaker actions', entry, self.logger, self.source)
        else:
            pass
        if entry.action == EventAction.ISOLATE and entry.equipment in (
                EquipmentKind.BUS, EquipmentKind.BREAKER, EquipmentKind.SWITCH, EquipmentKind.SWITCHING_DEVICE):
            check_feature(self.extended_isolation, 'extended automatic isolation (35.2)', entry, self.logger, self.source)
        else:
            pass
        if entry.action == EventAction.STUCK and (entry.equipment != EquipmentKind.BREAKER or entry.kind != AutomaticKind.SINGLE):
            reader.fail('Automatic STUCK requires SINGLE BREAKER')
        else:
            pass
        # CON's automatic grammar uses simple subsystem selectors, not MON's
        # later range selectors. Keep that distinction even in newer releases.
        for selection in (entry.selection, entry.to_selection):
            if selection is not None:
                allowed: tuple[SelectionKind, ...] = (SelectionKind.AREA, SelectionKind.ZONE,
                                                       SelectionKind.OWNER, SelectionKind.KV, SelectionKind.SUBSYSTEM)
                if (selection.last is not None or selection.last_bus is not None
                        or selection.kind not in allowed and not (from_bus and selection.kind == SelectionKind.BUS)):
                    reader.fail('Invalid automatic contingency selector')
                else:
                    pass
            else:
                pass
        if not reader.finish():
            entry.status = RecordStatus.INVALID
        else:
            pass
        return entry
