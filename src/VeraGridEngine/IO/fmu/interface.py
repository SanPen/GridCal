# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
"""Public FMI model-to-FMU interface."""

from __future__ import annotations

from pathlib import Path
import shutil

from VeraGridEngine.IO.fmu.archive import package_fmu, prepare_fmu_staging_dir
from VeraGridEngine.IO.fmu.config import ExportConfig, InterfaceType
from VeraGridEngine.IO.fmu.compiler import Compiler
from VeraGridEngine.IO.fmu.config import binary_directory
from VeraGridEngine.IO.fmu.CosimulationInterface.build import build_shared_library as build_co_simulation_library
from VeraGridEngine.IO.fmu.CosimulationInterface.build import emit_c_sources as emit_co_simulation_sources
from VeraGridEngine.IO.fmu.CosimulationInterface.build import ensure_build_layout as ensure_co_simulation_layout
from VeraGridEngine.IO.fmu.CosimulationInterface.build import write_debug_resources as write_co_simulation_resources
from VeraGridEngine.IO.fmu.CosimulationInterface.export_ir import build_export_model as build_co_simulation_model
from VeraGridEngine.IO.fmu.model import flatten_model
from VeraGridEngine.IO.fmu.logic import build_co_simulation_logic_entries
from VeraGridEngine.IO.fmu.model import build_model_snapshot
from VeraGridEngine.IO.fmu.CosimulationInterface.validate import validate_export_model as validate_co_simulation_model
from VeraGridEngine.IO.fmu.CosimulationInterface.xml_writer import write_model_description as write_co_simulation_description
from VeraGridEngine.IO.fmu.ExportInterface.build import build_shared_library as build_model_exchange_library
from VeraGridEngine.IO.fmu.ExportInterface.build import emit_c_sources as emit_model_exchange_sources
from VeraGridEngine.IO.fmu.ExportInterface.build import ensure_build_layout as ensure_model_exchange_layout
from VeraGridEngine.IO.fmu.ExportInterface.build import write_debug_resources as write_model_exchange_resources
from VeraGridEngine.IO.fmu.ExportInterface.export_ir import build_export_model as build_model_exchange_model
from VeraGridEngine.IO.fmu.ExportInterface.normalize import prepare_flat_block_for_me
from VeraGridEngine.IO.fmu.logic import build_model_exchange_logic_entries
from VeraGridEngine.IO.fmu.ExportInterface.validate import validate_export_model as validate_model_exchange_model
from VeraGridEngine.IO.fmu.ExportInterface.xml_writer import write_model_description as write_model_exchange_description


def export_model_as_fmu(
    model: object,
    cfg: ExportConfig,
    compiler: Compiler | None = None,
) -> Path:
    """Export one VeraGrid model through its selected FMI interface.

    :param model: VeraGrid symbolic model to export.
    :param cfg: Shared FMI export configuration.
    :param compiler: Optional caller-owned compiler session.
    :return: Path to the packaged FMU archive.
    """

    if cfg.interface_type == InterfaceType.CO_SIMULATION:
        return _export_co_simulation(model, cfg, compiler)
    if cfg.interface_type == InterfaceType.MODEL_EXCHANGE:
        return _export_model_exchange(model, cfg, compiler)
    raise ValueError("Unsupported FMI interface type")


def _export_co_simulation(
    model: object,
    config: ExportConfig,
    compiler: Compiler | None,
) -> Path:
    """Build and package one Co-Simulation FMU.

    :param model: VeraGrid symbolic model to export.
    :param config: Co-Simulation export settings.
    :param compiler: Optional caller-owned compiler session.
    :return: Packaged FMU path.
    """
    if not config.compile_binary:
        raise ValueError("Source-only FMU packaging is not implemented")
    snapshot = build_model_snapshot(model)
    flat_block = flatten_model(snapshot)
    logic_entries = build_co_simulation_logic_entries(flat_block)
    export_model = build_co_simulation_model(flat_block, config, snapshot, logic_entries)
    validate_co_simulation_model(export_model)
    source_dir, build_dir, staging_dir = ensure_co_simulation_layout(config)
    automatic_build_root: bool = config.build_dir is None
    build_root: Path = source_dir.parent
    export_completed: bool = False
    try:
        source_dir.mkdir(parents=True, exist_ok=True)
        staging_root: Path = prepare_fmu_staging_dir(staging_dir)
        emit_co_simulation_sources(export_model, config, source_dir)
        write_co_simulation_description(export_model, staging_root / "modelDescription.xml", config.fmi_version)
        write_co_simulation_resources(export_model, config, staging_root / "resources")
        library_path: Path = build_co_simulation_library(config, source_dir, build_dir, compiler)
        binaries_dir: Path = staging_root / "binaries" / binary_directory(config.target_platform, config.fmi_version)
        binaries_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(library_path, binaries_dir / config.library_name)
        output_path: Path = package_fmu(staging_root, config.output_path)
        export_completed = True
        return output_path
    finally:
        if automatic_build_root and not config.keep_build_dir:
            shutil.rmtree(build_root, ignore_errors=not export_completed)


def _export_model_exchange(
    model: object,
    config: ExportConfig,
    compiler: Compiler | None,
) -> Path:
    """Build and package one Model Exchange FMU.

    :param model: VeraGrid symbolic model to export.
    :param config: Model Exchange export settings.
    :param compiler: Optional caller-owned compiler session.
    :return: Packaged FMU path.
    """
    if not config.compile_binary:
        raise ValueError("Source-only FMU packaging is not implemented")
    snapshot = build_model_snapshot(model)
    flat_block = prepare_flat_block_for_me(snapshot)
    logic_entries = build_model_exchange_logic_entries(flat_block)
    export_model = build_model_exchange_model(flat_block, config, snapshot, logic_entries)
    validate_model_exchange_model(export_model)
    source_dir, build_dir, staging_dir = ensure_model_exchange_layout(config)
    automatic_build_root: bool = config.build_dir is None
    build_root: Path = source_dir.parent
    export_completed: bool = False
    try:
        source_dir.mkdir(parents=True, exist_ok=True)
        staging_root: Path = prepare_fmu_staging_dir(staging_dir)
        emit_model_exchange_sources(export_model, config, source_dir)
        write_model_exchange_description(export_model, staging_root / "modelDescription.xml", config.fmi_version)
        write_model_exchange_resources(export_model, config, staging_root / "resources")
        library_path: Path = build_model_exchange_library(config, source_dir, build_dir, compiler)
        binaries_dir: Path = staging_root / "binaries" / binary_directory(config.target_platform, config.fmi_version)
        binaries_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(library_path, binaries_dir / config.library_name)
        output_path: Path = package_fmu(staging_root, config.output_path)
        export_completed = True
        return output_path
    finally:
        if automatic_build_root and not config.keep_build_dir:
            shutil.rmtree(build_root, ignore_errors=not export_completed)
