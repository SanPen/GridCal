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

import os
import time
from math import isclose
from PySide2.QtCore import QThread, Signal
from PySide2 import QtGui

from GridCal.Engine.basic_structures import Logger
from GridCal.Engine.Core.multi_circuit import MultiCircuit
from GridCal.Engine.IO.file_handler import FileOpen
from GridCal.Engine.Devices.meta_devices import EditableDevice, DeviceType


from PySide2.QtCore import QAbstractItemModel, QFile, QIODevice, QModelIndex, Qt
from PySide2.QtWidgets import QApplication, QTreeView


class TreeItem(object):
    def __init__(self, data, parent=None):
        self.parentItem = parent
        self.itemData = data
        self.childItems = []

    def appendChild(self, item):
        self.childItems.append(item)

    def child(self, row):
        return self.childItems[row]

    def childCount(self):
        return len(self.childItems)

    def columnCount(self):
        return len(self.itemData)

    def data(self, column):
        try:
            return self.itemData[column]
        except IndexError:
            return None

    def parent(self):
        return self.parentItem

    def row(self):
        if self.parentItem:
            return self.parentItem.childItems.index(self)

        return 0


class SyncTreeModel(QAbstractItemModel):

    def __init__(self, data, parent=None):
        super(SyncTreeModel, self).__init__(parent)

        self.rootItem = TreeItem(("Conflicted?", "Device", "Property", "Mine", "Theirs", "Accept theirs?"))

        self.setupModelData(data.split('\n'), self.rootItem)

    def columnCount(self, parent):
        if parent.isValid():
            return parent.internalPointer().columnCount()
        else:
            return self.rootItem.columnCount()

    def data(self, index, role):
        if not index.isValid():
            return None

        if role != Qt.DisplayRole:
            return None

        item = index.internalPointer()

        return item.data(index.column())

    def flags(self, index):
        if not index.isValid():
            return Qt.NoItemFlags

        return Qt.ItemIsEnabled | Qt.ItemIsSelectable

    def headerData(self, section, orientation, role):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return self.rootItem.data(section)

        return None

    def index(self, row, column, parent):
        if not self.hasIndex(row, column, parent):
            return QModelIndex()

        if not parent.isValid():
            parentItem = self.rootItem
        else:
            parentItem = parent.internalPointer()

        childItem = parentItem.child(row)
        if childItem:
            return self.createIndex(row, column, childItem)
        else:
            return QModelIndex()

    def parent(self, index):
        if not index.isValid():
            return QModelIndex()

        childItem = index.internalPointer()
        parentItem = childItem.parent()

        if parentItem == self.rootItem:
            return QModelIndex()

        return self.createIndex(parentItem.row(), 0, parentItem)

    def rowCount(self, parent):
        if parent.column() > 0:
            return 0

        if not parent.isValid():
            parentItem = self.rootItem
        else:
            parentItem = parent.internalPointer()

        return parentItem.childCount()

    def setupModelData(self, lines, parent):
        parents = [parent]
        indentations = [0]

        number = 0

        while number < len(lines):
            position = 0
            while position < len(lines[number]):
                if lines[number][position] != ' ':
                    break
                position += 1

            lineData = lines[number][position:].trimmed()

            if lineData:
                # Read the column data from the rest of the line.
                columnData = [s for s in lineData.split('\t') if s]

                if position > indentations[-1]:
                    # The last child of the current parent is now the new
                    # parent unless the current parent has no children.

                    if parents[-1].childCount() > 0:
                        parents.append(parents[-1].child(parents[-1].childCount() - 1))
                        indentations.append(position)

                else:
                    while position < indentations[-1] and len(parents) > 0:
                        parents.pop()
                        indentations.pop()

                # Append a new item to the current parent's list of children.
                parents[-1].appendChild(TreeItem(columnData, parents[-1]))

            number += 1


def compare_devices(dev1: EditableDevice, dev2: EditableDevice):
    """
    Compare two devices and return the list of differences
    :param dev1: Device 1
    :param dev2: Device 2
    :return: list of differences [property name, value1, value2]
    """

    differences = list()
    if dev1.device_type == dev2.device_type:
        for prop_name, value in dev1.editable_headers.items():

            val1 = getattr(dev1, prop_name)
            val2 = getattr(dev2, prop_name)

            if value.tpe in [int, float]:
                if not isclose(val1, val2, abs_tol=1e-6):
                    differences.append([prop_name, val1, val2])
            else:
                if str(val1) != str(val2):
                    differences.append([prop_name, val1, val2])

    return differences


def compare_devices_lists(dev_list1, dev_list2):
    """
    Compare two devices lists
    :param dev_list1: list of devices 1
    :param dev_list2: list of devices 2
    :return: List of issues: device name, issue type, property, my value, their value, my object, their object
    """

    items_dict1 = {elm.name: elm for elm in dev_list1}
    items_dict2 = {elm.name: elm for elm in dev_list2}

    issues = list()  # device type, issue type, property, my value, their value, elm1, elm2

    # check my buses against the file buses
    for name1, elm1 in items_dict1.items():

        if name1 in items_dict2.keys():

            # get the other element
            elm2 = items_dict2[name1]

            # perform the comparison in the same types, compare
            ls = compare_devices(elm1, elm2)
            for prop, val1, val2 in ls:
                issues.append([elm1.device_type, 'Conflict', prop, val1, val2, elm1, elm2])

            # if this is a bus, then examine the children
            if elm1.device_type == DeviceType.BusDevice:
                # self.loads + self.controlled_generators + self.batteries + self.static_generators + self.shunts
                issues += compare_devices_lists(elm1.loads, elm2.loads)
                issues += compare_devices_lists(elm1.controlled_generators, elm2.controlled_generators)
                issues += compare_devices_lists(elm1.batteries, elm2.batteries)
                issues += compare_devices_lists(elm1.static_generators, elm2.static_generators)
                issues += compare_devices_lists(elm1.shunts, elm2.shunts)

        else:
            # my element has been deleted
            issues.append([elm1.device_type, 'Deleted', "", name1, "", elm1, None])

    # check the file buses against mine, here we only need to check for disagreements in the existence
    for name2, elm2 in items_dict2.items():
        if name2 not in items_dict1.keys():
            # new element added
            issues.append([elm2.device_type, 'Added', "", "", name2, None, elm2])

    return issues


def detect_changes_and_conflicts(current_circuit: MultiCircuit, file_circuit: MultiCircuit):
    """
    Detect changes
    :param current_circuit:
    :param file_circuit:
    :return:
    """

    issues = list()  # device name, issue type, property, my value, their value, elm1, elm2

    # buses
    issues += compare_devices_lists(dev_list1=current_circuit.buses,
                                    dev_list2=file_circuit.buses)

    # branches
    issues += compare_devices_lists(dev_list1=current_circuit.branches,
                                    dev_list2=file_circuit.branches)

    return issues


def model_check(current_circuit: MultiCircuit, file_circuit: MultiCircuit):
    """
    Perform model check
    :param current_circuit:
    :param file_circuit:
    :return: list of issues
    """

    issues = detect_changes_and_conflicts(current_circuit, file_circuit)

    if (current_circuit.model_version + 1) <= file_circuit.model_version:
        # the remote file version is newer.
        # The first action is to attempt to merge, looking out for conflict
        # to merge, we incorporate the remote file changes and then we save

        version_conflict = True

    else:
        # there is no version conflict, so we just save
        version_conflict = False

    return issues, version_conflict


def get_issues_tree_view_model(issues):
    """
    Get TreeView model of the issues
    :param issues: list of issues
    :return: Model for a TreeView
    """
    # structure the issues by issue type and by device type
    k = 0
    data = dict()
    for device_type, issue_type, prop, val1, val2, elm1, elm2 in issues:

        if issue_type in data.keys():

            if device_type.value in data[issue_type].keys():
                data[issue_type][device_type.value].append([k, prop, val1, val2])
            else:
                data[issue_type][device_type.value] = [[k, prop, val1, val2]]

        else:
            data[issue_type] = {device_type.value: [[k, prop, val1, val2]]}

        k += 1

    # build the tree
    model = QtGui.QStandardItemModel()
    model.setHorizontalHeaderLabels(['Issue #', 'property', 'my value', 'their value', 'Accept theirs'])

    # populate data
    for issue, devices in data.items():

        parent1 = QtGui.QStandardItem(issue)  # add the issue group

        for device, values in devices.items():

            parent2 = QtGui.QStandardItem(device)  # add the device type group

            for vals in values:  # add the row of information
                items = [QtGui.QStandardItem(str(v)) for v in vals]
                check = QtGui.QStandardItem()
                check.isCheckable()
                check.setCheckState(Qt.Checked)
                items.append(check)

                for item in items:
                    item.setEditable(False)
                parent2.appendRow(items)

            parent2.setEditable(False)
            parent1.appendRow(parent2)

        parent1.setEditable(False)
        model.appendRow(parent1)

    return model


class FileSyncThread(QThread):
    progress_signal = Signal(float)
    progress_text = Signal(str)
    done_signal = Signal()
    sync_event = Signal()

    def __init__(self, circuit: MultiCircuit, file_name, sleep_time):
        """

        :param circuit: current circuit
        :param file_name: name of the file to sync
        :param sleep_time: seconds between executions
        """
        QThread.__init__(self)

        self.circuit = circuit

        self.file_name = file_name

        self.sleep_time = sleep_time

        self.issues = list()

        self.version_conflict = False

        self.highest_version = 0

        self.logger = Logger()

        self.error_msg = ''

        self.__cancel__ = False

        self.__pause__ = False

    def run(self):
        """
        run the file save procedure
        """

        # create class to open the file
        fopen = FileOpen(self.file_name)

        while not self.__cancel__:

            if not self.__pause__:

                if os.path.exists(self.file_name):

                    # load the remote file
                    file_circuit = fopen.open(text_func=self.progress_text.emit,
                                              progress_func=self.progress_signal.emit)

                    # sync the models
                    self.issues, self.version_conflict = model_check(self.circuit, file_circuit)

                    self.highest_version = max(self.circuit.model_version, file_circuit.model_version)

                    # notify the external world that we did sync
                    self.sync_event.emit()

                else:
                    # the file disappeared!
                    self.logger.add('File missing for synchronization:' + self.file_name)
                    self.cancel()

                # sleep
                time.sleep(self.sleep_time)

            else:
                # sleep 1 second to catch other events
                time.sleep(1)
                print('Paused...')

        # post events
        self.progress_text.emit('Done!')

        self.done_signal.emit()

    def cancel(self):
        self.__cancel__ = True

    def pause(self):
        self.__pause__ = True
        print('\tPaused')

    def resume(self):
        self.__pause__ = False
        print('\tResume')
