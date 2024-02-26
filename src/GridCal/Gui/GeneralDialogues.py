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
import io
import pandas as pd
from typing import List
from datetime import datetime
from PySide6 import QtCore, QtGui, QtWidgets

from GridCalEngine.basic_structures import Logger
from GridCal.Gui.GuiFunctions import ObjectsModel, get_list_model, get_checked_indices


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
        self.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.NoContextMenu)
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
                and event.modifiers() & QtCore.Qt.KeyboardModifier.ShiftModifier
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
        self.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.NoContextMenu)
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
        self.btn_spacer = QtWidgets.QSpacerItem(10, 10, QtWidgets.QSizePolicy.Policy.Expanding)
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
                                                              filter="CSV (*.csv);;Excel files (*.xlsx)", )

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
        cb.clear()
        cb.setText(txt)


class ElementsDialogue(QtWidgets.QDialog):
    """
    Selected elements dialogue window
    """

    def __init__(self, name, elements: list()):
        super(ElementsDialogue, self).__init__()
        self.setObjectName("self")
        self.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.NoContextMenu)
        self.layout = QtWidgets.QVBoxLayout(self)

        # build elements list
        self.objects_table = QtWidgets.QTableView()

        if len(elements) > 0:
            model = ObjectsModel(objects=elements,
                                 time_index=None,
                                 property_list=elements[0].property_list,
                                 parent=self.objects_table,
                                 editable=False)

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
        self.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.NoContextMenu)
        self.main_layout = QtWidgets.QVBoxLayout(self)

        self.accepted = False

        # year
        d2 = datetime.now()
        d = datetime(year=d2.year, month=d2.month, day=d2.day, hour=d2.hour, minute=d2.minute, second=0)
        self.date_time_editor = QtWidgets.QDateTimeEdit()
        self.date_time_editor.setDateTime(d)

        # time step length
        self.step_length = QtWidgets.QDoubleSpinBox()
        self.step_length.setMinimum(0.0001)
        self.step_length.setMaximum(1000)
        self.step_length.setValue(1)

        # units combo box
        self.units = QtWidgets.QComboBox()
        self.units.setModel(get_list_model(['h', 'm', 's']))

        # accept button
        self.accept_btn = QtWidgets.QPushButton()
        self.accept_btn.setText('Accept')
        self.accept_btn.clicked.connect(self.accept_click)

        # add all to the GUI
        self.main_layout.addWidget(QtWidgets.QLabel("Start date"))
        self.main_layout.addWidget(self.date_time_editor)

        self.main_layout.addWidget(QtWidgets.QLabel("Time step length"))
        self.main_layout.addWidget(self.step_length)

        self.main_layout.addWidget(QtWidgets.QLabel("Time units"))
        self.main_layout.addWidget(self.units)

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
        self.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.NoContextMenu)
        self.main_layout = QtWidgets.QVBoxLayout(self)

        self.is_accepted = False

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
        self.is_accepted = True
        self.accept()


def clear_qt_layout(layout):
    """
    Remove all widgets from a layout object
    :param layout:
    """
    for i in reversed(range(layout.count())):
        layout.itemAt(i).widget().deleteLater()


class CheckListDialogue(QtWidgets.QDialog):
    """
    New profile dialogue window
    """

    def __init__(self, objects_list: List[str], title='Select objects'):
        QtWidgets.QDialog.__init__(self)
        self.setObjectName("self")
        self.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.NoContextMenu)
        self.main_layout = QtWidgets.QVBoxLayout(self)

        self.is_accepted: bool = False
        self.selected_indices: List[int] = list()

        self.label1 = QtWidgets.QLabel()
        self.label1.setText("Selected objects")

        # min voltage
        self.list_view = QtWidgets.QListView()
        self.mdl = get_list_model(objects_list, checks=True, check_value=True)
        self.list_view.setModel(self.mdl)

        # accept button
        self.accept_btn = QtWidgets.QPushButton()
        self.accept_btn.setText('Accept')
        self.accept_btn.clicked.connect(self.accept_click)

        # add all to the GUI
        self.main_layout.addWidget(self.label1)
        self.main_layout.addWidget(self.list_view)
        self.main_layout.addWidget(self.accept_btn)

        self.setLayout(self.main_layout)

        self.setWindowTitle(title)

        h = 260
        self.resize(h, int(0.8 * h))

    def accept_click(self):
        """
        Accept and close
        """
        self.is_accepted = True

        self.selected_indices = get_checked_indices(self.mdl)
        self.accept()


class InputNumberDialogue(QtWidgets.QDialog):
    """
    New InputNumberDialogue window
    """

    def __init__(self, min_value: float, max_value: float, default_value: float, is_int: bool = False,
                 title='Select objects', text='', decimals=2, suffix='', h=80, w=240):
        """

        :param min_value:
        :param max_value:
        :param is_int:
        :param title:
        :param text:
        :param decimals:
        :param suffix:
        :param h:
        :param w:
        """
        QtWidgets.QDialog.__init__(self)
        self.setObjectName("self")
        self.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.NoContextMenu)
        self.main_layout = QtWidgets.QVBoxLayout(self)

        self.is_accepted: bool = False
        self.value = 0 if is_int else 0.0

        self.label1 = QtWidgets.QLabel()
        self.label1.setText(text)

        # min voltage
        self.input_box = QtWidgets.QSpinBox() if is_int else QtWidgets.QDoubleSpinBox()
        self.input_box.setMinimum(min_value)
        self.input_box.setMaximum(max_value)
        self.input_box.setSuffix(suffix)
        self.input_box.setValue(default_value)

        if not is_int:
            self.input_box.setDecimals(decimals)

        # accept button
        self.accept_btn = QtWidgets.QPushButton()
        self.accept_btn.setText('Accept')
        self.accept_btn.clicked.connect(self.accept_click)

        # add all to the GUI
        self.main_layout.addWidget(self.label1)
        self.main_layout.addWidget(self.input_box)
        self.main_layout.addWidget(self.accept_btn)

        self.setLayout(self.main_layout)

        self.setWindowTitle(title)

        self.resize(w, h)

    def accept_click(self):
        """
        Accept and close
        """
        self.is_accepted = True

        self.value = self.input_box.value()
        self.accept()

class InputSearchDialogue(QtWidgets.QDialog):
    """
    New InputNumberDialogue window
    """

    def __init__(self, deafault_value: str, title='Search', prompt='', h=80, w=240):
        """
        :default_value:
        :param title:
        :param prompt:
        :param h:
        :param w:
        """

        self.searchText = ""
        QtWidgets.QDialog.__init__(self)
        self.setObjectName("self")
        self.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.NoContextMenu)
        self.main_layout = QtWidgets.QVBoxLayout(self)

        self.is_accepted: bool = False

        self.label1 = QtWidgets.QLabel()
        self.label1.setText(prompt)

        # min voltage
        self.input_box = QtWidgets.QLineEdit()


        # search button
        self.accept_btn = QtWidgets.QPushButton()
        self.accept_btn.setText('Search')
        self.accept_btn.clicked.connect(self.search_click)

        # add all to the GUI
        self.main_layout.addWidget(self.label1)
        self.main_layout.addWidget(self.input_box)
        self.main_layout.addWidget(self.accept_btn)

        self.setLayout(self.main_layout)

        self.setWindowTitle(title)

        self.resize(w, h)

    def search_click(self):
        """
        Serach and close
        """
        self.is_accepted = True

        self.searchText = self.input_box.text()
        self.accept()

class InputSearchDialogue(QtWidgets.QDialog):
    """
    New InputNumberDialogue window
    """

    def __init__(self, deafault_value: str, title='Search', prompt='', h=80, w=240):
        """
        :default_value:
        :param title:
        :param prompt:
        :param h:
        :param w:
        """

        self.searchText = ""
        QtWidgets.QDialog.__init__(self)
        self.setObjectName("self")
        self.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.NoContextMenu)
        self.main_layout = QtWidgets.QVBoxLayout(self)

        self.is_accepted: bool = False

        self.label1 = QtWidgets.QLabel()
        self.label1.setText(prompt)

        # min voltage
        self.input_box = QtWidgets.QLineEdit()


        # search button
        self.accept_btn = QtWidgets.QPushButton()
        self.accept_btn.setText('Search')
        self.accept_btn.clicked.connect(self.search_click)

        # add all to the GUI
        self.main_layout.addWidget(self.label1)
        self.main_layout.addWidget(self.input_box)
        self.main_layout.addWidget(self.accept_btn)

        self.setLayout(self.main_layout)

        self.setWindowTitle(title)

        self.resize(w, h)

    def search_click(self):
        """
        Serach and close
        """
        self.is_accepted = True

        self.searchText = self.input_box.text()
        self.accept()

class StartEndSelectionDialogue(QtWidgets.QDialog):
    """
    New StartEndSelectionDialogue window
    """

    def __init__(self, min_value: int, max_value: int, time_array,
                 title='Simulation limits selection', h=80, w=240):
        """

        :param min_value:
        :param max_value:
        :param time_array:
        :param title:
        :param h:
        :param w:
        """
        QtWidgets.QDialog.__init__(self)
        self.setObjectName("self")
        self.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.NoContextMenu)
        self.main_layout = QtWidgets.QVBoxLayout(self)

        self.is_accepted: bool = False

        self.time_array = time_array
        nt = len(time_array) - 1

        self.start_slider = QtWidgets.QSlider()
        self.start_slider.setMinimum(0)
        self.start_slider.setMaximum(nt)
        self.start_slider.setValue(min_value)
        self.start_slider.valueChanged.connect(self.slider_change)
        self.start_slider.setOrientation(QtCore.Qt.Orientation.Horizontal)

        self.start_label = QtWidgets.QLabel()

        self.end_slider = QtWidgets.QSlider()
        self.end_slider.setMinimum(0)
        self.end_slider.setMaximum(nt)
        self.end_slider.setValue(max_value)
        self.end_slider.valueChanged.connect(self.slider_change)
        self.end_slider.setOrientation(QtCore.Qt.Orientation.Horizontal)

        self.end_label = QtWidgets.QLabel()

        # accept button
        self.accept_btn = QtWidgets.QPushButton()
        self.accept_btn.setText('Accept')
        self.accept_btn.clicked.connect(self.accept_click)

        # add all to the GUI
        self.main_layout.addWidget(self.start_slider)
        self.main_layout.addWidget(self.start_label)
        self.main_layout.addWidget(self.end_slider)
        self.main_layout.addWidget(self.end_label)
        self.main_layout.addWidget(self.accept_btn)

        self.setLayout(self.main_layout)

        self.setWindowTitle(title)

        self.start_value = min_value
        self.end_value = max_value

        self.resize(w, h)

        self.slider_change()

    def slider_change(self):
        """
        On any slider change...
        """
        self.start_value = self.start_slider.value()
        self.end_value = self.end_slider.value()

        if self.start_value > self.end_value:
            self.end_slider.setValue(self.start_value)
            self.end_value = self.start_value

        t1 = pd.to_datetime(self.time_array[self.start_value]).strftime('%d/%m/%Y %H:%M')
        t2 = pd.to_datetime(self.time_array[self.end_value]).strftime('%d/%m/%Y %H:%M')
        self.start_label.setText(str(t1))
        self.end_label.setText(str(t2) + ' [{0}]'.format(self.end_value - self.start_value))

    def accept_click(self):
        """
        Accept and close
        """
        self.is_accepted = True

        self.accept()


class CustomQuestionDialogue(QtWidgets.QDialog):
    """
    Custom question dialogue
    """

    def __init__(self, title: str, question: str, answer1: str, answer2: str):
        super().__init__()

        self.setWindowTitle(title)

        layout = QtWidgets.QVBoxLayout()
        button_layout = QtWidgets.QHBoxLayout()

        label = QtWidgets.QLabel(question)
        label.setWordWrap(True)
        layout.addWidget(label)

        button_layout.addSpacerItem(QtWidgets.QSpacerItem(10, 10, QtWidgets.QSizePolicy.Policy.Expanding))

        button_1 = QtWidgets.QPushButton(answer1)
        button_1.clicked.connect(self.b1_clicked)
        button_layout.addWidget(button_1)

        button_2 = QtWidgets.QPushButton(answer2)
        button_2.clicked.connect(self.b2_clicked)
        button_layout.addWidget(button_2)

        layout.addLayout(button_layout)
        self.setLayout(layout)

        self.accepted_answer = 0

    def b1_clicked(self):
        self.accepted_answer = 1
        self.accept()

    def b2_clicked(self):
        self.accepted_answer = 2
        self.accept()


if __name__ == "__main__":
    import sys
    from PySide6.QtWidgets import QApplication

    app = QApplication(sys.argv)
    # window = InputNumberDialogue(min_value=3,
    #                              max_value=10,
    #                              default_value=3,
    #                              is_int=True,
    #                              title="stuff",
    #                              text="valor? fsd..xcfh.dfgbhdfbflb.lsdfnblsndf.bnsdf.bn.xdfnb.xdfbñlxdhfn.blxnd",
    #                              suffix=' cosas')

    window = CustomQuestionDialogue(title="My question",
                                    question="What do you want " * 10,
                                    answer1="Go home",
                                    answer2="stay here")

    window.show()
    sys.exit(app.exec_())
