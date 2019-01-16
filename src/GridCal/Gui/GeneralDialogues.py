# This file is part of GridCal.
#
# GridCal is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# GridCal is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with GridCal.  If not, see <http://www.gnu.org/licenses/>.

from enum import Enum
from datetime import datetime, timedelta
from PyQt5 import QtCore, QtGui, QtWidgets



def get_list_model(lst, checks=False):
    """
    Pass a list to a list model
    """
    list_model = QtGui.QStandardItemModel()
    if lst is not None:
        if not checks:
            for val in lst:
                # for the list model
                item = QtGui.QStandardItem(str(val))
                item.setEditable(False)
                list_model.appendRow(item)
        else:
            for val in lst:
                # for the list model
                item = QtGui.QStandardItem(str(val))
                item.setEditable(False)
                item.setCheckable(True)
                item.setCheckState(QtCore.Qt.Checked)
                list_model.appendRow(item)

    return list_model


class ProfileTypes(Enum):
    Loads = 1,
    Generators = 2


class NewProfilesStructureDialogue(QtWidgets.QDialog):
    """
    New profile dialogue window
    """
    def __init__(self):
        super(NewProfilesStructureDialogue, self).__init__()
        self.setObjectName("self")
        # self.resize(200, 71)
        # self.setMinimumSize(QtCore.QSize(200, 71))
        # self.setMaximumSize(QtCore.QSize(200, 71))
        self.setContextMenuPolicy(QtCore.Qt.NoContextMenu)
        # icon = QtGui.QIcon()
        # icon.addPixmap(QtGui.QPixmap("Icons/Plus-32.png"), QtGui.QIcon.Normal, QtGui.QIcon.Off)
        # self.setWindowIcon(icon)
        self.layout = QtWidgets.QVBoxLayout(self)

        # calendar
        self.calendar = QtWidgets.QDateTimeEdit()
        d = datetime.today()
        self.calendar.setDateTime(QtCore.QDateTime(d.year, 1, 1, 00, 00, 00))

        # number of time steps
        self.steps_spinner = QtWidgets.QSpinBox()
        self.steps_spinner.setMinimum(1)
        self.steps_spinner.setMaximum(9999999)
        self.steps_spinner.setValue(1)

        # time step length
        self.step_length = QtWidgets.QDoubleSpinBox()
        self.step_length.setMinimum(1)
        self.step_length.setMaximum(60)
        self.step_length.setValue(1)

        # units combo box
        self.units = QtWidgets.QComboBox()
        self.units.setModel(get_list_model(['h', 'm', 's']))

        # accept button
        self.accept_btn = QtWidgets.QPushButton()
        self.accept_btn.setText('Accept')
        self.accept_btn.clicked.connect(self.accept_click)

        # labels

        # add all to the GUI
        self.layout.addWidget(QtWidgets.QLabel("Start date"))
        self.layout.addWidget(self.calendar)

        self.layout.addWidget(QtWidgets.QLabel("Number of time steps"))
        self.layout.addWidget(self.steps_spinner)

        self.layout.addWidget(QtWidgets.QLabel("Time step length"))
        self.layout.addWidget(self.step_length)

        self.layout.addWidget(QtWidgets.QLabel("Time units"))
        self.layout.addWidget(self.units)

        self.layout.addWidget(self.accept_btn)

        self.setLayout(self.layout)

        self.setWindowTitle('New profiles structure')

    def accept_click(self):
        self.accept()

    def get_values(self):
        steps = self.steps_spinner.value()

        step_length = self.step_length.value()

        step_unit = self.units.currentText()

        time_base = self.calendar.dateTime()

        # a = QDateTime(2011, 4, 22, 00, 00, 00)
        # a
        return steps, step_length, step_unit, time_base.toPyDateTime()


class LogsDialogue(QtWidgets.QDialog):
    """
    New profile dialogue window
    """
    def __init__(self, name, logs: list()):
        super(LogsDialogue, self).__init__()
        self.setObjectName("self")
        # self.resize(200, 71)
        # self.setMinimumSize(QtCore.QSize(200, 71))
        # self.setMaximumSize(QtCore.QSize(200, 71))
        self.setContextMenuPolicy(QtCore.Qt.NoContextMenu)
        # icon = QtGui.QIcon()
        # icon.addPixmap(QtGui.QPixmap("Icons/Plus-32.png"), QtGui.QIcon.Normal, QtGui.QIcon.Off)
        # self.setWindowIcon(icon)
        self.layout = QtWidgets.QVBoxLayout(self)

        # logs_list
        self.logs_list = QtWidgets.QListView()
        model = QtGui.QStandardItemModel()
        self.logs_list.setModel(model)

        for entry in logs:
            item = QtGui.QStandardItem(entry)
            model.appendRow(item)

        # accept button
        self.accept_btn = QtWidgets.QPushButton()
        self.accept_btn.setText('Accept')
        self.accept_btn.clicked.connect(self.accept_click)

        # add all to the GUI
        self.layout.addWidget(QtWidgets.QLabel("Logs"))
        self.layout.addWidget(self.logs_list)

        self.layout.addWidget(self.accept_btn)

        self.setLayout(self.layout)

        self.setWindowTitle(name)

    def accept_click(self):
        self.accept()



