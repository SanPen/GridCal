# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations

from pathlib import Path
import sys
from typing import Optional, Tuple

from PySide6 import QtWidgets

from VeraGridEngine.Devices.assets import Assets
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Devices.Dynamic.manufacturer_native_model import ManufacturerNativeModel
from VeraGridEngine.Devices.Dynamic.rms_template import RmsModelTemplate
from VeraGridEngine.enumerations import (
    IeeeCigreDllModelMode,
    IeeeCigreDllPlatform,
    NativeModelInterface,
    NativeCompilerFramework,
)
from VeraGridEngine.IO.manufacturer_native.importer import (
    attach_manufacturer_native_binary_variant,
    import_manufacturer_native_model,
)
from VeraGridEngine.IO.manufacturer_native.model_info import (
    build_manufacturer_native_rebind_plan,
)
from VeraGridEngine.IO.manufacturer_native.model_info_codec import (
    decode_manufacturer_native_model_info,
)
from VeraGridEngine.IO.manufacturer_native.worker_artifact import prepare_manufacturer_native_runtime
from VeraGridEngine.IO.native_compiler.compiler_interface import NativeCompilerSelection
from VeraGridEngine.IO.native_compiler.selected_interface import (
    load_saved_local_llvm_selection,
    save_local_llvm_selection,
)
from VeraGridEngine.Utils.procedural_logic import (
    ManufacturerNativeControllerLogic,
    ManufacturerNativeRebindPlan,
    ProceduralLogicBase,
)
from VeraGridEngine.Utils.Symbolic.block import Block


class ManufacturerNativeImporterDialog(QtWidgets.QDialog):
    """Import or extend one manufacturer supplied native model provider."""

    __slots__ = (
        "_assets", "_provider", "_path_edit", "_interface_combo", "_platform_combo",
        "_no_late_loading_check", "_instance_isolation_check", "_status_view",
        "_rebind_consumer_combo", "_rebind_destination_combo",
        "_input_mapping_edit", "_output_mapping_edit", "_parameter_mapping_edit",
        "_rebind_button", "_rebind_group",
    )

    def __init__(self,
                 assets: Assets,
                 provider: Optional[ManufacturerNativeModel] = None,
                 parent: Optional[QtWidgets.QWidget] = None) -> None:
        """Build the native model import dialog.

        :param assets: Canonical circuit asset owner.
        :param provider: Existing provider when attaching another platform variant.
        :param parent: Optional parent widget.
        :return: None.
        """
        super().__init__(parent)
        self._assets: Assets = assets
        self._provider: Optional[ManufacturerNativeModel] = provider
        self._path_edit: QtWidgets.QLineEdit = QtWidgets.QLineEdit(self)
        self._interface_combo: QtWidgets.QComboBox = QtWidgets.QComboBox(self)
        self._platform_combo: QtWidgets.QComboBox = QtWidgets.QComboBox(self)
        self._no_late_loading_check: QtWidgets.QCheckBox = QtWidgets.QCheckBox(
            self.tr("The manufacturer declares that the library performs no late native loading."), self)
        self._instance_isolation_check: QtWidgets.QCheckBox = QtWidgets.QCheckBox(
            self.tr("The manufacturer declares that all mutable model state is owned by each Instance."), self)
        self._status_view: QtWidgets.QPlainTextEdit = QtWidgets.QPlainTextEdit(self)
        self._rebind_consumer_combo: QtWidgets.QComboBox = QtWidgets.QComboBox(self)
        self._rebind_destination_combo: QtWidgets.QComboBox = QtWidgets.QComboBox(self)
        self._input_mapping_edit: QtWidgets.QLineEdit = QtWidgets.QLineEdit(self)
        self._output_mapping_edit: QtWidgets.QLineEdit = QtWidgets.QLineEdit(self)
        self._parameter_mapping_edit: QtWidgets.QLineEdit = QtWidgets.QLineEdit(self)
        self._rebind_button: QtWidgets.QPushButton = QtWidgets.QPushButton(
            self.tr("Rebind selected template"),
            self,
        )
        self._rebind_group: QtWidgets.QGroupBox = QtWidgets.QGroupBox(
            self.tr("Rebind an existing template"),
            self,
        )
        self._build_ui()

    def _ensure_local_llvm_selection(self) -> NativeCompilerSelection | None:
        """Prepare a selected LLVM worker before saving a machine-local choice.

        :return: Usable compiler snapshot, or None when folder selection is cancelled.
        """

        saved_selection: NativeCompilerSelection | None = load_saved_local_llvm_selection()
        if saved_selection is not None:
            # An existing profile may have a new tool hash. Preparation will
            # verify its current cache or safely build only an absent cache.
            prepare_manufacturer_native_runtime(selection=saved_selection)
            return saved_selection
        else:
            pass
        binary_directory_text: str = QtWidgets.QFileDialog.getExistingDirectory(
            self,
            self.tr("Choose the LLVM bin directory"),
            str(Path.home()),
        )
        if len(binary_directory_text) == 0:
            return None
        else:
            binary_root: Path = Path(binary_directory_text)
        if sys.platform == "win32":
            support_directory_text: str = QtWidgets.QFileDialog.getExistingDirectory(
                self,
                self.tr("Choose the MinGW/UCRT support directory"),
                str(binary_root.parent),
            )
            if len(support_directory_text) == 0:
                return None
            else:
                support_root: Path | None = Path(support_directory_text)
        else:
            support_root = None
        selection: NativeCompilerSelection = NativeCompilerSelection(
            NativeCompilerFramework.LOCAL_LLVM,
            binary_root=binary_root,
            support_root=support_root,
        )
        # Folder existence alone cannot prove that Windows can link. A worker
        # build establishes usability before persisting this choice.
        prepare_manufacturer_native_runtime(selection=selection)
        save_local_llvm_selection(selection)
        return selection

    def _build_ui(self) -> None:
        """Create the compact import form and its actions.

        :return: None.
        """
        title: str
        if self._provider is None:
            title = self.tr("Import manufacturer native model")
        else:
            title = self.tr("Manufacturer native model variants")
        self.setWindowTitle(title)
        self.resize(720, 430)

        layout: QtWidgets.QVBoxLayout = QtWidgets.QVBoxLayout(self)
        explanation: QtWidgets.QLabel = QtWidgets.QLabel(
            self.tr(
                "Select the manufacturer contract and its precompiled platform library. "
                "VeraGrid validates and runs the binary in an isolated worker."
            ), self)
        explanation.setWordWrap(True)
        layout.addWidget(explanation)

        form: QtWidgets.QFormLayout = QtWidgets.QFormLayout()
        path_row: QtWidgets.QHBoxLayout = QtWidgets.QHBoxLayout()
        path_row.addWidget(self._path_edit)
        browse_button: QtWidgets.QPushButton = QtWidgets.QPushButton(self.tr("Browse..."), self)
        browse_button.clicked.connect(self._browse_binary)
        path_row.addWidget(browse_button)
        form.addRow(self.tr("Manufacturer binary"), path_row)

        self._interface_combo.addItem(
            "IEEE/CIGRE 1.1.0.0",
            NativeModelInterface.IEEE_CIGRE_V1_1,
        )
        self._interface_combo.addItem(
            "IEEE/CIGRE 1.0.0.0 (legacy)",
            NativeModelInterface.IEEE_CIGRE_V1_0,
        )
        self._interface_combo.addItem(
            "IEC ESE (internal solver)",
            NativeModelInterface.IEC_ESE,
        )
        if self._provider is None:
            pass
        else:
            provider_index: int = self._interface_combo.findData(self._provider.native_interface)
            if provider_index < 0:
                raise ValueError("Existing provider uses an unsupported native interface")
            else:
                self._interface_combo.setCurrentIndex(provider_index)
                self._interface_combo.setEnabled(False)
        self._interface_combo.currentIndexChanged.connect(self._update_interface_controls)
        form.addRow(self.tr("Manufacturer interface"), self._interface_combo)
        self._platform_combo.addItem("Windows x64 (.dll)", IeeeCigreDllPlatform.WINDOWS_X64)
        self._platform_combo.addItem("Windows x86 (.dll)", IeeeCigreDllPlatform.WINDOWS_X86)
        self._platform_combo.addItem("Linux x64 (.so)", IeeeCigreDllPlatform.LINUX_X64)
        form.addRow(self.tr("Platform variant"), self._platform_combo)
        layout.addLayout(form)

        layout.addWidget(self._no_late_loading_check)
        layout.addWidget(self._instance_isolation_check)
        self._update_interface_controls()
        declarations_help: QtWidgets.QLabel = QtWidgets.QLabel(
            self.tr(
                "Both declarations are part of the manufacturer delivery contract and are required before qualification."
            ), self)
        declarations_help.setWordWrap(True)
        layout.addWidget(declarations_help)

        self._status_view.setReadOnly(True)
        self._status_view.setPlaceholderText(self._current_provider_status())
        layout.addWidget(self._status_view)
        self._configure_rebind(layout)

        buttons: QtWidgets.QDialogButtonBox = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok
            | QtWidgets.QDialogButtonBox.StandardButton.Cancel,
            parent=self,
        )
        ok_button: QtWidgets.QPushButton = buttons.button(QtWidgets.QDialogButtonBox.StandardButton.Ok)
        if self._provider is None:
            ok_button.setText(self.tr("Inspect and import"))
        else:
            ok_button.setText(self.tr("Inspect and attach variant"))
        buttons.accepted.connect(self._inspect_and_store)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _configure_rebind(self, layout: QtWidgets.QVBoxLayout) -> None:
        """Build explicit provider and ordinal mapping controls.

        :param layout: Dialog layout that owns the rebind group.
        :return: None.
        """
        form: QtWidgets.QFormLayout = QtWidgets.QFormLayout(self._rebind_group)
        form.addRow(self.tr("Template"), self._rebind_consumer_combo)
        form.addRow(self.tr("Destination provider"), self._rebind_destination_combo)
        self._input_mapping_edit.setPlaceholderText(self.tr("Example: 1,0"))
        self._output_mapping_edit.setPlaceholderText(self.tr("Example: 0,1"))
        self._parameter_mapping_edit.setPlaceholderText(self.tr("Example: 2,0,1"))
        ordinal_help_text: str = self.tr(
            "Each comma-separated value is the destination ordinal for the source "
            "ordinal at that position. Example: 1,0 maps source 0 to destination 1 "
            "and source 1 to destination 0."
        )
        ordinal_help: QtWidgets.QLabel = QtWidgets.QLabel(ordinal_help_text, self._rebind_group)
        ordinal_help.setWordWrap(True)
        self._input_mapping_edit.setToolTip(ordinal_help_text)
        self._output_mapping_edit.setToolTip(ordinal_help_text)
        self._parameter_mapping_edit.setToolTip(ordinal_help_text)
        form.addRow(self.tr("Input destination ordinals"), self._input_mapping_edit)
        form.addRow(self.tr("Output destination ordinals"), self._output_mapping_edit)
        form.addRow(self.tr("Parameter destination ordinals"), self._parameter_mapping_edit)
        form.addRow(ordinal_help)
        form.addRow(self._rebind_button)
        layout.addWidget(self._rebind_group)
        self._rebind_button.clicked.connect(self._rebind_selected_consumer)

        if self._provider is None:
            self._rebind_group.setVisible(False)
        else:
            destination: ManufacturerNativeModel
            for destination in self._assets.manufacturer_native_models:
                if destination is not self._provider:
                    self._rebind_destination_combo.addItem(
                        destination.name,
                        destination,
                    )
                else:
                    pass
            self._refresh_rebind_consumers()

    def _refresh_rebind_consumers(self) -> None:
        """Reload templates that currently reference the displayed provider.

        :return: None.
        """
        self._rebind_consumer_combo.clear()
        if self._provider is None:
            pass
        else:
            consumer: RmsModelTemplate | EmtModelTemplate
            for consumer in self._assets.get_manufacturer_native_consumers(self._provider):
                self._rebind_consumer_combo.addItem(consumer.name, consumer)
        rebind_available: bool = (
            self._provider is not None
            and self._rebind_consumer_combo.count() > 0
            and self._rebind_destination_combo.count() > 0
        )
        self._rebind_group.setVisible(rebind_available)
        self._rebind_button.setEnabled(rebind_available)

    def _build_rebind_plan(self) -> ManufacturerNativeRebindPlan:
        """Build one IO-validated plan from explicit ordinal permutations.

        :return: Complete transient replacement plan.
        """
        source: ManufacturerNativeModel | None = self._provider
        destination_raw: object = self._rebind_destination_combo.currentData()
        consumer_raw: object = self._rebind_consumer_combo.currentData()
        if (
                source is None
                or not isinstance(destination_raw, ManufacturerNativeModel)
                or not isinstance(consumer_raw, (RmsModelTemplate, EmtModelTemplate))
        ):
            raise ValueError("Select a source, destination and consumer")
        else:
            destination: ManufacturerNativeModel = destination_raw
            consumer: RmsModelTemplate | EmtModelTemplate = consumer_raw

        mapping_edits: Tuple[QtWidgets.QLineEdit, ...] = (
            self._input_mapping_edit,
            self._output_mapping_edit,
            self._parameter_mapping_edit,
        )
        mappings: list[Tuple[int, ...]] = list()
        mapping_edit: QtWidgets.QLineEdit
        for mapping_edit in mapping_edits:
            mapping_text: str = mapping_edit.text().strip()
            if len(mapping_text) == 0:
                mappings.append(tuple())
            else:
                ordinal_texts: list[str] = mapping_text.split(",")
                ordinals: list[int] = list()
                ordinal_text: str
                for ordinal_text in ordinal_texts:
                    normalized_ordinal: str = ordinal_text.strip()
                    if len(normalized_ordinal) == 0:
                        raise ValueError("Ordinal mappings cannot contain empty entries")
                    else:
                        ordinals.append(int(normalized_ordinal))
                mappings.append(tuple(ordinals))

        if isinstance(consumer, RmsModelTemplate):
            consumer_mode: IeeeCigreDllModelMode = IeeeCigreDllModelMode.RMS
        else:
            consumer_mode = IeeeCigreDllModelMode.EMT
        occurrence_rows: list[
            Tuple[IeeeCigreDllModelMode, ManufacturerNativeControllerLogic]
        ] = list()
        block: Block
        for block in consumer.block.get_all_blocks():
            logic: ProceduralLogicBase
            for logic in block.procedural_logic:
                if isinstance(logic, ManufacturerNativeControllerLogic):
                    if logic.provider_idtag == source.idtag:
                        occurrence_rows.append((consumer_mode, logic))
                    else:
                        pass
                else:
                    pass

        return build_manufacturer_native_rebind_plan(
            consumer_idtag=consumer.idtag,
            source_provider_idtag=source.idtag,
            destination_provider_idtag=destination.idtag,
            source_model_info_sha256=source.model_info_sha256,
            destination_model_info_sha256=destination.model_info_sha256,
            source_model_info=decode_manufacturer_native_model_info(source.model_info),
            destination_model_info=decode_manufacturer_native_model_info(
                destination.model_info
            ),
            occurrences=tuple(occurrence_rows),
            input_port_mapping=mappings[0],
            output_port_mapping=mappings[1],
            parameter_mapping=mappings[2],
        )

    def _rebind_selected_consumer(self) -> None:
        """Validate and atomically rebind the selected template.

        :return: None.
        """
        source: ManufacturerNativeModel | None = self._provider
        destination_raw: object = self._rebind_destination_combo.currentData()
        consumer_raw: object = self._rebind_consumer_combo.currentData()
        if (
                source is None
                or not isinstance(destination_raw, ManufacturerNativeModel)
                or not isinstance(consumer_raw, (RmsModelTemplate, EmtModelTemplate))
        ):
            QtWidgets.QMessageBox.warning(
                self,
                self.windowTitle(),
                self.tr("Select a source, destination and template."),
            )
            return
        else:
            destination: ManufacturerNativeModel = destination_raw
            consumer: RmsModelTemplate | EmtModelTemplate = consumer_raw
        try:
            if source.model_info_sha256 == destination.model_info_sha256:
                plan: ManufacturerNativeRebindPlan | None = None
            else:
                plan = self._build_rebind_plan()
            self._assets.rebind_manufacturer_native_consumer(
                consumer=consumer,
                source=source,
                destination=destination,
                plan=plan,
            )
        except (TypeError, ValueError) as exception:
            QtWidgets.QMessageBox.warning(self, self.windowTitle(), str(exception))
            return
        self._status_view.setPlainText(
            self.tr("Rebound {consumer} to {provider}.").format(
                consumer=consumer.name,
                provider=destination.name,
            )
        )
        self._refresh_rebind_consumers()

    def _selected_interface(self) -> NativeModelInterface:
        """Return the explicitly selected manufacturer ABI.

        :return: Selected native interface.
        """
        interface_raw: object = self._interface_combo.currentData()
        if isinstance(interface_raw, NativeModelInterface):
            return interface_raw
        else:
            raise TypeError("The selected manufacturer interface is invalid")

    def _update_interface_controls(self) -> None:
        """Enable the shared-state attestation only for IEEE/CIGRE 1.1.

        :return: None.
        """
        native_interface: NativeModelInterface = self._selected_interface()
        shared_worker: bool = native_interface == NativeModelInterface.IEEE_CIGRE_V1_1
        self._instance_isolation_check.setEnabled(shared_worker)
        if shared_worker:
            pass
        else:
            self._instance_isolation_check.setChecked(False)

    def _selected_platform(self) -> IeeeCigreDllPlatform:
        """Return the exact selected platform enum.

        :return: Selected platform variant.
        """
        platform_raw: object = self._platform_combo.currentData()
        if isinstance(platform_raw, IeeeCigreDllPlatform):
            return platform_raw
        else:
            raise TypeError("The selected native platform is invalid")

    def _browse_binary(self) -> None:
        """Select one manufacturer supplied binary from disk.

        :return: None.
        """
        platform: IeeeCigreDllPlatform = self._selected_platform()
        if platform in (
                IeeeCigreDllPlatform.WINDOWS_X86,
                IeeeCigreDllPlatform.WINDOWS_X64,
        ):
            file_filter: str = self.tr("Windows libraries (*.dll)")
        else:
            file_filter = self.tr("Linux libraries (*.so)")
        selected_path: str
        selected_filter: str
        selected_path, selected_filter = QtWidgets.QFileDialog.getOpenFileName(
            self,
            self.tr("Select manufacturer library"),
            self._path_edit.text(),
            file_filter,
        )
        if len(selected_filter) >= 0 and len(selected_path) > 0:
            self._path_edit.setText(selected_path)
        else:
            pass

    def _current_provider_status(self) -> str:
        """Describe the variants already owned by an existing provider.

        :return: Human readable provider status.
        """
        if self._provider is None:
            return self.tr("No provider has been imported yet.")
        else:
            lines: list[str] = [self.tr("Provider: {name}").format(name=self._provider.name)]
        platform: IeeeCigreDllPlatform
        for platform in (
                IeeeCigreDllPlatform.WINDOWS_X64,
                IeeeCigreDllPlatform.WINDOWS_X86,
                IeeeCigreDllPlatform.LINUX_X64,
        ):
            variant = self._provider.get_platform_variant(platform)
            if variant is None:
                lines.append(self.tr("{platform}: missing").format(platform=platform.value))
            else:
                lines.append(self.tr("{platform}: {status}, SHA-256 {digest}").format(
                    platform=platform.value,
                    status=variant.verification_status.value,
                    digest=variant.content_sha256,
                ))
        return "\n".join(lines)

    def _inspect_and_store(self) -> None:
        """Run Engine qualification and mutate Assets only after success.

        :return: None.
        """
        source_path: Path = Path(self._path_edit.text()).expanduser()
        if source_path.is_file():
            pass
        else:
            QtWidgets.QMessageBox.warning(
                self, self.windowTitle(), self.tr("Choose an existing manufacturer binary."))
            return
        native_interface: NativeModelInterface = self._selected_interface()
        isolation_required: bool = native_interface == NativeModelInterface.IEEE_CIGRE_V1_1
        declarations_valid: bool = (
            self._no_late_loading_check.isChecked()
            and (not isolation_required or self._instance_isolation_check.isChecked())
        )
        if declarations_valid:
            pass
        else:
            QtWidgets.QMessageBox.warning(
                self,
                self.windowTitle(),
                self.tr("Complete the manufacturer declarations required by the selected interface."),
            )
            return

        self._status_view.setPlainText(self.tr("Inspecting the binary in an isolated worker..."))
        QtWidgets.QApplication.processEvents()
        is_new_import: bool = self._provider is None
        try:
            platform: IeeeCigreDllPlatform = self._selected_platform()
            # The packaged Windows x86 worker is already qualified and must not
            # force an unrelated host-x64 compiler download. Other native
            # platforms prepare the host worker only after the analyst commits
            # the import, keeping dialog open/cancel independent of a compiler.
            if platform == IeeeCigreDllPlatform.WINDOWS_X86:
                compiler_selection: NativeCompilerSelection | None = None
            else:
                compiler_selection = self._ensure_local_llvm_selection()
                if compiler_selection is None:
                    self._status_view.setPlainText(
                        self.tr("LLVM selection was cancelled; the manufacturer model was not imported.")
                    )
                    return
                else:
                    pass
            if is_new_import:
                provider, rms_templates, emt_templates = import_manufacturer_native_model(
                    assets=self._assets,
                    source_path=source_path,
                    platform=platform,
                    native_interface=native_interface,
                    vendor_declares_no_late_loading=True,
                    vendor_declares_instance_isolation=self._instance_isolation_check.isChecked(),
                    compiler_selection=compiler_selection,
                )
                self._provider = provider
                status: str = self.tr(
                    "Qualified and imported {name}. Created {rms} RMS and {emt} EMT template(s)."
                ).format(name=provider.name, rms=len(rms_templates), emt=len(emt_templates))
            else:
                variant = attach_manufacturer_native_binary_variant(
                    provider=self._provider,
                    source_path=source_path,
                    platform=platform,
                    vendor_declares_no_late_loading=True,
                    vendor_declares_instance_isolation=self._instance_isolation_check.isChecked(),
                    compiler_selection=compiler_selection,
                )
                status = self.tr("Qualified and attached {platform}: {digest}").format(
                    platform=variant.platform.value,
                    digest=variant.content_sha256,
                )
        except Exception as exception:
            self._status_view.setPlainText(str(exception))
            QtWidgets.QMessageBox.warning(self, self.windowTitle(), str(exception))
            return
        self._status_view.setPlainText(status + "\n\n" + self._current_provider_status())
        if is_new_import:
            rms_names: str = ", ".join(template.name for template in rms_templates)
            emt_names: str = ", ".join(template.name for template in emt_templates)
            if len(rms_names) == 0:
                rms_names = self.tr("None")
            else:
                pass
            if len(emt_names) == 0:
                emt_names = self.tr("None")
            else:
                pass
            summary: str = self.tr(
                "Provider: {provider}\n"
                "Platform: {platform}\n"
                "RMS templates created: {rms}\n"
                "EMT templates created: {emt}"
            ).format(
                provider=self._provider.name,
                platform=platform.value,
                rms=rms_names,
                emt=emt_names,
            )
        else:
            summary = self.tr(
                "Provider: {provider}\n"
                "Platform attached: {platform}\n"
                "Templates created: None (existing templates retained)."
            ).format(
                provider=self._provider.name,
                platform=platform.value,
            )
        QtWidgets.QMessageBox.information(
            self,
            self.tr("Manufacturer native model ready"),
            summary,
        )
        self.accept()
