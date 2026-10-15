# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
"""Command-line adapter for the VDMCheck static-validation package."""
from __future__ import annotations

import argparse
from pathlib import Path

from examples.fmi.vdmcheck import (
    VdmCheckValidationConfig,
    generate_vdmcheck_validation,
)


def main() -> int:
    """Parse explicit tool identities and run the sealed validation matrix.

    :return: Process status, zero after complete atomic publication.
    """

    parser: argparse.ArgumentParser = argparse.ArgumentParser(
        description="Validate the sealed Reference FMUs with FMPy and VDMCheck.",
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--source-branch", required=True)
    parser.add_argument("--source-revision", required=True)
    parser.add_argument("--source-tree-sha256", required=True)
    parser.add_argument("--catalog-path", type=Path, required=True)
    parser.add_argument("--corpus-root", type=Path, required=True)
    parser.add_argument("--fmpy-version", required=True)
    parser.add_argument("--fmpy-distribution-sha256", required=True)
    parser.add_argument("--java-runtime-root", type=Path, required=True)
    parser.add_argument("--java-runtime-file-count", type=int, required=True)
    parser.add_argument("--java-runtime-size-bytes", type=int, required=True)
    parser.add_argument("--java-runtime-tree-sha256", required=True)
    parser.add_argument("--java-version", required=True)
    parser.add_argument("--vdmcheck-two-root", type=Path, required=True)
    parser.add_argument("--vdmcheck-two-file-count", type=int, required=True)
    parser.add_argument("--vdmcheck-two-size-bytes", type=int, required=True)
    parser.add_argument("--vdmcheck-two-tree-sha256", required=True)
    parser.add_argument("--vdmcheck-two-version", required=True)
    parser.add_argument("--vdmcheck-three-root", type=Path, required=True)
    parser.add_argument("--vdmcheck-three-file-count", type=int, required=True)
    parser.add_argument("--vdmcheck-three-size-bytes", type=int, required=True)
    parser.add_argument("--vdmcheck-three-tree-sha256", required=True)
    parser.add_argument("--vdmcheck-three-version", required=True)
    parser.add_argument("--process-timeout-seconds", type=float, required=True)
    parser.add_argument("--stream-limit-bytes", type=int, required=True)
    arguments: argparse.Namespace = parser.parse_args()

    # The CLI only translates caller-owned values into the typed validation owner.
    config: VdmCheckValidationConfig = VdmCheckValidationConfig(
        output_directory=arguments.output_dir,
        source_branch=arguments.source_branch,
        source_revision=arguments.source_revision,
        source_tree_sha256=arguments.source_tree_sha256,
        catalog_path=arguments.catalog_path,
        corpus_root=arguments.corpus_root,
        fmpy_expected_version=arguments.fmpy_version,
        fmpy_expected_distribution_sha256=(
            arguments.fmpy_distribution_sha256
        ),
        java_runtime_root=arguments.java_runtime_root,
        java_runtime_expected_file_count=arguments.java_runtime_file_count,
        java_runtime_expected_total_size_bytes=(
            arguments.java_runtime_size_bytes
        ),
        java_runtime_expected_tree_sha256=(
            arguments.java_runtime_tree_sha256
        ),
        java_expected_version=arguments.java_version,
        vdmcheck_two_root=arguments.vdmcheck_two_root,
        vdmcheck_two_expected_file_count=arguments.vdmcheck_two_file_count,
        vdmcheck_two_expected_total_size_bytes=arguments.vdmcheck_two_size_bytes,
        vdmcheck_two_expected_tree_sha256=arguments.vdmcheck_two_tree_sha256,
        vdmcheck_two_expected_version=arguments.vdmcheck_two_version,
        vdmcheck_three_root=arguments.vdmcheck_three_root,
        vdmcheck_three_expected_file_count=arguments.vdmcheck_three_file_count,
        vdmcheck_three_expected_total_size_bytes=(
            arguments.vdmcheck_three_size_bytes
        ),
        vdmcheck_three_expected_tree_sha256=(
            arguments.vdmcheck_three_tree_sha256
        ),
        vdmcheck_three_expected_version=arguments.vdmcheck_three_version,
        process_timeout_seconds=arguments.process_timeout_seconds,
        stream_limit_bytes=arguments.stream_limit_bytes,
    )
    output_path: Path = generate_vdmcheck_validation(config)
    print(output_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
else:
    pass
