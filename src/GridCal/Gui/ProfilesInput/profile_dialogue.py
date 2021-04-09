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
from GridCal.Gui.ProfilesInput.gui import *
from GridCal.Gui.ProfilesInput.excel_dialog import *


class PandasModel(QtCore.QAbstractTableModel):
    """
    Class to populate a Qt table view with a pandas data frame
    """
    def __init__(self, data, parent=None):
        QtCore.QAbstractTableModel.__init__(self, parent)
        self._data = np.array(data.values)
        self._cols = data.columns
        self._index = data.index.values
        self.r, self.c = np.shape(self._data)
        self.isDate = False

        if len(self._index) > 0:
            if isinstance(self._index[0], np.datetime64):
                self._index = pd.to_datetime(self._index)
                self.isDate = True

        self.formatter = lambda x: "%.2f" % x

    def rowCount(self, parent=None):
        return self.r

    def columnCount(self, parent=None):
        return self.c

    def data(self, index, role=QtCore.Qt.DisplayRole):
        if index.isValid():
            if role == QtCore.Qt.DisplayRole:
                # return self.formatter(self._data[index.row(), index.column()])
                return str(self._data[index.row(), index.column()])
        return None

    def headerData(self, p_int, orientation, role):
        if role == QtCore.Qt.DisplayRole:
            if orientation == QtCore.Qt.Horizontal:
                return self._cols[p_int]
            elif orientation == QtCore.Qt.Vertical:
                if self._index is None:
                    return p_int
                else:
                    if self.isDate:
                        return self._index[p_int].strftime('%Y/%m/%d  %H:%M.%S')
                    else:
                        return str(self._index[p_int])
        return None


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


class MultiplierType(Enum):
    Mult = 1


class Association:

    def __init__(self, name, code, scale=1, multiplier=1, profile_name=''):
        """

        :param name:
        :param code:
        :param scale:
        :param multiplier:
        :param profile_name:
        """
        self.name: str = name
        self.code: str = code
        self.scale: float = scale
        self.multiplier: float = multiplier
        self.profile_name: str = profile_name

    def get_at(self, idx):

        if idx == 0:
            return self.name
        elif idx == 1:
            return self.code
        elif idx == 2:
            return self.profile_name
        elif idx == 3:
            return self.scale
        elif idx == 4:
            return self.multiplier
        else:
            return ''


class Associations(QAbstractTableModel):

    def __init__(self):
        QtCore.QAbstractTableModel.__init__(self)

        self.__values: List[Association] = list()

        self.__headers = ['Name', 'Code', 'Profile', 'Scale', 'Multiplier']

    def append(self, val: Association):
        self.__values.append(val)

    def set_profile_at(self, idx, value):
        self.__values[idx].profile_name = value

    def set_scale_at(self, idx, value):
        self.__values[idx].scale = value

    def set_multiplier_at(self, idx, value):
        self.__values[idx].multiplier = value

    def get_profile_at(self, idx):
        return self.__values[idx].profile_name

    def get_scale_at(self, idx):
        return self.__values[idx].scale

    def get_multiplier_at(self, idx):
        return self.__values[idx].multiplier

    def clear_at(self, idx):
        self.__values[idx].profile_name = ''
        self.__values[idx].scale = 1
        self.__values[idx].multiplier = 1

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


class StringSubstitutions(Enum):
    PSSeBranchName = 'N1_NME1_V1_N2_NME2_V2_CKT -> N1_N2_CKT'
    PSSeBusGenerator = 'N1_NME1_V1 -> N1_1'
    PSSeBusLoad = 'N -> N_1'


class ProfileInputGUI(QtWidgets.QDialog):

    def __init__(self, parent=None, list_of_objects=None, magnitudes=[''], use_native_dialogues=True):
        """

        Args:
            parent:
            list_of_objects: List of objects to which set a profile to
            magnitudes: Property of the objects to which set the pandas DataFrame
            list_of_objects: list ob object to modify
            use_native_dialogues: use the native file selection dialogues?
        """
        QtWidgets.QDialog.__init__(self, parent)
        if list_of_objects is None:
            list_of_objects = list()
        self.ui = Ui_Dialog()
        self.ui.setupUi(self)
        self.setWindowTitle('Profiles import dialogue')

        self.project_directory = None

        self.magnitudes = magnitudes

        self.use_native_dialogues = use_native_dialogues

        # results
        self.data = None
        self.time = None
        self.zeroed = None
        self.normalized = False

        # units
        self.units = dict()
        self.units['Y'] = 1e24
        self.units['Z'] = 1e21
        self.units['E'] = 1e18
        self.units['P'] = 1e15
        self.units['T'] = 1e12
        self.units['G'] = 1e9
        self.units['M'] = 1e6
        self.units['k'] = 1e3
        self.units['-'] = 1.0
        self.units['m'] = 1e-3
        self.units['µ'] = 1e-6
        self.units['n'] = 1e-9
        self.units['p'] = 1e-12
        self.units['f'] = 1e-15
        self.units['a'] = 1e-18
        self.units['z'] = 1e-21
        self.units['y'] = 1e-24

        relevant_units = ['T', 'G', 'M', 'k', '-', 'm']
        self.ui.units_combobox.addItems(relevant_units)
        self.ui.units_combobox.setCurrentIndex(2)

        # setup the plot widget
        self.ui.plotwidget.canvas.ax.clear()
        self.ui.plotwidget.canvas.draw()

        # initialize the objectives list
        self.objects = list_of_objects

        # initialize associations
        self.also_reactive_power = False

        self.associations = Associations()
        for elm in list_of_objects:
            self.associations.append(Association(elm.name, elm.code))
        self.display_associations()

        self.ui.splitter.setStretchFactor(0, 3)
        self.ui.splitter.setStretchFactor(1, 7)

        # set name transformations
        self.transformations = {
                                StringSubstitutions.PSSeBranchName.value: StringSubstitutions.PSSeBranchName,
                                StringSubstitutions.PSSeBusGenerator.value: StringSubstitutions.PSSeBusGenerator,
                                StringSubstitutions.PSSeBusLoad.value: StringSubstitutions.PSSeBusLoad
                                }
        self.ui.nameTransformationComboBox.setModel(get_list_model(list(self.transformations.keys())))

        self.original_data_frame = None

        self.profile_names = list()

        # click
        self.ui.open_button.clicked.connect(self.import_profile)
        self.ui.doit_button.clicked.connect(lambda: self.set_multiplier(MultiplierType.Mult))
        self.ui.set_multiplier_button.clicked.connect(lambda: self.set_multiplier(MultiplierType.Mult))
        self.ui.autolink_button.clicked.connect(self.auto_link)
        self.ui.rnd_link_pushButton.clicked.connect(self.rnd_link)
        self.ui.assign_to_selection_pushButton.clicked.connect(self.link_to_selection)
        self.ui.assign_to_all_pushButton.clicked.connect(self.link_to_all)
        self.ui.doit_button.clicked.connect(self.do_it)
        self.ui.clear_selection_button.clicked.connect(self.clear_selection)
        self.ui.transformNamesPushButton.clicked.connect(self.transform_names)

        # double click
        self.ui.sources_list.doubleClicked.connect(self.sources_list_double_click)
        self.ui.assignation_table.doubleClicked.connect(self.assignation_table_double_click)
        self.ui.tableView.doubleClicked.connect(self.print_profile)

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

    def get_multiplier(self):
        """
        Gets the necessary multiplier to pass the profile units to Mega
        Remember that the power units in GridCal are the MVA
        """
        unit = self.ui.units_combobox.currentText()
        return self.units[unit] / self.units['M']

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

        if len(filename) > 0:
            # get the filename extension
            name, file_extension = os.path.splitext(filename)

            # Depending on the extension load the file
            if file_extension == '.csv':
                self.original_data_frame = pd.read_csv(filename, index_col=0)

            elif file_extension in ['.xlsx', '.xls']:

                # select the sheet from the file
                window = ExcelDialog(self, filename)
                window.exec_()
                sheet_index = window.excel_sheet

                if sheet_index is not None:

                    self.original_data_frame = pd.read_excel(filename, sheet_name=sheet_index, index_col=0)

                else:
                    return

            # try to format the data
            try:
                self.original_data_frame = self.original_data_frame.astype(float)
            except:
                self.msg('The format of the data is not recognized. Only int or float values are allowed')
                return

            # set the profile names list
            self.profile_names = np.array([str(e).strip() for e in self.original_data_frame.columns.values], dtype=object)
            self.display_profiles()

    def sources_list_double_click(self):
        """
        When an item in the sources list is double clicked, plot the series
        :return:
        """
        if self.original_data_frame is not None:
            idx = self.ui.sources_list.selectedIndexes()[0].row()

            col_name = self.original_data_frame.columns[idx]

            self.ui.plotwidget.canvas.ax.clear()
            self.original_data_frame[col_name].plot(ax=self.ui.plotwidget.canvas.ax)
            self.ui.plotwidget.canvas.draw()

    def display_associations(self):
        """

        @return:
        """
        self.ui.assignation_table.setModel(self.associations)
        self.ui.assignation_table.repaint()

    def display_profiles(self):
        # set the loaded data_frame to the GUI
        model = PandasModel(self.original_data_frame)
        self.ui.tableView.setModel(model)
        self.ui.sources_list.setModel(get_list_model(self.profile_names))

    def print_profile(self):
        """
        prints the profile clicked on the table
        @return:
        """
        if self.original_data_frame is not None:
            idx = self.ui.tableView.selectedIndexes()[0].column()
            name = self.profile_names[idx]
            if idx >= 0:
                self.ui.plotwidget.canvas.ax.clear()
                self.original_data_frame[name].plot(ax=self.ui.plotwidget.canvas.ax)
                self.ui.plotwidget.canvas.draw()

    def make_association(self, source_idx, obj_idx, scale=None, mult=None, col_idx=None):
        """
        Makes an association in the associations table
        """
        if scale is None:
            scale = self.get_multiplier()

        if mult is None:
            mult = 1.0

        self.associations.set_profile_at(obj_idx, self.profile_names[source_idx])
        self.associations.set_scale_at(obj_idx, scale)
        self.associations.set_multiplier_at(obj_idx, mult)

    def assignation_table_double_click(self):
        """
        Set the selected profile into the clicked slot
        """
        if len(self.ui.sources_list.selectedIndexes()) > 0:
            idx_s = self.ui.sources_list.selectedIndexes()[0].row()
            idx_o = self.ui.assignation_table.selectedIndexes()[0].row()
            col = self.ui.assignation_table.selectedIndexes()[0].column()

            self.make_association(idx_s, idx_o, mult=None, col_idx=col)

            # self.display_associations()

    def set_multiplier(self, tpe):
        """
        Set the table multipliers
        """
        if len(self.ui.assignation_table.selectedIndexes()) > 0:
            mult = self.ui.multSpinBox.value()
            for index in self.ui.assignation_table.selectedIndexes():
                idx = index.row()

                if tpe == MultiplierType.Mult:
                    self.associations.set_multiplier_at(idx, mult)

            self.display_associations()

    @staticmethod
    def normalize_string(s):
        """
        Normalizes a string
        """
        for p in string.punctuation:
            s = s.replace(p, '')
        return s.lower().strip()

    def check_simularity(self, name_to_search, names_array, threshold):
        """

        :param name_to_search:
        :param names_array:
        :param threshold:
        :return:
        """

        if name_to_search in names_array:
            return np.where(names_array == name_to_search)[0][0]

        # else determine the likelihood
        if threshold > 0.01:
            max_val = 0
            max_idx = None
            for idx_s, col_name in enumerate(names_array):
                profile_name = col_name.strip()

                # find the string distance
                d = SequenceMatcher(None, name_to_search, profile_name).ratio()

                if d > max_val:
                    max_val = d
                    max_idx = idx_s

            # assign the string with the closest profile (60% or better similarity)
            if max_idx is not None and max_val > threshold:
                return max_idx
            else:
                return None
        else:
            return None

    def auto_link(self):
        """
        Performs an automatic link between the sources and the objectives based on the names
        """
        mult = self.get_multiplier()
        threshold = self.ui.autolink_slider.value() / 100.0

        for idx_o, elm in enumerate(self.objects):

            idx = self.check_simularity(name_to_search=elm.name.strip(),
                                        names_array=self.profile_names,
                                        threshold=threshold)

            # assign the string with the closest profile (60% or better similarity)
            if idx is not None:
                self.make_association(idx, idx_o, mult)

        self.display_associations()

    def rnd_link(self):
        """
        Random link
        """
        # scale = self.get_multiplier()
        mult = 1
        scale = self.get_multiplier()

        if self.ui.sources_list.model() is not None:

            if self.ui.sources_list.model().rowCount() > 0:
                # make a list of the source indices
                source_indices = [i for i in range(self.ui.sources_list.model().rowCount())]

                # make a list of the destination indices
                destination_indices = [i for i in range(self.ui.assignation_table.model().rowCount())]

                # while there are elements in the destination indices
                while len(destination_indices) > 0:

                    # pick a random source
                    rnd_idx_s = randint(0, len(source_indices)-1)

                    # pick and delete a random destination
                    rnd_idx_o = randint(0, len(destination_indices)-1)

                    # get the actual index
                    idx_s = source_indices[rnd_idx_s]

                    # get the actual index
                    idx_o = destination_indices.pop(rnd_idx_o)

                    # make the association
                    self.make_association(idx_s, idx_o, scale, mult)

                self.display_associations()
            else:
                pass
        else:
            pass

    def link_to_selection(self):
        """
        Links the selected origin with the selected destinations
        """

        if len(self.ui.sources_list.selectedIndexes()) > 0:
            idx_s = self.ui.sources_list.selectedIndexes()[0].row()

            scale = self.get_multiplier()
            mult = 1
            scale = self.get_multiplier()

            # set of different rows
            sel_rows = {item.row() for item in self.ui.assignation_table.selectedIndexes()}

            for idx_o in sel_rows:
                self.make_association(idx_s, idx_o, scale, mult)

            self.display_associations()

    def link_to_all(self):
        """
        Links the selected origin with all the destinations
        """

        if len(self.ui.sources_list.selectedIndexes()) > 0:
            idx_s = self.ui.sources_list.selectedIndexes()[0].row()
            mult = 1
            scale = self.get_multiplier()

            # set of different rows
            n_rows = self.ui.assignation_table.model().rowCount()

            for idx_o in range(n_rows):
                self.make_association(idx_s, idx_o, scale, mult)

            self.display_associations()

    def get_profile(self, parent=None, labels=None, alsoQ=None):
        """
        Return ths assigned profiles
        @return:
            Array of profiles assigned to the input objectives
            Array specifying which objectives are not assigned
        """

        if self.original_data_frame is None:
            return None, None, None

        n_obj = len(self.objects)
        rows_o, cols_o = np.shape(self.original_data_frame)

        profiles = [None] * n_obj
        zeroed = [False] * n_obj  # array to know which profiles are only zeros

        for i_obj in range(n_obj):

            scale = self.associations.get_scale_at(i_obj)
            mult = self.associations.get_multiplier_at(i_obj)
            profile_name = self.associations.get_profile_at(i_obj)

            if profile_name != '':
                # active power
                if self.also_reactive_power:
                    vals = self.original_data_frame[profile_name].values * scale * mult + 0j
                else:
                    vals = self.original_data_frame[profile_name].values * scale * mult

            else:
                vals = np.zeros(rows_o)

                if self.ui.setUnassignedToZeroCheckBox.isChecked():
                    zeroed[i_obj] = False
                else:
                    zeroed[i_obj] = True

            profiles[i_obj] = vals

        time_profile = self.original_data_frame.index

        return np.array(profiles).transpose(), time_profile, zeroed

    def clear_selection(self):
        """
        Clear the selected associations
        """
        for idx in self.ui.assignation_table.selectedIndexes():
            obj_idx = idx.row()
            self.associations.clear_at(obj_idx)
        self.display_associations()

    def transform_names(self):
        """
        Transform the names of the inputs
        :return:
        """
        if self.original_data_frame is not None:
            mode_txt = self.ui.nameTransformationComboBox.currentText()
            mode = self.transformations[mode_txt]

            if mode == StringSubstitutions.PSSeBranchName:

                for i, name in enumerate(self.profile_names):
                    if '_':
                        vals = name.split('_')
                        if len(vals) < 7:
                            pass
                        else:
                            self.profile_names[i] = vals[0] + '_' + vals[3] + '_' + vals[6]
                self.original_data_frame.columns = self.profile_names
                self.display_profiles()

            if mode == StringSubstitutions.PSSeBusGenerator:

                for i, name in enumerate(self.profile_names):
                    if '_':
                        vals = name.split('_')
                        if len(vals) == 3:
                            self.profile_names[i] = vals[0] + '_1'
                self.original_data_frame.columns = self.profile_names
                self.display_profiles()

            elif mode == StringSubstitutions.PSSeBusLoad:
                for i, name in enumerate(self.profile_names):
                    self.profile_names[i] = name + '_1'
                self.original_data_frame.columns = self.profile_names
                self.display_profiles()

    def do_it(self):
        """
        Close. The data has to be queried later to the object by the parent by calling get_association_data
        """

        # Generate profiles
        self.data, self.time, self.zeroed = self.get_profile()
        self.normalized = self.ui.normalized_checkBox.isChecked()

        if self.normalized:
            self.data /= self.data.max(axis=0)  # divide each series by the maximum
            self.data = np.nan_to_num(self.data)  # set nan to zero

        self.close()


class TestObj:
    def __init__(self, name, code):
        self.name = name
        self.code = code


if __name__ == "__main__":

    app = QtWidgets.QApplication(sys.argv)
    window = ProfileInputGUI(list_of_objects=[TestObj('Test object', 'code')] * 10)
    window.resize(1.61 * 700.0, 600.0)  # golden ratio
    window.show()
    sys.exit(app.exec_())

