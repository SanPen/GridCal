"""Exercise the map branch plot path and native deletion in a separate process."""

from __future__ import annotations

import faulthandler
import multiprocessing

import numpy as np
import pandas as pd
import shiboken6
from PySide6 import QtCore, QtGui, QtWidgets

from VeraGrid.Gui.Diagrams.MapWidget.Branches.map_line_container import MapLineContainer
from VeraGrid.Gui.Diagrams.base_diagram_widget import BaseDiagramWidget
from VeraGrid.Gui.Main.SubClasses.base_gui import BaseMainGui
from VeraGrid.Gui.PlotDialogue.plot_dialogue import PlotDialogue
from VeraGrid.Gui.PlotDialogue.qt_chart_widget import GraphsWidget
from VeraGridEngine.Devices.Branches.line import Line
from VeraGridEngine.Devices.Diagrams.map_diagram import MapDiagram
from VeraGridEngine.Devices.Substation.bus import Bus
from VeraGridEngine.Devices.multi_circuit import MultiCircuit
from VeraGridEngine.Simulations.results_table import ResultsTable
from VeraGridEngine.Simulations.results_template import ResultsTemplate
from VeraGridEngine.enumerations import DeviceType, ResultTypes, StudyResultsType


class BranchResults(ResultsTemplate):
    """Provide a branch result table and an explicit extraction-failure case."""

    __slots__ = ('fail',)

    def __init__(self) -> None:
        """Initialize the single available branch result.

        :return: None.
        """
        super().__init__('Power flow', [ResultTypes.BranchActivePowerFrom], None, None,
                         StudyResultsType.PowerFlowTimeSeries)
        self.fail: bool = False

    def mdl(self, result_type: ResultTypes) -> ResultsTable:
        """Return the branch table or simulate a failing results provider.

        :param result_type: Requested branch result type.
        :return: A finite time-series branch table.
        """
        if self.fail:
            raise ValueError('Result extraction failed')
        else:
            return ResultsTable(data=np.array([[1.0], [-2.0], [3.0]]), columns=np.array(['Line']),
                                index=pd.date_range('2026-01-01', periods=3), title='Branch power',
                                cols_device_type=DeviceType.LineDevice, idx_device_type=DeviceType.TimeDevice,
                                units='MW', xlabel='Time', ylabel='MW')


class BranchSession:
    """Expose the fixed results without starting any solver workers."""

    __slots__ = ('results',)

    def __init__(self) -> None:
        """Create results for the GUI extraction path.

        :return: None.
        """
        self.results: BranchResults = BranchResults()

    def drivers_results_iter(self) -> list[tuple[None, BranchResults]]:
        """Expose results using the session iteration protocol.

        :return: The single completed results source.
        """
        return [(None, self.results)]


class BranchPlotOwner(QtWidgets.QMainWindow):
    """Use the production plot registry without starting a complete main GUI."""

    __slots__ = ('circuit', 'session', '_open_plot_dialogs')

    def __init__(self) -> None:
        """Create a small real circuit and its time profiles.

        :return: None.
        """
        super().__init__()
        self.circuit: MultiCircuit = MultiCircuit()
        first_bus: Bus = Bus(name='From')
        second_bus: Bus = Bus(name='To')
        self.circuit.add_bus(first_bus)
        self.circuit.add_bus(second_bus)
        self.circuit.add_line(Line(bus_from=first_bus, bus_to=second_bus, name='Line'))
        self.circuit.time_profile = pd.date_range('2026-01-01', periods=3)
        self.circuit.ensure_profiles_exist()
        self.session: BranchSession = BranchSession()
        self._open_plot_dialogs: list[QtWidgets.QWidget] = list()

    def register_open_plot_dialog(self, dialog: QtWidgets.QWidget) -> None:
        """Exercise production registration on this minimal Qt owner.

        :param dialog: Newly created plot.
        :return: None.
        """
        BaseMainGui.register_open_plot_dialog(self, dialog)

    def _unregister_open_plot_dialog(self, dialog_obj: QtCore.QObject | None = None) -> None:
        """Exercise production destroyed-wrapper pruning.

        :param dialog_obj: Object reported by Qt destruction.
        :return: None.
        """
        BaseMainGui._unregister_open_plot_dialog(self, dialog_obj)


def run_map_line_plot_lifecycle() -> None:
    """Exercise menus, views, save pickers, failed creation and parent destruction.

    :return: None.
    """
    faulthandler.enable()
    app: QtWidgets.QApplication = QtWidgets.QApplication(list())
    owner: BranchPlotOwner = BranchPlotOwner()
    diagram: BaseDiagramWidget = BaseDiagramWidget(owner, MapDiagram(), QtGui.QStandardItemModel())
    graphic: MapLineContainer = MapLineContainer(diagram, owner.circuit.lines[0])
    scene: QtWidgets.QGraphicsScene = QtWidgets.QGraphicsScene(owner)
    scene.addItem(graphic)
    cycle: int
    for cycle in range(12):
        # Trigger the real map callback inside a menu's nested event loop.
        menu: QtWidgets.QMenu = QtWidgets.QMenu(owner)
        action: QtGui.QAction = menu.addAction('Plot profiles')
        action.triggered.connect(graphic.plot_profiles)
        QtCore.QTimer.singleShot(0, action.trigger)
        QtCore.QTimer.singleShot(0, menu.close)
        menu.exec(QtCore.QPoint())
        menu.deleteLater()
        app.processEvents()
        assert len(owner._open_plot_dialogs) == 1
        dialog: PlotDialogue = owner._open_plot_dialogs[0]
        chart: GraphsWidget = dialog.chart
        dialog.ui.actionAbs.trigger()
        dialog.ui.actionStacked_plot.trigger()
        dialog.ui.actionBar_plot.trigger()
        dialog.ui.actionAddPlot.trigger()
        dialog.save_image()
        picker: QtWidgets.QFileDialog = dialog._active_save_dialog
        assert picker is not None
        dialog.close()
        QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.Type.DeferredDelete)
        app.processEvents()
        assert not shiboken6.isValid(dialog)
        assert not shiboken6.isValid(chart)
        assert not shiboken6.isValid(picker)
        assert owner._open_plot_dialogs == list()
        assert owner.findChildren(PlotDialogue) == list()

    # Failed extraction must not leave an unregistered hidden window behind.
    owner.session.results.fail = True
    try:
        graphic.plot_profiles()
    except ValueError as error:
        assert str(error) == 'Result extraction failed'
    else:
        raise AssertionError('Expected extraction failure')
    QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.Type.DeferredDelete)
    assert owner.findChildren(PlotDialogue) == list()

    # Destroy the parent before the pending presentation callback is delivered.
    owner.session.results.fail = False
    graphic.plot_profiles()
    pending_dialog: QtWidgets.QWidget = owner._open_plot_dialogs[0]
    owner.deleteLater()
    QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.Type.DeferredDelete)
    app.processEvents()
    assert not shiboken6.isValid(pending_dialog)
    diagram.deleteLater()
    QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.Type.DeferredDelete)
    app.processEvents()


def test_map_line_plot_lifecycle_subprocess() -> None:
    """Distinguish native crashes from assertions using a fresh Qt process.

    :return: None.
    """
    context: multiprocessing.context.BaseContext = multiprocessing.get_context('spawn')
    process: multiprocessing.Process = context.Process(target=run_map_line_plot_lifecycle)
    process.start()
    process.join(45.0)
    if process.is_alive():
        process.terminate()
        process.join(5.0)
        raise AssertionError('Map plot lifecycle subprocess timed out')
    else:
        assert process.exitcode == 0, f'Map plot lifecycle process exited with {process.exitcode}'
