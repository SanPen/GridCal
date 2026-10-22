# SPDX-License-Identifier: MPL-2.0
"""Named SEQ fields from POM 33 §5.5.1 and DataFormats 34/35/36.

Omitted optional values remain None, including values whose defaults depend on
RAW data. Version layout differences are explicit constructor parameters fixed
by the version-specific document classes, not inferred from input field counts.
"""
from __future__ import annotations

from enum import Enum

from VeraGridEngine.IO.raw.psse_data import DataReader, DataRow
from VeraGridEngine.IO.raw.versioned.base.auxiliary import RecordStatus


class FaultCharacteristicKind(Enum):
    """Time- or voltage-dependent converter fault contribution."""

    TIME = 'TIM'
    VOLTAGE = 'VLT'


class SequenceEntry:
    """A sequence record with retained source and an explicit validity status."""

    __slots__ = ('row', 'status')

    def __init__(self, row: DataRow) -> None:
        """Initialize source ownership.

        :param row: Physical or assembled logical record.
        """
        self.row: DataRow = row
        self.status: RecordStatus = row.status


class SequenceGenerator(SequenceEntry):
    """Typed generator sequence data, in file units."""

    __slots__ = ('bus', 'machine_id', 'r_positive', 'x_subtransient', 'x_transient', 'x_synchronous', 'r_negative', 'x_negative', 'r_zero', 'x_zero', 'grounding_code', 'r_ground', 'x_ground', 'reference_angle')

    def __init__(self, reader: DataReader, reference_angle: bool) -> None:
        """Read the documented field order and retain omissions.

        :param reader: Checked field cursor.
        :param reference_angle: Version 34 and later append REFDEG.
        """
        super().__init__(reader.row)
        self.bus: int | None = reader.positive_integer()
        self.machine_id: str | None = reader.text(default='1', maximum=2)
        self.r_positive: float | None = reader.real()
        self.x_subtransient: float | None = reader.real()
        self.x_transient: float | None = reader.real()
        self.x_synchronous: float | None = reader.real()
        self.r_negative: float | None = reader.real()
        self.x_negative: float | None = reader.real()
        self.r_zero: float | None = reader.real()
        self.x_zero: float | None = reader.real()
        self.grounding_code: int | None = reader.integer()
        self.r_ground: float | None = reader.real()
        self.x_ground: float | None = reader.real()
        self.reference_angle: float | None = None
        if reference_angle:
            self.reference_angle = reader.real()
        else:
            pass
        if self.grounding_code is not None and self.grounding_code not in (1, 2):
            reader.fail('Unknown grounding impedance unit code')
        else:
            pass
        if not reader.finish():
            self.status = RecordStatus.INVALID
        else:
            pass


class SequenceLoad(SequenceEntry):
    """Typed load sequence data, in file units."""

    __slots__ = ('bus', 'load_id', 'p_negative', 'q_negative', 'grounded', 'p_zero', 'q_zero')

    def __init__(self, reader: DataReader) -> None:
        """Read the documented field order and retain omissions.

        :param reader: Checked field cursor.
        """
        super().__init__(reader.row)
        self.bus: int | None = reader.positive_integer()
        self.load_id: str | None = reader.text(default='1', maximum=2)
        self.p_negative: float | None = reader.real()
        self.q_negative: float | None = reader.real()
        self.grounded: int | None = reader.integer()
        self.p_zero: float | None = reader.real()
        self.q_zero: float | None = reader.real()
        if self.grounded is not None and self.grounded not in (0, 1):
            reader.fail('Grounding flag must be 0 or 1')
        else:
            pass
        if not reader.finish():
            self.status = RecordStatus.INVALID
        else:
            pass


class SequenceBranch(SequenceEntry):
    """Typed branch sequence data, in file units."""

    __slots__ = ('from_bus', 'to_bus', 'circuit', 'r_zero', 'x_zero', 'b_zero', 'g_from', 'b_from', 'g_to', 'b_to', 'rated_mov_current', 'short_circuit_type')

    def __init__(self, reader: DataReader) -> None:
        """Read the documented field order and retain omissions.

        :param reader: Checked field cursor.
        """
        super().__init__(reader.row)
        self.from_bus: int | None = reader.positive_integer()
        self.to_bus: int | None = reader.positive_integer()
        self.circuit: str | None = reader.text(default='1', maximum=2)
        self.r_zero: float | None = reader.real()
        self.x_zero: float | None = reader.real()
        self.b_zero: float | None = reader.real()
        self.g_from: float | None = reader.real()
        self.b_from: float | None = reader.real()
        self.g_to: float | None = reader.real()
        self.b_to: float | None = reader.real()
        self.rated_mov_current: float | None = reader.real()
        self.short_circuit_type: int | None = reader.integer()
        if self.rated_mov_current is not None and self.rated_mov_current < 0:
            reader.fail('MOV rated current cannot be negative')
        else:
            pass
        if self.short_circuit_type is not None and self.short_circuit_type not in (0, 1, 2, 3):
            reader.fail('Invalid series capacitor protection mode')
        else:
            pass
        if not reader.finish():
            self.status = RecordStatus.INVALID
        else:
            pass


class SequenceMutual(SequenceEntry):
    """Typed mutual sequence data, in file units."""

    __slots__ = ('from_bus', 'to_bus', 'circuit', 'other_from_bus', 'other_to_bus', 'other_circuit', 'r_mutual', 'x_mutual', 'first_start', 'first_end', 'second_start', 'second_end')

    def __init__(self, reader: DataReader) -> None:
        """Read the documented field order and retain omissions.

        :param reader: Checked field cursor.
        """
        super().__init__(reader.row)
        self.from_bus: int | None = reader.positive_integer()
        self.to_bus: int | None = reader.positive_integer()
        self.circuit: str | None = reader.text(default='1', maximum=2)
        self.other_from_bus: int | None = reader.positive_integer()
        self.other_to_bus: int | None = reader.positive_integer()
        self.other_circuit: str | None = reader.text(default='1', maximum=2)
        self.r_mutual: float | None = reader.real()
        self.x_mutual: float | None = reader.real()
        self.first_start: float | None = reader.real()
        self.first_end: float | None = reader.real()
        self.second_start: float | None = reader.real()
        self.second_end: float | None = reader.real()
        if not reader.finish():
            self.status = RecordStatus.INVALID
        else:
            pass


class SequenceFixedShunt(SequenceEntry):
    """Typed fixedshunt sequence data, in file units."""

    __slots__ = ('bus', 'shunt_id', 'g_zero', 'b_zero')

    def __init__(self, reader: DataReader) -> None:
        """Read the documented field order and retain omissions.

        :param reader: Checked field cursor.
        """
        super().__init__(reader.row)
        self.bus: int | None = reader.positive_integer()
        self.shunt_id: str | None = reader.text(default='1', maximum=2)
        self.g_zero: float | None = reader.real()
        self.b_zero: float | None = reader.real()
        if not reader.finish():
            self.status = RecordStatus.INVALID
        else:
            pass


class SequenceInduction(SequenceEntry):
    """Typed induction sequence data, in file units."""

    __slots__ = ('bus', 'machine_id', 'grounding_code', 'grounded', 'locked_rotor_subtransient', 'r_over_x_subtransient', 'r_zero', 'x_zero', 'r_ground', 'x_ground', 'locked_rotor_transient', 'r_over_x_transient', 'locked_rotor_negative', 'r_over_x_negative')

    def __init__(self, reader: DataReader, expanded: bool) -> None:
        """Read the documented field order and retain omissions.

        :param reader: Checked field cursor.
        :param expanded: Version 34 and later add transient/negative-sequence ratios.
        """
        super().__init__(reader.row)
        self.bus: int | None = reader.positive_integer()
        self.machine_id: str | None = reader.text(default='1', maximum=2)
        self.grounding_code: int | None = reader.integer()
        self.grounded: int | None = reader.integer()
        self.locked_rotor_subtransient: float | None = reader.real()
        self.r_over_x_subtransient: float | None = reader.real()
        self.r_zero: float | None = reader.real()
        self.x_zero: float | None = reader.real()
        self.r_ground: float | None = reader.real()
        self.x_ground: float | None = reader.real()
        self.locked_rotor_transient: float | None = None
        self.r_over_x_transient: float | None = None
        self.locked_rotor_negative: float | None = None
        self.r_over_x_negative: float | None = None
        if expanded:
            self.locked_rotor_transient = reader.real()
            self.r_over_x_transient = reader.real()
            self.locked_rotor_negative = reader.real()
            self.r_over_x_negative = reader.real()
        else:
            pass
        if self.grounding_code is not None and self.grounding_code not in (1, 2):
            reader.fail('Unknown grounding impedance unit code')
        else:
            pass
        if self.grounded is not None and self.grounded not in (0, 1):
            reader.fail('Grounding flag must be 0 or 1')
        else:
            pass
        if not reader.finish():
            self.status = RecordStatus.INVALID
        else:
            pass


class SequenceTransformer(SequenceEntry):
    """Typed transformer sequence data, in file units."""

    __slots__ = ('from_bus', 'to_bus', 'third_bus', 'circuit', 'impedance_code', 'grounding_code', 'connection_code', 'r_ground_1', 'x_ground_1', 'r_zero_1', 'x_zero_1', 'r_ground_2', 'x_ground_2', 'r_zero_2', 'x_zero_2', 'r_ground_3', 'x_ground_3', 'r_zero_3', 'x_zero_3', 'r_neutral', 'x_neutral')

    def __init__(self, reader: DataReader) -> None:
        """Read the documented field order and retain omissions.

        :param reader: Checked field cursor.
        """
        super().__init__(reader.row)
        self.from_bus: int | None = reader.positive_integer()
        self.to_bus: int | None = reader.positive_integer()
        self.third_bus: int | None = reader.positive_integer(required=False, allow_zero=True)
        self.circuit: str | None = reader.text(default='1', maximum=2)
        self.impedance_code: int | None = reader.integer()
        self.grounding_code: int | None = reader.integer()
        self.connection_code: int | None = reader.integer()
        self.r_ground_1: float | None = reader.real()
        self.x_ground_1: float | None = reader.real()
        self.r_zero_1: float | None = reader.real()
        self.x_zero_1: float | None = reader.real()
        self.r_ground_2: float | None = reader.real()
        self.x_ground_2: float | None = reader.real()
        self.r_zero_2: float | None = reader.real()
        self.x_zero_2: float | None = reader.real()
        self.r_ground_3: float | None = None
        self.x_ground_3: float | None = None
        self.r_zero_3: float | None = None
        self.x_zero_3: float | None = None
        self.r_neutral: float | None = None
        self.x_neutral: float | None = None
        if self.third_bus is not None and self.third_bus != 0:
            self.r_ground_3 = reader.real()
            self.x_ground_3 = reader.real()
            self.r_zero_3 = reader.real()
            self.x_zero_3 = reader.real()
        else:
            pass
        self.r_neutral = reader.real()
        self.x_neutral = reader.real()
        if self.grounding_code is not None and self.grounding_code not in (1, 2, 3):
            reader.fail('Unknown grounding impedance unit code')
        else:
            pass
        if self.impedance_code is not None and self.impedance_code not in (1, 2):
            reader.fail('Unknown winding impedance unit code')
        else:
            pass
        if not reader.finish():
            self.status = RecordStatus.INVALID
        else:
            pass


class SequenceNcsGenerator(SequenceEntry):
    """Typed ncsgenerator sequence data, in file units."""

    __slots__ = ('bus', 'machine_id', 'characteristic_type', 'positive_table', 'negative_table', 'maximum_current', 'deadband_minimum', 'deadband_maximum')

    def __init__(self, reader: DataReader) -> None:
        """Read the documented field order and retain omissions.

        :param reader: Checked field cursor.
        """
        super().__init__(reader.row)
        self.bus: int | None = reader.positive_integer()
        self.machine_id: str | None = reader.text(default='1', maximum=2)
        self.characteristic_type: FaultCharacteristicKind | None = None
        kind: str | None = reader.text(default='TIM', maximum=3)
        if kind in ('TIM', 'VLT'):
            self.characteristic_type = FaultCharacteristicKind.TIME if kind == 'TIM' else FaultCharacteristicKind.VOLTAGE
        else:
            reader.fail('Unknown fault contribution characteristic type')
        self.positive_table: str | None = reader.text(required=True, maximum=12)
        self.negative_table: str | None = reader.text(maximum=12)
        self.maximum_current: float | None = reader.real()
        self.deadband_minimum: float | None = reader.real()
        self.deadband_maximum: float | None = reader.real()
        if self.deadband_minimum is not None and self.deadband_maximum is not None and self.deadband_minimum > self.deadband_maximum:
            reader.fail('Fault contribution deadband minimum exceeds maximum')
        else:
            pass
        if not reader.finish():
            self.status = RecordStatus.INVALID
        else:
            pass
