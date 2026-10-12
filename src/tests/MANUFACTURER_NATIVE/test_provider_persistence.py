# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations

import hashlib
from pathlib import Path
import zipfile

import pytest

from VeraGridEngine.Devices.Dynamic.manufacturer_native_model import (
    ManufacturerNativeBinarySource,
    ManufacturerNativeBinaryVariant,
    ManufacturerNativeModel,
)
from VeraGridEngine.Devices.Dynamic.rms_template import RmsModelTemplate
from VeraGridEngine.Devices.multi_circuit import MultiCircuit
from VeraGridEngine.enumerations import (
    IeeeCigreDllModelMode,
    IeeeCigreDllPlatform,
    IeeeCigreDllVerificationStatus,
)
from VeraGridEngine.IO.file_open import FileOpen
from VeraGridEngine.IO.file_save import FileSave
from VeraGridEngine.IO.manufacturer_native.model_info import (
    ManufacturerNativeModelInfo,
    ManufacturerNativeSignalInfo,
    build_manufacturer_native_rebind_plan,
)
from VeraGridEngine.IO.manufacturer_native.model_info_codec import encode_manufacturer_native_model_info
from VeraGridEngine.Utils.procedural_logic import (
    IeeeCigreDllSignalBinding,
    ManufacturerNativeControllerLogic,
    ManufacturerNativeRebindPlan,
)
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.symbolic import Const, Var
from tests.MANUFACTURER_NATIVE.test_model_info_codec import _model_info


def _provider_with_binary(
        binary_path: Path,
        platform: IeeeCigreDllPlatform = IeeeCigreDllPlatform.WINDOWS_X64,
) -> ManufacturerNativeModel:
    """Create one qualified provider backed by existing precompiled bytes.

    :param binary_path: Existing persistence payload.
    :param platform: Exact Windows binary platform represented by the payload.
    :return: Provider with one selected Windows variant.
    """
    payload: bytes = binary_path.read_bytes()
    digest: str = hashlib.sha256(payload).hexdigest()
    provider: ManufacturerNativeModel = ManufacturerNativeModel(name="Manufacturer controller")
    provider.model_info = encode_manufacturer_native_model_info(_model_info())
    provider.set_platform_variant(ManufacturerNativeBinaryVariant(
        platform=platform,
        extension=".dll",
        content_sha256=digest,
        byte_size=len(payload),
        zip_member=(
            "native_models/manufacturer/ieee_cigre_v1_1/"
            + platform.value
            + "/"
            + digest
            + ".dll"
        ),
        verification_status=IeeeCigreDllVerificationStatus.DECLARED_AND_QUALIFIED,
    ))
    provider.set_binary_source(ManufacturerNativeBinarySource(
        platform=platform,
        file_path=str(binary_path),
    ))
    return provider


def _consumer(provider: ManufacturerNativeModel) -> RmsModelTemplate:
    """Create one ordinary RMS template referencing a provider by identity.

    :param provider: Provider owned by the same circuit.
    :return: RMS template with one native controller Block.
    """
    input_var: Var = Var("native_input")
    output_var: Var = Var("native_output")
    logic: ManufacturerNativeControllerLogic = ManufacturerNativeControllerLogic(
        provider_idtag=provider.idtag,
        model_info_sha256=provider.model_info_sha256,
        signal_bindings=(
            IeeeCigreDllSignalBinding(True, 0, 0, input_var),
            IeeeCigreDllSignalBinding(False, 0, 0, output_var),
        ),
        parameter_overrides=tuple(),
        name="Manufacturer controller",
    )
    template: RmsModelTemplate = RmsModelTemplate(name="Manufacturer controller RMS")
    template.block = Block(
        in_vars=[input_var],
        out_vars=[output_var],
        mode_dict={output_var: Const(0.0)},
        procedural_logic=(logic,),
        is_decomposable=False,
        name="Manufacturer controller",
    )
    return template


def test_provider_clone_rebind_and_delete_lifecycle(tmp_path: Path) -> None:
    """Provider lifecycle must preserve bytes and refuse dangling consumers."""
    binary_path: Path = tmp_path / "manufacturer.dll"
    binary_path.write_bytes(b"precompiled manufacturer payload")
    circuit: MultiCircuit = MultiCircuit()
    provider: ManufacturerNativeModel = _provider_with_binary(binary_path)
    consumer: RmsModelTemplate = _consumer(provider)
    circuit.add_manufacturer_native_model(provider)
    circuit.add_rms_model(consumer)

    assert circuit.get_element_deletion_blockers(provider) == [consumer]
    circuit.delete_manufacturer_native_model(provider)
    assert circuit.get_manufacturer_native_model_by_idtag(provider.idtag) is provider
    circuit.delete_element(provider)
    assert circuit.get_manufacturer_native_model_by_idtag(provider.idtag) is provider

    clone: ManufacturerNativeModel = provider.copy(forced_new_idtag=True)
    clone.name += " copy"
    circuit.add_element(clone)
    assert clone.idtag != provider.idtag
    assert clone.model_info == provider.model_info
    assert clone.get_platform_variant(IeeeCigreDllPlatform.WINDOWS_X64).content_sha256 == (
        provider.get_platform_variant(IeeeCigreDllPlatform.WINDOWS_X64).content_sha256
    )

    circuit.rebind_manufacturer_native_consumer(consumer, provider, clone)
    assert circuit.get_manufacturer_native_consumers(provider) == list()
    assert circuit.get_manufacturer_native_consumers(clone) == [consumer]
    circuit.delete_manufacturer_native_model(provider)
    assert circuit.get_manufacturer_native_model_by_idtag(provider.idtag) is None


def test_save_as_rebinds_archive_source_and_remains_self_contained(tmp_path: Path) -> None:
    """Save As must survive deletion of both the external file and source archive."""
    binary_path: Path = tmp_path / "manufacturer.dll"
    binary_payload: bytes = b"precompiled manufacturer payload"
    binary_path.write_bytes(binary_payload)
    circuit: MultiCircuit = MultiCircuit()
    provider: ManufacturerNativeModel = _provider_with_binary(binary_path)
    consumer: RmsModelTemplate = _consumer(provider)
    original_provider_idtag: str = provider.idtag
    original_consumer_idtag: str = consumer.idtag
    original_model_info: bytes = provider.model_info
    original_model_info_sha256: str = provider.model_info_sha256
    original_variant: ManufacturerNativeBinaryVariant | None = provider.get_platform_variant(
        IeeeCigreDllPlatform.WINDOWS_X64
    )
    assert original_variant is not None
    circuit.add_manufacturer_native_model(provider)
    circuit.add_rms_model(consumer)

    first_project: Path = tmp_path / "first.veragrid"
    first_logger = FileSave(circuit=circuit, file_name=str(first_project)).save()
    assert not first_logger.has_errors()
    binary_path.unlink()

    loaded: MultiCircuit | None = FileOpen(str(first_project)).open()
    assert loaded is not None
    second_project: Path = tmp_path / "second.veragrid"
    second_logger = FileSave(circuit=loaded, file_name=str(second_project)).save()
    assert not second_logger.has_errors()
    first_project.unlink()

    reopened: MultiCircuit | None = FileOpen(str(second_project)).open()
    assert reopened is not None
    reopened_provider: ManufacturerNativeModel = reopened.manufacturer_native_models[0]
    reopened_consumer: RmsModelTemplate = reopened.rms_models[0]
    reopened_logic: ManufacturerNativeControllerLogic = (
        reopened_consumer.block.procedural_logic[0]
    )
    source: ManufacturerNativeBinarySource | None = reopened_provider.get_binary_source(
        IeeeCigreDllPlatform.WINDOWS_X64
    )
    variant: ManufacturerNativeBinaryVariant | None = reopened_provider.get_platform_variant(
        IeeeCigreDllPlatform.WINDOWS_X64
    )
    assert source is not None
    assert variant is not None
    assert reopened_provider.idtag == original_provider_idtag
    assert reopened_consumer.idtag == original_consumer_idtag
    assert reopened_provider.model_info == original_model_info
    assert reopened_provider.model_info_sha256 == original_model_info_sha256
    assert variant.content_sha256 == original_variant.content_sha256
    assert reopened_logic.provider_idtag == reopened_provider.idtag
    assert reopened_logic.model_info_sha256 == reopened_provider.model_info_sha256
    assert source.archive_path == str(second_project.resolve())
    assert source.archive_member == variant.zip_member
    with zipfile.ZipFile(second_project, mode="r") as archive:
        assert archive.read(variant.zip_member) == binary_payload

def test_windows_x86_binary_is_self_contained_after_save_and_open(tmp_path: Path) -> None:
    """Persist a PE32 provider inside the project and restore its archive source.

    :param tmp_path: Isolated project and source directory.
    :return: None.
    """
    fixture: Path = (
        Path(__file__).resolve().parents[1]
        / "data"
        / "manufacturer_native"
        / "windows_x86"
        / "fixture_normal_x86.dll"
    )
    payload: bytes = fixture.read_bytes()
    binary_path: Path = tmp_path / "manufacturer_x86.dll"
    binary_path.write_bytes(payload)
    circuit: MultiCircuit = MultiCircuit()
    provider: ManufacturerNativeModel = _provider_with_binary(
        binary_path,
        IeeeCigreDllPlatform.WINDOWS_X86,
    )
    circuit.add_manufacturer_native_model(provider)
    project: Path = tmp_path / "x86-provider.veragrid"

    assert not FileSave(circuit=circuit, file_name=str(project)).save().has_errors()
    binary_path.unlink()
    loaded: MultiCircuit | None = FileOpen(str(project)).open()

    assert loaded is not None
    loaded_provider: ManufacturerNativeModel = loaded.manufacturer_native_models[0]
    variant: ManufacturerNativeBinaryVariant | None = loaded_provider.get_platform_variant(
        IeeeCigreDllPlatform.WINDOWS_X86
    )
    source: ManufacturerNativeBinarySource | None = loaded_provider.get_binary_source(
        IeeeCigreDllPlatform.WINDOWS_X86
    )
    assert variant is not None
    assert source is not None
    assert source.archive_path == str(project.resolve())
    assert source.archive_member == variant.zip_member
    with zipfile.ZipFile(project, mode="r") as archive:
        assert archive.read(variant.zip_member) == payload


def test_different_model_info_rebind_is_complete_and_atomic(tmp_path: Path) -> None:
    """A complete explicit plan commits once and a stale plan changes nothing.

    :param tmp_path: Isolated binary fixture directory.
    :return: None.
    """
    source_path: Path = tmp_path / "source.dll"
    destination_path: Path = tmp_path / "destination.dll"
    source_path.write_bytes(b"source manufacturer payload")
    destination_path.write_bytes(b"destination manufacturer payload")
    circuit: MultiCircuit = MultiCircuit()
    source: ManufacturerNativeModel = _provider_with_binary(source_path)
    destination: ManufacturerNativeModel = _provider_with_binary(destination_path)

    source_info: ManufacturerNativeModelInfo = _model_info()
    source_info.input_ports = (ManufacturerNativeSignalInfo(
        "source voltage",
        "terminal voltage",
        "pu",
        source_info.input_ports[0].data_type,
        1,
    ),)
    destination_info: ManufacturerNativeModelInfo = _model_info()
    destination_info.model_name = "Replacement controller"
    destination_info.input_ports = (ManufacturerNativeSignalInfo(
        "renamed voltage",
        "terminal voltage",
        "pu",
        destination_info.input_ports[0].data_type,
        1,
    ),)
    source.model_info = encode_manufacturer_native_model_info(source_info)
    destination.model_info = encode_manufacturer_native_model_info(destination_info)
    consumer: RmsModelTemplate = _consumer(source)
    circuit.add_manufacturer_native_model(source)
    circuit.add_manufacturer_native_model(destination)
    circuit.add_rms_model(consumer)
    logic: ManufacturerNativeControllerLogic = consumer.block.procedural_logic[0]

    plan: ManufacturerNativeRebindPlan = build_manufacturer_native_rebind_plan(
        consumer_idtag=consumer.idtag,
        source_provider_idtag=source.idtag,
        destination_provider_idtag=destination.idtag,
        source_model_info_sha256=source.model_info_sha256,
        destination_model_info_sha256=destination.model_info_sha256,
        source_model_info=source_info,
        destination_model_info=destination_info,
        occurrences=((IeeeCigreDllModelMode.RMS, logic),),
        input_port_mapping=(0,),
        output_port_mapping=(0,),
        parameter_mapping=tuple(range(len(source_info.parameters))),
    )
    circuit.rebind_manufacturer_native_consumer(
        consumer=consumer,
        source=source,
        destination=destination,
        plan=plan,
    )
    assert logic.provider_idtag == destination.idtag
    assert logic.model_info_sha256 == destination.model_info_sha256

    reverse_plan: ManufacturerNativeRebindPlan = build_manufacturer_native_rebind_plan(
        consumer_idtag=consumer.idtag,
        source_provider_idtag=destination.idtag,
        destination_provider_idtag=source.idtag,
        source_model_info_sha256=destination.model_info_sha256,
        destination_model_info_sha256=source.model_info_sha256,
        source_model_info=destination_info,
        destination_model_info=source_info,
        occurrences=((IeeeCigreDllModelMode.RMS, logic),),
        input_port_mapping=(0,),
        output_port_mapping=(0,),
        parameter_mapping=tuple(range(len(source_info.parameters))),
    )
    original_binding: IeeeCigreDllSignalBinding = logic.signal_bindings[0]
    original_binding.get_variable().set_name(
        original_binding.get_variable().name + "_changed"
    )
    with pytest.raises(ValueError, match="changed after plan construction"):
        circuit.rebind_manufacturer_native_consumer(
            consumer=consumer,
            source=destination,
            destination=source,
            plan=reverse_plan,
        )
    assert logic.provider_idtag == destination.idtag
    assert logic.model_info_sha256 == destination.model_info_sha256


def test_different_model_info_rebind_rejects_partial_mapping(tmp_path: Path) -> None:
    """A missing input ordinal is rejected before Assets can mutate a Block.

    :param tmp_path: Isolated binary fixture directory.
    :return: None.
    """
    source_path: Path = tmp_path / "source-partial.dll"
    destination_path: Path = tmp_path / "destination-partial.dll"
    source_path.write_bytes(b"source partial payload")
    destination_path.write_bytes(b"destination partial payload")
    source: ManufacturerNativeModel = _provider_with_binary(source_path)
    destination: ManufacturerNativeModel = _provider_with_binary(destination_path)
    source_info: ManufacturerNativeModelInfo = _model_info()
    destination_info: ManufacturerNativeModelInfo = _model_info()
    destination_info.model_name = "Different metadata"
    source.model_info = encode_manufacturer_native_model_info(source_info)
    destination.model_info = encode_manufacturer_native_model_info(destination_info)
    consumer: RmsModelTemplate = _consumer(source)
    logic: ManufacturerNativeControllerLogic = consumer.block.procedural_logic[0]

    with pytest.raises(ValueError, match="Input mapping"):
        build_manufacturer_native_rebind_plan(
            consumer_idtag=consumer.idtag,
            source_provider_idtag=source.idtag,
            destination_provider_idtag=destination.idtag,
            source_model_info_sha256=source.model_info_sha256,
            destination_model_info_sha256=destination.model_info_sha256,
            source_model_info=source_info,
            destination_model_info=destination_info,
            occurrences=((IeeeCigreDllModelMode.RMS, logic),),
            input_port_mapping=tuple(),
            output_port_mapping=(0,),
            parameter_mapping=tuple(range(len(source_info.parameters))),
        )
    assert logic.provider_idtag == source.idtag
