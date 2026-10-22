# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations

from pathlib import Path
import json
import os
import shutil
import tempfile

from VeraGridEngine.IO.fmu.compiler import Compiler, compile_fmu_shared_library, fmu_compiler_available
from VeraGridEngine.enumerations import FmiVersion
from VeraGridEngine.IO.fmu.config import ExportConfig
from VeraGridEngine.IO.fmu.CosimulationInterface.diff_to_c import render_discrete_derivative
from VeraGridEngine.IO.fmu.expression import ExprToCVisitor
from VeraGridEngine.IO.fmu.CosimulationInterface.export_ir import EquationGroup, ExportModel, StorageSegment, VariableCategory
from VeraGridEngine.IO.fmu.CosimulationInterface.procedural_to_c import render_procedural_c
from VeraGridEngine.IO.fmu.CosimulationInterface.variable_map import CVariableResolver



def ensure_build_layout(cfg: ExportConfig) -> tuple[Path, Path, Path]:
    """Execute the `ensure_build_layout` operation.

    :param cfg: Function input.
    :return: Function result.
    """
    if cfg.build_dir is None:
        if os.name == "nt":
            cfg.output_dir.mkdir(parents=True, exist_ok=True)
            # Building under the FMU output directory avoids Windows MSBuild warnings about
            # temporary intermediate folders and also keeps host-native artifacts together.
            root = Path(tempfile.mkdtemp(prefix="veragrid_fmu_build_", dir=str(cfg.output_dir)))
        else:
            # On Linux/macOS, especially under WSL mounted Windows paths, building on the
            # host temporary filesystem avoids clock-skew in native build tools.
            root = Path(tempfile.mkdtemp(prefix="veragrid_fmu_build_"))
    else:
        root = cfg.build_dir
    root.mkdir(parents=True, exist_ok=True)
    return root / "source", root / "build", (cfg.staging_dir or root / "staging")


def _copy_template_tree(cfg: ExportConfig, destination: Path) -> None:
    """Copy the neutral core, selected ABI adapter, and official headers.

    :param cfg: Export configuration that selects the FMI generation.
    :param destination: Build-scoped source root.
    :return: None.
    """

    runtime_root: Path = (
        Path(__file__).resolve().parents[3]
        / "data"
        / "fmu"
        / "c_runtime"
        / "co_simulation"
    )
    common_root: Path = runtime_root / "common_template"
    if cfg.fmi_version == FmiVersion.FMI_1_0:
        version_name: str = "fmi1/co_simulation"
        adapter_root: Path = runtime_root / "fmi1_adapter"
    else:
        if cfg.fmi_version == FmiVersion.FMI_2_0:
            version_name = "fmi2"
            adapter_root = runtime_root / "fmi2_adapter"
        else:
            if cfg.fmi_version == FmiVersion.FMI_3_0:
                version_name = "fmi3"
                adapter_root = runtime_root / "fmi3_adapter"
            else:
                raise NotImplementedError(
                    f"FMI {cfg.fmi_version.value} C runtime is not implemented"
                )
    c_api_root: Path = (
        Path(__file__).resolve().parents[3] / "data" / "fmu" / "c_api" / version_name
    )
    shutil.copytree(common_root / "src", destination / "src", dirs_exist_ok=True)
    shutil.copytree(adapter_root / "src", destination / "src", dirs_exist_ok=True)
    shutil.copytree(c_api_root, destination / "include", dirs_exist_ok=True)


def host_build_capable() -> bool:
    """
    Return whether the approved FMI compiler command set is available.

    :return: ``True`` when the host likely has a usable FMU build toolchain.
    """

    return fmu_compiler_available()


def _write_text(path: Path, content: str) -> Path:
    """Execute the `_write_text` operation.

    :param path: Function input.
    :param content: Function input.
    :return: Function result.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def _json_compatible(value):
    """Execute the `_json_compatible` operation.

    :param value: Function input.
    :return: Function result.
    """
    if isinstance(value, dict):
        return {str(key): _json_compatible(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_compatible(item) for item in value]
    return value


def _sorted_variables(export_model: ExportModel, category: VariableCategory) -> list:
    """Execute the `_sorted_variables` operation.

    :param export_model: Function input.
    :param category: Function input.
    :return: Function result.
    """
    return sorted(
        [variable for variable in export_model.variables if variable.category == category],
        key=lambda variable: variable.storage_index,
    )


def _storage_expr(segment: StorageSegment, index: int) -> str:
    """Execute the `_storage_expr` operation.

    :param segment: Function input.
    :param index: Function input.
    :return: Function result.
    """
    if segment == StorageSegment.STATES:
        return f"instance->states[{index}]"
    if segment == StorageSegment.ALGEBRAICS:
        return f"instance->algebraics[{index}]"
    if segment == StorageSegment.INPUTS:
        return f"instance->inputs[{index}]"
    if segment == StorageSegment.CONST_PARAMS:
        return f"instance->const_params[{index}]"
    if segment == StorageSegment.RUNTIME_PARAMS:
        return f"instance->runtime_params[{index}]"
    raise ValueError(f"Unsupported storage segment: {segment}")


def render_generated_metadata_h(export_model: ExportModel, cfg: ExportConfig) -> str:
    """Execute the `render_generated_metadata_h` operation.

    :param export_model: Function input.
    :param cfg: Function input.
    :return: Function result.
    """
    logic_count = len(export_model.logic_entries)
    lines = [
        "#ifndef GENERATED_METADATA_H",
        "#define GENERATED_METADATA_H",
        "",
        f"#define VG_MODEL_NAME \"{export_model.model_name}\"",
        f"#define VG_MODEL_IDENTIFIER \"{export_model.model_identifier}\"",
        f"#define VG_MODEL_IDENTIFIER_TOKEN {export_model.model_identifier}",
        f"#define VG_MODEL_GUID \"{export_model.guid}\"",
        f"#define VG_NUM_STATES {export_model.counts.get('states', 0)}",
        f"#define VG_NUM_ALGEBRAICS {export_model.counts.get('algebraics', 0)}",
        f"#define VG_NUM_CONTINUOUS_VARS {export_model.counts.get('states', 0) + export_model.counts.get('algebraics', 0)}",
        f"#define VG_NUM_INPUTS {export_model.counts.get('inputs', 0)}",
        f"#define VG_NUM_CONST_PARAMS {export_model.counts.get('const_params', 0)}",
        f"#define VG_NUM_RUNTIME_PARAMS {export_model.counts.get('runtime_params', 0)}",
        f"#define VG_NUM_RESIDUALS {export_model.counts.get('states', 0) + export_model.counts.get('algebraics', 0)}",
        f"#define VG_FIXED_STEP {cfg.fixed_step:.17g}",
        f"#define VG_NEWTON_TOLERANCE {cfg.newton_tolerance:.17g}",
        f"#define VG_MAX_NEWTON_ITERATIONS {cfg.max_newton_iterations}",
        f"#define VG_LOGIC_ENTRY_COUNT {logic_count}",
        f"#define VG_LOGIC_REAL_SLOTS {logic_count * 5}",
        f"#define VG_LOGIC_INT_SLOTS {logic_count * 3}",
        "",
        "#endif",
        "",
    ]
    return "\n".join(lines)


def render_generated_model_h() -> str:
    """Execute the `render_generated_model_h` operation.

    :return: Function result.
    """
    return "\n".join(
        [
            "#ifndef GENERATED_MODEL_H",
            "#define GENERATED_MODEL_H",
            "",
            '#include "model_instance.h"',
            "",
            "double vg_heaviside(double x);",
            "double vg_safe_log(double x);",
            "double vg_safe_sqrt(double x);",
            "",
            "void generated_set_start_values(ModelInstance* instance);",
            "void generated_eval_init(ModelInstance* instance);",
            "void generated_eval_discrete_init(ModelInstance* instance);",
            "void generated_eval_residual(ModelInstance* instance, double* out);",
            "void generated_eval_outputs(ModelInstance* instance);",
            "double generated_procedural_next_event(ModelInstance* instance, double t_prev, double t_target);",
            "void generated_procedural_update(ModelInstance* instance, double t);",
            "int generated_get_real(ModelInstance* instance, uint32_t vr, double* value);",
            "int generated_set_real(ModelInstance* instance, uint32_t vr, double value);",
            "",
            "#endif",
            "",
        ]
    )


def _render_start_assignments(export_model: ExportModel) -> list[str]:
    """Execute the `_render_start_assignments` operation.

    :param export_model: Function input.
    :return: Function result.
    """
    lines: list[str] = []
    for variable in export_model.variables:
        if variable.category == VariableCategory.DIFF:
            continue
        if variable.start is None:
            continue
        lines.append(f"    {_storage_expr(variable.storage_segment, variable.storage_index)} = {variable.start:.17g};")
    if not lines:
        lines.append("    (void)instance;")
    return lines


def _render_runtime_init(export_model: ExportModel, visitor: ExprToCVisitor, resolver: CVariableResolver) -> list[str]:
    """Execute the `_render_runtime_init` operation.

    :param export_model: Function input.
    :param visitor: Function input.
    :param resolver: Function input.
    :return: Function result.
    """
    lines: list[str] = []
    for equation in export_model.equations:
        if equation.group != EquationGroup.RUNTIME_INIT or equation.target_uid is None:
            continue
        lines.append(f"    {resolver.resolve_target(equation.target_uid)} = {visitor.render(equation.expression)};")
    return lines


def _render_init_assignments(export_model: ExportModel, visitor: ExprToCVisitor, resolver: CVariableResolver) -> list[str]:
    """Execute the `_render_init_assignments` operation.

    :param export_model: Function input.
    :param visitor: Function input.
    :param resolver: Function input.
    :return: Function result.
    """
    lines = _render_runtime_init(export_model, visitor, resolver)
    for equation in export_model.equations:
        if equation.group != EquationGroup.INIT or equation.target_uid is None:
            continue
        lines.append(f"    {resolver.resolve_target(equation.target_uid)} = {visitor.render(equation.expression)};")
    if not lines:
        lines.append("    (void)instance;")
    return lines


def _render_diff_init_assignments(export_model: ExportModel, visitor: ExprToCVisitor) -> list[str]:
    """Execute the `_render_diff_init_assignments` operation.

    :param export_model: Function input.
    :param visitor: Function input.
    :return: Function result.
    """
    lines: list[str] = []
    for equation in export_model.equations:
        if equation.group != EquationGroup.DIFF_INIT or equation.target_uid is None:
            continue
        diff_variable = export_model.variable_by_uid(equation.target_uid)
        base_uid = diff_variable.diff_base_uid
        if base_uid is None:
            continue
        base_variable = export_model.variable_by_uid(base_uid)
        if base_variable.history_index is None:
            continue
        lines.append(f"    instance->d_history[{base_variable.history_index}] = {visitor.render(equation.expression)};")
    if not lines:
        lines.append("    (void)instance;")
    return lines


def _render_residual_lines(export_model: ExportModel, cfg: ExportConfig, visitor: ExprToCVisitor, resolver: CVariableResolver) -> list[str]:
    """Execute the `_render_residual_lines` operation.

    :param export_model: Function input.
    :param cfg: Function input.
    :param visitor: Function input.
    :param resolver: Function input.
    :return: Function result.
    """
    lines: list[str] = []
    state_count = export_model.counts.get("states", 0)
    for equation in export_model.equations:
        if equation.group == EquationGroup.STATE and equation.target_uid is not None:
            variable = export_model.variable_by_uid(equation.target_uid)
            if variable.history_index is None:
                raise ValueError(f"State variable {variable.name!r} is missing history index")
            derivative = render_discrete_derivative(
                method=cfg.integration_method,
                state_expr=_storage_expr(StorageSegment.STATES, variable.storage_index),
                history_expr=f"instance->history[{variable.history_index}]",
                d_history_expr=f"instance->d_history[{variable.history_index}]",
                history2_expr=f"instance->history2[{variable.history_index}]",
                step_expr="instance->current_step_size",
            )
            lines.append(f"    out[{equation.index}] = ({derivative}) - ({visitor.render(equation.expression)});")
        elif equation.group == EquationGroup.ALGEBRAIC:
            lines.append(f"    out[{state_count + equation.index}] = {visitor.render(equation.expression)};")
    if not lines:
        lines.append("    (void)out;")
    return lines


def _render_get_real(export_model: ExportModel) -> list[str]:
    """Render Float64 access for exposed values and FMI 3 independent time.

    :param export_model: Neutral model whose value references are rendered.
    :return: C switch-body lines implementing Float64 reads.
    """
    lines: list[str] = ["    switch (vr) {"]
    maximum_value_reference: int = -1
    for variable in export_model.exposed_variables():
        lines.extend(
            [
                f"        case {variable.value_reference}u:",
                f"            *value = {_storage_expr(variable.storage_segment, variable.storage_index)};",
                "            return 0;",
            ]
        )
        if variable.value_reference is not None and variable.value_reference > maximum_value_reference:
            maximum_value_reference = variable.value_reference
        else:
            pass
    time_value_reference: int = maximum_value_reference + 1
    lines.extend(
        [
            f"        case {time_value_reference}u:",
            "            *value = instance->time;",
            "            return 0;",
        ]
    )
    lines.extend(["        default:", "            return 1;", "    }"])
    return lines

def _render_set_real(export_model: ExportModel) -> list[str]:
    """Execute the `_render_set_real` operation.

    :param export_model: Function input.
    :return: Function result.
    """
    lines = ["    switch (vr) {"]
    for variable in sorted(export_model.exposed_variables(), key=lambda item: item.value_reference or -1):
        target = _storage_expr(variable.storage_segment, variable.storage_index)
        if variable.causality == "input" or variable.category == VariableCategory.RUNTIME_PARAM:
            lines.extend(
                [
                    f"        case {variable.value_reference}u:",
                    f"            {target} = value;",
                    "            return 0;",
                ]
            )
        elif variable.category == VariableCategory.CONST_PARAM:
            lines.extend(
                [
                    f"        case {variable.value_reference}u:",
                    "            if (instance->initialized) return 1;",
                    f"            {target} = value;",
                    "            return 0;",
                ]
            )
    lines.extend(["        default:", "            return 1;", "    }"])
    return lines


def render_generated_model_c(export_model: ExportModel, cfg: ExportConfig) -> str:
    """Execute the `render_generated_model_c` operation.

    :param export_model: Function input.
    :param cfg: Function input.
    :return: Function result.
    """
    resolver = CVariableResolver(export_model, cfg)
    visitor = ExprToCVisitor(resolver)
    residual_count = export_model.counts.get("states", 0) + export_model.counts.get("algebraics", 0)
    lines = [
        '#include "generated_model.h"',
        '#include "generated_metadata.h"',
        '#include "runtime_support.h"',
        "",
        "double vg_heaviside(double x) { return x > 0.0 ? 1.0 : 0.0; }",
        "double vg_safe_log(double x) { return log(x > 1e-300 ? x : 1e-300); }",
        "double vg_safe_sqrt(double x) { return sqrt(x >= 0.0 ? x : 0.0); }",
        "",
        "void generated_set_start_values(ModelInstance* instance) {",
        *_render_start_assignments(export_model),
        "}",
        "",
        "void generated_eval_init(ModelInstance* instance) {",
        *_render_init_assignments(export_model, visitor, resolver),
        "}",
        "",
        "void generated_eval_discrete_init(ModelInstance* instance) {",
        *_render_diff_init_assignments(export_model, visitor),
        "}",
        "",
        "void generated_eval_residual(ModelInstance* instance, double* out) {",
        f"    memset(out, 0, sizeof(double) * {residual_count});",
        *_render_residual_lines(export_model, cfg, visitor, resolver),
        "}",
        "",
        "void generated_eval_outputs(ModelInstance* instance) {",
        "    (void)instance;",
        "}",
        "",
        "int generated_get_real(ModelInstance* instance, uint32_t vr, double* value) {",
        *_render_get_real(export_model),
        "}",
        "",
        "int generated_set_real(ModelInstance* instance, uint32_t vr, double value) {",
        *_render_set_real(export_model),
        "}",
        "",
    ]
    return "\n".join(lines)


def emit_c_sources(export_model: ExportModel, cfg: ExportConfig, source_root: Path) -> None:
    """Execute the `emit_c_sources` operation.

    :param export_model: Function input.
    :param cfg: Function input.
    :param source_root: Function input.
    :return: Function result.
    """
    _copy_template_tree(cfg, source_root)
    resolver = CVariableResolver(export_model, cfg)
    _write_text(source_root / "src" / "generated_metadata.h", render_generated_metadata_h(export_model, cfg))
    _write_text(source_root / "src" / "generated_model.h", render_generated_model_h())
    _write_text(source_root / "src" / "generated_model.c", render_generated_model_c(export_model, cfg))
    _write_text(source_root / "src" / "generated_procedural.c", render_procedural_c(export_model, resolver))


def write_debug_resources(export_model: ExportModel, cfg: ExportConfig, resources_dir: Path) -> None:
    """Execute the `write_debug_resources` operation.

    :param export_model: Function input.
    :param cfg: Function input.
    :param resources_dir: Function input.
    :return: Function result.
    """
    if cfg.include_export_model_resource:
        _write_text(resources_dir / "export_model.json", json.dumps(_json_compatible(export_model.to_dict()), indent=2, sort_keys=True))
    if cfg.include_snapshot_resource:
        _write_text(resources_dir / "snapshot.json", json.dumps(_json_compatible(export_model.source_snapshot), indent=2, sort_keys=True))


def build_shared_library(
    cfg: ExportConfig,
    source_dir: Path,
    build_dir: Path,
    compiler: Compiler | None = None,
) -> Path:
    """Build the shared library for the selected FMI generation.

    :param cfg: Export configuration.
    :param source_dir: Generated C source directory.
    :param build_dir: Binary output directory.
    :param compiler: Optional caller-owned sequential compiler session.
    :return: Built shared-library path.
    """

    source_root: Path = source_dir / "src"
    if cfg.fmi_version == FmiVersion.FMI_1_0:
        runtime_name: str = "runtime_fmi1.c"
    else:
        if cfg.fmi_version == FmiVersion.FMI_2_0:
            runtime_name = "runtime_fmi2.c"
        else:
            if cfg.fmi_version == FmiVersion.FMI_3_0:
                runtime_name = "runtime_fmi3.c"
            else:
                raise NotImplementedError(
                    f"FMI {cfg.fmi_version.value} Co-Simulation build is not implemented"
                )
    source_files: tuple[Path, ...] = (
        source_root / runtime_name,
        source_root / "model_instance.c",
        source_root / "solver.c",
        source_root / "generated_model.c",
        source_root / "generated_procedural.c",
    )
    include_directories: tuple[Path, ...] = (source_dir / "include", source_root)
    output_path: Path = build_dir / cfg.library_name
    return compile_fmu_shared_library(
        source_files=source_files,
        include_directories=include_directories,
        output_path=output_path,
        compiler=compiler,
    )
