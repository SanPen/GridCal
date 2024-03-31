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
from matplotlib import pyplot as plt
from typing import List, Union, Any
import math
from PySide6 import QtGui

from GridCalEngine.basic_structures import LogSeverity
from GridCalEngine.Devices.multi_circuit import MultiCircuit
from GridCalEngine.basic_structures import Logger
from GridCalEngine.enumerations import DeviceType
from GridCalEngine.Devices.types import ALL_DEV_TYPES


class GridErrorLog:
    """
    Log of grid errors
    """

    def __init__(self) -> None:
        """
        Constructor
        """
        self.logs = dict()

        self.header = ['Object type',
                       'Name',
                       'Index',
                       'Severity',
                       'Property',
                       'Lower',
                       'Value',
                       'Upper']

    def add(self,
            object_type,
            element_name: Union[str, Any],
            element_index: int,
            severity: LogSeverity,
            propty: str,
            message: str,
            lower: Union[str, float, int] = '',
            val: Union[str, float, int] = '',
            upper: Union[str, float, int] = ''):
        """

        :param object_type:
        :param element_name:
        :param element_index:
        :param severity:
        :param propty:
        :param message:
        :param lower:
        :param val:
        :param upper:
        :return:
        """

        e = [object_type,
             str(element_name),
             element_index,
             severity,
             propty,
             str(lower),
             str(val),
             str(upper)]

        if message in self.logs.keys():
            self.logs[message].append(e)
        else:
            self.logs[message] = [e]

    def clear(self):
        """
        Delete all logs
        """
        self.logs.clear()

    def get_model(self) -> "QtGui.QStandardItemModel":
        """
        Get TreeView Model
        :return: QStandardItemModel
        """
        model = QtGui.QStandardItemModel()
        model.setHorizontalHeaderLabels(self.header)

        # populate data
        for message_key, entries in self.logs.items():
            parent1 = QtGui.QStandardItem(message_key)
            for object_type, element_name, element_index, severity, prop, lower, val, upper in entries:
                children = [QtGui.QStandardItem(str(object_type)),
                            QtGui.QStandardItem(str(element_name)),
                            QtGui.QStandardItem(str(element_index)),
                            QtGui.QStandardItem(severity.value),
                            QtGui.QStandardItem(str(prop)),
                            QtGui.QStandardItem(str(lower)),
                            QtGui.QStandardItem(str(val)),
                            QtGui.QStandardItem(str(upper))]
                for chld in children:
                    chld.setEditable(False)

                parent1.appendRow(children)

            parent1.setEditable(False)
            model.appendRow(parent1)

        return model

    def get_df(self):
        """
        Save analysis to excel
        :return:
        """
        data = list()

        for message in self.logs.keys():

            items = self.logs[message]

            for [object_type, element_name, element_index, severity, propty, lower, val, upper] in items:
                data.append([message, object_type, element_name, element_index, severity, propty, lower, val, upper])

        hdr = ['Message', 'Object type', 'Name', 'Index', 'Severity', 'Property', 'Lower', 'Value', 'Upper']
        return pd.DataFrame(data=data, columns=hdr)

    def save(self, filename):
        """
        Save analysis to excel
        :param filename:
        :return:
        """
        df = self.get_df()
        df.to_excel(filename)


class FixableErrorOutOfRange:
    """
    Error type for when a value is out of range
    """

    def __init__(self,
                 grid_element: ALL_DEV_TYPES,
                 property_name: str,
                 value: float,
                 lower_limit: float,
                 upper_limit: float):
        """

        :param grid_element:
        :param property_name:
        :param value:
        :param lower_limit:
        :param upper_limit:
        """
        self.grid_element: ALL_DEV_TYPES = grid_element
        self.property_name: str = property_name
        self.value: float = value
        self.lower_limit: float = lower_limit
        self.upper_limit: float = upper_limit

    def fix(self, logger: Logger = Logger(), fix_ts=False):
        """

        :param logger:
        :param fix_ts:
        :return:
        """
        if self.value < self.lower_limit:
            self.grid_element.set_snapshot_value(property_name=self.property_name, value=self.lower_limit)
            logger.add_info("Fixed " + self.property_name, device=self.grid_element.idtag, value=self.value)

        elif self.value > self.upper_limit:
            self.grid_element.set_snapshot_value(property_name=self.property_name, value=self.upper_limit)
            logger.add_info("Fixed " + self.property_name, device=self.grid_element.idtag, value=self.value)

        # fix the associated time series
        gc_prop = self.grid_element.registered_properties.get(self.property_name, None)
        if fix_ts and gc_prop.has_profile():
            profile = self.grid_element.get_profile_by_prop(prop=gc_prop)
            for i in range(profile.size()):
                value = profile[i]
                if value < self.lower_limit:
                    profile[i] = self.lower_limit
                    logger.add_info("Fixed " + self.property_name, device=self.grid_element.idtag, value=value)

                elif value > self.upper_limit:
                    profile[i] = self.upper_limit
                    logger.add_info("Fixed " + self.property_name, device=self.grid_element.idtag, value=value)


class FixableErrorRangeFlip:
    """
    Error type for when a range is reversed
    """

    def __init__(self, grid_element, property_name_low, property_name_high, value_low, value_high):
        """

        :param grid_element:
        :param property_name_low:
        :param property_name_high:
        :param value_low:
        :param value_high:
        """
        self.grid_element = grid_element
        self.property_name_low = property_name_low
        self.property_name_high = property_name_high
        self.value_low = value_low
        self.value_high = value_high

    def fix(self, logger: Logger = Logger(), fix_ts=False):
        """

        :param logger:
        :param fix_ts:
        """
        if self.value_high < self.value_low:
            # flip the values
            self.grid_element.set_snapshot_value(property_name=self.property_name_low, value=self.value_high)
            self.grid_element.set_snapshot_value(property_name=self.property_name_high, value=self.value_low)


class FixableErrorNegative:
    """
    Error type for when a value is negative
    """

    def __init__(self, grid_element, property_name, value):
        """

        :param grid_element:
        :param property_name:
        :param value:
        """
        self.grid_element = grid_element
        self.property_name = property_name
        self.value = value

    def fix(self, logger: Logger = Logger(), fix_ts=False):
        """

        :param logger:
        :param fix_ts:
        :return:
        """
        # set the same value but positive
        if self.value < 0:
            self.grid_element.set_snapshot_value(property_name=self.property_name, value=-self.value)


class FixableTransformerVtaps:
    """
    Error type for when a transformer virtual taps are wrong
    """

    def __init__(self, grid_element, maximum_difference):
        """

        :param grid_element:
        :param maximum_difference:
        """
        self.grid_element = grid_element
        self.maximum_difference = maximum_difference

    def fix(self, logger: Logger = Logger(), fix_ts=False):
        """

        :param logger:
        :param fix_ts:
        :return:
        """
        # set the same value but positive
        self.grid_element.fix_inconsistencies(logger=logger,
                                              maximum_difference=self.maximum_difference)


def grid_analysis(circuit: MultiCircuit,
                  imbalance_threshold=0.02,
                  v_low=0.95,
                  v_high=1.05,
                  tap_min=0.95,
                  tap_max=1.05,
                  transformer_virtual_tap_tolerance=0.1,
                  branch_connection_voltage_tolerance=0.1,
                  min_vcc=8,
                  max_vcc=18,
                  logger=GridErrorLog(),
                  eps_max: float = 1e20,
                  eps_min: float = 1e-20):
    """
    Analyze the model data
    :param circuit: Circuit to analyze
    :param imbalance_threshold: Allowed percentage of imbalance
    :param v_low: lower voltage setting
    :param v_high: higher voltage setting
    :param tap_min: minimum tap value
    :param tap_max: maximum tap value
    :param transformer_virtual_tap_tolerance:
    :param branch_connection_voltage_tolerance:
    :param max_vcc: maximum short circuit voltage (%)
    :param min_vcc: Minimum short circuit voltage (%)
    :param logger: GridErrorLog
    :param eps_max: Max epsylon value for comparison
    :param eps_min: Min epsylon value for comparison
    :return: list of fixable error objects
    """
    if circuit.time_profile is not None:
        nt = len(circuit.time_profile)
    else:
        nt = 0

    fixable_errors: List[object] = list()

    Pl = 0
    Pg = 0
    Pl_prof = np.zeros(nt)
    Pg_prof = np.zeros(nt)

    Ql = 0
    Qg = 0
    Ql_prof = np.zeros(nt)
    Qg_prof = np.zeros(nt)

    Qmin = 0.0
    Qmax = 0.0

    # declare logs

    for template_elm in circuit.get_objects_with_profiles_list():

        # get the device type of the prototype object
        object_type = template_elm.device_type

        if object_type == DeviceType.LineDevice:
            elements = circuit.lines

            for i, elm in enumerate(elements):

                V1 = min(elm.bus_to.Vnom, elm.bus_from.Vnom)
                V2 = max(elm.bus_to.Vnom, elm.bus_from.Vnom)

                s = '[' + str(V1) + '-' + str(V2) + ']'

                if V1 > 0 and V2 > 0:
                    per = V1 / V2
                    if per < (1.0 - branch_connection_voltage_tolerance):
                        logger.add(object_type=object_type.value,
                                   element_name=elm.name,
                                   element_index=i,
                                   severity=LogSeverity.Error,
                                   propty='Connection',
                                   message='The branch is connected between voltages '
                                           'that differ in {}% or more. Should this '
                                           'be a transformer?'.format(int(branch_connection_voltage_tolerance * 100)),
                                   lower=V1,
                                   upper=V2)
                else:
                    logger.add(object_type=object_type.value,
                               element_name=elm.name,
                               element_index=i,
                               severity=LogSeverity.Error,
                               propty='Voltage',
                               message='The branch does is connected to a bus with Vnom=0, this is terrible.')

                if elm.name == '':
                    logger.add(object_type=object_type.value,
                               element_name=elm.name,
                               element_index=i,
                               severity=LogSeverity.Information,
                               propty='name',
                               message='The branch does not have a name')

                if elm.rate < 0.0:
                    logger.add(object_type=object_type.value,
                               element_name=elm.name,
                               element_index=i,
                               severity=LogSeverity.Error,
                               propty='rate',
                               message='The rating is negative. This cannot be.',
                               lower="0",
                               val=elm.rate)
                    fixable_errors.append(FixableErrorNegative(grid_element=elm,
                                                               property_name='rate',
                                                               value=elm.rate))

                elif elm.rate == 0.0:
                    logger.add(object_type=object_type.value,
                               element_name=elm.name,
                               element_index=i,
                               severity=LogSeverity.Error,
                               propty='rate',
                               message='There is no nominal power, this is bad.',
                               val=elm.rate)

                if elm.R < 0.0:
                    logger.add(object_type=object_type.value,
                               element_name=elm.name,
                               element_index=i,
                               severity=LogSeverity.Error,
                               propty='R',
                               message='The resistance is negative, that cannot be.',
                               lower="0.0",
                               val=elm.R)
                    fixable_errors.append(FixableErrorNegative(grid_element=elm,
                                                               property_name='R',
                                                               value=elm.R))

                elif elm.R == 1e-20:
                    logger.add(object_type=object_type.value,
                               element_name=elm.name,
                               element_index=i,
                               severity=LogSeverity.Information,
                               propty='R',
                               message='The resistance is practically zero.',
                               val=elm.R)
                    fixable_errors.append(FixableErrorOutOfRange(grid_element=elm,
                                                                 property_name='R',
                                                                 value=elm.R,
                                                                 lower_limit=eps_min,
                                                                 upper_limit=eps_max))

                if elm.X == 1e-20:
                    logger.add(object_type=object_type.value,
                               element_name=elm.name,
                               element_index=i,
                               severity=LogSeverity.Error,
                               propty='X',
                               message='The reactance is practically zero. This hurts numerical conditioning.',
                               val=elm.X)
                    fixable_errors.append(FixableErrorOutOfRange(grid_element=elm,
                                                                 property_name='X',
                                                                 value=elm.X,
                                                                 lower_limit=eps_min,
                                                                 upper_limit=eps_max))

                if elm.B == 0.0:
                    logger.add(object_type=object_type.value,
                               element_name=elm.name,
                               element_index=i,
                               severity=LogSeverity.Error,
                               propty='B',
                               message='There is no susceptance, this could hurt numerical conditioning.',
                               val=elm.B)
                    fixable_errors.append(FixableErrorOutOfRange(grid_element=elm,
                                                                 property_name='B',
                                                                 value=elm.B,
                                                                 lower_limit=eps_min,
                                                                 upper_limit=eps_max))

        elif object_type == DeviceType.Transformer2WDevice:
            elements = circuit.transformers2w

            for i, elm in enumerate(elements):

                if elm.name == '':
                    logger.add(object_type=object_type.value,
                               element_name=elm.name,
                               element_index=i,
                               severity=LogSeverity.Error,
                               propty='name',
                               message='The branch does not have a name')

                if elm.rate <= 0.0:
                    logger.add(object_type=object_type.value,
                               element_name=elm.name,
                               element_index=i,
                               severity=LogSeverity.Error,
                               propty='rate',
                               message='The rating is negative. This cannot be.',
                               lower="0",
                               val=elm.rate)
                    fixable_errors.append(FixableErrorNegative(grid_element=elm,
                                                               property_name='rate',
                                                               value=elm.rate))

                # check R and X
                if elm.R == 0.0 and elm.X == 0.0:
                    logger.add(object_type=object_type.value,
                               element_name=elm.name,
                               element_index=i,
                               severity=LogSeverity.Error,
                               propty='R+X',
                               message='There is no impedance, set at least a very low value',
                               lower="0",
                               val=elm.R + elm.X)
                    fixable_errors.append(FixableErrorOutOfRange(grid_element=elm,
                                                                 property_name='R',
                                                                 value=elm.rate,
                                                                 lower_limit=eps_min,
                                                                 upper_limit=eps_max))
                    fixable_errors.append(FixableErrorOutOfRange(grid_element=elm,
                                                                 property_name='X',
                                                                 value=elm.rate,
                                                                 lower_limit=eps_min,
                                                                 upper_limit=eps_max))

                else:
                    if elm.R < 0.0:
                        logger.add(object_type=object_type.value,
                                   element_name=elm.name,
                                   element_index=i,
                                   severity=LogSeverity.Warning,
                                   propty='R',
                                   message='The resistance is negative, that cannot be.',
                                   lower="0",
                                   val=elm.R)
                        fixable_errors.append(FixableErrorNegative(grid_element=elm,
                                                                   property_name='R',
                                                                   value=elm.R))

                    elif elm.R == 0.0:
                        logger.add(object_type=object_type.value,
                                   element_name=elm.name,
                                   element_index=i,
                                   severity=LogSeverity.Information,
                                   propty='R',
                                   message='The resistance is exactly zero',
                                   val=elm.R)
                        fixable_errors.append(FixableErrorOutOfRange(grid_element=elm,
                                                                     property_name='R',
                                                                     value=elm.R,
                                                                     lower_limit=eps_min,
                                                                     upper_limit=eps_max))

                    elif elm.X == 0.0:
                        logger.add(object_type=object_type.value,
                                   element_name=elm.name,
                                   element_index=i,
                                   severity=LogSeverity.Information,
                                   propty='X',
                                   message='The reactance is exactly zero',
                                   val=elm.X)
                        fixable_errors.append(FixableErrorOutOfRange(grid_element=elm,
                                                                     property_name='X',
                                                                     value=elm.rate,
                                                                     lower_limit=eps_min,
                                                                     upper_limit=eps_max))

                # check tap module
                if elm.tap_module > tap_max:
                    logger.add(object_type=object_type.value,
                               element_name=elm.name,
                               element_index=i,
                               severity=LogSeverity.Warning,
                               propty='tap_module',
                               message='Tap module too high',
                               upper=str(tap_max),
                               val=elm.tap_module)
                    fixable_errors.append(FixableErrorOutOfRange(grid_element=elm,
                                                                 property_name='tap_module',
                                                                 value=elm.tap_module,
                                                                 lower_limit=tap_min,
                                                                 upper_limit=tap_max))

                elif elm.tap_module < tap_min:
                    logger.add(object_type=object_type.value,
                               element_name=elm.name,
                               element_index=i,
                               severity=LogSeverity.Warning,
                               propty='tap_module',
                               message='Tap module too low',
                               upper=str(tap_min),
                               val=elm.tap_module)
                    fixable_errors.append(FixableErrorOutOfRange(grid_element=elm,
                                                                 property_name='tap_module',
                                                                 value=elm.tap_module,
                                                                 lower_limit=tap_min,
                                                                 upper_limit=tap_max))

                # check virtual taps
                tap_f, tap_t = elm.get_virtual_taps()

                if (1.0 - transformer_virtual_tap_tolerance) > tap_f or tap_f > (
                        1.0 + transformer_virtual_tap_tolerance):
                    logger.add(object_type=object_type.value,
                               element_name=elm.name,
                               element_index=i,
                               severity=LogSeverity.Error,
                               propty='HV or LV',
                               message='Large nominal voltage mismatch at the "from" bus',
                               lower=str(1.0 - transformer_virtual_tap_tolerance),
                               val=str(tap_f),
                               upper=str(1.0 + transformer_virtual_tap_tolerance))
                    fixable_errors.append(FixableTransformerVtaps(grid_element=elm,
                                                                  maximum_difference=transformer_virtual_tap_tolerance))

                if (1.0 - transformer_virtual_tap_tolerance) > tap_t or tap_t > (
                        1.0 + transformer_virtual_tap_tolerance):
                    logger.add(object_type=object_type.value,
                               element_name=elm.name,
                               element_index=i,
                               severity=LogSeverity.Error,
                               propty='HV or LV',
                               message='Large nominal voltage mismatch at the "to" bus',
                               lower=str(1.0 - transformer_virtual_tap_tolerance),
                               val=str(tap_t),
                               upper=str(1.0 + transformer_virtual_tap_tolerance))
                    fixable_errors.append(FixableTransformerVtaps(grid_element=elm,
                                                                  maximum_difference=transformer_virtual_tap_tolerance))

                # check VCC
                vcc = elm.get_vcc()
                if vcc < min_vcc or vcc > max_vcc:
                    logger.add(object_type=object_type.value,
                               element_name=elm.name,
                               element_index=i,
                               severity=LogSeverity.Warning,
                               propty='Vcc',
                               message='The short circuit value is suspicious',
                               lower=str(min_vcc),
                               upper=str(max_vcc),
                               val=str(vcc))

                # check the nominal power
                if elm.Sn > 0:
                    sn_ratio = elm.rate / elm.Sn
                    if not (0.9 < sn_ratio < 1.1):
                        logger.add(object_type=object_type.value,
                                   element_name=elm.name,
                                   element_index=i,
                                   severity=LogSeverity.Warning,
                                   propty='rate / Sn',
                                   message='Transformer rating is too different from the nominal power',
                                   lower=str(elm.Sn * 0.9),
                                   upper=str(elm.Sn * 1.1),
                                   val=elm.rate)
                        fixable_errors.append(FixableErrorOutOfRange(grid_element=elm,
                                                                     property_name='rate',
                                                                     value=elm.rate,
                                                                     lower_limit=elm.Sn,
                                                                     upper_limit=elm.Sn))

        elif object_type == DeviceType.BusDevice:
            elements = circuit.get_buses()
            names = set()

            for i, elm in enumerate(elements):

                if elm.Vnom <= 0.0:
                    logger.add(object_type=object_type.value,
                               element_name=elm.name,
                               element_index=i,
                               severity=LogSeverity.Error,
                               propty='Vnom',
                               message='The nominal voltage is <= 0, this causes problems',
                               lower="0",
                               val=elm.Vnom)
                    fixable_errors.append(FixableErrorOutOfRange(grid_element=elm,
                                                                 property_name='Vnom',
                                                                 value=elm.Vnom,
                                                                 lower_limit=tap_min,
                                                                 upper_limit=tap_max))

                if elm.name == '':
                    logger.add(object_type=object_type.value,
                               element_name=elm.name,
                               element_index=i,
                               severity=LogSeverity.Error,
                               propty='name',
                               message='The bus does not have a name')

                if elm.name in names:
                    logger.add(object_type=object_type.value,
                               element_name=elm.name,
                               element_index=i,
                               severity=LogSeverity.Information,
                               propty='name',
                               message='The bus name is not unique')

                # add the name to a set
                names.add(elm.name)

        elif object_type == DeviceType.GeneratorDevice:

            for k, obj in enumerate(circuit.get_generators()):
                Pg += obj.P * obj.active

                if circuit.time_profile is not None:
                    Pg_prof += obj.P_prof.toarray() * obj.active_prof.toarray()

                    if obj.Vset < v_low:
                        logger.add(object_type=object_type.value,
                                   element_name=obj,
                                   element_index=k,
                                   severity=LogSeverity.Warning,
                                   propty='Vset',
                                   message='The set point looks too low',
                                   lower=str(v_low),
                                   val=obj.Vset)
                        fixable_errors.append(FixableErrorOutOfRange(grid_element=obj,
                                                                     property_name='Vset',
                                                                     value=obj.Vset,
                                                                     lower_limit=v_low,
                                                                     upper_limit=v_high))

                    elif obj.Vset > v_high:
                        logger.add(object_type=object_type.value,
                                   element_name=obj,
                                   element_index=k,
                                   severity=LogSeverity.Warning,
                                   propty='Vset',
                                   message='The set point looks too high',
                                   val=obj.Vset,
                                   upper=str(v_high))
                        fixable_errors.append(FixableErrorOutOfRange(grid_element=obj,
                                                                     property_name='Vset',
                                                                     value=obj.Vset,
                                                                     lower_limit=v_low,
                                                                     upper_limit=v_high))

                    if obj.Qmax < obj.Qmin:
                        logger.add(object_type=object_type.value,
                                   element_name=obj,
                                   element_index=k,
                                   severity=LogSeverity.Error,
                                   propty='Qmax < Qmin',
                                   message='Wrong Q limit bounds',
                                   upper=obj.Qmax,
                                   lower=obj.Qmin)
                        fixable_errors.append(FixableErrorRangeFlip(grid_element=obj,
                                                                    property_name_low='Qmin',
                                                                    property_name_high='Qmax',
                                                                    value_low=obj.Qmin,
                                                                    value_high=obj.Qmax))

                    if obj.Qmax == obj.Qmin and obj.is_controlled:

                        if obj.Qmax == 0.0:
                            propty = 'Qmax == Qmin == 0'
                            message = 'Q limits equal to zero'

                        else:
                            propty = 'Qmax == Qmin'
                            message = 'Inflexible Q limit bounds'

                        logger.add(object_type=object_type.value,
                                   element_name=obj,
                                   element_index=k,
                                   severity=LogSeverity.Error,
                                   propty=propty,
                                   message=message,
                                   upper=obj.Qmax,
                                   lower=obj.Qmin)
                        fixable_errors.append(FixableErrorRangeFlip(grid_element=obj,
                                                                    property_name_low='Qmin',
                                                                    property_name_high='Qmax',
                                                                    value_low=obj.Qmin,
                                                                    value_high=obj.Qmax))

                    if obj.Pmax < obj.Pmin:
                        logger.add(object_type=object_type.value,
                                   element_name=obj,
                                   element_index=k,
                                   severity=LogSeverity.Error,
                                   propty='Pmax < Pmin',
                                   message='Wrong P limit bounds',
                                   upper=obj.Pmax,
                                   lower=obj.Pmin)
                        fixable_errors.append(FixableErrorRangeFlip(grid_element=obj,
                                                                    property_name_low='Pmin',
                                                                    property_name_high='Pmax',
                                                                    value_low=obj.Pmin,
                                                                    value_high=obj.Pmax))

        elif object_type == DeviceType.BatteryDevice:
            elements = circuit.get_batteries()

            for k, obj in enumerate(elements):
                Pg += obj.P * obj.active

                if circuit.time_profile is not None:
                    Pg_prof += obj.P_prof.toarray() * obj.active_prof.toarray()

                if obj.Vset < v_low:
                    logger.add(object_type=object_type.value,
                               element_name=obj,
                               element_index=k,
                               severity=LogSeverity.Warning,
                               propty='Vset',
                               message='The set point looks too low',
                               lower=str(v_low),
                               val=obj.Vset)
                    fixable_errors.append(FixableErrorOutOfRange(grid_element=obj,
                                                                 property_name='Vset',
                                                                 value=obj.Vset,
                                                                 lower_limit=v_low,
                                                                 upper_limit=v_high))

                elif obj.Vset > v_high:
                    logger.add(object_type=object_type.value,
                               element_name=obj,
                               element_index=k,
                               severity=LogSeverity.Warning,
                               propty='Vset',
                               message='The set point looks too high',
                               val=obj.Vset,
                               upper=str(v_high))
                    fixable_errors.append(FixableErrorOutOfRange(grid_element=obj,
                                                                 property_name='Vset',
                                                                 value=obj.Vset,
                                                                 lower_limit=v_low,
                                                                 upper_limit=v_high))

                if obj.Qmax < obj.Qmin:
                    logger.add(object_type=object_type.value,
                               element_name=obj,
                               element_index=k,
                               severity=LogSeverity.Error,
                               propty='Qmax < Qmin',
                               message='Wrong Q limit bounds',
                               upper=obj.Qmax,
                               lower=obj.Qmin)
                    fixable_errors.append(FixableErrorRangeFlip(grid_element=obj,
                                                                property_name_low='Qmin',
                                                                property_name_high='Qmax',
                                                                value_low=obj.Qmin,
                                                                value_high=obj.Qmax))

                if obj.Pmax < obj.Pmin:
                    logger.add(object_type=object_type.value,
                               element_name=obj,
                               element_index=k,
                               severity=LogSeverity.Error,
                               propty='Pmax < Pmin',
                               message='Wrong P limit bounds',
                               upper=obj.Pmax,
                               lower=obj.Pmin)
                    fixable_errors.append(FixableErrorRangeFlip(grid_element=obj,
                                                                property_name_low='Pmin',
                                                                property_name_high='Pmax',
                                                                value_low=obj.Pmin,
                                                                value_high=obj.Pmax))

                if obj.max_soc < obj.min_soc:
                    logger.add(object_type=object_type.value,
                               element_name=obj,
                               element_index=k,
                               severity=LogSeverity.Error,
                               propty='max_soc < min_soc',
                               message='Wrong SoC limit bounds',
                               upper=obj.max_soc,
                               lower=obj.min_soc)
                    fixable_errors.append(FixableErrorRangeFlip(grid_element=obj,
                                                                property_name_low='min_soc',
                                                                property_name_high='max_soc',
                                                                value_low=obj.min_soc,
                                                                value_high=obj.max_soc))

                if obj.Enom <= 0:
                    logger.add(object_type=object_type.value,
                               element_name=obj,
                               element_index=k,
                               severity=LogSeverity.Error,
                               propty='Enom',
                               message='Invalid nominal energy',
                               lower="0",
                               val=obj.Enom)

        elif object_type == DeviceType.StaticGeneratorDevice:
            elements = circuit.get_static_generators()

            for k, obj in enumerate(elements):
                Pg += obj.P * obj.active
                Qg += obj.Q * obj.active

                if circuit.time_profile is not None:
                    Pg_prof += obj.P_prof.toarray() * obj.active_prof.toarray()
                    Qg_prof += obj.Q_prof.toarray() * obj.active_prof.toarray()

                elif object_type == DeviceType.ShuntDevice:
                    elements = circuit.get_shunts()

                elif object_type == DeviceType.LoadDevice:
                    elements = circuit.get_loads()

                for elm in elements:
                    Pl += elm.P * elm.active
                    Ql += elm.Q * elm.active

                if circuit.time_profile is not None:
                    Pl_prof += obj.P_prof.toarray() * obj.active_prof.toarray()
                    Ql_prof += obj.Q_prof.toarray() * obj.active_prof.toarray()

                # compare loads
                p_ratio = abs(Pl - Pg) / (Pl + eps_min)

                if p_ratio > imbalance_threshold:
                    msg = ">> " + str(imbalance_threshold) + "%"
                    logger.add(object_type='Grid snapshot',
                               element_name=circuit,
                               element_index=-1,
                               severity=LogSeverity.Error,
                               propty='Active power balance ' + msg,
                               message='There is too much active power imbalance',
                               val="{:.1f}".format(p_ratio * 100))

                # compare reactive power limits
                if not (Qmin <= -Ql <= Qmax):
                    logger.add(object_type='Grid snapshot',
                               element_name=circuit,
                               element_index=-1,
                               severity=LogSeverity.Error,
                               propty="Reactive power out of bounds",
                               message='There is too much reactive power imbalance',
                               lower=str(Qmin),
                               val=str(Ql),
                               upper=str(Qmax))

                if circuit.time_profile is not None:
                    nt = len(circuit.time_profile)

                for t in range(nt):
                    # compare loads
                    p_ratio = abs(Pl_prof[t] - Pg_prof[t]) / (Pl_prof[t] + eps_min)
                    if p_ratio > imbalance_threshold:
                        msg = ">> " + str(imbalance_threshold) + "%"
                        logger.add(object_type='Active power balance',
                                   element_name=circuit,
                                   element_index=t,
                                   severity=LogSeverity.Error,
                                   propty=msg,
                                   message='There is too much active power imbalance',
                                   val="{:.1f}".format(p_ratio * 100))

                    # compare reactive power limits
                    if not (Qmin <= -Ql_prof[t] <= Qmax):
                        logger.add(object_type='Reactive power power balance',
                                   element_name=circuit,
                                   element_index=t,
                                   severity=LogSeverity.Error,
                                   propty="Reactive power out of bounds",
                                   message='There is too much reactive power imbalance',
                                   lower=str(Qmin),
                                   val=Ql_prof[t],
                                   upper=str(Qmax))

    return fixable_errors


def object_histogram_analysis(circuit: MultiCircuit,
                              object_type: DeviceType,
                              t_idx: Union[None, int],
                              fig=None):
    """
    Draw the histogram analysis of the provided object type
    :param circuit: Circuit
    :param object_type: Object Type (DeviceType)
    :param t_idx: Time index (None or int) to get the data
    :param fig: matplotlib figure (if None, a new one is created)
    """

    if object_type == DeviceType.LineDevice.value:
        properties = ['R', 'X', 'B', 'rate']
        log_scale = [False, False, False, False, False]
        objects = circuit.lines

    elif object_type == DeviceType.Transformer2WDevice.value:
        properties = ['R', 'X', 'G', 'B', 'tap_module', 'tap_phase', 'rate']
        log_scale = [False, False, False, False, False, False, False]
        objects = circuit.transformers2w

    elif object_type == DeviceType.BusDevice.value:
        properties = ['Vnom']
        log_scale = [False]
        objects = circuit.get_buses()

    elif object_type == DeviceType.GeneratorDevice.value:
        properties = ['Vset', 'P', 'Qmin', 'Qmax']
        log_scale = [False, False, False, False]
        objects = circuit.get_generators()

    elif object_type == DeviceType.BatteryDevice.value:
        properties = ['Vset', 'P', 'Qmin', 'Qmax']
        log_scale = [False, False, False, False]
        objects = circuit.get_batteries()

    elif object_type == DeviceType.StaticGeneratorDevice.value:
        properties = ['P', 'Q']
        log_scale = [False, False]
        objects = circuit.get_static_generators()

    elif object_type == DeviceType.ShuntDevice.value:
        properties = ['G', 'B']
        log_scale = [False, False]
        objects = circuit.get_shunts()

    elif object_type == DeviceType.LoadDevice.value:
        properties = ['P', 'Q', 'Ir', 'Ii', 'G', 'B']
        log_scale = [False, False, False, False, False, False]
        objects = circuit.get_loads()

    else:
        return

    n = len(objects)
    p = len(properties)
    vals = np.zeros((n, p))
    extended_prop = np.zeros(p, dtype=object)
    log_scale_extended = np.zeros(p, dtype=object)
    for j in range(len(properties)):

        if len(objects):
            gc_prop = objects[0].registered_properties[properties[j]]

            for i, elem in enumerate(objects):
                val = elem.get_property_value(prop=gc_prop, t_idx=t_idx)
                vals[i, j] = val
                extended_prop[j] = properties[j]
                log_scale_extended[j] = log_scale[j]

    # create figure if needed
    if fig is None:
        fig = plt.figure(figsize=(12, 6))

    fig.suptitle('Analysis of the ' + str(object_type), fontsize=16)
    fig.set_facecolor('white')

    if n > 0:
        k = int(np.round(math.sqrt(p)))
        axs = [None] * (p + 1)

        for j in range(p):
            x = vals[:, j]
            mu = x.mean()
            variance = x.var()
            sigma = math.sqrt(variance)
            r = (mu - 6 * sigma, mu + 6 * sigma)

            # plot
            ax = fig.add_subplot(k, k + 1, j + 1)
            ax.set_facecolor('white')
            # bin_edges = np.histogram_bin_edges(x)
            ax.hist(x,
                    # bins=len(bin_edges),
                    range=r,
                    cumulative=False,
                    bottom=None,
                    histtype='bar',
                    align='mid',
                    orientation='vertical')
            ax.plot(x, np.zeros(n), 'o')
            ax.set_title(extended_prop[j])

            if log_scale_extended[j]:
                ax.set_xscale('log')

            axs[j] = ax

        if object_type in [DeviceType.LineDevice.value,
                           DeviceType.Transformer2WDevice.value]:

            r = vals[:, 0]
            x = vals[:, 1]

            # plot
            ax = fig.add_subplot(k, k + 1, p + 2)
            ax.set_facecolor('white')
            ax.scatter(r, x)
            ax.set_title("R-X")
            ax.set_xlabel("R")
            ax.set_ylabel("X")
            axs[p] = ax

    fig.tight_layout(rect=[0, 0.03, 1, 0.95])
