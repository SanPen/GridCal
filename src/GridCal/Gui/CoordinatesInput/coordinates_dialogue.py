import os
import sys
import pandas as pd
from PySide6 import QtGui, QtCore, QtWidgets
from typing import List, Tuple, Union
from GridCal.Gui.CoordinatesInput.gui import Ui_Dialog
from GridCal.Gui.ProfilesInput.excel_dialog import ExcelDialog
from GridCal.Gui.GeneralDialogues import LogsDialogue
from GridCalEngine.Devices.Substation import Bus
from GridCalEngine.basic_structures import Logger
from GridCal.Gui.messages import error_msg


def get_list_model(iterable: List[str]) -> QtGui.QStandardItemModel:
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


def find_duplicates(arr: List[str]) -> Tuple[List[str], List[str]]:
    """
    Find duplicates in an array
    :param arr: original array
    :return: unique, duplicates
    """
    seen = set()
    duplicates = set()

    for element in arr:
        if element in seen:
            duplicates.add(element)
        else:
            seen.add(element)

    return list(seen), list(duplicates)


class CoordinatesInputAssociation:
    """
    Association
    """
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

    def get_at(self, idx: int) -> Union[float, str]:
        """
        Get association at index
        :param idx:
        :return:
        """
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


class CoordinatesInputAssociations(QtCore.QAbstractTableModel):

    def __init__(self):
        QtCore.QAbstractTableModel.__init__(self)

        self.__values: List[CoordinatesInputAssociation] = list()

        self.__headers = ['Name', 'Code', 'x', 'y', 'latitude', 'longitude']

    def append(self, val: CoordinatesInputAssociation):
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

    def data(self, index, role=QtCore.Qt.ItemDataRole.DisplayRole):
        if index.isValid():
            if role == QtCore.Qt.ItemDataRole.DisplayRole:
                # return self.formatter(self._data[index.row(), index.column()])
                return str(self.__values[index.row()].get_at(index.column()))
        return None

    def headerData(self,
                   section: int,
                   orientation: QtCore.Qt.Orientation,
                   role=QtCore.Qt.ItemDataRole.DisplayRole):

        if role == QtCore.Qt.ItemDataRole.DisplayRole:
            if orientation == QtCore.Qt.Orientation.Horizontal:
                return self.__headers[section]
            elif orientation == QtCore.Qt.Orientation.Vertical:
                return section
        return None


class CoordinatesInputGUI(QtWidgets.QDialog):
    """
    CoordinatesInputGUI
    """

    def __init__(self, parent=None, list_of_objects: List[Bus] = list()):
        """

        Args:
            parent:
            list_of_objects: List of objects to which set a profile to
            list_of_objects: list ob object to modify
        """
        QtWidgets.QDialog.__init__(self, parent)
        if list_of_objects is None:
            list_of_objects = list()
        self.ui = Ui_Dialog()
        self.ui.setupUi(self)
        self.setWindowTitle('Coordinates import dialogue')
        self.setAcceptDrops(True)

        self.project_directory = None

        self.assigned_count: int = 0

        # dataFrame
        self.original_data_frame: pd.DataFrame = None

        # initialize the objectives list
        self.objects: List[Bus] = list_of_objects

        self.associations = CoordinatesInputAssociations()
        for elm in list_of_objects:
            self.associations.append(CoordinatesInputAssociation(elm.name, elm.code, elm.x, elm.y, elm.latitude, elm.longitude))

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
        msg = QtWidgets.QMessageBox()
        msg.setIcon(QtWidgets.QMessageBox.Icon.Information)
        msg.setText(text)
        # msg.setInformativeText("This is additional information")
        msg.setWindowTitle(title)
        # msg.setDetailedText("The details are as follows:")
        msg.setStandardButtons(QtWidgets.QMessageBox.StandardButton.Ok)
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
        Set the options
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

            for i, name in enumerate(names):  # names are already in lowercase

                if name in ['x', 'xpos', 'x_pos']:
                    self.ui.xComboBox.setCurrentIndex(i)
                    self.ui.xCheckBox.setChecked(True)

                elif name in ['y', 'ypos', 'y_pos']:
                    self.ui.yComboBox.setCurrentIndex(i)
                    self.ui.yCheckBox.setChecked(True)

                elif name in ['latitude', 'lat']:
                    self.ui.latitudeComboBox.setCurrentIndex(i)
                    self.ui.latitudeCheckBox.setChecked(True)

                elif name in ['longitude', 'lon']:
                    self.ui.longitudeComboBox.setCurrentIndex(i)
                    self.ui.longitudeCheckBox.setChecked(True)

    def assign(self):
        """
        Assign the loaded values to the correspondance table
        """
        if self.original_data_frame is not None:
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

            self.assigned_count += 1

    def import_profile(self):
        """
        Select a file to be loaded
        """

        # declare the allowed file types
        files_types = "Formats (*.xlsx *.xls *.csv)"
        # call dialog to select the file
        # filename, type_selected = QFileDialog.getOpenFileNameAndFilter(self, 'Save file', '', files_types)

        # call dialog to select the file
        filename, type_selected = QtWidgets.QFileDialog.getOpenFileName(self, 'Open file', filter=files_types)
        self.open_file_now(filename)

    def open_file_now(self, filename: str):
        """
        Opena file
        :param filename: path of the file
        """
        if len(filename) > 0:
            # get the filename extension
            name, file_extension = os.path.splitext(filename)

            # Depending on the extension load the file
            if file_extension == '.csv':
                self.original_data_frame = pd.read_csv(filename, index_col=None)

            elif file_extension in ['.xlsx', '.xls']:

                # select the sheet from the file
                excel_window = ExcelDialog(self, filename)
                excel_window.exec()
                sheet_index = excel_window.excel_sheet

                if sheet_index is not None:
                    self.original_data_frame = pd.read_excel(filename, sheet_name=sheet_index, index_col=None)
                else:
                    return

            # check for duplicates
            unique_hdr, duplicate_hdr = find_duplicates(arr=list(self.original_data_frame.columns))

            if len(duplicate_hdr):
                # notify
                logger = Logger()
                for hdr in duplicate_hdr:
                    logger.add_error("Duplicated header", device=hdr)

                logs_dialogue = LogsDialogue(name="Duplictaed headers", logger=logger, expand_all=True)
                logs_dialogue.exec()

                # filter the headers
                self.original_data_frame = self.original_data_frame[unique_hdr]

            # set the profile names list
            self.set_combo_boxes()
            self.assign()
            self.display_associations()
            self.assigned_count = 0

    def do_it(self) -> None:
        """
        Close. The data has to be queried later to the object by the parent by calling get_association_data
        """

        if self.assigned_count == 0:
            # maybe the user clicked on accept without assigning, so assign as a last resort
            self.assign()

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


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)

    class TestObj:
        def __init__(self, name, code, x=0, y=0, latitude=0, longitude=0):
            self.name = name
            self.code = code
            self.x = x
            self.y = y
            self.latitude = latitude
            self.longitude = longitude


    window = CoordinatesInputGUI(list_of_objects=[TestObj('Test object', 'code')] * 10)
    window.resize(1.61 * 700.0, 600.0)  # golden ratio
    window.show()
    sys.exit(app.exec_())
