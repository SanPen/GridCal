import os
import string
import sys
from enum import Enum
import PySide2

import numpy as np
import pandas as pd
from matplotlib import pyplot as plt
import math

from PySide2.QtWidgets import *

from GridCal.Gui.Analysis.gui import *
from GridCal.Gui.GuiFunctions import PandasModel, get_list_model
from GridCal.Engine.Core.multi_circuit import MultiCircuit
from GridCal.Engine.Devices import *


class GridErrorLog:

    def __init__(self, parent=None):

        self.logs = dict()

        self.header = ['Object type', 'Name', 'Index', 'Severity', 'Property', 'Value']

    def add(self, object_type, element_name, element_index, severity, propty, message, val=''):
        """

        :param object_type:
        :param element_name:
        :param element_index:
        :param severity:
        :param propty:
        :param message:
        :return:
        """

        e = [object_type, element_name, element_index, severity, propty, val]

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
            for object_type, element_name, element_index, severity, prop, val in entries:
                children = [QtGui.QStandardItem(str(object_type)),
                            QtGui.QStandardItem(str(element_name)),
                            QtGui.QStandardItem(str(element_index)),
                            QtGui.QStandardItem(str(severity)),
                            QtGui.QStandardItem(str(prop)),
                            QtGui.QStandardItem(str(val))]
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

            for [object_type, element_name, element_index, severity, propty, val] in items:
                data.append([message, object_type, element_name, element_index, severity, propty, val])

        hdr = ['Message', 'Object type', 'Name', 'Index', 'Severity', 'Property', 'Value']
        return pd.DataFrame(data=data, columns=hdr)

    def save(self, filename):
        """
        Save analysis to excel
        :param filename:
        :return:
        """
        df = self.get_df()
        df.to_excel(filename)


class GridAnalysisGUI(QtWidgets.QMainWindow):

    def __init__(self, parent=None, object_types=list(), circuit: MultiCircuit=None, use_native_dialogues=False):
        """
        Constructor
        Args:
            parent:
            object_types:
            circuit:
        """
        QtWidgets.QMainWindow.__init__(self, parent)
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        self.setWindowTitle('Grid analysis')

        # set the circuit
        self.circuit = circuit

        self.use_native_dialogues = use_native_dialogues

        # declare logs
        self.log = GridErrorLog()

        self.object_types = object_types

        # set the objects type model
        self.ui.objectsListView.setModel(get_list_model(object_types))

        # click
        # self.ui.doit_button.clicked.connect(self.analyze_click)

        # list click
        self.ui.objectsListView.clicked.connect(self.object_type_selected)

        # Actions
        self.ui.plotwidget.canvas.fig.clear()
        self.ui.plotwidget.get_figure().set_facecolor('white')
        self.ui.plotwidget.get_axis().set_facecolor('white')

        self.ui.actionSave_diagnostic.triggered.connect(self.save_diagnostic)

        self.analyze_all()

    def msg(self, text, title="Warning"):
        """
        Message box
        :param text: Text to display
        :param title: Name of the window
        """
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Information)
        msg.setText(text)
        # msg.setInformativeText("This is additional information")
        msg.setWindowTitle(title)
        # msg.setDetailedText("The details are as follows:")
        msg.setStandardButtons(QMessageBox.Ok)
        retval = msg.exec_()

    def plot_analysis(self, object_type, fig=None):
        """
        PLot data + histogram
        Args:
            object_type:
            fig:
        """

        if object_type == DeviceType.LineDevice.value:
            properties = ['R', 'X', 'B', 'rate']
            types = [float, float, float, float, float]
            log_scale = [False, False, False, False, False]
            objects = self.circuit.lines

        elif object_type == DeviceType.Transformer2WDevice.value:
            properties = ['R', 'X', 'G', 'B', 'tap_module', 'angle', 'rate']
            types = [float, float, float, float, float, float, float]
            log_scale = [False, False, False, False, False, False, False]
            objects = self.circuit.transformers2w

        elif object_type == DeviceType.BusDevice.value:
            properties = ['Vnom']
            types = [float]
            log_scale = [False]
            objects = self.circuit.buses

        elif object_type == DeviceType.GeneratorDevice.value:
            properties = ['Vset', 'P', 'Qmin', 'Qmax']
            log_scale = [False, False, False, False]
            types = [float, float, float, float]
            objects = self.circuit.get_generators()

        elif object_type == DeviceType.BatteryDevice.value:
            properties = ['Vset', 'P', 'Qmin', 'Qmax']
            log_scale = [False, False, False, False]
            types = [float, float, float, float]
            objects = self.circuit.get_batteries()

        elif object_type == DeviceType.StaticGeneratorDevice.value:
            properties = ['P', 'Q']
            log_scale = [False, False]
            types = [float, float]
            objects = self.circuit.get_static_generators()

        elif object_type == DeviceType.ShuntDevice.value:
            properties = ['G', 'B']
            log_scale = [False, False]
            types = [float, float]
            objects = self.circuit.get_shunts()

        elif object_type == DeviceType.LoadDevice.value:
            properties = ['P', 'Q', 'Ir', 'Ii', 'G', 'B']
            log_scale = [False, False, False, False, False, False]
            types = [float, float, float, float, float, float]
            objects = self.circuit.get_loads()

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

                print(extended_prop[j], r, '\n\t', l, '\n\t', u)

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

    def object_type_selected(self):
        """
        On click-plot
        Returns:

        """
        if len(self.ui.objectsListView.selectedIndexes()) > 0:
            obj_type = self.ui.objectsListView.selectedIndexes()[0].data()  # selected text
            self.ui.plotwidget.canvas.fig.clear()
            self.plot_analysis(object_type=obj_type, fig=self.ui.plotwidget.get_figure())
            self.ui.plotwidget.redraw()
        else:
            self.msg('Select a data structure')

    def analyze_all(self, imbalance_threshold=0.02, v_low=0.95, v_high=1.05):
        """
        Analyze the model data
        :param imbalance_threshold: Allowed percentage of imbalance
        :param v_low: lower voltage setting
        :param v_high: higher voltage setting
        :return:
        """
        if self.circuit.time_profile is not None:
            nt = len(self.circuit.time_profile)
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
        self.log = GridErrorLog()

        for object_type in self.object_types:

            if object_type == DeviceType.LineDevice.value:
                elements = self.circuit.lines

                for i, elm in enumerate(elements):

                    V1 = min(elm.bus_to.Vnom, elm.bus_from.Vnom)
                    V2 = max(elm.bus_to.Vnom, elm.bus_from.Vnom)

                    s = '[' + str(V1) + '-' + str(V2) + ']'

                    if V1 > 0 and V2 > 0:
                        per = V1 / V2
                        if per < 0.9:
                            self.log.add(object_type='Line', element_name=elm.name, element_index=i,
                                         severity='High',
                                         propty='Connection',
                                         message='The branch is connected between voltages '
                                                 'that differ in 10% or more. Should this be a transformer?' + s)
                    else:
                        self.log.add(object_type='Line', element_name=elm.name, element_index=i, severity='High',
                                     propty='Voltage', message='The branch does is connected to a bus with '
                                                               'Vnom=0, this is terrible.' + s)

                    if elm.name == '':
                        self.log.add(object_type='Line', element_name=elm.name, element_index=i, severity='Low',
                                     propty='name', message='The branch does not have a name')

                    if elm.rate < 0.0:
                        self.log.add(object_type='Line', element_name=elm.name, element_index=i, severity='High',
                                     propty='rate', message='The rating is negative. This cannot be.')
                    elif elm.rate == 0.0:
                        self.log.add(object_type='Line', element_name=elm.name, element_index=i, severity='High',
                                     propty='rate', message='There is no nominal power, this is bad.')

                    if elm.R < 0.0:
                        self.log.add(object_type='Line', element_name=elm.name, element_index=i,
                                     severity='High',
                                     propty='R', message='The resistance is negative, that cannot be.')
                    elif elm.R == 0.0:
                        self.log.add(object_type='Line', element_name=elm.name, element_index=i,
                                     severity='Low',
                                     propty='R', message='The resistance is exactly zero.')
                    if elm.X == 0.0:
                        self.log.add(object_type='Line', element_name=elm.name, element_index=i,
                                     severity='High',
                                     propty='X',
                                     message='The reactance is exactly zero. This hurts numerical conditioning.')

                    if elm.B == 0.0:
                        self.log.add(object_type='Line', element_name=elm.name, element_index=i, severity='High',
                                     propty='B',
                                     message='There is no susceptance, this hurts numerical conditioning.')

            elif object_type in DeviceType.Transformer2WDevice.value:
                elements = self.circuit.transformers2w

                for i, elm in enumerate(elements):

                    if elm.name == '':
                        self.log.add(object_type='Transformer2W', element_name=elm.name, element_index=i,
                                     severity='High', propty='name', message='The branch does not have a name')

                    if elm.rate <= 0.0:
                        self.log.add(object_type='Transformer2W', element_name=elm.name, element_index=i,
                                     severity='High', propty='rate', message='There is no nominal power',
                                     val=elm.rate)

                    if elm.R == 0.0 and elm.X == 0.0:
                        self.log.add(object_type='Transformer2W', element_name=elm.name, element_index=i,
                                     severity='High', propty='R+X',
                                     message='There is no impedance, set at least a very low value')

                    else:
                        if elm.R < 0.0:
                            self.log.add(object_type='Transformer2W', element_name=elm.name, element_index=i,
                                         severity='Medium', propty='R',
                                         message='The resistance is negative, that cannot be.', val=elm.R)
                        elif elm.R == 0.0:
                            self.log.add(object_type='Transformer2W', element_name=elm.name, element_index=i,
                                         severity='Low', propty='R', message='The resistance is exactly zero',
                                         val=elm.R)
                        elif elm.X == 0.0:
                            self.log.add(object_type='Transformer2W', element_name=elm.name, element_index=i,
                                         severity='Low', propty='X', message='The reactance is exactly zero',
                                         val=elm.R)

                    tap_f, tap_t = elm.get_virtual_taps()

                    if 0.95 > tap_f or tap_f > 1.05:
                        self.log.add(object_type='Transformer2W', element_name=elm.name, element_index=i,
                                     severity='High', propty='HV or LV',
                                     message='Large nominal voltage mismatch at the from bus', val=tap_f)
                    if 0.95 > tap_t or tap_t > 1.05:
                        self.log.add(object_type='Transformer2W', element_name=elm.name, element_index=i,
                                     severity='High', propty='HV or LV',
                                     message='Large nominal voltage mismatch at the to bus', val=tap_t)

            elif object_type == DeviceType.BusDevice.value:
                elements = self.circuit.buses
                names = set()

                for i, elm in enumerate(elements):

                    qmin, qmax = elm.get_reactive_power_limits()
                    Qmin += qmin
                    Qmax += qmax

                    if elm.Vnom <= 0.0:
                        self.log.add(object_type='Bus', element_name=elm.name, element_index=i, severity='High',
                                     propty='Vnom', message='The nominal voltage is <= 0, this causes problems',
                                     val=elm.Vnom)

                    if elm.name == '':
                        self.log.add(object_type='Bus', element_name=elm.name, element_index=i, severity='High',
                                     propty='name', message='The bus does not have a name')

                    if elm.name in names:
                        self.log.add(object_type='Bus', element_name=elm.name, element_index=i, severity='Low',
                                     propty='name', message='The bus name is not unique')

                    # add the name to a set
                    names.add(elm.name)

            elif object_type == DeviceType.GeneratorDevice.value:

                elements = self.circuit.get_generators()

                for k, obj in enumerate(elements):
                    Pg += obj.P * obj.active

                    if self.circuit.time_profile is not None:
                        Pg_prof += obj.P_prof * obj.active_prof

                    if obj.Vset < v_low:
                        self.log.add(object_type='Generator',
                                     element_name=obj,
                                     element_index=k,
                                     severity='Medium',
                                     propty='Vset=' + str(obj.Vset) + '<' + str(v_low),
                                     message='The set point looks too low',
                                     val=obj.Vset)
                    elif obj.Vset > v_high:
                        self.log.add(object_type='Generator',
                                     element_name=obj,
                                     element_index=k,
                                     severity='Medium',
                                     propty='Vset=' + str(obj.Vset) + '>' + str(v_high),
                                     message='The set point looks too high',
                                     val=obj.Vset)

            elif object_type == DeviceType.BatteryDevice.value:
                elements = self.circuit.get_batteries()

                for obj in elements:
                    Pg += obj.P * obj.active

                    if self.circuit.time_profile is not None:
                        Pg_prof += obj.P_prof * obj.active_prof

            elif object_type == DeviceType.StaticGeneratorDevice.value:
                elements = self.circuit.get_static_generators()

                for k, obj in enumerate(elements):
                    Pg += obj.P * obj.active
                    Qg += obj.Q * obj.active

                    if self.circuit.time_profile is not None:
                        Pg_prof += obj.P_prof * obj.active_prof
                        Qg_prof += obj.Q_prof * obj.active_prof

            elif object_type == DeviceType.ShuntDevice.value:
                elements = self.circuit.get_shunts()

            elif object_type == DeviceType.LoadDevice.value:
                elements = self.circuit.get_loads()

                for obj in elements:
                    Pl += obj.P * obj.active
                    Ql += obj.Q * obj.active

                    if self.circuit.time_profile is not None:
                        Pl_prof += obj.P_prof * obj.active_prof
                        Ql_prof += obj.Q_prof * obj.active_prof

        # compare loads
        p_ratio = abs(Pl - Pg) / (Pl + 1e-20)

        if p_ratio > imbalance_threshold:
            msg = "{:.1f}".format(p_ratio * 100) + "% >> " + str(imbalance_threshold) + "%"
            self.log.add(object_type='Grid snapshot',
                         element_name=self.circuit,
                         element_index=-1,
                         severity='High',
                         propty='Active power balance ' + msg,
                         message='There is too much active power imbalance')

        # compare reactive power limits
        if not (Qmin <= -Ql <= Qmax):
            msg = "Reactive power out of bounds {0}<={1}<={2}".format(Qmin, Ql, Qmax)
            self.log.add(object_type='Grid snapshot',
                         element_name=self.circuit,
                         element_index=-1,
                         severity='High',
                         propty='Reactive power power balance ' + msg,
                         message='There is too much reactive power imbalance')

        if self.circuit.time_profile is not None:
            nt = len(self.circuit.time_profile)
            for t in range(nt):

                # compare loads
                p_ratio = abs(Pl_prof[t] - Pg_prof[t]) / (Pl_prof[t] + 1e-20)
                if p_ratio > imbalance_threshold:
                    msg = "{:.1f}".format(p_ratio * 100) + "% >> " + str(imbalance_threshold) + "%"
                    self.log.add(object_type='Active power balance',
                                 element_name=self.circuit,
                                 element_index=t,
                                 severity='High',
                                 propty=msg,
                                 message='There is too much active power imbalance')

                # compare reactive power limits
                if not (Qmin <= -Ql_prof[t] <= Qmax):
                    msg = "Reactive power out of bounds {0}<={1}<={2}".format(Qmin, Ql, Qmax)
                    self.log.add(object_type='Reactive power power balance',
                                 element_name=self.circuit,
                                 element_index=t,
                                 severity='High',
                                 propty=msg,
                                 message='There is too much reactive power imbalance')

        # set logs
        self.ui.logsTreeView.setModel(self.log.get_model())
        print('Done!')

    def save_diagnostic(self):

        files_types = "Excel (*.xlsx)"

        options = QFileDialog.Options()
        if self.use_native_dialogues:
            options |= QFileDialog.DontUseNativeDialog

        fname = 'Grid error analysis.xlsx'

        filename, type_selected = QFileDialog.getSaveFileName(self, 'Save file', fname, files_types,
        options = options)

        if filename != '':
            self.log.save(filename)

if __name__ == "__main__":

    app = QtWidgets.QApplication(sys.argv)
    window = GridAnalysisGUI()
    window.resize(1.61 * 700.0, 700.0)  # golden ratio
    window.show()
    sys.exit(app.exec_())

