from __future__ import annotations

import os
import subprocess
import sys
from enum import Enum
from pathlib import Path

from PySide6 import QtCore, QtWidgets

from VeraGrid.Gui.gui_functions import ComboModel, ComboStableKey
from VeraGrid.Gui.Main.SubClasses.Settings.configuration import (
    config_data_to_struct,
    get_combo_box_config_value,
    set_combo_box_config_value,
)


REPO_ROOT = Path(__file__).resolve().parents[3]
RUNNER = Path(__file__).with_name("combo_model_config_runner.py")


class LocalMode(Enum):
    """
    Small enum used to verify that combo boxes expose runtime enum values.
    """

    PowerFlow = "Power Flow"
    OptimalPowerFlow = "Optimal Power Flow"


def translate_with_prefix(source_text: str) -> str:
    """
    Translate text with a deterministic test prefix.

    :param source_text: Source text stored by the combo model.
    :return: Test translated text.
    """
    return "tr:" + source_text


def translate_with_new_prefix(source_text: str) -> str:
    """
    Translate text with a second deterministic test prefix.

    :param source_text: Source text stored by the combo model.
    :return: Test translated text.
    """
    return "new:" + source_text


def test_combo_model_keeps_runtime_data_stable_keys_and_source_text(qt_app: QtWidgets.QApplication) -> None:
    """
    Verify translated combo labels do not replace runtime enum values or persistence keys.

    :param qt_app: Shared Qt application fixture.
    :return: Nothing.
    """
    _qt_app: QtWidgets.QApplication = qt_app
    combo_box = QtWidgets.QComboBox()
    model = ComboModel(enum_values=[LocalMode.PowerFlow, LocalMode.OptimalPowerFlow],
                       text_items=[("Plain Text", "plain-text-key")],
                       translate=translate_with_prefix)
    combo_box.setModel(model)

    enum_value: LocalMode = combo_box.itemData(0)
    enum_key: ComboStableKey = combo_box.itemData(0, ComboModel.StableKeyRole)
    enum_source_text: str = combo_box.itemData(0, ComboModel.SourceTextRole)
    assert enum_value is LocalMode.PowerFlow
    assert enum_key == LocalMode.PowerFlow.value
    assert enum_source_text == LocalMode.PowerFlow.value
    assert combo_box.itemText(0) == "tr:" + LocalMode.PowerFlow.value

    combo_box.setCurrentIndex(1)
    saved_enum_key: ComboStableKey = get_combo_box_config_value(combo_box=combo_box)
    assert saved_enum_key == LocalMode.OptimalPowerFlow.value

    combo_box.setCurrentIndex(0)
    set_combo_box_config_value(combo_box=combo_box, value=saved_enum_key)
    restored_enum_value: LocalMode = combo_box.currentData()
    assert restored_enum_value is LocalMode.OptimalPowerFlow

    combo_box.setCurrentIndex(2)
    saved_text_key: ComboStableKey = get_combo_box_config_value(combo_box=combo_box)
    assert saved_text_key == "plain-text-key"

    combo_box.setCurrentIndex(0)
    set_combo_box_config_value(combo_box=combo_box, value=saved_text_key)
    restored_text_value: str = combo_box.currentData()
    assert restored_text_value == "plain-text-key"

    model.retranslate(translate=translate_with_new_prefix)
    assert combo_box.itemText(0) == "new:" + LocalMode.PowerFlow.value
    assert combo_box.itemData(0) is LocalMode.PowerFlow
    assert combo_box.itemData(0, ComboModel.StableKeyRole) == LocalMode.PowerFlow.value
    assert combo_box.itemData(0, ComboModel.SourceTextRole) == LocalMode.PowerFlow.value


def test_config_restore_ignores_legacy_bad_numeric_values(qt_app: QtWidgets.QApplication) -> None:
    """
    Verify legacy string values are not pushed into numeric GUI controls.

    :param qt_app: Shared Qt application fixture.
    :return: Nothing.
    """
    _qt_app: QtWidgets.QApplication = qt_app
    spin_box = QtWidgets.QSpinBox()
    spin_box.setValue(7)

    config_data_to_struct(data_={"section": {"samples": "Grid Metrics"}},
                          struct_={"section": {"samples": spin_box}})
    assert spin_box.value() == 7

    config_data_to_struct(data_={"section": {"samples": 12}},
                          struct_={"section": {"samples": spin_box}})
    assert spin_box.value() == 12


def test_plain_translated_enum_combo_saves_enum_value(qt_app: QtWidgets.QApplication) -> None:
    """
    Verify old translated addItem/data combos persist enum values instead of labels.

    :param qt_app: Shared Qt application fixture.
    :return: Nothing.
    """
    _qt_app: QtWidgets.QApplication = qt_app
    combo_box = QtWidgets.QComboBox()
    combo_box.addItem("flujo traducido", LocalMode.PowerFlow)
    combo_box.addItem("opf traducido", LocalMode.OptimalPowerFlow)

    combo_box.setCurrentIndex(1)
    saved_value: ComboStableKey = get_combo_box_config_value(combo_box=combo_box)
    assert saved_value == LocalMode.OptimalPowerFlow.value

    combo_box.setCurrentIndex(0)
    set_combo_box_config_value(combo_box=combo_box, value=saved_value)
    selected_mode: LocalMode = combo_box.currentData()
    assert selected_mode is LocalMode.OptimalPowerFlow


def test_main_window_config_combo_values_round_trip(tmp_path: Path) -> None:
    """
    Verify all main-window configuration combo boxes save and restore runtime values.

    :param tmp_path: Temporary directory provided by pytest.
    :return: Nothing.
    """
    env = os.environ.copy()
    env["QT_QPA_PLATFORM"] = env.get("QT_QPA_PLATFORM", "offscreen")

    # Keep the real main-window startup inside test-owned user state so its
    # configuration and plugin discovery cannot depend on the operator's home.
    isolated_home: Path = tmp_path / "home"
    isolated_home.mkdir(parents=True, exist_ok=True)
    env["HOME"] = str(isolated_home)
    env["USERPROFILE"] = str(isolated_home)

    python_path_entries = [
        str(REPO_ROOT / "src"),
        str(REPO_ROOT / "src" / "tests"),
    ]
    existing_pythonpath = env.get("PYTHONPATH", "")
    if len(existing_pythonpath) > 0:
        python_path_entries.append(existing_pythonpath)
    else:
        pass
    env["PYTHONPATH"] = os.pathsep.join(python_path_entries)

    result: subprocess.CompletedProcess[str] = subprocess.run(
        [sys.executable, str(RUNNER), str(tmp_path / "combo_config.json")],
        cwd=str(REPO_ROOT),
        env=env,
        capture_output=True,
        text=True,
        timeout=300,
    )

    if result.returncode != 0:
        raise AssertionError(
            f"Combo configuration round trip failed with exit code {result.returncode}\n"
            f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        )
    else:
        pass

    assert "all config combo round trip: ok" in result.stdout
    assert "covered:" in result.stdout

    # Confirm that the child resolved VeraGrid's standard state below the
    # isolated home while exercising the complete main-window configuration.
    isolated_veragrid_folder: Path = isolated_home / ".VeraGrid"
    assert isolated_veragrid_folder.is_dir()
