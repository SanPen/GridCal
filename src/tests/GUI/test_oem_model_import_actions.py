# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations

import hashlib
from pathlib import Path
import subprocess
import struct
import sys

import pytest
from PySide6 import QtCore, QtWidgets

from VeraGrid.Gui.DynamicModelEditor.Workspace.Tabs.dynamic_editor_tab import DynamicEditorTab
from VeraGrid.Gui.DynamicModelEditor.Workspace.dynamic_editor_workspace_session import DynamicEditorWorkspaceSession
from VeraGrid.Gui.DynamicModelEditor.Workspace.dynamic_editor_workspace_window import DynamicEditorWorkspaceWindow
from VeraGrid.Gui.FmuTemplateEditor.fmu_template_editor import FmuTemplateEditorDialog
from VeraGrid.Gui.Main.SubClasses.io import IoMain
from VeraGrid.Gui.ManufacturerNativeImporter.manufacturer_native_importer import ManufacturerNativeImporterDialog
from VeraGridEngine.Devices.Dynamic.manufacturer_native_model import (
    ManufacturerNativeBinaryVariant,
    ManufacturerNativeModel,
)
from VeraGridEngine.Devices.Dynamic.rms_template import RmsModelTemplate
from VeraGridEngine.Devices.multi_circuit import MultiCircuit
from VeraGridEngine.enumerations import (
    DynamicSimulationMode,
    IeeeCigreDllPlatform,
    IeeeCigreDllVerificationStatus,
    NativeModelInterface,
)

from VeraGridEngine.IO.manufacturer_native.model_info_codec import (
    encode_manufacturer_native_model_info,
)
from VeraGridEngine.IO.manufacturer_native.worker_artifact import (
    ManufacturerNativeWorkerArtifact,
    _worker_sources,
)
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.procedural_logic import ManufacturerNativeControllerLogic
from tests.MANUFACTURER_NATIVE.test_model_info_codec import _model_info

import VeraGridEngine.api as gce


class OemImportHarness(QtWidgets.QWidget):
    """Minimal real Qt owner for exercising the IoMain OEM actions."""

    __slots__ = (
        "circuit",
        "project_directory",
        "dynamic_editor_workspace_session",
        "view_refresh_count",
    )

    def __init__(self, project_directory: str) -> None:
        """
        Build an isolated import owner with the same collaborators used by IoMain.

        :param project_directory: Directory used to resolve selected OEM files.
        :return: None.
        """
        super().__init__()
        self.circuit: MultiCircuit = MultiCircuit()
        self.project_directory: str = project_directory
        self.dynamic_editor_workspace_session: DynamicEditorWorkspaceSession = (
            DynamicEditorWorkspaceSession()
        )
        self.view_refresh_count: int = 0

    def view_objects_data(self) -> None:
        """
        Record a database-view refresh requested by a successful import.

        :return: None.
        """
        self.view_refresh_count += 1


class FmuImportDialogDriver(QtCore.QObject):
    """Drive one real FMU modal through acceptance or cancellation."""

    __slots__ = ("_app", "_fmu_path", "_accept", "interacted")

    def __init__(
            self,
            app: QtWidgets.QApplication,
            fmu_path: Path,
            accept: bool,
    ) -> None:
        """
        Store the modal interaction requested by one test.

        :param app: Shared Qt application.
        :param fmu_path: Existing FMU selected during acceptance.
        :param accept: Whether to accept or cancel the dialog.
        :return: None.
        """
        super().__init__()
        self._app: QtWidgets.QApplication = app
        self._fmu_path: Path = fmu_path
        self._accept: bool = accept
        self.interacted: bool = False

    @QtCore.Slot()
    def interact(self) -> None:
        """
        Complete the active FMU dialog after its modal event loop starts.

        :return: None.
        """
        active_widget: QtWidgets.QWidget | None = self._app.activeModalWidget()
        if isinstance(active_widget, FmuTemplateEditorDialog):
            self.interacted = True
            if self._accept:
                active_widget._path_edit.setText(str(self._fmu_path))
                active_widget._accept_dialog()
            else:
                active_widget.reject()
        else:
            if active_widget is not None:
                active_widget.close()
            else:
                pass


class NativeImportCancelDriver(QtCore.QObject):
    """Cancel one real IEEE/CIGRE native import modal."""

    __slots__ = ("_app", "interacted")

    def __init__(self, app: QtWidgets.QApplication) -> None:
        """
        Store the Qt application used to find the active modal.

        :param app: Shared Qt application.
        :return: None.
        """
        super().__init__()
        self._app: QtWidgets.QApplication = app
        self.interacted: bool = False

    @QtCore.Slot()
    def interact(self) -> None:
        """
        Reject the active manufacturer-native importer.

        :return: None.
        """
        active_widget: QtWidgets.QWidget | None = self._app.activeModalWidget()
        if isinstance(active_widget, ManufacturerNativeImporterDialog):
            self.interacted = True
            active_widget.reject()
        else:
            if active_widget is not None:
                active_widget.close()
            else:
                pass


class NativeImportAcceptDriver(QtCore.QObject):
    """Drive one real IEEE/CIGRE native import modal with a PE32 fixture."""

    __slots__ = (
        "_app",
        "_binary_path",
        "_platform",
        "_native_interface",
        "_expect_acceptance",
        "interacted",
        "failure_text",
        "summary_text",
    )

    def __init__(
            self,
            app: QtWidgets.QApplication,
            binary_path: Path,
            platform: IeeeCigreDllPlatform = IeeeCigreDllPlatform.WINDOWS_X86,
            native_interface: NativeModelInterface = NativeModelInterface.IEEE_CIGRE_V1_1,
            expect_acceptance: bool = True,
    ) -> None:
        """Store the application and checked binary selected by the test.

        :param app: Shared Qt application.
        :param binary_path: Qualified PE32 manufacturer library.
        :param platform: Platform selected in the importer.
        :param native_interface: Native contract selected in the importer.
        :param expect_acceptance: Whether the selected combination must import.
        :return: None.
        """
        super().__init__()
        self._app: QtWidgets.QApplication = app
        self._binary_path: Path = binary_path
        self._platform: IeeeCigreDllPlatform = platform
        self._native_interface: NativeModelInterface = native_interface
        self._expect_acceptance: bool = expect_acceptance
        self.interacted: bool = False
        self.failure_text: str = ""
        self.summary_text: str = ""

    @QtCore.Slot()
    def close_unexpected_warning(self) -> None:
        """Close a qualification warning so a failed test cannot block Qt.

        :return: None.
        """
        active_widget: QtWidgets.QWidget | None = self._app.activeModalWidget()
        if isinstance(active_widget, QtWidgets.QMessageBox):
            if (
                    self._expect_acceptance
                    and active_widget.icon() == QtWidgets.QMessageBox.Icon.Information
            ):
                self.summary_text = active_widget.text()
            else:
                self.failure_text = active_widget.text()
            active_widget.accept()
        else:
            if isinstance(active_widget, QtWidgets.QFileDialog):
                active_widget.reject()
            else:
                pass

    @QtCore.Slot()
    def interact(self) -> None:
        """Populate and submit the active manufacturer-native importer.

        :return: None.
        """
        active_widget: QtWidgets.QWidget | None = self._app.activeModalWidget()
        if isinstance(active_widget, ManufacturerNativeImporterDialog):
            self.interacted = True
            platform_index: int = active_widget._platform_combo.findData(
                self._platform
            )
            interface_index: int = active_widget._interface_combo.findData(
                self._native_interface
            )
            if platform_index < 0 or interface_index < 0:
                self.failure_text = "Requested platform or interface is absent from the OEM importer"
                active_widget.reject()
            else:
                active_widget._platform_combo.setCurrentIndex(platform_index)
                active_widget._interface_combo.setCurrentIndex(interface_index)
                active_widget._path_edit.setText(str(self._binary_path))
                active_widget._no_late_loading_check.setChecked(True)
                active_widget._instance_isolation_check.setChecked(True)
                QtCore.QTimer.singleShot(100, self.close_unexpected_warning)
                active_widget._inspect_and_store()
                accepted: bool = (
                    active_widget.result() == int(QtWidgets.QDialog.DialogCode.Accepted)
                )
                if accepted:
                    if self._expect_acceptance:
                        pass
                    else:
                        self.failure_text = "Mismatched native import was unexpectedly accepted"
                else:
                    if len(self.failure_text) == 0:
                        self.failure_text = active_widget._status_view.toPlainText()
                    else:
                        pass
                    active_widget.reject()
        else:
            if active_widget is not None:
                active_widget.close()
            else:
                pass


def get_fmu_artifact_path() -> Path:
    """
    Return the checked-in FMU used by the real import-dialog test.

    :return: Existing FMU artifact path.
    """
    return Path(__file__).resolve().parents[1] / "data" / "fmi" / "artifacts" / "FrequencyLoadPilot.fmu"


def test_fmu_oem_action_adds_only_an_accepted_template(qt_app: object) -> None:
    """
    Exercise the real FMU dialog and verify atomic catalogue registration.

    :param qt_app: Shared Qt application fixture.
    :return: None.
    """
    app: QtWidgets.QApplication = qt_app
    fmu_path: Path = get_fmu_artifact_path()
    harness: OemImportHarness = OemImportHarness(project_directory=str(fmu_path.parent))
    driver: FmuImportDialogDriver = FmuImportDialogDriver(
        app=app,
        fmu_path=fmu_path,
        accept=True,
    )

    QtCore.QTimer.singleShot(0, driver.interact)
    IoMain.import_oem_fmu_model(harness)

    assert driver.interacted
    assert harness.circuit.get_fmu_templates_number() == 1
    assert harness.circuit.fmu_templates[0].fmu_relative_path == str(fmu_path)
    assert harness.view_refresh_count == 1

    harness.close()
    harness.deleteLater()


def test_fmu_oem_action_cancellation_leaves_catalogue_unchanged(qt_app: object) -> None:
    """
    Verify that cancelling the real FMU dialog creates no project asset.

    :param qt_app: Shared Qt application fixture.
    :return: None.
    """
    app: QtWidgets.QApplication = qt_app
    fmu_path: Path = get_fmu_artifact_path()
    harness: OemImportHarness = OemImportHarness(project_directory=str(fmu_path.parent))
    driver: FmuImportDialogDriver = FmuImportDialogDriver(
        app=app,
        fmu_path=fmu_path,
        accept=False,
    )

    QtCore.QTimer.singleShot(0, driver.interact)
    IoMain.import_oem_fmu_model(harness)

    assert driver.interacted
    assert harness.circuit.get_fmu_templates_number() == 0
    assert harness.view_refresh_count == 0

    harness.close()
    harness.deleteLater()


def test_native_oem_action_cancellation_leaves_assets_unchanged(qt_app: object) -> None:
    """
    Verify that cancelling the real native importer creates no provider or template.

    :param qt_app: Shared Qt application fixture.
    :return: None.
    """
    app: QtWidgets.QApplication = qt_app
    harness: OemImportHarness = OemImportHarness(project_directory=str(Path.cwd()))
    driver: NativeImportCancelDriver = NativeImportCancelDriver(app=app)

    QtCore.QTimer.singleShot(0, driver.interact)
    IoMain.import_oem_manufacturer_native_model(harness)

    assert driver.interacted
    assert len(harness.circuit.manufacturer_native_models) == 0
    assert len(harness.circuit.rms_models) == 0
    assert len(harness.circuit.emt_models) == 0
    assert harness.view_refresh_count == 0

    # Reuse the same real dialog flow for both analyst fail-closed cases. The
    # PE32 fixture is valid only as Windows x86 / IEEE-CIGRE 1.1, so either
    # mismatched selection must fail without leaving partial catalogue state.
    fixture_path: Path = (
        Path(__file__).resolve().parents[1]
        / "data"
        / "manufacturer_native"
        / "windows_x86"
        / "fixture_qualified_x86.dll"
    )
    mismatch_cases: tuple[
        tuple[IeeeCigreDllPlatform, NativeModelInterface], ...
    ] = (
        (
            IeeeCigreDllPlatform.WINDOWS_X64,
            NativeModelInterface.IEEE_CIGRE_V1_1,
        ),
        (
            IeeeCigreDllPlatform.WINDOWS_X86,
            NativeModelInterface.IEEE_CIGRE_V1_0,
        ),
    )
    mismatch_platform: IeeeCigreDllPlatform
    mismatch_interface: NativeModelInterface
    for mismatch_platform, mismatch_interface in mismatch_cases:
        mismatch_driver: NativeImportAcceptDriver = NativeImportAcceptDriver(
            app=app,
            binary_path=fixture_path,
            platform=mismatch_platform,
            native_interface=mismatch_interface,
            expect_acceptance=False,
        )
        QtCore.QTimer.singleShot(0, mismatch_driver.interact)
        IoMain.import_oem_manufacturer_native_model(harness)

        assert mismatch_driver.interacted
        assert len(mismatch_driver.failure_text) > 0
        assert len(harness.circuit.manufacturer_native_models) == 0
        assert len(harness.circuit.rms_models) == 0
        assert len(harness.circuit.emt_models) == 0
        assert harness.view_refresh_count == 0

    harness.close()
    harness.deleteLater()

def test_native_oem_dialog_offers_both_windows_architectures(qt_app: object) -> None:
    """Expose x64 and x86 as explicit variants in the existing OEM dialog.

    :param qt_app: Shared Qt application fixture.
    :return: None.
    """
    app: QtWidgets.QApplication = qt_app
    dialog: ManufacturerNativeImporterDialog = ManufacturerNativeImporterDialog(
        assets=MultiCircuit(),
    )
    windows_x64_index: int = dialog._platform_combo.findData(
        IeeeCigreDllPlatform.WINDOWS_X64
    )
    windows_x86_index: int = dialog._platform_combo.findData(
        IeeeCigreDllPlatform.WINDOWS_X86
    )
    linux_x64_index: int = dialog._platform_combo.findData(
        IeeeCigreDllPlatform.LINUX_X64
    )

    assert windows_x64_index >= 0
    assert windows_x86_index >= 0
    assert linux_x64_index >= 0
    dialog._platform_combo.setCurrentIndex(windows_x86_index)
    assert dialog._selected_platform() == IeeeCigreDllPlatform.WINDOWS_X86

    dialog.close()
    dialog.deleteLater()
    app.processEvents()

def test_native_oem_dialog_offers_all_supported_interfaces(qt_app: object) -> None:
    """Expose the three explicit manufacturer ABI contracts.

    :param qt_app: Shared Qt application fixture.
    :return: None.
    """
    app: QtWidgets.QApplication = qt_app
    dialog: ManufacturerNativeImporterDialog = ManufacturerNativeImporterDialog(
        assets=MultiCircuit(),
    )
    expected_interfaces: tuple[NativeModelInterface, ...] = (
        NativeModelInterface.IEEE_CIGRE_V1_1,
        NativeModelInterface.IEEE_CIGRE_V1_0,
        NativeModelInterface.IEC_ESE,
    )
    native_interface: NativeModelInterface
    for native_interface in expected_interfaces:
        assert dialog._interface_combo.findData(native_interface) >= 0

    ese_index: int = dialog._interface_combo.findData(NativeModelInterface.IEC_ESE)
    dialog._interface_combo.setCurrentIndex(ese_index)
    assert dialog._selected_interface() == NativeModelInterface.IEC_ESE
    assert not dialog._instance_isolation_check.isEnabled()

    dialog.close()
    dialog.deleteLater()
    app.processEvents()

def test_native_oem_dialog_exposes_rebind_only_for_valid_migration(
        qt_app: object,
) -> None:
    """Keep import, variant attachment, and provider migration visibly separate.

    :param qt_app: Shared Qt application fixture.
    :return: None.
    """
    app: QtWidgets.QApplication = qt_app
    empty_dialog: ManufacturerNativeImporterDialog = ManufacturerNativeImporterDialog(
        assets=MultiCircuit(),
    )
    assert empty_dialog._rebind_group.isHidden()
    empty_dialog.close()
    empty_dialog.deleteLater()

    circuit: MultiCircuit = MultiCircuit()
    source_provider: ManufacturerNativeModel = ManufacturerNativeModel(
        name="Source provider"
    )
    source_provider.model_info = encode_manufacturer_native_model_info(_model_info())
    destination_provider: ManufacturerNativeModel = ManufacturerNativeModel(
        name="Destination provider"
    )
    destination_provider.model_info = source_provider.model_info
    circuit.add_manufacturer_native_model(source_provider)
    circuit.add_manufacturer_native_model(destination_provider)

    without_consumer: ManufacturerNativeImporterDialog = (
        ManufacturerNativeImporterDialog(
            assets=circuit,
            provider=source_provider,
        )
    )
    assert without_consumer._rebind_group.isHidden()
    without_consumer.close()
    without_consumer.deleteLater()

    controller: ManufacturerNativeControllerLogic = ManufacturerNativeControllerLogic(
        provider_idtag=source_provider.idtag,
        model_info_sha256=source_provider.model_info_sha256,
        signal_bindings=tuple(),
        parameter_overrides=tuple(),
        name="Source controller",
    )
    consumer: RmsModelTemplate = RmsModelTemplate(name="Source RMS template")
    consumer.block = Block(
        name="Source controller block",
        procedural_logic=(controller,),
        is_decomposable=False,
    )
    circuit.add_rms_model(consumer)

    migration_dialog: ManufacturerNativeImporterDialog = (
        ManufacturerNativeImporterDialog(
            assets=circuit,
            provider=source_provider,
        )
    )
    assert not migration_dialog._rebind_group.isHidden()
    assert migration_dialog._rebind_consumer_combo.count() == 1
    assert migration_dialog._rebind_destination_combo.count() == 1
    assert migration_dialog._rebind_button.isEnabled()
    assert "source 0 to destination 1" in migration_dialog._input_mapping_edit.toolTip()

    migration_dialog.close()
    migration_dialog.deleteLater()
    app.processEvents()


def test_native_oem_action_rejects_windows_x86_model_on_linux(qt_app: object) -> None:
    """A Linux host must leave the catalogue untouched after a Windows import."""
    if not sys.platform.startswith("linux") or struct.calcsize("P") != 8:
        pytest.skip("This rejection path requires 64-bit Linux")

    app: QtWidgets.QApplication = qt_app
    fixture_path: Path = (
        Path(__file__).resolve().parents[1]
        / "data"
        / "manufacturer_native"
        / "windows_x86"
        / "fixture_qualified_x86.dll"
    )
    harness: OemImportHarness = OemImportHarness(
        project_directory=str(fixture_path.parent)
    )
    driver: NativeImportAcceptDriver = NativeImportAcceptDriver(
        app=app,
        binary_path=fixture_path,
        expect_acceptance=False,
    )
    QtCore.QTimer.singleShot(0, driver.interact)
    IoMain.import_oem_manufacturer_native_model(harness)

    assert driver.interacted
    assert driver.failure_text == "Native inspection must run on a host matching the binary platform"
    assert harness.circuit.manufacturer_native_models == []
    assert harness.circuit.rms_models == []
    assert harness.circuit.emt_models == []
    assert harness.view_refresh_count == 0
    harness.close()
    harness.deleteLater()
    app.processEvents()


@pytest.mark.parametrize(
    "platform",
    (IeeeCigreDllPlatform.WINDOWS_X86, IeeeCigreDllPlatform.LINUX_X64),
)
def test_native_oem_action_imports_qualified_model(
        qt_app: object,
        tmp_path: Path,
        platform: IeeeCigreDllPlatform) -> None:
    """Import a qualified native model and refresh an open RMS library.

    :param qt_app: Shared Qt application fixture.
    :return: None.
    """
    app: QtWidgets.QApplication = qt_app
    fixture_root: Path = Path(__file__).resolve().parents[1] / "data" / "manufacturer_native"
    worker_artifact: ManufacturerNativeWorkerArtifact | None = None
    if platform == IeeeCigreDllPlatform.WINDOWS_X86:
        if sys.platform != "win32" or struct.calcsize("P") != 8:
            pytest.skip("Windows x86 native worker requires a 64-bit Windows host")
        fixture_path: Path = fixture_root / "windows_x86" / "fixture_qualified_x86.dll"
    else:
        if not sys.platform.startswith("linux") or struct.calcsize("P") != 8:
            pytest.skip("Linux x64 native worker requires a 64-bit Linux host")
        fixture_path = tmp_path / "fixture_qualified_linux_x64.so"
        compiled: subprocess.CompletedProcess[str] = subprocess.run(
            [
                "cc", "-std=c11", "-O2", "-shared", "-fPIC", "-Wall", "-Wextra",
                "-Werror", "-DQUALIFIED=1", "-o", str(fixture_path),
                str(fixture_root / "linux_x64_v11" / "fixture.c"),
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        assert compiled.returncode == 0, compiled.stderr
        worker_source_root: Path = _worker_sources()[0].parent
        worker_path: Path = tmp_path / "veragrid-manufacturer-worker"
        worker_sources: list[str] = [
            str(worker_source_root / name)
            for name in (
                "worker.c", "platform_hash.c", "protocol.c",
                "adapter_ieee_cigre_v1_1.c", "adapter_ieee_cigre_v1_0.c",
                "adapter_iec_ese.c", "platform_linux.c",
            )
        ]
        worker_build: subprocess.CompletedProcess[str] = subprocess.run(
            [
                "cc", "-std=c11", "-O2", "-Wall", "-Wextra",
                "-DVERAGRID_MANUFACTURER_WORKER=1", *worker_sources,
                "-ldl", "-lm", "-o", str(worker_path),
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        assert worker_build.returncode == 0, worker_build.stderr
        worker_artifact = ManufacturerNativeWorkerArtifact(
            executable_path=worker_path,
            content_sha256=hashlib.sha256(worker_path.read_bytes()).hexdigest(),
            platform=IeeeCigreDllPlatform.LINUX_X64,
            cache_key="gui-test-local-worker",
        )
    harness: OemImportHarness = OemImportHarness(
        project_directory=str(fixture_path.parent)
    )

    # Keep one real editor open so the accepted action must update its existing
    # library model, rather than proving only that objects entered Assets.
    bus: gce.Bus = gce.Bus(name="OEM GUI bus", Vnom=10.0)
    harness.circuit.add_bus(bus)
    load: gce.Load = gce.Load(name="OEM GUI load")
    harness.circuit.add_load(bus=bus, api_obj=load)
    workspace: DynamicEditorWorkspaceWindow = DynamicEditorWorkspaceWindow(
        session=harness.dynamic_editor_workspace_session
    )
    page: DynamicEditorTab | None = workspace.open_dynamic_editor_for(
        load,
        harness.circuit,
        preferred_mode=DynamicSimulationMode.RMS,
    )
    assert page is not None
    assert page.editor is not None
    assert len(page.editor.templates_list) == 0

    driver: NativeImportAcceptDriver = NativeImportAcceptDriver(
        app=app,
        binary_path=fixture_path,
        platform=platform,
    )
    QtCore.QTimer.singleShot(0, driver.interact)
    IoMain.import_oem_manufacturer_native_model(harness, worker_artifact=worker_artifact)

    assert driver.interacted
    assert driver.failure_text == ""
    assert "Provider: GoldenModel" in driver.summary_text
    assert f"Platform: {platform.value}" in driver.summary_text
    assert "RMS templates created: GoldenModel RMS" in driver.summary_text
    assert "EMT templates created: GoldenModel EMT" in driver.summary_text
    assert len(harness.circuit.manufacturer_native_models) == 1
    assert len(harness.circuit.rms_models) == 1
    assert len(harness.circuit.emt_models) == 1
    provider: ManufacturerNativeModel = harness.circuit.manufacturer_native_models[0]
    variant: ManufacturerNativeBinaryVariant | None = provider.get_platform_variant(
        platform
    )
    assert variant is not None
    assert variant.verification_status == IeeeCigreDllVerificationStatus.DECLARED_AND_QUALIFIED
    assert page.editor.templates_list == [harness.circuit.rms_models[0]]
    assert page.editor.templates_list[0].name == "GoldenModel RMS"
    assert harness.view_refresh_count == 1

    # Reattach the already qualified platform through the distinct variant
    # workflow. It may replace that platform record, but it must not create a
    # second provider or another RMS/EMT template.
    attach_driver: NativeImportAcceptDriver = NativeImportAcceptDriver(
        app=app,
        binary_path=fixture_path,
        platform=platform,
    )
    attach_dialog: ManufacturerNativeImporterDialog = (
        ManufacturerNativeImporterDialog(
            assets=harness.circuit,
            provider=provider,
            worker_artifact=worker_artifact,
        )
    )
    QtCore.QTimer.singleShot(0, attach_driver.interact)
    attach_result: int = attach_dialog.exec()
    assert attach_result == int(QtWidgets.QDialog.DialogCode.Accepted)
    assert attach_driver.interacted
    assert attach_driver.failure_text == ""
    assert "Provider: GoldenModel" in attach_driver.summary_text
    assert f"Platform attached: {platform.value}" in attach_driver.summary_text
    assert "Templates created: None" in attach_driver.summary_text
    assert len(harness.circuit.manufacturer_native_models) == 1
    assert len(harness.circuit.rms_models) == 1
    assert len(harness.circuit.emt_models) == 1
    assert page.editor.templates_list == [harness.circuit.rms_models[0]]
    attach_dialog.deleteLater()

    harness.dynamic_editor_workspace_session.reset_for_tests()
    harness.close()
    harness.deleteLater()
    app.processEvents()
