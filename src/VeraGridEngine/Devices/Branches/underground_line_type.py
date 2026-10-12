# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations
from typing import Dict, List, Tuple

import numpy as np

from VeraGridEngine.basic_structures import CxMat, Logger
from VeraGridEngine.Devices.admittance_matrix import AdmittanceMatrix
from VeraGridEngine.Devices.Parents.editable_device import DeviceType, GCProp
from VeraGridEngine.Devices.Parents.dynamic_parent import DynamicDevice
from VeraGridEngine.Devices.Branches.overhead_line_type import build_y_4x4, n_circuits, phase2circuit
from VeraGridEngine.Devices.Branches.sequence_line_type import sequence_to_phase_matrix
from VeraGridEngine.Devices.Branches.underground_cable_calculation import calculate_underground_cable_matrices
from VeraGridEngine.Devices.Branches.underground_cable_type import UndergroundCableType
from VeraGridEngine.enumerations import PrpCat, SubObjectType


class CableInSystem:
    """Association between one physical cable and its system position."""

    __slots__ = (
        'cable',
        'name',
        'xpos',
        'ypos',
        '_phase',
        'circuit_index',
        'phase_type',
        'device_type',
    )

    def __init__(self,
                 cable: UndergroundCableType,
                 xpos: float = 0.0,
                 ypos: float = 1.0,
                 phase: int = 1) -> None:
        """Create one positioned cable relationship.

        :param cable: Physical cable catalogue entry.
        :param xpos: Horizontal coordinate in metres.
        :param ypos: Positive burial depth in metres.
        :param phase: Global phase number, starting at one.
        :return: None.
        """
        self.cable: UndergroundCableType | None = cable
        self.name: str = cable.name
        self.xpos: float = float(xpos)
        self.ypos: float = float(ypos)
        self._phase: int = int(phase)
        self.circuit_index: int = 1
        self.phase_type: str = 'A'
        self.device_type: DeviceType = DeviceType.UndergroundCableTypeDevice
        self.set_phase(phase=phase)

    def set_phase(self, phase: int) -> None:
        """Set phase label and circuit index from a global phase number.

        :param phase: Global phase number, starting at one.
        :return: None.
        """
        phase_number: int = int(phase)
        circuit_index: int = phase2circuit(phase=phase_number)
        phase_remainder: int = (phase_number - 1) % 3
        self._phase = phase_number
        self.circuit_index = circuit_index
        if phase_remainder == 0:
            self.phase_type = 'A'
        elif phase_remainder == 1:
            self.phase_type = 'B'
        else:
            self.phase_type = 'C'

    @property
    def phase(self) -> int:
        """Return the global phase number."""
        return self._phase

    @phase.setter
    def phase(self, value: int) -> None:
        """Set the global phase number.

        :param value: Global phase number.
        :return: None.
        """
        self.set_phase(phase=value)

    def to_dict(self) -> Dict[str, str | float | int | None]:
        """Return the persistent relation representation.

        :return: Serializable cable relationship.
        """
        cable_idtag: str | None = self.cable.idtag if self.cable is not None else None
        return dict(
            cable=cable_idtag,
            name=self.name,
            xpos=self.xpos,
            ypos=self.ypos,
            phase=self.phase,
            circuit_index=self.circuit_index,
        )

    def parse(self,
              data: Dict[str, str | float | int],
              cable_dict: Dict[str, UndergroundCableType]) -> None:
        """Load one persistent cable relationship.

        :param data: Serialized relationship data.
        :param cable_dict: Physical cables indexed by persistent identifier.
        :return: None.
        """
        cable_idtag: str = str(data.get('cable', ''))
        self.cable = cable_dict.get(cable_idtag, None)
        self.name = str(data.get('name', ''))
        self.xpos = float(data.get('xpos', 0.0))
        self.ypos = float(data.get('ypos', 1.0))
        self.phase = int(data.get('phase', 1))

    def copy(self) -> CableInSystem:
        """Copy the relationship while preserving its cable reference.

        :return: Independent relationship object.
        """
        if self.cable is not None:
            copied: CableInSystem = CableInSystem(
                cable=self.cable,
                xpos=self.xpos,
                ypos=self.ypos,
                phase=self.phase,
            )
        else:
            placeholder: UndergroundCableType = UndergroundCableType(name=self.name)
            copied = CableInSystem(
                cable=placeholder,
                xpos=self.xpos,
                ypos=self.ypos,
                phase=self.phase,
            )
            copied.cable = None
        return copied

    def __eq__(self, other: object) -> bool:
        """Compare complete cable relationships.

        :param other: Candidate relationship.
        :return: Whether both relationships contain the same data.
        """
        if isinstance(other, CableInSystem):
            return (
                self.cable == other.cable
                and self.xpos == other.xpos
                and self.ypos == other.ypos
                and self.phase == other.phase
                and self.circuit_index == other.circuit_index
                and self.name == other.name
            )
        else:
            return False


class ListOfCables:
    """Persistent ordered collection of positioned cable relationships."""

    __slots__ = ('data',)

    def __init__(self) -> None:
        """Create an empty cable relationship collection.

        :return: None.
        """
        self.data: List[CableInSystem] = list()

    def append(self, element: CableInSystem) -> None:
        """Append one cable relationship.

        :param element: Relationship to append.
        :return: None.
        """
        self.data.append(element)

    def to_list(self) -> List[Dict[str, str | float | int | None]]:
        """Return a serializable relation list.

        :return: Serialized cable relationships.
        """
        serialized: List[Dict[str, str | float | int | None]] = list()
        element: CableInSystem
        for element in self.data:
            serialized.append(element.to_dict())
        return serialized

    def parse(self,
              data: List[Dict[str, str | float | int | None]],
              cable_dict: Dict[str, UndergroundCableType]) -> None:
        """Load cable relationships from persistent data.

        :param data: Serialized relationship entries.
        :param cable_dict: Physical cables indexed by persistent identifier.
        :return: None.
        """
        entry: Dict[str, str | float | int | None]
        for entry in data:
            cable_idtag: str = str(entry.get('cable', ''))
            cable: UndergroundCableType | None = cable_dict.get(cable_idtag, None)
            if cable is not None:
                element: CableInSystem = CableInSystem(cable=cable)
                element.parse(data=entry, cable_dict=cable_dict)
                self.append(element=element)
            else:
                pass

    def get_circuits(self) -> List[int]:
        """Return sorted circuit indices represented by the collection.

        :return: Circuit indices.
        """
        circuits: set[int] = set()
        element: CableInSystem
        for element in self.data:
            circuits.add(element.circuit_index)
        return sorted(circuits)

    def copy(self) -> ListOfCables:
        """Return an independent relationship collection.

        :return: Copied collection.
        """
        copied: ListOfCables = ListOfCables()
        element: CableInSystem
        for element in self.data:
            copied.append(element=element.copy())
        return copied

    def __eq__(self, other: object) -> bool:
        """Compare ordered cable collections.

        :param other: Candidate collection.
        :return: Whether both collections contain equal relationships.
        """
        if isinstance(other, ListOfCables):
            return self.data == other.data
        else:
            return False


class UndergroundLineType(DynamicDevice):
    __slots__ = (
        'cables_in_system',
        '_Imax',
        '_Vnom',
        '_freq',
        '_earth_resistivity',
        '_R',
        '_X',
        '_B',
        '_C',
        '_R0',
        '_X0',
        '_B0',
        '_C0',
        '_n_circuits',
        '_capex',
        '_opex',
        '_z_primitive',
        '_y_primitive',
        '_z_nabc',
        '_y_nabc',
        '_z_seq',
        '_y_seq',
        '_z_phases_nabc',
        '_y_phases_nabc',
    )

    LOCAL_PROPERTY_DECLARATIONS: Tuple[GCProp, ...] = (
        GCProp(
            prop_name='Imax',
            units='kA',
            tpe=float,
            definition='Current rating of the line',
            old_names=['rating'],
            cat=[PrpCat.PF],
        ),
        GCProp(
            prop_name='Vnom',
            units='kV',
            tpe=float,
            definition='Voltage rating of the line',
            cat=[PrpCat.PF],
        ),
        GCProp(
            prop_name='freq',
            units='Hz',
            tpe=float,
            definition='Cable frequency',
            cat=[PrpCat.PF],
        ),
        GCProp(
            prop_name='earth_resistivity',
            units='Ohm*m',
            tpe=float,
            definition='Earth resistivity',
            cat=[PrpCat.TP],
        ),
        GCProp(
            prop_name='cables_in_system',
            units='',
            tpe=SubObjectType.ListOfCables,
            definition='Physical cables and their positions',
            editable=False,
            display=False,
            cat=[PrpCat.TP],
        ),
        GCProp(
            prop_name='R',
            units='Ohm/km',
            tpe=float,
            definition='Positive-sequence resistance per km',
            cat=[PrpCat.PF],
        ),
        GCProp(
            prop_name='X',
            units='Ohm/km',
            tpe=float,
            definition='Positive-sequence reactance per km',
            cat=[PrpCat.PF],
        ),
        GCProp(
            prop_name='B',
            units='uS/km',
            tpe=float,
            definition='Positive-sequence shunt susceptance per km',
            cat=[PrpCat.PF],
        ),
        GCProp(
            prop_name='C',
            units='uF/km',
            tpe=float,
            definition='Positive-sequence shunt capacitance per km (alternative to B',
            cat=[PrpCat.PF],
        ),
        GCProp(
            prop_name='R0',
            units='Ohm/km',
            tpe=float,
            definition='Zero-sequence resistance per km',
            cat=[PrpCat.SC, PrpCat.PF3],
        ),
        GCProp(
            prop_name='X0',
            units='Ohm/km',
            tpe=float,
            definition='Zero-sequence reactance per km',
            cat=[PrpCat.SC, PrpCat.PF3],
        ),
        GCProp(
            prop_name='B0',
            units='uS/km',
            tpe=float,
            definition='Zero-sequence shunt susceptance per km',
            cat=[PrpCat.SC, PrpCat.PF3],
        ),
        GCProp(
            prop_name='C0',
            units='uF/km',
            tpe=float,
            definition='Zero-sequence shunt capacitance per km (alternative to B0',
            cat=[PrpCat.SC, PrpCat.PF3],
        ),
        GCProp(
            prop_name='n_circuits',
            units='',
            tpe=int,
            definition='number of circuits',
            cat=[PrpCat.TP],
        ),
        GCProp(
            prop_name='capex',
            units='currency/km',
            tpe=float,
            definition='Capital expenditure per km',
            cat=[PrpCat.INV],
        ),
        GCProp(
            prop_name='opex',
            units='currency/MWh',
            tpe=float,
            definition='Operational expenditure',
            cat=[PrpCat.INV],
        ),
    )

    def __init__(self, name: str = 'UndergroundLine', idtag: None | str = None, Imax: float = 1.0,
                 Vnom: float = 1.0, R: float = 0.0, X: float = 0.0, B: float = 0.0, C: float = 0.0,
                 R0: float = 0.0, X0: float = 0.0, B0: float = 0.0, C0: float = 0.0,
                 freq: float = 50.0,
                 earth_resistivity: float = 100.0,
                 capex: float = 0.0, opex: float = 0.0) -> None:
        """
        Constructor
        :param name: name of the device
        :param Imax: rating in kA
        :param R: Resistance of positive sequence in Ohm/km
        :param X: Reactance of positive sequence in Ohm/km
        :param B: Susceptance of positive sequence in uS/km
        :param C: Capacitance of positive sequence in uF/km (alternative to B)
        :param R0: Resistance of zero sequence in Ohm/km
        :param X0: Reactance of zero sequence in Ohm/km
        :param B0: Susceptance of zero sequence in uS/km
        :param C0: Capacitance of zero sequence in uF/km (alternative to B0)
        :param freq: Frequency of underground line (Hz)
        :param earth_resistivity: Earth resistivity in ohm metres
        :param capex: Capital expenditures
        :param opex: Operating expenditures
        """
        DynamicDevice.__init__(self,
                                name=name,
                                idtag=idtag,
                                code='',
                                device_type=DeviceType.UnderGroundLineDevice)

        self.Imax = float(Imax)
        self.Vnom = float(Vnom)
        self._freq = float(freq)
        self.earth_resistivity = earth_resistivity

        # The physical composition is optional so existing sequence-only cable
        # catalogues retain their exact behaviour.
        self.cables_in_system: ListOfCables = ListOfCables()

        # impudence and admittance per unit of length
        self.R = float(R)
        self.X = float(X)
        self.B = float(B)
        self._C = float(C)

        self.R0 = float(R0)
        self.X0 = float(X0)
        self.B0 = float(B0)
        self._C0 = float(C0)

        self.n_circuits = 1

        self.capex = float(capex)
        self.opex = float(opex)

        # Physical matrices are derived from the composition and therefore are
        # recomputed after loading instead of being persisted independently.
        self._z_primitive: CxMat | None = None
        self._y_primitive: CxMat | None = None
        self._z_nabc: CxMat | None = None
        self._y_nabc: CxMat | None = None
        self._z_seq: CxMat | None = None
        self._y_seq: CxMat | None = None
        self._z_phases_nabc: np.ndarray | None = None
        self._y_phases_nabc: np.ndarray | None = None

    def has_physical_data(self) -> bool:
        """Return whether the template contains positioned physical cables.

        :return: True for a geometry-backed cable system.
        """
        return len(self.cables_in_system.data) > 0

    def is_computed(self) -> bool:
        """Return whether all physical cable matrices are available.

        :return: Matrix calculation state.
        """
        return (
            self._z_primitive is not None
            and self._y_primitive is not None
            and self._z_nabc is not None
            and self._y_nabc is not None
        )

    def get_dc_parameters(self, conductor: int = 1) -> tuple[float, float, float]:
        """Return Rdc [ohm/km], L [H/km] and C [F/km] for one DC conductor.

        For a physical system, ``conductor`` is its global phase number. The
        existing sheath-reduced matrices supply the diagonal L/C at ``freq``;
        Rdc comes from the physical core, without AC skin/earth-return losses.
        A scalar DcLine does not represent mutual coupling between conductors.
        Parameter-only systems use R, X and C (or B), including imported DGS
        equivalents whose construction is unknown.
        """
        if not np.isfinite(self.freq) or self.freq <= 0.0:
            raise ValueError('Cable System reference frequency must be positive')
        omega = 2.0 * np.pi * self.freq
        if self.has_physical_data():
            if not np.isfinite(self.earth_resistivity) or self.earth_resistivity <= 0.0:
                raise ValueError('Cable System earth resistivity must be positive')
            # Recompute so edits to a referenced Cable cannot leave stale L/C.
            logger = Logger()
            if not self.compute(logger=logger):
                raise ValueError('Cable System geometry or materials are invalid')
            indices = np.flatnonzero(self.z_phases_nabc == conductor)
            if len(indices) != 1:
                raise ValueError('Select an existing Cable System conductor number')
            idx = int(indices[0])
            cable = next(item.cable for item in self.cables_in_system.data
                         if item.phase == conductor)
            values = (float(cable.core_dc_resistance),
                      float(self.z_nabc[idx, idx].imag / omega),
                      float(self.y_nabc[idx, idx].imag / omega))
        else:
            if conductor != 1:
                raise ValueError('A parameter-only Cable System has one DC equivalent')
            values = (self.R, self.X / omega,
                      (self.C if self.C != 0.0 else self.B / omega) * 1.0e-6)
        if not all(np.isfinite(value) and value >= 0.0 for value in values):
            raise ValueError('Cable System DC parameters must be finite and non-negative')
        return values

    def get_dc_values(self, Sbase: float, length: float, line_Vnom: float,
                      conductor: int = 1) -> tuple[float, float, float]:
        """Return total DC R in p.u. and L/C in p.u. seconds.

        Keep the historical DC conversion: Zbase = Vnom**2/Sbase,
        Rpu = R*length/Zbase, Lpu = L*length/Zbase, Cpu = C*length*Zbase.
        """
        if not all(np.isfinite(value) and value > 0.0
                   for value in (Sbase, length, line_Vnom)):
            raise ValueError('DC bases and cable length must be positive and finite')
        resistance, inductance, capacitance = self.get_dc_parameters(conductor)
        zbase = line_Vnom * line_Vnom / Sbase
        return resistance * length / zbase, inductance * length / zbase, capacitance * length * zbase

    def get_branch_dynamic_templates(self, device_type: DeviceType, logger: Logger) -> tuple:
        """Share electrical data without assigning AC dynamic models to DC or vice versa."""
        templates = []
        for model in (self.rms_template, self.emt_template):
            if model is None or model.tpe in (device_type, DeviceType.NoDevice):
                templates.append(model)
            else:
                logger.add_warning('Cable System dynamic template does not match the branch type; not applied',
                                   device=self.name, value=model.name, expected_value=str(device_type))
                templates.append(None)
        return tuple(templates)

    def get_values(self,
                   Sbase: float,
                   length: float,
                   circuit_index: int = 1,
                   round_vals: bool = True,
                   Vnom: float | None = None) -> tuple[float, float, float, float, float, float, float]:
        """Return the line sequence values in per unit.

        :param Sbase: Base power in megavolt amperes.
        :param length: Line length in kilometres.
        :param circuit_index: One-based circuit index.
        :param round_vals: Round the per-unit values to the legacy six decimals.
        :param Vnom: Optional connected-line voltage overriding the template voltage.
        :return: Positive and zero sequence R/X/B plus rating.
        """
        if self.has_physical_data() and not self.is_computed():
            self.compute()
        else:
            pass

        nominal_voltage_kv: float = self.Vnom if Vnom is None else float(Vnom)
        positive_resistance: float = self.R
        positive_reactance: float = self.X
        positive_susceptance_us_km: float = self.B
        zero_resistance: float = self.R0
        zero_reactance: float = self.X0
        zero_susceptance_us_km: float = self.B0

        # Geometry-backed multi-circuit systems retain each circuit's diagonal
        # sequence block while legacy templates continue using their scalars.
        if self._z_seq is not None and self._y_seq is not None:
            zero_index: int = 3 * (circuit_index - 1)
            positive_index: int = zero_index + 1
            if positive_index < self._z_seq.shape[0]:
                positive_resistance = float(self._z_seq[positive_index, positive_index].real)
                positive_reactance = float(self._z_seq[positive_index, positive_index].imag)
                positive_susceptance_us_km = float(
                    self._y_seq[positive_index, positive_index].imag * 1.0e6
                )
                zero_resistance = float(self._z_seq[zero_index, zero_index].real)
                zero_reactance = float(self._z_seq[zero_index, zero_index].imag)
                zero_susceptance_us_km = float(self._y_seq[zero_index, zero_index].imag * 1.0e6)
            else:
                pass
        else:
            pass

        impedance_base_ohm: float = nominal_voltage_kv * nominal_voltage_kv / Sbase
        admittance_base_s: float = 1.0 / impedance_base_ohm
        positive_resistance_pu: float = positive_resistance * length / impedance_base_ohm
        positive_reactance_pu: float = positive_reactance * length / impedance_base_ohm
        positive_susceptance_pu: float = (
            positive_susceptance_us_km * 1.0e-6 * length / admittance_base_s
        )
        zero_resistance_pu: float = zero_resistance * length / impedance_base_ohm
        zero_reactance_pu: float = zero_reactance * length / impedance_base_ohm
        zero_susceptance_pu: float = zero_susceptance_us_km * 1.0e-6 * length / admittance_base_s

        if round_vals:
            positive_resistance_pu = float(np.round(positive_resistance_pu, 6))
            positive_reactance_pu = float(np.round(positive_reactance_pu, 6))
            positive_susceptance_pu = float(np.round(positive_susceptance_pu, 6))
            zero_resistance_pu = float(np.round(zero_resistance_pu, 6))
            zero_reactance_pu = float(np.round(zero_reactance_pu, 6))
            zero_susceptance_pu = float(np.round(zero_susceptance_pu, 6))
        else:
            pass

        rate_mva: float = self.Imax * nominal_voltage_kv * np.sqrt(3.0)
        return (
            positive_resistance_pu,
            positive_reactance_pu,
            positive_susceptance_pu,
            zero_resistance_pu,
            zero_reactance_pu,
            zero_susceptance_pu,
            rate_mva,
        )

    def z_series(self) -> complex:
        """Return positive-sequence series impedance in ohms per kilometre."""
        return complex(self.R, self.X)

    def y_shunt(self) -> complex:
        """Return positive-sequence shunt admittance in siemens per kilometre."""
        return complex(0.0, self.B * 1.0e-6)

    @property
    def z_primitive(self) -> CxMat | None:
        """Return the core-sheath primitive series matrix in ohms per kilometre."""
        return self._z_primitive

    @property
    def y_primitive(self) -> CxMat | None:
        """Return the core-sheath primitive shunt matrix in siemens per kilometre."""
        return self._y_primitive

    @property
    def z_seq(self) -> CxMat | None:
        """Return the calculated symmetrical-component series matrix."""
        return self._z_seq

    @property
    def y_seq(self) -> CxMat | None:
        """Return the calculated symmetrical-component shunt matrix."""
        return self._y_seq

    @property
    def z_nabc(self) -> CxMat:
        """Return the physical phase series-impedance matrix in ohms per kilometre."""
        if self._z_nabc is not None:
            return self._z_nabc
        else:
            return sequence_to_phase_matrix(
                positive_sequence_value=self.R + 1j * self.X,
                zero_sequence_value=self.R0 + 1j * self.X0,
            )

    @property
    def y_nabc(self) -> CxMat:
        """Return the physical phase shunt-admittance matrix in siemens per kilometre."""
        if self._y_nabc is not None:
            return self._y_nabc
        else:
            if abs(self.C) > 0.0 or abs(self.C0) > 0.0:
                positive_susceptance: float = 2.0 * np.pi * self.freq * self.C * 1.0e-6
                zero_susceptance: float = 2.0 * np.pi * self.freq * self.C0 * 1.0e-6
            else:
                positive_susceptance = self.B * 1.0e-6
                zero_susceptance = self.B0 * 1.0e-6
            return sequence_to_phase_matrix(
                positive_sequence_value=1j * positive_susceptance,
                zero_sequence_value=1j * zero_susceptance,
            )

    @property
    def z_phases_nabc(self) -> np.ndarray:
        """Return phase indices corresponding to ``z_nabc``."""
        if self._z_phases_nabc is not None:
            return self._z_phases_nabc
        else:
            return np.array([1, 2, 3], dtype=int)

    @property
    def y_phases_nabc(self) -> np.ndarray:
        """Return phase indices corresponding to ``y_nabc``."""
        if self._y_phases_nabc is not None:
            return self._y_phases_nabc
        else:
            return np.array([1, 2, 3], dtype=int)

    def add_cable_relationship(self,
                               cable: UndergroundCableType,
                               xpos: float = 0.0,
                               ypos: float = 1.0,
                               phase: int = 1) -> None:
        """Add a physical cable to this cable system.

        :param cable: Physical cable catalogue entry.
        :param xpos: Horizontal coordinate in metres.
        :param ypos: Positive burial depth in metres.
        :param phase: Global phase number, starting at one.
        :return: None.
        """
        relationship: CableInSystem = CableInSystem(
            cable=cable,
            xpos=xpos,
            ypos=ypos,
            phase=phase,
        )
        self.cables_in_system.append(element=relationship)
        self.n_circuits = max(self.n_circuits, relationship.circuit_index)

    def check(self, logger: Logger | None = None) -> bool:
        """Validate the supported single-core cable system geometry.

        :param logger: Optional validation logger.
        :return: True when the system can be calculated.
        """
        validation_logger: Logger = Logger() if logger is None else logger
        cable_count: int = len(self.cables_in_system.data)
        valid: bool = True
        if cable_count > 0:
            pass
        else:
            validation_logger.add_error('A physical cable system requires at least one cable',
                                        device=self.name)
            valid = False

        expected_phases: List[int] = list(range(1, cable_count + 1))
        actual_phases: List[int] = sorted(element.phase for element in self.cables_in_system.data)
        if actual_phases == expected_phases:
            pass
        else:
            validation_logger.add_error('Cable phases must be unique and consecutive', device=self.name)
            valid = False

        positions: set[tuple[float, float]] = set()
        relationship: CableInSystem
        for relationship in self.cables_in_system.data:
            cable: UndergroundCableType | None = relationship.cable
            if cable is not None:
                if (
                    cable.core_diameter > 0.0
                    and cable.cable_diameter > cable.core_diameter
                    and cable.sheath_thickness > 0.0
                    and relationship.ypos > 0.0
                ):
                    pass
                else:
                    validation_logger.add_error('Invalid cable dimensions, depth or filling factor',
                                                device=relationship.name)
                    valid = False
                try:
                    cable.validate_resistance_inputs()
                except ValueError as error:
                    validation_logger.add_error(str(error), device=cable.name)
                    valid = False
            else:
                validation_logger.add_error('Cable relationship has no catalogue type', device=relationship.name)
                valid = False

            position: tuple[float, float] = (relationship.xpos, relationship.ypos)
            if position in positions:
                validation_logger.add_error('Two cables cannot occupy the same position', device=self.name)
                valid = False
            else:
                positions.add(position)
        return valid

    def compute(self, logger: Logger | None = None) -> bool:
        """Calculate primitive, phase and sequence matrices from physical data.

        :param logger: Optional calculation logger.
        :return: True when all matrices were calculated.
        """
        calculation_logger: Logger = Logger() if logger is None else logger

        # Inputs are mutable through both the API and GUI. Clearing every
        # derived value first guarantees that a failed recalculation cannot
        # expose matrices from an older, different composition.
        self._z_primitive = None
        self._y_primitive = None
        self._z_nabc = None
        self._y_nabc = None
        self._z_seq = None
        self._y_seq = None
        self._z_phases_nabc = None
        self._y_phases_nabc = None
        if self.check(logger=calculation_logger):
            cable_count: int = len(self.cables_in_system.data)
            relationships: List[CableInSystem | None] = list((None,) * cable_count)
            unsorted_relationship: CableInSystem
            for unsorted_relationship in self.cables_in_system.data:
                relationships[unsorted_relationship.phase - 1] = unsorted_relationship
            dia_con: np.ndarray = np.empty(cable_count, dtype=float)
            dia_tube: np.ndarray = np.empty(cable_count, dtype=float)
            dia_cab: np.ndarray = np.empty(cable_count, dtype=float)
            th_sht: np.ndarray = np.empty(cable_count, dtype=float)
            th_ins: np.ndarray = np.empty(cable_count, dtype=float)
            resistivity: np.ndarray = np.empty((cable_count, 2), dtype=float)
            filling_factor: np.ndarray = np.empty((cable_count, 2), dtype=float)
            relative_permittivity: np.ndarray = np.empty((cable_count, 2), dtype=float)
            loss_factor: np.ndarray = np.empty((cable_count, 2), dtype=float)
            relative_permeability: np.ndarray = np.empty((cable_count, 2), dtype=float)
            skin_effect_factor: np.ndarray = np.empty(cable_count, dtype=float)
            coordinates_m: np.ndarray = np.empty((cable_count, 2), dtype=float)
            phases: np.ndarray = np.empty(cable_count, dtype=int)

            cable_index: int
            for cable_index in range(cable_count):
                relationship: CableInSystem | None = relationships[cable_index]
                cable: UndergroundCableType | None = relationship.cable if relationship is not None else None
                if cable is not None and relationship is not None:
                    dia_con[cable_index] = cable.core_diameter
                    dia_tube[cable_index] = cable.core_internal_diameter
                    dia_cab[cable_index] = cable.cable_diameter
                    th_sht[cable_index] = cable.sheath_thickness
                    # Numerical routines receive only the core and sheath (or their two insulations).
                    th_ins[cable_index] = cable.main_insulation_thickness
                    core_resistivity, core_filling_factor = cable.get_core_material_properties()
                    sheath_resistivity, sheath_filling_factor = cable.get_sheath_material_properties()
                    resistivity[cable_index, :] = (core_resistivity, sheath_resistivity)
                    filling_factor[cable_index, :] = (core_filling_factor, sheath_filling_factor)
                    relative_permittivity[cable_index, :] = (cable.main_insulation_permittivity, cable.outer_insulation_permittivity)
                    loss_factor[cable_index, :] = (cable.main_insulation_loss_tangent, cable.outer_insulation_loss_tangent)
                    relative_permeability[cable_index, :] = (cable.core_relative_permeability, cable.sheath_relative_permeability)
                    skin_effect_factor[cable_index] = cable.skin_effect_factor
                    coordinates_m[cable_index, 0] = relationship.xpos
                    coordinates_m[cable_index, 1] = relationship.ypos
                    phases[cable_index] = relationship.phase
                else:
                    pass

            # Keep the reusable circuit count synchronized after GUI edits.
            self.n_circuits = n_circuits(idx=phases)

            earth_conductivity_us_cm: float = 10000.0 / self.earth_resistivity
            try:
                (
                    self._z_primitive,
                    self._y_primitive,
                    self._z_nabc,
                    self._y_nabc,
                    self._z_seq,
                    self._y_seq,
                ) = calculate_underground_cable_matrices(
                    dia_con=dia_con,
                    dia_tube=dia_tube,
                    dia_cab=dia_cab,
                    th_sht=th_sht,
                    th_ins=th_ins,
                    resistivity_uohm_cm=resistivity,
                    filling_factor_percent=filling_factor,
                    relative_permittivity=relative_permittivity,
                    loss_factor=loss_factor,
                    relative_permeability=relative_permeability,
                    skin_effect_factor=skin_effect_factor,
                    coordinates_m=coordinates_m,
                    frequency_hz=self.freq,
                    earth_conductivity_us_cm=earth_conductivity_us_cm,
                )
                self._z_phases_nabc = phases
                self._y_phases_nabc = phases.copy()
            except np.linalg.LinAlgError:
                calculation_logger.add_error('Cable matrix reduction is singular', device=self.name)
                return False

            if self._z_seq is not None and self._y_seq is not None:
                self.R0 = float(self._z_seq[0, 0].real)
                self.X0 = float(self._z_seq[0, 0].imag)
                self.B0 = float(self._y_seq[0, 0].imag * 1.0e6)
                self.R = float(self._z_seq[1, 1].real)
                self.X = float(self._z_seq[1, 1].imag)
                self.B = float(self._y_seq[1, 1].imag * 1.0e6)
                angular_frequency_rad_s: float = 2.0 * np.pi * self.freq
                self._C = self.B / angular_frequency_rad_s
                self._C0 = self.B0 / angular_frequency_rad_s
            else:
                # Single- and two-phase PowerFactory systems have valid phase
                # matrices but no symmetrical-component representation.
                calculation_logger.add_info('Cable system has no complete sequence representation',
                                            device=self.name)
            return True
        else:
            return False

    def get_ys(self,
               circuit_idx: int,
               Sbase: float,
               length: float,
               Vnom: float) -> AdmittanceMatrix:
        """Return the total series branch admittance matrix in per unit.

        :param circuit_idx: One-based circuit index.
        :param Sbase: Base power in megavolt amperes.
        :param length: Line length in kilometres.
        :param Vnom: Line nominal voltage in kilovolts.
        :return: Four-by-four branch admittance matrix.
        """
        impedance_base_ohm: float = Vnom * Vnom / Sbase
        impedance_pu: CxMat = self.z_nabc * length / impedance_base_ohm
        try:
            phase_admittance_pu: CxMat = np.linalg.inv(impedance_pu)
        except np.linalg.LinAlgError:
            phase_admittance_pu = np.linalg.pinv(impedance_pu, rcond=1.0e-12)

        circuit_count: int = n_circuits(idx=self.z_phases_nabc)
        complete_size: int = 4 * circuit_count - (circuit_count - 1)
        complete_admittance: CxMat = np.zeros((complete_size, complete_size), dtype=complex)
        complete_admittance[np.ix_(self.z_phases_nabc, self.z_phases_nabc)] = phase_admittance_pu
        admittance: AdmittanceMatrix = AdmittanceMatrix(size=4)
        admittance.values = build_y_4x4(y_nxn=complete_admittance, circuit_idx=circuit_idx)
        admittance.phN = False
        admittance.phA = True
        admittance.phB = True
        admittance.phC = True
        return admittance

    def get_ysh(self,
                circuit_idx: int,
                Sbase: float,
                length: float,
                Vnom: float) -> AdmittanceMatrix:
        """Return the total shunt branch admittance matrix in micro per unit.

        :param circuit_idx: One-based circuit index.
        :param Sbase: Base power in megavolt amperes.
        :param length: Line length in kilometres.
        :param Vnom: Line nominal voltage in kilovolts.
        :return: Four-by-four shunt admittance matrix.
        """
        impedance_base_ohm: float = Vnom * Vnom / Sbase
        admittance_base_s: float = 1.0 / impedance_base_ohm
        phase_admittance_micro_pu: CxMat = self.y_nabc * length * 1.0e6 / admittance_base_s
        circuit_count: int = n_circuits(idx=self.y_phases_nabc)
        complete_size: int = 4 * circuit_count - (circuit_count - 1)
        complete_admittance: CxMat = np.zeros((complete_size, complete_size), dtype=complex)
        complete_admittance[np.ix_(self.y_phases_nabc, self.y_phases_nabc)] = phase_admittance_micro_pu
        admittance: AdmittanceMatrix = AdmittanceMatrix(size=4)
        admittance.values = build_y_4x4(y_nxn=complete_admittance, circuit_idx=circuit_idx)
        admittance.phN = False
        admittance.phA = True
        admittance.phB = True
        admittance.phC = True
        return admittance


    @property
    def C(self) -> float:
        return self._C

    @C.setter
    def C(self, C: float):
        self._C = float(C)

        if self.auto_update_enabled:
            self.B = 2 * np.pi * self._freq * self._C

    @property
    def C0(self) -> float:
        return self._C0

    @C0.setter
    def C0(self, C0: float):
        self._C0 = float(C0)

        if self.auto_update_enabled:
            self.B0 = 2 * np.pi * self._freq * self._C0

    @property
    def freq(self) -> float:
        return self._freq

    @freq.setter
    def freq(self, freq: float):
        self._freq = float(freq)

        if self.auto_update_enabled:
            self.B = 2 * np.pi * self._freq * self._C
            self.B0 = 2 * np.pi * self._freq * self._C0

    # Scalar property accessors coerce assignments to the declared schema types.

    @property
    def Imax(self) -> float:
        """
        Get ``Imax``.

        :return: float
        """
        return self._Imax

    @Imax.setter
    def Imax(self, val: float) -> None:
        """
        Set ``Imax``.

        :param val: Value to assign.
        :return: None
        """
        self._Imax = float(val)

    @property
    def Vnom(self) -> float:
        """
        Get ``Vnom``.

        :return: float
        """
        return self._Vnom

    @Vnom.setter
    def Vnom(self, val: float) -> None:
        """
        Set ``Vnom``.

        :param val: Value to assign.
        :return: None
        """
        self._Vnom = float(val)

    @property
    def R(self) -> float:
        """
        Get ``R``.

        :return: float
        """
        return self._R

    @R.setter
    def R(self, val: float) -> None:
        """
        Set ``R``.

        :param val: Value to assign.
        :return: None
        """
        self._R = float(val)

    @property
    def X(self) -> float:
        """
        Get ``X``.

        :return: float
        """
        return self._X

    @X.setter
    def X(self, val: float) -> None:
        """
        Set ``X``.

        :param val: Value to assign.
        :return: None
        """
        self._X = float(val)

    @property
    def B(self) -> float:
        """
        Get ``B``.

        :return: float
        """
        return self._B

    @B.setter
    def B(self, val: float) -> None:
        """
        Set ``B``.

        :param val: Value to assign.
        :return: None
        """
        self._B = float(val)

    @property
    def R0(self) -> float:
        """
        Get ``R0``.

        :return: float
        """
        return self._R0

    @R0.setter
    def R0(self, val: float) -> None:
        """
        Set ``R0``.

        :param val: Value to assign.
        :return: None
        """
        self._R0 = float(val)

    @property
    def X0(self) -> float:
        """
        Get ``X0``.

        :return: float
        """
        return self._X0

    @X0.setter
    def X0(self, val: float) -> None:
        """
        Set ``X0``.

        :param val: Value to assign.
        :return: None
        """
        self._X0 = float(val)

    @property
    def B0(self) -> float:
        """
        Get ``B0``.

        :return: float
        """
        return self._B0

    @B0.setter
    def B0(self, val: float) -> None:
        """
        Set ``B0``.

        :param val: Value to assign.
        :return: None
        """
        self._B0 = float(val)

    @property
    def n_circuits(self) -> int:
        """
        Get ``n_circuits``.

        :return: int
        """
        return self._n_circuits

    @n_circuits.setter
    def n_circuits(self, val: int) -> None:
        """
        Set ``n_circuits``.

        :param val: Value to assign.
        :return: None
        """
        self._n_circuits = int(val)

    @property
    def earth_resistivity(self) -> float:
        """Return earth resistivity in ohm metres."""
        return self._earth_resistivity

    @earth_resistivity.setter
    def earth_resistivity(self, value: float) -> None:
        """Set earth resistivity.

        :param value: Resistivity in ohm metres.
        :return: None.
        """
        self._earth_resistivity = float(value)

    @property
    def capex(self) -> float:
        """
        Get ``capex``.

        :return: float
        """
        return self._capex

    @capex.setter
    def capex(self, val: float) -> None:
        """
        Set ``capex``.

        :param val: Value to assign.
        :return: None
        """
        self._capex = float(val)

    @property
    def opex(self) -> float:
        """
        Get ``opex``.

        :return: float
        """
        return self._opex

    @opex.setter
    def opex(self, val: float) -> None:
        """
        Set ``opex``.

        :param val: Value to assign.
        :return: None
        """
        self._opex = float(val)
