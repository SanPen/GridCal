# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
import numpy as np

from VeraGridEngine.DataStructures.numerical_circuit import NumericalCircuit
from VeraGridEngine.DataStructures.generator_data import GeneratorData
from VeraGridEngine.basic_structures import CxVec, IntVec, Vec, BoolVec
from VeraGridEngine.enumerations import (BusMode, GeneratorControlMode, ShuntConnectionType, GeneratorType,
                                         ShuntControlMode)
from VeraGridEngine.Simulations.PowerFlow.NumericalMethods.common_functions import fortescue_012_to_abc
from VeraGridEngine.Simulations.PowerFlow.NumericalMethods.static_generator_droop import StaticGeneratorDroop


def generator_sequence_admittance(data: GeneratorData, members: IntVec) -> np.ndarray:
    """Build the passive sequence response shared by generators and batteries.

    :param data: Compiled generator or battery data, on the system base.
    :param members: Active device indices to combine.
    :return: ABC admittance with no passive positive-sequence branch.
    """
    y0: complex = 0j
    y2: complex = 0j
    member: int
    for member in members:
        connection: int = data.conn[member]
        if connection == ShuntConnectionType.GroundedStar.idx():
            z0: complex = complex(data.r0[member], data.x0[member])
            if not np.isfinite(z0) or abs(z0) < 1e-12:
                raise ValueError('U1 power-flow Z0 must be finite and nonzero for a grounded generator: '
                                 + str(data.names[member])
                                 + '. Check R0/X0; for DGS imports, export r0 and x0 from PowerFactory.')
            else:
                y0 += 1.0 / z0
        elif connection in (ShuntConnectionType.FloatingStar.idx(), ShuntConnectionType.Delta.idx()):
            pass
        else:
            raise ValueError('U1 power-flow control does not support an explicit neutral connection: '
                             + str(data.names[member]))
        z2: complex = complex(data.r2[member], data.x2[member])
        if not np.isfinite(z2) or abs(z2) < 1e-12:
            raise ValueError('U1 power-flow Z2 must be finite and nonzero: '
                             + str(data.names[member])
                             + '. Check R2/X2; for DGS imports, export r2 and x2 from PowerFactory.')
        else:
            y2 += 1.0 / z2
    # A blocked zero sequence is Y0=0, never Z0=0.
    return fortescue_012_to_abc(y0, 0j, y2)


def sequence_source_currents(voltage: np.ndarray, power: CxVec,
                             admittance: np.ndarray, rotation: CxVec,
                             total_power: bool) -> np.ndarray:
    """Evaluate an I1 source with the passive I0/I2 response.

    :param voltage: ABC terminal voltages, one row per source.
    :param power: Source power injections in system pu.
    :param admittance: Passive ABC response, one matrix per source.
    :param rotation: Positive-sequence ABC rotation.
    :param total_power: Compensate passive absorption for the existing PV terminal-power model.
    :return: ABC current injections in system pu.
    """
    v1: CxVec = voltage @ rotation.conj() / 3.0
    passive_current: np.ndarray = -np.einsum('nij,nj->ni', admittance, voltage)
    if total_power:
        power = power - np.sum(voltage * passive_current.conj(), axis=1) / 3.0
    else:
        # Fixed PQ follows the existing StaticGenerator/PF constq sequence convention.
        pass
    i1: CxVec = np.conj(power / v1)
    return i1[:, None] * rotation + passive_current


class PositiveSequenceControl:
    """Local U1 control for generators and continuous shunts, preserving their connections."""

    __slots__ = ('bus_idx', 'phases', 'regular_idx', 'p', 'q', 'vset', 'qmin', 'qmax',
                 'limited', 'qbound', 'rotation', 'sbase', 'yabc', 'static_droop', 'droop_phases',
                 'static_phases', 'static_power', 'generator_share', 'generator_offset',
                 'shunt_slope', 'shunt_offset', 'battery_phases', 'battery_power', 'battery_yabc')

    def __init__(self, nc: NumericalCircuit, bus_lookup: IntVec) -> None:
        """Group active U1 regulators on each non-reference bus.

        :param nc: Compiled island, with powers in MW/MVAr.
        :param bus_lookup: Mapping from full NABC slots to retained voltage unknowns.
        """
        asynchronous: BoolVec = nc.generator_data.active.astype(bool) & (
            nc.generator_data.tpe_int == GeneratorType.Asynchronous.idx())
        if np.any(asynchronous & (nc.generator_data.control_mode_int != GeneratorControlMode.Q.idx())):
            raise ValueError('Asynchronous generators require Q control mode in ABC; '
                             'their reactive power is calculated from the equivalent circuit.')
        else:
            pass
        pv: BoolVec = nc.generator_data.active.astype(bool) & (
            nc.generator_data.control_mode_int == GeneratorControlMode.V.idx())
        selected: BoolVec = pv & (
            nc.bus_data.bus_types[nc.generator_data.bus_idx] != BusMode.Slack_tpe.value)
        battery_selected: BoolVec = nc.battery_data.active.astype(bool) & (
            nc.battery_data.control_mode_int == GeneratorControlMode.V.idx()) & (
            nc.bus_data.bus_types[nc.battery_data.bus_idx] != BusMode.Slack_tpe.value)
        shunts: BoolVec = nc.shunt_data.active & (
            nc.shunt_data.control_mode_int == ShuntControlMode.Continuous.idx()) & (
            nc.bus_data.bus_types[nc.shunt_data.bus_idx] != BusMode.Slack_tpe.value)
        self.bus_idx: IntVec = np.union1d(np.union1d(nc.generator_data.bus_idx[selected],
            nc.battery_data.bus_idx[battery_selected]), nc.shunt_data.bus_idx[shunts])
        self.phases: np.ndarray = bus_lookup[4 * self.bus_idx[:, None] + np.array((1, 2, 3))]
        self.regular_idx: IntVec = np.flatnonzero(nc.generator_data.active.astype(bool) & ~selected)
        count: int = len(self.bus_idx)
        self.p: Vec = np.zeros(count)
        self.q: Vec = np.zeros(count)
        self.vset: Vec = np.ones(count)
        self.qmin: Vec = np.zeros(count)
        self.qmax: Vec = np.zeros(count)
        self.limited: BoolVec = np.zeros(count, dtype=bool)
        self.qbound: Vec = np.zeros(count)
        self.rotation: CxVec = np.exp(-2j * np.pi / 3 * np.arange(3))
        self.sbase: float = nc.Sbase
        # Fixed-Q storage uses the same sequence source without adding control unknowns.
        battery_idx: IntVec = np.flatnonzero(nc.battery_data.active.astype(bool) & (
            nc.battery_data.control_mode_int == GeneratorControlMode.Q.idx()))
        self.battery_phases: np.ndarray = bus_lookup[
            4 * nc.battery_data.bus_idx[battery_idx, None] + np.array((1, 2, 3))]
        self.battery_power: CxVec = (nc.battery_data.p[battery_idx]
                                     + 1j * nc.battery_data.q[battery_idx]) / nc.Sbase
        self.battery_yabc: np.ndarray = np.zeros((len(battery_idx), 3, 3), dtype=complex)
        if np.any(self.battery_phases < 0):
            raise ValueError('Battery sequence model requires all three terminal phases.')
        elif np.any(nc.battery_data.active.astype(bool) & ~np.isin(nc.battery_data.control_mode_int,
                (GeneratorControlMode.Q.idx(), GeneratorControlMode.V.idx()))):
            raise ValueError('Battery ABC power flow supports fixed Q or positive-sequence voltage control.')
        else:
            pass
        index: int
        member: int
        for index, member in enumerate(battery_idx):
            self.battery_yabc[index] = generator_sequence_admittance(nc.battery_data, np.array((member,)))
        self.yabc: np.ndarray = np.zeros((count, 3, 3), dtype=complex)
        self.generator_share: Vec = np.ones(count)
        self.generator_offset: Vec = np.zeros(count)
        self.shunt_slope: np.ndarray = np.zeros((count, 3, 3), dtype=complex)
        self.shunt_offset: np.ndarray = np.zeros((count, 3, 3), dtype=complex)
        self.static_droop: StaticGeneratorDroop = StaticGeneratorDroop(nc)
        static_idx: IntVec = np.flatnonzero(nc.load_data.active & nc.load_data.is_positive_sequence
                                          & (nc.load_data.S != 0j))
        self.static_phases: np.ndarray = bus_lookup[
            4 * nc.load_data.bus_idx[static_idx, None] + np.array((1, 2, 3))]
        self.static_power: CxVec = -nc.load_data.S[static_idx] / nc.Sbase
        if np.any(self.static_phases < 0):
            raise ValueError('Static generator sequence model requires all three terminal phases.')
        else:
            pass
        self.droop_phases: np.ndarray = bus_lookup[
            4 * self.static_droop.bus_idx[:, None] + np.array((1, 2, 3))]
        if np.any(self.droop_phases < 0):
            raise ValueError('Static generator Q-V droop requires all three terminal phases.')
        else:
            pass

        # Colocated regulators share one voltage constraint and aggregate Q capability.
        index: int
        bus: int
        for index, bus in enumerate(self.bus_idx):
            members: IntVec = np.flatnonzero(selected & (nc.generator_data.bus_idx == bus))
            battery_members: IntVec = np.flatnonzero(battery_selected & (nc.battery_data.bus_idx == bus))
            shunt_members: IntVec = np.flatnonzero(shunts & (nc.shunt_data.bus_idx == bus))
            if np.any(self.phases[index] < 0):
                raise ValueError('Positive-sequence voltage control requires a local ABC bus.')
            elif len(members):
                self.vset[index] = nc.generator_data.v[members[0]]
            elif len(battery_members):
                self.vset[index] = nc.battery_data.v[battery_members[0]]
            else:
                self.vset[index] = nc.shunt_data.vset[shunt_members[0]]
            data: GeneratorData
            indices: IntVec
            for data, indices in ((nc.generator_data, members), (nc.battery_data, battery_members)):
                remote: IntVec = data.controllable_bus_idx[indices]
                if np.any((remote >= 0) & (remote != bus)):
                    raise ValueError('Positive-sequence voltage control requires a local ABC bus.')
                elif not np.allclose(data.v[indices], self.vset[index], rtol=0.0, atol=1e-8):
                    raise ValueError('Positive-sequence regulators on the same bus need the same voltage setpoint.')
                else:
                    self.p[index] += np.sum(data.p[indices]) / nc.Sbase
                    self.qmin[index] += np.sum(data.qmin[indices]) / nc.Sbase
                    self.qmax[index] += np.sum(data.qmax[indices]) / nc.Sbase
                    self.yabc[index] += generator_sequence_admittance(data, indices)

            # One shared U1 constraint avoids duplicate equations for colocated units.
            # Share the group variable over their available Q / nominal-B ranges.
            if len(shunt_members):
                remote = nc.shunt_data.controllable_bus_idx[shunt_members]
                if np.any((remote >= 0) & (remote != bus)):
                    raise ValueError('Continuous shunt U1 control requires a local ABC bus.')
                elif not np.allclose(nc.shunt_data.vset[shunt_members], self.vset[index], rtol=0.0, atol=1e-8):
                    raise ValueError('Positive-sequence regulators on the same bus need the same voltage setpoint.')
                elif (not np.all(np.isfinite(nc.shunt_data.qmin[shunt_members]))
                      or not np.all(np.isfinite(nc.shunt_data.qmax[shunt_members]))
                      or np.any(nc.shunt_data.qmin[shunt_members] > nc.shunt_data.qmax[shunt_members])):
                    raise ValueError('Continuous shunt U1 control requires finite, ordered limits.')
                else:
                    pass
                generator_min: float = self.qmin[index]
                generator_range: float = self.qmax[index] - generator_min
                self.qmin[index] += np.sum(nc.shunt_data.qmin[shunt_members]) / nc.Sbase
                self.qmax[index] += np.sum(nc.shunt_data.qmax[shunt_members]) / nc.Sbase
                span: float = self.qmax[index] - self.qmin[index]
                if span < 0.0 or not np.isfinite(span):
                    raise ValueError('Continuous shunt U1 control requires finite, ordered limits.')
                elif span == 0.0:
                    self.limited[index] = True
                    self.qbound[index] = self.qmin[index]
                    self.generator_share[index] = 0.0
                else:
                    self.generator_share[index] = generator_range / span
                self.generator_offset[index] = generator_min - self.qmin[index] * self.generator_share[index]
                for member in shunt_members:
                    connection: int = nc.shunt_data.conn[member]
                    if connection == ShuntConnectionType.GroundedStar.idx():
                        pattern: np.ndarray = np.eye(3, dtype=complex)
                    elif connection in (ShuntConnectionType.Delta.idx(), ShuntConnectionType.FloatingStar.idx()):
                        pattern = fortescue_012_to_abc(0j, 1+0j, 1+0j)
                    else:
                        raise ValueError('Continuous shunt U1 control does not support an explicit neutral: '
                                         + str(nc.shunt_data.names[member]))
                    share: float = ((nc.shunt_data.qmax[member] - nc.shunt_data.qmin[member]) / nc.Sbase / span
                                    if span > 0.0 else 0.0)
                    self.shunt_slope[index] += share * pattern
                    self.shunt_offset[index] += (nc.shunt_data.qmin[member] / nc.Sbase
                                                 - self.qmin[index] * share) * pattern
            else:
                pass

    def add_currents(self, currents: CxVec, voltage: CxVec, q: Vec) -> None:
        """Add voltage-controlled and fixed-power positive-sequence sources.

        :param currents: Existing generator injections, modified in place (MW / pu voltage).
        :param voltage: Retained phase voltages in pu.
        :param q: Group Q / nominal shunt susceptance, in system pu.
        """
        generator_q: Vec = self.generator_offset + self.generator_share * q
        currents[self.phases] += sequence_source_currents(voltage[self.phases], self.p + 1j * generator_q,
            self.yabc, self.rotation, total_power=True) * self.sbase / 3.0
        np.add.at(currents, self.battery_phases,
            sequence_source_currents(voltage[self.battery_phases], self.battery_power,
                self.battery_yabc, self.rotation, total_power=False) * self.sbase / 3.0)
        # A shunt changes one common B, rather than injecting only positive-sequence current.
        # Its connection therefore retains the physical negative/zero-sequence response.
        shunt_admittance: np.ndarray = self.shunt_offset + q[:, None, None] * self.shunt_slope
        currents[self.phases] -= (1j * np.einsum('nij,nj->ni', shunt_admittance, voltage[self.phases])
                                  * self.sbase / 3.0)
        # Reuse the same U1 projection and ABC rotation for controlled static injections.
        # Their Q is an explicit function of U1, so no additional Newton unknown is needed.
        droop_v1: CxVec = voltage[self.droop_phases] @ self.rotation.conj() / 3.0
        droop_i1: CxVec = np.conj(self.static_droop.power(droop_v1) / droop_v1)
        np.add.at(currents, self.droop_phases,
                  droop_i1[:, None] * self.rotation * self.sbase / 3.0)
        # Fixed-power sequence injections use the same U1 projection. Their passive
        # I0/I2 response is already compiled into Ybus, so do not add it here again.
        static_v1: CxVec = voltage[self.static_phases] @ self.rotation.conj() / 3.0
        static_i1: CxVec = np.conj(self.static_power / static_v1)
        np.add.at(currents, self.static_phases,
                  static_i1[:, None] * self.rotation * self.sbase / 3.0)

    def residual(self, voltage: CxVec, q: Vec) -> Vec:
        """Return U1 constraints, or fixed Q constraints after a capability limit.

        :param voltage: Retained phase voltages in pu.
        :param q: Group reactive variable in system pu; shunt contribution is nominal at 1 pu.
        :return: One residual per regulated bus.
        """
        v1: CxVec = voltage[self.phases] @ self.rotation.conj() / 3.0
        return np.where(self.limited, q - self.qbound, np.abs(v1) - self.vset)

    def enforce_limits(self) -> bool:
        """Latch violated Q/B limits, following the existing one-way PV-to-PQ policy.

        :return: Whether any voltage constraint changed to fixed Q.
        """
        violated: BoolVec = ~self.limited & ((self.q < self.qmin) | (self.q > self.qmax))
        self.qbound[violated] = np.clip(self.q, self.qmin, self.qmax)[violated]
        self.limited |= violated
        return bool(np.any(violated))
