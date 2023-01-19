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

import numpy as np
import pandas as pd
from matplotlib import pyplot as plt
import math
from PySide2 import QtWidgets, QtGui

from GridCal.Engine.basic_structures import LogSeverity
from GridCal.Engine.Core.multi_circuit import MultiCircuit
from GridCal.Engine.Devices import *


class GridErrorLog:

    def __init__(self, parent=None):

        self.logs = dict()

        self.header = ['Object type', 'Name', 'Index', 'Severity', 'Property', 'Lower', 'Value', 'Upper']

    def add(self, object_type, element_name, element_index, severity: LogSeverity, propty, message, lower='', val='', upper=''):
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

        e = [object_type, element_name, element_index, severity, propty, lower, val, upper]

        if message in self.logs.keys():
            self.logs[message].append(e)
        else:
            self.logs[message] = [e]

    def clear(self):
        """
        Delete all logs
        """
        self.logs = list()

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
        :param filename:
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


def grid_analysis(circuit: MultiCircuit, imbalance_threshold=0.02, v_low=0.95, v_high=1.05, tap_min=0.95, tap_max=1.05):
    """
    Analyze the model data
    :param circuit: Circuit to analyze
    :param imbalance_threshold: Allowed percentage of imbalance
    :param v_low: lower voltage setting
    :param v_high: higher voltage setting
    :return:
    """
    if circuit.time_profile is not None:
        nt = len(circuit.time_profile)
    else:
        nt = 0

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

    print('Analyzing...')
    # declare logs
    logger = GridErrorLog()

    for dev in circuit.objects_with_profiles:

        # get the device type of the prototype object
        object_type = dev.device_type

        if object_type == DeviceType.LineDevice:
            elements = circuit.lines

            for i, elm in enumerate(elements):

                V1 = min(elm.bus_to.Vnom, elm.bus_from.Vnom)
                V2 = max(elm.bus_to.Vnom, elm.bus_from.Vnom)

                s = '[' + str(V1) + '-' + str(V2) + ']'

                if V1 > 0 and V2 > 0:
                    per = V1 / V2
                    if per < 0.9:
                        logger.add(object_type=object_type.value,
                                   element_name=elm.name,
                                   element_index=i,
                                   severity=LogSeverity.Error,
                                   propty='Connection',
                                   message='The branch is connected between voltages '
                                           'that differ in 10% or more. Should this be a transformer?' + s,
                                   lower=V1,
                                   upper=V2)
                else:
                    logger.add(object_type=object_type.value,
                               element_name=elm.name,
                               element_index=i,
                               severity=LogSeverity.Error,
                               propty='Voltage',
                               message='The branch does is connected to a bus with Vnom=0, this is terrible.' + s)

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
                               lower=0,
                               val=elm.rate)

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

                elif elm.R == 0.0:
                    logger.add(object_type=object_type.value,
                               element_name=elm.name,
                               element_index=i,
                               severity=LogSeverity.Information,
                               propty='R',
                               message='The resistance is exactly zero.',
                               val=elm.R)

                if elm.X == 0.0:
                    logger.add(object_type=object_type.value,
                               element_name=elm.name,
                               element_index=i,
                               severity=LogSeverity.Error,
                               propty='X',
                               message='The reactance is exactly zero. This hurts numerical conditioning.',
                               val=elm.X)

                if elm.B == 0.0:
                    logger.add(object_type=object_type.value,
                               element_name=elm.name,
                               element_index=i,
                               severity=LogSeverity.Error,
                               propty='B',
                               message='There is no susceptance, this hurts numerical conditioning.',
                               val=elm.B)

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
                               message='There is no nominal power',
                               lower="0",
                               val=elm.rate)

                if elm.R == 0.0 and elm.X == 0.0:
                    logger.add(object_type=object_type.value,
                               element_name=elm.name,
                               element_index=i,
                               severity=LogSeverity.Error,
                               propty='R+X',
                               message='There is no impedance, set at least a very low value',
                               lower="0",
                               val=elm.R + elm.X)

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

                    elif elm.R == 0.0:
                        logger.add(object_type=object_type.value,
                                   element_name=elm.name,
                                   element_index=i,
                                   severity=LogSeverity.Information,
                                   propty='R',
                                   message='The resistance is exactly zero',
                                   val=elm.R)

                    elif elm.X == 0.0:
                        logger.add(object_type=object_type.value,
                                   element_name=elm.name,
                                   element_index=i,
                                   severity=LogSeverity.Information,
                                   propty='X',
                                   message='The reactance is exactly zero',
                                   val=elm.X)

                tap_f, tap_t = elm.get_virtual_taps()

                if tap_min > tap_f or tap_f > tap_max:
                    logger.add(object_type=object_type.value,
                               element_name=elm.name,
                               element_index=i,
                               severity=LogSeverity.Error,
                               propty='HV or LV',
                               message='Large nominal voltage mismatch at the "from" bus',
                               lower=tap_min,
                               val=tap_f,
                               upper=tap_max)

                if tap_min > tap_t or tap_t > tap_max:
                    logger.add(object_type=object_type.value,
                               element_name=elm.name,
                               element_index=i,
                               severity=LogSeverity.Error,
                               propty='HV or LV',
                               message='Large nominal voltage mismatch at the "to" bus',
                               lower=tap_min,
                               val=tap_t,
                               upper=tap_max)

        elif object_type == DeviceType.BusDevice:
            elements = circuit.buses
            names = set()

            for i, elm in enumerate(elements):

                qmin, qmax = elm.get_reactive_power_limits()
                Qmin += qmin
                Qmax += qmax

                if elm.Vnom <= 0.0:
                    logger.add(object_type=object_type.value,
                               element_name=elm.name,
                               element_index=i,
                               severity=LogSeverity.Error,
                               propty='Vnom',
                               message='The nominal voltage is <= 0, this causes problems',
                               lower="0",
                               val=elm.Vnom)

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

            elements = circuit.get_generators()

            for k, obj in enumerate(elements):
                Pg += obj.P * obj.active

                if circuit.time_profile is not None:
                    Pg_prof += obj.P_prof * obj.active_prof

                if obj.Vset < v_low:
                    logger.add(object_type=object_type.value,
                               element_name=obj,
                               element_index=k,
                               severity=LogSeverity.Warning,
                               propty='Vset',
                               message='The set point looks too low',
                               lower=v_low,
                               val=obj.Vset)

                elif obj.Vset > v_high:
                    logger.add(object_type=object_type.value,
                               element_name=obj,
                               element_index=k,
                               severity=LogSeverity.Warning,
                               propty='Vset',
                               message='The set point looks too high',
                               val=obj.Vset,
                               upper=v_high)

                if obj.Qmax < obj.Qmin:
                    logger.add(object_type=object_type.value,
                               element_name=obj,
                               element_index=k,
                               severity=LogSeverity.Error,
                               propty='Qmax < Qmin',
                               message='Wrong Q limit bounds',
                               upper=obj.Qmax,
                               lower=obj.Qmin)

                if obj.Pmax < obj.Pmin:
                    logger.add(object_type=object_type.value,
                               element_name=obj,
                               element_index=k,
                               severity=LogSeverity.Error,
                               propty='Pmax < Pmin',
                               message='Wrong P limit bounds',
                               upper=obj.Pmax,
                               lower=obj.Pmin)

        elif object_type == DeviceType.BatteryDevice:
            elements = circuit.get_batteries()

            for k, obj in enumerate(elements):
                Pg += obj.P * obj.active

                if circuit.time_profile is not None:
                    Pg_prof += obj.P_prof * obj.active_prof

                if obj.Vset < v_low:
                    logger.add(object_type=object_type.value,
                               element_name=obj,
                               element_index=k,
                               severity=LogSeverity.Warning,
                               propty='Vset',
                               message='The set point looks too low',
                               lower=v_low,
                               val=obj.Vset)

                elif obj.Vset > v_high:
                    logger.add(object_type=object_type.value,
                               element_name=obj,
                               element_index=k,
                               severity=LogSeverity.Warning,
                               propty='Vset',
                               message='The set point looks too high',
                               val=obj.Vset,
                               upper=v_high)

                if obj.Qmax < obj.Qmin:
                    logger.add(object_type=object_type.value,
                               element_name=obj,
                               element_index=k,
                               severity=LogSeverity.Error,
                               propty='Qmax < Qmin',
                               message='Wrong Q limit bounds',
                               upper=obj.Qmax,
                               lower=obj.Qmin)

                if obj.Pmax < obj.Pmin:
                    logger.add(object_type=object_type.value,
                               element_name=obj,
                               element_index=k,
                               severity=LogSeverity.Error,
                               propty='Pmax < Pmin',
                               message='Wrong P limit bounds',
                               upper=obj.Pmax,
                               lower=obj.Pmin)

                if obj.max_soc < obj.min_soc:
                    logger.add(object_type=object_type.value,
                               element_name=obj,
                               element_index=k,
                               severity=LogSeverity.Error,
                               propty='max_soc < min_soc',
                               message='Wrong SoC limit bounds',
                               upper=obj.max_soc,
                               lower=obj.min_soc)

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
                    Pg_prof += obj.P_prof * obj.active_prof
                    Qg_prof += obj.Q_prof * obj.active_prof

        elif object_type == DeviceType.ShuntDevice:
            elements = circuit.get_shunts()

        elif object_type == DeviceType.LoadDevice:
            elements = circuit.get_loads()

            for obj in elements:
                Pl += obj.P * obj.active
                Ql += obj.Q * obj.active

                if circuit.time_profile is not None:
                    Pl_prof += obj.P_prof * obj.active_prof
                    Ql_prof += obj.Q_prof * obj.active_prof

    # compare loads
    p_ratio = abs(Pl - Pg) / (Pl + 1e-20)

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
                   lower=Qmin,
                   val=Ql,
                   upper=Qmax)

    if circuit.time_profile is not None:
        nt = len(circuit.time_profile)
        for t in range(nt):

            # compare loads
            p_ratio = abs(Pl_prof[t] - Pg_prof[t]) / (Pl_prof[t] + 1e-20)
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
                           lower=Qmin,
                           val=Ql_prof[t],
                           upper=Qmax)

    return logger


def object_histogram_analysis(circuit: MultiCircuit, object_type: DeviceType, fig=None):
    """
    Draw the histogram analysis of the provided object type
    :param circuit: Circuit
    :param object_type: Object Type (DeviceType)
    :param fig: matplotlib figure (if None, a new one is created)
    """

    if object_type == DeviceType.LineDevice.value:
        properties = ['R', 'X', 'B', 'rate']
        types = [float, float, float, float, float]
        log_scale = [False, False, False, False, False]
        objects = circuit.lines

    elif object_type == DeviceType.Transformer2WDevice.value:
        properties = ['R', 'X', 'G', 'B', 'tap_module', 'angle', 'rate']
        types = [float, float, float, float, float, float, float]
        log_scale = [False, False, False, False, False, False, False]
        objects = circuit.transformers2w

    elif object_type == DeviceType.BusDevice.value:
        properties = ['Vnom']
        types = [float]
        log_scale = [False]
        objects = circuit.buses

    elif object_type == DeviceType.GeneratorDevice.value:
        properties = ['Vset', 'P', 'Qmin', 'Qmax']
        log_scale = [False, False, False, False]
        types = [float, float, float, float]
        objects = circuit.get_generators()

    elif object_type == DeviceType.BatteryDevice.value:
        properties = ['Vset', 'P', 'Qmin', 'Qmax']
        log_scale = [False, False, False, False]
        types = [float, float, float, float]
        objects = circuit.get_batteries()

    elif object_type == DeviceType.StaticGeneratorDevice.value:
        properties = ['P', 'Q']
        log_scale = [False, False]
        types = [float, float]
        objects = circuit.get_static_generators()

    elif object_type == DeviceType.ShuntDevice.value:
        properties = ['G', 'B']
        log_scale = [False, False]
        types = [float, float]
        objects = circuit.get_shunts()

    elif object_type == DeviceType.LoadDevice.value:
        properties = ['P', 'Q', 'Ir', 'Ii', 'G', 'B']
        log_scale = [False, False, False, False, False, False]
        types = [float, float, float, float, float, float]
        objects = circuit.get_loads()

    else:
        return

    # fill values
    p = 0
    for i in range(len(properties)):
        if types[i] is complex:
            p += 2
        else:
            p += 1

    n = len(objects)
    vals = np.zeros((n, p))
    extended_prop = [None] * p
    log_scale_extended = [None] * p
    for i, elem in enumerate(objects):
        a = 0
        for j in range(len(properties)):
            if types[j] is complex:
                val = getattr(elem, properties[j])
                vals[i, a] = val.real
                vals[i, a + 1] = val.imag
                extended_prop[a] = properties[j] + '.re'
                extended_prop[a + 1] = properties[j] + '.im'
                log_scale_extended[a] = log_scale[j]
                log_scale_extended[a + 1] = log_scale[j]
                a += 2
            else:
                vals[i, a] = getattr(elem, properties[j])
                extended_prop[a] = properties[j]
                log_scale_extended[a] = log_scale[j]
                a += 1

    # create figure if needed
    if fig is None:
        fig = plt.figure(figsize=(12, 6))
    fig.suptitle('Analysis of the ' + object_type, fontsize=16)
    fig.set_facecolor('white')

    if n > 0:
        k = int(np.round(math.sqrt(p)))
        axs = [None] * p

        for j in range(p):
            x = vals[:, j]
            mu = x.mean()
            variance = x.var()
            sigma = math.sqrt(variance)
            r = (mu - 6 * sigma, mu + 6 * sigma)

            # print checks
            l = np.where(x < r[0])[0]
            u = np.where(x > r[1])[0]

            # print(extended_prop[j], r, '\n\t', l, '\n\t', u)

            # plot
            axs[j] = fig.add_subplot(k, k + 1, j + 1)
            axs[j].set_facecolor('white')
            axs[j].hist(x, bins=100, range=r,
                        cumulative=False, bottom=None, histtype='bar',
                        align='mid', orientation='vertical')
            axs[j].plot(x, np.zeros(n), 'o')
            axs[j].set_title(extended_prop[j])

            if log_scale_extended[j]:
                axs[j].set_xscale('log')

    fig.tight_layout(rect=[0, 0.03, 1, 0.95])

