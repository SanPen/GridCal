import gc
import os.path
from typing import List, Union
import webbrowser
import darkdetect
import pandas as pd
import qdarktheme
# Engine imports

# GUI imports
from GridCal.Gui.GuiFunctions import *
from GridCal.Gui.messages import *
from GridCal.Gui.RosetaExplorer.MainWindow import *
from GridCal.Gui.TreeModelViewer.TreeModelViewer import TreeModelViewerGUI

from GridCalEngine.IO.cim.cgmes.cgmes_circuit import CgmesCircuit
from GridCalEngine.IO.cim.cgmes.cgmes_enums import cgmesProfile
from GridCalEngine.IO.raw.devices.psse_circuit import PsseCircuit
from GridCalEngine.IO.cim.db.db_handler import DbHandler
from GridCalEngine.data_logger import DataLogger

try:
    from GridCal.Gui.RosetaExplorer.ConsoleWidget import ConsoleWidget

    qt_console_available = True
except ModuleNotFoundError:
    print('No qtconsole available')
    qt_console_available = False


def clear_qt_layout(layout):
    """
    Remove all widgets from a layout object
    :param layout:
    """
    for i in reversed(range(layout.count())):
        layout.itemAt(i).widget().deleteLater()


########################################################################################################################
# Main Window
########################################################################################################################


class RosetaExplorerGUI(QMainWindow):
    """

    """

    def __init__(self, parent=None, db_handler: Union[DbHandler, None] = None):
        """

        @param parent:
        """

        # create main window
        QMainWindow.__init__(self, parent)
        self.ui = Ui_mainWindow()
        self.ui.setupUi(self)
        self.title = 'Roseta Explorer'
        self.setWindowTitle(self.title)
        self.setAcceptDrops(True)

        # 1:4
        self.ui.main_splitter.setStretchFactor(0, 1)
        self.ui.main_splitter.setStretchFactor(1, 8)
        self.ui.lookup_db_splitter.setStretchFactor(0, 1)
        self.ui.lookup_db_splitter.setStretchFactor(1, 6)

        self.open_file_thread_object = None

        self.accepted_extensions = ['.zip', '.xml', '.raw']
        self.project_directory = ''
        self.lock_ui = True

        self.tree_navigation_windows: List[TreeModelViewerGUI] = list()

        self.circuit: Union[CgmesCircuit, PsseCircuit, None] = None

        self.logger: DataLogger = DataLogger()

        # Representation models
        self.classes_model = None
        self.properties_model = None
        self.properties_proxy_model = QtCore.QSortFilterProxyModel(self.ui.propertiesTableView)
        self.properties_proxy_model.setRecursiveFilteringEnabled(False)
        self.properties_proxy_model.setFilterKeyColumn(0)
        self.ui.propertiesTableView.setSortingEnabled(True)

        # DB
        self.db_handler: DbHandler = DbHandler(new_db=False) if db_handler is None else db_handler
        self.update_combo_boxes()

        # Console
        self.console = None
        try:
            self.create_console()
        except TypeError:
            error_msg('The console has failed because the QtConsole guys have a bug in their package :(')

        # Connections --------------------------------------------------------------------------------------------------

        # triggered
        self.ui.actionSave_logs.triggered.connect(self.save_logs)

        self.ui.actionNavigation_tree.triggered.connect(self.launch_tree_view)

        self.ui.actionNew.triggered.connect(self.new_rosetta_explorer)

        self.ui.actionDocumentation.triggered.connect(self.show_docs)

        self.ui.actionAbout.triggered.connect(self.about)

        # clicked

        self.ui.filterButton.clicked.connect(self.filter_properties_table)
        self.ui.modelTypeLabel.mouseDoubleClickEvent = self.display_circuit

        # text changed

        self.ui.filterComboBox.currentTextChanged.connect(self.on_filter_combobox_changed)

        self.ui.availableDBsComboBox.currentTextChanged.connect(self.available_db_combo_box_changed)

        # lineedit enter

        self.ui.filterLineEdit.returnPressed.connect(self.filter_properties_table)

        # list clicks

        self.ui.clasesListView.clicked.connect(self.on_class_click)

        self.ui.dbTablesListView.clicked.connect(self.on_look_up_db_class_click)

        self.UNLOCK()
        self.update_combo_boxes()

    def LOCK(self, val=True):
        """
        Lock the interface to prevent new simulation launches
        :param val:
        :return:
        """
        self.lock_ui = val
        self.ui.progress_frame.setVisible(self.lock_ui)
        QtGui.QGuiApplication.processEvents()

    def UNLOCK(self):
        """
        Unlock the interface
        """
        if not self.any_thread_running():
            self.LOCK(False)

    def create_console(self):
        """
        Create console
        """
        if qt_console_available:
            if self.console is not None:
                clear_qt_layout(self.ui.consoleLayout.layout())

            self.console = ConsoleWidget(customBanner="Roseta Grid Converter console.\n\n"
                                                      "type hlp() to see the available specific commands.\n\n"
                                                      "the following libraries are already loaded:\n"
                                                      "np: numpy\n"
                                                      "pd: pandas\n"
                                                      "app: This instance of Roseta Grid Converter\n"
                                                      "circuit or app.circuit: The current grid\n\n")

            self.console.buffer_size = 10000

            # add the console widget to the user interface
            self.ui.consoleLayout.layout().addWidget(self.console)

            # push some variables to the console
            self.console.push_vars({"np": np,
                                    "pd": pd,
                                    'app': self,
                                    'circuit': self.circuit})

    def update_combo_boxes(self):
        """
        Properly update te combo boxes
        """
        if type(self.circuit) == PsseCircuit:
            # we do this first so that the model changing does not trigger the on_combo_box_text_change function
            if self.db_handler.psse_lookup_db.last_file_opened in self.db_handler.psse_lookup_db.list_of_db_files:
                idx = self.db_handler.psse_lookup_db.list_of_db_files.index(
                    self.db_handler.psse_lookup_db.last_file_opened)
            else:
                idx = 0

            self.ui.availableDBsComboBox.setModel(get_list_model(self.db_handler.psse_lookup_db.list_of_db_files))
            self.ui.availableDBsComboBox.setCurrentIndex(idx)

        elif type(self.circuit) == CgmesCircuit:

            # we do this first so that the model changing does not trigger the on_combo_box_text_change function
            if self.db_handler.cgmes_lookup_db.last_file_opened in self.db_handler.cgmes_lookup_db.list_of_db_files:
                idx = self.db_handler.cgmes_lookup_db.list_of_db_files.index(
                    self.db_handler.cgmes_lookup_db.last_file_opened)
            else:
                idx = 0

            self.ui.availableDBsComboBox.setModel(get_list_model(self.db_handler.cgmes_lookup_db.list_of_db_files))
            self.ui.availableDBsComboBox.setCurrentIndex(idx)

        else:
            pass

    def get_process_threads(self):
        """
        Get all threads that has to do with processing
        :return: list of process threads
        """
        all_threads = [self.open_file_thread_object]
        return all_threads

    def get_all_threads(self):
        """
        Get all threads
        :return: list of all threads
        """
        all_threads = self.get_process_threads()
        return all_threads

    def any_thread_running(self):
        """
        Checks if any thread is running
        :return: True/False
        """
        val = False

        # this list cannot be created only once, because the None will be copied
        # instead of being a pointer to the future value like it would in a typed language
        all_threads = self.get_all_threads()

        for thr in all_threads:
            if thr is not None:
                if thr.isRunning():
                    return True
        return val

    def dragEnterEvent(self, event):
        """

        :param event:
        :return:
        """
        if event.mimeData().hasUrls:
            event.accept()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        """

        :param event:
        :return:
        """
        if event.mimeData().hasUrls:
            event.accept()
        else:
            event.ignore()

    def on_filter_combobox_changed(self):
        """
        Main property chooser for filtering table data
        """
        idx = self.ui.filterComboBox.currentIndex()

        if idx > -1:
            self.properties_proxy_model.setFilterKeyColumn(idx)

    def filter_properties_table(self):
        """
        Action of filtering the main table data
        """
        self.properties_proxy_model.setFilterRegExp(self.ui.filterLineEdit.text())

    def set_grid_model(self, circuit: Union[CgmesCircuit, PsseCircuit]):
        """
        Set a grid Model
        :param circuit: circuit model passed
        :param
        """
        if type(circuit) in [CgmesCircuit, PsseCircuit]:
            self.circuit = circuit

            self.display_circuit(trim_empty=True)

    def display_circuit(self, trim_empty=False):
        """

        :param trim_empty:
        :return:
        """
        if self.circuit is not None:
            classes = [prop.property_name for prop in self.circuit.get_class_properties()]
            classes.sort()

            if trim_empty:
                classes = [cl for cl in classes if len(self.circuit.get_objects_list(elm_type=cl)) > 0]

            self.classes_model = get_list_model(classes)

            self.ui.clasesListView.setModel(self.classes_model)

            self.set_model_label()
            self.update_combo_boxes()
            self.available_db_combo_box_changed()

            if self.console:
                self.console.push_vars({'app': self,
                                        'circuit': self.circuit})

    def set_model_label(self):
        """
        Set the model label based on the model inner type
        """
        if isinstance(self.circuit, PsseCircuit):
            self.ui.modelTypeLabel.setText("PSSe")
            self.setWindowTitle(self.title + ': PSSe')

        elif isinstance(self.circuit, CgmesCircuit):
            self.ui.modelTypeLabel.setText("CGMES")
            self.setWindowTitle(self.title + ': CGMES')

        else:
            raise Exception('Unknown circuit type :(')

    def set_logger(self, logger: DataLogger, message=True):
        """
        Set the main logger
        :param logger: DataLogger object
        :param message: Open message if relevant
        """
        self.logger = logger  # assign the logger pointer
        logger_model = get_logger_tree_model(logger)  # crete tree model
        self.ui.loggerTreeView.setModel(logger_model)  # display

        if logger.size():
            error_msg(logger.get_message(), 'Logger')

    def on_class_click(self):
        """
        On click on the classes list...
        """
        # get the class type
        elm_type = self.ui.clasesListView.selectedIndexes()[0].data(role=QtCore.Qt.DisplayRole)

        # get the objects list of said class depending on the circuit type
        if isinstance(self.circuit, PsseCircuit):
            objects = self.circuit.get_objects_list(elm_type)

        elif isinstance(self.circuit, CgmesCircuit):
            objects = self.circuit.get_objects_list(elm_type)

        else:
            raise Exception('Unknown circuit type :(')

        # represent the model
        if len(objects) > 0:

            editable_headers = {p.property_name: p for p in objects[0].get_properties()}
            headers = [p.property_name for p in objects[0].get_properties()]

        else:

            editable_headers = dict()
            headers = list()

        self.ui.filterComboBox.setModel(get_list_model(headers))

        self.properties_model = RosetaObjectsModel(objects=objects,
                                                   editable_headers=editable_headers,
                                                   parent=self.ui.propertiesTableView,
                                                   editable=True,
                                                   non_editable_attributes=[],
                                                   dictionary_of_lists={})

        self.properties_proxy_model.setSourceModel(self.properties_model)
        self.ui.propertiesTableView.setModel(self.properties_proxy_model)

    def save_logs(self):
        """
        Save logger content
        """
        if self.logger.size():

            file, selected_filter = QtWidgets.QFileDialog.getSaveFileName(self, "Export logs", '',
                                                                          filter="Excel files (*.xlsx)")

            if file != '':
                if 'xlsx' in selected_filter:
                    f = file
                    if not f.endswith('.xlsx'):
                        f += '.xlsx'
                    self.logger.to_xlsx(f)

                else:
                    error_msg(file[0] + ' is not valid :(')
        else:
            warning_msg('There no logs :)')

    def launch_tree_view(self):
        """
        Launch tree view of the model
        """
        if self.circuit is not None:

            if isinstance(self.circuit, CgmesCircuit):
                window = TreeModelViewerGUI()
                self.tree_navigation_windows.append(window)
                h = 740
                window.resize(int(1.61 * h), h)  # golden ratio :)

                window.set_circuit(self.circuit)

                window.show()
            else:
                info_msg("Only CGMES models are available for the tree view :/")
        else:
            warning_msg("There is not model :/")

    def new_rosetta_explorer(self, model: Union[PsseCircuit, CgmesCircuit, None] = None,
                             logger: Union[DataLogger, None] = None):
        """
        New roseta window
        :param model: (optional) the model to load
        :param logger: (optional) DataLogger to display
        """
        window = RosetaExplorerGUI(db_handler=self.db_handler)
        self.tree_navigation_windows.append(window)
        h = 740
        window.resize(int(1.61 * h), h)  # golden ratio :)

        if model is not None:
            window.set_grid_model(model)

        if logger is not None:
            window.set_logger(logger)

        window.show()

    def available_db_combo_box_changed(self):
        """
        Read PSSe lookup DB
        """
        name = self.ui.availableDBsComboBox.currentText()

        if type(self.circuit) == PsseCircuit:
            self.db_handler.psse_lookup_db.read_db_file(name)
            self.ui.dbTablesListView.setModel(get_list_model(self.db_handler.psse_lookup_db.get_structures_names()))
            self.on_look_up_db_class_click()

        elif type(self.circuit) == CgmesCircuit:
            self.db_handler.cgmes_lookup_db.read_db_file(name)
            self.ui.dbTablesListView.setModel(get_list_model(self.db_handler.cgmes_lookup_db.get_structures_names()))
            self.on_look_up_db_class_click()

    def on_look_up_db_class_click(self):
        """

        :return:
        """

        if len(self.ui.dbTablesListView.selectedIndexes()) > 0:
            elm_type = self.ui.dbTablesListView.selectedIndexes()[0].data(role=QtCore.Qt.DisplayRole)

            if type(self.circuit) == PsseCircuit:
                db = self.db_handler.psse_lookup_db
                df = getattr(db, elm_type)
                mdl = PandasModel(data=df)

            elif type(self.circuit) == CgmesCircuit:
                objects = self.db_handler.cgmes_lookup_db.circuit.elements_by_type.get(elm_type, [])
                if len(objects) > 0:
                    editable_headers = {p.property_name: p for p in objects[0].get_properties()}
                    headers = [p.property_name for p in objects[0].get_properties()]

                else:
                    editable_headers = dict()
                    headers = list()

                mdl = ObjectsModelOld(objects=objects,
                                      editable_headers=editable_headers,
                                      parent=self.ui.propertiesTableView,
                                      editable=True,
                                      dictionary_of_lists={})
            else:
                return

            # set the model
            self.ui.dbTableView.setModel(mdl)
        else:
            self.ui.dbTableView.setModel(None)

    @staticmethod
    def show_docs():
        """
        Show the docs
        """
        this_py_file = os.path.realpath(__file__)
        current_folder_path, current_folder_name = os.path.split(this_py_file)
        index_path = os.path.join(current_folder_path, '..', '..', 'docs', 'html', 'index.html')
        if os.path.exists(index_path):
            webbrowser.open(index_path, new=2)
        else:
            error_msg("The documentation could not be found under " + index_path)

    def about(self):
        """
        Show the "about" dialogue
        :return:
        """
        pass


def runRosetaExplorer(use_native_dialogues=False):
    """
    Main function to run the GUI
    :return:
    """
    import sys
    qdarktheme.enable_hi_dpi()
    app = QApplication()
    # app.setStyle('Fusion')  # ['Breeze', 'Oxygen', 'QtCurve', 'Windows', 'Fusion']

    # Apply the complete dark theme to your Qt App.
    qdarktheme.setup_theme(
        theme='auto',
        custom_colors={
            "primary": "#00aa88ff",
            "primary>list.selectionBackground": "#00aa88be"
        }
    )

    # dark = QDarkPalette(None)
    # dark.set_app(app)

    window = RosetaExplorerGUI()
    h = 740
    window.resize(int(1.61 * h), h)  # golden ratio :)
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    runRosetaExplorer()
