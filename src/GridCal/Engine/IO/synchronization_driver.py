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
from typing import List, Dict
from PySide2.QtCore import QThread, Signal
from PySide2 import QtGui

from GridCal.Engine.basic_structures import Logger, SyncIssueType
from GridCal.Engine.Core.multi_circuit import MultiCircuit
from GridCal.Engine.IO.file_handler import FileOpen
from GridCal.Engine.Devices.editable_device import EditableDevice, DeviceType


from PySide2.QtCore import QAbstractItemModel, QFile, QIODevice, QModelIndex, Qt
from PySide2.QtWidgets import QApplication, QTreeView


class SyncIssue:

    def __init__(self, device_type, issue_type: SyncIssueType, property_name, my_elm, their_elm):
        """

        :param device_type:
        :param issue_type:
        :param property_name:
        :param my_elm:
        :param their_elm:
        """

        self.device_type = device_type

        self.issue_type = issue_type

        self.property_name = property_name

        self.my_elm = my_elm

        self.their_elm = their_elm

        self.__accept__ = True

    def __str__(self):
        if self.issue_type == SyncIssueType.Conflict:
            return 'Mod::' + self.device_type.value + ', ' + self.issue_type.value + ', ' + self.my_elm.name + ':' + self.property_name
        elif self.issue_type == SyncIssueType.Added:
            return 'Add::' + self.device_type.value + ', ' + self.issue_type.value + ', ' + self.their_elm.name
        elif self.issue_type == SyncIssueType.Deleted:
            return 'Del::' + self.device_type.value + ', ' + self.issue_type.value + ', ' + self.my_elm.name
        else:
            return ""

    def accept(self):
        self.__accept__ = True

    def reject(self):
        self.__accept__ = False

    def accepted(self):
        return self.__accept__

    def get_my_name(self):
        return str(self.my_elm)

    def get_my_value(self):
        if self.my_elm is not None and self.property_name != "":
            return getattr(self.my_elm, self.property_name)
        else:
            return ""

    def get_their_value(self):
        if self.their_elm is not None and self.property_name != "":
            return getattr(self.their_elm, self.property_name)
        else:
            return ""

    def accept_change(self):
        """
        process the change
        :return:
        """
        their_val = self.get_their_value()
        setattr(self.my_elm, self.property_name, their_val)


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
    :return: List of issues
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
                issue = SyncIssue(device_type=elm1.device_type,
                                  issue_type=SyncIssueType.Conflict,
                                  property_name=prop,
                                  my_elm=elm1,
                                  their_elm=elm2)
                issues.append(issue)

            # if this is a bus, then examine the children
            if elm1.device_type == DeviceType.BusDevice:

                issues += compare_devices_lists(elm1.loads, elm2.loads)
                issues += compare_devices_lists(elm1.controlled_generators, elm2.controlled_generators)
                issues += compare_devices_lists(elm1.batteries, elm2.batteries)
                issues += compare_devices_lists(elm1.static_generators, elm2.static_generators)
                issues += compare_devices_lists(elm1.shunts, elm2.shunts)

        else:
            # my element has been deleted
            issue = SyncIssue(device_type=elm1.device_type,
                              issue_type=SyncIssueType.Deleted,
                              property_name="",
                              my_elm=elm1,
                              their_elm=None)
            issues.append(issue)

    # check the file buses against mine, here we only need to check for disagreements in the existence
    for name2, elm2 in items_dict2.items():
        if name2 not in items_dict1.keys():
            # new element added
            issue = SyncIssue(device_type=elm2.device_type,
                              issue_type=SyncIssueType.Added,
                              property_name="",
                              my_elm=None,
                              their_elm=elm2)
            issues.append(issue)

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
    issues += compare_devices_lists(dev_list1=current_circuit.lines,
                                    dev_list2=file_circuit.lines)

    issues += compare_devices_lists(dev_list1=current_circuit.transformers2w,
                                    dev_list2=file_circuit.transformers2w)

    issues += compare_devices_lists(dev_list1=current_circuit.hvdc_lines,
                                    dev_list2=file_circuit.hvdc_lines)

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


def get_issues_tree_view_model(issues: List[SyncIssue]):
    """
    Get TreeView model of the issues
    :param issues: list of issues
    :return: Model for a TreeView
    """
    # structure the issues by issue type and by device type
    k = 0
    data = dict()
    for issue in issues:

        # device_type
        # issue_type
        # prop
        # val1
        # val2
        # elm1
        # elm2

        if issue.issue_type in data.keys():

            if issue.device_type.value in data[issue.issue_type.value].keys():
                data[issue.issue_type.value][issue.device_type.value].append((k, issue))
            else:
                data[issue.issue_type.value][issue.device_type.value] = [(k, issue)]

        else:
            data[issue.issue_type.value] = {issue.device_type.value: [(k, issue)]}

        k += 1

    # build the tree
    model = QtGui.QStandardItemModel()
    model.setHorizontalHeaderLabels(['Issue #', 'name', 'property', 'my value', 'their value', 'Accept theirs'])

    # populate data
    for issue_name, devices in data.items():

        parent1 = QtGui.QStandardItem(issue_name)  # add the issue group

        for device, list_of_issues in devices.items():

            parent2 = QtGui.QStandardItem(device)  # add the device type group

            for k, issue_item in list_of_issues:  # add the row of information

                items = list()
                items.append(QtGui.QStandardItem(str(k)))
                items.append(QtGui.QStandardItem(issue_item.get_my_name()))
                items.append(QtGui.QStandardItem(issue_item.property_name))
                items.append(QtGui.QStandardItem(str(issue_item.get_my_value())))
                items.append(QtGui.QStandardItem(str(issue_item.get_their_value())))

                check = QtGui.QStandardItem(str(issue_item.__accept__))
                check.isCheckable()

                if issue_item.__accept__:
                    check.setCheckState(Qt.Checked)
                else:
                    check.setCheckState(Qt.Unchecked)

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
    items_processed_event = Signal()

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

                    if file_circuit is not None:
                        # sync the models
                        self.issues, self.version_conflict = model_check(self.circuit, file_circuit)

                        self.highest_version = max(self.circuit.model_version, file_circuit.model_version)

                        # notify the external world that we did sync
                        self.sync_event.emit()
                    else:
                        # the sync failed because the file was being used by another sync process
                        pass

                else:
                    # the file disappeared!
                    self.logger.add('File missing for synchronization:' + self.file_name)
                    self.cancel()

                # sleep
                time.sleep(self.sleep_time)

            else:
                # sleep 1 second to catch other events
                time.sleep(1)

        # post events
        self.progress_text.emit('Done!')
        self.done_signal.emit()

    def cancel(self):
        """
        Cancel the sync checking
        """
        self.__cancel__ = True

    def pause(self):
        """
        Pause the sync checking
        """
        self.__pause__ = True

    def resume(self):
        """
        Resume the sync checking
        """
        self.__pause__ = False

    def process_issues(self):
        """
        Process all the issues
        :return:
        """

        self.items_processed_event.emit()
