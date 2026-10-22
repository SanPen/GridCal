from __future__ import annotations

import multiprocessing
import queue
import traceback
import faulthandler
from pathlib import Path
from typing import Any, List

import numpy as np
from PySide6 import QtCore
from PySide6 import QtWidgets

import VeraGridEngine.api as gce
from VeraGrid.Gui.Main.VeraGridMain import VeraGridMainGUI
from VeraGrid.Gui.dialog_lifecycle import delete_dialog_safely
from VeraGridEngine.enumerations import EngineType, SimulationTypes, SolverType
from tests.GUI.conftest import ModalDialogAutoCloser
from tests.GUI.test_opf_to_power_flow_copy_gui import wait_for_file_open, wait_for_simulation, select_gui_engine
from tests.NTC.test_ntc import get_grid_path


def select_transfer_areas(gui: VeraGridMainGUI) -> None:
    """
    Check the first area as the sending one and the second as the receiving one in the NTC lists.

    :param gui: Main GUI instance.
    :return: None.
    """
    view: QtWidgets.QListView
    row: int
    for view, row in ((gui.ui.fromListView, 0), (gui.ui.toListView, 1)):
        r: int
        for r in range(view.model().rowCount()):
            if r == row:
                view.model().item(r).setCheckState(QtCore.Qt.CheckState.Checked)
            else:
                view.model().item(r).setCheckState(QtCore.Qt.CheckState.Unchecked)


class SelectionDialogAnswerer(QtCore.QObject):
    """
    Answer the next item selection dialog with a given item, recording what it offered.
    """

    __slots__ = ("_app", "_item", "_timer", "offered", "answered")

    def __init__(self, app: QtWidgets.QApplication, item: str, parent: QtCore.QObject | None = None) -> None:
        """
        Build one selection dialog answerer.

        :param app: Shared Qt application.
        :param item: Item to select in the dialog.
        :param parent: Optional Qt owner.
        :return: None.
        """
        QtCore.QObject.__init__(self, parent)
        self._app: QtWidgets.QApplication = app
        self._item: str = item
        self.offered: List[str] = list()
        self.answered: bool = False
        self._timer: QtCore.QTimer = QtCore.QTimer(self)
        self._timer.setInterval(25)
        self._timer.timeout.connect(self.answer)

    def start(self) -> None:
        """
        Start polling for the selection dialog.

        :return: None.
        """
        self._timer.start()

    def stop(self) -> None:
        """
        Stop polling for the selection dialog.

        :return: None.
        """
        self._timer.stop()

    @QtCore.Slot()
    def answer(self) -> None:
        """
        Select the item in the open selection dialog, if any, and accept it.

        :return: None.
        """
        dialog: QtWidgets.QWidget | None = self._app.activeModalWidget()
        if isinstance(dialog, QtWidgets.QInputDialog):
            self.offered = list(dialog.comboBoxItems())
            dialog.setTextValue(self._item)
            dialog.accept()
            self.answered = True
            self._timer.stop()
        else:
            pass  # no selection dialog open yet


def run_ntc_to_power_flow_gui_flow(grid_path: str, bus_count: int, message_queue: Any) -> None:
    """
    Launch the GUI and check that the "OPF results to power flow" option makes a linear power flow
    show the NTC flows: in the snapshot, picking the NTC results in the dialog offered when the OPF
    results are also computed, and in the time series, where only the NTC results are computed.

    :param grid_path: grid with two areas and a four step time profile.
    :param bus_count: number of buses of that grid, which proves it is loaded.
    :param message_queue: Parent-visible queue receiving status and failure details.
    :return: None.
    """
    faulthandler.enable(all_threads=True)

    app: QtWidgets.QApplication | None = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication(list(("ntc-to-power-flow-regression",)))
    else:
        pass

    gui: VeraGridMainGUI = VeraGridMainGUI()
    gui.show()
    app.processEvents()
    modal_closer: ModalDialogAutoCloser = ModalDialogAutoCloser(app=app, protected_widget=gui, parent=gui)
    modal_closer.start()

    try:
        message_queue.put("opening file")
        gui.open_file_now(filenames=grid_path)
        wait_for_file_open(gui=gui, app=app, timeout_s=60.0, expected_bus_count=bus_count)
        message_queue.put("file opened")

        # NTC between the two areas, without generation limits or contingencies, and a linear power flow
        select_gui_engine(gui=gui, engine=EngineType.VeraGrid)
        select_transfer_areas(gui=gui)
        gui.ui.skipNtcGenerationLimitsCheckBox.setChecked(True)
        gui.ui.consider_ntc_contingencies_checkBox.setChecked(False)
        gui.ui.ntcSelectBasedOnExchangeSensitivityCheckBox.setChecked(False)
        gui.ui.solver_comboBox.setCurrentIndex(gui.ui.solver_comboBox.findData(SolverType.Linear))

        # snapshot: with the OPF and the NTC computed, the NTC results picked in the dialog set the power flow
        gui.ui.actionactivate_time_series.setChecked(False)
        message_queue.put("running the snapshot NTC")
        gui.ui.actionOptimal_Net_Transfer_Capacity.trigger()
        wait_for_simulation(gui=gui, app=app, simulation_type=SimulationTypes.OPF_NTC_run, timeout_s=180.0)
        ntc: gce.OptimalNetTransferCapacityResults | None
        _, ntc = gui.session.optimal_net_transfer_capacity
        assert ntc is not None
        message_queue.put("running the snapshot OPF")
        gui.ui.actionOPF.trigger()
        wait_for_simulation(gui=gui, app=app, simulation_type=SimulationTypes.OPF_run, timeout_s=180.0)
        assert gui.session.optimal_power_flow[1] is not None

        message_queue.put("running the snapshot power flow, picking the NTC results")
        answerer: SelectionDialogAnswerer = SelectionDialogAnswerer(app=app,
                                                                    item=SimulationTypes.OPF_NTC_run.value,
                                                                    parent=gui)
        modal_closer.stop()
        answerer.start()
        gui.ui.actionOpf_to_Power_flow.setChecked(True)
        gui.ui.actionPower_flow.trigger()
        wait_for_simulation(gui=gui, app=app, simulation_type=SimulationTypes.PowerFlow_run, timeout_s=180.0)
        answerer.stop()
        modal_closer.start()
        assert answerer.answered
        assert answerer.offered == [SimulationTypes.OPF_run.value, SimulationTypes.OPF_NTC_run.value]
        assert gui.ui.actionOpf_to_Power_flow.isChecked()
        power_flow: gce.PowerFlowResults | None
        _, power_flow = gui.session.power_flow
        assert power_flow is not None
        assert np.allclose(np.real(power_flow.Sf), np.real(np.asarray(ntc.Sf, dtype=complex)), atol=1e-3)

        # time series: only the NTC is computed, so its results set every step without asking
        gui.ui.actionactivate_time_series.setChecked(True)
        message_queue.put("running the NTC time series")
        gui.ui.actionOptimal_Net_Transfer_Capacity_Time_Series.trigger()
        wait_for_simulation(gui=gui, app=app,
                            simulation_type=SimulationTypes.OptimalNetTransferCapacityTimeSeries_run,
                            timeout_s=180.0)
        ntc_ts: gce.OptimalNetTransferCapacityTimeSeriesResults | None
        _, ntc_ts = gui.session.optimal_net_transfer_capacity_ts
        assert ntc_ts is not None

        message_queue.put("running the power flow time series with the NTC results")
        answerer = SelectionDialogAnswerer(app=app, item=SimulationTypes.OPF_NTC_run.value, parent=gui)
        modal_closer.stop()
        answerer.start()
        gui.ui.actionPower_Flow_Time_series.trigger()
        wait_for_simulation(gui=gui, app=app, simulation_type=SimulationTypes.PowerFlowTimeSeries_run,
                            timeout_s=180.0)
        power_flow_ts: gce.PowerFlowTimeSeriesResults | None
        answerer.stop()
        modal_closer.start()
        assert not answerer.answered
        _, power_flow_ts = gui.session.power_flow_ts
        assert power_flow_ts is not None
        assert np.allclose(np.real(power_flow_ts.Sf), np.real(np.asarray(ntc_ts.Sf, dtype=complex)), atol=1e-3)

        # cancelling the selection (the modal closer rejects the dialog) unchecks the option
        message_queue.put("running the snapshot power flow, cancelling the selection")
        gui.ui.actionactivate_time_series.setChecked(False)
        gui.ui.actionOpf_to_Power_flow.setChecked(True)
        gui.ui.actionPower_flow.trigger()
        wait_for_simulation(gui=gui, app=app, simulation_type=SimulationTypes.PowerFlow_run, timeout_s=180.0)
        assert not gui.ui.actionOpf_to_Power_flow.isChecked()
        message_queue.put("done")
    except Exception:
        message_queue.put(traceback.format_exc())
        raise
    finally:
        modal_closer.stop()
        gui.hide()
        gui.stop_all_threads()
        delete_dialog_safely(dialog=gui)
        QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.Type.DeferredDelete)
        app.processEvents()


def test_ntc_to_power_flow_gui_flow(tmp_path: Path) -> None:
    """
    The "OPF results to power flow" option sets the NTC results into the GUI power flow, snapshot and
    time series, asking which results to use when the OPF results are computed too.

    :param tmp_path: pytest temporary folder for the grid file.
    :return: None.
    """
    # IEEE14 with two areas, a controlled phase shifter, an HVDC line and four load steps
    grid: gce.MultiCircuit = gce.open_file(get_grid_path('IEEE14 - ntc areas_voltages_hvdc_shifter_l10free.gridcal'))
    grid.transformers2w[6].tap_phase_control_mode = gce.TapPhaseControl.Pf
    grid.create_profiles(steps=4, step_length=1, step_unit="h")
    load: gce.Load
    index: int
    for index, load in enumerate(grid.get_loads()):
        load.P_prof.set(load.P * np.array([0.8, 0.9, 1.0, 1.1]) * (1.0 + 0.05 * (index % 3)))
    grid_path: Path = tmp_path / "ieee14_ntc_ts.veragrid"
    gce.save_file(grid, str(grid_path))

    process_context: multiprocessing.context.BaseContext = multiprocessing.get_context("spawn")
    message_queue: Any = process_context.Queue()
    process: multiprocessing.Process = process_context.Process(
        target=run_ntc_to_power_flow_gui_flow,
        args=(str(grid_path), grid.get_bus_number(), message_queue),
    )

    process.start()
    process.join(600.0)

    message: str = ""
    try:
        while True:
            queued_message: object = message_queue.get_nowait()
            if isinstance(queued_message, str):
                message = queued_message
            else:
                message = repr(queued_message)
    except queue.Empty:
        pass

    if process.is_alive():
        process.terminate()
        process.join(10.0)
        raise AssertionError(f"NTC-to-power-flow GUI subprocess timed out: {message}")
    else:
        pass

    assert process.exitcode == 0, message
