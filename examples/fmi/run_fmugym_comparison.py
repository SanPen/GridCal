# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
"""Command-line entry point for the isolated FMUGym-FMPy comparison."""
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

from examples.fmi.fmugym import (
    FmugymComparisonConfig,
    generate_fmugym_comparison,
)


def main() -> int:
    """Parse explicit evidence paths and publish one FMUGym package.

    :return: Zero after the package passes complete re-verification.
    """

    parser: argparse.ArgumentParser = argparse.ArgumentParser(
        description="Run the authenticated FMUGym-FMPy open-source comparison.",
    )
    parser.add_argument("--output", required=True)
    parser.add_argument("--source-branch", required=True)
    parser.add_argument("--source-revision", required=True)
    parser.add_argument("--source-tree-sha256", required=True)
    parser.add_argument("--runtime-root", required=True)
    parser.add_argument("--wheel", required=True)
    parser.add_argument("--system-root", required=True)
    parser.add_argument("--processor-architecture", required=True)
    parser.add_argument("--fmi2-smib", required=True)
    parser.add_argument("--fmi3-feedthrough", required=True)
    arguments: argparse.Namespace = parser.parse_args()

    worker_path: Path = Path(__file__).with_name("fmugym_worker.py").resolve(
        strict=True
    )
    worker_bytes: bytes = worker_path.read_bytes()
    config: FmugymComparisonConfig = FmugymComparisonConfig(
        output_directory=Path(arguments.output).resolve(strict=False),
        source_branch=arguments.source_branch,
        source_revision=arguments.source_revision,
        source_tree_sha256=arguments.source_tree_sha256,
        runtime_root=Path(arguments.runtime_root).resolve(strict=True),
        runtime_entry_count=10_748,
        runtime_regular_bytes=292_058_959,
        runtime_tree_sha256=(
            "37f979dba3e17665d2dcf582ef1e70cbec098c1274459bd57e8dc7279cb9f4b5"
        ),
        python_executable_size_bytes=274_712,
        python_executable_sha256=(
            "21bb438c0d4a6f1f164b9a646f6ee000340185e5871180aec06db8d3f07c0082"
        ),
        wheel_path=Path(arguments.wheel).resolve(strict=True),
        wheel_size_bytes=12_237,
        wheel_sha256=(
            "9ffb332f2f0c347cea7e7039f1e938b2aeec4a18f76e1a6879ade97749d7d98e"
        ),
        system_root_path=Path(arguments.system_root).resolve(strict=True),
        processor_architecture=arguments.processor_architecture,
        fmi_two_path=Path(arguments.fmi2_smib).resolve(strict=True),
        fmi_two_size_bytes=1_383_924,
        fmi_two_sha256=(
            "76d1b0588be8865c12581977b01c5f1946e2ac94dd00f3679409e893fb87ad6a"
        ),
        fmi_three_path=Path(arguments.fmi3_feedthrough).resolve(strict=True),
        fmi_three_size_bytes=255_474,
        fmi_three_sha256=(
            "cbb038007286be266707fb919ed4614ea3c5eba3c18941e3d50482a2b8e467c9"
        ),
        worker_path=worker_path,
        worker_size_bytes=len(worker_bytes),
        worker_sha256=hashlib.sha256(worker_bytes).hexdigest(),
        process_timeout_seconds=120.0,
        stream_limit_bytes=1_048_576,
    )
    manifest_path: Path = generate_fmugym_comparison(config)
    print(manifest_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
