# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations

from pathlib import Path
from typing import Tuple

from VeraGridEngine.Devices.assets import Assets
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Devices.Dynamic.manufacturer_native_model import (
    ManufacturerNativeBinarySource,
    ManufacturerNativeBinaryVariant,
    ManufacturerNativeModel,
)
from VeraGridEngine.Devices.Dynamic.rms_template import RmsModelTemplate
from VeraGridEngine.enumerations import (
    IeeeCigreDllModelMode,
    IeeeCigreDllPlatform,
    NativeModelInterface,
)
from VeraGridEngine.IO.manufacturer_native.inspection import (
    ManufacturerNativeInspectionLimits,
    ManufacturerNativeInspectionResult,
    inspect_manufacturer_native,
)
from VeraGridEngine.IO.native_compiler.compiler_interface import NativeCompilerSelection
from VeraGridEngine.Utils.procedural_logic import (
    IeeeCigreDllSignalBinding,
    ManufacturerNativeControllerLogic,
)
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.symbolic import Const, Var


def _signal_variable_name(direction: str,
                          signal_name: str,
                          port_ordinal: int,
                          element_ordinal: int,
                          width: int) -> str:
    """Create a unique stable Block variable name without storing metadata.

    :param direction: ``in`` or ``out`` interface direction.
    :param signal_name: Manufacturer signal name used only for readability.
    :param port_ordinal: Stable ModelInfo port ordinal.
    :param element_ordinal: Stable array element ordinal.
    :param width: Declared signal width.
    :return: Unique symbolic name.
    """
    suffix: str = "" if width == 1 else "_" + str(element_ordinal)
    return "native_" + direction + "_" + str(port_ordinal) + "_" + signal_name + suffix


def _build_native_block(result: ManufacturerNativeInspectionResult) -> Block:
    """Build the ordinary composable Block projection of one provider.

    :param result: Fully qualified inspection evidence.
    :return: Block with input/output Vars and one provider reference.
    """
    input_vars: list[Var] = list()
    output_vars: list[Var] = list()
    mode_dict: dict[Var, Const] = dict()
    bindings: list[IeeeCigreDllSignalBinding] = list()
    port_ordinal: int
    signal = None
    for port_ordinal, signal in enumerate(result.model_info.input_ports):
        element_ordinal: int
        for element_ordinal in range(signal.width):
            variable: Var = Var(name=_signal_variable_name(
                direction="in",
                signal_name=signal.name,
                port_ordinal=port_ordinal,
                element_ordinal=element_ordinal,
                width=signal.width,
            ))
            input_vars.append(variable)
            bindings.append(IeeeCigreDllSignalBinding(
                is_input=True,
                port_ordinal=port_ordinal,
                element_ordinal=element_ordinal,
                variable=variable,
            ))
    for port_ordinal, signal in enumerate(result.model_info.output_ports):
        for element_ordinal in range(signal.width):
            variable = Var(name=_signal_variable_name(
                direction="out",
                signal_name=signal.name,
                port_ordinal=port_ordinal,
                element_ordinal=element_ordinal,
                width=signal.width,
            ))
            output_vars.append(variable)
            mode_dict[variable] = Const(0.0)
            bindings.append(IeeeCigreDllSignalBinding(
                is_input=False,
                port_ordinal=port_ordinal,
                element_ordinal=element_ordinal,
                variable=variable,
            ))
    logic: ManufacturerNativeControllerLogic = ManufacturerNativeControllerLogic(
        provider_idtag="pending-provider",
        model_info_sha256=result.model_info_sha256,
        signal_bindings=tuple(bindings),
        parameter_overrides=tuple(),
        name=result.model_info.model_name,
    )
    return Block(
        in_vars=input_vars,
        out_vars=output_vars,
        mode_dict=mode_dict,
        procedural_logic=(logic,),
        is_decomposable=False,
        name=result.model_info.model_name,
    )


def _bind_block_provider(block: Block, provider: ManufacturerNativeModel) -> None:
    """Replace the temporary build identity with the registered provider idtag.

    :param block: Newly constructed native model Block.
    :param provider: Canonical provider that will precede the template.
    :return: None.
    """
    logic_raw = block.procedural_logic[0]
    if not isinstance(logic_raw, ManufacturerNativeControllerLogic):
        raise TypeError("Manufacturer Block is missing its native controller reference")
    else:
        logic_raw.provider_idtag = provider.idtag


def _build_templates(result: ManufacturerNativeInspectionResult,
                     provider: ManufacturerNativeModel) -> Tuple[Tuple[RmsModelTemplate, ...],
                                                                  Tuple[EmtModelTemplate, ...]]:
    """Create ordinary RMS/EMT templates supported by declared model mode.

    :param result: Fully qualified inspection evidence.
    :param provider: Canonical provider identity.
    :return: RMS and EMT template tuples.
    """
    rms_templates: list[RmsModelTemplate] = list()
    emt_templates: list[EmtModelTemplate] = list()
    if result.model_info.model_mode in (IeeeCigreDllModelMode.RMS, IeeeCigreDllModelMode.EMT_AND_RMS):
        rms_block: Block = _build_native_block(result)
        _bind_block_provider(rms_block, provider)
        rms_template: RmsModelTemplate = RmsModelTemplate(name=result.model_info.model_name + " RMS")
        rms_template.block = rms_block
        rms_templates.append(rms_template)
    else:
        pass
    if result.model_info.model_mode in (IeeeCigreDllModelMode.EMT, IeeeCigreDllModelMode.EMT_AND_RMS):
        emt_block: Block = _build_native_block(result)
        _bind_block_provider(emt_block, provider)
        emt_template: EmtModelTemplate = EmtModelTemplate(name=result.model_info.model_name + " EMT")
        emt_template.block = emt_block
        emt_templates.append(emt_template)
    else:
        pass
    if len(rms_templates) == 0 and len(emt_templates) == 0:
        raise ValueError("Manufacturer library supports neither RMS nor EMT")
    else:
        return tuple(rms_templates), tuple(emt_templates)


def import_manufacturer_native_model(assets: Assets,
                                source_path: str | Path,
                                platform: IeeeCigreDllPlatform,
                                native_interface: NativeModelInterface,
                                vendor_declares_no_late_loading: bool,
                                vendor_declares_instance_isolation: bool,
                                limits: ManufacturerNativeInspectionLimits | None = None,
                                compiler_selection: NativeCompilerSelection | None = None) -> Tuple[
                                    ManufacturerNativeModel,
                                    Tuple[RmsModelTemplate, ...],
                                    Tuple[EmtModelTemplate, ...],
                                ]:
    """Inspect completely, then atomically register provider before templates.

    :param assets: Canonical circuit asset owner.
    :param source_path: Manufacturer-supplied precompiled platform library.
    :param platform: Exact host platform variant.
    :param native_interface: Exact manufacturer ABI selected during import.
    :param vendor_declares_no_late_loading: Vendor dependency-policy attestation.
    :param vendor_declares_instance_isolation: Vendor per-Instance state attestation.
    :param limits: Optional finite inspection limits.
    :param compiler_selection: Explicit compiler snapshot for worker inspection.
    :return: Registered provider and created ordinary RMS/EMT templates.
    """
    result: ManufacturerNativeInspectionResult = inspect_manufacturer_native(
        source_path=source_path,
        platform=platform,
        native_interface=native_interface,
        vendor_declares_no_late_loading=vendor_declares_no_late_loading,
        vendor_declares_instance_isolation=vendor_declares_instance_isolation,
        limits=limits,
        compiler_selection=compiler_selection,
    )
    provider: ManufacturerNativeModel = ManufacturerNativeModel(name=result.model_info.model_name)
    provider.native_interface = result.model_info.native_interface
    provider.model_info_schema_version = 2
    provider.model_info = result.canonical_model_info
    variant: ManufacturerNativeBinaryVariant = ManufacturerNativeBinaryVariant(
        platform=result.platform,
        extension=(
            ".dll"
            if result.platform in (IeeeCigreDllPlatform.WINDOWS_X86, IeeeCigreDllPlatform.WINDOWS_X64)
            else ".so"
        ),
        content_sha256=result.binary_sha256,
        byte_size=result.binary_size,
        zip_member=(
            "native_models/manufacturer/by_sha256/" + result.binary_sha256
            + (
                ".dll"
                if result.platform in (IeeeCigreDllPlatform.WINDOWS_X86, IeeeCigreDllPlatform.WINDOWS_X64)
                else ".so"
            )
        ),
        verification_status=result.verification_status,
    )
    provider.set_platform_variant(variant)
    provider.set_binary_source(ManufacturerNativeBinarySource(
        platform=result.platform,
        file_path=str(Path(source_path).resolve()),
    ))
    rms_templates: Tuple[RmsModelTemplate, ...]
    emt_templates: Tuple[EmtModelTemplate, ...]
    rms_templates, emt_templates = _build_templates(result, provider)
    assets.add_manufacturer_native_model(provider)
    registered_rms: list[RmsModelTemplate] = list()
    registered_emt: list[EmtModelTemplate] = list()
    try:
        rms_template: RmsModelTemplate
        for rms_template in rms_templates:
            assets.add_rms_model(rms_template)
            registered_rms.append(rms_template)
        emt_template: EmtModelTemplate
        for emt_template in emt_templates:
            assets.add_emt_model(emt_template)
            registered_emt.append(emt_template)
    except BaseException:
        for rms_template in registered_rms:
            assets.rms_models.remove(rms_template)
        for emt_template in registered_emt:
            assets.emt_models.remove(emt_template)
        assets.manufacturer_native_models.remove(provider)
        raise
    return provider, rms_templates, emt_templates


def attach_manufacturer_native_binary_variant(provider: ManufacturerNativeModel,
                                         source_path: str | Path,
                                         platform: IeeeCigreDllPlatform,
                                         vendor_declares_no_late_loading: bool,
                                         vendor_declares_instance_isolation: bool,
                                         limits: ManufacturerNativeInspectionLimits | None = None,
                                         compiler_selection: NativeCompilerSelection | None = None) -> ManufacturerNativeBinaryVariant:
    """Attach another qualified platform binary only when ModelInfo is identical.

    :param provider: Existing canonical manufacturer provider.
    :param source_path: Manufacturer-supplied precompiled platform library.
    :param platform: Exact host platform variant.
    :param vendor_declares_no_late_loading: Vendor dependency-policy attestation.
    :param vendor_declares_instance_isolation: Vendor per-Instance state attestation.
    :param limits: Optional finite inspection limits.
    :param compiler_selection: Explicit compiler snapshot for worker inspection.
    :return: Newly attached complete variant record.
    """
    result: ManufacturerNativeInspectionResult = inspect_manufacturer_native(
        source_path=source_path,
        platform=platform,
        native_interface=provider.native_interface,
        vendor_declares_no_late_loading=vendor_declares_no_late_loading,
        vendor_declares_instance_isolation=vendor_declares_instance_isolation,
        limits=limits,
        compiler_selection=compiler_selection,
    )
    if result.model_info_sha256 != provider.model_info_sha256:
        raise ValueError("Platform variant ModelInfo digest differs from the provider")
    else:
        pass
    extension: str = (
        ".dll"
        if platform in (IeeeCigreDllPlatform.WINDOWS_X86, IeeeCigreDllPlatform.WINDOWS_X64)
        else ".so"
    )
    variant: ManufacturerNativeBinaryVariant = ManufacturerNativeBinaryVariant(
        platform=platform,
        extension=extension,
        content_sha256=result.binary_sha256,
        byte_size=result.binary_size,
        zip_member=(
            "native_models/manufacturer/by_sha256/"
            + result.binary_sha256 + extension
        ),
        verification_status=result.verification_status,
    )
    provider.set_platform_variant(variant)
    provider.set_binary_source(ManufacturerNativeBinarySource(
        platform=platform,
        file_path=str(Path(source_path).resolve()),
    ))
    return variant
