# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
"""Command-line adapter for the Reference FMU execution package."""
from __future__ import annotations

import argparse
from pathlib import Path

from examples.fmi.reference_fmu_execution import (
    ReferenceFmuExecutionConfig,
    generate_reference_fmu_comparison,
)


def main() -> int:
    """Parse explicit paths and identities, then run the comparison.

    :return: Process status, zero after successful atomic publication.
    """

    parser: argparse.ArgumentParser = argparse.ArgumentParser(
        description="Execute the sealed Reference FMU FMPy/fmusim matrix.",
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--source-branch", required=True)
    parser.add_argument("--source-revision", required=True)
    parser.add_argument("--source-tree-sha256", required=True)
    parser.add_argument("--catalog-path", type=Path, required=True)
    parser.add_argument("--corpus-root", type=Path, required=True)
    parser.add_argument("--fmpy-version", required=True)
    parser.add_argument("--fmpy-distribution-sha256", required=True)
    parser.add_argument("--fmusim-executable", type=Path, required=True)
    parser.add_argument("--fmusim-size-bytes", type=int, required=True)
    parser.add_argument("--fmusim-sha256", required=True)
    parser.add_argument("--fmusim-version", required=True)
    arguments: argparse.Namespace = parser.parse_args()
    config: ReferenceFmuExecutionConfig = ReferenceFmuExecutionConfig(
        output_dir=arguments.output_dir,
        source_branch=arguments.source_branch,
        source_revision=arguments.source_revision,
        source_tree_sha256=arguments.source_tree_sha256,
        catalog_path=arguments.catalog_path,
        corpus_root=arguments.corpus_root,
        fmpy_expected_version=arguments.fmpy_version,
        fmpy_expected_distribution_sha256=(
            arguments.fmpy_distribution_sha256
        ),
        fmusim_executable=arguments.fmusim_executable,
        fmusim_expected_size_bytes=arguments.fmusim_size_bytes,
        fmusim_expected_sha256=arguments.fmusim_sha256,
        fmusim_expected_version=arguments.fmusim_version,
    )
    output_path: Path = generate_reference_fmu_comparison(config)
    print(output_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
