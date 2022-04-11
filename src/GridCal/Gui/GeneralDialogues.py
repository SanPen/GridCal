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
import io
from enum import Enum
from datetime import datetime
from PySide2 import QtCore, QtGui, QtWidgets

from GridCal.Engine.basic_structures import Logger
from GridCal.Gui.GuiFunctions import ObjectsModel, get_tree_model, get_list_model


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


class MTreeExpandHook(QtCore.QObject):
    """
    MTreeExpandHook( QTreeView )
    """

    def __init__(self, tree):
        super(MTreeExpandHook, self).__init__()
        self.setParent(tree)
        # NOTE viewport for click event listen
        tree.viewport().installEventFilter(self)
        self.tree = tree

    def eventFilter(self, receiver, event):
        if (
            # NOTE mouse left click
            event.type() == QtCore.QEvent.Type.MouseButtonPress
            # NOTE keyboard shift press
            and event.modifiers() & QtCore.Qt.ShiftModifier
        ):
            # NOTE get mouse local position
            pos = self.tree.mapFromGlobal(QtGui.QCursor.pos())
            index = self.tree.indexAt(pos)
            if not self.tree.isExpanded(index):
                # NOTE expand all child
                self.tree.expandRecursively(index)
                return True
        return super(MTreeExpandHook, self).eventFilter(self.tree, event)


class LogsDialogue(QtWidgets.QDialog):
    """
    New profile dialogue window
    """
    def __init__(self, name, logger: Logger(), expand_all=True):
        super(LogsDialogue, self).__init__()
        self.setObjectName("self")
        self.setContextMenuPolicy(QtCore.Qt.NoContextMenu)
        self.main_layout = QtWidgets.QVBoxLayout(self)

        self.logger = logger

        # logs_list
        self.logs_table = QtWidgets.QTreeView()
        model = fill_tree_from_logs(logger)
        self.logs_table.setModel(model)
        self.logs_table.setFirstColumnSpanned(0, QtCore.QModelIndex(), True)
        self.logs_table.setFirstColumnSpanned(1, QtCore.QModelIndex(), True)
        self.logs_table.setAnimated(True)
        # MTreeExpandHook(self.logs_table)

        if expand_all:
            self.logs_table.expandAll()

        # accept button
        self.accept_btn = QtWidgets.QPushButton()
        self.accept_btn.setText('Accept')
        self.accept_btn.clicked.connect(self.accept_click)

        self.save_btn = QtWidgets.QPushButton()
        self.save_btn.setText('Save')
        self.save_btn.clicked.connect(self.save_click)

        self.copy_btn = QtWidgets.QPushButton()
        self.copy_btn.setText('Copy')
        self.copy_btn.clicked.connect(self.copy_click)

        self.btn_frame = QtWidgets.QFrame()
        self.btn_layout = QtWidgets.QHBoxLayout(self.btn_frame)
        self.btn_spacer = QtWidgets.QSpacerItem(10, 10, QtWidgets.QSizePolicy.Expanding)
        self.btn_layout.addWidget(self.save_btn)
        self.btn_layout.addWidget(self.copy_btn)
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
        file, filter_ = QtWidgets.QFileDialog.getSaveFileName(self, "Export results", '',
                                                              filter="CSV (*.csv);;Excel files (*.xlsx)",)

        if file != '':
            if 'xlsx' in filter_:
                f = file
                if not f.endswith('.xlsx'):
                    f += '.xlsx'
                self.logger.to_xlsx(f)

            if 'csv' in filter_:
                f = file
                if not f.endswith('.csv'):
                    f += '.csv'
                self.logger.to_csv(f)

    def copy_click(self):
        """
        Copy logs to the clipboard
        """
        df = self.logger.to_df()
        s = io.StringIO()
        df.to_csv(s, sep='\t')
        txt = s.getvalue()

        # copy to clipboard
        cb = QtWidgets.QApplication.clipboard()
        cb.clear(mode=cb.Clipboard)
        cb.setText(txt, mode=cb.Clipboard)


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


class TimeReIndexDialogue(QtWidgets.QDialog):
    """
    New profile dialogue window
    """
    def __init__(self):
        super(TimeReIndexDialogue, self).__init__()
        self.setObjectName("self")
        self.setContextMenuPolicy(QtCore.Qt.NoContextMenu)
        self.main_layout = QtWidgets.QVBoxLayout(self)

        self.accepted = False

        self.label1 = QtWidgets.QLabel()
        self.label1.setText("Year")

        # year
        d = datetime.now()
        self.year_spinner = QtWidgets.QSpinBox()
        self.year_spinner.setMinimum(0)
        self.year_spinner.setMaximum(3000)
        self.year_spinner.setValue(d.year)

        self.label2 = QtWidgets.QLabel()
        self.label2.setText("Hours per interval")

        self.interval_hours = QtWidgets.QDoubleSpinBox()
        self.interval_hours.setMinimum(0.0001)
        self.interval_hours.setMaximum(1000)
        self.interval_hours.setValue(1)

        # accept button
        self.accept_btn = QtWidgets.QPushButton()
        self.accept_btn.setText('Accept')
        self.accept_btn.clicked.connect(self.accept_click)

        # add all to the GUI
        self.main_layout.addWidget(self.label1)
        self.main_layout.addWidget(self.year_spinner)
        self.main_layout.addWidget(self.label2)
        self.main_layout.addWidget(self.interval_hours)
        self.main_layout.addWidget(self.accept_btn)

        self.setLayout(self.main_layout)

        self.setWindowTitle('Time re-index')

        h = 120
        self.resize(h, int(1.1 * h))

    def accept_click(self):
        """
        Accept and close
        """
        self.accepted = True
        self.accept()


class CorrectInconsistenciesDialogue(QtWidgets.QDialog):
    """
    New profile dialogue window
    """
    def __init__(self):
        super(CorrectInconsistenciesDialogue, self).__init__()
        self.setObjectName("self")
        self.setContextMenuPolicy(QtCore.Qt.NoContextMenu)
        self.main_layout = QtWidgets.QVBoxLayout(self)

        self.accepted = False

        self.label1 = QtWidgets.QLabel()
        self.label1.setText("Minimum generator set point")

        # min voltage
        self.min_voltage = QtWidgets.QDoubleSpinBox()
        self.min_voltage.setMinimum(0)
        self.min_voltage.setMaximum(2)
        self.min_voltage.setSingleStep(0.01)
        self.min_voltage.setValue(0.98)

        self.label2 = QtWidgets.QLabel()
        self.label2.setText("Maximum generator set point")

        # min voltage
        self.max_voltage = QtWidgets.QDoubleSpinBox()
        self.max_voltage.setMinimum(0)
        self.max_voltage.setMaximum(2)
        self.max_voltage.setSingleStep(0.01)
        self.max_voltage.setValue(1.02)

        self.label3 = QtWidgets.QLabel()
        self.label3.setText("Maximum virtual tap difference")

        self.max_virtual_tap = QtWidgets.QDoubleSpinBox()
        self.max_virtual_tap.setMinimum(0)
        self.max_virtual_tap.setMaximum(1)
        self.max_virtual_tap.setSingleStep(0.01)
        self.max_virtual_tap.setValue(0.1)

        # accept button
        self.accept_btn = QtWidgets.QPushButton()
        self.accept_btn.setText('Accept')
        self.accept_btn.clicked.connect(self.accept_click)

        # add all to the GUI
        self.main_layout.addWidget(self.label1)
        self.main_layout.addWidget(self.min_voltage)
        self.main_layout.addWidget(self.label2)
        self.main_layout.addWidget(self.max_voltage)
        self.main_layout.addWidget(self.label3)
        self.main_layout.addWidget(self.max_virtual_tap)
        self.main_layout.addWidget(self.accept_btn)

        self.setLayout(self.main_layout)

        self.setWindowTitle('Correct inconsistencies')

        h = 120
        self.resize(h, int(1.1 * h))

    def accept_click(self):
        """
        Accept and close
        """
        self.accepted = True
        self.accept()


def clear_qt_layout(layout):
    """
    Remove all widgets from a layout object
    :param layout:
    """
    for i in reversed(range(layout.count())):
        layout.itemAt(i).widget().deleteLater()


if __name__ == "__main__":
    import sys
    from PySide2.QtWidgets import QApplication
    app = QApplication(sys.argv)
    window = LogsDialogue(name='', logger=Logger())
    window.show()
    sys.exit(app.exec_())
