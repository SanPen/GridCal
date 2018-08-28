import os
import string
import sys
from enum import Enum

import numpy as np
import pandas as pd
from matplotlib import pyplot as plt
import math
from PyQt5.QtWidgets import *

from GridCal.Gui.Analysis.gui import *
from GridCal.Engine.CalculationEngine import MultiCircuit, BranchType


class PandasModel(QtCore.QAbstractTableModel):
    """
    Class to populate a Qt table view with a pandas data frame
    """
    def __init__(self, data, parent=None):
        QtCore.QAbstractTableModel.__init__(self, parent)
        self._data = np.array(data.values)
        self._cols = data.columns
        self.index = data.index.values
        self.r, self.c = np.shape(self._data)
        self.isDate = False
        if isinstance(self.index[0], np.datetime64):
            self.index = pd.to_datetime(self.index)
            self.isDate = True

        self.formatter = lambda x: "%.2f" % x

    def rowCount(self, parent=None):
        return self.r

    def columnCount(self, parent=None):
        return self.c

    def data(self, index, role=QtCore.Qt.DisplayRole):
        if index.isValid():
            if role == QtCore.Qt.DisplayRole:
                # return self.formatter(self._data[index.row(), index.column()])
                return str(self._data[index.row(), index.column()])
        return None

    def headerData(self, p_int, orientation, role):
        if role == QtCore.Qt.DisplayRole:
            if orientation == QtCore.Qt.Horizontal:
                return self._cols[p_int]
            elif orientation == QtCore.Qt.Vertical:
                if self.index is None:
                    return p_int
                else:
                    if self.isDate:
                        return self.index[p_int].strftime('%Y/%m/%d  %H:%M.%S')
                    else:
                        return str(self.index[p_int])
        return None


def get_list_model(iterable):
    """
    get Qt list model from a simple iterable
    :param iterable: 
    :return: List model
    """
    list_model = QtGui.QStandardItemModel()
    if iterable is not None:
        for val in iterable:
            # for the list model
            item = QtGui.QStandardItem(val)
            item.setEditable(False)
            list_model.appendRow(item)
    return list_model


class GridErrorLog(QtCore.QAbstractTableModel):

    def __init__(self, parent=None):

        QtCore.QAbstractTableModel.__init__(self, parent)

        self.logs = list()

        self.header = ['Object type', 'Name', 'Index', 'Severity', 'Property', 'Message']

    def add(self, object_type, element_name, element_index, severity, property, message):

        self.logs.append([object_type, element_name, element_index, severity, property, message])

    def clear(self):
        """
        Delete all logs
        """
        self.logs = list()

    def rowCount(self, parent=None):
        return len(self.logs)

    def columnCount(self, parent=None):
        return len(self.header)

    def data(self, index, role=QtCore.Qt.DisplayRole):
        if index.isValid():
            if role == QtCore.Qt.DisplayRole:
                # return self.formatter(self._data[index.row(), index.column()])
                return str(self.logs[index.row()][index.column()])
        return None

    def headerData(self, p_int, orientation, role):
        if role == QtCore.Qt.DisplayRole:
            if orientation == QtCore.Qt.Horizontal:
                return self.header[p_int]


class GridAnalysisGUI(QtWidgets.QDialog):

    def __init__(self, parent=None, object_types=list(), circuit: MultiCircuit=None):
        """
        Constructor
        Args:
            parent:
            object_types:
            circuit:
        """
        QtWidgets.QDialog.__init__(self, parent)
        self.ui = Ui_Dialog()
        self.ui.setupUi(self)
        self.setWindowTitle('Grid analysis')

        # set the circuit
        self.circuit = circuit

        # declare logs
        self.log = GridErrorLog()

        self.object_types = object_types

        # set logs
        self.ui.logsTableView.setModel(self.log)

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
        self.analyze_click()

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

        if object_type == 'branches':
            properties = ['R', 'X', 'G', 'B', 'rate']
            types = [float, float, float, float, float]
            # log_scale = [True, True, True, True, False]
            log_scale = [False, False, False, False, False]
            objects = self.circuit.branches

        elif object_type == 'buses':
            properties = ['Vnom']
            types = [float]
            log_scale = [False]
            objects = self.circuit.buses

        elif object_type == 'controlled generators':
            properties = ['Vset', 'P', 'Qmin', 'Qmax']
            log_scale = [False, False, False, False]
            types = [float, float, float, float]
            objects = self.circuit.get_controlled_generators()

        elif object_type == 'batteries':
            properties = ['Vset', 'P', 'Qmin', 'Qmax']
            log_scale = [False, False, False, False]
            types = [float, float, float, float]
            objects = self.circuit.get_batteries()

        elif object_type == 'static generators':
            properties = ['S']
            log_scale = [False]
            types = [complex]
            objects = self.circuit.get_static_generators()

        elif object_type == 'shunts':
            properties = ['Y']
            log_scale = [False]
            types = [complex]
            objects = self.circuit.get_shunts()

        elif object_type == 'loads':
            properties = ['S', 'I', 'Z']
            log_scale = [False, False, False]
            types = [complex, complex, complex]
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
            k = int(math.sqrt(p))
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
                axs[j].hist(x, bins=100, range=r, density=None, weights=None,
                            cumulative=False, bottom=None, histtype='bar',
                            align='mid', orientation='vertical')
                axs[j].plot(x, np.zeros(n), 'o')
                axs[j].set_title(extended_prop[j])

                if log_scale_extended[j]:
                    axs[j].set_xscale('log')

    def object_type_selected(self):
        """
        On click-plot
        Returns:

        """
        if len(self.ui.objectsListView.selectedIndexes()) > 0:
            obj_type = self.ui.objectsListView.selectedIndexes()[0].data().lower()  # selected text
            self.ui.plotwidget.canvas.fig.clear()
            self.plot_analysis(object_type=obj_type, fig=self.ui.plotwidget.get_figure())
            self.ui.plotwidget.redraw()
        else:
            self.msg('Select a data structure')

    def analyze_object_type(self, object_type):
        """
        Analyze all
        """
        # analyze buses

        if object_type == 'branches':
            properties = ['R', 'X', 'G', 'B', 'rate']
            types = [float, float, float, float, float]
            # log_scale = [True, True, True, True, False]
            log_scale = [False, False, False, False, False]
            objects = self.circuit.branches

            for i, elm in enumerate(objects):

                if elm.branch_type != BranchType.Transformer:
                    V1 = min(elm.bus_to.Vnom, elm.bus_from.Vnom)
                    V2 = max(elm.bus_to.Vnom, elm.bus_from.Vnom)

                    s = '[' + str(V1) + '-' + str(V2) + ']'

                    if V1 > 0 and V2 > 0:
                        per = V1 / V2
                        if per < 0.9:
                            self.log.add(object_type='Branch', element_name=elm.name, element_index=i, severity='High',
                                         property='Connection', message='The branch if connected between a voltage that differs in 10% or more. Should this not be a transformer?' + s)
                    else:
                        self.log.add(object_type='Branch', element_name=elm.name, element_index=i, severity='High',
                                     property='Voltage', message='The branch does is connected to a bus with Vnom=0, this is terrible.' + s)

                if elm.name == '':
                    self.log.add(object_type='Branch', element_name=elm.name, element_index=i, severity='High',
                                 property='name', message='The branch does not have a name')

                if elm.rate <= 0.0:
                    self.log.add(object_type='Branch', element_name=elm.name, element_index=i, severity='High',
                                 property='rate', message='There is no nominal power')

                if elm.R == 0.0 and elm.X == 0.0:
                    self.log.add(object_type='Branch', element_name=elm.name, element_index=i, severity='High',
                                 property='R+X', message='There is no impedance, set at least a very low value')

                else:
                    if elm.R < 0.0:
                        self.log.add(object_type='Branch', element_name=elm.name, element_index=i, severity='Medium',
                                     property='R', message='There resistance is negative')
                    elif elm.R == 0.0:
                        self.log.add(object_type='Branch', element_name=elm.name, element_index=i, severity='Low',
                                     property='R', message='There resistance is exactly zero')
                    elif elm.X == 0.0:
                        self.log.add(object_type='Branch', element_name=elm.name, element_index=i, severity='Low',
                                     property='X', message='There reactance is exactly zero')

        elif object_type == 'buses':
            properties = ['Vnom']
            types = [float]
            log_scale = [False]
            objects = self.circuit.buses

            names = set()

            for i, elm in enumerate(objects):

                if elm.Vnom <= 0.0:
                    self.log.add(object_type='Bus', element_name=elm.name, element_index=i, severity='High',
                                 property='Vnom', message='The nominal voltage is <= 0, this causes problems')

                if elm.name == '':
                    self.log.add(object_type='Bus', element_name=elm.name, element_index=i, severity='High',
                                 property='name', message='The bus does not have a name')

                if elm.name in names:
                    self.log.add(object_type='Bus', element_name=elm.name, element_index=i, severity='High',
                                 property='name', message='The bus name is not unique')

                # add the name to a set
                names.add(elm.name)

        elif object_type == 'controlled generators':
            properties = ['Vset', 'P', 'Qmin', 'Qmax']
            log_scale = [False, False, False, False]
            types = [float, float, float, float]
            objects = self.circuit.get_controlled_generators()

        elif object_type == 'batteries':
            properties = ['Vset', 'P', 'Qmin', 'Qmax']
            log_scale = [False, False, False, False]
            types = [float, float, float, float]
            objects = self.circuit.get_batteries()

        elif object_type == 'static generators':
            properties = ['S']
            log_scale = [False]
            types = [complex]
            objects = self.circuit.get_static_generators()

        elif object_type == 'shunts':
            properties = ['Y']
            log_scale = [False]
            types = [complex]
            objects = self.circuit.get_shunts()

        elif object_type == 'loads':
            properties = ['S', 'I', 'Z']
            log_scale = [False, False, False]
            types = [complex, complex, complex]
            objects = self.circuit.get_loads()

        else:
            return

    def analyze_click(self):
        """
        Analyze all the circuit data
        """

        print('Analyzing...')
        # declare logs
        self.log = GridErrorLog()

        for tpe in self.object_types:
            print('Analyzing...', tpe)
            self.analyze_object_type(tpe.lower())

        # set logs
        self.ui.logsTableView.setModel(self.log)
        print('Done!')


if __name__ == "__main__":

    app = QtWidgets.QApplication(sys.argv)
    window = GridAnalysisGUI()
    window.resize(1.61 * 700.0, 700.0)  # golden ratio
    window.show()
    sys.exit(app.exec_())

