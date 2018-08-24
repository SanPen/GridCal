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


class Wire:

    def __init__(self, name, x, y, gmr, r):
        self.name = name
        self.x = x
        self.y = y
        self.r = r
        self.gmr = gmr


class WiresCollection(QtCore.QAbstractTableModel):

    def __init__(self, parent=None):
        QtCore.QAbstractTableModel.__init__(self, parent)

        self.header = ['Name', 'R (Ohm/km)', 'GMR (m)']

        self.index_prop = {0: 'name', 1: 'r', 2: 'gmr'}

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
        self.beginRemoveRows(QtCore.QModelIndex(), row, row)
        self.wires.pop(index)
        self.endRemoveRows()

    def rowCount(self, parent=QtCore.QModelIndex()):
        return len(self.wires)

    def columnCount(self, parent=QtCore.QModelIndex()):
        return len(self.header)

    def index(self, row, column, parent=QtCore.QModelIndex(), *args, **kwargs):
        if self.hasIndex(row, column, parent):
            return self.createIndex(row, column, self.m_data[row])
        return QtCore.QModelIndex()

    def parent(self, index=None):
        return QtCore.QModelIndex()

    def data(self, index, role=QtCore.Qt.DisplayRole):
        if index.isValid():
            if role == QtCore.Qt.DisplayRole:
                val = getattr(self.wires[index.row()], self.index_prop(index.column()))
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
        wire = self.wires[index.row()]
        attr = self.index_prop[index.column()]
        setattr(wire, attr, value)


class Tower(QtCore.QAbstractTableModel):

    def __init__(self, parent=None):
        QtCore.QAbstractTableModel.__init__(self, parent)

        self.header = ['Wire', 'X (m)', 'Y (m)']

        self.index_prop = {0: 'name', 1: 'x', 2: 'y'}

        self.wires = list()

    def addWire(self, wire: Wire):
        self.wires.append(wire)

    def deleteWire(self, index):
        self.wires.pop(index)

    def rowCount(self, parent=None):
        return len(self.wires)

    def columnCount(self, parent=None):
        return len(self.header)

    def data(self, index, role=QtCore.Qt.DisplayRole):
        if index.isValid():
            if role == QtCore.Qt.DisplayRole:
                val = getattr(self.wires[index.row()], self.index_prop(index.column()))
                return str(val)
        return None

    def headerData(self, p_int, orientation, role):
        if role == QtCore.Qt.DisplayRole:
            if orientation == QtCore.Qt.Horizontal:
                return self.header[p_int]


class ProxyModel(QtCore.QSortFilterProxyModel):
    def __init__(self):
        super(ProxyModel, self).__init__()
        self.cb_status = True

    def cbChanged(self, arg=None):
        self.cb_status = arg
        print(self.cb_status)
        self.invalidateFilter()



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
        self.setWindowTitle('Tower builder')

        self.wire_collection = WiresCollection(self)

        self.tower = Tower(self)

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
            self.wire_collection.delete(sel_idx)
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
            selected_wire = self.wire_collection.wires[sel_idx]
            self.tower.addWire(selected_wire)
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
            self.tower.deleteWire(sel_idx)
        else:
            self.msg('Select a wire from the tower')

    def compute(self):
        pass

    def plot(self):
        pass


if __name__ == "__main__":

    app = QtWidgets.QApplication(sys.argv)
    window = TowerBuilderGUI()
    window.resize(1.61 * 700.0, 700.0)  # golden ratio
    window.show()
    sys.exit(app.exec_())

