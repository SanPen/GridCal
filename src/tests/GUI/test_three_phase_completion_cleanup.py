from __future__ import annotations

import pytest

import VeraGridEngine.api as vge
from VeraGrid.Gui.Main.SubClasses.simulations import SimulationsMain
from VeraGrid.Session.session import GcThread, SimulationSession
from VeraGridEngine.basic_structures import Logger
from VeraGridEngine.enumerations import SimulationTypes


class _ProgressLabel:
    """
    Minimal progress-label stand-in for the three-phase post callback.
    """

    __slots__ = ("text",)

    def __init__(self) -> None:
        """
        Build the fake label.

        :return: None.
        """
        self.text: str = ""

    def setText(self, text: str) -> None:
        """
        Store the last progress text written by the callback.

        :param text: Progress text.
        :return: None.
        """
        self.text = text


class _Ui:
    """
    Minimal UI holder for the three-phase post callback.
    """

    __slots__ = ("progress_label",)

    def __init__(self) -> None:
        """
        Build the fake UI holder.

        :return: None.
        """
        self.progress_label: _ProgressLabel = _ProgressLabel()


class _Results:
    """
    Minimal power-flow results stand-in.
    """

    __slots__ = ("converged",)

    def __init__(self) -> None:
        """
        Build converged fake results.

        :return: None.
        """
        self.converged: bool = True


class _Session:
    """
    Minimal session stand-in for a completed three-phase worker.
    """

    __slots__ = ("results",)

    def __init__(self, results: _Results) -> None:
        """
        Build the fake session.

        :param results: Results returned by the session property.
        :return: None.
        """
        self.results: _Results = results

    @property
    def power_flow_3ph(self) -> tuple[None, _Results]:
        """
        Return the completed three-phase results.

        :return: Driver placeholder and results.
        """
        return None, self.results

    @property
    def short_circuit(self) -> tuple[None, _Results]:
        """
        Return the completed short-circuit results.

        :return: Driver placeholder and results.
        """
        return None, self.results

    def is_anything_running(self) -> bool:
        """
        Report that the worker has finished.

        :return: Always ``False``.
        """
        return False


class _Main:
    """
    Small object carrying only the state used by ``post_power_flow3ph``.
    """

    __slots__ = ("session", "stuff_running_now", "ui", "unlocked", "shown_logger")

    def __init__(self) -> None:
        """
        Build the fake main window state.

        :return: None.
        """
        self.session: _Session | SimulationSession = _Session(results=_Results())
        self.stuff_running_now: list[SimulationTypes] = list()
        self.stuff_running_now.append(SimulationTypes.PowerFlow3ph_run)
        self.ui: _Ui = _Ui()
        self.unlocked: bool = False
        self.shown_logger: Logger | None = None

    def show_logs(self, logger: Logger, name: str) -> None:
        """Capture the diagnostic selected for the user-facing error dialog.

        :param logger: Engine diagnostics retained by the failed worker.
        :param name: Dialog title.
        :return: None.
        """
        assert name == "Power flow 3ph failed"
        self.shown_logger = logger

    def remove_simulation(self, val: SimulationTypes) -> None:
        """
        Remove the finished simulation marker.

        :param val: Simulation type to remove.
        :return: None.
        """
        while val in self.stuff_running_now:
            self.stuff_running_now.remove(val)

    def update_available_results(self) -> None:
        """
        Simulate a GUI post-processing failure after the worker has finished.

        :return: None.
        """
        raise RuntimeError("post-processing failed")

    def colour_diagrams(self) -> None:
        """
        Stand in for diagram colouring.

        :return: None.
        """
        return None

    def show_info_toast(self, text: str) -> None:
        """
        Stand in for the success toast.

        :param text: Toast text.
        :return: None.
        """
        return None

    def show_warning_toast(self, text: str) -> None:
        """
        Stand in for the warning toast.

        :param text: Toast text.
        :return: None.
        """
        return None

    def sender(self) -> None:
        """
        Stand in for QObject.sender() when the callback is called directly.

        :return: No Qt sender.
        """
        return None

    def tr(self, text: str) -> str:
        """
        Return untranslated text.

        :param text: Source text.
        :return: Same text.
        """
        return text

    def UNLOCK(self) -> None:
        """
        Record that the post callback unlocked the GUI.

        :return: None.
        """
        self.unlocked = True


def test_three_phase_post_cleanup_runs_when_gui_post_processing_fails() -> None:
    """
    The completion callback must clear GUI busy state even if colouring fails.

    :return: None.
    """
    main: _Main = _Main()

    with pytest.raises(RuntimeError, match="post-processing failed"):
        SimulationsMain.post_power_flow3ph(main)

    assert main.stuff_running_now == list()
    assert main.unlocked


def test_short_circuit_post_cleanup_runs_when_gui_post_processing_fails() -> None:
    """
    The short-circuit callback must clear GUI busy state even if colouring fails.

    :return: None.
    """
    main: _Main = _Main()
    main.stuff_running_now.clear()
    main.stuff_running_now.append(SimulationTypes.ShortCircuit_run)

    with pytest.raises(RuntimeError, match="post-processing failed"):
        SimulationsMain.post_short_circuit(main)

    assert main.stuff_running_now == list()
    assert main.unlocked


@pytest.mark.parametrize("sequence", (0, 2))
@pytest.mark.parametrize("impedance", (0.0, 1e-20))
def test_three_phase_post_reports_invalid_generator_sequence(sequence: int, impedance: float) -> None:
    """Carry an actual Z0/Z2 failure through the worker to the GUI error log.

    :param sequence: Invalid generator impedance sequence.
    :param impedance: Zero or legacy missing-data placeholder.
    :return: None.
    """
    grid: vge.MultiCircuit = vge.MultiCircuit()
    slack: vge.Bus = grid.add_bus(vge.Bus(name="Slack", Vnom=20.0, is_slack=True))
    pv: vge.Bus = grid.add_bus(vge.Bus(name="PV", Vnom=20.0))
    grid.add_generator(bus=slack, api_obj=vge.Generator())
    generator: vge.Generator = vge.Generator(name="Invalid sequence generator",
                                           r0=0.01, x0=0.08, r2=0.02, x2=0.10)
    grid.add_generator(bus=pv, api_obj=generator)
    grid.add_line(vge.Line(bus_from=slack, bus_to=pv, r=0.02, x=0.08, r0=0.04, x0=0.16))
    if sequence == 0:
        generator.R0, generator.X0 = impedance, impedance
    else:
        generator.R2, generator.X2 = impedance, impedance

    driver: vge.PowerFlowDriver3Ph = vge.PowerFlowDriver3Ph(grid=grid, options=vge.PowerFlowOptions())
    thread: GcThread = GcThread(driver=driver)
    session: SimulationSession = SimulationSession()
    session.register(driver)
    thread.run()
    assert thread.has_failed()
    assert driver.results is None

    main: _Main = _Main()
    main.session = session
    SimulationsMain.post_power_flow3ph(main)
    assert main.shown_logger is driver.logger
    diagnostic: str = str(main.shown_logger)
    assert f"Z{sequence} must be finite and nonzero" in diagnostic
    assert generator.name in diagnostic
    assert f"Check R{sequence}/X{sequence}" in diagnostic
    assert "Is there any slack bus" not in diagnostic
    assert main.stuff_running_now == list()
    assert main.unlocked
