# SPDX-License-Identifier: MPL-2.0
"""Named OPF fields from POM 33 §14.9 and DataFormats 34–36 OPF chapters.

Units are those of the manual; None retains a case-dependent omission.
"""
from __future__ import annotations
from enum import IntEnum
from VeraGridEngine.IO.raw.psse_data import DataReader, DataRow
from VeraGridEngine.IO.raw.versioned.base.auxiliary import RecordStatus


class RopVariable(IntEnum):
    """Variable identities used in linear dependency coefficients."""
    VOLTAGE_MAGNITUDE = 1
    VOLTAGE_ANGLE = 2
    ACTIVE_GENERATION = 3
    REACTIVE_GENERATION = 4
    TRANSFORMER_TAP = 5
    BRANCH_FLOW = 6
    INTERFACE_FLOW = 7
    ADJUSTABLE_SHUNT = 8
    SWITCHED_SHUNT = 9
    LOAD_ADJUSTMENT = 10


class RopEntry:
    """Source, status and optional nested membership of an OPF record."""
    __slots__ = ('row', 'validity', 'members')

    def __init__(self, row: DataRow) -> None:
        """Initialize source ownership.

        :param row: Original source record.
        """
        self.row: DataRow = row
        self.validity: RecordStatus = row.status
        self.members: tuple[RopEntry, ...] = ()


class RopBusVoltage(RopEntry):
    """Documented BusVoltage field order."""
    __slots__ = ('bus', 'v_normal_max', 'v_normal_min', 'v_emergency_max', 'v_emergency_min', 'limit_type', 'penalty',)

    def __init__(self, reader: DataReader) -> None:
        """Read fields without applying working-case defaults.

        :param reader: Checked source cursor.
        """
        super().__init__(reader.row)
        self.bus: int | None = reader.positive_integer()
        self.v_normal_max: float | None = reader.real()
        self.v_normal_min: float | None = reader.real()
        self.v_emergency_max: float | None = reader.real()
        self.v_emergency_min: float | None = reader.real()
        self.limit_type: int | None = reader.integer()
        self.penalty: float | None = reader.real()
        if self.limit_type is not None and self.limit_type not in (0, 1, 2, 3):
            reader.fail('Invalid limit_type code')
        else:
            pass
        if self.v_normal_min is not None and self.v_normal_max is not None and self.v_normal_min > self.v_normal_max:
            reader.fail('Minimum exceeds maximum')
        else:
            pass
        if self.v_emergency_min is not None and self.v_emergency_max is not None and self.v_emergency_min > self.v_emergency_max:
            reader.fail('Minimum exceeds maximum')
        else:
            pass
        if self.limit_type is not None and self.limit_type not in (0, 1, 2, 3):
            reader.fail('Invalid limit_type code')
        else:
            pass
        if self.v_normal_min is not None and self.v_normal_max is not None and self.v_normal_min > self.v_normal_max:
            reader.fail('Minimum exceeds maximum')
        else:
            pass
        if self.v_emergency_min is not None and self.v_emergency_max is not None and self.v_emergency_min > self.v_emergency_max:
            reader.fail('Minimum exceeds maximum')
        else:
            pass
        if not reader.finish():
            self.validity = RecordStatus.INVALID
        else:
            pass


class RopAdjustableShunt(RopEntry):
    """Documented AdjustableShunt field order."""
    __slots__ = ('bus', 'shunt_id', 'b_initial', 'b_max', 'b_min', 'cost', 'cost_type', 'status', 'cost_table',)

    def __init__(self, reader: DataReader, status_before_cost: bool) -> None:
        """Read fields without applying working-case defaults.

        :param reader: Checked source cursor.
        :param status_before_cost: Version 35/36 put STATUS before CTYP.
        """
        super().__init__(reader.row)
        self.bus: int | None = reader.positive_integer()
        self.shunt_id: str | None = reader.text(default='1', maximum=2)
        self.b_initial: float | None = reader.real()
        self.b_max: float | None = reader.real()
        self.b_min: float | None = reader.real()
        self.cost: float | None = reader.real()
        self.cost_type: int | None = None
        self.status: int | None = None
        if status_before_cost:
            self.status = reader.integer()
            self.cost_type = reader.integer()
        else:
            self.cost_type = reader.integer()
            self.status = reader.integer()
        self.cost_table: int | None = reader.integer()
        if self.cost_type is not None and self.cost_type not in (1, 2, 3):
            reader.fail('Invalid cost_type code')
        else:
            pass
        if self.status is not None and self.status not in (0, 1):
            reader.fail('Invalid status code')
        else:
            pass
        if self.b_min is not None and self.b_max is not None and self.b_min > self.b_max:
            reader.fail('Minimum exceeds maximum')
        else:
            pass
        if self.cost_type is not None and self.cost_type not in (1, 2, 3):
            reader.fail('Invalid cost_type code')
        else:
            pass
        if self.status is not None and self.status not in (0, 1):
            reader.fail('Invalid status code')
        else:
            pass
        if self.b_min is not None and self.b_max is not None and self.b_min > self.b_max:
            reader.fail('Minimum exceeds maximum')
        else:
            pass
        if not reader.finish():
            self.validity = RecordStatus.INVALID
        else:
            pass


class RopBusLoad(RopEntry):
    """Documented BusLoad field order."""
    __slots__ = ('bus', 'load_id', 'load_table',)

    def __init__(self, reader: DataReader) -> None:
        """Read fields without applying working-case defaults.

        :param reader: Checked source cursor.
        """
        super().__init__(reader.row)
        self.bus: int | None = reader.positive_integer()
        self.load_id: str | None = reader.text(default='1', maximum=2)
        self.load_table: int | None = reader.integer()
        if not reader.finish():
            self.validity = RecordStatus.INVALID
        else:
            pass


class RopLoadTable(RopEntry):
    """Documented LoadTable field order."""
    __slots__ = ('table', 'multiplier', 'multiplier_max', 'multiplier_min', 'fraction', 'fraction_max', 'fraction_min', 'cost', 'cost_type', 'status', 'cost_table',)

    def __init__(self, reader: DataReader) -> None:
        """Read fields without applying working-case defaults.

        :param reader: Checked source cursor.
        """
        super().__init__(reader.row)
        self.table: int | None = reader.positive_integer()
        self.multiplier: float | None = reader.real()
        self.multiplier_max: float | None = reader.real()
        self.multiplier_min: float | None = reader.real()
        self.fraction: float | None = reader.real()
        self.fraction_max: float | None = reader.real()
        self.fraction_min: float | None = reader.real()
        self.cost: float | None = reader.real()
        self.cost_type: int | None = reader.integer()
        self.status: int | None = reader.integer()
        self.cost_table: int | None = reader.integer()
        if self.status is not None and self.status not in (0, 1):
            reader.fail('Invalid status code')
        else:
            pass
        if self.multiplier_min is not None and self.multiplier_max is not None and self.multiplier_min > self.multiplier_max:
            reader.fail('Minimum exceeds maximum')
        else:
            pass
        if self.fraction_min is not None and self.fraction_max is not None and self.fraction_min > self.fraction_max:
            reader.fail('Minimum exceeds maximum')
        else:
            pass
        if self.status is not None and self.status not in (0, 1):
            reader.fail('Invalid status code')
        else:
            pass
        if self.multiplier_min is not None and self.multiplier_max is not None and self.multiplier_min > self.multiplier_max:
            reader.fail('Minimum exceeds maximum')
        else:
            pass
        if self.fraction_min is not None and self.fraction_max is not None and self.fraction_min > self.fraction_max:
            reader.fail('Minimum exceeds maximum')
        else:
            pass
        if not reader.finish():
            self.validity = RecordStatus.INVALID
        else:
            pass


class RopGeneratorDispatch(RopEntry):
    """Documented GeneratorDispatch field order."""
    __slots__ = ('bus', 'machine_id', 'dispatch', 'dispatch_table',)

    def __init__(self, reader: DataReader) -> None:
        """Read fields without applying working-case defaults.

        :param reader: Checked source cursor.
        """
        super().__init__(reader.row)
        self.bus: int | None = reader.positive_integer()
        self.machine_id: str | None = reader.text(default='1', maximum=2)
        self.dispatch: float | None = reader.real()
        self.dispatch_table: int | None = reader.integer()
        if not reader.finish():
            self.validity = RecordStatus.INVALID
        else:
            pass


class RopActiveDispatch(RopEntry):
    """Documented ActiveDispatch field order."""
    __slots__ = ('table', 'p_max', 'p_min', 'fuel_cost', 'cost_type', 'status', 'cost_table',)

    def __init__(self, reader: DataReader) -> None:
        """Read fields without applying working-case defaults.

        :param reader: Checked source cursor.
        """
        super().__init__(reader.row)
        self.table: int | None = reader.positive_integer()
        self.p_max: float | None = reader.real()
        self.p_min: float | None = reader.real()
        self.fuel_cost: float | None = reader.real()
        self.cost_type: int | None = reader.integer()
        self.status: int | None = reader.integer()
        self.cost_table: int | None = reader.integer()
        if self.cost_type is not None and self.cost_type not in (1, 2, 3):
            reader.fail('Invalid cost_type code')
        else:
            pass
        if self.status is not None and self.status not in (0, 1):
            reader.fail('Invalid status code')
        else:
            pass
        if self.p_min is not None and self.p_max is not None and self.p_min > self.p_max:
            reader.fail('Minimum exceeds maximum')
        else:
            pass
        if self.cost_type is not None and self.cost_type not in (1, 2, 3):
            reader.fail('Invalid cost_type code')
        else:
            pass
        if self.status is not None and self.status not in (0, 1):
            reader.fail('Invalid status code')
        else:
            pass
        if self.p_min is not None and self.p_max is not None and self.p_min > self.p_max:
            reader.fail('Minimum exceeds maximum')
        else:
            pass
        if not reader.finish():
            self.validity = RecordStatus.INVALID
        else:
            pass


class RopGenerationReserve(RopEntry):
    """Documented GenerationReserve field order."""
    __slots__ = ('bus', 'machine_id', 'ramp', 'maximum',)

    def __init__(self, reader: DataReader) -> None:
        """Read fields without applying working-case defaults.

        :param reader: Checked source cursor.
        """
        super().__init__(reader.row)
        self.bus: int | None = reader.positive_integer()
        self.machine_id: str | None = reader.text(default='1', maximum=2)
        self.ramp: float | None = reader.real()
        self.maximum: float | None = reader.real()
        if not reader.finish():
            self.validity = RecordStatus.INVALID
        else:
            pass


class RopReactiveCapability(RopEntry):
    """Documented ReactiveCapability field order."""
    __slots__ = ('bus', 'machine_id', 'x_d', 'stator_current_max', 'power_factor_lagging', 'power_factor_leading', 'q_limit', 'status',)

    def __init__(self, reader: DataReader) -> None:
        """Read fields without applying working-case defaults.

        :param reader: Checked source cursor.
        """
        super().__init__(reader.row)
        self.bus: int | None = reader.positive_integer()
        self.machine_id: str | None = reader.text(default='1', maximum=2)
        self.x_d: float | None = reader.real()
        self.stator_current_max: float | None = reader.real()
        self.power_factor_lagging: float | None = reader.real()
        self.power_factor_leading: float | None = reader.real()
        self.q_limit: float | None = reader.real()
        self.status: int | None = reader.integer()
        if self.status is not None and self.status not in (0, 1, 2, 3, 4):
            reader.fail('Invalid status code')
        else:
            pass
        if self.status is not None and self.status not in (0, 1, 2, 3, 4):
            reader.fail('Invalid status code')
        else:
            pass
        if not reader.finish():
            self.validity = RecordStatus.INVALID
        else:
            pass


class RopBranchReactance(RopEntry):
    """Documented BranchReactance field order."""
    __slots__ = ('from_bus', 'to_bus', 'circuit', 'multiplier', 'multiplier_max', 'multiplier_min', 'cost', 'cost_type', 'status', 'cost_table',)

    def __init__(self, reader: DataReader) -> None:
        """Read fields without applying working-case defaults.

        :param reader: Checked source cursor.
        """
        super().__init__(reader.row)
        self.from_bus: int | None = reader.positive_integer()
        self.to_bus: int | None = reader.integer()
        self.circuit: str | None = reader.text(default='1', maximum=2)
        self.multiplier: float | None = reader.real()
        self.multiplier_max: float | None = reader.real()
        self.multiplier_min: float | None = reader.real()
        self.cost: float | None = reader.real()
        self.cost_type: int | None = reader.integer()
        self.status: int | None = reader.integer()
        self.cost_table: int | None = reader.integer()
        if self.status is not None and self.status not in (0, 1):
            reader.fail('Invalid status code')
        else:
            pass
        if self.multiplier_min is not None and self.multiplier_max is not None and self.multiplier_min > self.multiplier_max:
            reader.fail('Minimum exceeds maximum')
        else:
            pass
        if self.status is not None and self.status not in (0, 1):
            reader.fail('Invalid status code')
        else:
            pass
        if self.multiplier_min is not None and self.multiplier_max is not None and self.multiplier_min > self.multiplier_max:
            reader.fail('Minimum exceeds maximum')
        else:
            pass
        if not reader.finish():
            self.validity = RecordStatus.INVALID
        else:
            pass


class RopPolynomialCost(RopEntry):
    """Documented PolynomialCost field order."""
    __slots__ = ('table', 'label', 'constant', 'linear', 'quadratic', 'exponential', 'exponent',)

    def __init__(self, reader: DataReader) -> None:
        """Read fields without applying working-case defaults.

        :param reader: Checked source cursor.
        """
        super().__init__(reader.row)
        self.table: int | None = reader.positive_integer()
        self.label: str | None = reader.text(maximum=12)
        self.constant: float | None = reader.real()
        self.linear: float | None = reader.real()
        self.quadratic: float | None = reader.real()
        self.exponential: float | None = reader.real()
        self.exponent: float | None = reader.real()
        if not reader.finish():
            self.validity = RecordStatus.INVALID
        else:
            pass


class RopPeriodReserve(RopEntry):
    """Documented PeriodReserve field order."""
    __slots__ = ('reserve_id', 'mw_limit', 'duration', 'status',)

    def __init__(self, reader: DataReader) -> None:
        """Read fields without applying working-case defaults.

        :param reader: Checked source cursor.
        """
        super().__init__(reader.row)
        self.reserve_id: int | None = reader.positive_integer()
        self.mw_limit: float | None = reader.real()
        self.duration: float | None = reader.real()
        self.status: int | None = reader.integer()
        if self.status is not None and self.status not in (0, 1):
            reader.fail('Invalid status code')
        else:
            pass
        if self.reserve_id is not None and self.reserve_id > 15:
            reader.fail('Reserve ID must be between 1 and 15')
        else:
            pass
        if self.status is not None and self.status not in (0, 1):
            reader.fail('Invalid status code')
        else:
            pass
        if self.reserve_id is not None and self.reserve_id > 15:
            reader.fail('Reserve ID must be between 1 and 15')
        else:
            pass
        if not reader.finish():
            self.validity = RecordStatus.INVALID
        else:
            pass


class RopBranchFlow(RopEntry):
    """Documented BranchFlow field order."""
    __slots__ = ('from_bus', 'to_bus', 'circuit', 'flow_id', 'maximum', 'minimum', 'emergency_maximum', 'emergency_minimum', 'flow_type', 'limit_type', 'penalty', 'third_bus',)

    def __init__(self, reader: DataReader) -> None:
        """Read fields without applying working-case defaults.

        :param reader: Checked source cursor.
        """
        super().__init__(reader.row)
        self.from_bus: int | None = reader.positive_integer()
        self.to_bus: int | None = reader.integer()
        self.circuit: str | None = reader.text(default='1', maximum=2)
        self.flow_id: str | None = reader.text(default='1', maximum=1)
        self.maximum: float | None = reader.real()
        self.minimum: float | None = reader.real()
        self.emergency_maximum: float | None = reader.real()
        self.emergency_minimum: float | None = reader.real()
        self.flow_type: int | None = reader.integer()
        self.limit_type: int | None = reader.integer()
        self.penalty: float | None = reader.real()
        self.third_bus: int | None = reader.integer()
        if self.flow_type is not None and self.flow_type not in (1, 2, 3, 4):
            reader.fail('Invalid flow_type code')
        else:
            pass
        if self.limit_type is not None and self.limit_type not in (0, 1, 2, 3):
            reader.fail('Invalid limit_type code')
        else:
            pass
        if self.minimum is not None and self.maximum is not None and self.minimum > self.maximum:
            reader.fail('Minimum exceeds maximum')
        else:
            pass
        if self.emergency_minimum is not None and self.emergency_maximum is not None and self.emergency_minimum > self.emergency_maximum:
            reader.fail('Minimum exceeds maximum')
        else:
            pass
        if self.flow_type is not None and self.flow_type not in (1, 2, 3, 4):
            reader.fail('Invalid flow_type code')
        else:
            pass
        if self.limit_type is not None and self.limit_type not in (0, 1, 2, 3):
            reader.fail('Invalid limit_type code')
        else:
            pass
        if self.minimum is not None and self.maximum is not None and self.minimum > self.maximum:
            reader.fail('Minimum exceeds maximum')
        else:
            pass
        if self.emergency_minimum is not None and self.emergency_maximum is not None and self.emergency_minimum > self.emergency_maximum:
            reader.fail('Minimum exceeds maximum')
        else:
            pass
        if not reader.finish():
            self.validity = RecordStatus.INVALID
        else:
            pass


class RopInterfaceFlow(RopEntry):
    """Documented InterfaceFlow field order."""
    __slots__ = ('interface_id', 'label', 'maximum', 'minimum', 'flow_type', 'limit_type', 'penalty',)

    def __init__(self, reader: DataReader) -> None:
        """Read fields without applying working-case defaults.

        :param reader: Checked source cursor.
        """
        super().__init__(reader.row)
        self.interface_id: int | None = reader.positive_integer()
        self.label: str | None = reader.text(maximum=32)
        self.maximum: float | None = reader.real()
        self.minimum: float | None = reader.real()
        self.flow_type: int | None = reader.integer()
        self.limit_type: int | None = reader.integer()
        self.penalty: float | None = reader.real()
        if self.flow_type is not None and self.flow_type not in (1, 2, 3, 4):
            reader.fail('Invalid flow_type code')
        else:
            pass
        if self.limit_type is not None and self.limit_type not in (0, 1, 2, 3):
            reader.fail('Invalid limit_type code')
        else:
            pass
        if self.minimum is not None and self.maximum is not None and self.minimum > self.maximum:
            reader.fail('Minimum exceeds maximum')
        else:
            pass
        if self.flow_type is not None and self.flow_type not in (1, 2, 3, 4):
            reader.fail('Invalid flow_type code')
        else:
            pass
        if self.limit_type is not None and self.limit_type not in (0, 1, 2, 3):
            reader.fail('Invalid limit_type code')
        else:
            pass
        if self.minimum is not None and self.maximum is not None and self.minimum > self.maximum:
            reader.fail('Minimum exceeds maximum')
        else:
            pass
        if not reader.finish():
            self.validity = RecordStatus.INVALID
        else:
            pass


class RopLinearDependency(RopEntry):
    """Documented LinearDependency field order."""
    __slots__ = ('equation_id', 'label', 'slack_max', 'slack_min',)

    def __init__(self, reader: DataReader) -> None:
        """Read fields without applying working-case defaults.

        :param reader: Checked source cursor.
        """
        super().__init__(reader.row)
        self.equation_id: int | None = reader.positive_integer()
        self.label: str | None = reader.text(maximum=32)
        self.slack_max: float | None = reader.real()
        self.slack_min: float | None = reader.real()
        if self.slack_min is not None and self.slack_max is not None and self.slack_min > self.slack_max:
            reader.fail('Minimum exceeds maximum')
        else:
            pass
        if self.slack_min is not None and self.slack_max is not None and self.slack_min > self.slack_max:
            reader.fail('Minimum exceeds maximum')
        else:
            pass
        if not reader.finish():
            self.validity = RecordStatus.INVALID
        else:
            pass


class RopReserveMember(RopEntry):
    """Documented ReserveMember field order."""
    __slots__ = ('bus', 'machine_id',)

    def __init__(self, reader: DataReader) -> None:
        """Read fields without applying working-case defaults.

        :param reader: Checked source cursor.
        """
        super().__init__(reader.row)
        self.bus: int | None = reader.positive_integer()
        self.machine_id: str | None = reader.text(default='1', maximum=2)
        if not reader.finish():
            self.validity = RecordStatus.INVALID
        else:
            pass


class RopInterfaceMember(RopEntry):
    """Documented InterfaceMember field order."""
    __slots__ = ('from_bus', 'to_bus', 'circuit', 'third_bus',)

    def __init__(self, reader: DataReader) -> None:
        """Read fields without applying working-case defaults.

        :param reader: Checked source cursor.
        """
        super().__init__(reader.row)
        self.from_bus: int | None = reader.positive_integer()
        self.to_bus: int | None = reader.integer()
        self.circuit: str | None = reader.text(default='1', maximum=2)
        self.third_bus: int | None = reader.integer()
        if not reader.finish():
            self.validity = RecordStatus.INVALID
        else:
            pass
