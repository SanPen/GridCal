from __future__ import annotations

import ast
import copy
import multiprocessing
import queue
import tempfile
import time
import traceback
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Set

import numpy as np
import pandas as pd
import shiboken6
from PySide6 import QtCore, QtGui, QtTest
from PySide6 import QtWidgets

import VeraGridEngine as vge
import VeraGrid.Gui.GridReduce.grid_reduce as grid_reduce_module
from VeraGrid.Gui.AboutDialogue.about_dialogue import AboutDialogueGuiGUI
from VeraGrid.Gui.AiAgent.ai_chat_dialogue import AiChatDialogue
from VeraGrid.Gui.Analysis.AnalysisDialogue import GridAnalysisGUI
from VeraGrid.Gui.CatalogueElementsDialogue.catalogue_elements_dialogue import CatalogueElementsSelectionDialogue
from VeraGrid.Gui.ContingencyPlanner.contingency_planner_dialogue import ContingencyPlannerGUI
from VeraGrid.Gui.DeviceEditors.ControllableShuntEditor.controllable_shunt_editor import ControllableShuntEditor
from VeraGrid.Gui.DeviceEditors.DcLineEditor.dc_line_editor import DcLineEditor
from VeraGrid.Gui.DeviceEditors.GeneratorEditor.SolarPowerWizard.solar_power_wizzard import SolarPvWizard
from VeraGrid.Gui.DeviceEditors.GeneratorEditor.WindPowerWizard.wind_power_wizzard import WindFarmWizard
from VeraGrid.Gui.DeviceEditors.GeneratorEditor.generator_editor import GeneratorEditor
from VeraGrid.Gui.DeviceEditors.GeneratorEditor.generator_editor import GeneratorQCurveEditor
from VeraGrid.Gui.DeviceEditors.LineEditor.line_editor import LineEditor
from VeraGrid.Gui.DeviceEditors.LoadDesigner.load_designer import LoadDesigner
from VeraGrid.Gui.DeviceEditors.TemplateDeviceEditor.template_device_editor import TemplateDeviceEditor
from VeraGrid.Gui.DeviceEditors.TowerBuilder.LineBuilderDialogue import TowerBuilderGUI
from VeraGrid.Gui.DeviceEditors.UndergroundCableBuilder.underground_cable_builder import UndergroundCableBuilderGUI
from VeraGrid.Gui.DeviceEditors.Transformer3wEditor.transformer3w_editor import Transformer3WEditor
from VeraGrid.Gui.DeviceEditors.TransformerEditor.transformer_editor import TransformerEditor
from VeraGrid.Gui.Diagrams.Editors.bus_selector import BusSelectorDialogue
from VeraGrid.Gui.Diagrams.Editors.new_line_dialogue import NewMapLineDialogue
from VeraGrid.Gui.Diagrams.graphics_manager import GraphicsManager
from VeraGrid.Gui.Diagrams.MapWidget.grid_map_widget import SelectionDialog
from VeraGrid.Gui.Diagrams.SchematicWidget.diagram_bus_selection_dialogue import DiagramBusSelectorDialogue
import VeraGrid.Gui.Diagrams.SchematicWidget.schematic_widget as schematic_widget_module
from VeraGrid.Gui.DynamicModelEditor.Events.dynamic_events_support import DynamicEventsGroupsDialog
from VeraGrid.Gui.DynamicModelEditor.Events.dynamic_events_support import SwitchSequenceDialog
from VeraGrid.Gui.DynamicModelEditor.Editor.ElementDialogues.jmarti_line_emt_dialog import JMartiLineEmtDialog
from VeraGrid.Gui.DynamicModelEditor.Editor.ElementDialogues.MeasurementsDialog import MeasurementsDialog
from VeraGrid.Gui.DynamicModelEditor.Workspace.detachable_editor_tabs_widget import DynamicEditorPickerDialog
from VeraGrid.Gui.DynamicModelEditor.Editor.dynamic_block_editor import DynamicBlockEditorGUI
from VeraGrid.Gui.DynamicModelEditor.Editor.BlockProperties import AddSymbolDialog
from VeraGrid.Gui.DynamicModelEditor.Editor.BlockProperties import DynamicBlockPropertiesDialog
from VeraGrid.Gui.DynamicModelEditor.Editor.dynamic_editor_validation import (
    ValidationSection,
    ValidationSectionDialog,
    add_validation_detail,
)
from VeraGrid.Gui.DynamicModelEditor.Workspace.dynamic_editor_workspace_window import DynamicEditorWorkspaceWindow
from VeraGrid.Gui.FileDialogues.CGMESDialogue.cgmes_export import CgmesExportDialogue
from VeraGrid.Gui.FileDialogues.CGMESDialogue.cgmes_import import CgmesImportDialogue
from VeraGrid.Gui.FileDialogues.CoordinatesInput.coordinates_dialogue import CoordinatesInputGUI
from VeraGrid.Gui.FileDialogues.DgsDialogue.dgs_export import DgsExportDialogue
from VeraGrid.Gui.FileDialogues.DgsDialogue.dgs_import import DgsImportDialogue
from VeraGrid.Gui.FileDialogues.LoadCatalogue.catalogue_dialogue import CatalogueGUI
from VeraGrid.Gui.FileDialogues.MatpowerDialogue.matpower_export import MatpowerExportDialogue
from VeraGrid.Gui.FileDialogues.ProfilesInput.excel_dialog import ExcelDialog
from VeraGrid.Gui.FileDialogues.ProfilesInput.models_dialogue import ModelsInputGUI
from VeraGrid.Gui.FileDialogues.ProfilesInput.profile_dialogue import GeneratorsProfileOptionsDialogue
from VeraGrid.Gui.FileDialogues.ProfilesInput.profile_dialogue import ProfileInputGUI
from VeraGrid.Gui.FileDialogues.PsseDialogue.psse_export import PsseExportDialogue
from VeraGrid.Gui.FileDialogues.PsseDialogue.psse_import import PsseImportDialogue
from VeraGrid.Gui.FileDialogues.RosetaExplorer.RosetaExplorer import RosetaExplorerGUI
from VeraGrid.Gui.FileDialogues.ServerFileDialog.server_file_dialogue_window import ServerFileDialogue
from VeraGrid.Gui.FileDialogues.UcteDialogue.ucte_export import UcteExportDialogue
from VeraGrid.Gui.FmuTemplateEditor.fmu_template_editor import FmuTemplateEditorDialog
from VeraGrid.Gui.GridGenerator.grid_generator_dialogue import GridGeneratorGUI
from VeraGrid.Gui.GridMerge.grid_diff import GridDiffDialogue
from VeraGrid.Gui.GridMerge.grid_merge import GridMergeDialogue
from VeraGrid.Gui.GridReduce.grid_reduce import GridReduceDialogue
from VeraGrid.Gui.Main.SubClasses.Model.diagrams import DiagramsMain
from VeraGrid.Gui.Main.SubClasses.io import IoMain
from VeraGrid.Gui.Main.object_select_window import ListSelectWindow
from VeraGrid.Gui.Main.object_select_window import ObjectSelectWindow
from VeraGrid.Gui.ProceduralGrid.map_warning import MapWarningDialog
from VeraGrid.Gui.ProceduralGrid.procedural_grid import ProceduralGridWindow
from VeraGrid.Gui.ProceduralGrid.voltage_warning import VoltageWarningDialog
from VeraGrid.Gui.PlotDialogue.plot_dialogue import PlotDialogue
from VeraGrid.Gui.rms_plot_variables_dialog import RmsPlotDialog
from VeraGrid.Gui.ShortCircuitEditor.short_circuit_selector import ShortCircuitSelector
from VeraGrid.Gui.SigmaAnalysis.sigma_analysis_dialogue import SigmaAnalysisGUI
from VeraGrid.Gui.SubstationDesigner.substation_designer import SubstationDesigner
from VeraGrid.Gui.SubstationDesigner.voltage_level_conversion import VoltageLevelConversionWizard
from VeraGrid.Gui.SyncDialogue.sync_dialogue import SyncDialogueWindow
from VeraGrid.Gui.SystemScaler.system_scaler import SystemScaler
from VeraGrid.Gui.PlotDialogue.qt_chart_widget import GraphsWidget
from VeraGrid.Gui.dialog_lifecycle import delete_dialog_safely
from VeraGrid.Gui.dialog_lifecycle import exec_dialog_safely
from VeraGrid.Gui.dialog_lifecycle import is_dialog_available
from VeraGrid.Gui.general_dialogues import ArrayEditor
from VeraGrid.Gui.general_dialogues import CgmesOptionsSelector
from VeraGrid.Gui.general_dialogues import CheckListDialogue
from VeraGrid.Gui.general_dialogues import CorrectInconsistenciesDialogue
from VeraGrid.Gui.general_dialogues import CustomQuestionDialogue
from VeraGrid.Gui.general_dialogues import DeleteDialogue
from VeraGrid.Gui.general_dialogues import DeviceSelectorDialogue
from VeraGrid.Gui.general_dialogues import ElementsDialogue
from VeraGrid.Gui.general_dialogues import FileTypeSelector
from VeraGrid.Gui.general_dialogues import InputNumberDialogue
from VeraGrid.Gui.general_dialogues import InputSearchDialogue
from VeraGrid.Gui.general_dialogues import LogsDialogue
from VeraGrid.Gui.general_dialogues import NewConnectedDeviceDialogue
from VeraGrid.Gui.general_dialogues import NewProfilesStructureDialogue
from VeraGrid.Gui.general_dialogues import StartEndSelectionDialogue
from VeraGrid.Gui.general_dialogues import TimeReIndexDialogue
from VeraGrid.Gui.gui_functions import LookupMatrixEditorDialog
from VeraGrid.Gui.gui_functions import SequenceEditorDialog
from VeraGrid.Gui.object_column_filter_dialog import ObjectColumnFilterDialog
from VeraGrid.Gui.object_model import ObjectsModel
from VeraGrid.Gui.object_proxy_model import ObjectModelFilterProxy
from VeraGrid.Session.session import SimulationSession
from VeraGrid.Gui.DynamicModelEditor.Workspace.dynamic_editor_workspace_session import DynamicEditorWorkspaceSession
from VeraGridEngine.Devices.Dynamic.fmu_template import FmuTemplate
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Devices.Parents.editable_device import GCProp
from VeraGridEngine.IO.file_open import FileOpenOptions
from VeraGridEngine.Simulations.PowerFlow.power_flow_options import PowerFlowOptions
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.symbolic import Var
from VeraGridEngine.basic_structures import Logger
from VeraGridEngine.enumerations import BlockSymbolCategory
from VeraGridEngine.enumerations import BlockType
from VeraGridEngine.enumerations import DeviceType
from VeraGridEngine.enumerations import DynamicSimulationMode
from VeraGridEngine.enumerations import DynEditorGraphicsModes
from VeraGridEngine.enumerations import VarPowerFlowReferenceType
from VeraGridEngine.enumerations import WaveformSequenceType


class DialogSmokeTarget(Enum):
    """
    Dialog classes with stable, cheap constructor fixtures.
    """

    ABOUT_DIALOGUE = "AboutDialogueGuiGUI"
    AI_CHAT_DIALOGUE = "AiChatDialogue"
    GRID_ANALYSIS = "GridAnalysisGUI"
    CATALOGUE_ELEMENTS = "CatalogueElementsSelectionDialogue"
    CONTINGENCY_PLANNER = "ContingencyPlannerGUI"
    CONTROLLABLE_SHUNT_EDITOR = "ControllableShuntEditor"
    DC_LINE_EDITOR = "DcLineEditor"
    SOLAR_PV_WIZARD = "SolarPvWizard"
    WIND_FARM_WIZARD = "WindFarmWizard"
    GENERATOR_EDITOR = "GeneratorEditor"
    GENERATOR_Q_CURVE_EDITOR = "GeneratorQCurveEditor"
    LINE_EDITOR = "LineEditor"
    LOAD_DESIGNER = "LoadDesigner"
    PLOT_DIALOGUE = "PlotDialogue"
    TEMPLATE_DEVICE_EDITOR = "TemplateDeviceEditor"
    TOWER_BUILDER = "TowerBuilderGUI"
    UNDERGROUND_CABLE_BUILDER = "UndergroundCableBuilderGUI"
    TRANSFORMER_3W_EDITOR = "Transformer3WEditor"
    TRANSFORMER_EDITOR = "TransformerEditor"
    BUS_SELECTOR = "BusSelectorDialogue"
    NEW_MAP_LINE = "NewMapLineDialogue"
    MAP_SELECTION = "SelectionDialog"
    DIAGRAM_BUS_SELECTOR = "DiagramBusSelectorDialogue"
    SWITCH_SEQUENCE = "SwitchSequenceDialog"
    DYNAMIC_EVENTS_GROUPS = "DynamicEventsGroupsDialog"
    JMARTI_LINE_EMT = "JMartiLineEmtDialog"
    MEASUREMENTS = "MeasurementsDialog"
    DYNAMIC_BLOCK_EDITOR = "DynamicBlockEditorGUI"
    DYNAMIC_BLOCK_PROPERTIES = "DynamicBlockPropertiesDialog"
    ADD_SYMBOL = "AddSymbolDialog"
    DYNAMIC_EDITOR_PICKER = "DynamicEditorPickerDialog"
    DYNAMIC_EDITOR_WORKSPACE = "DynamicEditorWorkspaceWindow"
    VALIDATION_SECTION = "ValidationSectionDialog"
    CGMES_EXPORT = "CgmesExportDialogue"
    CGMES_IMPORT = "CgmesImportDialogue"
    COORDINATES_INPUT = "CoordinatesInputGUI"
    CATALOGUE = "CatalogueGUI"
    DGS_EXPORT = "DgsExportDialogue"
    DGS_IMPORT = "DgsImportDialogue"
    MATPOWER_EXPORT = "MatpowerExportDialogue"
    EXCEL_DIALOG = "ExcelDialog"
    MODELS_INPUT = "ModelsInputGUI"
    GENERATORS_PROFILE_OPTIONS = "GeneratorsProfileOptionsDialogue"
    PROFILE_INPUT = "ProfileInputGUI"
    PSSE_EXPORT = "PsseExportDialogue"
    PSSE_IMPORT = "PsseImportDialogue"
    ROSETA_EXPLORER = "RosetaExplorerGUI"
    SERVER_FILE = "ServerFileDialogue"
    UCTE_EXPORT = "UcteExportDialogue"
    FMU_TEMPLATE_EDITOR = "FmuTemplateEditorDialog"
    GRID_GENERATOR = "GridGeneratorGUI"
    GRID_DIFF = "GridDiffDialogue"
    GRID_MERGE = "GridMergeDialogue"
    GRID_REDUCE = "GridReduceDialogue"
    OBJECT_SELECT = "ObjectSelectWindow"
    LIST_SELECT = "ListSelectWindow"
    PROCEDURAL_GRID = "ProceduralGridWindow"
    MAP_WARNING = "MapWarningDialog"
    VOLTAGE_WARNING = "VoltageWarningDialog"
    RMS_PLOT = "RmsPlotDialog"
    SHORT_CIRCUIT_SELECTOR = "ShortCircuitSelector"
    SIGMA_ANALYSIS = "SigmaAnalysisGUI"
    SUBSTATION_DESIGNER = "SubstationDesigner"
    VOLTAGE_LEVEL_CONVERSION = "VoltageLevelConversionWizard"
    SYNC_DIALOGUE = "SyncDialogueWindow"
    SYSTEM_SCALER = "SystemScaler"
    NEW_PROFILES_STRUCTURE = "NewProfilesStructureDialogue"
    LOGS = "LogsDialogue"
    DEVICE_SELECTOR = "DeviceSelectorDialogue"
    NEW_CONNECTED_DEVICE = "NewConnectedDeviceDialogue"
    ELEMENTS = "ElementsDialogue"
    TIME_RE_INDEX = "TimeReIndexDialogue"
    CORRECT_INCONSISTENCIES = "CorrectInconsistenciesDialogue"
    CHECK_LIST = "CheckListDialogue"
    DELETE = "DeleteDialogue"
    INPUT_NUMBER = "InputNumberDialogue"
    INPUT_SEARCH = "InputSearchDialogue"
    START_END_SELECTION = "StartEndSelectionDialogue"
    CUSTOM_QUESTION = "CustomQuestionDialogue"
    ARRAY_EDITOR = "ArrayEditor"
    FILE_TYPE_SELECTOR = "FileTypeSelector"
    CGMES_OPTIONS_SELECTOR = "CgmesOptionsSelector"
    SEQUENCE_EDITOR = "SequenceEditorDialog"
    LOOKUP_MATRIX_EDITOR = "LookupMatrixEditorDialog"
    OBJECT_COLUMN_FILTER = "ObjectColumnFilterDialog"


class NamedObject:
    """
    Minimal object with the ``name`` attribute expected by selector dialogs.
    """

    __slots__ = ("name",)

    def __init__(self, name: str) -> None:
        """
        Store the visible name.

        :param name: Visible object name.
        :return: None.
        """
        self.name: str = name

    def __str__(self) -> str:
        """
        Return the visible name.

        :return: Object name.
        """
        return self.name


class ProceduralGraphEngine:
    """Minimal completed procedural-engine result used to render a preview chart."""

    __slots__ = ("_buses", "_lines")

    def __init__(self, buses: List[vge.Bus], lines: List[vge.Line]) -> None:
        """Store a completed topology that can be rendered by the preview window.

        :param buses: Existing preview buses.
        :param lines: Newly created preview lines.
        :return: None.
        """
        self._buses: List[vge.Bus] = buses
        self._lines: List[vge.Line] = lines

    def get_buses(self) -> List[vge.Bus]:
        """Return all preview buses.

        :return: Preview buses.
        """
        return self._buses

    def get_new_buses(self) -> List[vge.Bus]:
        """Return the preview's newly created buses.

        :return: Empty list because this compact fixture adds only a line.
        """
        return list()

    def get_new_lines(self) -> List[vge.Line]:
        """Return the preview's newly created lines.

        :return: Preview lines.
        """
        return self._lines

    def get_new_transformers(self) -> List[vge.Transformer2W]:
        """Return the preview's newly created transformers.

        :return: Empty transformer list.
        """
        return list()


class FakeSpinBox:
    """
    Minimal spin-box facade used by diagram dialogue constructors.
    """

    __slots__ = ()

    def value(self) -> float:
        """
        Return a stable default voltage.

        :return: Default voltage in kV.
        """
        return 110.0


class FakeMainUi:
    """
    Minimal GUI namespace required by a few diagram dialogues.
    """

    __slots__ = ("defaultBusVoltageSpinBox",)

    def __init__(self) -> None:
        """
        Build the fake UI object.

        :return: None.
        """
        self.defaultBusVoltageSpinBox: FakeSpinBox = FakeSpinBox()


class FakeServerDriver:
    """
    Deterministic server driver used by ``ServerFileDialogue``.
    """

    __slots__ = ("_files_payload",)

    def __init__(self) -> None:
        """
        Build a fake server tree.

        :return: None.
        """
        model_rows: List[Dict[str, Any]] = list()
        model_rows.append(
            {
                "idtag": "model-a",
                "name": "Model A",
                "parent_model_idtag": None,
                "is_base_model": True,
            }
        )
        self._files_payload: List[Dict[str, Any]] = list()
        self._files_payload.append(
            {
                "idtag": "file-a",
                "name": "File A",
                "user": "tester",
                "created_at": "2026-01-01T00:00:00Z",
                "models": model_rows,
            }
        )

    def list_database_files_tree(self) -> List[Dict[str, Any]]:
        """
        Return a detached file tree.

        :return: File payload rows.
        """
        return copy.deepcopy(self._files_payload)


class FakeIoApp:
    """
    Minimal main-window facade used by import/export and diagram dialogs.
    """

    __slots__ = (
        "circuit",
        "current_boundary_set",
        "psse_export_dialogue",
        "dgs_export_dialogue",
        "matpower_export_dialogue",
        "ucte_export_dialogue",
        "cgmes_dialogue",
        "file_name",
        "project_directory",
        "server_driver",
        "session",
        "ui",
    )

    def __init__(self, circuit: vge.MultiCircuit) -> None:
        """
        Build the fake application facade.

        :param circuit: Circuit exposed to dialogs.
        :return: None.
        """
        self.psse_export_dialogue: PsseExportDialogue | None = None
        self.dgs_export_dialogue: DgsExportDialogue | None = None
        self.matpower_export_dialogue: MatpowerExportDialogue | None = None
        self.ucte_export_dialogue: UcteExportDialogue | None = None
        self.cgmes_dialogue: CgmesExportDialogue | None = None
        self.circuit: vge.MultiCircuit = circuit
        self.current_boundary_set: Set[object] = set()
        self.file_name: str = ""
        self.project_directory: str = tempfile.gettempdir()
        self.server_driver: FakeServerDriver = FakeServerDriver()
        self.session: SimulationSession = SimulationSession()
        self.ui: FakeMainUi = FakeMainUi()

    def get_selected_buses(self) -> Set[vge.Bus]:
        """
        Return an empty selected-bus set.

        :return: Selected buses.
        """
        return set()

    def get_current_diagram_substations(self) -> list[object]:
        """
        Return no active map substation graphics.

        :return: Empty graphics rows.
        """
        return list()

    def get_diagram_slider_index(self) -> None:
        """
        Return no active time index.

        :return: None.
        """
        return None

    def add_complete_bus_branch_diagram_now(self, name: str = "") -> None:
        """
        Accept diagram creation requests from smoke constructors.

        :param name: Diagram name.
        :return: None.
        """
        del name

    def add_diagram_widget_and_diagram(self, diagram_widget: object, diagram: object) -> None:
        """
        Accept diagram registration requests from smoke constructors.

        :param diagram_widget: Diagram widget.
        :param diagram: Diagram object.
        :return: None.
        """
        del diagram_widget
        del diagram

    def set_diagrams_list_view(self) -> None:
        """
        Accept diagram list refresh requests.

        :return: None.
        """

    def set_diagram_widget(self, widget: object) -> None:
        """
        Accept active diagram widget changes.

        :param widget: Diagram widget.
        :return: None.
        """
        del widget

    def save_file_as(self, *args: object, **kwargs: object) -> None:
        """
        Accept save-as requests without touching disk.

        :param args: Positional arguments.
        :param kwargs: Keyword arguments.
        :return: None.
        """
        del args
        del kwargs

    def save_file_now(self, *args: object, **kwargs: object) -> None:
        """
        Accept save-now requests without touching disk.

        :param args: Positional arguments.
        :param kwargs: Keyword arguments.
        :return: None.
        """
        del args
        del kwargs

    def export_all(self, *args: object, **kwargs: object) -> None:
        """
        Accept export requests without touching disk.

        :param args: Positional arguments.
        :param kwargs: Keyword arguments.
        :return: None.
        """
        del args
        del kwargs


class FakeBranchGraphic:
    """
    Minimal map branch graphic with an ``api_object`` pointer.
    """

    __slots__ = ("api_object",)

    def __init__(self, api_object: object) -> None:
        """
        Store the branch API object.

        :param api_object: Branch object.
        :return: None.
        """
        self.api_object: object = api_object


class FakeQtGraphic(QtWidgets.QWidget):
    """
    Minimal valid Qt graphic wrapper with an API object pointer.
    """

    __slots__ = ("api_object",)

    def __init__(self, api_object: object) -> None:
        """
        Store the API object on a live Qt wrapper.

        :param api_object: API object owned by the graphic.
        :return: None.
        """
        QtWidgets.QWidget.__init__(self)
        self.api_object: object = api_object


class FakeSelectedBusGraphic:
    """
    Minimal selected bus graphic for stale selection lookup tests.
    """

    __slots__ = ("api_object",)

    def __init__(self, api_object: object) -> None:
        """
        Store the API object represented by the fake graphic.

        :param api_object: API object.
        :return: None.
        """
        self.api_object: object = api_object

    def isSelected(self) -> bool:
        """
        Return selected state.

        :return: Always ``True``.
        """
        return True


class FakeReductionDiagram:
    """
    Minimal diagram facade for stale-graphics cleanup.
    """

    __slots__ = ("graphics_manager", "removed_graphics")

    def __init__(self) -> None:
        """
        Build an empty fake reduction diagram.

        :return: None.
        """
        self.graphics_manager: GraphicsManager = GraphicsManager()
        self.removed_graphics: List[object] = list()

    def _remove_from_scene(self, graphic_object: object) -> None:
        """
        Record scene-only removal.

        :param graphic_object: Graphic object to remove.
        :return: None.
        """
        self.removed_graphics.append(graphic_object)


class FakeReductionMain:
    """
    Minimal main-window facade exposing the active circuit.
    """

    __slots__ = ("circuit",)

    def __init__(self, circuit: vge.MultiCircuit) -> None:
        """
        Store the active circuit.

        :param circuit: Active circuit.
        :return: None.
        """
        self.circuit: vge.MultiCircuit = circuit


class FakeDiagramListView:
    """
    Diagram-list facade with a current row but no selected rows.
    """

    __slots__ = ("_current_index",)

    def __init__(self, current_index: QtCore.QModelIndex) -> None:
        """
        Store the current model index.

        :param current_index: Current model index.
        :return: None.
        """
        self._current_index: QtCore.QModelIndex = current_index

    def selectedIndexes(self) -> List[QtCore.QModelIndex]:
        """
        Return no selected rows.

        :return: Empty index list.
        """
        return list()

    def currentIndex(self) -> QtCore.QModelIndex:
        """
        Return the current row.

        :return: Current index.
        """
        return self._current_index


class FakeDiagramMainUi:
    """
    Minimal UI facade exposing the diagrams list view.
    """

    __slots__ = ("diagramsListView",)

    def __init__(self, diagrams_list_view: FakeDiagramListView) -> None:
        """
        Store the diagrams list view.

        :param diagrams_list_view: Diagram list view facade.
        :return: None.
        """
        self.diagramsListView: FakeDiagramListView = diagrams_list_view


class FakeDiagramMain:
    """
    Main facade for selected-diagram fallback tests.
    """

    __slots__ = ("diagram_widgets_list", "ui")

    def __init__(self, current_index: QtCore.QModelIndex) -> None:
        """
        Build the fake main facade.

        :param current_index: Current diagram-list index.
        :return: None.
        """
        self.diagram_widgets_list: List[object] = [object()]
        self.ui: FakeDiagramMainUi = FakeDiagramMainUi(
            diagrams_list_view=FakeDiagramListView(current_index=current_index)
        )

    def _ensure_diagram_widget_at_index(self, index: int) -> object | None:
        """
        Return the diagram object at the requested row.

        :param index: Diagram row.
        :return: Diagram object.
        """
        if index == 0:
            return self.diagram_widgets_list[0]
        else:
            return None


class FakeSyncThread:
    """
    Minimal sync-thread facade used by ``SyncDialogueWindow``.
    """

    __slots__ = ("issues",)

    def __init__(self) -> None:
        """
        Build an empty issue list.

        :return: None.
        """
        self.issues: list[object] = list()

    def pause(self) -> None:
        """
        Accept pause requests.

        :return: None.
        """

    def resume(self) -> None:
        """
        Accept resume requests.

        :return: None.
        """

    def process_issues(self) -> None:
        """
        Accept issue-processing requests.

        :return: None.
        """


class FakeRmsResults:
    """
    Minimal result object consumed by ``RmsPlotDialog``.
    """

    __slots__ = (
        "devices",
        "devices_vars_info",
        "time_array",
        "uid2idx",
        "units",
        "values",
        "variable_array",
        "vars_glob_name2uid",
    )

    def __init__(self, device: object, variable: Var) -> None:
        """
        Build the result facade.

        :param device: Device owning the variable.
        :param variable: Dynamic variable.
        :return: None.
        """
        variables: List[Var] = list()
        variables.append(variable)
        self.devices: List[object] = list()
        self.devices.append(device)
        self.devices_vars_info: Dict[object, List[Var]] = dict()
        self.devices_vars_info[device] = variables
        self.time_array: np.ndarray = np.array([0.0, 1.0], dtype=float)
        self.uid2idx: Dict[int, int] = dict()
        self.uid2idx[1] = 0
        self.vars_glob_name2uid: Dict[str, int] = dict()
        self.vars_glob_name2uid["speedGenerator"] = 1
        self.variable_array: np.ndarray = np.array(["speedGenerator"], dtype=str)
        self.values: np.ndarray = np.zeros((2, 1), dtype=float)
        self.units: str = ""


class DialogSmokeContext:
    """
    Shared real objects used to construct smoke dialogs.
    """

    __slots__ = ("app", "circuit", "fake_app", "time_array")

    def __init__(self, app: QtWidgets.QApplication) -> None:
        """
        Build one smoke context.

        :param app: Shared Qt application.
        :return: None.
        """
        self.app: QtWidgets.QApplication = app
        self.circuit: vge.MultiCircuit = build_smoke_circuit()
        self.fake_app: FakeIoApp = FakeIoApp(circuit=self.circuit)
        self.time_array: pd.DatetimeIndex = pd.date_range("2026-01-01 00:00:00", periods=2, freq="h")


def build_smoke_circuit() -> vge.MultiCircuit:
    """
    Build the smallest circuit that satisfies editor constructors.

    :return: Smoke-test circuit.
    """
    circuit: vge.MultiCircuit = vge.MultiCircuit()
    bus_from: vge.Bus = vge.Bus(name="Bus 1", Vnom=110.0, is_slack=True, latitude=1.0, longitude=1.0)
    bus_to: vge.Bus = vge.Bus(name="Bus 2", Vnom=110.0, latitude=2.0, longitude=2.0)
    circuit.add_bus(obj=bus_from)
    circuit.add_bus(obj=bus_to)

    line: vge.Line = vge.Line(name="Line", bus_from=bus_from, bus_to=bus_to, r=0.01, x=0.05, rate=100.0)
    circuit.add_line(obj=line)
    dc_line: vge.DcLine = vge.DcLine(name="DC Line", bus_from=bus_from, bus_to=bus_to, r=0.01, rate=100.0)
    circuit.add_dc_line(dc_line)
    transformer_2w: vge.Transformer2W = vge.Transformer2W(
        name="Transformer 2W",
        bus_from=bus_from,
        bus_to=bus_to,
        rate=100.0,
    )
    circuit.add_transformer2w(transformer_2w)
    transformer_3w: vge.Transformer3W = vge.Transformer3W(
        name="Transformer 3W",
        bus1=bus_from,
        bus2=bus_to,
        bus3=bus_to,
        V1=110.0,
        V2=110.0,
        V3=110.0,
        rate12=100.0,
        rate23=100.0,
        rate31=100.0,
    )
    circuit.add_transformer3w(transformer_3w)

    load: vge.Load = vge.Load(name="Load", P=1.0, Q=0.2)
    circuit.add_load(bus=bus_to, api_obj=load)
    generator: vge.Generator = vge.Generator(name="Generator", P=1.0)
    circuit.add_generator(bus=bus_from, api_obj=generator)
    shunt: vge.ControllableShunt = vge.ControllableShunt(name="Controllable Shunt")
    circuit.add_controllable_shunt(bus=bus_to, api_obj=shunt)
    substation: vge.Substation = vge.Substation(name="Substation")
    circuit.add_substation(substation)
    rms_events_group: vge.RmsEventsGroup = vge.RmsEventsGroup(name="RMS events")
    circuit.add_rms_events_group(rms_events_group)

    return circuit


def accept_grid_reduction_question(text: str, title: str) -> bool:
    """
    Accept the destructive grid-reduction confirmation in the regression test.

    :param text: Question text.
    :param title: Question title.
    :return: Always ``True``.
    """
    return True


def fake_logged_ptdf_reduction(grid: vge.MultiCircuit,
                               reduction_bus_indices: np.ndarray) -> tuple[vge.MultiCircuit, Logger]:
    """
    Mutate the grid like the real reducer and emit one log entry.

    :param grid: Circuit to reduce.
    :param reduction_bus_indices: Bus indices to delete.
    :return: Reduced circuit and logger.
    """
    logger: Logger = Logger()
    bus_to_delete: vge.Bus

    logger.add_info(msg="synthetic reduction log")
    if grid.get_bus_number() > 1:
        bus_to_delete = grid.buses[1]
    else:
        bus_to_delete = grid.buses[int(reduction_bus_indices[0])]

    grid.delete_buses(lst=[bus_to_delete], delete_associated=True)
    return grid, logger


def fake_failing_ptdf_reduction(grid: vge.MultiCircuit,
                                reduction_bus_indices: np.ndarray) -> tuple[vge.MultiCircuit, Logger]:
    """
    Mutate the reducer input and fail like the PTDF dimension error.

    :param grid: Circuit passed to the reducer.
    :param reduction_bus_indices: Bus indices to delete.
    :return: Never returned.
    """
    grid.delete_buses(lst=[grid.buses[int(reduction_bus_indices[0])]], delete_associated=True)
    raise ValueError("Incompatible dimensions")


def build_object_filter_dialog() -> ObjectColumnFilterDialog:
    """
    Build an object-column filter dialog with a real proxy model.

    :return: Dialog instance.
    """
    table_view: QtWidgets.QTableView = QtWidgets.QTableView()
    bus: vge.Bus = vge.Bus(name="Alpha")
    objects: List[vge.Bus] = list()
    objects.append(bus)
    properties: List[GCProp] = list()
    properties.append(bus.registered_properties["name"])
    source_model: ObjectsModel = ObjectsModel(
        objects=objects,
        property_list=properties,
        time_index=None,
        parent=table_view,
        editable=True,
    )
    proxy_model: ObjectModelFilterProxy = ObjectModelFilterProxy(mdl=source_model)
    table_view.setModel(proxy_model)
    dialog: ObjectColumnFilterDialog = ObjectColumnFilterDialog(
        proxy_model=proxy_model,
        source_column=0,
        table_view=table_view,
        parent=table_view,
    )
    return dialog


def build_rms_results(circuit: vge.MultiCircuit) -> FakeRmsResults:
    """
    Build minimal RMS results for the plot-variable dialog.

    :param circuit: Circuit supplying one visible device.
    :return: RMS results facade.
    """
    variable: Var = Var(name="speed", uid=1)
    results: FakeRmsResults = FakeRmsResults(device=circuit.generators[0], variable=variable)
    return results


def build_dialog_for_smoke(target: DialogSmokeTarget, context: DialogSmokeContext) -> QtWidgets.QWidget:
    """
    Build one dialog for smoke testing.

    :param target: Dialog target.
    :param context: Shared smoke context.
    :return: Dialog widget.
    """
    circuit: vge.MultiCircuit = context.circuit
    fake_app: FakeIoApp = context.fake_app

    if target == DialogSmokeTarget.ABOUT_DIALOGUE:
        dialog: QtWidgets.QWidget = AboutDialogueGuiGUI()
    elif target == DialogSmokeTarget.AI_CHAT_DIALOGUE:
        dialog = AiChatDialogue()
    elif target == DialogSmokeTarget.GRID_ANALYSIS:
        dialog = GridAnalysisGUI(circuit=circuit)
    elif target == DialogSmokeTarget.CATALOGUE_ELEMENTS:
        dialog = CatalogueElementsSelectionDialogue(parent=None, circuit=circuit)
    elif target == DialogSmokeTarget.CONTINGENCY_PLANNER:
        dialog = ContingencyPlannerGUI(grid=circuit)
    elif target == DialogSmokeTarget.CONTROLLABLE_SHUNT_EDITOR:
        dialog = ControllableShuntEditor(api_object=circuit.controllable_shunts[0])
    elif target == DialogSmokeTarget.DC_LINE_EDITOR:
        dialog = DcLineEditor(branch=circuit.dc_lines[0])
    elif target == DialogSmokeTarget.SOLAR_PV_WIZARD:
        dialog = SolarPvWizard(
            time_array=context.time_array,
            peak_power=1.0,
            latitude=28.0,
            longitude=-16.0,
        )
    elif target == DialogSmokeTarget.WIND_FARM_WIZARD:
        dialog = WindFarmWizard(
            time_array=context.time_array,
            peak_power=1.0,
            latitude=28.0,
            longitude=-16.0,
        )
    elif target == DialogSmokeTarget.GENERATOR_EDITOR:
        dialog = GeneratorEditor(api_object=circuit.generators[0], circuit=circuit)
    elif target == DialogSmokeTarget.GENERATOR_Q_CURVE_EDITOR:
        dialog = GeneratorQCurveEditor(
            q_curve=vge.GeneratorQCurve(),
            Qmin=-1.0,
            Qmax=1.0,
            Pmin=0.0,
            Pmax=1.0,
            Snom=1.0,
        )
    elif target == DialogSmokeTarget.LINE_EDITOR:
        dialog = LineEditor(line=circuit.lines[0], grid=circuit)
    elif target == DialogSmokeTarget.LOAD_DESIGNER:
        dialog = LoadDesigner(
            time_array=context.time_array,
            active_power=1.0,
            reactive_power=0.2,
            latitude=28.0,
            longitude=-16.0,
        )
    elif target == DialogSmokeTarget.PLOT_DIALOGUE:
        dialog = PlotDialogue(title="Smoke plot")
    elif target == DialogSmokeTarget.TEMPLATE_DEVICE_EDITOR:
        dialog = TemplateDeviceEditor(api_object=circuit.lines[0], circuit=circuit)
    elif target == DialogSmokeTarget.TOWER_BUILDER:
        dialog = TowerBuilderGUI(tower=vge.OverheadLineType(name="Tower", Vnom=110.0), wires_catalogue=list())
    elif target == DialogSmokeTarget.UNDERGROUND_CABLE_BUILDER:
        cable: vge.UndergroundCableType = vge.UndergroundCableType(name="Smoke cable")
        dialog = UndergroundCableBuilderGUI(
            system=vge.UndergroundLineType(name="Cable system", Vnom=110.0),
            cables_catalogue=list((cable,)),
        )
    elif target == DialogSmokeTarget.TRANSFORMER_3W_EDITOR:
        dialog = Transformer3WEditor(tr3=circuit.transformers3w[0], Sbase=circuit.Sbase)
    elif target == DialogSmokeTarget.TRANSFORMER_EDITOR:
        dialog = TransformerEditor(branch=circuit.transformers2w[0], grid=circuit)
    elif target == DialogSmokeTarget.BUS_SELECTOR:
        dialog = BusSelectorDialogue(grid=circuit, se=circuit.substations[0])
    elif target == DialogSmokeTarget.NEW_MAP_LINE:
        dialog = NewMapLineDialogue(grid=circuit, se_from=circuit.substations[0], se_to=circuit.substations[0])
    elif target == DialogSmokeTarget.MAP_SELECTION:
        dialog = SelectionDialog(branch=FakeBranchGraphic(api_object=circuit.lines[0]), vnom=110.0)
    elif target == DialogSmokeTarget.DIAGRAM_BUS_SELECTOR:
        dialog = DiagramBusSelectorDialogue(gui=fake_app, grid=circuit, substation=circuit.substations[0])
    elif target == DialogSmokeTarget.SWITCH_SEQUENCE:
        dialog = SwitchSequenceDialog(mode_parameters=list(), events_groups=list())
    elif target == DialogSmokeTarget.DYNAMIC_EVENTS_GROUPS:
        dialog = DynamicEventsGroupsDialog(mode=DynamicSimulationMode.RMS)
    elif target == DialogSmokeTarget.JMARTI_LINE_EMT:
        dialog = JMartiLineEmtDialog()
    elif target == DialogSmokeTarget.MEASUREMENTS:
        measurements: Dict[str, Dict[BlockType, List[VarPowerFlowReferenceType]]] = dict()
        ac_measurements: Dict[BlockType, List[VarPowerFlowReferenceType]] = dict()
        voltage_references: List[VarPowerFlowReferenceType] = list()
        voltage_references.append(VarPowerFlowReferenceType.Vm)
        ac_measurements[BlockType.MEASUREMENTS_VOLTAGE_ANGLE] = voltage_references
        measurements["a_c_bus"] = ac_measurements
        dialog = MeasurementsDialog(
            buses=circuit.buses,
            measurement_vars_dict=measurements,
        )
    elif target == DialogSmokeTarget.DYNAMIC_BLOCK_EDITOR:
        root_block: Block = Block(name="Root")
        dialog = DynamicBlockEditorGUI(
            var_factory=circuit.var_factory,
            api_object=circuit.loads[0],
            circuit=circuit,
            current_theme=DynEditorGraphicsModes.LIGHT,
            mode=DynamicSimulationMode.RMS,
            templates_list=list(),
            is_root_editor=True,
            modal=False,
            workspace_embedded=False,
            root_block=root_block,
            current_block=root_block,
        )
    elif target == DialogSmokeTarget.DYNAMIC_BLOCK_PROPERTIES:
        variable: Var = Var(name="x", uid=100)
        output_variables: List[Var] = list()
        output_variables.append(variable)
        block: Block = Block(name="Gain", out_vars=output_variables)
        dialog = DynamicBlockPropertiesDialog(
            block=block,
            block_type_name=BlockType.GAIN.name,
            var_factory=VarFactory(),
        )
    elif target == DialogSmokeTarget.ADD_SYMBOL:
        owner_block: Block = Block(name="Owner")
        owners: list[Block] = list()
        owners.append(owner_block)
        dialog = AddSymbolDialog(
            category=BlockSymbolCategory.VARIABLES,
            owners=owners,
            preferred_owner=owner_block,
        )
    elif target == DialogSmokeTarget.DYNAMIC_EDITOR_PICKER:
        dialog = DynamicEditorPickerDialog(entries=list())
    elif target == DialogSmokeTarget.DYNAMIC_EDITOR_WORKSPACE:
        dialog = DynamicEditorWorkspaceWindow(session=DynamicEditorWorkspaceSession())
    elif target == DialogSmokeTarget.VALIDATION_SECTION:
        dialog = ValidationSectionDialog(section_results=list())
    elif target == DialogSmokeTarget.CGMES_EXPORT:
        dialog = CgmesExportDialogue(app=fake_app)
    elif target == DialogSmokeTarget.CGMES_IMPORT:
        dialog = CgmesImportDialogue(app=fake_app, options=FileOpenOptions())
    elif target == DialogSmokeTarget.COORDINATES_INPUT:
        dialog = CoordinatesInputGUI(grid=circuit)
    elif target == DialogSmokeTarget.CATALOGUE:
        dialog = CatalogueGUI()
    elif target == DialogSmokeTarget.DGS_EXPORT:
        dialog = DgsExportDialogue(app=fake_app)
    elif target == DialogSmokeTarget.DGS_IMPORT:
        dialog = DgsImportDialogue(options=FileOpenOptions())
    elif target == DialogSmokeTarget.MATPOWER_EXPORT:
        dialog = MatpowerExportDialogue(app=fake_app)
    elif target == DialogSmokeTarget.EXCEL_DIALOG:
        dialog = ExcelDialog()
    elif target == DialogSmokeTarget.MODELS_INPUT:
        dialog = ModelsInputGUI(main_grid=circuit)
    elif target == DialogSmokeTarget.GENERATORS_PROFILE_OPTIONS:
        dialog = GeneratorsProfileOptionsDialogue()
    elif target == DialogSmokeTarget.PROFILE_INPUT:
        dialog = ProfileInputGUI(
            parent=None,
            circuit=circuit,
            dev_type=DeviceType.LoadDevice,
            objects=circuit.loads,
            magnitude="P",
        )
    elif target == DialogSmokeTarget.PSSE_EXPORT:
        dialog = PsseExportDialogue(app=fake_app)
    elif target == DialogSmokeTarget.PSSE_IMPORT:
        dialog = PsseImportDialogue(app=fake_app, options=FileOpenOptions())
    elif target == DialogSmokeTarget.ROSETA_EXPLORER:
        dialog = RosetaExplorerGUI()
    elif target == DialogSmokeTarget.SERVER_FILE:
        dialog = ServerFileDialogue(parent=None, app=fake_app)
    elif target == DialogSmokeTarget.UCTE_EXPORT:
        dialog = UcteExportDialogue(app=fake_app)
    elif target == DialogSmokeTarget.FMU_TEMPLATE_EDITOR:
        dialog = FmuTemplateEditorDialog(
            circuit=circuit,
            template=FmuTemplate(name="FMU"),
            project_directory=tempfile.gettempdir(),
        )
    elif target == DialogSmokeTarget.GRID_GENERATOR:
        dialog = GridGeneratorGUI()
    elif target == DialogSmokeTarget.GRID_DIFF:
        dialog = GridDiffDialogue(grid=circuit)
    elif target == DialogSmokeTarget.GRID_MERGE:
        dialog = GridMergeDialogue(grid=circuit, diff=circuit)
    elif target == DialogSmokeTarget.GRID_REDUCE:
        selected_buses: Set[vge.Bus] = set()
        selected_buses.add(circuit.buses[0])
        dialog = GridReduceDialogue(grid=circuit, session=SimulationSession(), selected_buses_set=selected_buses)
    elif target == DialogSmokeTarget.OBJECT_SELECT:
        named_objects: List[NamedObject] = list()
        named_objects.append(NamedObject(name="Alpha"))
        named_objects.append(NamedObject(name="Beta"))
        dialog = ObjectSelectWindow(title="Select object", object_list=named_objects)
    elif target == DialogSmokeTarget.LIST_SELECT:
        elements: List[str] = list()
        elements.append("Alpha")
        elements.append("Beta")
        dialog = ListSelectWindow(title="Select value", elements=elements)
    elif target == DialogSmokeTarget.PROCEDURAL_GRID:
        dialog = ProceduralGridWindow(app=fake_app)
    elif target == DialogSmokeTarget.MAP_WARNING:
        dialog = MapWarningDialog()
    elif target == DialogSmokeTarget.VOLTAGE_WARNING:
        offenders: List[tuple[str, float]] = list()
        offenders.append(("Bus", 33.0))
        dialog = VoltageWarningDialog(offenders=offenders, valid_voltages=[10.0, 20.0])
    elif target == DialogSmokeTarget.RMS_PLOT:
        dialog = RmsPlotDialog(results=build_rms_results(circuit=circuit))
    elif target == DialogSmokeTarget.SHORT_CIRCUIT_SELECTOR:
        dialog = ShortCircuitSelector()
    elif target == DialogSmokeTarget.SIGMA_ANALYSIS:
        dialog = SigmaAnalysisGUI(grid=circuit, options=PowerFlowOptions(), classical_sigma=True)
    elif target == DialogSmokeTarget.SUBSTATION_DESIGNER:
        dialog = SubstationDesigner(grid=circuit)
    elif target == DialogSmokeTarget.VOLTAGE_LEVEL_CONVERSION:
        dialog = VoltageLevelConversionWizard(bus=circuit.buses[0], grid=circuit)
    elif target == DialogSmokeTarget.SYNC_DIALOGUE:
        dialog = SyncDialogueWindow(file_sync_thread=FakeSyncThread())
    elif target == DialogSmokeTarget.SYSTEM_SCALER:
        dialog = SystemScaler(grid=circuit)
    elif target == DialogSmokeTarget.NEW_PROFILES_STRUCTURE:
        dialog = NewProfilesStructureDialogue()
    elif target == DialogSmokeTarget.LOGS:
        dialog = LogsDialogue(name="Log", logger=Logger())
    elif target == DialogSmokeTarget.DEVICE_SELECTOR:
        dialog = DeviceSelectorDialogue(devices_by_type={DeviceType.BusDevice: circuit.buses})
    elif target == DialogSmokeTarget.NEW_CONNECTED_DEVICE:
        dialog = NewConnectedDeviceDialogue(name="New", bus_count=2, buses=circuit.buses)
    elif target == DialogSmokeTarget.ELEMENTS:
        dialog = ElementsDialogue(name="Elements", elements=circuit.buses)
    elif target == DialogSmokeTarget.TIME_RE_INDEX:
        dialog = TimeReIndexDialogue()
    elif target == DialogSmokeTarget.CORRECT_INCONSISTENCIES:
        dialog = CorrectInconsistenciesDialogue()
    elif target == DialogSmokeTarget.CHECK_LIST:
        dialog = CheckListDialogue(objects_list=["Alpha", "Beta"])
    elif target == DialogSmokeTarget.DELETE:
        dialog = DeleteDialogue(names_list=["Alpha", "Beta"])
    elif target == DialogSmokeTarget.INPUT_NUMBER:
        dialog = InputNumberDialogue(min_value=0.0, max_value=10.0, default_value=1.0)
    elif target == DialogSmokeTarget.INPUT_SEARCH:
        dialog = InputSearchDialogue(deafault_value="Alpha")
    elif target == DialogSmokeTarget.START_END_SELECTION:
        dialog = StartEndSelectionDialogue(min_value=0, max_value=1, time_array=context.time_array)
    elif target == DialogSmokeTarget.CUSTOM_QUESTION:
        dialog = CustomQuestionDialogue(title="Question", question="Continue?", answer1="Yes", answer2="No")
    elif target == DialogSmokeTarget.ARRAY_EDITOR:
        dialog = ArrayEditor()
    elif target == DialogSmokeTarget.FILE_TYPE_SELECTOR:
        dialog = FileTypeSelector(file_name="grid.veragrid")
    elif target == DialogSmokeTarget.CGMES_OPTIONS_SELECTOR:
        dialog = CgmesOptionsSelector()
    elif target == DialogSmokeTarget.SEQUENCE_EDITOR:
        dialog = SequenceEditorDialog(parent=None, sequence_type=WaveformSequenceType)
    elif target == DialogSmokeTarget.LOOKUP_MATRIX_EDITOR:
        dialog = LookupMatrixEditorDialog()
    elif target == DialogSmokeTarget.OBJECT_COLUMN_FILTER:
        dialog = build_object_filter_dialog()
    else:
        raise AssertionError(f"Unhandled smoke target {target}")

    return dialog


def close_dialog_for_smoke(dialog: QtWidgets.QWidget,
                           app: QtWidgets.QApplication,
                           close_extra_widgets: bool = True) -> None:
    """
    Close one smoke dialog using its real lifecycle.

    :param dialog: Dialog or window to close.
    :param app: Shared Qt application.
    :param close_extra_widgets: Close helper top-level widgets created by the dialog.
    :return: None.
    """
    if is_dialog_available(dialog=dialog):
        if isinstance(dialog, AiChatDialogue):
            dialog.prepare_for_shutdown()
            dialog.shutdown_turn_thread()
            dialog.close()
        elif isinstance(dialog, QtWidgets.QDialog):
            dialog.reject()
        else:
            dialog.close()

        delete_dialog_safely(dialog=dialog)
    else:
        pass

    if close_extra_widgets:
        close_extra_top_level_widgets(app=app, primary_dialog=dialog)
        collect_qt_deletes(app=app)
    else:
        app.processEvents()


def close_extra_top_level_widgets(app: QtWidgets.QApplication, primary_dialog: QtWidgets.QWidget | None) -> None:
    """
    Close top-level helper widgets created by smoke-dialog constructors.

    :param app: Shared Qt application.
    :param primary_dialog: Dialog already closed by the caller.
    :return: None.
    """
    widgets: List[QtWidgets.QWidget] = list(app.topLevelWidgets())
    widget: QtWidgets.QWidget
    for widget in widgets:
        if widget is primary_dialog:
            pass
        elif is_dialog_available(dialog=widget):
            if isinstance(widget, AiChatDialogue):
                widget.prepare_for_shutdown()
                widget.shutdown_turn_thread()
                widget.close()
            elif isinstance(widget, QtWidgets.QDialog):
                widget.reject()
            else:
                widget.close()
            delete_dialog_safely(dialog=widget)
        else:
            pass


def collect_qt_deletes(app: QtWidgets.QApplication) -> None:
    """
    Flush Qt deferred deletes left by smoke constructors.

    :param app: Shared Qt application.
    :return: None.
    """
    app.processEvents()
    QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.Type.DeferredDelete)
    app.processEvents()
    QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.Type.DeferredDelete)
    app.processEvents()


def exercise_chart_widgets_for_smoke(dialog: QtWidgets.QWidget, app: QtWidgets.QApplication) -> None:
    """Exercise every embedded QWidget chart through its paint lifecycle.

    :param dialog: Displayed window that owns the chart widgets.
    :param app: Shared Qt application delivering renderer events.
    :return: None.
    """
    plot_widgets: list[GraphsWidget] = dialog.findChildren(GraphsWidget)
    plot_widget: GraphsWidget
    for plot_widget in plot_widgets:
        # Start from a known state before repeatedly replacing private point buffers.
        plot_widget.clear()
        x_values: np.ndarray = np.asarray((0.0, 1.0, 2.0), dtype=float)
        plot_widget.add_line_series(name="Smoke line", x_values=x_values, y_values=x_values, color="#2563eb")
        plot_widget.add_scatter_series(name="Smoke points", x_values=x_values, y_values=-x_values, color="#f97316")
        original_series: tuple[object, ...] = tuple(plot_widget._series)
        assert len(original_series) == 2

        update_index: int
        for update_index in range(12):
            updated_x: np.ndarray = np.linspace(0.0, 2.0 + update_index, 8)
            updated_y: np.ndarray = updated_x * float(update_index + 1)
            updated: bool = plot_widget.replace_xy_series_data(series_data=(
                (updated_x, updated_y, "#2563eb"),
                (updated_x, -updated_y, "#f97316"),
            ))
            assert updated
            assert tuple(plot_widget._series) == original_series
            dialog.resize(760 + update_index, 520 + update_index)
            plot_widget.redraw()
            app.processEvents()

        # A final clear releases buffers before dialog close disposes the chart widget.
        plot_widget.clear()
        app.processEvents()


def exercise_chart_window_operation_for_smoke(target: DialogSmokeTarget,
                                              dialog: QtWidgets.QWidget,
                                              app: QtWidgets.QApplication) -> None:
    """Run the real chart-producing operation for each chart-hosting window.

    :param target: Dialog type whose chart operation is exercised.
    :param dialog: Displayed dialog owning the chart.
    :param app: Shared Qt application delivering renderer events.
    :return: None.
    """
    if target == DialogSmokeTarget.SOLAR_PV_WIZARD and isinstance(dialog, SolarPvWizard):
        dialog.plot()
        assert len(dialog._open_plot_dialogs) == 1
    elif target == DialogSmokeTarget.WIND_FARM_WIZARD and isinstance(dialog, WindFarmWizard):
        dialog.plot()
        assert len(dialog._open_plot_dialogs) == 1
    elif target == DialogSmokeTarget.RMS_PLOT and isinstance(dialog, RmsPlotDialog):
        dialog.add_variable()
        dialog.show_external_plot()
        assert dialog._plot_dialogue is not None
    elif target == DialogSmokeTarget.PROFILE_INPUT and isinstance(dialog, ProfileInputGUI):
        profile_data: pd.DataFrame = pd.DataFrame(
            data={"Smoke profile": (1.0, 2.0)},
            index=pd.date_range("2026-01-01", periods=2, freq="h"),
        )
        dialog.assign_origin_df(df=profile_data)
        profile_index: QtCore.QModelIndex = dialog.ui.sources_list.model().index(0, 0)
        dialog.ui.sources_list.selectionModel().select(
            profile_index,
            QtCore.QItemSelectionModel.SelectionFlag.ClearAndSelect,
        )
        dialog.plot_selected()
        assert len(dialog._open_plot_dialogs) == 1
    elif target == DialogSmokeTarget.TEMPLATE_DEVICE_EDITOR and isinstance(dialog, TemplateDeviceEditor):
        grouped_series: dict[str, list[tuple[str, np.ndarray]]] = dict()
        grouped_series["MW"] = [("Smoke profile", np.asarray((1.0, 2.0), dtype=float))]
        dialog._open_profiles_plot_dialog(grouped_series=grouped_series, title="Smoke profiles")
        assert len(dialog._open_plot_dialogs) == 1
    elif target == DialogSmokeTarget.SEQUENCE_EDITOR and isinstance(dialog, SequenceEditorDialog):
        dialog.add_point()
        dialog.add_point()
        dialog.table.item(1, 0).setText("1.0")
        dialog.table.item(1, 1).setText("2.0")
        dialog.show_plot()
        assert dialog._plot_dialogue is not None
    elif target == DialogSmokeTarget.LOOKUP_MATRIX_EDITOR and isinstance(dialog, LookupMatrixEditorDialog):
        dialog._add_x()
        dialog._add_x()
        dialog._add_y()
        dialog._add_y()
        dialog.show_plot()
        assert dialog._plot_dialogue is not None
    elif target == DialogSmokeTarget.TOWER_BUILDER and isinstance(dialog, TowerBuilderGUI):
        wire: vge.Wire = vge.Wire(name="Smoke wire", diameter=23.0, diameter_internal=9.0,
                                  is_tube=True, r=0.19, max_current=1.0)
        dialog.tower_driver.tower.add_wire_relationship(wire=wire, xpos=-2.0, ypos=20.0, phase=1)
        dialog.tower_driver.tower.add_wire_relationship(wire=wire, xpos=0.0, ypos=20.0, phase=2)
        dialog.tower_driver.tower.add_wire_relationship(wire=wire, xpos=2.0, ypos=20.0, phase=3)
        dialog.compute()
        original_series: tuple[object, ...] = tuple(dialog.ui.plotwidget._series)
        dialog.compute()
        assert tuple(dialog.ui.plotwidget._series) == original_series
    elif target == DialogSmokeTarget.UNDERGROUND_CABLE_BUILDER and isinstance(dialog, UndergroundCableBuilderGUI):
        dialog.ui.wires_tableView.selectRow(0)
        dialog.add_cable_to_system()
        original_series = tuple(dialog.ui.plotwidget._series)
        dialog.plot()
        assert len(original_series) == 1
        assert tuple(dialog.ui.plotwidget._series) == original_series
        dialog.ui.tower_tableView.selectRow(0)
        dialog.delete_cable_from_system()
        assert tuple(dialog.ui.plotwidget._series) == original_series
    elif target == DialogSmokeTarget.PLOT_DIALOGUE and isinstance(dialog, PlotDialogue):
        x_values: np.ndarray = np.array((0.0, 1.0, 2.0), dtype=float)
        assert dialog.set_line_series(
            x_values=x_values,
            series_names=("Line",),
            series_values=(np.array((1.0, 2.0, 1.0), dtype=float),),
            title="Line",
            x_axis_title="X",
            y_axis_title="Y",
        )
        assert dialog.set_cumulative_area_series(
            x_values=x_values,
            series_names=("Area A", "Area B"),
            series_values=(
                np.array((1.0, 1.0, 1.0), dtype=float),
                np.array((0.5, 0.75, 0.5), dtype=float),
            ),
            title="Area",
            x_axis_title="X",
            y_axis_title="Y",
        )
        assert dialog.set_polar_series(
            series_names=("Polar",),
            angle_values=(np.array((0.0, 1.0, 2.0), dtype=float),),
            radius_values=(np.array((1.0, 0.5, 1.0), dtype=float),),
            title="Polar",
            radius_title="Radius",
        )
        dialog.ui.actionResetView.trigger()
    elif target == DialogSmokeTarget.LOAD_DESIGNER and isinstance(dialog, LoadDesigner):
        dialog.update_results()
        original_series = tuple(dialog.ui.plotwidget._series)
        dialog.update_results()
        assert tuple(dialog.ui.plotwidget._series) == original_series
    elif target == DialogSmokeTarget.GRID_GENERATOR and isinstance(dialog, GridGeneratorGUI):
        dialog.ui.nodes_spinBox.setValue(12)
        dialog.preview()
        dialog.preview()
    elif target == DialogSmokeTarget.GRID_ANALYSIS and isinstance(dialog, GridAnalysisGUI):
        dialog.analyze_all()
    elif target == DialogSmokeTarget.PROCEDURAL_GRID and isinstance(dialog, ProceduralGridWindow):
        dialog.compute_candidates()
        engine: ProceduralGraphEngine = ProceduralGraphEngine(
            buses=dialog.app.circuit.buses,
            lines=dialog.app.circuit.lines,
        )
        dialog._draw_graph(engine=engine)
        original_series = tuple(dialog.ui.plotWidget._series)
        dialog._draw_graph(engine=engine)
        assert tuple(dialog.ui.plotWidget._series) == original_series
    elif target == DialogSmokeTarget.GENERATOR_Q_CURVE_EDITOR and isinstance(dialog, GeneratorQCurveEditor):
        dialog.q_curve_widget.add_row()
        dialog.q_curve_widget.add_row()
    elif target == DialogSmokeTarget.GENERATOR_EDITOR and isinstance(dialog, GeneratorEditor):
        dialog.qcurve_editor_widget.add_row()
        dialog.qcurve_editor_widget.add_row()
    elif target == DialogSmokeTarget.SIGMA_ANALYSIS and isinstance(dialog, SigmaAnalysisGUI):
        dialog.rerun_sigma_analysis()
        original_series = tuple(dialog.ui.plotwidget._series)
        dialog.rerun_sigma_analysis()
        assert len(original_series) == 3
        assert tuple(dialog.ui.plotwidget._series) == original_series
    else:
        pass
    app.processEvents()


def run_dialog_smoke_suite_in_child(message_queue: Any) -> None:
    """
    Run the full dialog smoke inventory in a disposable child process.

    :param message_queue: Parent-visible queue receiving failure details.
    :return: None.
    """
    app: QtWidgets.QApplication | None = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication(list(("dialog-smoke",)))
    else:
        pass

    chart_targets: Set[DialogSmokeTarget] = set()
    chart_targets.add(DialogSmokeTarget.GRID_ANALYSIS)
    chart_targets.add(DialogSmokeTarget.SOLAR_PV_WIZARD)
    chart_targets.add(DialogSmokeTarget.WIND_FARM_WIZARD)
    chart_targets.add(DialogSmokeTarget.GENERATOR_EDITOR)
    chart_targets.add(DialogSmokeTarget.GENERATOR_Q_CURVE_EDITOR)
    chart_targets.add(DialogSmokeTarget.LOAD_DESIGNER)
    chart_targets.add(DialogSmokeTarget.PLOT_DIALOGUE)
    chart_targets.add(DialogSmokeTarget.TOWER_BUILDER)
    chart_targets.add(DialogSmokeTarget.UNDERGROUND_CABLE_BUILDER)
    chart_targets.add(DialogSmokeTarget.GRID_GENERATOR)
    chart_targets.add(DialogSmokeTarget.PROCEDURAL_GRID)
    chart_targets.add(DialogSmokeTarget.SIGMA_ANALYSIS)
    chart_targets.add(DialogSmokeTarget.RMS_PLOT)
    chart_targets.add(DialogSmokeTarget.PROFILE_INPUT)
    chart_targets.add(DialogSmokeTarget.TEMPLATE_DEVICE_EDITOR)
    chart_targets.add(DialogSmokeTarget.SEQUENCE_EDITOR)
    chart_targets.add(DialogSmokeTarget.LOOKUP_MATRIX_EDITOR)

    target: DialogSmokeTarget
    for target in DialogSmokeTarget:
        context: DialogSmokeContext = DialogSmokeContext(app=app)
        dialog: QtWidgets.QWidget | None = None
        message_queue.put(target.value)

        try:
            dialog = build_dialog_for_smoke(target=target, context=context)
            dialog.show()
            app.processEvents()
            assert shiboken6.isValid(dialog)
            if target in chart_targets:
                exercise_chart_window_operation_for_smoke(target=target, dialog=dialog, app=app)
                assert len(dialog.findChildren(GraphsWidget)) > 0
                exercise_chart_widgets_for_smoke(dialog=dialog, app=app)
            else:
                pass
        except Exception:
            message_queue.put(f"{target.value}\n{traceback.format_exc()}")
            raise
        finally:
            if dialog is None:
                pass
            else:
                close_dialog_for_smoke(dialog=dialog, app=app)

        active_modal_widget: QtWidgets.QWidget | None = app.activeModalWidget()
        if active_modal_widget is None:
            pass
        else:
            message_queue.put(f"{target.value}\nleft active modal widget: {active_modal_widget}")
            raise AssertionError(f"{target.value} left active modal widget")


def run_dialog_smoke_suite_subprocess(timeout_s: float) -> None:
    """
    Run dialog smoke coverage outside the parent pytest Qt process.

    :param timeout_s: Maximum interval without child-process progress in seconds.
    :return: None.
    """
    process_context: multiprocessing.context.BaseContext = multiprocessing.get_context("spawn")
    message_queue: Any = process_context.Queue()
    process: multiprocessing.Process = process_context.Process(
        target=run_dialog_smoke_suite_in_child,
        args=(message_queue,),
    )

    process.start()
    message: str = ""

    # Treat each queued dialog name as a watchdog heartbeat. The complete
    # inventory can legitimately exceed one fixed wall-clock budget on slower
    # machines, while a genuinely blocked constructor or close operation stops
    # producing these progress messages.
    last_progress_time_s: float = time.monotonic()
    while process.is_alive() and time.monotonic() - last_progress_time_s <= timeout_s:
        try:
            queued_message: object = message_queue.get(timeout=1.0)
            if isinstance(queued_message, str):
                message = queued_message
            else:
                message = repr(queued_message)
            last_progress_time_s = time.monotonic()
        except queue.Empty:
            pass

    if process.is_alive():
        process.terminate()
        process.join(10.0)
        raise AssertionError(f"Dialog smoke subprocess made no progress for {timeout_s} seconds: {message}")
    else:
        process.join(10.0)

    # Capture any final diagnostic that the child queued immediately before it
    # exited so construction failures still report their traceback.
    try:
        while True:
            queued_message = message_queue.get_nowait()
            if isinstance(queued_message, str):
                message = queued_message
            else:
                message = repr(queued_message)
    except queue.Empty:
        pass

    assert process.exitcode == 0, message


def get_smoked_dialog_class_names() -> Set[str]:
    """
    Return class names covered by the smoke test.

    :return: Covered class names.
    """
    names: Set[str] = set()
    target: DialogSmokeTarget
    for target in DialogSmokeTarget:
        names.add(target.value)
    return names


def get_deferred_dialog_class_names() -> Set[str]:
    """
    Return base classes and dialogs covered by dedicated GUI fixtures.

    :return: Deferred class names.
    """
    names: Set[str] = set()
    names.add("BaseMainGui")
    names.add("CenteredDialog")
    names.add("CandidateInvestmentsWindow")
    names.add("ManufacturerNativeImporterDialog")
    return names


def discover_qt_dialog_class_names() -> Set[str]:
    """
    Discover dialog/window classes declared under ``VeraGrid.Gui``.

    :return: Class names backed by QDialog/QMainWindow/CenteredDialog.
    """
    tests_root: Path = Path(__file__).resolve().parents[1]
    gui_root: Path = tests_root.parent / "VeraGrid" / "Gui"
    class_names: Set[str] = set()
    path: Path
    for path in gui_root.rglob("*.py"):
        tree: ast.Module = ast.parse(path.read_text(encoding="utf-8"))
        node: ast.stmt
        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                bases: List[str] = list()
                base: ast.expr
                for base in node.bases:
                    bases.append(ast.unparse(base))
                if ("QDialog" in bases) or ("QMainWindow" in bases) or ("QtWidgets.QDialog" in bases):
                    class_names.add(node.name)
                elif ("CenteredDialog" in bases) or ("QtWidgets.QMainWindow" in bases):
                    class_names.add(node.name)
                else:
                    pass
            else:
                pass
    return class_names


def test_dialog_opens_and_closes_without_blowing_up() -> None:
    """
    Smoke open and close each stable GUI dialog in an isolated process.

    :return: None.
    """
    run_dialog_smoke_suite_subprocess(timeout_s=120.0)


def test_logs_dialogue_expands_first_column_and_colors_severity(qt_app: QtWidgets.QApplication) -> None:
    """
    Check the log tree keeps messages readable and severity-coded.

    :param qt_app: Shared Qt application fixture.
    :return: None.
    """
    logger: Logger = Logger()
    logger.add_error(msg="Error message", device="Line 1")
    logger.add_warning(msg="Warning message", device="Bus 2")
    logger.add_info(msg="Info message", device="Bus 3")
    logger.add_divergence(msg="Divergence message", device="Bus 4", value=1.0, expected_value=0.0)

    dialog: LogsDialogue = LogsDialogue(name="Log", logger=logger)
    try:
        header: QtWidgets.QHeaderView = dialog.logs_table.header()
        model: QtGui.QStandardItemModel = dialog.logs_table.model()
        error_item: QtGui.QStandardItem = model.item(0, 0)
        error_empty_item: QtGui.QStandardItem = model.item(0, 1)
        warning_item: QtGui.QStandardItem = model.item(1, 0)
        information_item: QtGui.QStandardItem = model.item(2, 0)
        divergence_item: QtGui.QStandardItem = model.item(3, 0)
        error_message_item: QtGui.QStandardItem = error_item.child(0, 0)
        error_message_empty_item: QtGui.QStandardItem = error_item.child(0, 1)
        error_child_item: QtGui.QStandardItem = error_message_item.child(0, 0)

        assert header.sectionResizeMode(0) == QtWidgets.QHeaderView.ResizeMode.Interactive
        assert dialog.logs_table.columnWidth(0) == 320
        assert dialog.logs_table.selectionMode() == QtWidgets.QAbstractItemView.SelectionMode.NoSelection
        assert dialog.logs_table.focusPolicy() == QtCore.Qt.FocusPolicy.NoFocus
        assert error_item.background().style() != QtCore.Qt.BrushStyle.NoBrush
        assert error_empty_item.background().style() != QtCore.Qt.BrushStyle.NoBrush
        assert error_item.background().color().name() == "#ff0000"
        assert error_item.foreground().color().name() == "#ffffff"
        assert error_message_item.background().style() == QtCore.Qt.BrushStyle.NoBrush
        assert error_message_empty_item.background().style() == QtCore.Qt.BrushStyle.NoBrush
        assert error_child_item.background().style() == QtCore.Qt.BrushStyle.NoBrush
        assert error_message_item.foreground().style() == QtCore.Qt.BrushStyle.NoBrush
        assert error_child_item.foreground().style() == QtCore.Qt.BrushStyle.NoBrush
        assert warning_item.background().color().name() == "#ff9900"
        assert information_item.background().color().name() == "#808080"
        assert divergence_item.background().color().name() == "#00aa00"

        dialog.show()
        dialog.accept_btn.setFocus()
        qt_app.processEvents()

        error_empty_index: QtCore.QModelIndex = model.index(0, 1)
        error_empty_point: QtCore.QPoint = dialog.logs_table.visualRect(error_empty_index).center()
        viewport_image: QtGui.QImage = dialog.logs_table.viewport().grab().toImage()
        assert viewport_image.pixelColor(1, error_empty_point.y()).name() == "#ff0000"

        dialog.logs_table.setStyleSheet("QTreeView::item:!selected:hover { background: rgb(64, 65, 67); }")
        QtTest.QTest.mouseMove(dialog.logs_table.viewport(), error_empty_point)
        qt_app.processEvents()

        viewport_image = dialog.logs_table.viewport().grab().toImage()
        assert viewport_image.pixelColor(error_empty_point).name() == "#ff0000"

        row_idx: int
        for row_idx in range(model.rowCount()):
            column_idx: int
            for column_idx in range(model.columnCount()):
                group_item: QtGui.QStandardItem = model.item(row_idx, column_idx)
                assert group_item.foreground().color().name() == "#ffffff"
                assert group_item.background().style() != QtCore.Qt.BrushStyle.NoBrush

            parent_item: QtGui.QStandardItem = model.item(row_idx, 0)
            message_idx: int
            for message_idx in range(parent_item.rowCount()):
                for column_idx in range(model.columnCount()):
                    message_item: QtGui.QStandardItem = parent_item.child(message_idx, column_idx)
                    assert message_item.foreground().style() == QtCore.Qt.BrushStyle.NoBrush
                    assert message_item.background().style() == QtCore.Qt.BrushStyle.NoBrush
    finally:
        close_dialog_for_smoke(dialog=dialog, app=qt_app)


def test_dialog_smoke_inventory_is_explicit() -> None:
    """
    Keep the smoke target list aligned with real dialog/window classes.

    :return: None.
    """
    known_names: Set[str] = get_smoked_dialog_class_names()
    known_names.update(get_deferred_dialog_class_names())
    missing_names: Set[str] = discover_qt_dialog_class_names() - known_names

    assert sorted(missing_names) == list()


def test_measurements_dialog_tree_io_column_composes_reference_directions(qt_app: QtWidgets.QApplication) -> None:
    """
    Check that the I/O tree column composes input and output reference lists.

    :param qt_app: Shared Qt application fixture.
    :return: None.
    """
    app: QtWidgets.QApplication = qt_app
    bus: vge.Bus = vge.Bus(name="Bus 1", Vnom=110.0)
    references: List[VarPowerFlowReferenceType] = list()
    references.append(VarPowerFlowReferenceType.Vm)
    references.append(VarPowerFlowReferenceType.Va)
    ac_measurements: Dict[BlockType, List[VarPowerFlowReferenceType]] = dict()
    ac_measurements[BlockType.MEASUREMENTS_VOLTAGE_ANGLE] = references
    power_references: List[VarPowerFlowReferenceType] = list()
    power_references.append(VarPowerFlowReferenceType.P)
    power_references.append(VarPowerFlowReferenceType.Q)
    ac_measurements[BlockType.MEASUREMENTS_P_Q] = power_references
    measurements: Dict[str, Dict[BlockType, List[VarPowerFlowReferenceType]]] = dict()
    measurements["a_c_bus"] = ac_measurements
    dialog: MeasurementsDialog = MeasurementsDialog(
        buses=list((bus,)),
        measurement_vars_dict=measurements,
        initial_bus=bus,
    )

    try:
        parent_item: QtWidgets.QTreeWidgetItem = dialog.ui.measurement_tree.topLevelItem(0)
        child_item: QtWidgets.QTreeWidgetItem = parent_item.child(0)
        sibling_parent_item: QtWidgets.QTreeWidgetItem = dialog.ui.measurement_tree.topLevelItem(1)
        sibling_child_item: QtWidgets.QTreeWidgetItem = sibling_parent_item.child(0)
        reference_data: object = child_item.data(0, QtCore.Qt.ItemDataRole.UserRole)
        assert isinstance(reference_data, VarPowerFlowReferenceType)
        assert dialog.ui.measurement_tree.columnCount() == 3
        assert dialog.ui.measurement_tree.headerItem().text(0) == "Name"
        assert dialog.ui.measurement_tree.headerItem().text(1) == "I/O"
        assert dialog.ui.measurement_tree.headerItem().text(2) == "Comment"
        assert parent_item.text(2) == "Direct bus voltage state references."
        assert child_item.text(2) == "Output-only bus voltage magnitude in p.u."
        assert sibling_parent_item.text(2) == "Direct active and reactive power references."
        assert sibling_child_item.text(2) == "Input-only active power injection in p.u."
        assert not bool(child_item.flags() & QtCore.Qt.ItemFlag.ItemIsUserCheckable)
        assert not bool(sibling_child_item.flags() & QtCore.Qt.ItemFlag.ItemIsUserCheckable)
        tree_header: QtWidgets.QHeaderView = dialog.ui.measurement_tree.header()
        assert not tree_header.stretchLastSection()
        assert (
            tree_header.sectionResizeMode(0)
            == QtWidgets.QHeaderView.ResizeMode.Interactive
        )
        assert (
            tree_header.sectionResizeMode(1)
            == QtWidgets.QHeaderView.ResizeMode.Interactive
        )
        assert (
            tree_header.sectionResizeMode(2)
            == QtWidgets.QHeaderView.ResizeMode.Interactive
        )

        parent_item.setCheckState(0, QtCore.Qt.CheckState.Checked)
        assert child_item.checkState(1) == QtCore.Qt.CheckState.Unchecked
        assert parent_item.child(1).checkState(1) == QtCore.Qt.CheckState.Unchecked
        assert sibling_parent_item.checkState(0) == QtCore.Qt.CheckState.Unchecked
        assert sibling_child_item.checkState(1) == QtCore.Qt.CheckState.Unchecked

        selected_bus: vge.Bus
        selected_block_type: BlockType
        input_references: List[VarPowerFlowReferenceType]
        output_references: List[VarPowerFlowReferenceType]
        selected_bus, selected_block_type, input_references, output_references = dialog.get_user_info()
        assert selected_bus is bus
        assert selected_block_type is BlockType.MEASUREMENTS_VOLTAGE_ANGLE
        assert input_references == list()
        assert output_references == references
        assert child_item.text(1) == "Output"

        sibling_parent_item.setCheckState(0, QtCore.Qt.CheckState.Checked)
        assert child_item.checkState(1) == QtCore.Qt.CheckState.Unchecked
        assert sibling_child_item.checkState(1) == QtCore.Qt.CheckState.Checked
        assert sibling_parent_item.child(1).checkState(1) == QtCore.Qt.CheckState.Checked
        selected_bus, selected_block_type, input_references, output_references = dialog.get_user_info()
        assert selected_block_type is BlockType.MEASUREMENTS_VOLTAGE_ANGLE
        assert input_references == power_references
        assert output_references == references
        assert sibling_child_item.text(1) == "Input"

        parent_item.setCheckState(0, QtCore.Qt.CheckState.Unchecked)
        assert child_item.checkState(1) == QtCore.Qt.CheckState.Unchecked
        assert parent_item.child(1).checkState(1) == QtCore.Qt.CheckState.Unchecked
        assert sibling_parent_item.checkState(0) == QtCore.Qt.CheckState.Checked
        assert sibling_child_item.checkState(1) == QtCore.Qt.CheckState.Checked
        selected_bus, selected_block_type, input_references, output_references = dialog.get_user_info()
        assert selected_block_type is BlockType.MEASUREMENTS_P_Q
        assert input_references == power_references
        assert output_references == list()
        assert child_item.text(1) == "Output"
    finally:
        delete_dialog_safely(dialog=dialog)
        app.processEvents()


def test_delete_dialog_safely_deletes_child_widgets(qt_app: QtWidgets.QApplication) -> None:
    """
    Check that dialog lifecycle cleanup invalidates child widget wrappers.

    :param qt_app: Shared Qt application fixture.
    :return: None.
    """
    app: QtWidgets.QApplication = qt_app
    dialog: QtWidgets.QDialog = QtWidgets.QDialog()
    layout: QtWidgets.QVBoxLayout = QtWidgets.QVBoxLayout(dialog)
    child_widget: QtWidgets.QWidget = QtWidgets.QWidget(dialog)
    nested_widget: QtWidgets.QPushButton = QtWidgets.QPushButton(child_widget)
    child_layout: QtWidgets.QVBoxLayout = QtWidgets.QVBoxLayout(child_widget)

    child_layout.addWidget(nested_widget)
    layout.addWidget(child_widget)
    dialog.show()
    app.processEvents()

    delete_dialog_safely(dialog=dialog)
    QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.Type.DeferredDelete)
    app.processEvents()

    assert not shiboken6.isValid(nested_widget)
    assert not shiboken6.isValid(child_widget)
    assert not shiboken6.isValid(dialog)


def test_validation_dialogue_releases_each_modal_instance(
        qt_app: QtWidgets.QApplication) -> None:
    """Validation modals must not retain Qt objects across repeated runs.

    :param qt_app: Shared Qt application fixture.
    :return: None.
    """
    app: QtWidgets.QApplication = qt_app
    owner_dialog: QtWidgets.QDialog = QtWidgets.QDialog()
    dialog_index: int
    for dialog_index in range(3):
        _unused_dialog_index: int = dialog_index
        dialog: ValidationSectionDialog = ValidationSectionDialog(
            section_results=list(),
            parent=owner_dialog,
        )
        table_model: QtGui.QStandardItemModel = dialog._table_model
        results_table: QtWidgets.QTableView = dialog._ui.resultsTableView

        # Close the modal from its own event loop, then deliver the deferred
        # deletion posted by the shared dialogue lifecycle helper.
        QtCore.QTimer.singleShot(0, dialog.accept)
        dialog_result: int = exec_dialog_safely(dialog=dialog)
        QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.Type.DeferredDelete)
        app.processEvents()

        assert dialog_result == QtWidgets.QDialog.DialogCode.Accepted
        assert not shiboken6.isValid(results_table)
        assert not shiboken6.isValid(table_model)
        assert not shiboken6.isValid(dialog)
        assert owner_dialog.findChildren(ValidationSectionDialog) == list()

    delete_dialog_safely(dialog=owner_dialog)
    QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.Type.DeferredDelete)
    app.processEvents()
    assert not shiboken6.isValid(owner_dialog)


def test_validation_dialogue_preserves_uuid_block_identity(
        qt_app: QtWidgets.QApplication) -> None:
    """Store and emit a 128-bit block UID without QVariant integer overflow.

    :param qt_app: Shared Qt application fixture.
    :return: None.
    """
    _unused_application: QtWidgets.QApplication = qt_app
    block_uid: int = (1 << 127) + 12345
    block: Block = Block(name="UUID block", uid=block_uid)
    section: ValidationSection = ValidationSection(title="Identity check")
    add_validation_detail(section=section, block=block, detail="Example issue")
    dialog: ValidationSectionDialog = ValidationSectionDialog(
        section_results=list((section,)),
    )

    # Qt item data receives a decimal string because QVariant cannot represent
    # the complete UUID-v4 integer range used by symbolic blocks.
    result_index: QtCore.QModelIndex = dialog._table_model.index(0, 0)
    stored_uid: object = result_index.data(QtCore.Qt.ItemDataRole.UserRole)
    assert stored_uid == str(block_uid)

    signal_spy: QtTest.QSignalSpy = QtTest.QSignalSpy(dialog.issueSelected)
    dialog._show_selected_issue_in_model(index=result_index)
    assert signal_spy.count() == 1
    emitted_arguments: list[object] = signal_spy.at(0)
    assert emitted_arguments[0] == block_uid
    dialog.close()


def test_grid_reduce_accepts_before_log_display(qt_app: QtWidgets.QApplication, monkeypatch: Any) -> None:
    """
    Keep logged reductions from blocking the reducer dialog result.

    :param qt_app: Shared Qt application fixture.
    :param monkeypatch: Pytest monkeypatch fixture.
    :return: None.
    """
    app: QtWidgets.QApplication = qt_app
    circuit: vge.MultiCircuit = build_smoke_circuit()
    selected_buses: Set[vge.Bus] = {circuit.buses[0]}
    dialog: GridReduceDialogue = GridReduceDialogue(
        grid=circuit,
        session=SimulationSession(),
        selected_buses_set=selected_buses
    )
    accepted_result: int = int(QtWidgets.QDialog.DialogCode.Accepted)

    monkeypatch.setattr(grid_reduce_module, "yes_no_question", accept_grid_reduction_question)
    monkeypatch.setattr(grid_reduce_module, "ptdf_reduction", fake_logged_ptdf_reduction)

    try:
        QtCore.QTimer.singleShot(0, dialog.reduce_grid)
        result: int = int(dialog.exec())
        app.processEvents()

        assert result == accepted_result
        assert dialog.result() == accepted_result
        assert dialog.did_reduce is True
        deleted_bus_names: List[str] = [bus.name for bus in dialog.deleted_buses]
        assert "Bus 2" in deleted_bus_names
        assert circuit.get_bus_number() > 1
        assert dialog.reduced_grid is not None
        assert dialog.reduced_grid.get_bus_number() == 1
    finally:
        delete_dialog_safely(dialog=dialog)


def test_grid_reduce_failure_does_not_mutate_live_grid(qt_app: QtWidgets.QApplication, monkeypatch: Any) -> None:
    """
    Keep PTDF failures from deleting buses in the live circuit.

    :param qt_app: Shared Qt application fixture.
    :param monkeypatch: Pytest monkeypatch fixture.
    :return: None.
    """
    app: QtWidgets.QApplication = qt_app
    circuit: vge.MultiCircuit = build_smoke_circuit()
    selected_bus: vge.Bus = circuit.buses[0]
    original_bus_number: int = circuit.get_bus_number()
    dialog: GridReduceDialogue = GridReduceDialogue(
        grid=circuit,
        session=SimulationSession(),
        selected_buses_set={selected_bus}
    )
    rejected_result: int = int(QtWidgets.QDialog.DialogCode.Rejected)

    monkeypatch.setattr(grid_reduce_module, "yes_no_question", accept_grid_reduction_question)
    monkeypatch.setattr(grid_reduce_module, "ptdf_reduction", fake_failing_ptdf_reduction)

    try:
        QtCore.QTimer.singleShot(0, dialog.reduce_grid)
        result: int = int(dialog.exec())
        app.processEvents()

        assert result == rejected_result
        assert dialog.did_reduce is False
        assert dialog.reduced_grid is None
        assert circuit.get_bus_number() == original_bus_number
        assert selected_bus in circuit.buses
        assert dialog.logger.has_logs()
    finally:
        delete_dialog_safely(dialog=dialog)


def test_grid_reduction_cleanup_removes_indirect_dead_graphics(qt_app: QtWidgets.QApplication) -> None:
    """
    Remove graphics for branch objects deleted as side effects of grid reduction.

    :param qt_app: Shared Qt application fixture.
    :return: None.
    """
    app: QtWidgets.QApplication = qt_app
    circuit: vge.MultiCircuit = build_smoke_circuit()
    line: vge.Line = circuit.lines[0]
    fake_main: FakeReductionMain = FakeReductionMain(circuit=circuit)
    fake_diagram: FakeReductionDiagram = FakeReductionDiagram()
    graphic: FakeQtGraphic = FakeQtGraphic(api_object=line)

    fake_diagram.graphics_manager.add_device(elm=line, graphic=graphic)
    circuit.delete_line(obj=line)

    DiagramsMain.remove_dead_graphics_from_diagram(fake_main, diagram_widget=fake_diagram)
    app.processEvents()

    assert fake_diagram.graphics_manager.query(elm=line) is None
    assert fake_diagram.removed_graphics == [graphic]


def test_schematic_selected_buses_skip_stale_graphics(monkeypatch: Any) -> None:
    """
    Keep grid-reduction launch from crashing on a stale selected bus graphic.

    :param monkeypatch: Pytest monkeypatch fixture.
    :return: None.
    """
    circuit: vge.MultiCircuit = build_smoke_circuit()
    stale_bus: vge.Bus = circuit.buses[0]
    fake_app: FakeReductionMain = FakeReductionMain(circuit=circuit)
    widget: schematic_widget_module.SchematicWidget = schematic_widget_module.SchematicWidget.__new__(
        schematic_widget_module.SchematicWidget
    )
    widget.gui = fake_app
    widget.graphics_manager = GraphicsManager()
    widget.graphics_manager.add_device(elm=stale_bus, graphic=FakeSelectedBusGraphic(api_object=stale_bus))

    monkeypatch.setattr(schematic_widget_module, "BusGraphicItem", FakeSelectedBusGraphic)
    circuit.delete_bus(obj=stale_bus, delete_associated=True)

    selected_buses: List[tuple[int, vge.Bus, FakeSelectedBusGraphic]] = widget.get_selected_buses()

    assert selected_buses == list()


def test_selected_diagram_uses_current_index_when_selection_is_empty() -> None:
    """
    Keep menu actions working when the diagrams list has a current row but no selected row.

    :return: None.
    """
    model: QtGui.QStandardItemModel = QtGui.QStandardItemModel()
    model.appendRow(QtGui.QStandardItem("Diagram"))
    current_index: QtCore.QModelIndex = model.index(0, 0)
    fake_main: FakeDiagramMain = FakeDiagramMain(current_index=current_index)
    selected_diagram: object | None = DiagramsMain.get_selected_diagram_widget(fake_main)

    assert selected_diagram is fake_main.diagram_widgets_list[0]


def test_modeless_export_dialogues_reuse_live_windows(qt_app: QtWidgets.QApplication) -> None:
    """
    Check that repeated export actions do not orphan live modeless dialogs.

    :param qt_app: Shared Qt application fixture.
    :return: None.
    """
    app: QtWidgets.QApplication = qt_app
    # Exercise the real export actions without starting unrelated maps or user settings.
    gui: FakeIoApp = FakeIoApp(circuit=vge.MultiCircuit())

    try:
        IoMain.export_psse(gui)
        app.processEvents()
        psse_dialog: PsseExportDialogue | None = gui.psse_export_dialogue
        assert is_dialog_available(dialog=psse_dialog)
        IoMain.export_psse(gui)
        app.processEvents()
        assert gui.psse_export_dialogue is psse_dialog

        IoMain.export_power_factory(gui)
        app.processEvents()
        dgs_dialog: DgsExportDialogue | None = gui.dgs_export_dialogue
        assert is_dialog_available(dialog=dgs_dialog)
        IoMain.export_power_factory(gui)
        app.processEvents()
        assert gui.dgs_export_dialogue is dgs_dialog

        IoMain.export_matpower(gui)
        app.processEvents()
        matpower_dialog: MatpowerExportDialogue | None = gui.matpower_export_dialogue
        assert is_dialog_available(dialog=matpower_dialog)
        IoMain.export_matpower(gui)
        app.processEvents()
        assert gui.matpower_export_dialogue is matpower_dialog

        IoMain.export_ucte(gui)
        app.processEvents()
        ucte_dialog: UcteExportDialogue | None = gui.ucte_export_dialogue
        assert is_dialog_available(dialog=ucte_dialog)
        IoMain.export_ucte(gui)
        app.processEvents()
        assert gui.ucte_export_dialogue is ucte_dialog

        IoMain.export_cgmes(gui)
        app.processEvents()
        cgmes_dialog: CgmesExportDialogue | None = gui.cgmes_dialogue
        assert is_dialog_available(dialog=cgmes_dialog)
        IoMain.export_cgmes(gui)
        app.processEvents()
        assert gui.cgmes_dialogue is cgmes_dialog
    finally:
        if is_dialog_available(dialog=gui.psse_export_dialogue):
            close_dialog_for_smoke(dialog=gui.psse_export_dialogue, app=app, close_extra_widgets=False)
        else:
            pass
        if is_dialog_available(dialog=gui.dgs_export_dialogue):
            close_dialog_for_smoke(dialog=gui.dgs_export_dialogue, app=app, close_extra_widgets=False)
        else:
            pass
        if is_dialog_available(dialog=gui.matpower_export_dialogue):
            close_dialog_for_smoke(dialog=gui.matpower_export_dialogue, app=app, close_extra_widgets=False)
        else:
            pass
        if is_dialog_available(dialog=gui.ucte_export_dialogue):
            close_dialog_for_smoke(dialog=gui.ucte_export_dialogue, app=app, close_extra_widgets=False)
        else:
            pass
        if is_dialog_available(dialog=gui.cgmes_dialogue):
            close_dialog_for_smoke(dialog=gui.cgmes_dialogue, app=app, close_extra_widgets=False)
        else:
            pass
        collect_qt_deletes(app=app)
