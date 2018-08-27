import os
import string
import sys
from enum import Enum

import numpy as np
import pandas as pd
from matplotlib import pyplot as plt
import math
from PyQt5.QtWidgets import *

from GridCal.Gui.LineBuilder.gui import *
from GridCal.Gui.LineBuilder.line_parameters import *
from GridCal.Gui.GuiFunctions import PandasModel


class WiresCollection(QtCore.QAbstractTableModel):

    def __init__(self, parent=None):
        QtCore.QAbstractTableModel.__init__(self, parent)

        self.header = ['Name', 'R (Ohm/km)', 'GMR (m)']

        self.index_prop = {0: 'name', 1: 'r', 2: 'gmr'}

        self.converter = {0: str, 1: float, 2: float}

        self.editable = [True, True, True]

        self.wires = list()

    def add(self, wire: Wire):
        """
        Add wire
        :param wire:
        :return:
        """
        row = len(self.wires)
        self.beginInsertRows(QtCore.QModelIndex(), row, row)
        self.wires.append(wire)
        self.endInsertRows()

    def delete(self, index):
        """
        Delete wire
        :param index:
        :return:
        """
        row = len(self.wires)
        self.beginRemoveRows(QtCore.QModelIndex(), row - 1, row - 1)
        self.wires.pop(index)
        self.endRemoveRows()

    def is_used(self, name):
        """
        checks if the name is used
        """
        n = len(self.wires)
        for i in range(n-1, -1, -1):
            if self.wires[i].name == name:
                return True
        return False

    def flags(self, index):
        if self.editable[index.column()]:
            return QtCore.Qt.ItemIsEditable | QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable
        else:
            return QtCore.Qt.ItemIsEnabled

    def rowCount(self, parent=QtCore.QModelIndex()):
        return len(self.wires)

    def columnCount(self, parent=QtCore.QModelIndex()):
        return len(self.header)

    def parent(self, index=None):
        return QtCore.QModelIndex()

    def data(self, index, role=QtCore.Qt.DisplayRole):
        if index.isValid():
            if role == QtCore.Qt.DisplayRole:
                val = getattr(self.wires[index.row()], self.index_prop[index.column()])
                return str(val)
        return None

    def headerData(self, p_int, orientation, role):
        if role == QtCore.Qt.DisplayRole:
            if orientation == QtCore.Qt.Horizontal:
                return self.header[p_int]

    def setData(self, index, value, role=QtCore.Qt.DisplayRole):
        """
        Set data by simple editor (whatever text)
        :param index:
        :param value:
        :param role:
        """
        if self.editable[index.column()]:
            wire = self.wires[index.row()]
            attr = self.index_prop[index.column()]

            if attr == 'name':
                if self.is_used(value):
                    pass
                else:
                    setattr(wire, attr, self.converter[index.column()](value))
            else:
                setattr(wire, attr, self.converter[index.column()](value))

        return True


class Tower(QtCore.QAbstractTableModel):

    def __init__(self, parent=None, edit_callback=None):
        QtCore.QAbstractTableModel.__init__(self, parent)

        self.header = ['Wire', 'X (m)', 'Y (m)', 'Phase', 'Ri (Ohm/km)', 'Xi (Ohm/km)', 'GMR (m)']

        self.index_prop = {0: 'name', 1: 'xpos', 2: 'ypos', 3: 'phase', 4: 'r', 5: 'x', 6: 'gmr'}

        self.converter = {0: str, 1: float, 2: float, 3: int, 4: float, 5: float, 6:float}

        self.editable = [False, True, True, True, True, True, True]

        self.wires = list()

        self.edit_callback = edit_callback

    def add(self, wire: Wire):
        """
        Add wire
        :param wire:
        :return:
        """
        row = len(self.wires)
        self.beginInsertRows(QtCore.QModelIndex(), row, row)
        self.wires.append(wire)
        self.endInsertRows()

    def delete(self, index):
        """
        Delete wire
        :param index:
        :return:
        """
        row = len(self.wires)
        self.beginRemoveRows(QtCore.QModelIndex(), row - 1, row - 1)
        self.wires.pop(index)
        self.endRemoveRows()

    def plot(self, ax=None):

        if ax is None:
            fig = plt.Figure(figsize=(12, 6))
            ax = fig.add_subplot(1, 1, 1)

        n = len(self.wires)
        x = np.zeros(n)
        y = np.zeros(n)
        for i, wire in enumerate(self.wires):
            x[i] = wire.xpos
            y[i] = wire.ypos

        ax.plot(x, y, '.')
        ax.set_title('Tower wire position')
        ax.set_xlabel('m')
        ax.set_ylabel('m')
        ax.set_xlim([min(0, np.min(x) - 1), np.max(x) + 1])
        ax.set_ylim([0, np.max(y) + 1])

    def delete_by_name(self, wire: Wire):
        n = len(self.wires)
        for i in range(n-1, -1, -1):
            if self.wires[i].name == wire.name:
                self.delete(i)

    def is_used(self, wire: Wire):
        n = len(self.wires)
        for i in range(n-1, -1, -1):
            if self.wires[i].name == wire.name:
                return True

    def flags(self, index):
        if self.editable[index.column()]:
            return QtCore.Qt.ItemIsEditable | QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable
        else:
            return QtCore.Qt.ItemIsEnabled

    def rowCount(self, parent=None):
        return len(self.wires)

    def columnCount(self, parent=None):
        return len(self.header)

    def data(self, index, role=QtCore.Qt.DisplayRole):
        if index.isValid():
            if role == QtCore.Qt.DisplayRole:
                val = getattr(self.wires[index.row()], self.index_prop[index.column()])
                return str(val)
        return None

    def headerData(self, p_int, orientation, role):
        if role == QtCore.Qt.DisplayRole:
            if orientation == QtCore.Qt.Horizontal:
                return self.header[p_int]

    def setData(self, index, value, role=QtCore.Qt.DisplayRole):
        """
        Set data by simple editor (whatever text)
        :param index:
        :param value:
        :param role:
        """
        if self.editable[index.column()]:
            wire = self.wires[index.row()]
            attr = self.index_prop[index.column()]

            try:
                val = self.converter[index.column()](value)
            except:
                val = 0

            # correct the phase to the correct range
            if attr == 'phase':
                if val < 0 or val > 3:
                    val = 0

            setattr(wire, attr, val)

            if self.edit_callback is not None:
                self.edit_callback()

        return True


class TowerBuilderGUI(QtWidgets.QDialog):

    def __init__(self, parent=None):
        """
        Constructor
        Args:
            parent:
        """
        QtWidgets.QDialog.__init__(self, parent)
        self.ui = Ui_Dialog()
        self.ui.setupUi(self)
        self.setWindowTitle('Line builder')

        self.wire_collection = WiresCollection(self)

        self.tower = Tower(self, edit_callback=self.plot)

        # set models
        self.ui.wires_tableView.setModel(self.wire_collection)
        self.ui.tower_tableView.setModel(self.tower)

        # button clicks
        self.ui.add_wire_pushButton.clicked.connect(self.add_wire_to_collection)
        self.ui.delete_wire_pushButton.clicked.connect(self.delete_wire_from_collection)
        self.ui.add_to_tower_pushButton.clicked.connect(self.add_wire_to_tower)
        self.ui.delete_from_tower_pushButton.clicked.connect(self.delete_wire_from_tower)
        self.ui.compute_pushButton.clicked.connect(self.compute)

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

    def add_wire_to_collection(self):
        """
        Add new wire to collection
        :return:
        """
        name = 'Wire_' + str(len(self.wire_collection.wires) + 1)
        wire = Wire(name, x=0, y=0, gmr=0, r=0.01)
        self.wire_collection.add(wire)

    def delete_wire_from_collection(self):
        """
        Delete wire from the collection
        :return:
        """
        idx = self.ui.wires_tableView.currentIndex()
        sel_idx = idx.row()

        if sel_idx > -1:

            # delete all the wires from the tower too
            self.tower.delete_by_name(self.wire_collection.wires[sel_idx])

            # delete from the catalogue
            self.wire_collection.delete(sel_idx)

            self.plot()
        else:
            self.msg('Select a wire in the wires collection')

    def add_wire_to_tower(self):
        """
        Add wire to tower
        :return:
        """
        idx = self.ui.wires_tableView.currentIndex()
        sel_idx = idx.row()

        if sel_idx > -1:
            selected_wire = self.wire_collection.wires[sel_idx].copy()
            self.tower.add(selected_wire)
        else:
            self.msg('Select a wire in the wires collection')

    def delete_wire_from_tower(self):
        """
        Delete wire from the tower
        :return:
        """
        idx = self.ui.tower_tableView.currentIndex()
        sel_idx = idx.row()

        if sel_idx > -1:
            self.tower.delete(sel_idx)

            self.plot()
        else:
            self.msg('Select a wire from the tower')

    def compute(self):

        f = 50
        rho = 100

        # Impedances
        z_abcn, phases_abcn, z_abc, phases_abc, z_seq = calc_z_matrix(self.tower.wires, f=f, rho=rho)

        cols = ['Phase' + str(i) for i in phases_abcn]
        z_df = pd.DataFrame(data=z_abcn, columns=cols, index=cols)
        self.ui.z_tableView_abcn.setModel(PandasModel(z_df))

        cols = ['Phase' + str(i) for i in phases_abc]
        z_df = pd.DataFrame(data=z_abc, columns=cols, index=cols)
        self.ui.z_tableView_abc.setModel(PandasModel(z_df))

        cols = ['Sequence ' + str(i) for i in range(3)]
        z_df = pd.DataFrame(data=z_seq, columns=cols, index=cols)
        self.ui.z_tableView_seq.setModel(PandasModel(z_df))

        # Admittances
        y_abcn, phases_abcn, y_abc, phases_abc, y_seq = calc_y_matrix(self.tower.wires, f=f, rho=rho)

        cols = ['Phase' + str(i) for i in phases_abcn]
        z_df = pd.DataFrame(data=y_abcn * 1e-6, columns=cols, index=cols)
        self.ui.y_tableView_abcn.setModel(PandasModel(z_df))

        cols = ['Phase' + str(i) for i in phases_abc]
        z_df = pd.DataFrame(data=y_abc * 1e-6, columns=cols, index=cols)
        self.ui.y_tableView_abc.setModel(PandasModel(z_df))

        cols = ['Sequence ' + str(i) for i in range(3)]
        z_df = pd.DataFrame(data=y_seq * 1e-6, columns=cols, index=cols)
        self.ui.y_tableView_seq.setModel(PandasModel(z_df))

        self.plot()

    def plot(self):

        self.ui.plotwidget.clear()
        ax = self.ui.plotwidget.get_axis()
        self.tower.plot(ax=ax)
        self.ui.plotwidget.redraw()

    def example_1(self):
        name = '4/0 6/1 ACSR'
        r = 0.367851632  # ohm / km
        x = 0  # ohm / km
        gmr = 0.002481072  # m

        self.tower.add(Wire(name, xpos=0, ypos=8.8392, gmr=gmr, r=r, x=x, phase=0))
        self.tower.add(Wire(name, xpos=0.762, ypos=8.8392, gmr=gmr, r=r, x=x, phase=1))
        self.tower.add(Wire(name, xpos=2.1336, ypos=8.8392, gmr=gmr, r=r, x=x, phase=2))
        self.tower.add(Wire(name, xpos=1.2192, ypos=7.62, gmr=gmr, r=r, x=x, phase=3))

    def example_2(self):
        name = '4/0 6/1 ACSR'
        r = 0.367851632  # ohm / km
        x = 0  # ohm / km
        gmr = 0.002481072  # m

        incx = 0.1
        incy = 0.1

        self.tower.add(Wire(name, xpos=0,      ypos=8.8392, gmr=gmr, r=r, x=x, phase=1))
        self.tower.add(Wire(name, xpos=0.762,  ypos=8.8392, gmr=gmr, r=r, x=x, phase=2))
        self.tower.add(Wire(name, xpos=2.1336, ypos=8.8392, gmr=gmr, r=r, x=x, phase=3))
        self.tower.add(Wire(name, xpos=1.2192, ypos=7.62,   gmr=gmr, r=r, x=x, phase=0))

        self.tower.add(Wire(name, xpos=incx+0, ypos=8.8392, gmr=gmr, r=r, x=x, phase=1))
        self.tower.add(Wire(name, xpos=incx+0.762, ypos=8.8392, gmr=gmr, r=r, x=x, phase=2))
        self.tower.add(Wire(name, xpos=incx+2.1336, ypos=8.8392, gmr=gmr, r=r, x=x, phase=3))
        # self.tower.add(Wire(name, xpos=incx+1.2192, ypos=7.62, gmr=gmr, r=r, x=x, phase=0))

        self.tower.add(Wire(name, xpos=incx/2 + 0,    ypos=incy+8.8392, gmr=gmr, r=r, x=x, phase=1))
        self.tower.add(Wire(name, xpos=incx/2 + 0.762, ypos=incy+8.8392, gmr=gmr, r=r, x=x, phase=2))
        self.tower.add(Wire(name, xpos=incx/2 + 2.1336, ypos=incy+8.8392, gmr=gmr, r=r, x=x, phase=3))
        # self.tower.add(Wire(name, xpos=incx/2 + 1.2192, ypos=incy+7.62, gmr=gmr, r=r, x=x, phase=0))


if __name__ == "__main__":

    app = QtWidgets.QApplication(sys.argv)
    window = TowerBuilderGUI()

    window.example_2()
    window.compute()

    window.resize(1.61 * 700.0, 700.0)  # golden ratio
    window.show()
    sys.exit(app.exec_())

