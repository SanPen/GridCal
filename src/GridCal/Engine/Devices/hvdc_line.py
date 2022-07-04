# GridCal
# Copyright (C) 2022 Santiago Peñate Vera
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


import pandas as pd
import numpy as np
from matplotlib import pyplot as plt

from GridCal.Engine.basic_structures import Logger
from GridCal.Engine.Devices.bus import Bus
from GridCal.Engine.Devices.enumerations import BranchType
from GridCal.Engine.Devices.underground_line import UndergroundLineType

from GridCal.Engine.Devices.editable_device import EditableDevice, DeviceType, GCProp
from GridCal.Engine.Devices.enumerations import HvdcControlType


def firing_angles_to_reactive_limits(P, alphamin, alphamax):
    # minimum reactive power calculated under assumption of no overlap angle
    # i.e. power factor equals to tan(alpha)
    Qmin = P * np.tan(alphamin)

    # maximum reactive power calculated when overlap angle reaches max
    # value (60 deg). I.e.
    #      cos(phi) = 1/2*(cos(alpha)+cos(delta))
    #      Q = P*tan(phi)
    phi = np.arccos(0.5 * (np.cos(alphamax) + np.cos(np.deg2rad(60))))
    Qmax = P * np.tan(phi)
    # if Qmin < 0:
    #     Qmin = -Qmin
    #
    # if Qmax < 0:
    #     Qmax = -Qmax

    return Qmin, Qmax


def getFromAndToPowerAt(Pset, theta_f, theta_t, Vnf, Vnt, v_set_f, v_set_t, Sbase, r1, angle_droop, rate,
                        free: bool, in_pu: bool = False):
    """
    Compute the power and losses
    :param Pset: set power in MW
    :param theta_f: angle from (rad)
    :param theta_t: angle to (rad)
    :param Vnf: nominal voltage from (kV)
    :param Vnt: nominal voltage to (kV)
    :param v_set_f: control voltage from (p.u.)
    :param v_set_t: control voltage to (p.u.)
    :param Sbase: base power MVA
    :param r1: line resistance (ohm)
    :param angle_droop: angle droop control (MW/deg)
    :param free: is free to use the angle droop?
    :param in_pu: return power in per unit? otherwise the power comes in MW
    :return: Pf, Pt, losses (in MW or p.u. depending on `in_pu`)
    """

    if not free:

        # simply copy the set power value
        Pcalc = Pset

    elif free:

        # compute the angular difference in degrees (0.017453292f -> pi/180)
        # theta_f and theta_t are in rad
        # for the control not to be oscillatory, the angle difference must be the opposite (to - from)
        dtheta = np.rad2deg(theta_t - theta_f)

        # compute the desired control power flow
        Pcalc = Pset + angle_droop * dtheta  # this is in MW

        # rate truncation
        if Pcalc > rate:
            Pcalc = rate

        elif Pcalc < -rate:
            Pcalc = -rate

    else:
        Pcalc = 0

    # depending on the value of Pcalc, assign the from and to values
    if Pcalc > 0:
        # from ->  to
        I = Pcalc / (Vnf * v_set_f)  # current in kA
        loss = r1 * I * I  # losses in MW
        Pf = - Pcalc
        Pt = Pcalc - loss

    elif Pcalc < 0:
        # to -> from
        I = Pcalc / (Vnt * v_set_t)  # current in kA
        loss = r1 * I * I  # losses in MW
        Pf = - Pcalc - loss
        Pt = Pcalc  # is negative

    else:
        Pf = 0
        Pt = 0
        loss = 0

    # convert to p.u.
    if in_pu:
        Pf /= Sbase
        Pt /= Sbase
        loss /= Sbase

    return Pf, Pt, loss


class HvdcLine(EditableDevice):
    """
    The **Line** class represents the connections between nodes (i.e.
    :ref:`buses<bus>`) in **GridCal**. A branch is an element (cable, line, capacitor,
    transformer, etc.) with an electrical impedance. The basic **Branch** class
    includes basic electrical attributes for most passive elements, but other device
    types may be passed to the **Branch** constructor to configure it as a specific
    type.

    For example, a transformer may be created with the following code:

    .. code:: ipython3

        from GridCal.Engine.Core.multi_circuit import MultiCircuit
        from GridCal.Engine.Devices import *
        from GridCal.Engine.Devices.types import *

        # Create grid
        grid = MultiCircuit()

        # Create buses
        POI = Bus(name="POI",
                  vnom=100, #kV
                  is_slack=True)
        grid.add_bus(POI)

        B_C3 = Bus(name="B_C3",
                   vnom=10) #kV
        grid.add_bus(B_C3)

        # Create transformer types
        SS = TransformerType(name="SS",
                             hv_nominal_voltage=100, # kV
                             lv_nominal_voltage=10, # kV
                             nominal_power=100, # MVA
                             copper_losses=10000, # kW
                             iron_losses=125, # kW
                             no_load_current=0.5, # %
                             short_circuit_voltage=8) # %
        grid.add_transformer_type(SS)

        # Create transformer
        X_C3 = Branch(bus_from=POI,
                      bus_to=B_C3,
                      name="X_C3",
                      branch_type=BranchType.Transformer,
                      template=SS,
                      )

        # Add transformer to grid
        grid.add_branch(X_C3)

    Refer to the :class:`GridCal.Engine.Devices.branch.TapChanger` class for an example
    using a voltage regulator.

    Arguments:

        **bus_from** (:ref:`Bus`): "From" :ref:`bus<Bus>` object

        **bus_to** (:ref:`Bus`): "To" :ref:`bus<Bus>` object

        **name** (str, "Branch"): Name of the branch

        **r** (float, 1e-20): Branch resistance in per unit

        **x** (float, 1e-20): Branch reactance in per unit

        **g** (float, 1e-20): Branch shunt conductance in per unit

        **b** (float, 1e-20): Branch shunt susceptance in per unit

        **rate** (float, 1.0): Branch rate in MVA

        **tap** (float, 1.0): Branch tap module

        **shift_angle** (int, 0): Tap shift angle in radians

        **active** (bool, True): Is the branch active?

        **tolerance** (float, 0): Tolerance specified for the branch impedance in %

        **mttf** (float, 0.0): Mean time to failure in hours

        **mttr** (float, 0.0): Mean time to recovery in hours

        **r_fault** (float, 0.0): Mid-line fault resistance in per unit (SC only)

        **x_fault** (float, 0.0): Mid-line fault reactance in per unit (SC only)

        **fault_pos** (float, 0.0): Mid-line fault position in per unit (0.0 = `bus_from`, 0.5 = middle, 1.0 = `bus_to`)

        **branch_type** (BranchType, BranchType.Line): Device type enumeration (ex.: :class:`GridCal.Engine.Devices.transformer.TransformerType`)

        **length** (float, 0.0): Length of the branch in km

        **vset** (float, 1.0): Voltage set-point of the voltage controlled bus in per unit

        **temp_base** (float, 20.0): Base temperature at which `r` is measured in °C

        **temp_oper** (float, 20.0): Operating temperature in °C

        **alpha** (float, 0.0033): Thermal constant of the material in °C

        **bus_to_regulated** (bool, False): Is the `bus_to` voltage regulated by this branch?

        **template** (BranchTemplate, BranchTemplate()): Basic branch template
    """

    def __init__(self, bus_from: Bus = None, bus_to: Bus = None, name='HVDC Line', idtag=None, active=True, code='',
                 rate=1.0, Pset=0.0, r=1e-20, loss_factor=0.0, Vset_f=1.0, Vset_t=1.0, length=1.0, mttf=0.0, mttr=0.0,
                 overload_cost=1000.0,   min_firing_angle_f=-1.0, max_firing_angle_f=1.0, min_firing_angle_t=-1.0,
                 max_firing_angle_t=1.0,  active_prof=np.ones(0, dtype=bool), rate_prof=np.zeros(0),
                 Pset_prof=np.zeros(0), Vset_f_prof=np.ones(0), Vset_t_prof=np.ones(0), overload_cost_prof=np.zeros(0),
                 contingency_factor=1.0, control_mode: HvdcControlType=HvdcControlType.type_1_Pset,
                 dispatchable=False, angle_droop=0, angle_droop_prof=np.ones(0), contingency_factor_prof=None):
        """
        HVDC Line model
        :param bus_from: Bus from
        :param bus_to: Bus to
        :param idtag: id tag of the line
        :param name: name of the line
        :param active: Is the line active?
        :param rate: Line rate in MVA
        :param Pset: Active power set point
        :param loss_factor: Losses factor (p.u.)
        :param Vset_f: Voltage set point at the "from" side
        :param Vset_t: Voltage set point at the "to" side
        :param min_firing_angle_f: minimum firing angle at the "from" side
        :param max_firing_angle_f: maximum firing angle at the "from" side
        :param min_firing_angle_t: minimum firing angle at the "to" side
        :param max_firing_angle_t: maximum firing angle at the "to" side
        :param overload_cost: cost of a line overload in EUR/MW
        :param mttf: Mean time to failure in hours
        :param mttr: Mean time to recovery in hours
        :param length: line length in km
        :param active_prof: profile of active states (bool)
        :param rate_prof: Profile of ratings in MVA
        :param Pset_prof: Active power set points profile
        :param Vset_f_prof: Voltage set points at the "from" side profile
        :param Vset_t_prof: Voltage set points at the "to" side profile
        :param overload_cost_prof: Profile of overload costs in EUR/MW
        """

        EditableDevice.__init__(self,
                                name=name,
                                idtag=idtag,
                                code=code,
                                active=active,
                                device_type=DeviceType.HVDCLineDevice,
                                editable_headers={'name': GCProp('', str, 'Name of the line.'),
                                                  'idtag': GCProp('', str, 'Unique ID'),
                                                  'bus_from': GCProp('', DeviceType.BusDevice,
                                                                     'Name of the bus at the "from" side of the line.'),
                                                  'bus_to': GCProp('', DeviceType.BusDevice,
                                                                   'Name of the bus at the "to" side of the line.'),
                                                  'active': GCProp('', bool, 'Is the line active?'),

                                                  'dispatchable': GCProp('', bool, 'Is the line power optimizable?'),

                                                  'rate': GCProp('MVA', float, 'Thermal rating power of the line.'),

                                                  'contingency_factor': GCProp('p.u.', float,
                                                                               'Rating multiplier for contingencies.'),

                                                  'control_mode': GCProp('-', HvdcControlType, 'Control type.'),

                                                  'Pset': GCProp('MW', float, 'Set power flow.'),

                                                  'r': GCProp('Ohm', float, 'line resistance.'),

                                                  'angle_droop': GCProp('MW/deg', float, 'Power/angle rate control'),

                                                  'Vset_f': GCProp('p.u.', float, 'Set voltage at the from side'),
                                                  'Vset_t': GCProp('p.u.', float, 'Set voltage at the to side'),

                                                  'min_firing_angle_f': GCProp('rad', float,
                                                                               'minimum firing angle at the '
                                                                               '"from" side.'),
                                                  'max_firing_angle_f': GCProp('rad', float,
                                                                               'maximum firing angle at the '
                                                                               '"from" side.'),
                                                  'min_firing_angle_t': GCProp('rad', float,
                                                                               'minimum firing angle at the '
                                                                               '"to" side.'),
                                                  'max_firing_angle_t': GCProp('rad', float,
                                                                               'maximum firing angle at the '
                                                                               '"to" side.'),

                                                  'mttf': GCProp('h', float, 'Mean time to failure, '
                                                                             'used in reliability studies.'),
                                                  'mttr': GCProp('h', float, 'Mean time to recovery, '
                                                                             'used in reliability studies.'),

                                                  'length': GCProp('km', float, 'Length of the branch '
                                                                                '(not used for calculation)'),

                                                  'overload_cost': GCProp('e/MWh', float,
                                                                          'Cost of overloads. Used in OPF.'),
                                                  },
                                non_editable_attributes=['bus_from', 'bus_to', 'idtag'],
                                properties_with_profile={'active': 'active_prof',
                                                         'rate': 'rate_prof',
                                                         'contingency_factor': 'contingency_factor_prof',
                                                         'Pset': 'Pset_prof',
                                                         'Vset_f': 'Vset_f_prof',
                                                         'Vset_t': 'Vset_t_prof',
                                                         'angle_droop': 'angle_droop_prof',
                                                         'overload_cost': 'overload_cost_prof'})

        # connectivity
        self.bus_from = bus_from
        self.bus_to = bus_to

        # List of measurements
        self.measurements = list()

        # line length in km
        self.length = length

        self.dispatchable = dispatchable

        self.Pset = Pset

        self.r = r

        self.angle_droop = angle_droop

        self.loss_factor = loss_factor

        self.mttf = mttf

        self.mttr = mttr

        self.overload_cost = overload_cost

        self.Vset_f = Vset_f
        self.Vset_t = Vset_t

        # converter / inverter firing angles
        self.min_firing_angle_f = min_firing_angle_f
        self.max_firing_angle_f = max_firing_angle_f
        self.min_firing_angle_t = min_firing_angle_t
        self.max_firing_angle_t = max_firing_angle_t

        self.Qmin_f, self.Qmax_f = firing_angles_to_reactive_limits(self.Pset,
                                                                    self.min_firing_angle_f,
                                                                    self.max_firing_angle_f)

        self.Qmin_t, self.Qmax_t = firing_angles_to_reactive_limits(self.Pset,
                                                                    self.min_firing_angle_t,
                                                                    self.max_firing_angle_t)

        self.overload_cost_prof = overload_cost_prof

        self.control_mode = control_mode

        self.Pset_prof = Pset_prof
        self.active_prof = active_prof
        self.Vset_f_prof = Vset_f_prof
        self.Vset_t_prof = Vset_t_prof

        self.angle_droop_prof = angle_droop_prof

        # branch rating in MVA
        self.rate = rate
        self.contingency_factor = contingency_factor
        self.rate_prof = rate_prof
        self.contingency_factor_prof = contingency_factor_prof

    def get_from_and_to_power(self, theta_f, theta_t, Sbase, in_pu=False):
        """
        Get the power set at both ends accounting for meaningful losses
        :return: power from, power to
        """
        if self.active:
            Pf, Pt, losses = getFromAndToPowerAt(Pset=self.Pset,
                                                 theta_f=theta_f,
                                                 theta_t=theta_t,
                                                 Vnf=self.bus_from.Vnom,
                                                 Vnt=self.bus_to.Vnom,
                                                 v_set_f=self.Vset_f,
                                                 v_set_t=self.Vset_t,
                                                 Sbase=Sbase,
                                                 r1=self.r,
                                                 angle_droop=self.angle_droop,
                                                 rate=self.rate,
                                                 free=self.control_mode == HvdcControlType.type_0_free,
                                                 in_pu=in_pu)

            return Pf, Pt, losses
        else:
            return 0, 0, 0

    def get_from_and_to_power_at(self, t, theta_f, theta_t, Sbase, in_pu=False):
        """
        Get the power set at both ends accounting for meaningful losses
        :return: power from, power to
        """
        if self.active_prof[t]:
            Pf, Pt, losses = getFromAndToPowerAt(Pset=self.Pset_prof[t],
                                                 theta_f=theta_f,
                                                 theta_t=theta_t,
                                                 Vnf=self.bus_from.Vnom,
                                                 Vnt=self.bus_to.Vnom,
                                                 v_set_f=self.Vset_f_prof[t],
                                                 v_set_t=self.Vset_t_prof[t],
                                                 Sbase=Sbase,
                                                 r1=self.r,
                                                 angle_droop=self.angle_droop,
                                                 rate=self.rate_prof[t],
                                                 free=self.control_mode == HvdcControlType.type_0_free,
                                                 in_pu=in_pu)

            return Pf, Pt, losses
        else:
            return 0, 0, 0

    def get_from_and_to_power_profiles(self, theta_f, theta_t, Sbase):
        """
        Get the power set at both ends accounting for meaningful losses
        :return: power from, power to
        """
        # A = (self.Pset_prof > 0).astype(int)
        # B = 1 - A
        #
        # Pf = - self.Pset_prof * A + self.Pset_prof * (1 - self.loss_factor) * B
        # Pt = self.Pset_prof * A * (1 - self.loss_factor) - self.Pset_prof * B

        Pf = np.zeros_like(self.Pset_prof)
        Pt = np.zeros_like(self.Pset_prof)
        losses = np.zeros_like(self.Pset_prof)
        for t in range(len(self.Pset_prof)):
            Pf[t], Pt[t], losses[t] = getFromAndToPowerAt(Pset=self.Pset_prof[t],
                                                          theta_f=theta_f[t],
                                                          theta_t=theta_t[t],
                                                          Vnf=self.bus_from.Vnom,
                                                          Vnt=self.bus_to.Vnom,
                                                          v_set_f=self.Vset_f_prof[t],
                                                          v_set_t=self.Vset_t_prof[t],
                                                          Sbase=Sbase,
                                                          r1=self.r,
                                                          angle_droop=self.angle_droop,
                                                          rate=self.rate_prof[t],
                                                          free=self.control_mode == HvdcControlType.type_0_free)

        return Pf, Pt

    def copy(self, bus_dict=None):
        """
        Returns a copy of the branch
        @return: A new  with the same content as this
        """

        if bus_dict is None:
            f = self.bus_from
            t = self.bus_to
        else:
            f = bus_dict[self.bus_from]
            t = bus_dict[self.bus_to]

        '''
        bus_from: Bus = None, 
        bus_to: Bus = None, 
        name='HVDC Line', 
        idtag=None, 
        active=True,
        rate=1.0, Pfset=0.0, 
        loss_factor=0.0, 
        Vset_f=1.0, 
        Vset_t=1.0, 
        length=1.0, 
        mttf=0.0, 
        mttr=0.0, 
        overload_cost=1000.0,   
        min_firing_angle_f=-1.0, 
        max_firing_angle_f=1.0, 
        min_firing_angle_t=-1.0, 
        max_firing_angle_t=1.0, 
        active_prof=np.ones(0, dtype=bool), 
        rate_prof=np.zeros(0), 
        Pset_prof=np.zeros(0), 
        Vset_f_prof=np.ones(0), 
        Vset_t_prof=np.ones(0), 
        overload_cost_prof=np.zeros(0)
        '''

        b = HvdcLine(bus_from=f,
                     bus_to=t,
                     name=self.name,
                     idtag=self.idtag,
                     rate=self.rate,
                     active=self.active,
                     loss_factor=self.loss_factor,
                     Vset_f=self.Vset_f,
                     Vset_t=self.Vset_t,
                     length=self.length,
                     mttf=self.mttf,
                     mttr=self.mttr,
                     overload_cost=self.overload_cost,
                     min_firing_angle_f=self.min_firing_angle_f,
                     max_firing_angle_f=self.max_firing_angle_f,
                     min_firing_angle_t=self.min_firing_angle_t,
                     max_firing_angle_t=self.max_firing_angle_t,
                     active_prof=self.active_prof,
                     rate_prof=self.rate_prof,
                     Pset_prof=self.Pset_prof,
                     Vset_f_prof=self.Vset_f_prof,
                     Vset_t_prof=self.Vset_t_prof,
                     overload_cost_prof=self.overload_cost_prof)

        b.measurements = self.measurements

        b.active_prof = self.active_prof.copy()

        return b

    def get_save_data(self):
        """
        Return the data that matches the edit_headers
        :return:
        """
        data = list()
        for name, properties in self.editable_headers.items():
            obj = getattr(self, name)

            if properties.tpe == DeviceType.BusDevice:
                obj = obj.idtag

            elif properties.tpe not in [str, float, int, bool]:
                obj = str(obj)

            data.append(obj)
        return data

    def get_properties_dict(self, version=3):
        """
        Get json dictionary
        :return:
        """
        if version == 2:
            d = {'id': self.idtag,
                 'type': 'hvdc',
                 'phases': 'ps',
                 'name': self.name,
                 'name_code': self.code,
                 'bus_from': self.bus_from.idtag,
                 'bus_to': self.bus_to.idtag,
                 'active': self.active,
                 'rate': self.rate,
                 'control_mode': self.control_mode.value,
                 'r': self.r,
                 'length': self.length,
                 'loss_factor': self.loss_factor,
                 'angle_droop': self.angle_droop,
                 'vset_from': self.Vset_f,
                 'vset_to': self.Vset_t,
                 'Pset': self.Pset,
                 'min_firing_angle_f': self.min_firing_angle_f,
                 'max_firing_angle_f': self.max_firing_angle_f,
                 'min_firing_angle_t': self.min_firing_angle_t,
                 'max_firing_angle_t': self.max_firing_angle_t,
                 'overload_cost': self.overload_cost,
                 'base_temperature': 20,
                 'operational_temperature': 20,
                 'alpha': 0.00330,
                 'locations': []
                 }
        elif version == 3:
            d = {'id': self.idtag,
                 'type': 'hvdc',
                 'phases': 'ps',
                 'name': self.name,
                 'name_code': self.code,
                 'bus_from': self.bus_from.idtag,
                 'bus_to': self.bus_to.idtag,
                 'active': self.active,
                 'rate': self.rate,
                 'control_mode': self.control_mode.value,
                 'contingency_factor1': self.contingency_factor,
                 'contingency_factor2': self.contingency_factor,
                 'contingency_factor3': self.contingency_factor,
                 'r': self.r,
                 'length': self.length,
                 'loss_factor': self.loss_factor,
                 'angle_droop': self.angle_droop,
                 'vset_from': self.Vset_f,
                 'vset_to': self.Vset_t,
                 'Pset': self.Pset,
                 'min_firing_angle_f': self.min_firing_angle_f,
                 'max_firing_angle_f': self.max_firing_angle_f,
                 'min_firing_angle_t': self.min_firing_angle_t,
                 'max_firing_angle_t': self.max_firing_angle_t,
                 'overload_cost': self.overload_cost,
                 'base_temperature': 20,
                 'operational_temperature': 20,
                 'alpha': 0.00330,
                 'locations': []
                 }
        else:
            d = dict()

        return d

    def get_profiles_dict(self, version=3):
        """

        :return:
        """

        if self.active_prof is not None:
            active_prof = self.active_prof.tolist()
            rate_prof = self.rate_prof.tolist()
            pset_prof = self.Pset_prof.tolist()
            vset_prof_f = self.Vset_f_prof.tolist()
            vset_prof_t = self.Vset_t_prof.tolist()
            cost_prof = self.overload_cost_prof.tolist()
        else:
            active_prof = list()
            rate_prof = list()
            pset_prof = list()
            cost_prof = list()
            vset_prof_f = list()
            vset_prof_t = list()

        return {'id': self.idtag,
                'active': active_prof,
                'rate': rate_prof,
                'Pset': pset_prof,
                'vset_from': vset_prof_f,
                'vset_to': vset_prof_t,
                'overload_cost': cost_prof}

    def get_units_dict(self, version=3):
        """
        Get units of the values
        """
        return {'rate': 'MW',
                'length': 'km',
                'loss_factor': '%',
                'vset_f': 'p.u.',
                'vset_t': 'p.u.',
                'pset': 'MW',
                'min_firing_angle_f': 'radians',
                'max_firing_angle_f': 'radians',
                'min_firing_angle_t': 'radians',
                'max_firing_angle_t': 'radians',
                'overload_cost': '€/MWh'}

    def plot_profiles(self, time_series=None, my_index=0, show_fig=True):
        """
        Plot the time series results of this object
        :param time_series: TimeSeries Instance
        :param my_index: index of this object in the simulation
        :param show_fig: Show the figure?
        """

        if time_series is not None:
            fig = plt.figure(figsize=(12, 8))

            ax_1 = fig.add_subplot(211)
            ax_2 = fig.add_subplot(212, sharex=ax_1)

            x = time_series.results.time

            # loading
            y = self.Pset_prof / (self.rate_prof + 1e-9) * 100.0
            df = pd.DataFrame(data=y, index=x, columns=[self.name])
            ax_1.set_title('Loading', fontsize=14)
            ax_1.set_ylabel('Loading [%]', fontsize=11)
            df.plot(ax=ax_1)

            # losses
            y = self.Pset_prof * self.loss_factor
            df = pd.DataFrame(data=y, index=x, columns=[self.name])
            ax_2.set_title('Losses', fontsize=14)
            ax_2.set_ylabel('Losses [MVA]', fontsize=11)
            df.plot(ax=ax_2)

            plt.legend()
            fig.suptitle(self.name, fontsize=20)

        if show_fig:
            plt.show()

    def get_coordinates(self):
        """
        Get the branch defining coordinates
        """
        return [self.bus_from.get_coordinates(), self.bus_to.get_coordinates()]
