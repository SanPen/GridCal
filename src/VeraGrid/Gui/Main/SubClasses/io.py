# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

import os
import pathlib
import tempfile
from typing import Dict, Union, List, Callable
from PySide6 import QtWidgets, QtGui

import VeraGrid.Gui.gui_functions as gf
import VeraGrid.Session.export_results_driver as exprtdrv
import VeraGrid.Session.file_handler as filedrv
from VeraGrid.Gui.GridMerge.grid_diff import GridDiffDialogue
from VeraGrid.Gui.GridMerge.grid_merge import GridMergeDialogue
from VeraGrid.plugins import install_plugin, get_plugin_info
from VeraGrid.Gui.FileDialogues.CoordinatesInput.coordinates_dialogue import CoordinatesInputGUI
from VeraGrid.Gui.general_dialogues import LogsDialogue, CustomQuestionDialogue, FileTypeSelector
from VeraGrid.Gui.Diagrams.SchematicWidget.schematic_widget import SchematicWidget
from VeraGrid.Gui.messages import yes_no_question, error_msg, warning_msg, info_msg
from VeraGrid.Gui.GridGenerator.grid_generator_dialogue import GridGeneratorGUI
from VeraGrid.Gui.FileDialogues.RosetaExplorer.RosetaExplorer import RosetaExplorerGUI
from VeraGrid.Gui.FileDialogues.CGMESDialogue.cgmes_import import CgmesImportDialogue
from VeraGrid.Gui.FileDialogues.DgsDialogue.dgs_export import DgsExportDialogue
from VeraGrid.Gui.FileDialogues.DgsDialogue.dgs_import import DgsImportDialogue
from VeraGrid.Gui.FileDialogues.MatpowerDialogue.matpower_export import MatpowerExportDialogue
from VeraGrid.Gui.FileDialogues.UcteDialogue.ucte_export import UcteExportDialogue
from VeraGrid.Gui.Main.SubClasses.Model.scenarios import ScenariosMain
from VeraGrid.Gui.FileDialogues.ServerFileDialog import ServerFileDialogue
from VeraGrid.Gui.dialog_lifecycle import delete_dialog_safely, exec_dialog_safely, is_dialog_available
from VeraGrid.Gui.FileDialogues.CGMESDialogue.cgmes_export import CgmesExportDialogue
from VeraGrid.Gui.FileDialogues.PsseDialogue.psse_export import PsseExportDialogue
from VeraGrid.Gui.FileDialogues.PsseDialogue.psse_import import PsseImportDialogue
from VeraGridEngine.Devices.multi_circuit import MultiCircuit
from VeraGridEngine.Devices.multiverse import MultiVerse, ScenarioNode
from VeraGridEngine.Compilers.circuit_to_pgm import PGM_AVAILABLE, PGM_UNAVAILABLE_REASON
from VeraGridEngine.IO.file_save import FileSavingOptions
from VeraGridEngine.IO.file_open import determine_file_type, FileOpen
from VeraGridEngine.basic_structures import Logger
from VeraGridEngine.enumerations import SimulationTypes, FileType
from VeraGridEngine.IO.veragrid.contingency_parser import import_contingencies_from_json, export_contingencies_json_file
from VeraGridEngine.IO.veragrid.catalogue import save_catalogue, load_catalogue
from VeraGridEngine.Compilers.Gslv.activation import install_gslv_license
from VeraGrid.Gui.CatalogueElementsDialogue.catalogue_elements_dialogue import CatalogueElementsSelectionDialogue
from VeraGrid.Gui.FmuTemplateEditor.fmu_template_editor import FmuTemplateEditorDialog
from VeraGrid.Gui.ManufacturerNativeImporter.manufacturer_native_importer import ManufacturerNativeImporterDialog
from VeraGridEngine.IO.manufacturer_native.worker_artifact import ManufacturerNativeWorkerArtifact
from VeraGridEngine.Devices.Dynamic.fmu_template import FmuTemplate


def get_session_tree_icon_map(session_data_dict: Dict[str, Dict[str, List[str]]]) -> Dict[str, str]:
    """
    Build an icon map for persisted session trees without polluting runtime icon keys.

    Persisted session metadata stores study names as strings because they are file-format
    identifiers used again when loading results from disk. The GUI converts those strings
    to enums only for icon lookup.

    :param session_data_dict: Persisted session tree data.
    :return: Icon map keyed by persisted study name strings.
    """
    simulation_icons: Dict[SimulationTypes, str] = gf.get_simulation_tree_icons()
    icon_map: Dict[str, str] = dict()
    studies: Dict[str, List[str]]
    study_name: str
    simulation_type: SimulationTypes

    for studies in session_data_dict.values():
        for study_name in studies.keys():
            try:
                simulation_type = SimulationTypes(study_name)
            except ValueError:
                pass
            else:
                icon_path: str | None = simulation_icons.get(simulation_type, None)
                if icon_path is not None:
                    icon_map[study_name] = icon_path
                else:
                    pass

    return icon_map


def open_logger_requires_dialog(logger: Logger) -> bool:
    """Return whether a successful file-open log needs a modal dialogue.

    Informational import diagnostics remain available in the logger but do not
    interrupt a successful GUI open. Warnings and errors remain visible because
    they describe states that require review before using the imported circuit.

    :param logger: File-open diagnostic logger to classify.
    :return: ``True`` when the logger contains at least one warning or error.
    """
    warning_count: int = logger.warning_count()
    error_count: int = logger.error_count()
    return warning_count > 0 or error_count > 0


class IoMain(ScenariosMain):
    """
    Inputs-Outputs Main
    """

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        """
        Build the GUI I/O controller and connect file-related actions.

        :param parent: Optional Qt parent widget.
        :return: None.
        """

        # create the main window
        ScenariosMain.__init__(self, parent)

        self.rosetta_gui: Union[RosetaExplorerGUI, None] = None

        self.accepted_extensions = ['.veragrid', '.dveragrid',
                                    '.gridcal', '.dgridcal',
                                    '.xlsx', '.xls', '.sqlite', '.gch5',
                                    '.dgs', '.m', '.matpower', '.raw', '.RAW', '.json', '.uct', '.ucte',
                                    '.iidm', '.xiidm', '.xiidm.bz2',
                                    '.ejson2', '.ejson3', '.p', '.nc', '.hdf5',
                                    '.xml', '.rawx', '.zip', '.dpx', '.pwf', '.epc', '.EPC',
                                    '.ech', '.dta',
                                    '.vgplugin', '.gslv']

        # window pointers
        self.cgmes_dialogue: CgmesExportDialogue | None = None
        self.psse_export_dialogue: PsseExportDialogue | None = None
        self.dgs_export_dialogue: DgsExportDialogue | None = None
        self.matpower_export_dialogue: MatpowerExportDialogue | None = None
        self.ucte_export_dialogue: UcteExportDialogue | None = None
        self.remote_database_file_idtag: str = ""
        self.remote_database_model_idtag: str = ""
        self.remote_database_file_name: str = ""
        self.remote_database_baseline_multiverse: MultiVerse | None = None
        self._pending_remote_database_context: dict[str, object] | None = None
        self._temporary_remote_download_paths: list[str] = list()

        # actions
        self.ui.actionNew_project.triggered.connect(self.new_project)
        self.ui.actionOpen_file.triggered.connect(self.open_file)
        self.ui.actionAdd_circuit.triggered.connect(self.import_circuit)
        self.ui.actionImport_FMU.triggered.connect(self.import_oem_fmu_model)
        self.ui.actionImport_IEEE_CIGRE_DLL.triggered.connect(self.import_oem_manufacturer_native_model)
        self.ui.actionExport_circuit_differential.triggered.connect(self.export_circuit_differential)
        self.ui.actionSave.triggered.connect(self.save_file)
        self.ui.actionSave_as.triggered.connect(self.save_file_as)
        self.ui.actionExport_all_the_device_s_profiles.triggered.connect(self.export_object_profiles)
        self.ui.actionExport_all_results.triggered.connect(self.export_all)
        self.ui.actiongrid_Generator.triggered.connect(self.grid_generator)
        self.ui.actionImport_bus_coordinates.triggered.connect(self.import_bus_coordinates)
        self.ui.actionImport_contingencies.triggered.connect(self.import_contingencies)
        self.ui.actionExport_contingencies.triggered.connect(self.export_contingencies)
        self.ui.actionAdd_default_catalogue.triggered.connect(self.add_default_catalogue)
        self.ui.actionAdd_custom_catalogue.triggered.connect(self.load_custom_catalogue)
        self.ui.actionExportCatalogue.triggered.connect(self.save_custom_catalogue)

        self.ui.actionPSS_e_Raw_Rawx.triggered.connect(self.export_psse)
        self.ui.actionPower_Factory_DGS.triggered.connect(self.export_power_factory)
        self.ui.actionMATPOWER.triggered.connect(self.export_matpower)
        self.ui.actionUCTE.triggered.connect(self.export_ucte)
        self.ui.actionCIM.triggered.connect(self.export_cim)
        self.ui.actionCGMES.triggered.connect(self.export_cgmes)
        self.ui.actionPower_Grid_Models.triggered.connect(self.export_power_grid_models)
        self.ui.actionJSON.triggered.connect(self.export_json)
        self.ui.actionH5.triggered.connect(self.export_h5)
        self.ui.actionMicrosoft_Excel.triggered.connect(self.export_excel)
        self.ui.actionSQLite.triggered.connect(self.export_sqlite)
        self.ui.actionExportVeragridScenario.triggered.connect(self.export_veragrid_scenario)

        # Buttons
        self.ui.exportSimulationDataButton.clicked.connect(self.export_simulation_data)
        self.ui.diskSessionsTreeView.customContextMenuRequested.connect(self.show_disk_sessions_context_menu)
        self.ui.diskSessionsTreeView.setContextMenuPolicy(QtGui.Qt.ContextMenuPolicy.CustomContextMenu)

    def import_oem_fmu_model(self) -> None:
        """
        Import one manufacturer FMU as a reusable dynamic model template.

        The dialog configures a transient template first, so cancelling or
        rejecting invalid metadata leaves the circuit catalogue unchanged.

        :return: None.
        """
        # Build the candidate outside the canonical catalogue. The template
        # becomes project data only after the existing FMU editor validates it.
        template_number: int = self.circuit.get_fmu_templates_number() + 1
        candidate: FmuTemplate = FmuTemplate(name=f"FMU template {template_number}")
        dialog: FmuTemplateEditorDialog = FmuTemplateEditorDialog(
            circuit=self.circuit,
            template=candidate,
            project_directory=self.project_directory,
            parent=self,
        )
        dialog_result: int = exec_dialog_safely(dialog=dialog)
        import_accepted: bool = dialog_result == int(QtWidgets.QDialog.DialogCode.Accepted)
        if import_accepted:
            # Register the validated template once, then rebuild each open
            # editor library from the circuit-owned catalogue.
            self.circuit.add_fmu_template(candidate)
            self.dynamic_editor_workspace_session.refresh_dynamic_library_templates(
                circuit=self.circuit,
            )
            self.view_objects_data()
        else:
            pass

    def import_oem_manufacturer_native_model(
            self, worker_artifact: ManufacturerNativeWorkerArtifact | None = None) -> None:
        """
        Import one manufacturer supplied IEEE/CIGRE DLL or shared library.

        The established importer qualifies the binary in an isolated worker
        and updates the circuit only after all contract checks succeed.

        :param worker_artifact: Optional prepared worker for native qualification.
        :return: None.
        """
        dialog: ManufacturerNativeImporterDialog = ManufacturerNativeImporterDialog(
            assets=self.circuit,
            worker_artifact=worker_artifact,
            parent=self,
        )
        dialog_result: int = exec_dialog_safely(dialog=dialog)
        import_accepted: bool = dialog_result == int(QtWidgets.QDialog.DialogCode.Accepted)
        if import_accepted:
            # Qualification may create provider-backed RMS and EMT templates.
            # Refresh both the database view and every live editor catalogue.
            self.dynamic_editor_workspace_session.refresh_dynamic_library_templates(
                circuit=self.circuit,
            )
            self.view_objects_data()
        else:
            pass

    def check_extension(self, path: str) -> bool:
        """
        Check whether a path has an accepted extension.

        :param path: File path received from the GUI or drag-and-drop event.
        :return: ``True`` when the path extension is accepted.
        """
        normalized_path: str = path.casefold()
        for ext in self.accepted_extensions:
            if normalized_path.endswith(ext.casefold()):
                return True

        return False

    def refresh_catalogue_dependent_views(self) -> None:
        """
        Rebuild GUI views that depend on the loaded catalogue.

        :return: None.
        """
        self.setup_objects_tree()
        self.view_objects_data()
        self.update_from_to_list_views()
        self.update_date_dependent_combos()

    def dragEnterEvent(self, event: QtGui.QDragEnterEvent) -> None:
        """
        Accept drag events only when they contain file URLs.

        :param event: Incoming Qt drag-enter event.
        :return: None.
        """
        if event.mimeData().hasUrls:
            event.accept()
        else:
            event.ignore()

    def dragMoveEvent(self, event: QtGui.QDragMoveEvent) -> None:
        """
        Keep accepting drag-move events while the payload is a file list.

        :param event: Incoming Qt drag-move event.
        :return: None.
        """
        if event.mimeData().hasUrls:
            event.accept()
        else:
            event.ignore()

    def dropEvent(self, event: QtGui.QDropEvent) -> None:
        """
        Process files dropped on the main window.

        The handler filters unsupported extensions first, then decides whether
        the dropped payload should replace the current circuit, merge into it,
        or be treated as a plugin/license side action.

        :param event: Qt drop event containing the dragged file URLs.
        :return: None.
        """
        if event.mimeData().hasUrls:
            events = event.mimeData().urls()
            if len(events) > 0:

                file_names = list()

                any_grid_delta = False
                any_normal_grid = False

                for event in events:
                    file_name = event.toLocalFile()
                    # name, file_extension = os.path.splitext(file_name)
                    file_extension = ''.join(pathlib.Path(file_name).suffixes)
                    if self.check_extension(file_name):
                        file_names.append(file_name)

                        if file_name.endswith('.dgridcal') or file_name.endswith('.dveragrid'):
                            any_grid_delta = True
                        elif file_name.endswith('.vgplugin'):
                            self.install_plugin_now(file_name)
                            return
                        elif file_name.endswith('.license.gslv'):
                            ok, msg = install_gslv_license(file_name)
                            if ok:
                                self.show_info_toast(msg)
                            else:
                                self.show_error_toast(msg)
                            return
                        elif file_name.endswith(".xiidm.bz2"):
                            any_grid_delta = False
                            any_normal_grid = True
                        else:
                            any_normal_grid = True

                    else:
                        self.show_error_toast(
                            self.tr('The file type {file_extension} is not accepted :(').format(
                                file_extension=file_extension.lower()
                            )
                        )

                if self.circuit.valid_for_simulation() > 0:

                    if any_grid_delta and not any_normal_grid:
                        # only grid deltas...
                        self.open_file_now(filenames=file_names,
                                           post_function=self.post_import_circuit)
                    else:
                        quit_msg = self.tr("Are you sure that you want to quit the current grid and open a new one?"
                                           "\n If the process is cancelled the grid will remain.")
                        reply: bool = yes_no_question(text=quit_msg, title=self.tr('Message'), parent=self)

                        if reply:
                            self.open_file_now(filenames=file_names)
                else:
                    # Just open the file
                    self.open_file_now(filenames=file_names)

    def new_project_now(self, create_default_diagrams: bool = True) -> bool:
        """
        Reset the current GUI state and create one empty project immediately.

        :param create_default_diagrams: Whether to create the default schematic
            and map diagrams for the new empty circuit.
        :return: ``True`` when the project was replaced; ``False`` when an open
            dynamic editor cancelled the replacement.
        """
        # Dynamic editors retain direct references to their circuit, devices,
        # symbolic blocks and working copies. Close the complete detachable
        # workspace family before invalidating those project-owned objects.
        dynamic_editors_closed: bool = self.dynamic_editor_workspace_session.close_all_for_project_replacement(
            parent=self,
        )
        if dynamic_editors_closed:
            pass
        else:
            return False

        if self.stop_all_threads():
            pass
        else:
            self.show_warning_toast(self.tr("Some operations are still stopping. Try again after they finish."))
            return False

        # clear the circuit model
        self.circuit = MultiCircuit()

        # clear the file name
        self.file_name = ''

        self.remove_all_diagrams()

        self.setup_objects_tree()

        # clear the results
        self.ui.resultsTableView.setModel(None)
        self.ui.resultsLogsTreeView.setModel(None)

        # clear the comments
        self.ui.comments_textEdit.setText("")

        self.ui.grid_name_line_edit.setText("")

        analysis_dialogue: QtWidgets.QMainWindow | QtWidgets.QDialog | None = self.window_manager.get("analysis_dialogue")
        if is_dialog_available(dialog=analysis_dialogue):
            analysis_dialogue.close()

        self.clear_stuff_running()
        self.clear_results()

        if create_default_diagrams:
            self.add_complete_bus_branch_diagram()
            self.add_map_diagram()
            self.set_diagram_widget(self.diagram_widgets_list[0])

        return True

    def new_project(self) -> None:
        """
        Prompt the user before replacing the current project with an empty one.

        :return: None.
        """
        if self.circuit.valid_for_simulation() > 0:
            quit_msg = self.tr("Are you sure that you want to quit the current grid and create a new one?")
            reply: bool = yes_no_question(text=quit_msg, title=self.tr('Message'), parent=self)

            if reply:
                self.new_project_now(create_default_diagrams=True)

    def open_file(self) -> None:
        """
        Prompt for one grid file and start the threaded open workflow.

        :return: None.
        """
        if self.server_driver.is_running():
            self.open_server_file_dialogue()
        elif ('file_save' not in self.stuff_running_now) and ('file_open' not in self.stuff_running_now):
            self.clear_remote_database_context()
            if self.circuit.valid_for_simulation() > 0:
                quit_msg = self.tr("Are you sure that you want to quit the current grid and open a new one?"
                                   "\n If the process is cancelled the grid will remain.")
                reply: bool = yes_no_question(text=quit_msg, title=self.tr('Message'), parent=self)

                if reply:
                    self.open_file_threaded()
                else:
                    pass
            else:
                # Just open the file
                self.open_file_threaded()

        else:
            warning_msg(self.tr('There is a file being processed now.'))

    def open_server_file_dialogue(self) -> None:
        """
        Open the server-side file browser dialogue.

        :return: None.
        """
        server_file_dialogue: ServerFileDialogue = ServerFileDialogue(parent=self, app=self)
        exec_dialog_safely(dialog=server_file_dialogue)

    def clear_remote_database_context(self) -> None:
        """
        Forget the current remote database selection context.

        :return: None.
        """
        self.remote_database_file_idtag = ""
        self.remote_database_model_idtag = ""
        self.remote_database_file_name = ""
        self.remote_database_baseline_multiverse = None
        self._pending_remote_database_context = None

    @staticmethod
    def _load_multiverse_from_path(file_name: str) -> MultiVerse:
        """
        Load one VeraGrid archive synchronously and require a multiverse payload.

        :param file_name: VeraGrid archive path.
        :return: Parsed multiverse instance.
        """
        file_handler = FileOpen(file_name=file_name)
        file_handler.open()

        if file_handler.multiverse is None:
            raise ValueError("Remote database file did not contain a multiverse payload")

        return file_handler.multiverse

    @staticmethod
    def _iter_multiverse_nodes(node: ScenarioNode) -> list[ScenarioNode]:
        """
        Flatten one scenario subtree into a node list.

        :param node: Root node to walk.
        :return: Depth-first list of nodes.
        """
        data = [node]

        child: ScenarioNode
        for child in node.children:
            data.extend(IoMain._iter_multiverse_nodes(child))

        return data

    @staticmethod
    def _find_multiverse_node_by_model_idtag(multiverse: MultiVerse, model_idtag: str) -> ScenarioNode | None:
        """
        Find one multiverse node by its model idtag.

        :param multiverse: MultiVerse to search.
        :param model_idtag: Model identifier.
        :return: Matching scenario node or ``None``.
        """
        if len(model_idtag.strip()) == 0:
            return multiverse.current_node

        root_node: ScenarioNode
        for root_node in multiverse.root_nodes:
            node: ScenarioNode
            for node in IoMain._iter_multiverse_nodes(root_node):
                if node.circuit.idtag == model_idtag:
                    return node
                else:
                    pass

        return None

    @staticmethod
    def _are_circuits_equal(circuit_a: MultiCircuit, circuit_b: MultiCircuit) -> bool:
        """
        Compare two circuits for semantic equality.

        :param circuit_a: First circuit.
        :param circuit_b: Second circuit.
        :return: ``True`` when they match.
        """
        equal, _logger = circuit_a.compare_circuits(grid2=circuit_b)
        return equal

    def _download_remote_multiverse(self, file_idtag: str) -> MultiVerse:
        """
        Download one full remote database file and parse it as a multiverse.

        :param file_idtag: Remote file identifier.
        :return: Parsed multiverse snapshot.
        """
        with tempfile.NamedTemporaryFile(delete=False, suffix=".veragrid") as tmp_file:
            temp_path: str = tmp_file.name

        try:
            self.server_driver.download_database_file(
                file_idtag=file_idtag,
                target_path=temp_path,
                model_idtag="",
                base_only=False,
            )
            return self._load_multiverse_from_path(file_name=temp_path)
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
            else:
                pass

    def _store_remote_model_into_multiverse(self,
                                            multiverse: MultiVerse,
                                            model_idtag: str,
                                            circuit: MultiCircuit) -> None:
        """
        Replace one model inside a remote multiverse snapshot.

        :param multiverse: Target multiverse.
        :param model_idtag: Model identifier to replace.
        :param circuit: New full composed circuit for that model.
        :return: None.
        """
        node = self._find_multiverse_node_by_model_idtag(multiverse=multiverse, model_idtag=model_idtag)

        if node is None:
            raise ValueError(f"Remote model '{model_idtag}' was not found in the selected file")

        multiverse._store_composed_node_data(node=node, composed=circuit.copy())
        multiverse._set_active_node(node)

    def load_remote_database_entry(self,
                                   file_idtag: str,
                                   file_name: str,
                                   model_idtag: str = "",
                                   base_only: bool = False) -> None:
        """
        Download one remote database entry and route it through the normal open workflow.

        :param file_idtag: Remote file identifier.
        :param file_name: Remote file name.
        :param model_idtag: Optional remote model identifier.
        :param base_only: Download only the base model when ``True``.
        :return: None.
        """
        with tempfile.NamedTemporaryFile(delete=False, suffix=".veragrid") as tmp_file:
            temp_path: str = tmp_file.name

        baseline_multiverse: MultiVerse | None = None

        if len(model_idtag.strip()) == 0 and not base_only:
            baseline_temp_path = temp_path
        else:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".veragrid") as baseline_tmp_file:
                baseline_temp_path = baseline_tmp_file.name

        self.server_driver.download_database_file(
            file_idtag=file_idtag,
            target_path=temp_path,
            model_idtag=model_idtag,
            base_only=base_only,
        )

        if baseline_temp_path != temp_path:
            self.server_driver.download_database_file(
                file_idtag=file_idtag,
                target_path=baseline_temp_path,
                model_idtag="",
                base_only=False,
            )
        else:
            pass

        try:
            baseline_multiverse = self._load_multiverse_from_path(file_name=baseline_temp_path)
        finally:
            if baseline_temp_path != temp_path and os.path.exists(baseline_temp_path):
                os.unlink(baseline_temp_path)
            else:
                pass

        self._temporary_remote_download_paths.append(temp_path)
        self._pending_remote_database_context = {
            "file_idtag": file_idtag,
            "file_name": file_name,
            "model_idtag": model_idtag,
            "base_only": base_only,
            "baseline_multiverse": baseline_multiverse,
        }
        self.open_file_now(filenames=temp_path)

    def save_remote_database_entry(self, file_idtag: str, file_name: str, model_idtag: str = "") -> None:
        """
        Save the current project back into one remote database file or model.

        :param file_idtag: Remote file identifier.
        :param file_name: Remote file name.
        :param model_idtag: Optional remote model identifier.
        :return: None.
        """
        with tempfile.NamedTemporaryFile(delete=False, suffix=".veragrid") as tmp_file:
            temp_path: str = tmp_file.name

        try:
            self.circuit.comments = self.ui.comments_textEdit.toPlainText()
            options = self.get_file_save_options()

            if len(model_idtag.strip()) == 0:
                saver = filedrv.FileSave(
                    circuit=self.circuit,
                    multiverse=self.multiverse,
                    file_name=temp_path,
                    options=options,
                )
                saver.save()
            else:
                if self.remote_database_baseline_multiverse is None:
                    raise ValueError("No remote baseline is loaded for model-level save")

                baseline_node = self._find_multiverse_node_by_model_idtag(
                    multiverse=self.remote_database_baseline_multiverse,
                    model_idtag=model_idtag,
                )
                if baseline_node is None:
                    raise ValueError(f"Loaded baseline model '{model_idtag}' was not found")

                latest_remote_multiverse = self._download_remote_multiverse(file_idtag=file_idtag)
                latest_remote_node = self._find_multiverse_node_by_model_idtag(
                    multiverse=latest_remote_multiverse,
                    model_idtag=model_idtag,
                )
                if latest_remote_node is None:
                    raise ValueError(f"Current remote model '{model_idtag}' was not found")

                baseline_circuit = self.remote_database_baseline_multiverse.checkout(baseline_node)
                latest_remote_circuit = latest_remote_multiverse.checkout(latest_remote_node)
                merged_circuit = self.circuit.copy()

                if not self._are_circuits_equal(circuit_a=baseline_circuit, circuit_b=latest_remote_circuit):
                    merge_dialogue = GridMergeDialogue(
                        parent=self,
                        grid=latest_remote_circuit.copy(),
                        diff=merged_circuit,
                    )
                    exec_dialog_safely(dialog=merge_dialogue)

                    if not merge_dialogue.merged_grid:
                        self.show_info_toast(self.tr("Server save cancelled."))
                        return

                    merged_circuit = merge_dialogue.grid

                self._store_remote_model_into_multiverse(
                    multiverse=latest_remote_multiverse,
                    model_idtag=model_idtag,
                    circuit=merged_circuit,
                )
                latest_remote_multiverse.commit_current()

                saver = filedrv.FileSave(
                    circuit=latest_remote_multiverse.current_model,
                    multiverse=latest_remote_multiverse,
                    file_name=temp_path,
                    options=options,
                )
                saver.save()
                self.remote_database_baseline_multiverse = latest_remote_multiverse

            self.server_driver.replace_database_file(
                file_idtag=file_idtag,
                source_path=temp_path,
                upload_file_name=file_name,
            )
            self.remote_database_file_idtag = file_idtag
            self.remote_database_file_name = file_name
            self.remote_database_model_idtag = model_idtag
            self.show_info_toast(self.tr("Server file saved."))
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
            else:
                pass

    def delete_remote_database_file(self, file_idtag: str) -> None:
        """
        Delete one remote database file and clear the local remote context if needed.

        :param file_idtag: Remote file identifier.
        :return: None.
        """
        self.server_driver.delete_database_file(file_idtag=file_idtag)

        if self.remote_database_file_idtag == file_idtag:
            self.clear_remote_database_context()
        else:
            pass

        self.show_info_toast(self.tr("Server file deleted."))

    def delete_remote_database_model(self, file_idtag: str, model_idtag: str) -> None:
        """
        Delete one remote model and clear the local remote context if needed.

        :param file_idtag: Remote file identifier.
        :param model_idtag: Remote model identifier.
        :return: None.
        """
        self.server_driver.delete_database_model(file_idtag=file_idtag, model_idtag=model_idtag)

        if self.remote_database_file_idtag == file_idtag and self.remote_database_model_idtag == model_idtag:
            self.remote_database_model_idtag = ""
        else:
            pass

        self.show_info_toast(self.tr("Server model deleted."))

    def cleanup_temporary_remote_downloads(self) -> None:
        """
        Remove every temporary file downloaded from the remote database API.

        :return: None.
        """
        temp_path: str
        for temp_path in self._temporary_remote_download_paths:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
            else:
                pass

        self._temporary_remote_download_paths = list()

    def open_file_threaded(self,
                           post_function: Callable[[], None] | None = None,
                           allow_diff_file_format: bool = False,
                           title: str = 'Open file') -> None:
        """
        Ask the user for one file selection and open it in a worker thread.

        :param post_function: Optional callback executed when the open thread
            finishes successfully.
        :param allow_diff_file_format: Allow loading VeraGrid diff files?
        :param title: Caption shown by the file selection dialogue.
        :return: None.
        """

        files_types = "*.gridcal *.veragrid "

        if allow_diff_file_format:
            files_types += "*.dgridcal *.dveragrid "

        files_types += "*.gch5 *.xlsx *.xls *.sqlite *.dgs *.iidm *.xiidm"
        files_types += "*.m *.matpower *.raw *.RAW *.rawx *.uct *.json *.ejson2 *.ejson3 *.xml "
        files_types += "*.zip *.dpx *.pwf *.epc *.EPC *.ech *.dta *.nc *.hdf5 *.p"

        dialogue = QtWidgets.QFileDialog(None,
                                         caption=self.tr(title),
                                         directory=self.project_directory,
                                         filter=self.tr("Formats ({files_types})").format(files_types=files_types))
        dialogue.setFileMode(QtWidgets.QFileDialog.FileMode.ExistingFiles)

        if exec_dialog_safely(dialog=dialogue):
            filenames = dialogue.selectedFiles()
            self.open_file_now(filenames, post_function)

    def open_file_now(self, filenames: Union[str, List[str]],
                      post_function: Union[None, Callable[[], None]] = None,
                      bool_prompt_to_ask_if_unclear: bool = True) -> None:
        """
        Start loading one or more files without prompting for confirmation first.

        :param filenames: File path or list of file paths. Multiple entries are
            allowed for multi-file formats such as CIM TP/EQ packages.
        :param post_function: Optional callback executed once the open thread
            finishes.
        :param bool_prompt_to_ask_if_unclear: When ``True``, ambiguous file
            extensions such as ``.xml`` or ``.zip`` open one selector dialogue.
        :return: None.
        """
        normalized_filenames: List[str]
        if isinstance(filenames, str):
            normalized_filenames = [filenames]
        else:
            normalized_filenames = filenames

        if len(normalized_filenames) > 0:

            for f_name in normalized_filenames:
                if not os.path.exists(f_name):
                    error_msg(text=self.tr("The file does not exist :( \n {file_name}").format(file_name=f_name),
                              title=self.tr("File opening"))
                    return

            selected_file_name: str = normalized_filenames[0]

            # Store the selected directory immediately, but keep the current
            # project's filename until the loaded circuit is accepted. This
            # preserves the old project identity if a dynamic editor cancels
            # the replacement after parsing has completed.
            self.project_directory = os.path.dirname(selected_file_name)

            # lock the ui
            self.LOCK()

            options = filedrv.FileOpenOptions()

            file_name = normalized_filenames if len(normalized_filenames) > 1 else normalized_filenames[0]

            # try to determine the file type
            options.file_type = determine_file_type(file_name)

            if options.file_type is None and bool_prompt_to_ask_if_unclear:
                file_selector: FileTypeSelector = FileTypeSelector(file_name=file_name)
                try:
                    exec_dialog_safely(dialog=file_selector)
                    options.file_type = file_selector.file_type
                finally:
                    delete_dialog_safely(dialog=file_selector)

                if options.file_type == FileType.CGMES:
                    cgmes_import_dialogue: CgmesImportDialogue = CgmesImportDialogue(app=self, options=options)
                    exec_dialog_safely(dialog=cgmes_import_dialogue)
                else:
                    pass

            elif options.file_type == FileType.PSSE_raw or options.file_type == FileType.PSSE_rawx:
                psse_import_dialogue: PsseImportDialogue = PsseImportDialogue(app=self, options=options)
                exec_dialog_safely(dialog=psse_import_dialogue)
                # NOTE: options will be modified inside
            elif options.file_type == FileType.CGMES:
                cgmes_import_dialogue = CgmesImportDialogue(app=self, options=options)
                exec_dialog_safely(dialog=cgmes_import_dialogue)
            elif options.file_type == FileType.DGS:
                dgs_import_dialogue: DgsImportDialogue = DgsImportDialogue(options=options)
                exec_dialog_safely(dialog=dgs_import_dialogue)
            else:
                pass

            # create thread
            self.open_file_thread_object = filedrv.FileOpenThread(
                file_name=file_name,
                previous_circuit=self.circuit,
                options=options
            )
            self.open_file_thread_object.setParent(self)

            # make connections
            self.open_file_thread_object.progress_signal.connect(self.ui.progressBar.setValue)
            self.open_file_thread_object.progress_text.connect(self.ui.progress_label.setText)
            self.open_file_thread_object.finished.connect(self.UNLOCK)

            if post_function is None:
                self.open_file_thread_object.finished.connect(self.post_open_file)
            else:
                self.open_file_thread_object.finished.connect(post_function)

            # thread start
            self.open_file_thread_object.start()

            # register as the latest file driver
            self.last_file_driver = self.open_file_thread_object

            # register thread
            self.stuff_running_now.append(SimulationTypes.FileOpen)

    def post_open_file(self) -> None:
        """
        Finalize the GUI state after a file-open worker completes.

        The method installs the loaded circuit or multiverse, rebuilds diagrams,
        refreshes date-dependent widgets, applies any persisted GUI config and
        shows import logs when they are present.

        :return: None.
        """

        self.stuff_running_now.remove(SimulationTypes.FileOpen)

        if self.open_file_thread_object is not None:

            if self.open_file_thread_object.valid:

                # A successfully parsed file must not coexist with editors that
                # retain devices from the previous circuit. If the user keeps
                # unapplied editor changes, leave the old project untouched.
                project_replacement_accepted: bool = self.new_project_now(create_default_diagrams=False)
                if project_replacement_accepted:
                    pass
                else:
                    self.show_info_toast(
                        self.tr(
                            "The file was loaded but the current project was kept "
                            "because closing a dynamic editor was cancelled."
                        )
                    )
                    return

                if self.open_file_thread_object.multiverse is not None:
                    # A multiverse file already contains the complete scenario tree and active
                    # scenario. Reassigning through self.circuit would rebuild a fresh
                    # single-root MultiVerse and discard the loaded multiverse information.
                    self.multiverse = self.open_file_thread_object.multiverse
                    if self.circuit is not None:
                        self.ui.activeScenarioLabel.setText(self.tr("Current: {circuit_name}").format(
                            circuit_name=self.circuit.name
                        ))
                    self.file_name = self.open_file_thread_object.file_name

                elif self.open_file_thread_object.circuit is not None:
                    self.circuit = self.open_file_thread_object.circuit
                    self.file_name = self.open_file_thread_object.file_name

                if self.circuit is None:
                    self.show_error_toast(self.tr("No grid to load :("))
                    return

                if self.circuit.has_diagrams():
                    # create the diagrams that came with the file
                    if self.open_file_thread_object.multiverse is not None:
                        self.reload_diagrams_for_active_scenario()
                    else:
                        self.create_circuit_stored_diagrams()

                else:
                    if self.circuit.get_bus_number() > 300:
                        self.show_info_toast(self.tr("The grid is quite big, no diagram is automatically created"),
                                             duration=5000)

                    else:
                        # create schematic
                        self.add_complete_bus_branch_diagram()

                # set base magnitudes
                self.ui.sbase_doubleSpinBox.setValue(self.circuit.Sbase)
                self.ui.fbase_doubleSpinBox.setValue(self.circuit.fBase)

                # set circuit comments
                try:
                    self.ui.comments_textEdit.setText(str(self.circuit.comments))
                except ValueError:
                    pass

                # update the drop-down menus that display dates
                self.update_date_dependent_combos()
                self.update_from_to_list_views()

                # get the session tree structure
                session_data_dict = self.open_file_thread_object.get_session_tree()
                mdl = gf.get_tree_model(
                    session_data_dict,
                    self.tr('Sessions'),
                    icons=get_session_tree_icon_map(session_data_dict=session_data_dict)
                )
                self.ui.diskSessionsTreeView.setModel(mdl)

                # apply the GUI settings if found:
                gui_config_data = self.open_file_thread_object.json_files.get('gui_config', None)
                if gui_config_data is not None:
                    self.apply_gui_config(data=gui_config_data)

                # clear the results
                self.clear_results()
                self.dynamic_results_handlers = dict()
                self.clear_dynamic_results_view()

                self.ui.grid_name_line_edit.setText(self.circuit.name)

                # if this was a CGMES file, launch the Rosetta GUI
                if self.open_file_thread_object.options.file_type == FileType.CGMES:

                    show_rosetta = yes_no_question(title=self.tr("Show Rosetta"),
                                                   text=self.tr("Do you want to open the Rosetta CGMES browser?"))

                    if show_rosetta:
                        rosetta_window: QtWidgets.QWidget | None = self.window_manager.get("rosseta")
                        if isinstance(rosetta_window, RosetaExplorerGUI) and is_dialog_available(dialog=rosetta_window):
                            rosetta_gui: RosetaExplorerGUI = rosetta_window
                        else:
                            rosetta_gui = RosetaExplorerGUI()
                        rosetta_gui.set_grid_model(self.open_file_thread_object.cgmes_circuit)
                        rosetta_gui.set_logger(self.open_file_thread_object.cgmes_logger)
                        rosetta_gui.update_combo_boxes()
                        self.show_dialogue(win=rosetta_gui, key="rosseta")
                    else:
                        # else, show the logger if it is necessary
                        if open_logger_requires_dialog(self.open_file_thread_object.logger):
                            dlg = LogsDialogue(self.tr('Open CGMES file logger'), self.open_file_thread_object.logger)
                            exec_dialog_safely(dialog=dlg)
                        else:
                            pass

                else:
                    # else, show the logger if it is necessary
                    if open_logger_requires_dialog(self.open_file_thread_object.logger):
                        dlg = LogsDialogue(self.tr('Open file logger'), self.open_file_thread_object.logger)
                        exec_dialog_safely(dialog=dlg)
                    else:
                        pass

                if self._pending_remote_database_context is not None:
                    self.remote_database_file_idtag = str(self._pending_remote_database_context["file_idtag"])
                    self.remote_database_file_name = str(self._pending_remote_database_context["file_name"])
                    self.remote_database_model_idtag = str(self._pending_remote_database_context["model_idtag"])
                    baseline_multiverse = self._pending_remote_database_context.get("baseline_multiverse", None)
                    if isinstance(baseline_multiverse, MultiVerse):
                        self.remote_database_baseline_multiverse = baseline_multiverse
                    else:
                        self.remote_database_baseline_multiverse = None
                else:
                    pass

            else:
                warning_msg(text=self.tr('Error while loading the file(s)'))
                # else, show the logger if it is necessary
                if len(self.open_file_thread_object.logger) > 0:
                    dlg = LogsDialogue(self.tr('Open file logger'), self.open_file_thread_object.logger)
                    exec_dialog_safely(dialog=dlg)
        else:
            # center nodes
            diagram = self.get_selected_diagram_widget()
            if diagram is not None:
                if isinstance(diagram, SchematicWidget):
                    diagram.center_nodes()

        self._pending_remote_database_context = None
        self.cleanup_temporary_remote_downloads()
        self.setup_time_sliders()
        self.get_circuit_snapshot_datetime()
        self.change_theme_mode()

    def install_plugin_now(self, file_name: str) -> None:
        """
        Install one VeraGrid plugin package immediately.

        :param file_name: Plugin archive path.
        :return: None.
        """
        if file_name.endswith('.vgplugin'):
            info = get_plugin_info(file_name)

            if info is not None:

                if not info.is_compatible():
                    error_msg(self.tr("{name} {version} requires VeraGrid {veragrid_version}").format(
                        name=info.name,
                        version=info.version,
                        veragrid_version=info.veragrid_version,
                    ), self.tr("Plugin install"))
                    return

                # search for the plugin
                for key, plugin in self.plugins_info.plugins.items():
                    if plugin.name == info.name:

                        ok = yes_no_question(self.tr("There is already a plugin: "
                                                     "{plugin_name} {plugin_version}. "
                                                     "The new plugin is {new_version}. "
                                                     "Install?").format(
                            plugin_name=plugin.name,
                            plugin_version=plugin.version,
                            new_version=info.version,
                        ), self.tr("Plugin install"))
                        if not ok:
                            return
                        else:
                            break

                install_plugin(file_name)
                self.add_plugins()
                info_msg(self.tr("{name} {version} installed!").format(name=info.name, version=info.version),
                         self.tr("Plugin install"))
            else:
                error_msg(self.tr("There is no manifest :("), self.tr("Plugin install"))
        else:
            error_msg(self.tr("Does not seem to be a plugin :/"), self.tr("Plugin install"))

    def select_csv_file(self, caption: str = 'Open CSV file') -> str | None:
        """
        Prompt for one CSV file path.

        :param caption: Dialogue caption.
        :return: Selected CSV file path or ``None``.
        """
        files_types = self.tr("CSV (*.csv)")

        filename, type_selected = QtWidgets.QFileDialog.getOpenFileName(parent=self,
                                                                        caption=self.tr(caption),
                                                                        dir=self.project_directory,
                                                                        filter=files_types)

        if len(filename) > 0:
            return filename
        else:
            return None

    def import_circuit(self) -> None:
        """
        Prompt for another circuit file and route the result to the merge flow.

        :return: None.
        """
        self.open_file_threaded(post_function=self.post_import_circuit,
                                allow_diff_file_format=True)

    def post_import_circuit(self) -> None:
        """
        Merge or append one newly opened circuit into the current project.

        :return: None.
        """
        self.stuff_running_now.remove(SimulationTypes.FileOpen)

        if self.open_file_thread_object is not None:

            new_circuit = self.open_file_thread_object.circuit

            if open_logger_requires_dialog(self.open_file_thread_object.logger):
                dlg = LogsDialogue(self.tr('Open file logger'),
                                   self.open_file_thread_object.logger)
                exec_dialog_safely(dialog=dlg)
            else:
                pass

            if self.open_file_thread_object.valid:

                merge_dlg = GridMergeDialogue(grid=self.circuit, diff=new_circuit)
                exec_dialog_safely(dialog=merge_dlg)

                if merge_dlg.added_grid:
                    # Create a blank diagram and add to it
                    # logger = self.circuit.add_circuit(new_circuit)

                    # for sure, we want to add to the current schematic
                    diagram_widget = self.get_selected_diagram_widget()

                elif merge_dlg.merged_grid:

                    dlg3 = CustomQuestionDialogue(title=self.tr("Grid merge"),
                                                  question=self.tr("How do you want to represent the merged grid?"),
                                                  answer1=self.tr("Create new diagram"),
                                                  answer2=self.tr("Add to current diagram"))
                    exec_dialog_safely(dialog=dlg3)

                    if dlg3.accepted_answer == 1:
                        # Create a blank diagram and add to it
                        diagram_widget = self.create_blank_schematic_diagram(name=new_circuit.name)

                    elif dlg3.accepted_answer == 2:
                        diagram_widget = self.get_selected_diagram_widget()

                    else:
                        # not imported
                        return

                    if diagram_widget is not None:
                        if isinstance(diagram_widget, SchematicWidget):
                            injections_by_bus = new_circuit.get_injection_devices_grouped_by_bus()
                            injections_by_fluid_node = new_circuit.get_injection_devices_grouped_by_fluid_node()

                            diagram_widget.add_elements_to_schematic(buses=new_circuit.buses,
                                                                     lines=new_circuit.lines,
                                                                     dc_lines=new_circuit.dc_lines,
                                                                     transformers2w=new_circuit.transformers2w,
                                                                     transformers3w=new_circuit.transformers3w,
                                                                     transformers_nw=new_circuit.transformers_nw,
                                                                     hvdc_lines=new_circuit.hvdc_lines,
                                                                     vsc_devices=new_circuit.vsc_devices,
                                                                     upfc_devices=new_circuit.upfc_devices,
                                                                     switches=new_circuit.switch_devices,
                                                                     fluid_nodes=new_circuit.fluid_nodes,
                                                                     fluid_paths=new_circuit.fluid_paths,
                                                                     injections_by_bus=injections_by_bus,
                                                                     injections_by_fluid_node=injections_by_fluid_node,
                                                                     explode_factor=1.0,
                                                                     prog_func=None,
                                                                     text_func=None)
                            diagram_widget.set_selected_buses(buses=new_circuit.buses)
                        else:
                            info_msg(self.tr("No schematic diagram was selected..."),
                                     title=self.tr("Add to current diagram"))

                else:
                    return

    def export_circuit_differential(self) -> None:
        """
        Open the circuit-differential export dialogue.

        :return: None.
        """
        dlg = GridDiffDialogue(grid=self.circuit)
        exec_dialog_safely(dialog=dlg)

    def save_file_as(self) -> None:
        """
        Force one new target path and then delegate to the normal save flow.

        :return: None.
        """
        # by deleting the file_name, the save_file function will ask for it
        self.file_name = ''
        self.save_file()

    @staticmethod
    def is_direct_veragrid_save_path(file_name: str) -> bool:
        """
        Check whether the current file path is safe for direct VeraGrid overwrite.

        :param file_name: Current GUI file path.
        :return: ``True`` only for native VeraGrid archive files.
        """
        file_extension: str = pathlib.Path(file_name).suffix.lower()
        return file_extension in (".veragrid", ".gridcal")

    def save_file(self) -> None:
        """
        Save the current project to disk using the active file target.

        :return: None.
        """

        if self.server_driver.is_running():
            self.open_server_file_dialogue()
        else:
            # declare the allowed file types
            files_types = self.tr("VeraGrid zip (*.veragrid)")

            # call dialog to select the file
            if self.project_directory is None:
                self.project_directory = ''

            # gather comments
            self.circuit.comments = self.ui.comments_textEdit.toPlainText()

            if self.file_name == '' or not self.is_direct_veragrid_save_path(file_name=self.file_name):
                # if the global file_name is empty, ask where to save
                fname = os.path.join(self.project_directory, self.ui.grid_name_line_edit.text())

                filename, type_selected = QtWidgets.QFileDialog.getSaveFileName(self,
                                                                                self.tr('Save file'),
                                                                                fname,
                                                                                files_types)

                if filename != '':

                    # if the user did not enter the extension, add it automatically
                    name, file_extension = os.path.splitext(filename)

                    if file_extension == '':
                        filename = name + ".veragrid"

                    # we were able to compose the file correctly, now save it
                    self.file_name = filename
                    options = self.get_file_save_options()
                    options.file_type = FileType.VeraGrid
                    self.save_file_now(
                        filename=self.file_name,
                        type_selected=type_selected,
                        options=options,
                    )
            else:
                # save directly
                self.save_file_now(filename=self.file_name)

    def get_file_save_options(self) -> filedrv.FileSavingOptions:
        """
        Build the file-save options from the current GUI state.

        :return: File-save options snapshot.
        """

        # get save data
        sessions_data = self.session.get_save_data() if self.ui.saveResultsCheckBox.isChecked() else list()

        # get json files to store
        json_files = {"gui_config": self.get_gui_config_data()}

        options = filedrv.FileSavingOptions(
            sessions_data=sessions_data,
            dictionary_of_json_files=json_files,
        )

        return options

    def save_file_now(self, filename: str,
                      type_selected: str = "",
                      grid: Union[MultiCircuit, None] = None,
                      options: filedrv.FileSavingOptions | None = None) -> None:
        """
        Launch the threaded save workflow without showing another prompt.

        :param filename: Output file path.
        :param type_selected: Human-readable file-type label selected in the
            save dialogue, for example ``VeraGrid zip (*.veragrid)``.
        :param grid: Optional circuit override. When ``None``, ``self.circuit``
            is saved.
        :param options: Optional file-save options override.
        :return: None.
        """

        if ((SimulationTypes.FileSave not in self.stuff_running_now) and
                (SimulationTypes.FileOpen not in self.stuff_running_now)):
            # lock the ui
            self.LOCK()

            # A blocking save cannot be cancelled by QThread.quit(); refusing a
            # second save keeps two serializers away from the same circuit.
            if self.save_file_thread_object is not None:
                if self.save_file_thread_object.isRunning():
                    warning_msg(self.tr("The current save is still finishing. Please retry when it is done."))
                    self.UNLOCK()
                    return

            options2 = self.get_file_save_options() if options is None else options
            options2.type_selected = type_selected

            self.save_file_thread_object = filedrv.FileSaveThread(
                circuit=self.circuit if grid is None else grid,
                multiverse=self.multiverse,
                file_name=filename,
                options=options2
            )
            self.save_file_thread_object.setParent(self)

            # make connections
            self.save_file_thread_object.progress_signal.connect(self.ui.progressBar.setValue)
            self.save_file_thread_object.progress_text.connect(self.ui.progress_label.setText)
            self.save_file_thread_object.finished.connect(self.UNLOCK)
            self.save_file_thread_object.finished.connect(self.post_file_save)

            # thread start
            self.save_file_thread_object.start()

            # register as the latest file driver
            self.last_file_driver = self.save_file_thread_object

            self.stuff_running_now.append(SimulationTypes.FileSave)

        else:
            warning_msg(self.tr('There is a file being processed..'))

    def post_file_save(self) -> None:
        """
        Finalize the GUI state after one threaded save completes.

        :return: None.
        """
        if self.save_file_thread_object.logger is not None:
            if len(self.save_file_thread_object.logger) > 0:
                dlg: LogsDialogue = LogsDialogue(self.tr('Save file logger'), self.save_file_thread_object.logger)
                exec_dialog_safely(dialog=dlg)
            else:
                pass
        else:
            pass

        self.stuff_running_now.remove(SimulationTypes.FileSave)

        self.ui.model_version_label.setText(self.tr('Model v. {model_version}').format(
            model_version=self.circuit.model_version
        ))
        self.ui.grid_idtag_label.setText(self.tr('idtag. {idtag}').format(idtag=self.circuit.idtag))

        # get the session tree structure
        session_data_dict = self.save_file_thread_object.get_session_tree()
        mdl = gf.get_tree_model(
            session_data_dict,
            self.tr('Sessions'),
            icons=get_session_tree_icon_map(session_data_dict=session_data_dict)
        )
        self.ui.diskSessionsTreeView.setModel(mdl)

    def grid_generator(self) -> None:
        """
        Open the random-grid generator dialogue and optionally replace the project.

        :return: None.
        """
        grid_generator_dialogue: GridGeneratorGUI = GridGeneratorGUI(parent=self)
        grid_generator_dialogue.resize(int(1.61 * 600.0), 550)  # golden ratio
        try:
            exec_dialog_safely(dialog=grid_generator_dialogue)
            generator_applied: bool = grid_generator_dialogue.applied
            generated_circuit: MultiCircuit = grid_generator_dialogue.circuit
        finally:
            delete_dialog_safely(dialog=grid_generator_dialogue)

        if generator_applied:

            if self.circuit.valid_for_simulation() > 0:
                reply: bool = yes_no_question(
                    text=self.tr('Are you sure that you want to delete the current grid and replace it?'),
                    title=self.tr('Message'),
                    parent=self,
                )

                if not reply:
                    return

            self.circuit = generated_circuit

            # create schematic
            self.redraw_current_diagram()

            # set circuit name
            diagram = self.get_selected_diagram_widget()
            if diagram is not None:
                if isinstance(diagram, SchematicWidget):
                    diagram.name = self.tr("Random grid {bus_count} buses").format(
                        bus_count=self.circuit.get_bus_number()
                    )

            # set base magnitudes
            self.ui.sbase_doubleSpinBox.setValue(self.circuit.Sbase)
            self.ui.fbase_doubleSpinBox.setValue(self.circuit.fBase)
            self.ui.model_version_label.setText(self.tr("Model v. {model_version}").format(
                model_version=self.circuit.model_version
            ))
            self.ui.grid_idtag_label.setText(self.tr('idtag. {idtag}').format(idtag=self.circuit.idtag))

            # set circuit comments
            self.ui.comments_textEdit.setText(self.tr("Grid generated randomly using the RPGM algorithm."))

            # update the drop down menus that display dates
            self.update_date_dependent_combos()
            self.update_from_to_list_views()

            # clear the results
            self.clear_results()

    def import_bus_coordinates(self) -> None:
        """
        Open the coordinate-import dialogue and refresh the XY projection.

        :return: None.
        """
        coordinates_window: CoordinatesInputGUI = CoordinatesInputGUI(grid=self.circuit, parent=self)
        try:
            exec_dialog_safely(dialog=coordinates_window)
            coordinates_accepted: bool = coordinates_window.was_accepted
        finally:
            delete_dialog_safely(dialog=coordinates_window)

        if coordinates_accepted:
            self.set_xy_from_lat_lon()
        else:
            pass

    def export_object_profiles(self) -> None:
        """
        Export all object profiles to one Excel workbook.

        :return: None.
        """
        if self.circuit.time_profile is not None:

            # declare the allowed file types
            files_types = self.tr("Excel file (*.xlsx)")
            # call dialog to select the file
            if self.project_directory is None:
                self.project_directory = ''

            fname = os.path.join(self.project_directory, self.tr('profiles of ') + self.ui.grid_name_line_edit.text())

            filename, type_selected = QtWidgets.QFileDialog.getSaveFileName(self, self.tr('Save file'), fname,
                                                                            files_types)

            if filename != "":
                if not filename.endswith('.xlsx'):
                    filename += '.xlsx'
                # TODO: correct this function
                self.circuit.export_profiles(file_name=filename)
        else:
            warning_msg(self.tr('There are no profiles!'), self.tr('Export object profiles'))

    def export_all(self) -> None:
        """
        Export every available simulation result to one ZIP archive.

        :return: None.
        """

        available_results = self.get_available_drivers()

        if len(available_results) > 0:

            files_types = self.tr("Zip file (*.zip)")
            fname = os.path.join(self.project_directory, self.tr('Results of ') + self.ui.grid_name_line_edit.text())

            filename, type_selected = QtWidgets.QFileDialog.getSaveFileName(self, self.tr('Save file'), fname,
                                                                            files_types)

            if filename != "":
                self.LOCK()

                self.stuff_running_now.append(SimulationTypes.ExportAll)
                self.export_all_thread_object = exprtdrv.ExportAllThread(circuit=self.circuit,
                                                                         drivers_list=available_results,
                                                                         file_name=filename)
                self.export_all_thread_object.setParent(self)

                self.export_all_thread_object.progress_signal.connect(self.ui.progressBar.setValue)
                self.export_all_thread_object.progress_text.connect(self.ui.progress_label.setText)
                self.export_all_thread_object.finished.connect(self.post_export_all)
                self.export_all_thread_object.start()
        else:
            warning_msg(self.tr('There are no results available :/'))

    def post_export_all(self) -> None:
        """
        Finalize the GUI state after the export-all worker completes.

        :return: None.
        """
        self.stuff_running_now.remove(SimulationTypes.ExportAll)

        if self.export_all_thread_object is not None:
            if self.export_all_thread_object.logger.has_logs():
                self.show_logs(name=self.tr('Export all'),
                               logger=self.export_all_thread_object.logger)

        if len(self.stuff_running_now) == 0:
            self.UNLOCK()

    def export_simulation_data(self) -> None:
        """
        Export the compiled calculation data currently shown in the GUI.

        :return: None.
        """

        # declare the allowed file types
        files_types = self.tr("Excel file (*.xlsx)")

        # call dialog to select the file
        if self.project_directory is None:
            self.project_directory = ''

        fname = os.path.join(self.project_directory, self.ui.grid_name_line_edit.text())

        filename, type_selected = QtWidgets.QFileDialog.getSaveFileName(self, self.tr('Save file'), fname,
                                                                        files_types)

        if filename != "":
            if not filename.endswith('.xlsx'):
                filename += '.xlsx'

            if self.compiled_arrays is None:
                self.recompile_circuits_for_display()

            self.compiled_arrays.export_to_excel(file_name=filename)

            self.show_info_toast(self.tr("Done!"))

    def load_results_driver(self) -> None:
        """
        Load one previously saved simulation driver from disk into the session.

        :return: None.
        """
        idx = self.ui.diskSessionsTreeView.selectedIndexes()
        if len(idx) > 0:
            tree_mdl = self.ui.diskSessionsTreeView.model()
            item = tree_mdl.itemFromIndex(idx[0])
            path = gf.get_tree_item_path(item)

            if len(path) > 1:
                session_name = path[0]
                study_name = path[1]
                if self.last_file_driver is not None:
                    data_dict = self.last_file_driver.load_session_objects(session_name=session_name,
                                                                           study_name=study_name)

                    logger = self.session.register_driver_from_disk_data(grid=self.circuit,
                                                                         study_name=study_name,
                                                                         data_dict=data_dict)

                    if logger.has_logs():
                        self.show_logs(name=self.tr("Results parsing"), logger=logger, expand_all=True)

                    self.update_available_results()
                    self.show_info_toast(self.tr("Loaded '{study_name}' results from disk").format(
                        study_name=study_name
                    ))
                else:
                    error_msg(self.tr('No file driver declared :/'))
            else:
                info_msg(self.tr('Select a driver inside a session'), self.tr('Driver load from disk'))

    def show_disk_sessions_context_menu(self, pos) -> None:
        """
        Display the context menu for loading saved results from disk.

        :param pos: Local click position in the tree view.
        :return: None.
        """
        index = self.ui.diskSessionsTreeView.indexAt(pos)

        if index.isValid():
            self.ui.diskSessionsTreeView.setCurrentIndex(index)
            menu = QtWidgets.QMenu(self.ui.diskSessionsTreeView)
            gf.add_menu_entry(menu=menu,
                              text=self.tr("Load results from disk"),
                              icon_path=":/Icons/icons/loadc.png",
                              function_ptr=self.load_results_driver)
            menu.exec(self.ui.diskSessionsTreeView.viewport().mapToGlobal(pos))
        else:
            pass

    def import_contingencies(self) -> None:
        """
        Import contingencies from one JSON file.

        :return: None.
        """

        files_types = self.tr("Formats (*.json)")

        # call dialog to select the file

        filenames, type_selected = QtWidgets.QFileDialog.getOpenFileNames(parent=self,
                                                                          caption=self.tr('Open file'),
                                                                          dir=self.project_directory,
                                                                          filter=files_types)

        if len(filenames) == 1:
            contingencies = import_contingencies_from_json(filenames[0])
            logger = self.circuit.set_contingencies(contingencies=contingencies)

            if len(logger) > 0:
                dlg = LogsDialogue(self.tr('Contingencies import'), logger)
                exec_dialog_safely(dialog=dlg)

    def export_contingencies(self) -> None:
        """
        Export current contingencies to one JSON file.

        :return: None.
        """
        if len(self.circuit.contingencies) > 0:

            # declare the allowed file types
            files_types = self.tr("JSON file (*.json)")

            # call dialog to select the file
            filename, type_selected = QtWidgets.QFileDialog.getSaveFileName(self, self.tr('Save file'), '',
                                                                            files_types)

            if not (filename.endswith('.json')):
                filename += ".json"

            if filename != "":
                # save file
                export_contingencies_json_file(circuit=self.circuit, file_path=filename)

    def add_default_catalogue(self) -> None:
        """
        Add catalogue elements to the circuit (interactive selection).

        :return: None.
        """
        if isinstance(self, QtWidgets.QWidget):
            dlg = CatalogueElementsSelectionDialogue(parent=self, circuit=self.circuit)
            exec_dialog_safely(dialog=dlg)
            return None

        self.refresh_catalogue_dependent_views()
        self.show_info_toast(self.tr("Catalogue added!"))
        return None

    def load_custom_catalogue(self) -> None:
        """
        Load one custom catalogue workbook and merge it into the circuit.

        :return: None.
        """

        files_types = self.tr("Catalogue file (*.xlsx)")

        filename, type_selected = QtWidgets.QFileDialog.getOpenFileName(parent=self,
                                                                        caption=self.tr("Load catalogue"),
                                                                        dir=self.project_directory,
                                                                        filter=files_types)

        if len(filename) > 0:
            if os.path.exists(filename):

                data, logger = load_catalogue(fname=filename)

                if logger.has_logs():
                    self.show_logs(name=self.tr('Open catalogue logger'), logger=logger)

                self.circuit.add_catalogue(data)
                self.refresh_catalogue_dependent_views()
                self.show_info_toast(self.tr("Catalogue loaded!"))
            return None
        else:
            return None

    def save_custom_catalogue(self) -> None:
        """
        Export the current catalogue state to one Excel workbook.

        :return: None.
        """

        # declare the allowed file types
        files_types = self.tr("Catalogue Excel file (*.xlsx)")

        # call dialog to select the file
        filename, type_selected = QtWidgets.QFileDialog.getSaveFileName(self,
                                                                        self.tr('Save catalogue'),
                                                                        '',
                                                                        files_types)
        if filename != "":
            if not (filename.endswith('.xlsx')):
                filename += ".xlsx"

            save_catalogue(fname=filename, grid=self.circuit)
            self.show_info_toast(self.tr("Catalogue saved!"))

    def set_circuit(self, grid: MultiCircuit, create_diagram: bool = True) -> None:
        """
        Replace the active circuit and refresh dependent GUI state.

        :param grid: New active circuit.
        :param create_diagram: Whether to create the default bus-branch diagram.
        :return: None.
        """
        self.remove_all_diagrams()

        self.circuit = grid

        if create_diagram:
            self.add_complete_bus_branch_diagram()

        self.update_date_dependent_combos()
        self.update_from_to_list_views()
        self.clear_results()
        self.setup_time_sliders()
        self.get_circuit_snapshot_datetime()
        self.change_theme_mode()

    def export_psse(self) -> None:
        """
        Open the PSS/E export dialogue.

        :return: None.
        """
        dialog: PsseExportDialogue | None = self.psse_export_dialogue
        if is_dialog_available(dialog=dialog):
            pass
        else:
            dialog = PsseExportDialogue(app=self)
            self.psse_export_dialogue = dialog

        if dialog is not None:
            dialog.show()
            dialog.raise_()
            dialog.activateWindow()
        else:
            pass

    def export_power_factory(self) -> None:
        """
        Open the DGS export dialogue.

        :return: None.
        """
        dialog: DgsExportDialogue | None = self.dgs_export_dialogue
        if is_dialog_available(dialog=dialog):
            pass
        else:
            dialog = DgsExportDialogue(app=self)
            self.dgs_export_dialogue = dialog

        if dialog is not None:
            dialog.show()
            dialog.raise_()
            dialog.activateWindow()
        else:
            pass

    def export_matpower(self) -> None:
        """
        Open the MATPOWER export dialogue.

        :return: None.
        """
        dialog: MatpowerExportDialogue | None = self.matpower_export_dialogue
        if is_dialog_available(dialog=dialog):
            pass
        else:
            dialog = MatpowerExportDialogue(app=self)
            self.matpower_export_dialogue = dialog

        if dialog is not None:
            dialog.show()
            dialog.raise_()
            dialog.activateWindow()
        else:
            pass

    def export_ucte(self) -> None:
        """
        Open the UCTE export dialogue.

        :return: None.
        """
        dialog: UcteExportDialogue | None = self.ucte_export_dialogue
        if is_dialog_available(dialog=dialog):
            pass
        else:
            dialog = UcteExportDialogue(app=self)
            self.ucte_export_dialogue = dialog

        if dialog is not None:
            dialog.show()
            dialog.raise_()
            dialog.activateWindow()
        else:
            pass

    def export_cim(self) -> None:
        """
        Export the current circuit to one CIM XML file.

        :return: None.
        """
        # if the global file_name is empty, ask where to save
        fname = os.path.join(self.project_directory, self.ui.grid_name_line_edit.text())

        files_types = self.tr("CIM (*.xml)")
        filename, type_selected = QtWidgets.QFileDialog.getSaveFileName(self,
                                                                        self.tr('Export to CIM'),
                                                                        fname,
                                                                        files_types)

        if filename != '':

            # if the user did not enter the extension, add it automatically
            name, file_extension = os.path.splitext(filename)

            if file_extension == '':
                filename = name + '.xml'

            # we were able to compose the file correctly, now save it
            self.file_name = filename
            self.save_file_now(
                filename=self.file_name,
                type_selected=type_selected,
                options=FileSavingOptions(
                    file_type=FileType.CIM
                )
            )

    def export_cgmes(self) -> None:
        """
        Open the CGMES export dialogue.

        :return: None.
        """
        dialog: CgmesExportDialogue | None = self.cgmes_dialogue
        if is_dialog_available(dialog=dialog):
            pass
        else:
            dialog = CgmesExportDialogue(app=self)
            self.cgmes_dialogue = dialog

        if dialog is not None:
            dialog.show()
            dialog.raise_()
            dialog.activateWindow()
        else:
            pass

    def export_power_grid_models(self) -> None:
        """
        Export the current circuit to one Power Grid Models file when available.

        :return: None.
        """

        if PGM_AVAILABLE:
            # if the global file_name is empty, ask where to save
            fname = os.path.join(self.project_directory, self.ui.grid_name_line_edit.text())

            files_types = self.tr("Power Grid Models (*.pgm)")
            filename, type_selected = QtWidgets.QFileDialog.getSaveFileName(self,
                                                                            self.tr('Export to Power Grid Models'),
                                                                            fname,
                                                                            files_types)

            if filename != '':

                # if the user did not enter the extension, add it automatically
                name, file_extension = os.path.splitext(filename)

                if file_extension == '':
                    filename = name + '.pgm'

                # we were able to compose the file correctly, now save it
                self.file_name = filename
                self.save_file_now(
                    filename=self.file_name,
                    type_selected=type_selected,
                    options=FileSavingOptions(
                        file_type=FileType.PGM
                    )
                )
        else:
            self.show_warning_toast(self.tr("Power Grid Model unavailable: {reason}").format(
                reason=PGM_UNAVAILABLE_REASON
            ))

    def export_json(self) -> None:
        """
        Export the current circuit to one VeraGrid JSON file.

        :return: None.
        """
        # if the global file_name is empty, ask where to save
        fname = os.path.join(self.project_directory, self.ui.grid_name_line_edit.text())

        files_types = self.tr("Electrical Json V3 (*.ejson3)")
        filename, type_selected = QtWidgets.QFileDialog.getSaveFileName(self,
                                                                        self.tr('Export to JSON'),
                                                                        fname,
                                                                        files_types)

        if filename != '':

            # if the user did not enter the extension, add it automatically
            name, file_extension = os.path.splitext(filename)

            if file_extension == '':
                filename = name + '.ejson3'

            # we were able to compose the file correctly, now save it
            self.file_name = filename
            self.save_file_now(
                filename=self.file_name,
                type_selected=type_selected,
                options=FileSavingOptions(
                    file_type=FileType.VeraGrid_json
                )
            )

    def export_h5(self) -> None:
        """
        Export the current circuit to one VeraGrid HDF5 file.

        :return: None.
        """
        # if the global file_name is empty, ask where to save
        fname = os.path.join(self.project_directory, self.ui.grid_name_line_edit.text())

        files_types = self.tr("VeraGrid HDF5 (*.gch5)")
        filename, type_selected = QtWidgets.QFileDialog.getSaveFileName(self,
                                                                        self.tr('Export to VeraGrid HDF5'),
                                                                        fname,
                                                                        files_types)

        if filename != '':

            # if the user did not enter the extension, add it automatically
            name, file_extension = os.path.splitext(filename)

            if file_extension == '':
                filename = name + '.gch5'

            # we were able to compose the file correctly, now save it
            self.file_name = filename
            self.save_file_now(
                filename=self.file_name,
                type_selected=type_selected,
                options=FileSavingOptions(
                    file_type=FileType.VeraGrid_h5
                )
            )

    def export_excel(self) -> None:
        """
        Export the current circuit to one VeraGrid Excel workbook.

        :return: None.
        """
        # if the global file_name is empty, ask where to save
        fname = os.path.join(self.project_directory, self.ui.grid_name_line_edit.text())

        files_types = self.tr("Excel (*.xlsx)")
        filename, type_selected = QtWidgets.QFileDialog.getSaveFileName(self,
                                                                        self.tr('Export to Microsoft Excel'),
                                                                        fname,
                                                                        files_types)

        if filename != '':

            # if the user did not enter the extension, add it automatically
            name, file_extension = os.path.splitext(filename)

            if file_extension == '':
                filename = name + '.xlsx'

            # we were able to compose the file correctly, now save it
            self.file_name = filename
            self.save_file_now(
                filename=self.file_name,
                type_selected=type_selected,
                options=FileSavingOptions(
                    file_type=FileType.VeraGrid_xlsx4
                )
            )

    def export_sqlite(self) -> None:
        """
        Export the current circuit to one VeraGrid SQLite database.

        :return: None.
        """
        # if the global file_name is empty, ask where to save
        fname = os.path.join(self.project_directory, self.ui.grid_name_line_edit.text())

        files_types = self.tr("Sqlite (*.sqlite)")
        filename, type_selected = QtWidgets.QFileDialog.getSaveFileName(self,
                                                                        self.tr('Export to Sqlite'),
                                                                        fname,
                                                                        files_types)

        if filename != '':

            # if the user did not enter the extension, add it automatically
            name, file_extension = os.path.splitext(filename)

            if file_extension == '':
                filename = name + '.sqlite'

            # we were able to compose the file correctly, now save it
            self.file_name = filename
            self.save_file_now(
                filename=self.file_name,
                type_selected=type_selected,
                options=FileSavingOptions(
                    file_type=FileType.VeraGrid_sqlite
                )
            )

    def export_veragrid_scenario(self):
        """
        Export the current veragrid Scenario to a non-multiverse file
        """
        # if the global file_name is empty, ask where to save
        fname = os.path.join(self.project_directory, self.ui.grid_name_line_edit.text())

        files_types = self.tr("VeraGrid (*.veragrid)")
        filename, type_selected = QtWidgets.QFileDialog.getSaveFileName(self,
                                                                        self.tr('Export VeraGrid scenario'),
                                                                        fname,
                                                                        files_types)

        if filename != '':

            # if the user did not enter the extension, add it automatically
            name, file_extension = os.path.splitext(filename)

            if file_extension == '':
                filename = name + '.veragrid'

            # we were able to compose the file correctly, now save it
            self.file_name = filename
            self.save_file_now(
                filename=self.file_name,
                type_selected=type_selected,
                options=FileSavingOptions(
                    file_type=FileType.VeraGridScenario
                )
            )
