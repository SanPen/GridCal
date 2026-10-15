# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
"""Command-line adapter for the authenticated libcosim comparison."""
from __future__ import annotations

import argparse
from pathlib import Path

from examples.fmi.libcosim import (
    LibcosimComparisonConfig,
    generate_libcosim_comparison,
)


def main() -> int:
    """Parse explicit identities and execute the comparison.

    :return: Zero after verified atomic publication.
    """

    parser: argparse.ArgumentParser = argparse.ArgumentParser(
        description=(
            "Compare a delayed two-FMU composition in libcosim and VeraGrid."
        )
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--source-branch", required=True)
    parser.add_argument("--source-revision", required=True)
    parser.add_argument("--source-tree-sha256", required=True)
    parser.add_argument("--wsl-executable", type=Path, required=True)
    parser.add_argument("--wsl-executable-size-bytes", type=int, required=True)
    parser.add_argument("--wsl-executable-sha256", required=True)
    parser.add_argument("--wsl-version", required=True)
    parser.add_argument("--wsl-distribution", required=True)
    parser.add_argument("--wsl-distribution-pretty-name", required=True)
    parser.add_argument("--wsl-distribution-version-id", required=True)
    parser.add_argument("--wsl-architecture", required=True)
    parser.add_argument("--wsl-kernel", required=True)
    parser.add_argument("--wsl-glibc-version", required=True)
    parser.add_argument("--libcosim-bundle", type=Path, required=True)
    parser.add_argument("--libcosim-bundle-size-bytes", type=int, required=True)
    parser.add_argument("--libcosim-bundle-sha256", required=True)
    parser.add_argument("--cosim-version", required=True)
    parser.add_argument("--libcosim-version", required=True)
    parser.add_argument("--reference-manifest", type=Path, required=True)
    parser.add_argument(
        "--reference-manifest-size-bytes", type=int, required=True
    )
    parser.add_argument("--reference-manifest-sha256", required=True)
    parser.add_argument("--plant-fmu", type=Path, required=True)
    parser.add_argument("--plant-fmu-size-bytes", type=int, required=True)
    parser.add_argument("--plant-fmu-sha256", required=True)
    parser.add_argument("--governor-fmu", type=Path, required=True)
    parser.add_argument("--governor-fmu-size-bytes", type=int, required=True)
    parser.add_argument("--governor-fmu-sha256", required=True)
    parser.add_argument("--process-timeout-seconds", type=float, required=True)
    parser.add_argument("--stream-limit-bytes", type=int, required=True)
    arguments: argparse.Namespace = parser.parse_args()
    config: LibcosimComparisonConfig = LibcosimComparisonConfig(
        output_directory=arguments.output_dir,
        source_branch=arguments.source_branch,
        source_revision=arguments.source_revision,
        source_tree_sha256=arguments.source_tree_sha256,
        wsl_executable_path=arguments.wsl_executable,
        wsl_executable_expected_size_bytes=(
            arguments.wsl_executable_size_bytes
        ),
        wsl_executable_expected_sha256=arguments.wsl_executable_sha256,
        wsl_expected_version=arguments.wsl_version,
        wsl_distribution_name=arguments.wsl_distribution,
        wsl_expected_distribution_pretty_name=(
            arguments.wsl_distribution_pretty_name
        ),
        wsl_expected_distribution_version_id=(
            arguments.wsl_distribution_version_id
        ),
        wsl_expected_architecture=arguments.wsl_architecture,
        wsl_expected_kernel=arguments.wsl_kernel,
        wsl_expected_glibc_version=arguments.wsl_glibc_version,
        libcosim_bundle_path=arguments.libcosim_bundle,
        libcosim_bundle_expected_size_bytes=(
            arguments.libcosim_bundle_size_bytes
        ),
        libcosim_bundle_expected_sha256=arguments.libcosim_bundle_sha256,
        libcosim_expected_cosim_version=arguments.cosim_version,
        libcosim_expected_library_version=arguments.libcosim_version,
        reference_manifest_path=arguments.reference_manifest,
        reference_manifest_expected_size_bytes=(
            arguments.reference_manifest_size_bytes
        ),
        reference_manifest_expected_sha256=(
            arguments.reference_manifest_sha256
        ),
        plant_fmu_path=arguments.plant_fmu,
        plant_fmu_expected_size_bytes=arguments.plant_fmu_size_bytes,
        plant_fmu_expected_sha256=arguments.plant_fmu_sha256,
        governor_fmu_path=arguments.governor_fmu,
        governor_fmu_expected_size_bytes=arguments.governor_fmu_size_bytes,
        governor_fmu_expected_sha256=arguments.governor_fmu_sha256,
        process_timeout_seconds=arguments.process_timeout_seconds,
        stream_limit_bytes=arguments.stream_limit_bytes,
    )
    manifest_path: Path = generate_libcosim_comparison(config)
    print(manifest_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
else:
    pass
