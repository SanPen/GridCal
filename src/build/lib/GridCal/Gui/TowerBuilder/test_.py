
import sys
from PySide2.QtWidgets import *
from PySide2 import QtCore, QtGui, QtWidgets


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
        self.beginRemoveRows(QtCore.QModelIndex(), index, index)
        self.wires.pop(index)
        self.endRemoveRows()

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
        wire = self.wires[index.row()]
        attr = self.index_prop[index.column()]
        setattr(wire, attr, value)


class TowerBuilderGUI(QtWidgets.QDialog):

    def __init__(self, parent=None):
        """
        Constructor
        Args:
            parent:
        """
        QtWidgets.QDialog.__init__(self, parent)
        self.setWindowTitle('Tower builder')

        # GUI objects
        self.setContextMenuPolicy(QtCore.Qt.NoContextMenu)
        self.layout = QVBoxLayout(self)
        self.wires_tableView = QTableView()
        self.add_wire_pushButton = QPushButton()
        self.add_wire_pushButton.setText('Add')
        self.delete_wire_pushButton = QPushButton()
        self.delete_wire_pushButton.setText('Delete')

        self.layout.addWidget(self.wires_tableView)
        self.layout.addWidget(self.add_wire_pushButton)
        self.layout.addWidget(self.delete_wire_pushButton)

        self.setLayout(self.layout)

        # Model
        self.wire_collection = WiresCollection(self)

        # set models
        self.wires_tableView.setModel(self.wire_collection)

        # button clicks
        self.add_wire_pushButton.clicked.connect(self.add_wire_to_collection)
        self.delete_wire_pushButton.clicked.connect(self.delete_wire_from_collection)

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
        wire = Wire(name=name, x=0, y=0, gmr=0, r=0.01)
        self.wire_collection.add(wire)

    def delete_wire_from_collection(self):
        """
        Delete wire from the collection
        :return:
        """
        idx = self.wires_tableView.currentIndex()
        sel_idx = idx.row()

        if sel_idx > -1:
            self.wire_collection.delete(sel_idx)
        else:
            self.msg('Select a wire in the wires collection')


if __name__ == "__main__":

    app = QtWidgets.QApplication(sys.argv)
    window = TowerBuilderGUI()
    window.show()
    sys.exit(app.exec_())

