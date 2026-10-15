# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
"""Command-line entry point for the OpenModelica SMIB comparison."""
from __future__ import annotations

import argparse
from pathlib import Path

from examples.fmi.openmodelica import (
    OpenModelicaBuildConfig,
    OpenModelicaBuildEvidence,
    build_openmodelica_smib_evidence,
)
from examples.fmi.smib_comparison import (
    SmibComparisonConfig,
    generate_smib_comparison,
)


def main() -> int:
    """Parse pinned identities, build the FMU and run all four tool paths.

    :return: Process status code, zero after both packages publish.
    """

    parser: argparse.ArgumentParser = argparse.ArgumentParser(
        description="Build and compare the maintained dynamic SMIB FMI 2 CS model."
    )
    parser.add_argument("--source-path", required=True, type=Path)
    parser.add_argument("--source-size-bytes", required=True, type=int)
    parser.add_argument("--source-sha256", required=True)
    parser.add_argument("--omc-executable", required=True, type=Path)
    parser.add_argument("--omc-version", required=True)
    parser.add_argument("--omc-size-bytes", required=True, type=int)
    parser.add_argument("--omc-sha256", required=True)
    parser.add_argument("--build-output-dir", required=True, type=Path)
    parser.add_argument("--omsimulator-executable", required=True, type=Path)
    parser.add_argument("--omsimulator-version", required=True)
    parser.add_argument("--omsimulator-size-bytes", required=True, type=int)
    parser.add_argument("--omsimulator-sha256", required=True)
    parser.add_argument("--fmpy-version", required=True)
    parser.add_argument("--fmpy-distribution-sha256", required=True)
    parser.add_argument("--comparison-output-dir", required=True, type=Path)
    parser.add_argument("--build-timeout-seconds", type=float, default=180.0)
    parser.add_argument("--simulation-timeout-seconds", type=float, default=70.0)
    arguments: argparse.Namespace = parser.parse_args()

    build_config: OpenModelicaBuildConfig = OpenModelicaBuildConfig(
        source_path=arguments.source_path,
        source_expected_size_bytes=arguments.source_size_bytes,
        source_expected_sha256=arguments.source_sha256,
        omc_executable=arguments.omc_executable,
        omc_expected_version=arguments.omc_version,
        omc_expected_size_bytes=arguments.omc_size_bytes,
        omc_expected_sha256=arguments.omc_sha256,
        output_directory=arguments.build_output_dir,
        stop_time=4.0,
        step_size=0.002,
        process_timeout_seconds=arguments.build_timeout_seconds,
    )
    build_evidence: OpenModelicaBuildEvidence = build_openmodelica_smib_evidence(
        build_config
    )
    comparison_config: SmibComparisonConfig = SmibComparisonConfig(
        build_evidence=build_evidence,
        omsimulator_executable=arguments.omsimulator_executable,
        omsimulator_expected_version=arguments.omsimulator_version,
        omsimulator_expected_size_bytes=arguments.omsimulator_size_bytes,
        omsimulator_expected_sha256=arguments.omsimulator_sha256,
        fmpy_expected_version=arguments.fmpy_version,
        fmpy_expected_distribution_sha256=arguments.fmpy_distribution_sha256,
        output_directory=arguments.comparison_output_dir,
        process_timeout_seconds=arguments.simulation_timeout_seconds,
        communication_step=0.000125,
        output_interval=0.002,
        convergence_step_sizes=(0.002, 0.001, 0.0005, 0.00025, 0.000125),
    )
    comparison_manifest: Path = generate_smib_comparison(comparison_config)
    print(build_evidence.fmu_path)
    print(comparison_manifest)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
else:
    pass
