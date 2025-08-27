# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.  
# SPDX-License-Identifier: MPL-2.0
from typing import Tuple
import numpy as np
from VeraGridEngine.Devices.admittance_matrix import AdmittanceMatrix
from VeraGridEngine.Devices.Parents.editable_device import EditableDevice, DeviceType


def get_line_impedances_with_c(r_ohm: float, x_ohm: float, c_nf: float,
                               length: float, Imax: float,
                               freq: float, Sbase: float, Vnom: float) -> Tuple[float, float, float, float]:
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
    :return R, X, B, rate
    """
    r_ohm_total = r_ohm * length
    x_ohm_total = x_ohm * length
    b_siemens_total = (2 * np.pi * freq * c_nf * 1e-9) * length

    Zbase = (Vnom * Vnom) / Sbase
    Ybase = 1.0 / Zbase

    R = np.round(r_ohm_total / Zbase, 6)
    X = np.round(x_ohm_total / Zbase, 6)
    B = np.round(b_siemens_total / Ybase, 6)

    rate = np.round(Imax * Vnom * 1.73205080757, 6)  # nominal power in MVA = kA * kV * sqrt(3)

    return R, X, B, rate


def get_line_impedances_with_b(r_ohm: float, x_ohm: float, b_us: float, length: float,
                               Imax: float, Sbase: float, Vnom: float) -> Tuple[float, float, float, float]:
    """
    Fill R, X, B from not-in-per-unit parameters
    :param r_ohm: Resistance per km in OHM/km
    :param x_ohm: Reactance per km in OHM/km
    :param b_us: Susceptance per km in uS/km
    :param length: length in kn
    :param Imax: Maximum current in kA
    :param Sbase: Base power in MVA (take always 100 MVA)
    :param Vnom: nominal voltage (kV)
    :return R, X, B, rate
    """
    r_ohm_total = r_ohm * length
    x_ohm_total = x_ohm * length
    b_siemens_total = (b_us * 1e-6) * length

    Zbase = (Vnom * Vnom) / Sbase
    Ybase = 1.0 / Zbase

    R = np.round(r_ohm_total / Zbase, 6)
    X = np.round(x_ohm_total / Zbase, 6)
    B = np.round(b_siemens_total / Ybase, 6)

    rate = np.round(Imax * Vnom * 1.73205080757, 6)  # nominal power in MVA = kA * kV * sqrt(3)

    return R, X, B, rate


class SequenceLineType(EditableDevice):
    __slots__ = (
        'Imax',
        'Vnom',
        'R',
        'X',
        'B',
        'Cnf',
        'R0',
        'X0',
        'B0',
        'Cnf0',
        'use_conductance',
        'n_circuits'
    )

    def __init__(self, name='SequenceLine', idtag=None, Imax=1, Vnom=1,
                 R=1e-20, X=1e-20, B=1e-20, R0=1e-20, X0=1e-20, B0=1e-20, CnF=1e-20, CnF0=1e-20,
                 use_conductance: bool = False):
        """
        Constructor
        :param name: name of the model
        :param Imax: Line rating current in kA
        :param R: Resistance of positive sequence in Ohm/km
        :param X: Reactance of positive sequence in Ohm/km
        :param B: Susceptance of positive sequence in uS/km
        :param R0: Resistance of zero sequence in Ohm/km
        :param X0: Reactance of zero sequence in Ohm/km
        :param B0: Susceptance of zero sequence in uS/km
        :param CnF: Conductivity of positive sequence in uS/km
        :param CnF0: Conductivity of zero sequence in uS/km
        """

        EditableDevice.__init__(self,
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
        self.Cnf = CnF

        self.R0 = R0
        self.X0 = X0
        self.B0 = B0
        self.Cnf0 = CnF0

        self.use_conductance = use_conductance

        self.n_circuits = 1

        self.register(key='Imax', units='kA', tpe=float, definition='Current rating of the line', old_names=['rating'])
        self.register(key='Vnom', units='kV', tpe=float, definition='Voltage rating of the line')
        self.register(key='R', units='Ohm/km', tpe=float, definition='Positive-sequence resistance per km')
        self.register(key='X', units='Ohm/km', tpe=float, definition='Positive-sequence reactance per km')
        self.register(key='B', units='uS/km', tpe=float, definition='Positive-sequence shunt susceptance per km')
        self.register(key='R0', units='Ohm/km', tpe=float, definition='Zero-sequence resistance per km')
        self.register(key='X0', units='Ohm/km', tpe=float, definition='Zero-sequence reactance per km')
        self.register(key='B0', units='uS/km', tpe=float, definition='Zero-sequence shunt susceptance per km')
        self.register(key='Cnf', units='nF/km', tpe=float, definition='Positive-sequence shunt conductance per km')
        self.register(key='Cnf0', units='nF/km', tpe=float, definition='Zero-sequence shunt conductance per km')
        self.register(key='use_conductance', units='', tpe=bool,
                      definition='Use conductance? else the susceptance is used')
        self.register(key='n_circuits', units='', tpe=int, definition='number of circuits')

    def get_values(self, Sbase: float, freq: float, length: float, line_Vnom: float, ):
        """
        Get the per-unit values
        :param Sbase: Base power (MVA, always use 100MVA)
        :param freq: Frequency (Hz)
        :param length: length in km
        :param line_Vnom: Line nominal voltage
        :return: R (p.u.), x(p.u.), B(p.u.), Rate (MVA)
        """

        if self.use_conductance:
            R, X, B, rate = get_line_impedances_with_c(r_ohm=self.R,
                                                       x_ohm=self.X,
                                                       c_nf=self.Cnf,
                                                       length=length, Imax=self.Imax,
                                                       freq=freq, Sbase=Sbase, Vnom=line_Vnom)
            R0, X0, B0, _ = get_line_impedances_with_c(r_ohm=self.R0,
                                                       x_ohm=self.X0,
                                                       c_nf=self.Cnf0,
                                                       length=length, Imax=self.Imax,
                                                       freq=freq, Sbase=Sbase, Vnom=line_Vnom)
        else:
            R, X, B, rate = get_line_impedances_with_b(r_ohm=self.R,
                                                       x_ohm=self.X,
                                                       b_us=self.B,
                                                       length=length, Imax=self.Imax,
                                                       Sbase=Sbase, Vnom=line_Vnom)
            R0, X0, B0, _ = get_line_impedances_with_b(r_ohm=self.R0,
                                                       x_ohm=self.X0,
                                                       b_us=self.B0,
                                                       length=length, Imax=self.Imax,
                                                       Sbase=Sbase, Vnom=line_Vnom)

        return R, X, B, R0, X0, B0, rate

    def get_ys_abc(self) -> AdmittanceMatrix:
        """
        Get the series 3x3 admittance matrix
        :return: AdmittanceMatrix
        """
        z1 = self.R + 1j * self.X
        z0 = self.R0 + 1j * self.X0

        diag = (2 * z1 + z0) / 3
        off_diag = (z0 - z1) / 3

        zabc = np.full((3, 3), off_diag)
        np.fill_diagonal(zabc, diag)

        adm = AdmittanceMatrix(size=3)
        try:
            adm.values = np.linalg.inv(zabc)
        except np.linalg.LinAlgError:
            adm.values = np.linalg.pinv(zabc)

        adm.phA = 1
        adm.phB = 1
        adm.phC = 1

        return adm

    def get_ysh_abc(self) -> AdmittanceMatrix:
        """
        get the 3x3 shunt admittance matrix from the sequence values
        :return AdmittanceMatrix
        """
        if self.use_conductance:
            y1 = 1 / (1j * 2 * np.pi * 50 * self.Cnf / 10 ** 9 + 1e-20)
            y0 = 1 / (1j * 2 * np.pi * 50 * self.Cnf0 / 10 ** 9 + 1e-20)
        else:
            y1 = 1j * self.B
            y0 = 1j * self.B0

        diag = (2.0 * y1 + y0) / 3.0
        off_diag = (y0 - y1) / 3.0

        yabc = np.full((3, 3), off_diag)
        np.fill_diagonal(yabc, diag)

        adm = AdmittanceMatrix(size=3)
        adm.values = yabc
        adm.phA = 1
        adm.phB = 1
        adm.phC = 1

        return adm
