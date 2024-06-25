# GridCal
# Copyright (C) 2015 - 2024 Santiago Peñate Vera
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 3 of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program; if not, write to the Free Software Foundation,
# Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.


import numpy as np
import pandas as pd
from scipy.sparse.linalg import splu
from scipy.sparse import csr_matrix as sparse
from enum import Enum
from warnings import warn
from matplotlib import pyplot as plt


class DiffEqSolver(Enum):
    """
    DiffEqSolver
    """
    EULER = 1,
    RUNGE_KUTTA = 2


class DynamicModels(Enum):
    """
    DynamicModels
    """
    NoModel = 0,
    SynchronousGeneratorOrder4 = 1,  # fourth order synchronous machine
    SynchronousGeneratorOrder6 = 2,  # sixth order synchronous machine
    VoltageSourceConverter = 3,  # voltage source converter
    ExternalGrid = 4,  # external grid
    AsynchronousSingleCageMotor = 5,  # single cage asynchronous motor
    AsynchronousDoubleCageMotor = 6  # double cage asynchronous motor


class TransientStabilityEvents:
    """
    TransientStabilityEvents
    """

    def __init__(self):
        self.time = list()
        self.event_type = list()
        self.object = list()
        self.params = list()

        self.events_available = ['Bus short circuit', 'Bus recovery', 'Line failure', 'Line recovery']

    def add(self, t, evt_type, obj, param):
        """
        Add elements
        :param t: time in seconds
        :param evt_type: event type
        :param obj: object selected
        :param param: extra parameters
        """

        if evt_type not in self.events_available:
            raise Exception('Event not supported!')

        self.time.append(t)
        self.event_type.append(evt_type)
        self.object.append(obj)
        self.params.append(param)

    def remove_at(self, i):
        """
        Remove the elements at a position
        :param i: index
        """
        self.time.pop(i)
        self.event_type.pop(i)
        self.object.pop(i)
        self.params.pop(i)


class TransientStabilityResults:

    def __init__(self):

        self.name = "Transient stability"

        self.voltage = None

        self.omega = None

        self.time = None

        self.available_results = ['Bus voltage']

    def plot(self, result_type, ax=None, indices=None, names=None, LINEWIDTH=2):
        """
        Plot the results
        :param result_type:
        :param ax:
        :param indices:
        :param names:
        :return:
        """
        if ax is None:
            fig = plt.figure()
            ax = fig.add_subplot(111)

        if indices is None:
            indices = np.array(range(len(names)))

        if len(indices) > 0:
            labels = names[indices]
            y_label = ''
            title = ''
            if result_type == 'Bus voltage':

                y = np.abs(self.voltage[:, indices])
                y_label = '(p.u.)'
                title = 'Bus voltage module'

            else:
                pass

            df = pd.DataFrame(data=y, columns=labels, index=self.time)

            df.fillna(0, inplace=True)

            if len(df.columns) > 10:
                df.plot(ax=ax, linewidth=LINEWIDTH, legend=False)
            else:
                df.plot(ax=ax, linewidth=LINEWIDTH, legend=True)

            ax.set_title(title)
            ax.set_ylabel(y_label)
            ax.set_xlabel('Time')

            return df

        else:
            return None


class SynchronousMachineOrder4:
    """
    4th Order Synchronous Machine Model
    https://wiki.openelectrical.org/index.php?title=Synchronous_Machine_Models#4th_Order_.28Two-Axis.29_Model
    Copyright (C) 2014-2015 Julius Susanto. All rights reserved.

    typical values:
    Ra = 0.0
    Xa = 0.0
    Xd = 1.68
    Xq = 1.61
    Xdp = 0.32
    Xqp = 0.32
    Xdpp = 0.2
    Xqpp = 0.2
    Td0p = 5.5
    Tq0p = 4.60375
    Td0pp = 0.0575
    Tq0pp = 0.0575
    H = 2
    """

    def __init__(self, H, Ra, Xd, Xdp, Xdpp, Xq, Xqp, Xqpp, Td0p, Tq0p, base_mva, Sbase, bus_idx, fn=50,
                 speed_volt=False, solver=DiffEqSolver.RUNGE_KUTTA):
        """

        :param H: is the machine inertia constant (MWs/MVA)
        :param Ra: armature resistance (pu)
        :param Xd: d-axis reactance (p.u.)
        :param Xdp: d-axis transient reactance (p.u.)
        :param Xdpp:is the d-axis subtransient reactance (pu)
        :param Xq: q-axis reactance (p.u.)
        :param Xqp: q-axis transient reactance (p.u.)
        :param Xqpp: is the q-axis subtransient reactance (pu)
        :param Td0p: d-axis transient open loop time constant (s)
        :param Tq0p: q-axis transient open loop time constant (s)
        :param base_mva: machine base power
        :param Sbase: system base power (100 MVA usually)
        :param fn: frequency
        :param speed_volt: include speed-voltage term option?
        :param solver: DiffEqSolver
        """

        self.solver = solver

        self.bus_idx = bus_idx

        self.Vfd = 0.0

        self.Id = 0.0
        self.Iq = 0.0

        # stator voltage (d, q axis)
        self.Vd = 0.0
        self.Vq = 0.0

        self.Vt = 0.0

        self.P = 0.0
        self.Q = 0.0

        self.Pm = 0.0

        self.omega = 0.0
        self.delta = 0.0
        self.Eqp = 0.0
        self.Edp = 0.0

        self.Vang = 0.0

        self.Tm = 0.0
        self.In = 0.0
        self.Im = 0.0

        self.omega_prev = 0.0
        self.delta_prev = 0.0
        self.Eqp_prev = 0.0
        self.Edp_prev = 0.0

        self.arr_Eqp = np.zeros(3)
        self.arr_Edp = np.zeros(3)
        self.arr_omega = np.zeros(3)
        self.arr_delta = np.zeros(3)

        self.Td0p = Td0p
        self.Tq0p = Tq0p

        # angular speed (w = 2·pi·f)
        self.omega_n = 2.0 * np.ones_like(H) * np.pi * fn

        # Check for speed-voltage term option
        self.speed_volt = speed_volt  # True / False

        # Convert impedances and H to system MVA base
        self.H = H * base_mva / Sbase
        self.Ra = Ra * Sbase / base_mva
        self.Xd = Xd * Sbase / base_mva
        self.Xdp = Xdp * Sbase / base_mva
        self.Xdpp = Xdpp * Sbase / base_mva
        self.Xq = Xq * Sbase / base_mva
        self.Xqp = Xqp * Sbase / base_mva
        self.Xqpp = Xqpp * Sbase / base_mva

        # Equivalent Norton impedance for Ybus
        self.Yg = self.get_yg()

    def get_yg(self):
        """
        Get the generator admittance
        :return: shunt admittance
        """
        return (self.Ra - 1j * 0.5 * (self.Xdp + self.Xqp)) / (self.Ra ** 2.0 + (self.Xdp * self.Xqp))

    def initialise(self, vt0, S0):
        """
        Initialise machine signals and states based on load flow voltage and complex power injection
        :param vt0: complex initial voltage
        :param S0: complex initial power
        :return:
        """

        # Calculate initial armature current
        Ia0 = np.conj(S0 / vt0)
        phi0 = np.angle(Ia0)

        # Calculate steady state machine emf (i.e. voltage behind synchronous reactance)
        Eq0 = vt0 + (self.Ra + 1j * self.Xq) * Ia0
        self.delta = np.angle(Eq0)

        # Convert currents to rotor reference frame
        self.Id = np.abs(Ia0) * np.sin(self.delta - phi0)
        self.Iq = np.abs(Ia0) * np.cos(self.delta - phi0)

        # Convert voltages to rotor reference frame
        self.Vd = np.abs(vt0) * np.sin(self.delta - np.angle(vt0))
        self.Vq = np.abs(vt0) * np.cos(self.delta - np.angle(vt0))

        # Calculate machine state variables and Vfd
        self.Eqp = self.Vq + self.Ra * self.Iq + self.Xdp * self.Id
        self.Edp = self.Vd + self.Ra * self.Id - self.Xqp * self.Iq
        self.Vfd = np.abs(self.Eqp) + (self.Xd - self.Xdp) * self.Id

        # Calculate active and reactive power
        self.P = (self.Vd + self.Ra * self.Id) * self.Id + (self.Vq + self.Ra * self.Iq) * self.Iq
        self.Q = self.Vq * self.Id - self.Vd * self.Iq

        # Initialise the rest
        self.Vt = np.abs(vt0)
        self.Pm = self.P
        self.omega = 1

        self.check_diffs()

    def calc_currents(self, Vbus, Ibus):
        """
        Calculate machine current Injections (in network reference frame)
        :param vt: complex initial voltage
        :return:
        """

        vt = Vbus[self.bus_idx]

        # Calculate terminal voltage in dq reference frame
        self.Vd = np.abs(vt) * np.sin(self.delta - np.angle(vt))
        self.Vq = np.abs(vt) * np.cos(self.delta - np.angle(vt))

        # Check if speed-voltage term should be included
        k = np.where(self.speed_volt == False)[0]
        omega = self.omega
        omega[k] = np.ones_like(k)

        # Calculate Id and Iq (Norton equivalent current injection in dq frame)
        self.Id = (self.Eqp - self.Ra / (self.Xqp * omega) * (self.Vd - self.Edp) - self.Vq / omega) / (
                    self.Xdp + self.Ra ** 2 / (omega * omega * self.Xqp))
        self.Iq = (self.Vd / omega + self.Ra * self.Id / omega - self.Edp) / self.Xqp

        # Calculate power output
        self.P = (self.Vd + self.Ra * self.Id) * self.Id + (self.Vq + self.Ra * self.Iq) * self.Iq
        self.Q = self.Vq * self.Id - self.Vd * self.Iq

        # Calculate machine current injection (Norton equivalent current injection in network frame)
        self.In = (self.Iq - 1j * self.Id) * np.exp(1j * self.delta)
        self.Im = self.In + self.Yg * vt

        self.Vt = np.abs(vt)
        self.Vang = np.angle(vt)

        # apply th currents to the passed vector
        Ibus[self.bus_idx] = self.Im

    def check_diffs(self):
        """
        Check if differential equations are zero (on initialisation)
        """

        # State variables
        dEqp = (self.Vfd - (self.Xd - self.Xdp) * self.Id - self.Eqp) / self.Td0p
        dEdp = ((self.Xq - self.Xqp) * self.Iq - self.Edp) / self.Tq0p

        if np.all(np.round(dEdp, 6)) != 0 or np.all(np.round(dEqp, 6)) != 0:
            warn('Warning: differential equations not zero on initialisation...')
            print('dEdp = ' + str(dEdp) + ', dEqp = ' + str(dEqp))

    def function(self, h, Eqp, Edp, omega):
        """
        Compute the magnitude's derivatives
        :param Eqp:
        :param Edp:
        :param omega:
        :return:
        """
        # Electrical differential equations
        f1 = (self.Vfd - (self.Xd - self.Xdp) * self.Id - Eqp) / self.Td0p

        f2 = ((self.Xq - self.Xqp) * self.Iq - Edp) / self.Tq0p

        # Swing equation
        f3 = 1.0 / (2.0 * self.H) * (self.Pm / omega - self.P)

        f4 = self.omega_n * (omega - 1.0)

        return h * f1, h * f2, h * f3, h * f4

    def solve(self, h):
        """
        Solve using Runge-Kutta
        Args:
            h: step size

        Returns: self.Eqp, self.Edp, self.omega, self.delta
        """
        # step 1
        k1_Eqp, k1_Edp, k1_omega, k1_delta = self.function(h, self.Eqp, self.Edp, self.omega)

        # step 2
        k2_Eqp, k2_Edp, k2_omega, k2_delta = self.function(h, self.Eqp + 0.5 * k1_Eqp,
                                                           self.Edp + 0.5 * k1_Edp,
                                                           self.omega + 0.5 * k1_omega)

        # step 3
        k3_Eqp, k3_Edp, k3_omega, k3_delta = self.function(h, self.Eqp + 0.5 * k2_Eqp,
                                                           self.Edp + 0.5 * k2_Edp,
                                                           self.omega + 0.5 * k2_omega)

        # step 4
        k4_Eqp, k4_Edp, k4_omega, k4_delta = self.function(h, self.Eqp + 0.5 * k3_Eqp,
                                                           self.Edp + 0.5 * k3_Edp,
                                                           self.omega + 0.5 * k3_omega)
        a = 1.0 / 6.0

        # Tm = Pm / omega_0

        # update the values

        self.Eqp += a * (k1_Eqp + 2.0 * k2_Eqp + 2.0 * k3_Eqp + k4_Eqp)

        self.Edp += a * (k1_Edp + 2.0 * k2_Edp + 2.0 * k3_Edp + k4_Edp)

        self.omega += a * (k1_omega + 2.0 * k2_omega + 2.0 * k3_omega + k4_omega)

        self.delta += a * (k1_delta + 2.0 * k2_delta + 2.0 * k3_delta + k4_delta)

        return self.Eqp, self.Edp, self.omega, self.delta


class SynchronousMachineOrder6SauerPai:
    """
    PYPOWER-Dynamics
    6th Order Synchronous Machine Model
    Based on Sauer-Pai model
    Sauer, P.W., Pai, M. A., "Power System Dynamics and Stability", Stipes Publishing, 2006 
    """

    def __init__(self, H, Ra, Xa, Xd, Xdp, Xdpp, Xq, Xqp, Xqpp, Td0p, Tq0p, Td0pp, Tq0pp, base_mva, Sbase, bus_idx,
                 fn=50, speed_volt=False):

        self.omega_n = 2 * np.pi * fn

        self.bus_idx = bus_idx

        # Check for speed-voltage term option 
        self.speed_volt = speed_volt

        self.H = H * base_mva / Sbase
        self.Ra = Ra * Sbase / base_mva
        self.Xa = Xa * Sbase / base_mva
        self.Xd = Xd * Sbase / base_mva
        self.Xdp = Xdp * Sbase / base_mva
        self.Xdpp = Xdpp * Sbase / base_mva
        self.Xq = Xq * Sbase / base_mva
        self.Xqp = Xqp * Sbase / base_mva
        self.Xqpp = Xqpp * Sbase / base_mva

        self.Td0p, self.Tq0p, self.Td0pp, self.Tq0pp = Td0p, Tq0p, Td0pp, Tq0pp

        # Internal variables
        self.gamma_d1 = (self.Xdpp - self.Xa) / (self.Xdp - self.Xa)
        self.gamma_d2 = (1 - self.gamma_d1) / (self.Xdp - self.Xa)
        self.gamma_q1 = (self.Xqpp - self.Xa) / (self.Xqp - self.Xa)
        self.gamma_q2 = (1 - self.gamma_q1) / (self.Xqp - self.Xa)

        # Equivalent Norton impedance for Ybus modification
        self.Yg = (self.Ra - 1j * 0.5 * (self.Xdpp + self.Xqpp)) / (self.Ra ** 2 + (self.Xdpp * self.Xqpp))

        # results
        self.Vfd = 0
        self.Id = 0
        self.Iq = 0
        self.Vd = 0
        self.Vq = 0
        self.Vt = 0
        self.Vang = 0
        self.P = 0
        self.Q = 0
        self.Pm = 0
        self.Tm = 0
        self.omega = 1
        self.delta = 0
        self.Eqp = 0
        self.phiq_pp = 0
        self.Edp = 0
        self.phid_pp = 0
        self.In = 0
        self.Im = 0

    def get_yg(self):
        """
        Get the generator admittance
        :return: shunt admittance
        """
        return (self.Ra - 1j * 0.5 * (self.Xdp + self.Xqp)) / (self.Ra ** 2.0 + (self.Xdp * self.Xqp))

    def initialise(self, vt0, S0):
        """
        Initialise machine signals and states based on load flow voltage and complex power injection
        """

        # Calculate initial armature current
        Ia0 = np.conj(S0 / vt0)
        phi0 = np.angle(Ia0)

        # Calculate steady state machine emf (i.e. voltage behind synchronous reactance)
        Eq0 = vt0 + (self.Ra + 1j * self.Xq) * Ia0
        self.delta = np.angle(Eq0)

        # Convert currents to rotor reference frame
        self.Id = np.abs(Ia0) * np.sin(self.delta - phi0)
        self.Iq = np.abs(Ia0) * np.cos(self.delta - phi0)

        self.Vd = np.abs(vt0) * np.sin(self.delta - np.angle(vt0))
        self.Vq = np.abs(vt0) * np.cos(self.delta - np.angle(vt0))

        # Calculate machine state variables and Vfd
        self.Edp = self.Vd - self.Xqpp * self.Iq + self.Ra * self.Id - (1 - self.gamma_q1) * (
                    self.Xqp - self.Xa) * self.Iq
        self.Eqp = self.Vq + self.Xdpp * self.Id + self.Ra * self.Iq + (1 - self.gamma_d1) * (
                    self.Xdp - self.Xa) * self.Id
        self.phid_pp = self.Eqp - (self.Xdp - self.Xa) * self.Id
        self.phiq_pp = -self.Edp - (self.Xqp - self.Xa) * self.Iq
        self.Vfd = self.Eqp + (self.Xd - self.Xdp) * (
                    self.Id - self.gamma_d2 * self.phid_pp - (1 - self.gamma_d1) * self.Id + self.gamma_d2 * self.Eqp)

        # Calculate active and reactive power
        self.P = self.Vd * self.Id + self.Vq * self.Iq
        self.Q = self.Vq * self.Id - self.Vd * self.Iq

        # Initialise signals, states and parameters
        self.Vt = np.abs(vt0)
        self.Vang = 0
        self.Pm = self.P
        self.Tm = self.P
        self.omega = 1

        self.check_diffs()

    def check_diffs(self):
        """
        Check if differential equations are zero (on initialisation)
        """

        dEqp = (self.Vfd - (self.Xd - self.Xdp)
                * (self.Id - self.gamma_d2 * self.phid_pp - (1 - self.gamma_d1)
                   * self.Id + self.gamma_d2 * self.Eqp) - self.Eqp) / self.Td0p
        dEdp = ((self.Xq - self.Xqp)
                * (self.Iq - self.gamma_q2 * self.phiq_pp - (1 - self.gamma_q1)
                   * self.Iq - self.gamma_q2 * self.Edp) - self.Edp) / self.Tq0p
        dphid_pp = (self.Eqp - (self.Xdp - self.Xa) * self.Id - self.phid_pp) / self.Td0pp
        dphiq_pp = (-self.Edp - (self.Xqp - self.Xa) * self.Iq - self.phiq_pp) / self.Tq0pp

        if (np.all(np.round(dEdp, 6)) != 0
                or np.all(np.round(dEqp, 6)) != 0
                or np.all(np.round(dphid_pp, 6)) != 0
                or np.all(np.round(dphiq_pp, 6)) != 0):
            print('Warning: differential equations not zero on initialisation...')
            print('dEdp = ' + str(dEdp) + ', dEqp = ' + str(dEqp) + ', dphid_pp = ' + str(
                dphid_pp) + ', dphiq_pp = ' + str(dphiq_pp))

    def calc_currents(self, vt):
        """
        Calculate machine current Injections (in network reference frame)
        """

        # Calculate terminal voltage in dq reference frame
        self.Vd = np.abs(vt) * np.sin(self.delta - np.angle(vt))
        self.Vq = np.abs(vt) * np.cos(self.delta - np.angle(vt))

        # Check if speed-voltage term should be included
        if self.speed_volt:
            omega = self.omega
        else:
            omega = 1

        # Calculate Id and Iq (Norton equivalent current injection in dq frame)
        self.Id = (-self.Vq / omega + self.gamma_d1 * self.Eqp + (1 - self.gamma_d1) * self.phid_pp
                   - self.Ra / (omega * self.Xqpp)
                   * (self.Vd - self.gamma_q1 * self.Edp + (1 - self.gamma_q1) * self.phiq_pp)) \
                  / (self.Xdpp + self.Ra ** 2 / (omega * omega * self.Xqpp))

        self.Iq = (self.Vd / omega + (self.Ra * self.Id / omega) - self.gamma_q1 * self.Edp
                   + (1 - self.gamma_q1) * self.phiq_pp) / self.Xqpp

        # Calculate power output
        self.P = (self.Vd + self.Ra * self.Id) * self.Id + (self.Vq + self.Ra * self.Iq) * self.Iq
        self.Q = self.Vq * self.Id - self.Vd * self.Iq
        # self.S = np.complex(p, q)

        # Calculate machine current injection (Norton equivalent current injection in network frame)
        delta = self.delta
        self.In = (self.Iq - 1j * self.Id) * np.exp(1j * self.delta)
        self.Im = self.In + self.Yg * vt

        # Update signals
        self.Vt = np.abs(vt)
        self.Vang = np.angle(vt)

        return self.Im

    def function(self, Eqp, Edp, omega):
        """
        Solve machine differential equations for the next stage in the integration step
        :param Eqp:
        :param Edp:
        :param omega:
        :return:
        """

        # Eq'
        f1 = (self.Vfd
              - (self.Xd - self.Xdp) * (self.Id - self.gamma_d2 * self.phid_pp
                                        - (1 - self.gamma_d1) * self.Id + self.gamma_d2 * Eqp) - Eqp) / self.Td0p

        # Ed'
        f2 = ((self.Xq - self.Xqp) * (self.Iq - self.gamma_q2 * self.phiq_pp
                                      - (1 - self.gamma_q1) * self.Iq - self.gamma_q2 * Edp) - Edp) / self.Tq0p

        # phi d pp
        f3 = (Eqp - (self.Xdp - self.Xa) * self.Id - self.phid_pp) / self.Td0pp

        # phi_q''
        f4 = (-Edp - (self.Xqp - self.Xa) * self.Iq - self.phiq_pp) / self.Tq0pp

        # omega
        f5 = 0.5 / self.H * (self.Pm / omega - self.P)

        # delta
        f6 = self.omega_n * (omega - 1)

        return f1, f2, f3, f4, f5, f6


class VoltageSourceConverterAverage:
    """
    Voltage Source Converter Model Class
    Average model of a VSC in voltage-control mode (i.e. controlled voltage source behind an impedance).
    Copyright (C) 2014-2015 Julius Susanto. All rights reserved.
    """

    def __init__(self, Rl, Xl, fn, bus_idx):
        self.bus_idx = bus_idx

        self.Rl = Rl
        self.Xl = Xl
        self.fn = fn

        self.Edq = 0.0
        self.delta = 0.0
        self.omega = 0.0
        self.Id = 0.0
        self.Iq = 0.0
        self.Vt = 0.0
        self.Ed = 0.0
        self.Eq = 0.0
        self.Vd = 0.0
        self.Vq = 0.0

        self.In = 0.0
        self.Im = 0.0

        # Equivalent Norton impedance for Ybus modification
        self.Yg = self.get_yg()

    def get_yg(self):
        """
        Get the generator admittance
        :return: shunt admittance
        """
        return 1 / (self.Rl + 1j * self.Xl)

    def initialise(self, vt0, S0):
        """
        Initialise converter emf based on load flow voltage and grid current injection
        :param vt0: complex voltage
        :param S0: complex power
        """
        # Calculate initial armature current
        Ia0 = np.conj(S0 / vt0)
        phi0 = np.angle(Ia0)

        # Calculate steady state machine emf (i.e. voltage behind synchronous reactance)
        self.Edq = vt0 + (self.Rl + 1j * self.Xl) * Ia0
        self.delta = np.angle(self.Edq)

        # Convert currents to rotor reference frame
        self.Id = np.abs(Ia0) * np.sin(self.delta - phi0)
        self.Iq = np.abs(Ia0) * np.cos(self.delta - phi0)

        # Initialise signals, states and parameters
        self.Vt = np.abs(vt0)
        self.Ed = np.real(self.Edq)
        self.Eq = np.imag(self.Edq)
        self.omega = 1.0

    def calc_currents(self, vt):
        """
        Solve grid current Injections (in network reference frame)
        :param vt: complex voltage
        :return:
        """
        self.Edq = self.Ed + 1j * self.Eq
        self.delta = np.angle(self.Edq)

        # Calculate terminal voltage in dq reference frame
        self.Vd = np.abs(vt) * np.sin(self.delta - np.angle(vt))
        self.Vq = np.abs(vt) * np.cos(self.delta - np.angle(vt))

        # Calculate Id and Iq (Norton equivalent current injection in dq frame)
        Ia = (self.Edq - vt) / (self.Rl + 1j * self.Xl)
        phi = np.angle(Ia)
        self.Id = np.abs(Ia) * np.sin(self.delta - phi)
        self.Iq = np.abs(Ia) * np.cos(self.delta - phi)

        # Calculate machine current injection (Norton equivalent current injection in network frame)
        self.In = (self.Iq - 1j * self.Id) * np.exp(1j * self.delta)
        self.Im = self.In + self.Yg * vt
        self.Vt = np.abs(vt)

        # self.delta = delta

        return self.Im

    def function(self, h, d):
        """
        Solve machine differential equations for the next stage in the integration step
        :param h: solve step in seconds
        """

        # State variables do not change in this model
        pass


class ExternalGrid:
    """
    External Grid Model Class
    Grid is modelled as a constant voltage behind a transient reactance
    and two differential equations representing the swing equations.
    """

    def __init__(self, Xdp, H, fn, bus_idx):
        self.bus_idx = bus_idx

        self.Xdp = Xdp
        self.H = H
        self.fn = fn

        # result values
        self.Vt = 0
        self.P = 0
        self.Pm = 0
        self.Eq = 0
        self.omega = 0
        self.delta = 0

    def initialise(self, vt0, S0):
        """
        Initialise grid emf based on load flow voltage and grid current injection
        """
        # Calculate initial armature current
        Ia0 = np.conj(S0 / vt0)
        phi0 = np.angle(Ia0)

        # Calculate steady state machine emf (i.e. voltage behind synchronous reactance)
        Eq0 = vt0 + 1j * self.Xdp * Ia0
        delta0 = np.angle(Eq0)

        p0 = 1 / self.Xdp * np.abs(vt0) * np.abs(Eq0) * np.sin(delta0 - np.angle(vt0))

        # Initialise signals, states and parameters
        self.Vt = np.abs(vt0)
        self.P = p0
        self.Pm = p0
        self.Eq = np.abs(Eq0)
        self.omega = 1
        self.delta = delta0

    def get_yg(self):
        """
        Return the shunt admittance
        Returns:

        """
        return 1 / (1j * self.Xdp)

    def calc_currents(self, vt):
        """
        Solve grid current Injections (in network reference frame)
        """

        self.P = np.abs(vt) * self.Eq * np.sin(self.delta - np.angle(vt)) / self.Xdp

        # Update signals
        self.Vt = np.abs(vt)

        i_grid = self.Eq * np.exp(1j * self.delta) / (1j * self.Xdp)

        return i_grid

    def function(self, Eqp, Edp, omega):
        """
        Solve machine differential equations for the next stage in the integration step
        """

        # Solve swing equation
        f1 = 1 / (2 * self.H) * (self.Pm / omega - self.P)

        f2 = 2 * np.pi * self.fn * (omega - 1.0)

        f3 = np.zeros_like(Eqp)

        f4 = np.zeros_like(Eqp)

        return f1, f2, f3, f4


class SingleCageAsynchronousMotor:
    """
    Single Cage Asynchronous Motor Model

    Model equations based on section 15.2.4 of:
    Milano, F., "Power System Modelling and Scripting", Springer-Verlag, 2010

    """

    def __init__(self, H, Rr, Xr, Rs, Xs, a, Xm, MVA_Rating, Sbase, bus_idx, fn=50):
        """
        
        :param H: 
        :param Rr: 
        :param Xr: 
        :param Rs: 
        :param Xs: 
        :param a: 
        :param Xm: 
        :param Sbase: System base power
        :param fn: system frequency
        """

        self.bus_idx = bus_idx

        self.omega_n = 2 * np.pi * fn

        self.Sbase = Sbase
        self.base_mva = MVA_Rating
        # Convert parameters to 100MVA base
        self.H = H * self.base_mva / 100
        self.a = a * self.base_mva / 100
        self.Rs = Rs * 100 / self.base_mva
        self.Xs = Xs * 100 / self.base_mva
        self.Xm = Xm * 100 / self.base_mva
        self.Rr = Rr * 100 / self.base_mva
        self.Xr = Xr * 100 / self.base_mva

        # Calculate internal parameters
        self.X0 = self.Xs + self.Xm
        self.Xp = self.Xs + self.Xr * self.Xm / (self.Xr + self.Xm)
        self.T0p = (self.Xr + self.Xm) / (self.omega_n * self.Rr)

        # Motor start signal
        self.start = 0

        # Equivalent Norton impedance for Ybus modification (NOTE: currently not used)
        self.Ym = self.Rs - 1j * self.Xs

        # results
        self.Id = np.zeros_like(H)
        self.Iq = np.zeros_like(H)
        self.Vd = np.zeros_like(H)
        self.Vq = np.zeros_like(H)
        self.Vt = np.zeros_like(H)
        self.P = np.zeros_like(H)
        self.Q = np.zeros_like(H)
        self.Te = np.zeros_like(H)
        self.slip = np.zeros_like(H)
        self.Eqp = np.zeros_like(H)
        self.Edp = np.zeros_like(H)
        self.omega = 1 - self.slip
        self.Im = np.zeros_like(H)
        self.In = np.zeros_like(H)
        self.Vang = np.zeros_like(H)

    def get_yg(self):
        """
        Get the generator admittance
        :return: shunt admittance
        """
        return 1 / (self.Rr + 1j * self.Xr)

    def initialise(self, vt0, S0):
        """
        Initialise machine signals and states based on load flow voltage and complex power injection
        NOTE: currently only initialised at standstill
        """

        # Initialise signals, states and parameters
        self.Id = 0
        self.Iq = 0
        self.Vd = 0
        self.Vq = 0
        self.Vt = np.abs(vt0)
        self.P = 0
        self.Q = 0
        self.Te = 0
        self.omega = 1 - 0

        self.slip = 1
        self.Eqp = 0
        self.Edp = 0

        self.check_diffs()

    def calc_tmech(self, s):
        """
        Calculate mechanical load torque (with a quadratic load model)
        :param s: slip
        :return: 
        """

        Tm = self.a * (1 - s) ** 2

        return Tm

    def calc_currents(self, vt):
        """
        Calculate machine current Injections (in network reference frame)
        """

        if self.start == 1:
            # Calculate terminal voltage in dq reference frame (set to rotate with q-axis)
            self.Vd = -np.abs(vt) * np.sin(np.angle(vt))
            self.Vq = np.abs(vt) * np.cos(np.angle(vt))

            # Calculate Id and Iq (Norton equivalent current injection in dq frame)
            self.Iq = (self.Rs / self.Xp * (self.Vq - self.Eqp) - self.Vd + self.Edp) / (
                        self.Xp + self.Rs ** 2 / self.Xp)
            self.Id = (self.Vq - self.Eqp - self.Rs * self.Iq) / self.Xp

            # Calculate power output and electrical torque
            self.P = -(self.Vd * self.Id + self.Vq * self.Iq)
            self.Q = -(self.Vq * self.Id - self.Vd * self.Iq)
            self.Te = (self.Edp * self.Id + self.Eqp * self.Iq)  # / self.omega_n

            # Calculate machine current injection (Norton equivalent current injection in network frame)
            self.In = (self.Id + 1j * self.Iq) * np.exp(1j * (-np.pi / 2))
            self.Im = -self.In  # + self.Ym * vt

            # Update signals
            self.Vt = np.abs(vt)
            self.Vang = np.angle(vt)
            self.omega = 1 - self.slip

        else:
            self.Im = 0

        return self.Im

    def function(self, Edp, Eqp):
        """
        Solve machine differential equations for the next stage in the integration step
        """

        if self.start == 1:

            # Eq'
            f1 = (-self.omega_n * self.slip * Edp - (
                        Eqp - (self.X0 - self.Xp) * self.Id) / self.T0p) * self.base_mva / self.Sbase

            # Ed'
            f2 = (self.omega_n * self.slip * Eqp - (
                        Edp + (self.X0 - self.Xp) * self.Iq) / self.T0p) * self.base_mva / self.Sbase

            # Tm
            Tm = self.calc_tmech(self.slip)
            f3 = (Tm - self.Te) / (2 * self.H)

        else:
            f1 = np.zeros_like(Edp)
            f2 = np.zeros_like(Edp)
            f3 = np.zeros_like(Edp)

        return f1, f2, f3

    def check_diffs(self):
        """
        Check if differential equations are zero (on initialisation)
        """

        # State variables
        dEdp = self.omega_n * self.slip * self.Eqp - (self.Edp + (self.X0 - self.Xp) * self.Iq) / self.T0p
        dEqp = -self.omega_n * self.slip * self.Edp - (self.Eqp - (self.X0 - self.Xp) * self.Id) / self.T0p
        ds = self.calc_tmech(1) - self.Te

        if (np.all(np.round(dEdp, 6)) != 0
                or np.all(np.round(dEqp, 6)) != 0
                or np.all(np.round(ds, 6)) != 0):
            warn('Warning: differential equations not zero on initialisation...')
            print('dEdp = ', dEdp, ', dEqp = ', dEqp, ', ds = ', ds)


class DoubleCageAsynchronousMotor:
    """
    Double Cage Asynchronous Machine Model

    Model equations based on section 15.2.5 of:
    Milano, F., "Power System Modelling and Scripting", Springer-Verlag, 2010

    """

    def __init__(self, H, Rr, Xr, Rs, Xs, a, Xm, Rr2, Xr2, MVA_Rating, Sbase, bus_idx, fn=50):

        self.bus_idx = bus_idx

        self.omega_n = 2 * np.pi * fn

        # Convert parameters to 100MVA base
        self.base_mva = MVA_Rating
        self.Sbase = Sbase
        self.H = H * self.base_mva / self.Sbase
        self.a = a * self.base_mva / self.Sbase
        self.Rs = Rs * self.Sbase / self.base_mva
        self.Xs = Xs * self.Sbase / self.base_mva
        self.Xm = Xm * self.Sbase / self.base_mva
        self.Rr = Rr * self.Sbase / self.base_mva
        self.Xr = Xr * self.Sbase / self.base_mva
        self.Rr2 = Rr2 * self.Sbase / self.base_mva
        self.Xr2 = Xr2 * self.Sbase / self.base_mva

        # Calculate internal parameters
        self.X0 = self.Xs + self.Xm
        self.Xp = self.Xs + self.Xr * self.Xm / (self.Xr + self.Xm)
        self.Xpp = self.Xs + self.Xr * self.Xr2 * self.Xm / (
                    self.Xr * self.Xr2 + self.Xm * self.Xr + self.Xm * self.Xr2)
        self.T0p = (self.Xr + self.Xm) / (self.omega_n * self.Rr)
        self.T0pp = (self.Xr2 + (self.Xr * self.Xm) / (self.Xr + self.Xm)) / (self.omega_n * self.Rr2)

        # Motor start signal
        self.start = 0

        # Equivalent Norton impedance for Ybus modification (NOTE: currently not used)
        self.Ym = self.Rs - 1j * self.Xs

        # results
        self.Id = 0
        self.Iq = 0
        self.Vd = 0
        self.Vq = 0
        self.Vt = 0
        self.P = 0
        self.Q = 0
        self.Te = 0
        self.slip = 0
        self.Eqp = 0
        self.Edp = 0
        self.Eqpp = 0
        self.Edpp = 0
        self.omega = 1 - self.slip
        self.Im = 0.0
        self.In = 0.0
        self.Vang = 0.0

    def get_yg(self):
        """
        Get the generator admittance
        :return: shunt admittance
        """
        return 1 / (self.Rr + 1j * self.Xr)

    def initialise(self, vt0, S0):
        """
        Initialise machine signals and states based on load flow voltage and complex power injection
        NOTE: currently only initialised at standstill
        """

        # Initialise signals, states and parameters
        self.Id = 0
        self.Iq = 0
        self.Vd = 0
        self.Vq = 0
        self.Vt = np.abs(vt0)
        self.P = 0
        self.Q = 0
        self.Te = 0
        self.slip = 1
        self.omega = 1 - self.slip

        self.Eqp = 0
        self.Edp = 0
        self.Eqpp = 0
        self.Edpp = 0

        self.check_diffs()

    def calc_tmech(self, s):
        """
        Calculate mechanical load torque (with a quadratic load model)
        """

        Tm = self.a * (1 - s) ** 2

        return Tm

    def calc_currents(self, vt):
        """
        Calculate machine current Injections (in network reference frame)
        """

        if self.start == 1:
            # Calculate terminal voltage in dq reference frame (set to rotate with q-axis)
            self.Vd = -np.abs(vt) * np.sin(np.angle(vt))
            self.Vq = np.abs(vt) * np.cos(np.angle(vt))

            # Calculate Id and Iq (Norton equivalent current injection in dq frame)
            self.Iq = (self.Rs / self.Xpp * (self.Vq - self.Eqpp) - self.Vd + self.Edpp) / (
                        self.Xpp + self.Rs ** 2 / self.Xpp)
            self.Id = (self.Vq - self.Eqpp - self.Rs * self.Iq) / self.Xpp

            # Calculate power output and electrical torque
            self.P = -(self.Vd * self.Id + self.Vq * self.Iq)
            self.Q = -(self.Vq * self.Id - self.Vd * self.Iq)
            self.Te = self.Edpp * self.Id + self.Eqpp * self.Iq

            # Calculate machine current injection (Norton equivalent current injection in network frame)
            self.In = (self.Id + 1j * self.Iq) * np.exp(1j * (-np.pi / 2))
            self.Im = -self.In  # + self.Ym * vt

            # Update signals
            self.Vt = np.abs(vt)
            self.Vang = np.angle(vt)
            self.omega = 1 - self.slip

        else:
            self.Im = 0

        return self.Im

    def solve_step(self, Edp, Eqp, Edpp, Eqpp):
        """
        Solve machine differential equations for the next stage in the integration step
        """

        if self.start == 1:

            # Eq'
            f1 = (-self.omega_n * self.slip * Edp - (
                        Eqp - (self.X0 - self.Xp) * self.Id) / self.T0p) * self.base_mva / self.Sbase
            # k_Eqp = h * f1

            # Ed'
            f2 = (self.omega_n * self.slip * Eqp - (
                        Edp + (self.X0 - self.Xp) * self.Iq) / self.T0p) * self.base_mva / self.Sbase
            # k_Edp = h * f2

            # Eq''
            f3 = f1 + (self.omega_n * self.slip * (Edp - Edpp) + (
                    Eqp - Eqpp + (self.Xp - self.Xpp) * self.Id) / self.T0pp) * self.base_mva / self.Sbase
            # k_Eqpp = h * f3

            # Ed''
            f4 = f2 + (-self.omega_n * self.slip * (Eqp - Eqpp) + (
                    Edp - Edpp - (self.Xp - self.Xpp) * self.Iq) / self.T0pp) * self.base_mva / self.Sbase
            # k_Edpp = h * f4

            # Mechanical equation
            Tm = self.calc_tmech(self.slip)
            f5 = (Tm - self.Te) / (2 * self.H)
            # k_s = h * f5

        else:
            f1 = np.zeros_like(Edp)
            f2 = np.zeros_like(Edp)
            f3 = np.zeros_like(Edp)
            f4 = np.zeros_like(Edp)
            f5 = np.zeros_like(Edp)

        return f1, f2, f3, f4, f5

    def check_diffs(self):
        """
        Check if differential equations are zero (on initialisation)
        """

        # State variables
        # Eqp_0 = self.Eqp
        # Edp_0 = self.Edp
        # self.slip = self.slip
        # 
        # Id = self.Id
        # Iq = self.Iq
        # Te = self.Te
        # 
        # Rs = self.Rs
        # X0 = self.X0
        # T0p = self.T0p
        # Xp = self.Xp

        dEdp = self.omega_n * self.slip * self.Eqp - (self.Edp + (self.X0 - self.Xp) * self.Iq) / self.T0p
        dEqp = -self.omega_n * self.slip * self.Edp - (self.Eqp - (self.X0 - self.Xp) * self.Id) / self.T0p
        ds = self.calc_tmech(1) - self.Te

        if (np.all(np.round(dEdp, 6)) != 0
                or np.all(np.round(dEqp, 6)) != 0
                or np.all(np.round(ds, 6)) != 0):
            print('Warning: differential equations not zero on initialisation...')
            print('dEdp = ' + str(dEdp) + ', dEqp = ' + str(dEqp) + ', ds = ' + str(ds))


def dynamic_simulation(n, Vbus, Sbus, Ybus, Sbase, fBase, t_sim, h, dynamic_devices=list(), bus_indices=list(),
                       callback=None):
    """
    Dynamic transient simulation of a power system
    Args:
        n: number of nodes
        Vbus:
        Ybus:
        Sbase:
        fBase: base frequency i.e. 50Hz
        t_sim:
        h:
        dynamic_devices: objects of each machine
        bus_indices:

    Returns:

    """
    max_err = 1e-3
    max_iter = 20

    # compose dynamic controllers
    '''
    class DynamicModels(Enum):
    NoModel = 0,
    SM4 = 1,
    SM6b = 2,
    VSC = 3,
    EG = 4,
    SAM = 5,
    DAM = 6  
    '''
    sm4_idx = list()
    sm6b_idx = list()
    vsc_idx = list()
    eg_idx = list()
    sam_idx = list()
    dam_idx = list()

    sm4_bus_idx = list()
    sm6b_bus_idx = list()
    vsc_bus_idx = list()
    eg_bus_idx = list()
    sam_bus_idx = list()
    dam_bus_idx = list()

    n_obj = len(dynamic_devices)
    H = np.zeros(n_obj)
    a = np.zeros(n_obj)
    Xm = np.zeros(n_obj)
    Ra = np.zeros(n_obj)
    Rs = np.zeros(n_obj)
    Xs = np.zeros(n_obj)
    Xd = np.zeros(n_obj)
    Xa = np.zeros(n_obj)
    Xdp = np.zeros(n_obj)
    Xdpp = np.zeros(n_obj)
    Xq = np.zeros(n_obj)
    Xqp = np.zeros(n_obj)
    Xqpp = np.zeros(n_obj)
    Td0p = np.zeros(n_obj)
    Tq0p = np.zeros(n_obj)
    Td0pp = np.zeros(n_obj)
    Tq0pp = np.zeros(n_obj)
    base_mva = np.zeros(n_obj)

    Rr = np.zeros(n_obj)
    Rr2 = np.zeros(n_obj)
    Xr = np.zeros(n_obj)
    Xr2 = np.zeros(n_obj)
    speed_volt = np.zeros(n_obj, dtype=bool)

    machine_types = [None] * n_obj

    # extract the parameters from the objects into the arrays
    for k, machine in enumerate(dynamic_devices):

        # store the machine model in a list for later
        machine_types[k] = machine.machine_model

        # store the machine data into the representing vector
        if machine.machine_model == DynamicModels.NoModel:  # no model
            pass

        elif machine.machine_model == DynamicModels.SynchronousGeneratorOrder4:  # fourth order synchronous machine

            H[k] = dynamic_devices[k].H
            Ra[k] = dynamic_devices[k].Ra
            Xd[k] = dynamic_devices[k].Xd
            Xa[k] = dynamic_devices[k].Xa
            Xdp[k] = dynamic_devices[k].Xdp
            Xdpp[k] = dynamic_devices[k].Xdpp
            Xq[k] = dynamic_devices[k].Xq
            Xqp[k] = dynamic_devices[k].Xqp
            Xqpp[k] = dynamic_devices[k].Xqpp
            Td0p[k] = dynamic_devices[k].Td0p
            Tq0p[k] = dynamic_devices[k].Tq0p
            base_mva[k] = dynamic_devices[k].Snom
            speed_volt[k] = dynamic_devices[k].speed_volt
            sm4_idx.append(k)
            sm4_bus_idx.append(bus_indices[k])

        elif machine.machine_model == DynamicModels.SynchronousGeneratorOrder6:  # sixth order synchronous machine

            H[k] = dynamic_devices[k].H
            Ra[k] = dynamic_devices[k].Ra
            Xd[k] = dynamic_devices[k].Xd
            Xdp[k] = dynamic_devices[k].Xdp
            Xdpp[k] = dynamic_devices[k].Xdpp
            Xq[k] = dynamic_devices[k].Xq
            Xqp[k] = dynamic_devices[k].Xqp
            Xqpp[k] = dynamic_devices[k].Xqpp
            Td0p[k] = dynamic_devices[k].Td0p
            Tq0p[k] = dynamic_devices[k].Tq0p
            Td0pp[k] = dynamic_devices[k].Td0pp
            Tq0pp[k] = dynamic_devices[k].Tq0pp
            base_mva[k] = dynamic_devices[k].Snom
            speed_volt[k] = dynamic_devices[k].speed_volt
            sm6b_idx.append(k)
            sm6b_bus_idx.append(bus_indices[k])

        elif machine.machine_model == DynamicModels.VoltageSourceConverter:  # voltage source converter

            # R1, X1, fn
            Ra[k] = dynamic_devices[k].R1
            Xd[k] = dynamic_devices[k].X1
            vsc_idx.append(k)
            vsc_bus_idx.append(bus_indices[k])

        elif machine.machine_model == DynamicModels.ExternalGrid:  # external grid
            # Xdp, H
            H[k] = dynamic_devices[k].H
            Xdp[k] = dynamic_devices[k].Xdp
            eg_idx.append(k)
            eg_bus_idx.append(bus_indices[k])

        elif machine.machine_model == DynamicModels.AsynchronousSingleCageMotor:  # single cage asynchronous motor
            # H, Rr, Xr, Rs, Xs, a, Xm, Sbase, MVA_Rating
            H[k] = dynamic_devices[k].H
            Rr[k] = dynamic_devices[k].Rr
            Xr[k] = dynamic_devices[k].Xr
            Rs[k] = dynamic_devices[k].Rs
            Xs[k] = dynamic_devices[k].Xs
            Xq[k] = dynamic_devices[k].Xq
            a[k] = dynamic_devices[k].a
            Xm[k] = dynamic_devices[k].Xm
            base_mva[k] = dynamic_devices[k].MVA_Rating
            sam_idx.append(k)
            sam_bus_idx.append(bus_indices[k])

        elif machine.machine_model == DynamicModels.AsynchronousDoubleCageMotor:  # double cage asynchronous motor
            # H, Rr, Xr, Rs, Xs, a, Xm, Rr2, Xr2, MVA_Rating, Sbase
            H[k] = dynamic_devices[k].H
            Rr[k] = dynamic_devices[k].Rr
            Xr[k] = dynamic_devices[k].Xr
            Rs[k] = dynamic_devices[k].Rs
            Xs[k] = dynamic_devices[k].Xs
            Rr2[k] = dynamic_devices[k].Rr2
            Xr2[k] = dynamic_devices[k].Xr2
            a[k] = dynamic_devices[k].a
            Xm[k] = dynamic_devices[k].Xm
            base_mva[k] = dynamic_devices[k].MVA_Rating
            dam_idx.append(k)
            dam_bus_idx.append(bus_indices[k])

    # create the controllers
    sm4 = SynchronousMachineOrder4(H=H[sm4_idx],
                                   Ra=Ra[sm4_idx],
                                   Xd=Xd[sm4_idx],
                                   Xdp=Xdp[sm4_idx],
                                   Xdpp=Xdpp[sm4_idx],
                                   Xq=Xq[sm4_idx],
                                   Xqp=Xqp[sm4_idx],
                                   Xqpp=Xqp[sm4_idx],
                                   Td0p=Td0p[sm4_idx],
                                   Tq0p=Tq0p[sm4_idx],
                                   base_mva=base_mva[sm4_idx],
                                   Sbase=Sbase,
                                   bus_idx=sm4_bus_idx,
                                   fn=fBase,
                                   speed_volt=speed_volt[sm4_idx])

    sm6 = SynchronousMachineOrder6SauerPai(H=H[sm6b_idx],
                                           Ra=Ra[sm6b_idx],
                                           Xa=Xa[sm6b_idx],
                                           Xd=Xd[sm6b_idx],
                                           Xdp=Xdp[sm6b_idx],
                                           Xdpp=Xdpp[sm6b_idx],
                                           Xq=Xq[sm6b_idx],
                                           Xqp=Xqp[sm6b_idx],
                                           Xqpp=Xqpp[sm6b_idx],
                                           Td0p=Td0p[sm6b_idx],
                                           Tq0p=Tq0p[sm6b_idx],
                                           Td0pp=Td0pp[sm6b_idx],
                                           Tq0pp=Tq0pp[sm6b_idx],
                                           base_mva=base_mva[sm6b_idx],
                                           Sbase=Sbase,
                                           bus_idx=sm6b_bus_idx,
                                           fn=fBase,
                                           speed_volt=speed_volt[sm6b_idx])

    vsc = VoltageSourceConverterAverage(Rl=Ra[vsc_idx], Xl=Xd[vsc_idx], fn=fBase, bus_idx=vsc_bus_idx)

    exg = ExternalGrid(Xdp=Xdp[eg_idx], H=H[eg_idx], fn=fBase, bus_idx=eg_bus_idx)

    sam = SingleCageAsynchronousMotor(H=H[sam_idx],
                                      Rr=Rr[sam_idx],
                                      Xr=Xr[sam_idx],
                                      Rs=Rs[sam_idx],
                                      Xs=Xs[sam_idx],
                                      a=a[sam_idx],
                                      Xm=Xm[sam_idx],
                                      MVA_Rating=base_mva[sam_idx],
                                      Sbase=Sbase,
                                      bus_idx=sam_bus_idx,
                                      fn=fBase)

    dam = DoubleCageAsynchronousMotor(H=H[dam_idx],
                                      Rr=Rr[dam_idx],
                                      Xr=Xr[dam_idx],
                                      Rs=Rs[dam_idx],
                                      Xs=Xs[dam_idx],
                                      a=a[dam_idx],
                                      Xm=Xm[dam_idx],
                                      Rr2=Rr2[dam_idx],
                                      Xr2=Xr2[dam_idx],
                                      MVA_Rating=base_mva[dam_idx],
                                      Sbase=Sbase,
                                      bus_idx=dam_bus_idx,
                                      fn=fBase)

    # modify Ybus to add the admittances

    Y_shunt = np.zeros(n, dtype=complex)
    load_idx = np.where(Sbus > 0)[0]
    Y_shunt[load_idx] = Sbus[load_idx] / np.power(Vbus[load_idx], 2)  # add loads as admittances

    Y_shunt[sm4.bus_idx] += sm4.get_yg()
    Y_shunt[sm6.bus_idx] += sm6.get_yg()
    Y_shunt[vsc.bus_idx] += vsc.get_yg()
    Y_shunt[exg.bus_idx] += exg.get_yg()
    Y_shunt[sam.bus_idx] += sam.get_yg()
    Y_shunt[dam.bus_idx] += dam.get_yg()

    ib = range(n)
    Ydiag = sparse((Y_shunt, (ib, ib)))

    # factorize the impedance matrix
    Zbus = splu(Ybus + Ydiag)

    # copy the initial voltage
    V = Vbus.copy()
    I = np.zeros(n, dtype=complex)

    # initialize machines
    sm4.initialise(vt0=Vbus[sm4_bus_idx], S0=Sbus[sm4_bus_idx])
    sm6.initialise(vt0=Vbus[sm6b_bus_idx], S0=Sbus[sm6b_bus_idx])
    vsc.initialise(vt0=Vbus[vsc_bus_idx], S0=Sbus[vsc_bus_idx])
    exg.initialise(vt0=Vbus[eg_bus_idx], S0=Sbus[eg_bus_idx])
    sam.initialise(vt0=Vbus[sam_bus_idx], S0=Sbus[sam_bus_idx])
    dam.initialise(vt0=Vbus[dam_bus_idx], S0=Sbus[dam_bus_idx])

    voltages = list()
    omegas = list()

    # iterate
    t = 0.0
    time = list()
    while t < t_sim:

        sm4.solve(h)

        # compute machine currents

        sm4.calc_currents(V, I)

        # solve voltages
        V = Zbus.solve(I)

        voltages.append(V)
        omegas.append(sm4.omega)
        time.append(t)

        t += h

        if callback is not None:
            progress = t / t_sim * 100
            txt = 'Running transient stability t:' + str(t)
            callback(txt, progress)

    res = TransientStabilityResults()
    res.voltage = np.array(voltages)
    res.omegas = np.array(omegas)
    res.time = np.array(time)

    return res
