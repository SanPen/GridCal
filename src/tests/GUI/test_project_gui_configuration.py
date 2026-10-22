"""Check that project archives deliver saved preferences to GUI controls."""

from pathlib import Path

import pytest
from PySide6 import QtWidgets

from VeraGrid.Gui.Main.SubClasses.Settings.configuration import config_data_to_struct
from VeraGrid.Session.file_handler import FileOpenThread
from VeraGridEngine.Devices.multi_circuit import MultiCircuit
from VeraGridEngine.Devices.multiverse import MultiVerse
from VeraGridEngine.IO.file_save import (
    FileSavingOptions, save_veragrid_circuit, save_veragrid_multiverse,
)


@pytest.mark.parametrize("multiverse_archive", (False, True))
def test_project_preferences_reach_gui_controls(
        qt_app: QtWidgets.QApplication,
        tmp_path: Path,
        multiverse_archive: bool,
) -> None:
    """Restore preferences through the same file worker used by the GUI.

    :param qt_app: Shared Qt application.
    :param tmp_path: Temporary project directory.
    :param multiverse_archive: Whether to save the GUI's multiverse layout.
    :return: None.
    """
    circuit: MultiCircuit = MultiCircuit(name="GUI preferences")
    file_name: str = str(tmp_path / "preferences.veragrid")
    options: FileSavingOptions = FileSavingOptions(
        dictionary_of_json_files=dict(gui_config=dict(power_flow=dict(max_iterations=37))),
    )
    # Both legacy single-circuit and current GUI archives must keep root JSON.
    if multiverse_archive:
        save_veragrid_multiverse(file_name=file_name, multiverse=MultiVerse(circuit), options=options)
    else:
        save_veragrid_circuit(circuit=circuit, file_name=file_name, options=options)

    worker: FileOpenThread = FileOpenThread(file_name=file_name)
    worker.run()
    assert worker.valid
    assert worker.circuit is not None
    assert worker.circuit.name == circuit.name
    assert (worker.multiverse is not None) == multiverse_archive

    # post_open_file passes this exact payload to the configuration mapper.
    iterations: QtWidgets.QSpinBox = QtWidgets.QSpinBox()
    iterations.setValue(5)
    config_data_to_struct(worker.json_files["gui_config"],
                          dict(power_flow=dict(max_iterations=iterations)))
    assert iterations.value() == 37
    iterations.close()
