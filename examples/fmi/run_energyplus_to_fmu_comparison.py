"""Command-line entry point for the EnergyPlusToFMU comparison."""
from __future__ import annotations

import argparse
from pathlib import Path

from examples.fmi.energyplus_to_fmu import (
    EnergyPlusToFmuComparisonConfig,
    generate_energyplus_to_fmu_comparison,
)


def main() -> int:
    """Parse explicit identities and publish one comparison package.

    :return: Zero after complete package verification.
    """

    parser: argparse.ArgumentParser = argparse.ArgumentParser()
    parser.add_argument("--output-directory", required=True, type=Path)
    parser.add_argument("--source-branch", required=True)
    parser.add_argument("--source-revision", required=True)
    parser.add_argument("--source-tree-sha256", required=True)
    parser.add_argument("--upstream-commit", required=True)
    parser.add_argument("--upstream-tree", required=True)
    parser.add_argument("--exporter-source-file-count", required=True, type=int)
    parser.add_argument("--exporter-source-total-size-bytes", required=True, type=int)
    parser.add_argument("--exporter-source-tree-sha256", required=True)
    parser.add_argument("--compatibility-patch-path", required=True, type=Path)
    parser.add_argument("--compatibility-patch-size-bytes", required=True, type=int)
    parser.add_argument("--compatibility-patch-sha256", required=True)
    parser.add_argument("--python-path", required=True, type=Path)
    parser.add_argument("--python-size-bytes", required=True, type=int)
    parser.add_argument("--python-sha256", required=True)
    parser.add_argument("--fmpy-root", required=True, type=Path)
    parser.add_argument("--fmpy-file-count", required=True, type=int)
    parser.add_argument("--fmpy-total-size-bytes", required=True, type=int)
    parser.add_argument("--fmpy-tree-sha256", required=True)
    parser.add_argument("--worker-path", required=True, type=Path)
    parser.add_argument("--worker-size-bytes", required=True, type=int)
    parser.add_argument("--worker-sha256", required=True)
    parser.add_argument("--exporter-path", required=True, type=Path)
    parser.add_argument("--exporter-size-bytes", required=True, type=int)
    parser.add_argument("--exporter-sha256", required=True)
    parser.add_argument("--idd-path", required=True, type=Path)
    parser.add_argument("--idd-size-bytes", required=True, type=int)
    parser.add_argument("--idd-sha256", required=True)
    parser.add_argument("--idf-path", required=True, type=Path)
    parser.add_argument("--idf-size-bytes", required=True, type=int)
    parser.add_argument("--idf-sha256", required=True)
    parser.add_argument("--epw-path", required=True, type=Path)
    parser.add_argument("--epw-size-bytes", required=True, type=int)
    parser.add_argument("--epw-sha256", required=True)
    parser.add_argument("--cmd-path", required=True, type=Path)
    parser.add_argument("--cmd-size-bytes", required=True, type=int)
    parser.add_argument("--cmd-sha256", required=True)
    parser.add_argument("--vsdevcmd-path", required=True, type=Path)
    parser.add_argument("--vsdevcmd-size-bytes", required=True, type=int)
    parser.add_argument("--vsdevcmd-sha256", required=True)
    parser.add_argument("--compiler-path", required=True, type=Path)
    parser.add_argument("--compiler-size-bytes", required=True, type=int)
    parser.add_argument("--compiler-sha256", required=True)
    parser.add_argument("--linker-path", required=True, type=Path)
    parser.add_argument("--linker-size-bytes", required=True, type=int)
    parser.add_argument("--linker-sha256", required=True)
    parser.add_argument("--energyplus-path", required=True, type=Path)
    parser.add_argument("--energyplus-size-bytes", required=True, type=int)
    parser.add_argument("--energyplus-sha256", required=True)
    parser.add_argument("--energyplus-file-count", required=True, type=int)
    parser.add_argument("--energyplus-total-size-bytes", required=True, type=int)
    parser.add_argument("--energyplus-tree-sha256", required=True)
    parser.add_argument("--communication-step-seconds", required=True, type=float)
    parser.add_argument("--steps-per-level", required=True, type=int)
    parser.add_argument("--input-level", required=True, action="append", type=float)
    parser.add_argument("--temporary-directory", required=True, type=Path)
    parser.add_argument("--process-timeout-seconds", required=True, type=float)
    parser.add_argument("--stream-limit-bytes", required=True, type=int)
    arguments: argparse.Namespace = parser.parse_args()
    config: EnergyPlusToFmuComparisonConfig = EnergyPlusToFmuComparisonConfig(
        output_directory=arguments.output_directory,
        source_branch=arguments.source_branch,
        source_revision=arguments.source_revision,
        source_tree_sha256=arguments.source_tree_sha256,
        upstream_commit=arguments.upstream_commit,
        upstream_tree=arguments.upstream_tree,
        exporter_source_file_count=arguments.exporter_source_file_count,
        exporter_source_total_size_bytes=arguments.exporter_source_total_size_bytes,
        exporter_source_tree_sha256=arguments.exporter_source_tree_sha256,
        compatibility_patch_path=arguments.compatibility_patch_path,
        compatibility_patch_size_bytes=arguments.compatibility_patch_size_bytes,
        compatibility_patch_sha256=arguments.compatibility_patch_sha256,
        python_path=arguments.python_path,
        python_size_bytes=arguments.python_size_bytes,
        python_sha256=arguments.python_sha256,
        fmpy_root=arguments.fmpy_root,
        fmpy_file_count=arguments.fmpy_file_count,
        fmpy_total_size_bytes=arguments.fmpy_total_size_bytes,
        fmpy_tree_sha256=arguments.fmpy_tree_sha256,
        worker_path=arguments.worker_path,
        worker_size_bytes=arguments.worker_size_bytes,
        worker_sha256=arguments.worker_sha256,
        exporter_path=arguments.exporter_path,
        exporter_size_bytes=arguments.exporter_size_bytes,
        exporter_sha256=arguments.exporter_sha256,
        idd_path=arguments.idd_path,
        idd_size_bytes=arguments.idd_size_bytes,
        idd_sha256=arguments.idd_sha256,
        idf_path=arguments.idf_path,
        idf_size_bytes=arguments.idf_size_bytes,
        idf_sha256=arguments.idf_sha256,
        epw_path=arguments.epw_path,
        epw_size_bytes=arguments.epw_size_bytes,
        epw_sha256=arguments.epw_sha256,
        cmd_path=arguments.cmd_path,
        cmd_size_bytes=arguments.cmd_size_bytes,
        cmd_sha256=arguments.cmd_sha256,
        vsdevcmd_path=arguments.vsdevcmd_path,
        vsdevcmd_size_bytes=arguments.vsdevcmd_size_bytes,
        vsdevcmd_sha256=arguments.vsdevcmd_sha256,
        compiler_path=arguments.compiler_path,
        compiler_size_bytes=arguments.compiler_size_bytes,
        compiler_sha256=arguments.compiler_sha256,
        linker_path=arguments.linker_path,
        linker_size_bytes=arguments.linker_size_bytes,
        linker_sha256=arguments.linker_sha256,
        energyplus_path=arguments.energyplus_path,
        energyplus_size_bytes=arguments.energyplus_size_bytes,
        energyplus_sha256=arguments.energyplus_sha256,
        energyplus_file_count=arguments.energyplus_file_count,
        energyplus_total_size_bytes=arguments.energyplus_total_size_bytes,
        energyplus_tree_sha256=arguments.energyplus_tree_sha256,
        communication_step_seconds=arguments.communication_step_seconds,
        steps_per_level=arguments.steps_per_level,
        input_levels=tuple(arguments.input_level),
        temporary_directory=arguments.temporary_directory,
        process_timeout_seconds=arguments.process_timeout_seconds,
        stream_limit_bytes=arguments.stream_limit_bytes,
    )
    package_path: Path = generate_energyplus_to_fmu_comparison(config)
    print(package_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
