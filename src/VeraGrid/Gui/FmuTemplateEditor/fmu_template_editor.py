from __future__ import annotations

from pathlib import Path

from PySide6 import QtWidgets

from VeraGridEngine.Devices.Dynamic.fmu_template import FmuTemplate
from VeraGridEngine.Devices.multi_circuit import MultiCircuit
from VeraGridEngine.enumerations import DeviceType, FmuTemplateDomain, FmuTemplateMode
from VeraGridEngine.IO.fmu.model_description import FmuModelDescription
from VeraGridEngine.IO.fmu.model_description import read_fmu_model_description
from VeraGridEngine.IO.fmu.fmu_device_integration import configure_fmu_template, summarize_fmu_template_metadata


class FmuTemplateEditorDialog(QtWidgets.QDialog):
    """
    Minimal editor used to configure one reusable FMU template from a selected FMU file.
    """

    __slots__ = (
        "_circuit",
        "_template",
        "_project_directory",
        "_name_edit",
        "_path_edit",
        "_device_type_combo",
        "_domain_combo",
        "_mode_combo",
        "_metadata_view",
    )

    _SUPPORTED_DEVICE_TYPES: tuple[DeviceType, ...] = (
        DeviceType.LoadDevice,
        DeviceType.GeneratorDevice,
        DeviceType.BatteryDevice,
        DeviceType.ExternalGridDevice,
        DeviceType.CurrentInjectionDevice,
        DeviceType.LineDevice,
        DeviceType.Transformer2WDevice,
        DeviceType.VscDevice,
        DeviceType.HVDCLineDevice,
    )

    def __init__(self,
                 circuit: MultiCircuit,
                 template: FmuTemplate,
                 project_directory: str | None,
                 parent: QtWidgets.QWidget | None = None) -> None:
        """
        Build the FMU template editor dialog.

        :param circuit: Active circuit owning the RMS and EMT variable factories.
        :param template: Template instance being edited.
        :param project_directory: Current project directory used as browse base.
        :param parent: Parent Qt widget.
        """

        super().__init__(parent)
        self._circuit: MultiCircuit = circuit
        self._template: FmuTemplate = template
        self._project_directory: str | None = project_directory
        self._name_edit = QtWidgets.QLineEdit(self)
        self._path_edit = QtWidgets.QLineEdit(self)
        self._device_type_combo = QtWidgets.QComboBox(self)
        self._domain_combo = QtWidgets.QComboBox(self)
        self._mode_combo = QtWidgets.QComboBox(self)
        self._metadata_view = QtWidgets.QPlainTextEdit(self)
        self._build_ui()
        self._load_template_state()

    def _build_ui(self) -> None:
        """
        Build the dialog widgets and signal connections.

        :return: None.
        """

        self.setWindowTitle(self.tr("FMU Template Editor"))
        self.resize(760, 420)

        form_layout = QtWidgets.QFormLayout()
        path_layout = QtWidgets.QHBoxLayout()
        browse_button = QtWidgets.QPushButton(self.tr("Browse..."), self)
        path_layout.addWidget(self._path_edit)
        path_layout.addWidget(browse_button)

        device_type: DeviceType
        for device_type in self._SUPPORTED_DEVICE_TYPES:
            self._device_type_combo.addItem(device_type.value, device_type)

        domain: FmuTemplateDomain
        for domain in FmuTemplateDomain:
            self._domain_combo.addItem(domain.value.upper(), domain)

        mode: FmuTemplateMode
        for mode in FmuTemplateMode:
            self._mode_combo.addItem(mode.value, mode)

        self._metadata_view.setReadOnly(True)
        self._metadata_view.setPlainText(
            self.tr("Choose an FMU archive to load its metadata and build the visual block.")
        )

        form_layout.addRow(self.tr("Name"), self._name_edit)
        form_layout.addRow(self.tr("FMU file"), path_layout)
        form_layout.addRow(self.tr("Device type"), self._device_type_combo)
        form_layout.addRow(self.tr("Domain"), self._domain_combo)
        form_layout.addRow(self.tr("Mode"), self._mode_combo)
        form_layout.addRow(self.tr("Metadata"), self._metadata_view)

        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok | QtWidgets.QDialogButtonBox.StandardButton.Cancel,
            self,
        )

        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.addLayout(form_layout)
        main_layout.addWidget(buttons)

        browse_button.clicked.connect(self._browse_fmu_file)
        self._path_edit.editingFinished.connect(self._reload_metadata_from_editor_path)
        buttons.accepted.connect(self._accept_dialog)
        buttons.rejected.connect(self.reject)

    def _load_template_state(self) -> None:
        """
        Populate the dialog from the current template state.

        :return: None.
        """

        self._name_edit.setText(self._template.name)
        self._path_edit.setText(self._template.fmu_relative_path)
        self._select_combo_value(self._device_type_combo, self._template.tpe)
        self._select_combo_value(self._domain_combo, self._template.domain)
        self._select_combo_value(self._mode_combo, self._template.mode)

        initial_path = self._resolve_fmu_path(self._template.fmu_relative_path)
        if initial_path is not None and initial_path.exists():
            self._render_metadata(initial_path)
        else:
            pass

    def _select_combo_value(self, combo: QtWidgets.QComboBox, value: object) -> None:
        """
        Select one combo-box item by its stored user data.

        :param combo: Target combo box.
        :param value: Value stored in the combo item.
        :return: None.
        """

        index = combo.findData(value)
        if index >= 0:
            combo.setCurrentIndex(index)
        else:
            pass

    def _resolve_fmu_path(self, path_text: str) -> Path | None:
        """
        Resolve one editor path into an absolute FMU path when possible.

        :param path_text: Path text from the editor or template.
        :return: Absolute FMU path when resolvable.
        """

        normalized_text = str(path_text).strip()
        if len(normalized_text) == 0:
            return None
        else:
            candidate = Path(normalized_text).expanduser()
            if candidate.is_absolute():
                return candidate.resolve()
            else:
                if self._project_directory is None:
                    return candidate.resolve()
                else:
                    return (Path(self._project_directory) / candidate).resolve()

    def _browse_fmu_file(self) -> None:
        """
        Open a file chooser and update the selected FMU path.

        :return: None.
        """

        initial_directory: str
        current_path = self._resolve_fmu_path(self._path_edit.text())
        if current_path is not None and current_path.exists():
            initial_directory = str(current_path.parent)
        else:
            if self._project_directory is None:
                initial_directory = ""
            else:
                initial_directory = self._project_directory

        file_name, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            self.tr("Select FMU file"),
            initial_directory,
            self.tr("FMU files (*.fmu)"),
        )
        if len(file_name) > 0:
            self._path_edit.setText(file_name)
            self._render_metadata(Path(file_name).resolve())
        else:
            pass

    def _sync_mode_combo_with_metadata(self, metadata: FmuModelDescription) -> None:
        """
        Select the first supported mode if the current choice is not available in the FMU.

        :param metadata: Parsed FMU metadata.
        :return: None.
        """

        supported_modes: list[FmuTemplateMode] = list()
        if metadata.get_supports_co_simulation():
            supported_modes.append(FmuTemplateMode.CO_SIMULATION)
        else:
            pass
        if metadata.get_supports_model_exchange():
            supported_modes.append(FmuTemplateMode.MODEL_EXCHANGE)
        else:
            pass

        current_mode = self._mode_combo.currentData()
        if current_mode in supported_modes:
            pass
        else:
            if len(supported_modes) > 0:
                self._select_combo_value(self._mode_combo, supported_modes[0])
            else:
                pass

    def _render_metadata(self, fmu_path: Path) -> None:
        """
        Read the FMU metadata and display a detailed summary.

        :param fmu_path: Selected FMU archive.
        :return: None.
        """

        metadata = read_fmu_model_description(fmu_path)
        self._sync_mode_combo_with_metadata(metadata)
        self._metadata_view.setPlainText(summarize_fmu_template_metadata(metadata))
        if len(self._name_edit.text().strip()) == 0:
            self._name_edit.setText(metadata.model_name)
        else:
            pass

    def _reload_metadata_from_editor_path(self) -> None:
        """
        Reload FMU metadata from the path currently written in the editor.

        :return: None.
        """

        fmu_path = self._resolve_fmu_path(self._path_edit.text())
        if fmu_path is None:
            self._metadata_view.setPlainText(
                self.tr("Choose an FMU archive to load its metadata and build the visual block.")
            )
        else:
            if fmu_path.exists():
                self._render_metadata(fmu_path)
            else:
                self._metadata_view.setPlainText(
                    self.tr("FMU file not found:\n{path}").format(path=fmu_path)
                )

    def _accept_dialog(self) -> None:
        """
        Validate the editor state and store the resulting FMU template.

        :return: None.
        """

        fmu_path = self._resolve_fmu_path(self._path_edit.text())
        if fmu_path is None:
            QtWidgets.QMessageBox.warning(
                self,
                self.tr("FMU Template Editor"),
                self.tr("Choose an FMU file first."),
            )
            return
        else:
            if not fmu_path.exists():
                QtWidgets.QMessageBox.warning(
                    self,
                    self.tr("FMU Template Editor"),
                    self.tr("FMU file not found:\n{path}").format(path=fmu_path),
                )
                return
            else:
                pass

        device_tpe = self._device_type_combo.currentData()
        domain = self._domain_combo.currentData()
        mode = self._mode_combo.currentData()
        template_name = self._name_edit.text().strip()

        try:
            configure_fmu_template(
                template=self._template,
                var_factory=self._circuit.var_factory,
                fmu_path=fmu_path,
                device_tpe=device_tpe,
                domain=domain,
                mode=mode,
                template_name=template_name,
            )
        except Exception as exc:
            QtWidgets.QMessageBox.warning(self, self.tr("FMU Template Editor"), str(exc))
            return

        self.accept()
