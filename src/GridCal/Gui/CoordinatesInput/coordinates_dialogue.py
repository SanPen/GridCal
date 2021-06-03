import os
import string
import sys
from random import randint
from enum import Enum
from difflib import SequenceMatcher
import numpy as np
import pandas as pd
from PySide2.QtWidgets import *
from typing import List, Dict
from GridCal.Gui.CoordinatesInput.gui import *
from GridCal.Gui.ProfilesInput.excel_dialog import *
from GridCal.Engine.Devices.bus import Bus
from GridCal.Gui.GridEditorWidget.messages import *


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
            item = QtGui.QStandardItem(str(val))
            item.setEditable(False)
            list_model.appendRow(item)
    return list_model


class Association:

    def __init__(self, name, code, x=0, y=0, latitude=0, longitude=0):
        """

        :param name:
        :param code:
        :param x:
        :param y:
        :param latitude:
        :param longitude:
        """
        self.name: str = name
        self.code: str = code
        self.x: float = x
        self.y: float = y
        self.latitude: float = latitude
        self.longitude: float = longitude

    def get_at(self, idx):

        if idx == 0:
            return self.name
        elif idx == 1:
            return self.code
        elif idx == 2:
            return self.x
        elif idx == 3:
            return self.y
        elif idx == 4:
            return self.latitude
        elif idx == 5:
            return self.longitude
        else:
            return ''


class Associations(QAbstractTableModel):

    def __init__(self):
        QtCore.QAbstractTableModel.__init__(self)

        self.__values: List[Association] = list()

        self.__headers = ['Name', 'Code', 'x', 'y', 'latitude', 'longitude']

    def append(self, val: Association):
        self.__values.append(val)

    def set_x_at(self, idx, value):
        self.__values[idx].x = value

    def set_y_at(self, idx, value):
        self.__values[idx].y = value

    def set_latitude_at(self, idx, value):
        self.__values[idx].latitude = value

    def set_longitude_at(self, idx, value):
        self.__values[idx].longitude = value

    def get_name_at(self, idx):
        return self.__values[idx].name

    def get_code_at(self, idx):
        return self.__values[idx].code

    def get_x_at(self, idx):
        return self.__values[idx].x

    def get_y_at(self, idx):
        return self.__values[idx].y

    def get_latitude_at(self, idx):
        return self.__values[idx].latitude

    def get_longitude_at(self, idx):
        return self.__values[idx].longitude

    def clear_at(self, idx):
        self.__values[idx].x = 0
        self.__values[idx].y = 0
        self.__values[idx].latitude = 0
        self.__values[idx].longitude = 0

    def rowCount(self, parent=None):
        return len(self.__values)

    def columnCount(self, parent=None):
        return len(self.__headers)

    def data(self, index, role=QtCore.Qt.DisplayRole):
        if index.isValid():
            if role == QtCore.Qt.DisplayRole:
                # return self.formatter(self._data[index.row(), index.column()])
                return str(self.__values[index.row()].get_at(index.column()))
        return None

    def headerData(self, p_int, orientation, role):
        if role == QtCore.Qt.DisplayRole:
            if orientation == QtCore.Qt.Horizontal:
                return self.__headers[p_int]
            elif orientation == QtCore.Qt.Vertical:
                return p_int
        return None


class CoordinatesInputGUI(QtWidgets.QDialog):

    def __init__(self, parent=None, list_of_objects: List[Bus] = list(), use_native_dialogues=True):
        """

        Args:
            parent:
            list_of_objects: List of objects to which set a profile to
            list_of_objects: list ob object to modify
            use_native_dialogues: use the native file selection dialogues?
        """
        QtWidgets.QDialog.__init__(self, parent)
        if list_of_objects is None:
            list_of_objects = list()
        self.ui = Ui_Dialog()
        self.ui.setupUi(self)
        self.setWindowTitle('Coordinates import dialogue')
        self.setAcceptDrops(True)

        self.project_directory = None

        self.use_native_dialogues = use_native_dialogues

        # dataFrame
        self.original_data_frame: pd.DataFrame = None

        # initialize the objectives list
        self.objects: List[Bus] = list_of_objects

        self.associations = Associations()
        for elm in list_of_objects:
            self.associations.append(Association(elm.name, elm.code, elm.x, elm.y, elm.latitude, elm.longitude))

        self.display_associations()

        self.accepted_extensions = ['.csv', '.xlsx', '.xls']

        self.ui.splitter.setStretchFactor(0, 3)
        self.ui.splitter.setStretchFactor(1, 7)

        # click
        self.ui.open_button.clicked.connect(self.import_profile)
        self.ui.acceptButton.clicked.connect(self.do_it)
        self.ui.refreshButton.clicked.connect(self.assign)

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

    def dropEvent(self, event):
        """
        Drop file on the GUI, the default behaviour is to load the file
        :param event: event containing all the information
        """
        if event.mimeData().hasUrls:
            events = event.mimeData().urls()
            if len(events) > 0:

                file_names = list()

                for event in events:
                    file_name = event.toLocalFile()
                    name, file_extension = os.path.splitext(file_name)
                    if file_extension.lower() in self.accepted_extensions:
                        file_names.append(file_name)
                    else:
                        error_msg('The file type ' + file_extension.lower() + ' is not accepted :(')

                if len(file_names) > 0:
                    # Just open the file
                    self.open_file_now(filename=file_names)

    def display_associations(self):

        self.ui.assignation_table.setModel(self.associations)

    def set_combo_boxes(self):
        """

        :return:
        """
        if self.original_data_frame is not None:
            names = [val.lower().strip() for val in self.original_data_frame.columns.values]

            mdl = get_list_model(names)
            self.ui.nameComboBox.setModel(mdl)
            self.ui.codeComboBox.setModel(mdl)
            self.ui.xComboBox.setModel(mdl)
            self.ui.yComboBox.setModel(mdl)
            self.ui.latitudeComboBox.setModel(mdl)
            self.ui.longitudeComboBox.setModel(mdl)

            for i, name in enumerate(names):

                if name == 'x':
                    self.ui.xComboBox.setCurrentIndex(i)
                    self.ui.xCheckBox.setChecked(True)
                elif name == 'y':
                    self.ui.yComboBox.setCurrentIndex(i)
                    self.ui.yCheckBox.setChecked(True)
                elif name == 'latitude':
                    self.ui.latitudeComboBox.setCurrentIndex(i)
                    self.ui.latitudeCheckBox.setChecked(True)
                elif name == 'longitude':
                    self.ui.longitudeComboBox.setCurrentIndex(i)
                    self.ui.longitudeCheckBox.setChecked(True)

    def assign(self):
        """

        :return:
        """
        if self.original_data_frame is not None:
            print('Assign')
            name_idx = self.ui.nameComboBox.currentIndex()
            code_idx = self.ui.codeComboBox.currentIndex()
            x_idx = self.ui.xComboBox.currentIndex()
            y_idx = self.ui.yComboBox.currentIndex()
            lat_idx = self.ui.latitudeComboBox.currentIndex()
            lon_idx = self.ui.longitudeComboBox.currentIndex()

            for i in range(self.original_data_frame.shape[0]):

                if self.ui.nameRadioButton.isChecked():
                    if isinstance(self.original_data_frame.values[i, name_idx], float):
                        dat_name = str(int(self.original_data_frame.values[i, name_idx]))
                    else:
                        dat_name = str(self.original_data_frame.values[i, name_idx])

                elif self.ui.codeRadioButton.isChecked():
                    if isinstance(self.original_data_frame.values[i, code_idx], float):
                        dat_name = str(int(self.original_data_frame.values[i, code_idx]))
                    else:
                        dat_name = str(self.original_data_frame.values[i, code_idx])

                else:
                    dat_name = 'a'

                # search in the buses
                for j in range(self.associations.rowCount()):

                    if self.ui.nameRadioButton.isChecked():
                        name = str(self.associations.get_name_at(j))
                    elif self.ui.codeRadioButton.isChecked():
                        name = str(self.associations.get_code_at(j))
                    else:
                        name = 'b'

                    # if the search criteria match...
                    if dat_name.lower() == name.lower():

                        if self.ui.xCheckBox.isChecked():
                            self.associations.set_x_at(j, self.original_data_frame.values[i, x_idx])

                        if self.ui.yCheckBox.isChecked():
                            self.associations.set_y_at(j, self.original_data_frame.values[i, y_idx])

                        if self.ui.longitudeCheckBox.isChecked():
                            self.associations.set_longitude_at(j, self.original_data_frame.values[i, lon_idx])

                        if self.ui.latitudeCheckBox.isChecked():
                            self.associations.set_latitude_at(j, self.original_data_frame.values[i, lat_idx])

            self.display_associations()

    def import_profile(self):
        """
        Select a file to be loaded
        """

        # declare the allowed file types
        files_types = "Formats (*.xlsx *.xls *.csv)"
        # call dialog to select the file
        # filename, type_selected = QFileDialog.getOpenFileNameAndFilter(self, 'Save file', '', files_types)

        # call dialog to select the file

        options = QFileDialog.Options()
        if self.use_native_dialogues:
            options |= QFileDialog.DontUseNativeDialog

        filename, type_selected = QFileDialog.getOpenFileName(self, 'Open file',
                                                              filter=files_types,
                                                              options=options)
        self.open_file_now(filename)

    def open_file_now(self, filename):
        """

        :param filename:
        :return:
        """
        if len(filename) > 0:
            # get the filename extension
            name, file_extension = os.path.splitext(filename)

            # Depending on the extension load the file
            if file_extension == '.csv':
                self.original_data_frame = pd.read_csv(filename, index_col=None)

            elif file_extension in ['.xlsx', '.xls']:

                # select the sheet from the file
                window = ExcelDialog(self, filename)
                window.exec_()
                sheet_index = window.excel_sheet

                if sheet_index is not None:
                    self.original_data_frame = pd.read_excel(filename, sheet_name=sheet_index, index_col=None)

                else:
                    return

            # set the profile names list
            self.set_combo_boxes()
            self.assign()
            self.display_associations()

    def do_it(self):
        """
        Close. The data has to be queried later to the object by the parent by calling get_association_data
        """

        # assign the values back
        for i, bus in enumerate(self.objects):
            if self.ui.xCheckBox.isChecked():
                bus.x = self.associations.get_x_at(i)

            if self.ui.yCheckBox.isChecked():
                bus.y = - self.associations.get_y_at(i)

            if self.ui.longitudeCheckBox.isChecked():
                bus.longitude = self.associations.get_longitude_at(i)

            if self.ui.latitudeCheckBox.isChecked():
                bus.latitude = self.associations.get_latitude_at(i)

        self.close()


class TestObj:
    def __init__(self, name, code, x=0, y=0, latitude=0, longitude=0):
        self.name = name
        self.code = code
        self.x = x
        self.y = y
        self.latitude = latitude
        self.longitude = longitude


if __name__ == "__main__":

    app = QtWidgets.QApplication(sys.argv)
    window = CoordinatesInputGUI(list_of_objects=[TestObj('Test object', 'code')] * 10)
    window.resize(1.61 * 700.0, 600.0)  # golden ratio
    window.show()
    sys.exit(app.exec_())

