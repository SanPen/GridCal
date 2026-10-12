# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations
from VeraGridEngine.enumerations import InterfaceType, IntegrationMethod, TargetPlatform

from pathlib import Path
import platform
import re
import uuid

from VeraGridEngine.enumerations import FmiVersion


def parse_declared_fmi_version(value: str) -> FmiVersion:
    """Resolve one model-description version declaration.

    :param value: FMI version text.
    :return: Supported FMI family.
    """
    if not isinstance(value, str):
        raise TypeError("The FMI version declaration must be text")
    if value == FmiVersion.FMI_1_0.value:
        return FmiVersion.FMI_1_0
    if value == FmiVersion.FMI_2_0.value:
        return FmiVersion.FMI_2_0
    if re.fullmatch(r"3\.0(?:\.(?:0|[1-9][0-9]*))?", value, flags=re.ASCII) is not None:
        return FmiVersion.FMI_3_0
    raise ValueError(f"Invalid or unsupported FMI version declaration: {value!r}")


def normalize_fmi_export_version(value: FmiVersion | str) -> FmiVersion:
    """Normalize one public export-version selection.

    :param value: FMI version enum or canonical text.
    :return: Canonical FMI version.
    """
    if isinstance(value, FmiVersion):
        return value
    if isinstance(value, str):
        normalized_value: str = value.strip()
        for version in FmiVersion:
            if normalized_value == version.value:
                return version
        else:
            pass
        raise ValueError(f"Unsupported FMI version selection: {normalized_value!r}")
    else:
        raise TypeError("FMI export-version selection must be text or FmiVersion")


def select_target_platform(system_name: str, machine_name: str) -> TargetPlatform:
    """Select the supported native FMU platform.

    :param system_name: Operating-system name.
    :param machine_name: Architecture name.
    :return: Target platform.
    """
    system: str = system_name.strip().lower()
    machine: str = machine_name.strip().lower()
    if system == "windows" and machine in {"amd64", "x86_64"}:
        return TargetPlatform.WIN64
    if system == "linux" and machine in {"amd64", "x86_64"}:
        return TargetPlatform.LINUX64
    if system == "darwin" and machine in {"amd64", "x86_64"}:
        return TargetPlatform.DARWIN64
    if system == "darwin" and machine in {"arm64", "aarch64"}:
        return TargetPlatform.DARWIN_ARM64
    raise RuntimeError(f"Unsupported FMU host platform: {system_name}/{machine_name}")


def detect_target_platform() -> TargetPlatform:
    """Detect the current native FMU platform.

    :return: Current target platform.
    """
    return select_target_platform(platform.system(), platform.machine())


def library_suffix(target_platform: TargetPlatform) -> str:
    """Return the native shared-library suffix.

    :param target_platform: FMU target platform.
    :return: Shared-library suffix.
    """
    if target_platform == TargetPlatform.WIN64:
        return ".dll"
    if target_platform == TargetPlatform.LINUX64:
        return ".so"
    return ".dylib"


def binary_directory(target_platform: TargetPlatform, fmi_version: FmiVersion) -> str:
    """Return the standard FMU binary directory.

    :param target_platform: FMU target platform.
    :param fmi_version: FMI family.
    :return: Relative binary directory.
    """
    if fmi_version in {FmiVersion.FMI_1_0, FmiVersion.FMI_2_0}:
        if target_platform == TargetPlatform.WIN64:
            return "win64"
        if target_platform == TargetPlatform.LINUX64:
            return "linux64"
        return "darwin64"
    if target_platform == TargetPlatform.WIN64:
        return "x86_64-windows"
    if target_platform == TargetPlatform.LINUX64:
        return "x86_64-linux"
    if target_platform == TargetPlatform.DARWIN64:
        return "x86_64-darwin"
    return "aarch64-darwin"


def sanitize_identifier(name: str) -> str:
    """
    Convert one user-facing model name into a valid C/FMI identifier.

    :param name: Requested model identifier or model name.
    :return: Sanitized identifier.
    """

    text: str = re.sub(r"[^0-9A-Za-z_]", "_", name)
    if len(text) == 0:
        text = "GeneratedModel"
    else:
        pass
    if text[0].isdigit():
        text = f"M_{text}"
    else:
        pass
    return text


def build_export_guid() -> str:
    """
    Create a fresh GUID for one exported FMU.

    :return: GUID string.
    """

    return str(uuid.uuid4())


class ExportConfig:
    """
    Lightweight export configuration for FMI 2.0 Co-Simulation packaging.

    The configuration is explicit on purpose because the FMU exporter needs stable
    values for naming, staging, numerical settings, and host-platform packaging.
    """

    __slots__ = (
        "model_name",
        "output_path",
        "fmi_version",
        "guid",
        "interface_type",
        "target_platform",
        "integration_method",
        "relative_tolerance",
        "fixed_step",
        "build_dir",
        "staging_dir",
        "model_identifier",
        "debug",
        "keep_build_dir",
        "include_snapshot_resource",
        "include_export_model_resource",
        "compile_binary",
        "max_newton_iterations",
        "newton_tolerance",
    )

    def __init__(self,
                 model_name: str,
                 output_path: Path | str,
                 guid: str | None = None,
                 interface_type: InterfaceType = InterfaceType.CO_SIMULATION,
                 target_platform: TargetPlatform | None = None,
                 integration_method: IntegrationMethod = IntegrationMethod.BACKWARD_EULER,
                 relative_tolerance: float = 1e-6,
                 fixed_step: float = 1e-4,
                 build_dir: Path | str | None = None,
                 staging_dir: Path | str | None = None,
                 model_identifier: str | None = None,
                 debug: bool = False,
                 keep_build_dir: bool = False,
                 include_snapshot_resource: bool = True,
                 include_export_model_resource: bool = True,
                 compile_binary: bool = True,
                 max_newton_iterations: int = 10,
                 newton_tolerance: float = 1e-9,
                 fmi_version: FmiVersion | str = FmiVersion.FMI_2_0) -> None:
        """
        Build one explicit FMU export configuration.

        :param model_name: User-visible FMU model name.
        :param output_path: Final `.fmu` output path.
        :param guid: Optional explicit FMU GUID.
        :param interface_type: FMI interface type.
        :param target_platform: Target FMI binary folder.
        :param integration_method: Generated runtime integration method.
        :param relative_tolerance: Default Model Exchange relative tolerance.
        :param fixed_step: Default fixed communication step.
        :param build_dir: Optional persistent build directory.
        :param staging_dir: Optional staging directory used before packaging.
        :param model_identifier: Optional explicit FMI model identifier.
        :param debug: Whether to keep debug-friendly generation settings.
        :param keep_build_dir: Preserve the generated build directory.
        :param include_snapshot_resource: Include the serialized source snapshot.
        :param include_export_model_resource: Include the export IR resource.
        :param compile_binary: Compile the FMU binary.
        :param max_newton_iterations: Maximum nonlinear iterations in the runtime solver.
        :param newton_tolerance: Nonlinear solver tolerance.
        :param fmi_version: Canonical FMI family selected for export.
        :return: None.
        """

        self.model_name: str = model_name
        self.output_path: Path = Path(output_path)
        self.fmi_version: FmiVersion = normalize_fmi_export_version(fmi_version)
        if guid is None:
            self.guid: str = build_export_guid()
        else:
            self.guid = guid
        self.interface_type: InterfaceType = interface_type
        if target_platform is None:
            self.target_platform: TargetPlatform = detect_target_platform()
        else:
            self.target_platform = target_platform
        self.integration_method: IntegrationMethod = integration_method
        self.relative_tolerance: float = relative_tolerance
        self.fixed_step: float = fixed_step
        if build_dir is None:
            self.build_dir: Path | None = None
        else:
            self.build_dir = Path(build_dir)
        if staging_dir is None:
            self.staging_dir: Path | None = None
        else:
            self.staging_dir = Path(staging_dir)
        self.model_identifier: str = sanitize_identifier(model_identifier or model_name)
        self.debug: bool = debug
        self.keep_build_dir: bool = keep_build_dir
        self.include_snapshot_resource: bool = include_snapshot_resource
        self.include_export_model_resource: bool = include_export_model_resource
        self.compile_binary: bool = compile_binary
        self.max_newton_iterations: int = max_newton_iterations
        self.newton_tolerance: float = newton_tolerance
        self._validate()

    def _validate(self) -> None:
        """
        Validate the numerical and filesystem settings for one export configuration.

        :return: None.
        """

        if self.fmi_version in (
            FmiVersion.FMI_1_0,
            FmiVersion.FMI_2_0,
            FmiVersion.FMI_3_0,
        ):
            pass
        else:
            raise NotImplementedError(
                f"FMI {self.fmi_version.value} FMU export is not connected yet"
            )
        if self.fixed_step <= 0.0:
            raise ValueError("fixed_step must be positive")
        else:
            pass
        if self.relative_tolerance <= 0.0:
            raise ValueError("relative_tolerance must be positive")
        else:
            pass
        if self.max_newton_iterations <= 0:
            raise ValueError("max_newton_iterations must be positive")
        else:
            pass
        if self.newton_tolerance <= 0.0:
            raise ValueError("newton_tolerance must be positive")
        else:
            pass

    @property
    def output_dir(self) -> Path:
        """
        Return the directory that will contain the final `.fmu` file.

        :return: Output directory.
        """

        return self.output_path.parent

    @property
    def library_name(self) -> str:
        """
        Return the platform-specific shared-library file name.

        :return: Shared-library file name.
        """

        return f"{self.model_identifier}{library_suffix(self.target_platform)}"
