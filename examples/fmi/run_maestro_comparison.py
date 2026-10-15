# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
"""Command-line adapter for the authenticated Maestro comparison."""
from __future__ import annotations

import argparse
from pathlib import Path

from examples.fmi.maestro import (
    MaestroComparisonConfig,
    generate_maestro_comparison,
)


def main() -> int:
    """Parse explicit evidence identities and execute the comparison.

    :return: Zero after verified atomic publication.
    """

    parser: argparse.ArgumentParser = argparse.ArgumentParser(
        description="Compare a two-FMU delayed composition in Maestro and VeraGrid.",
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--source-branch", required=True)
    parser.add_argument("--source-revision", required=True)
    parser.add_argument("--source-tree-sha256", required=True)
    parser.add_argument("--java-runtime-root", type=Path, required=True)
    parser.add_argument("--java-runtime-file-count", type=int, required=True)
    parser.add_argument("--java-runtime-total-size-bytes", type=int, required=True)
    parser.add_argument("--java-runtime-tree-sha256", required=True)
    parser.add_argument("--java-version", required=True)
    parser.add_argument("--maestro-jar", type=Path, required=True)
    parser.add_argument("--maestro-jar-size-bytes", type=int, required=True)
    parser.add_argument("--maestro-jar-sha256", required=True)
    parser.add_argument("--maestro-version", required=True)
    parser.add_argument("--plant-fmu", type=Path, required=True)
    parser.add_argument("--plant-fmu-size-bytes", type=int, required=True)
    parser.add_argument("--plant-fmu-sha256", required=True)
    parser.add_argument("--governor-fmu", type=Path, required=True)
    parser.add_argument("--governor-fmu-size-bytes", type=int, required=True)
    parser.add_argument("--governor-fmu-sha256", required=True)
    parser.add_argument("--process-timeout-seconds", type=float, required=True)
    parser.add_argument("--stream-limit-bytes", type=int, required=True)
    arguments: argparse.Namespace = parser.parse_args()
    config: MaestroComparisonConfig = MaestroComparisonConfig(
        output_directory=arguments.output_dir,
        source_branch=arguments.source_branch,
        source_revision=arguments.source_revision,
        source_tree_sha256=arguments.source_tree_sha256,
        java_runtime_root=arguments.java_runtime_root,
        java_runtime_expected_file_count=arguments.java_runtime_file_count,
        java_runtime_expected_total_size_bytes=(
            arguments.java_runtime_total_size_bytes
        ),
        java_runtime_expected_tree_sha256=arguments.java_runtime_tree_sha256,
        java_expected_version=arguments.java_version,
        maestro_jar_path=arguments.maestro_jar,
        maestro_jar_expected_size_bytes=arguments.maestro_jar_size_bytes,
        maestro_jar_expected_sha256=arguments.maestro_jar_sha256,
        maestro_expected_version=arguments.maestro_version,
        plant_fmu_path=arguments.plant_fmu,
        plant_fmu_expected_size_bytes=arguments.plant_fmu_size_bytes,
        plant_fmu_expected_sha256=arguments.plant_fmu_sha256,
        governor_fmu_path=arguments.governor_fmu,
        governor_fmu_expected_size_bytes=arguments.governor_fmu_size_bytes,
        governor_fmu_expected_sha256=arguments.governor_fmu_sha256,
        process_timeout_seconds=arguments.process_timeout_seconds,
        stream_limit_bytes=arguments.stream_limit_bytes,
    )
    manifest_path: Path = generate_maestro_comparison(config)
    print(manifest_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
else:
    pass
