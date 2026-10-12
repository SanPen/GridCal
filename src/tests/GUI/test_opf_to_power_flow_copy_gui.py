from __future__ import annotations

import multiprocessing
import queue
import time
import traceback
import faulthandler
from pathlib import Path
from typing import Any

from PySide6 import QtCore
from PySide6 import QtWidgets

from VeraGrid.Gui.Main.VeraGridMain import VeraGridMainGUI
from VeraGrid.Gui.dialog_lifecycle import delete_dialog_safely
from VeraGrid.Session.file_handler import FileOpenThread
from VeraGrid.Session.session import GcThread
from VeraGridEngine.enumerations import EngineType, SimulationTypes
from tests.GUI.conftest import ModalDialogAutoCloser


OPF_TO_PF_COPY_GRID: Path = Path(__file__).resolve().parents[1] / "data" / "grids" / "IEEE39_1W_batt.gridcal"


def wait_for_file_open(gui: VeraGridMainGUI,
                       app: QtWidgets.QApplication,
                       timeout_s: float,
                       expected_bus_count: int | None = None) -> None:
    """
    Process Qt events until the GUI file-open worker has finished.

    :param gui: Main GUI instance running the file-open worker.
    :param app: Shared Qt application.
    :param timeout_s: Maximum wait time in seconds.
    :param expected_bus_count: Optional bus count proving the requested grid is loaded.
    :return: None.
    """
    deadline_s: float = time.monotonic() + timeout_s
    open_finished: bool = False

    while time.monotonic() < deadline_s and not open_finished:
        app.processEvents()
        open_thread: FileOpenThread | None = gui.open_file_thread_object
        expected_grid_loaded: bool = (
            expected_bus_count is None
            or gui.circuit.get_bus_number() == expected_bus_count
        )

        if open_thread is None:
            if expected_grid_loaded:
                open_finished = True
            else:
                time.sleep(0.01)
        elif open_thread.isRunning():
            time.sleep(0.01)
        elif SimulationTypes.FileOpen in gui.stuff_running_now:
            time.sleep(0.01)
        elif expected_grid_loaded:
            open_thread.wait(5000)
            open_finished = True
        else:
            time.sleep(0.01)

    assert open_finished


def wait_for_simulation(gui: VeraGridMainGUI,
                        app: QtWidgets.QApplication,
                        simulation_type: SimulationTypes,
                        timeout_s: float) -> None:
    """
    Process Qt events until one GUI simulation worker has finished.

    :param gui: Main GUI instance running the simulation worker.
    :param app: Shared Qt application.
    :param simulation_type: Simulation type to wait for.
    :param timeout_s: Maximum wait time in seconds.
    :return: None.
    """
    deadline_s: float = time.monotonic() + timeout_s
    simulation_finished: bool = False

    while time.monotonic() < deadline_s and not simulation_finished:
        app.processEvents()
        simulation_thread: GcThread | None = gui.session.threads.get(simulation_type, None)

        if simulation_thread is None:
            simulation_finished = True
        elif simulation_thread.isRunning():
            time.sleep(0.01)
        elif simulation_type in gui.stuff_running_now:
            time.sleep(0.01)
        else:
            simulation_thread.wait(5000)
            simulation_finished = True

    assert simulation_finished


def select_gui_engine(gui: VeraGridMainGUI, engine: EngineType) -> None:
    """
    Select an engine through the GUI combo box.

    :param gui: Main GUI instance.
    :param engine: Engine to select.
    :return: None.
    """
    engine_index: int = gui.ui.engineComboBox.findData(engine)
    assert engine_index >= 0
    gui.ui.engineComboBox.setCurrentIndex(engine_index)


def run_opf_to_power_flow_copy_gui_flow(message_queue: Any) -> None:
    """
    Launch the GUI, run OPF on the battery grid, enable OPF-to-PF copy, and run PF.

    :param message_queue: Parent-visible queue receiving status and failure details.
    :return: None.
    """
    faulthandler.enable(all_threads=True)

    app: QtWidgets.QApplication | None = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication(list(("opf-to-power-flow-copy-regression",)))
    else:
        pass

    gui: VeraGridMainGUI = VeraGridMainGUI()
    gui.show()
    app.processEvents()
    modal_closer: ModalDialogAutoCloser = ModalDialogAutoCloser(app=app, protected_widget=gui, parent=gui)
    modal_closer.start()

    try:
        message_queue.put("opening file")
        gui.open_file_now(filenames=str(OPF_TO_PF_COPY_GRID))
        wait_for_file_open(gui=gui, app=app, timeout_s=60.0, expected_bus_count=39)
        message_queue.put("file opened")

        assert gui.circuit.get_bus_number() == 39
        assert gui.circuit.get_batteries_number() == 1

        select_gui_engine(gui=gui, engine=EngineType.VeraGrid)
        gui.ui.actionactivate_time_series.setChecked(False)
        app.processEvents()

        message_queue.put("running OPF")
        gui.ui.actionOPF.trigger()
        wait_for_simulation(gui=gui, app=app, simulation_type=SimulationTypes.OPF_run, timeout_s=180.0)
        message_queue.put("OPF finished")

        opf_driver, opf_results = gui.session.optimal_power_flow
        assert opf_driver is not None
        assert opf_results is not None
        assert opf_results.battery_power.shape == (1,)

        message_queue.put("running power flow with OPF copy")
        gui.ui.actionOpf_to_Power_flow.setChecked(True)
        gui.ui.actionPower_flow.trigger()
        wait_for_simulation(gui=gui, app=app, simulation_type=SimulationTypes.PowerFlow_run, timeout_s=180.0)
        message_queue.put("power flow finished")

        power_flow_driver, power_flow_results = gui.session.power_flow
        assert power_flow_driver is not None
        assert power_flow_results is not None
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


def test_opf_to_power_flow_copy_gui_flow_does_not_crash() -> None:
    """
    Reproduce OPF followed by power flow with the OPF-to-PF copy action enabled.

    :return: None.
    """
    process_context: multiprocessing.context.BaseContext = multiprocessing.get_context("spawn")
    message_queue: Any = process_context.Queue()
    process: multiprocessing.Process = process_context.Process(
        target=run_opf_to_power_flow_copy_gui_flow,
        args=(message_queue,),
    )

    process.start()
    process.join(360.0)

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
        raise AssertionError(f"OPF-to-power-flow copy GUI subprocess timed out: {message}")
    else:
        pass

    assert process.exitcode == 0, message
