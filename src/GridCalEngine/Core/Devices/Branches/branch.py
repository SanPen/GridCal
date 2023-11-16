# GridCal
# Copyright (C) 2015 - 2023 Santiago Peñate Vera
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

import uuid
import pandas as pd
import numpy as np
from matplotlib import pyplot as plt
from enum import Enum
from GridCalEngine.Core.Devices.Substation.bus import Bus
from GridCalEngine.enumerations import BuildStatus
from GridCalEngine.Core.Devices.Branches.templates.parent_branch import ParentBranch
from GridCalEngine.Core.Devices.Branches.tap_changer import TapChanger
from GridCalEngine.Core.Devices.Branches.transformer import Transformer2W
from GridCalEngine.Core.Devices.Branches.line import Line

from GridCalEngine.Core.Devices.editable_device import DeviceType

# Global sqrt of 3 (bad practice?)
SQRT3 = np.sqrt(3.0)


class BranchType(Enum):
    Branch = 'branch'
    Line = 'line'
    DCLine = 'DC-line'
    VSC = 'VSC'
    UPFC = 'UPFC'
    Transformer = 'transformer'
    Reactance = 'reactance'
    Switch = 'switch'
    Winding = 'Winding'
    BranchTemplate = 'BranchTemplate'

    def __str__(self):
        return self.value

    def __repr__(self):
        return str(self)

    @staticmethod
    def argparse(s):
        try:
            return BranchType[s]
        except KeyError:
            return s

    @classmethod
    def list(cls):
        return list(map(lambda c: c.value, cls))



class BranchTemplate:
    """
    This is the template for a branch
    This class only exists for legacy reasons
    """

    def __init__(self, name='BranchTemplate', tpe=BranchType.Branch) -> None:
        self.idtag = uuid.uuid4().hex

        self.name = name

        self.tpe = tpe

        self.device_type = DeviceType.BranchTypeDevice

        self.edit_headers = []
        self.units = []
        self.non_editable_indices = []
        self.edit_types = {}

    def __str__(self):
        return self.name

    def get_save_data(self):
        """

        :return:
        """
        dta = list()
        for p in self.edit_headers:
            dta.append(getattr(self, p))
        return dta


class Branch(ParentBranch):

    def __init__(self, bus_from: Bus = None, bus_to: Bus = None, name='Branch', idtag=None, r=1e-20, x=1e-20, g=1e-20,
                 b=1e-20,
                 rate=1.0, tap=1.0, shift_angle=0, active=True, tolerance=0, cost=0.0,
                 mttf=0, mttr=0, r_fault=0.0, x_fault=0.0, fault_pos=0.5,
                 branch_type: BranchType = BranchType.Line, length=1, vset=1.0,
                 temp_base=20, temp_oper=20, alpha=0.00330,
                 bus_to_regulated=False, template=BranchTemplate(), ):
        """
        This class exists for legacy reasons, use the Line or Transformer2w classes instead! *
        The **Branch** class represents the connections between nodes (i.e.
        :ref:`buses<bus>`) in **GridCal**. A branch is an element (cable, line, capacitor,
        transformer, etc.) with an electrical impedance. The basic **Branch** class
        includes basic electrical attributes for most passive elements, but other device
        types may be passed to the **Branch** constructor to configure it as a specific
        type.
        :param bus_from: "From" :ref:`bus<Bus>` object
        :param bus_to: "To" :ref:`bus<Bus>` object
        :param name: Name of the branch
        :param idtag: UUID code
        :param r: Branch resistance in per unit
        :param x: Branch reactance in per unit
        :param g: Branch shunt conductance in per unit
        :param b: Branch shunt susceptance in per unit
        :param rate: Branch rate in MVA
        :param tap: Branch tap module
        :param shift_angle: Tap shift angle in radians
        :param active: Is the branch active?
        :param tolerance: Tolerance specified for the branch impedance in %
        :param cost:
        :param mttf: Mean time to failure in hours
        :param mttr: Mean time to recovery in hours
        :param r_fault: Mid-line fault resistance in per unit (SC only)
        :param x_fault: Mid-line fault reactance in per unit (SC only)
        :param fault_pos: Mid-line fault position in per unit (0.0 = `bus_from`, 0.5 = middle, 1.0 = `bus_to`)
        :param branch_type: Device type enumeration (ex.: :class:`GridCalEngine.Devices.transformer.TransformerType`)
        :param length: Length of the branch in km
        :param vset: Voltage set-point of the voltage controlled bus in per unit
        :param temp_base: Base temperature at which `r` is measured in °C
        :param temp_oper: Operating temperature in °C
        :param alpha: Thermal constant of the material in °C
        :param bus_to_regulated:  Is the `bus_to` voltage regulated by this branch?
        :param template: Basic branch template
        """
        ParentBranch.__init__(self,
                              name=name,
                              idtag=idtag,
                              code="",
                              bus_from=bus_from,
                              bus_to=bus_to,
                              cn_from=None,
                              cn_to=None,
                              active=active,
                              active_prof=None,
                              rate=rate,
                              rate_prof=None,
                              contingency_factor=1.0,
                              contingency_factor_prof=None,
                              contingency_enabled=True,
                              monitor_loading=True,
                              mttf=mttf,
                              mttr=mttr,
                              build_status=BuildStatus.Commissioned,
                              capex=0.0,
                              opex=0.0,
                              Cost=cost,
                              Cost_prof=None,
                              device_type=DeviceType.BranchDevice)

        # List of measurements
        self.measurements = list()

        # line length in km
        self.length = length

        # branch impedance tolerance
        self.tolerance = tolerance

        # short circuit impedance
        self.r_fault = r_fault
        self.x_fault = x_fault
        self.fault_pos = fault_pos

        # total impedance and admittance in p.u.
        self.R = r
        self.X = x
        self.G = g
        self.B = b

        # Conductor base and operating temperatures in ºC
        self.temp_base = temp_base
        self.temp_oper = temp_oper

        self.temp_oper_prof = None

        # Conductor thermal constant (1/ºC)
        self.alpha = alpha

        # tap changer object
        self.tap_changer = TapChanger()

        # Tap module
        if tap != 0:
            self.tap_module = tap
            self.tap_changer.set_tap(self.tap_module)
        else:
            self.tap_module = self.tap_changer.get_tap()

        # Tap angle
        self.angle = shift_angle

        # branch rating in MVA
        self.rate = rate

        self.rate_prof = None

        # branch type: Line, Transformer, etc...
        self.branch_type = branch_type

        # type template
        self.template = template
        self.bus_to_regulated = bus_to_regulated
        self.vset = vset

        # converter for enumerations
        self.conv = {'branch': BranchType.Branch,
                     'line': BranchType.Line,
                     'transformer': BranchType.Transformer,
                     'switch': BranchType.Switch,
                     'reactance': BranchType.Reactance}

        self.inv_conv = {val: key for key, val in self.conv.items()}

        self.register(key='R', units='p.u.', tpe=float, definition='Total positive sequence resistance.')
        self.register(key='X', units='p.u.', tpe=float, definition='Total positive sequence reactance.')
        self.register(key='B', units='p.u.', tpe=float, definition='Total positive sequence shunt susceptance.')
        self.register(key='G', units='p.u.', tpe=float, definition='Total positive sequence shunt conductance.')
        self.register(key='tolerance', units='%', tpe=float,
                      definition='Tolerance expected for the impedance values % is expected for '
                                 'transformers0% for lines.')
        self.register(key='length', units='km', tpe=float, definition='Length of the line (not used for calculation)')
        self.register(key='temp_base', units='ºC', tpe=float, definition='Base temperature at which R was measured.')
        self.register(key='temp_oper', units='ºC', tpe=float, definition='Operation temperature to modify R.',
                      profile_name='temp_oper_prof')
        self.register(key='alpha', units='1/ºC', tpe=float,
                      definition='Thermal coefficient to modify R,around a reference temperatureusing a linear '
                                 'approximation.For example:Copper @ 20ºC: 0.004041,Copper @ 75ºC: 0.00323,Annealed '
                                 'copper @ 20ºC: 0.00393,Aluminum @ 20ºC: 0.004308,Aluminum @ 75ºC: 0.00330')
        self.register(key='tap_module', units='', tpe=float, definition='Tap changer module, it a value close to 1.0')
        self.register(key='angle', units='rad', tpe=float, definition='Angle shift of the tap changer.')
        self.register(key='template', units='', tpe=BranchType, definition='', editable=False)

        self.register(key='bus_to_regulated', units='', tpe=bool, definition='Is the regulation at the bus to?')
        self.register(key='vset', units='p.u.', tpe=float, definition='set control voltage.')

        self.register(key='r_fault', units='p.u.', tpe=float, definition='Fault resistance.')
        self.register(key='x_fault', units='p.u.', tpe=float, definition='Fault reactance.')
        self.register(key='fault_pos', units='p.u.', tpe=float,
                      definition='proportion of the fault location measured from the "from" bus.')
        self.register(key='branch_type', units='p.u.', tpe=BranchType, definition='Fault resistance.')

    @property
    def R_corrected(self):
        """
        Returns a temperature corrected resistance based on a formula provided by:
        NFPA 70-2005, National Electrical Code, Table 8, footnote #2; and
        https://en.wikipedia.org/wiki/Electrical_resistivity_and_conductivity#Linear_approximation
        (version of 2019-01-03 at 15:20 EST).
        """
        return self.R * (1 + self.alpha * (self.temp_oper - self.temp_base))

    def get_weight(self):
        return np.sqrt(self.R * self.R + self.X * self.X)

    def branch_type_converter(self, val_string):
        """
        function to convert the branch type string into the BranchType
        :param val_string:
        :return: branch type conversion
        """
        return self.conv[val_string.lower()]

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

        # z_series = complex(self.R, self.X)
        # y_shunt = complex(self.G, self.B)
        b = Branch(bus_from=f,
                   bus_to=t,
                   name=self.name,
                   r=self.R,
                   x=self.X,
                   g=self.G,
                   b=self.B,
                   rate=self.rate,
                   tap=self.tap_module,
                   shift_angle=self.angle,
                   active=self.active,
                   mttf=self.mttf,
                   mttr=self.mttr,
                   bus_to_regulated=self.bus_to_regulated,
                   vset=self.vset,
                   temp_base=self.temp_base,
                   temp_oper=self.temp_oper,
                   alpha=self.alpha,
                   branch_type=self.branch_type,
                   template=self.template)

        b.measurements = self.measurements

        b.active_prof = self.active_prof.copy()

        return b

    def tap_up(self):
        """
        Move the tap changer one position up
        """
        self.tap_changer.tap_up()
        self.tap_module = self.tap_changer.get_tap()

    def tap_down(self):
        """
        Move the tap changer one position up
        """
        self.tap_changer.tap_down()
        self.tap_module = self.tap_changer.get_tap()

    def apply_tap_changer(self, tap_changer: TapChanger):
        """
        Apply a new tap changer

        Argument:

            **tap_changer** (:class:`GridCalEngine.Devices.branch.TapChanger`): Tap changer object

        """
        self.tap_changer = tap_changer

        if self.tap_module != 0:
            self.tap_changer.set_tap(self.tap_module)
        else:
            self.tap_module = self.tap_changer.get_tap()

    def get_save_data(self):
        """
        Return the data that matches the edit_headers
        :return:
        """
        data = list()
        for name, properties in self.editable_headers.items():
            obj = getattr(self, name)

            if properties.tpe == BranchType:
                obj = self.branch_type.value

            elif properties.tpe == BranchTemplate:
                if obj is None:
                    obj = ''
                else:
                    obj = str(obj)

            elif properties.tpe not in [str, float, int, bool]:
                obj = str(obj)

            data.append(obj)
        return data

    def get_properties_dict(self, version=3):
        """
        Get json dictionary
        :return:
        """

        d = {'id': self.idtag,
             'type': 'branch',
             'phases': 'ps',
             'name': self.name,
             'from': self.bus_from.idtag,
             'to': self.bus_to.idtag,
             'active': self.active,
             'rate': self.rate,
             'r': self.R,
             'x': self.X,
             'g': self.G,
             'b': self.B,
             'length': self.length,
             'tap_module': self.tap_module,
             'bus_to_regulated': self.bus_to_regulated,
             'vset': self.vset,
             'temp_base': self.temp_base,
             'temp_oper': self.temp_oper,
             'alpha': self.alpha,
             'tap_angle': self.angle,
             'branch_type': str(self.branch_type),
             'active_profile': [],
             'rate_prof': []}

        if self.active_prof is not None:
            d['active_profile'] = self.active_prof.tolist()
            d['rate_prof'] = self.rate_prof.tolist()

        return d

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

            x = time_series.results.time_array

            # loading
            y = time_series.results.loading * 100.0
            df = pd.DataFrame(data=y[:, my_index], index=x, columns=[self.name])
            ax_1.set_title('Loading', fontsize=14)
            ax_1.set_ylabel('Loading [%]', fontsize=11)
            df.plot(ax=ax_1)

            # losses
            y = time_series.results.losses
            df = pd.DataFrame(data=y[:, my_index], index=x, columns=[self.name])
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

    def get_equivalent_transformer(self) -> Transformer2W:
        """
        Convert this line into a transformer
        This is necessary if the buses' voltage differ too much
        :return: Transformer2W
        """
        V1 = min(self.bus_to.Vnom, self.bus_from.Vnom)
        V2 = max(self.bus_to.Vnom, self.bus_from.Vnom)
        return Transformer2W(bus_from=self.bus_from,
                             bus_to=self.bus_to,
                             name=self.name,
                             r=self.R,
                             x=self.X,
                             b=self.B,
                             rate=self.rate,
                             active=self.active,
                             tolerance=self.tolerance,
                             cost=self.Cost,
                             mttf=self.mttf,
                             mttr=self.mttr,
                             tap_module=self.tap_module,
                             tap_phase=self.angle,
                             vset=self.vset,
                             bus_to_regulated=self.bus_to_regulated,
                             temp_base=self.temp_base,
                             temp_oper=self.temp_oper,
                             alpha=self.alpha,
                             template=self.template,
                             rate_prof=self.rate_prof,
                             Cost_prof=self.Cost_prof,
                             active_prof=self.active_prof,
                             temp_oper_prof=self.temp_oper_prof)

    def get_equivalent_line(self) -> Line:
        """
        Get the equivalent line object
        :return:
        """
        return Line(bus_from=self.bus_from,
                    bus_to=self.bus_to,
                    name=self.name,
                    r=self.R,
                    x=self.X,
                    b=self.B,
                    rate=self.rate,
                    active=self.active,
                    tolerance=self.tolerance,
                    cost=self.Cost,
                    mttf=self.mttf,
                    mttr=self.mttr,
                    r_fault=self.r_fault,
                    x_fault=self.x_fault,
                    fault_pos=self.fault_pos,
                    length=self.length,
                    temp_base=self.temp_base,
                    temp_oper=self.temp_oper,
                    alpha=self.alpha,
                    rate_prof=self.rate_prof,
                    Cost_prof=self.Cost_prof,
                    active_prof=self.active_prof,
                    temp_oper_prof=self.temp_oper_prof)


def convert_branch(branch: Branch):
    """

    :param branch:
    :return:
    """
    if branch.branch_type == BranchType.Line:

        return Line(bus_from=branch.bus_from,
                    bus_to=branch.bus_to,
                    name=branch.name,
                    r=branch.R,
                    x=branch.X,
                    b=branch.B,
                    rate=branch.rate,
                    active=branch.active,
                    tolerance=branch.tolerance,
                    cost=branch.Cost,
                    mttf=branch.mttf,
                    mttr=branch.mttr,
                    r_fault=branch.r_fault,
                    x_fault=branch.x_fault,
                    fault_pos=branch.fault_pos,
                    length=branch.length,
                    temp_base=branch.temp_base,
                    temp_oper=branch.temp_oper,
                    alpha=branch.alpha,
                    rate_prof=branch.rate_prof,
                    Cost_prof=branch.Cost_prof,
                    active_prof=branch.active_prof,
                    temp_oper_prof=branch.temp_oper_prof)

    elif branch.branch_type == BranchType.Transformer:

        return Transformer2W(bus_from=branch.bus_from,
                             bus_to=branch.bus_to,
                             name=branch.name,
                             r=branch.R,
                             x=branch.X,
                             b=branch.B,
                             rate=branch.rate,
                             active=branch.active,
                             tolerance=branch.tolerance,
                             cost=branch.Cost,
                             mttf=branch.mttf,
                             mttr=branch.mttr,
                             tap_module=branch.tap_module,
                             tap_phase=branch.angle,
                             vset=branch.vset,
                             bus_to_regulated=branch.bus_to_regulated,
                             temp_base=branch.temp_base,
                             temp_oper=branch.temp_oper,
                             alpha=branch.alpha,
                             template=branch.template,
                             rate_prof=branch.rate_prof,
                             Cost_prof=branch.Cost_prof,
                             active_prof=branch.active_prof,
                             temp_oper_prof=branch.temp_oper_prof)
    else:
        return branch
