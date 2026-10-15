# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
"""Command-line entry point for the isolated PathSim-FMI comparison."""
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

from examples.fmi.pathsim import (
    PathSimComparisonConfig,
    generate_pathsim_comparison,
)


def main() -> int:
    """Parse explicit evidence paths and publish one PathSim package.

    :return: Zero after the package passes complete re-verification.
    """

    parser: argparse.ArgumentParser = argparse.ArgumentParser(
        description="Run the authenticated PathSim-FMI open-source matrix.",
    )
    parser.add_argument("--output", required=True)
    parser.add_argument("--source-branch", required=True)
    parser.add_argument("--source-revision", required=True)
    parser.add_argument("--source-tree-sha256", required=True)
    parser.add_argument("--runtime-root", required=True)
    parser.add_argument("--python", required=True)
    parser.add_argument("--system-root", required=True)
    parser.add_argument("--processor-architecture", required=True)
    parser.add_argument("--catalog", required=True)
    parser.add_argument("--archive", required=True)
    parser.add_argument("--fmi2-bouncing-ball", required=True)
    parser.add_argument("--fmi2-stair", required=True)
    parser.add_argument("--fmi3-bouncing-ball", required=True)
    parser.add_argument("--fmi3-stair", required=True)
    parser.add_argument("--reference-manifest", required=True)
    arguments: argparse.Namespace = parser.parse_args()

    catalog_path: Path = Path(arguments.catalog).resolve(strict=True)
    catalog_bytes: bytes = catalog_path.read_bytes()
    worker_path: Path = Path(__file__).with_name("pathsim_worker.py").resolve(
        strict=True
    )
    worker_bytes: bytes = worker_path.read_bytes()
    config: PathSimComparisonConfig = PathSimComparisonConfig(
        output_directory=Path(arguments.output).resolve(strict=False),
        source_branch=arguments.source_branch,
        source_revision=arguments.source_revision,
        source_tree_sha256=arguments.source_tree_sha256,
        runtime_root=Path(arguments.runtime_root).resolve(strict=True),
        runtime_entry_count=13_024,
        runtime_regular_bytes=428_818_054,
        runtime_tree_sha256=(
            "15899e333049b92e3fd8de68bc63492e1b5ea523c08097301df12e5e1aed8e90"
        ),
        python_executable_path=Path(arguments.python).resolve(strict=True),
        python_executable_size_bytes=274_712,
        python_executable_sha256=(
            "21bb438c0d4a6f1f164b9a646f6ee000340185e5871180aec06db8d3f07c0082"
        ),
        system_root_path=Path(arguments.system_root).resolve(strict=True),
        processor_architecture=arguments.processor_architecture,
        catalog_path=catalog_path,
        catalog_size_bytes=len(catalog_bytes),
        catalog_sha256=hashlib.sha256(catalog_bytes).hexdigest(),
        archive_path=Path(arguments.archive).resolve(strict=True),
        archive_size_bytes=3_390_239,
        archive_sha256=(
            "62babca76b9c23a51c3096be4bb5930ff8b4388659056be3c0c4ef7a3aeb5403"
        ),
        fmu_paths=(
            Path(arguments.fmi2_bouncing_ball).resolve(strict=True),
            Path(arguments.fmi2_stair).resolve(strict=True),
            Path(arguments.fmi3_bouncing_ball).resolve(strict=True),
            Path(arguments.fmi3_stair).resolve(strict=True),
        ),
        reference_manifest_path=Path(arguments.reference_manifest).resolve(
            strict=True
        ),
        reference_manifest_size_bytes=26_321,
        reference_manifest_sha256=(
            "7c0dce184104e6ff78bb38cb234c7159cc33fa2ed352ec9c7955d787d8d27c78"
        ),
        worker_path=worker_path,
        worker_size_bytes=len(worker_bytes),
        worker_sha256=hashlib.sha256(worker_bytes).hexdigest(),
        process_timeout_seconds=120.0,
        stream_limit_bytes=1_048_576,
    )
    manifest_path: Path = generate_pathsim_comparison(config)
    print(manifest_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
