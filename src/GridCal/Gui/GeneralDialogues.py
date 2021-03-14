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
from datetime import datetime
from PySide2 import QtCore, QtGui, QtWidgets

from GridCal.Engine.basic_structures import Logger
from GridCal.Gui.GuiFunctions import ObjectsModel, get_tree_model


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

        return steps, step_length, step_unit, time_base.toPython()

#
# class LogsModel(QtCore.QAbstractTableModel):
#
#     def __init__(self, logs: Logger, parent=None):
#
#         QtCore.QAbstractTableModel.__init__(self, parent)
#
#         self.logs = logs
#
#     def flags(self, index):
#         return QtCore.Qt.ItemIsEnabled
#
#     def rowCount(self, parent=None):
#         return len(self.logs)
#
#     def columnCount(self, parent=None):
#         return 2
#
#     def headerData(self, section, orientation, role=None):
#         """
#
#         :param section:
#         :param orientation:
#         :param role:
#         :return:
#         """
#         if role == QtCore.Qt.DisplayRole and orientation == QtCore.Qt.Horizontal:
#             if section == 0:
#                 return "Severity"
#             elif section == 1:
#                 return "Message"
#         return None
#
#     def data(self, index, role=None):
#         """
#
#         :param index:
#         :param role:
#         :return:
#         """
#         if index.isValid() and role == QtCore.Qt.DisplayRole:
#
#             if index.column() == 0:
#                 return str(self.logs.severity[index.row()])
#
#             elif index.column() == 1:
#                 return str(self.logs.messages[index.row()])
#
#         return None


def fill_tree_from_logs(logger: Logger):
    """
    Fill logger tree
    :param logger: Logger instance
    :return: QStandardItemModel instance
    """
    d = logger.to_dict()
    editable = False
    model = QtGui.QStandardItemModel()
    model.setHorizontalHeaderLabels(['Time', 'Element', 'Value', 'Expected value'])
    parent = model.invisibleRootItem()

    for severity, messages_dict in d.items():
        severity_child = QtGui.QStandardItem(severity)

        # print(severity)

        for message, data_list in messages_dict.items():
            message_child = QtGui.QStandardItem(message)

            # print('\t', message)

            for time, elm, value, expected_value in data_list:

                # print('\t', '\t', time, elm, value, expected_value)

                time_child = QtGui.QStandardItem(time)
                time_child.setEditable(editable)

                elm_child = QtGui.QStandardItem(elm)
                elm_child.setEditable(editable)

                value_child = QtGui.QStandardItem(value)
                value_child.setEditable(editable)

                expected_val_child = QtGui.QStandardItem(expected_value)
                expected_val_child.setEditable(editable)

                message_child.appendRow([time_child, elm_child, value_child, expected_val_child])

            message_child.setEditable(editable)
            severity_child.appendRow(message_child)

        severity_child.setEditable(editable)
        parent.appendRow(severity_child)

    return model


class LogsDialogue(QtWidgets.QDialog):
    """
    New profile dialogue window
    """
    def __init__(self, name, logs: Logger()):
        super(LogsDialogue, self).__init__()
        self.setObjectName("self")
        self.setContextMenuPolicy(QtCore.Qt.NoContextMenu)
        self.main_layout = QtWidgets.QVBoxLayout(self)

        self.logs = logs

        # logs_list
        self.logs_table = QtWidgets.QTreeView()
        model = fill_tree_from_logs(logs)
        self.logs_table.setModel(model)
        self.logs_table.setFirstColumnSpanned(0, QtCore.QModelIndex(), True)
        self.logs_table.setFirstColumnSpanned(1, QtCore.QModelIndex(), True)
        self.logs_table.setAnimated(True)

        # accept button
        self.accept_btn = QtWidgets.QPushButton()
        self.accept_btn.setText('Accept')
        self.accept_btn.clicked.connect(self.accept_click)

        self.save_btn = QtWidgets.QPushButton()
        self.save_btn.setText('Save')
        self.save_btn.clicked.connect(self.save_click)

        self.btn_frame = QtWidgets.QFrame()
        self.btn_layout = QtWidgets.QHBoxLayout(self.btn_frame)
        self.btn_spacer = QtWidgets.QSpacerItem(10, 10, QtWidgets.QSizePolicy.Expanding)
        self.btn_layout.addWidget(self.save_btn)
        self.btn_layout.addSpacerItem(self.btn_spacer)
        self.btn_layout.addWidget(self.accept_btn)
        self.btn_frame.setLayout(self.btn_layout)

        # add all to the GUI
        self.main_layout.addWidget(self.logs_table)
        self.main_layout.addWidget(self.btn_frame)

        self.setLayout(self.main_layout)

        self.setWindowTitle(name)

        h = 400
        self.resize(int(1.61 * h), h)

    def accept_click(self):
        """
        Accept and close
        """
        self.accept()

    def save_click(self):
        """
        Save the logs to excel or CSV
        """
        file, filter = QtWidgets.QFileDialog.getSaveFileName(self, "Export results", '',
                                                             filter="CSV (*.csv);;Excel files (*.xlsx)",)

        if file != '':
            if 'xlsx' in filter:
                f = file
                if not f.endswith('.xlsx'):
                    f += '.xlsx'
                self.logs.to_xlsx(f)

            if 'csv' in filter:
                f = file
                if not f.endswith('.csv'):
                    f += '.csv'
                self.logs.to_csv(f)


class ElementsDialogue(QtWidgets.QDialog):
    """
    Selected elements dialogue window
    """

    def __init__(self, name, elements: list()):
        super(ElementsDialogue, self).__init__()
        self.setObjectName("self")
        self.setContextMenuPolicy(QtCore.Qt.NoContextMenu)
        self.layout = QtWidgets.QVBoxLayout(self)

        # build elements list
        self.objects_table = QtWidgets.QTableView()

        if len(elements) > 0:
            model = ObjectsModel(elements, elements[0].editable_headers,
                                 parent=self.objects_table, editable=False,
                                 non_editable_attributes=[1, 2, 14])

            self.objects_table.setModel(model)

        # accept button
        self.accept_btn = QtWidgets.QPushButton()
        self.accept_btn.setText('Proceed')
        self.accept_btn.clicked.connect(self.accept_click)

        # Copy button
        self.copy_btn = QtWidgets.QPushButton()
        self.copy_btn.setText('Copy')
        self.copy_btn.clicked.connect(self.copy_click)

        # add all to the GUI
        self.layout.addWidget(self.objects_table)
        self.frame2 = QtWidgets.QFrame()
        self.layout.addWidget(self.frame2)
        self.layout2 = QtWidgets.QHBoxLayout(self.frame2)

        self.layout2.addWidget(self.accept_btn)
        # self.layout2.addWidget(QtWidgets.QSpacerItem())
        self.layout2.addWidget(self.copy_btn)

        self.setLayout(self.layout)

        self.setWindowTitle(name)

        self.accepted = False

    def accept_click(self):
        self.accepted = True
        self.accept()

    def copy_click(self):
        pass


if __name__ == "__main__":
    import sys
    from PySide2.QtWidgets import QApplication
    app = QApplication(sys.argv)
    window = LogsDialogue(name='', logs=Logger())
    window.show()
    sys.exit(app.exec_())
