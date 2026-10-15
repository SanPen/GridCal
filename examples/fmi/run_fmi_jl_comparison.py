# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
"""Command-line adapter for the authenticated FMI.jl comparison."""
from __future__ import annotations

import argparse
from pathlib import Path

from examples.fmi.fmi_jl import (
    FmiJlComparisonConfig,
    generate_fmi_jl_comparison,
)


def main() -> int:
    """Parse explicit identities and execute the FMI.jl comparison.

    :return: Zero after verified atomic publication.
    """

    parser: argparse.ArgumentParser = argparse.ArgumentParser(
        description="Compare two interacting FMI 2 CS FMUs in FMI.jl and VeraGrid."
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--source-branch", required=True)
    parser.add_argument("--source-revision", required=True)
    parser.add_argument("--source-tree-sha256", required=True)
    parser.add_argument("--wsl-executable", type=Path, required=True)
    parser.add_argument("--wsl-executable-size-bytes", type=int, required=True)
    parser.add_argument("--wsl-executable-sha256", required=True)
    parser.add_argument("--wsl-distribution", required=True)
    parser.add_argument("--wsl-version", required=True)
    parser.add_argument("--wsl-distribution-pretty-name", required=True)
    parser.add_argument("--wsl-distribution-version-id", required=True)
    parser.add_argument("--wsl-architecture", required=True)
    parser.add_argument("--wsl-kernel", required=True)
    parser.add_argument("--wsl-glibc-version", required=True)
    parser.add_argument("--wsl-python-executable", type=Path, required=True)
    parser.add_argument(
        "--wsl-python-executable-size-bytes", type=int, required=True
    )
    parser.add_argument("--wsl-python-executable-sha256", required=True)
    parser.add_argument("--wsl-python-version", required=True)
    parser.add_argument("--julia-archive", type=Path, required=True)
    parser.add_argument("--julia-archive-size-bytes", type=int, required=True)
    parser.add_argument("--julia-archive-sha256", required=True)
    parser.add_argument("--julia-executable", type=Path, required=True)
    parser.add_argument("--julia-executable-size-bytes", type=int, required=True)
    parser.add_argument("--julia-executable-sha256", required=True)
    parser.add_argument("--julia-runtime-entry-count", type=int, required=True)
    parser.add_argument("--julia-runtime-regular-bytes", type=int, required=True)
    parser.add_argument("--julia-runtime-tree-sha256", required=True)
    parser.add_argument("--julia-project", type=Path, required=True)
    parser.add_argument("--julia-project-size-bytes", type=int, required=True)
    parser.add_argument("--julia-project-sha256", required=True)
    parser.add_argument("--julia-manifest", type=Path, required=True)
    parser.add_argument("--julia-manifest-size-bytes", type=int, required=True)
    parser.add_argument("--julia-manifest-sha256", required=True)
    parser.add_argument("--julia-depot", type=Path, required=True)
    parser.add_argument("--julia-depot-entry-count", type=int, required=True)
    parser.add_argument("--julia-depot-regular-bytes", type=int, required=True)
    parser.add_argument("--julia-depot-tree-sha256", required=True)
    parser.add_argument("--wsl-home", required=True)
    parser.add_argument("--julia-version", required=True)
    parser.add_argument("--fmi-jl-version", required=True)
    parser.add_argument("--runner", type=Path, required=True)
    parser.add_argument("--runner-size-bytes", type=int, required=True)
    parser.add_argument("--runner-sha256", required=True)
    parser.add_argument("--plant-fmu", type=Path, required=True)
    parser.add_argument("--plant-fmu-size-bytes", type=int, required=True)
    parser.add_argument("--plant-fmu-sha256", required=True)
    parser.add_argument("--governor-fmu", type=Path, required=True)
    parser.add_argument("--governor-fmu-size-bytes", type=int, required=True)
    parser.add_argument("--governor-fmu-sha256", required=True)
    parser.add_argument("--reference-manifest", type=Path, required=True)
    parser.add_argument(
        "--reference-manifest-size-bytes", type=int, required=True
    )
    parser.add_argument("--reference-manifest-sha256", required=True)
    parser.add_argument("--process-timeout-seconds", type=float, required=True)
    parser.add_argument("--stream-limit-bytes", type=int, required=True)
    arguments: argparse.Namespace = parser.parse_args()
    config: FmiJlComparisonConfig = FmiJlComparisonConfig(
        output_directory=arguments.output_dir,
        source_branch=arguments.source_branch,
        source_revision=arguments.source_revision,
        source_tree_sha256=arguments.source_tree_sha256,
        wsl_executable_path=arguments.wsl_executable,
        wsl_executable_size_bytes=arguments.wsl_executable_size_bytes,
        wsl_executable_sha256=arguments.wsl_executable_sha256,
        wsl_distribution=arguments.wsl_distribution,
        wsl_version=arguments.wsl_version,
        wsl_distribution_pretty_name=arguments.wsl_distribution_pretty_name,
        wsl_distribution_version_id=arguments.wsl_distribution_version_id,
        wsl_architecture=arguments.wsl_architecture,
        wsl_kernel=arguments.wsl_kernel,
        wsl_glibc_version=arguments.wsl_glibc_version,
        wsl_python_executable_path=arguments.wsl_python_executable,
        wsl_python_executable_size_bytes=(
            arguments.wsl_python_executable_size_bytes
        ),
        wsl_python_executable_sha256=arguments.wsl_python_executable_sha256,
        wsl_python_version=arguments.wsl_python_version,
        julia_archive_path=arguments.julia_archive,
        julia_archive_size_bytes=arguments.julia_archive_size_bytes,
        julia_archive_sha256=arguments.julia_archive_sha256,
        julia_executable_path=arguments.julia_executable,
        julia_executable_size_bytes=arguments.julia_executable_size_bytes,
        julia_executable_sha256=arguments.julia_executable_sha256,
        julia_runtime_entry_count=arguments.julia_runtime_entry_count,
        julia_runtime_regular_bytes=arguments.julia_runtime_regular_bytes,
        julia_runtime_tree_sha256=arguments.julia_runtime_tree_sha256,
        julia_project_path=arguments.julia_project,
        julia_project_size_bytes=arguments.julia_project_size_bytes,
        julia_project_sha256=arguments.julia_project_sha256,
        julia_manifest_path=arguments.julia_manifest,
        julia_manifest_size_bytes=arguments.julia_manifest_size_bytes,
        julia_manifest_sha256=arguments.julia_manifest_sha256,
        julia_depot_path=arguments.julia_depot,
        julia_depot_entry_count=arguments.julia_depot_entry_count,
        julia_depot_regular_bytes=arguments.julia_depot_regular_bytes,
        julia_depot_tree_sha256=arguments.julia_depot_tree_sha256,
        wsl_home=arguments.wsl_home,
        julia_version=arguments.julia_version,
        fmi_jl_version=arguments.fmi_jl_version,
        runner_path=arguments.runner,
        runner_size_bytes=arguments.runner_size_bytes,
        runner_sha256=arguments.runner_sha256,
        plant_fmu_path=arguments.plant_fmu,
        plant_fmu_size_bytes=arguments.plant_fmu_size_bytes,
        plant_fmu_sha256=arguments.plant_fmu_sha256,
        governor_fmu_path=arguments.governor_fmu,
        governor_fmu_size_bytes=arguments.governor_fmu_size_bytes,
        governor_fmu_sha256=arguments.governor_fmu_sha256,
        reference_manifest_path=arguments.reference_manifest,
        reference_manifest_size_bytes=arguments.reference_manifest_size_bytes,
        reference_manifest_sha256=arguments.reference_manifest_sha256,
        process_timeout_seconds=arguments.process_timeout_seconds,
        stream_limit_bytes=arguments.stream_limit_bytes,
    )
    output_path: Path = generate_fmi_jl_comparison(config)
    print(output_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
else:
    pass
