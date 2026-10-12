# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.  
# SPDX-License-Identifier: MPL-2.0
from typing import Tuple
import numpy as np
from VeraGridEngine.Devices.admittance_matrix import AdmittanceMatrix
from VeraGridEngine.Devices.Parents.editable_device import DeviceType, GCProp
from VeraGridEngine.Devices.Parents.dynamic_parent import DynamicDevice
from VeraGridEngine.basic_structures import Logger
from VeraGridEngine.enumerations import PrpCat


def sequence_to_phase_matrix(positive_sequence_value: complex,
                             zero_sequence_value: complex) -> np.ndarray:
    """Build a symmetric ABC matrix assuming negative sequence equals positive sequence."""
    diagonal_value = (2.0 * positive_sequence_value + zero_sequence_value) / 3.0
    off_diagonal_value = (zero_sequence_value - positive_sequence_value) / 3.0
    matrix_abc = np.full((3, 3), off_diagonal_value, dtype=np.complex128)
    np.fill_diagonal(matrix_abc, diagonal_value)
    return matrix_abc


def get_line_impedances_with_c(r_ohm: float,
                               x_ohm: float,
                               c_nf: float,
                               length: float,
                               Imax: float,
                               freq: float,
                               Sbase: float,
                               Vnom: float,
                               logger: Logger = Logger(),
                               decimals_rounding: int = 6) -> Tuple[float, float, float, float]:
    """
    Fill R, X, B from not-in-per-unit parameters
    :param r_ohm: Resistance per km in OHM/km
    :param x_ohm: Reactance per km in OHM/km
    :param c_nf: Capacitance per km in nF/km
    :param length: length in kn
    :param Imax: Maximum current in kA
    :param freq: System frequency in Hz
    :param Sbase: Base power in MVA (take always 100 MVA)
    :param Vnom: nominal voltage (kV)
    :param logger: logger
    :param decimals_rounding: Number of decimals to round to
    :return R, X, B, rate
    """
    r_ohm_total = r_ohm * length
    x_ohm_total = x_ohm * length
    b_siemens_total = (2 * np.pi * freq * c_nf * 1e-9) * length

    if Vnom > 0.0:
        Zbase = (Vnom * Vnom) / Sbase
        Ybase = 1.0 / Zbase

        R: float = np.round(r_ohm_total / Zbase, decimals_rounding)
        X: float = np.round(x_ohm_total / Zbase, decimals_rounding)
        B: float = np.round(b_siemens_total / Ybase, decimals_rounding)
        rate: float = np.round(Imax * Vnom * 1.73205080757,
                               decimals_rounding)  # nominal power in MVA = kA * kV * sqrt(3)

        return R, X, B, rate
    else:
        logger.add_error("Nominal voltage is zero", device_class="SequenceLineType")
        return 1e-20, 1e-20, 0, 1e-20


def get_line_impedances_with_b(r_ohm: float, x_ohm: float, b_us: float, length: float,
                               Imax: float, Sbase: float, Vnom: float,
                               logger: Logger = Logger(),
                               decimals_rounding: int = 6) -> Tuple[float, float, float, float]:
    """
    Fill R, X, B from not-in-per-unit parameters
    :param r_ohm: Resistance per km in OHM/km
    :param x_ohm: Reactance per km in OHM/km
    :param b_us: Susceptance per km in uS/km
    :param length: length in kn
    :param Imax: Maximum current in kA
    :param Sbase: Base power in MVA (take always 100 MVA)
    :param Vnom: nominal voltage (kV)
    :param logger: Logger (optional)
    :param decimals_rounding: number of decimals to round
    :return R, X, B, rate
    """
    r_ohm_total = r_ohm * length
    x_ohm_total = x_ohm * length
    b_siemens_total = (b_us * 1e-6) * length

    if Vnom > 0:
        Zbase = (Vnom * Vnom) / Sbase
        Ybase = 1.0 / Zbase

        R: float = np.round(r_ohm_total / Zbase, decimals_rounding)
        X: float = np.round(x_ohm_total / Zbase, decimals_rounding)
        B: float = np.round(b_siemens_total / Ybase, decimals_rounding)
        rate: float = np.round(Imax * Vnom * 1.73205080757,
                               decimals_rounding)  # nominal power in MVA = kA * kV * sqrt(3)

        return R, X, B, rate
    else:
        logger.add_error("Nominal voltage is zero", device_class="SequenceLineType")

        return 1e-20, 1e-20, 0, 1e-20


class SequenceLineType(DynamicDevice):
    __slots__ = (
        '_Imax',
        '_Vnom',
        '_R',
        '_X',
        '_B',
        '_G',
        '_Cnf',
        '_R0',
        '_X0',
        '_B0',
        '_G0',
        '_Cnf0',
        '_use_conductance',
        '_n_circuits',
        '_capex',
        '_opex',
    )

    LOCAL_PROPERTY_DECLARATIONS: Tuple[GCProp, ...] = (
        GCProp(
            prop_name='Imax',
            units='kA',
            tpe=float,
            definition='Current rating of the line',
            old_names=['rating'],
            cat=[PrpCat.TP],
        ),
        GCProp(
            prop_name='Vnom',
            units='kV',
            tpe=float,
            definition='Voltage rating of the line',
            cat=[PrpCat.TP],
        ),
        GCProp(
            prop_name='R',
            units='Ohm/km',
            tpe=float,
            definition='Positive-sequence resistance per km',
            cat=[PrpCat.TP],
        ),
        GCProp(
            prop_name='X',
            units='Ohm/km',
            tpe=float,
            definition='Positive-sequence reactance per km',
            cat=[PrpCat.TP],
        ),
        GCProp(
            prop_name='B',
            units='uS/km',
            tpe=float,
            definition='Positive-sequence shunt susceptance per km',
            cat=[PrpCat.TP],
        ),
        GCProp(
            prop_name='G',
            units='uS/km',
            tpe=float,
            definition='Positive-sequence shunt conductance per km',
            cat=[PrpCat.TP],
        ),
        GCProp(
            prop_name='R0',
            units='Ohm/km',
            tpe=float,
            definition='Zero-sequence resistance per km',
            cat=[PrpCat.TP],
        ),
        GCProp(
            prop_name='X0',
            units='Ohm/km',
            tpe=float,
            definition='Zero-sequence reactance per km',
            cat=[PrpCat.TP],
        ),
        GCProp(
            prop_name='B0',
            units='uS/km',
            tpe=float,
            definition='Zero-sequence shunt susceptance per km',
            cat=[PrpCat.TP],
        ),
        GCProp(
            prop_name='G0',
            units='uS/km',
            tpe=float,
            definition='Zero-sequence shunt conductance per km',
            cat=[PrpCat.TP],
        ),
        GCProp(
            prop_name='Cnf',
            units='nF/km',
            tpe=float,
            definition='Positive-sequence shunt conductance per km',
            cat=[PrpCat.TP],
        ),
        GCProp(
            prop_name='Cnf0',
            units='nF/km',
            tpe=float,
            definition='Zero-sequence shunt conductance per km',
            cat=[PrpCat.TP],
        ),
        GCProp(
            prop_name='use_conductance',
            units='',
            tpe=bool,
            definition='Use conductance? else the susceptance is used',
            cat=[PrpCat.TP],
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

    def __init__(self, name='SequenceLine',
                 idtag: str | None = None,
                 Imax: float = 1, Vnom: float = 1,
                 R=1e-20, X=1e-20, B=1e-20, G: float = 0.0,
                 R0=1e-20, X0=1e-20, B0=1e-20, G0: float = 0.0,
                 CnF=1e-20, CnF0=1e-20,
                 use_conductance: bool = False,
                 capex: float = 0.0, opex: float = 0.0,
                 n_circuits: int = 1):
        """
        Constructor
        :param name: name of the model
        :param Imax: Line rating current in kA
        :param R: Resistance of positive sequence in Ohm/km
        :param X: Reactance of positive sequence in Ohm/km
        :param B: Susceptance of positive sequence in uS/km
        :param G: Conductance of positive sequence in uS/km
        :param R0: Resistance of zero sequence in Ohm/km
        :param X0: Reactance of zero sequence in Ohm/km
        :param B0: Susceptance of zero sequence in uS/km
        :param G0: Conductance of zero sequence in uS/km
        :param CnF: Conductivity of positive sequence in uS/km
        :param CnF0: Conductivity of zero sequence in uS/km
        :param capex: Capital expenditures
        :param opex: Operating expenditures
        :param n_circuits: Number of circuits
        """

        DynamicDevice.__init__(self,
                                name=name,
                                idtag=idtag,
                                code="",
                                device_type=DeviceType.SequenceLineDevice)

        self.Imax = Imax
        self.Vnom = Vnom

        # impudence and admittance per unit of length
        self.R = R
        self.X = X
        self.B = B
        self.G = G
        self.Cnf = CnF

        self.R0 = R0
        self.X0 = X0
        self.B0 = B0
        self.G0 = G0
        self.Cnf0 = CnF0

        self.use_conductance = use_conductance

        self.n_circuits = n_circuits

        self.capex = float(capex)
        self.opex = float(opex)

    def get_values(
            self: "SequenceLineType",
            Sbase: float,
            freq: float,
            length: float,
            line_Vnom: float,
            logger: Logger = Logger(),
            decimals_rounding: int = 6,
    ) -> Tuple[float, float, float, float, float, float, float, float, float]:
        """
        Get the total per-unit sequence line values.

        :param Sbase: Base power (MVA).
        :param freq: Frequency (Hz).
        :param length: Line length (km).
        :param line_Vnom: Line-to-line nominal voltage (kV).
        :param logger: Logger instance.
        :param decimals_rounding: Number of decimal digits to retain.
        :return: R, X, B, G, R0, X0, B0, G0 (p.u.) and rate (MVA).
        """
        r_pu: float
        x_pu: float
        b_pu: float
        r0_pu: float
        x0_pu: float
        b0_pu: float
        rate_mva: float
        _zero_rate_mva: float

        # Preserve the established series and charging conversion for each input mode.
        if self.use_conductance:
            r_pu, x_pu, b_pu, rate_mva = get_line_impedances_with_c(
                r_ohm=self.R, x_ohm=self.X, c_nf=self.Cnf, length=length,
                Imax=self.Imax, freq=freq, Sbase=Sbase, Vnom=line_Vnom,
                logger=logger, decimals_rounding=decimals_rounding,
            )
            r0_pu, x0_pu, b0_pu, _zero_rate_mva = get_line_impedances_with_c(
                r_ohm=self.R0, x_ohm=self.X0, c_nf=self.Cnf0, length=length,
                Imax=self.Imax, freq=freq, Sbase=Sbase, Vnom=line_Vnom,
                logger=logger, decimals_rounding=decimals_rounding,
            )
        else:
            r_pu, x_pu, b_pu, rate_mva = get_line_impedances_with_b(
                r_ohm=self.R, x_ohm=self.X, b_us=self.B, length=length,
                Imax=self.Imax, Sbase=Sbase, Vnom=line_Vnom,
                decimals_rounding=decimals_rounding,
            )
            r0_pu, x0_pu, b0_pu, _zero_rate_mva = get_line_impedances_with_b(
                r_ohm=self.R0, x_ohm=self.X0, b_us=self.B0, length=length,
                Imax=self.Imax, Sbase=Sbase, Vnom=line_Vnom,
                decimals_rounding=decimals_rounding,
            )

        # Conductance is independent of the charging input mode. Keep its existing
        # length/base scaling, rounding and guard in this single conversion owner.
        g_pu: float
        g0_pu: float
        if line_Vnom > 0.0 and Sbase > 0.0:
            impedance_base_ohm: float = line_Vnom * line_Vnom / Sbase
            g_pu = float(np.round(
                self.G * 1.0e-6 * length * impedance_base_ohm,
                decimals_rounding,
            ))
            g0_pu = float(np.round(
                self.G0 * 1.0e-6 * length * impedance_base_ohm,
                decimals_rounding,
            ))
        else:
            g_pu = 0.0
            g0_pu = 0.0

        return (
            float(r_pu), float(x_pu), float(b_pu), g_pu,
            float(r0_pu), float(x0_pu), float(b0_pu), g0_pu, float(rate_mva),
        )

    @property
    def z_nabc(self) -> np.ndarray:
        """Return the physical ABC series-impedance matrix in Ohm/km."""
        return sequence_to_phase_matrix(
            positive_sequence_value=self.R + 1j * self.X,
            zero_sequence_value=self.R0 + 1j * self.X0,
        )

    @property
    def y_nabc(self) -> np.ndarray:
        """Return the physical ABC shunt-admittance matrix in S/km."""
        if self.use_conductance:
            positive_susceptance = 2.0 * np.pi * 50.0 * self.Cnf * 1.0e-9
            zero_susceptance = 2.0 * np.pi * 50.0 * self.Cnf0 * 1.0e-9
        else:
            positive_susceptance = self.B * 1.0e-6
            zero_susceptance = self.B0 * 1.0e-6

        return sequence_to_phase_matrix(
            positive_sequence_value=self.G * 1.0e-6 + 1j * positive_susceptance,
            zero_sequence_value=self.G0 * 1.0e-6 + 1j * zero_susceptance,
        )

    @property
    def z_phases_nabc(self) -> np.ndarray:
        """Return the phase indices corresponding to ``z_nabc``."""
        return np.array([1, 2, 3], dtype=int)

    @property
    def y_phases_nabc(self) -> np.ndarray:
        """Return the phase indices corresponding to ``y_nabc``."""
        return np.array([1, 2, 3], dtype=int)

    def get_ys_nabc(self) -> AdmittanceMatrix:
        """
        Get the series 3x3 admittance matrix
        :return: AdmittanceMatrix
        """
        adm = AdmittanceMatrix(size=4)
        try:
            adm.values[1:4, 1:4] = np.linalg.inv(self.z_nabc)
        except np.linalg.LinAlgError:
            adm.values[1:4, 1:4] = np.linalg.pinv(self.z_nabc, rcond=1e-12)

        adm.phN = False
        adm.phA = True
        adm.phB = True
        adm.phC = True

        return adm

    def get_ysh_nabc(self) -> AdmittanceMatrix:
        """
        Embed the sequence shunt admittances in the stored NABC matrix.

        The susceptance-input path retains conductance in the same stored units.

        :return: Four-terminal admittance matrix with the ABC shunt block.
        """
        y1: complex
        y0: complex
        if self.use_conductance:
            y1 = 1 / (1j * 2 * np.pi * 50 * self.Cnf / 10 ** 9 + 1e-20)
            y0 = 1 / (1j * 2 * np.pi * 50 * self.Cnf0 / 10 ** 9 + 1e-20)
        else:
            # Retain physical losses when translating sequence shunts to phases.
            y1 = complex(self.G, self.B)
            y0 = complex(self.G0, self.B0)

        diag: complex = (2.0 * y1 + y0) / 3.0
        off_diag: complex = (y0 - y1) / 3.0

        y_abc: np.ndarray = np.full((3, 3), off_diag)
        np.fill_diagonal(y_abc, diag)

        adm: AdmittanceMatrix = AdmittanceMatrix(size=4)
        adm.values[1:4, 1:4] = y_abc

        adm.phN = False
        adm.phA = True
        adm.phB = True
        adm.phC = True

        return adm

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
    def G(self) -> float:
        """Return positive-sequence shunt conductance in uS/km.

        :return: Positive-sequence conductance.
        """
        return self._G

    @G.setter
    def G(self, val: float) -> None:
        """Set positive-sequence shunt conductance in uS/km.

        :param val: Conductance to assign.
        :return: None.
        """
        self._G = float(val)

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
    def G0(self) -> float:
        """Return zero-sequence shunt conductance in uS/km.

        :return: Zero-sequence conductance.
        """
        return self._G0

    @G0.setter
    def G0(self, val: float) -> None:
        """Set zero-sequence shunt conductance in uS/km.

        :param val: Conductance to assign.
        :return: None.
        """
        self._G0 = float(val)

    @property
    def Cnf(self) -> float:
        """
        Get ``Cnf``.

        :return: float
        """
        return self._Cnf

    @Cnf.setter
    def Cnf(self, val: float) -> None:
        """
        Set ``Cnf``.

        :param val: Value to assign.
        :return: None
        """
        self._Cnf = float(val)

    @property
    def Cnf0(self) -> float:
        """
        Get ``Cnf0``.

        :return: float
        """
        return self._Cnf0

    @Cnf0.setter
    def Cnf0(self, val: float) -> None:
        """
        Set ``Cnf0``.

        :param val: Value to assign.
        :return: None
        """
        self._Cnf0 = float(val)

    @property
    def use_conductance(self) -> bool:
        """
        Get ``use_conductance``.

        :return: bool
        """
        return self._use_conductance

    @use_conductance.setter
    def use_conductance(self, val: bool) -> None:
        """
        Set ``use_conductance``.

        :param val: Value to assign.
        :return: None
        """
        self._use_conductance = bool(val)

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
