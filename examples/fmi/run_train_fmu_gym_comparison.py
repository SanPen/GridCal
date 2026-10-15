"""Command-line entry point for the train_fmu_gym comparison."""

from __future__ import annotations

import argparse
from pathlib import Path

from examples.fmi.train_fmu_gym import (
    TrainFmuGymComparisonConfig,
    generate_train_fmu_gym_comparison,
)


def main() -> int:
    """Parse explicit identities and publish one comparison package.

    :return: Zero after the package passes complete verification.
    """

    parser: argparse.ArgumentParser = argparse.ArgumentParser()
    parser.add_argument("--output-directory", required=True, type=Path)
    parser.add_argument("--source-branch", required=True)
    parser.add_argument("--source-revision", required=True)
    parser.add_argument("--source-tree-sha256", required=True)
    parser.add_argument("--upstream-root", required=True, type=Path)
    parser.add_argument("--upstream-commit", required=True)
    parser.add_argument("--upstream-git-tree", required=True)
    parser.add_argument("--runtime-root", required=True, type=Path)
    parser.add_argument("--runtime-file-count", required=True, type=int)
    parser.add_argument("--runtime-total-size-bytes", required=True, type=int)
    parser.add_argument("--runtime-tree-sha256", required=True)
    parser.add_argument("--python-size-bytes", required=True, type=int)
    parser.add_argument("--python-sha256", required=True)
    parser.add_argument("--cli-python-path", required=True, type=Path)
    parser.add_argument("--cli-python-size-bytes", required=True, type=int)
    parser.add_argument("--cli-python-sha256", required=True)
    parser.add_argument("--worker-path", required=True, type=Path)
    parser.add_argument("--worker-size-bytes", required=True, type=int)
    parser.add_argument("--worker-sha256", required=True)
    parser.add_argument("--fmi-two-path", required=True, type=Path)
    parser.add_argument("--fmi-two-size-bytes", required=True, type=int)
    parser.add_argument("--fmi-two-sha256", required=True)
    parser.add_argument("--fmi-three-path", required=True, type=Path)
    parser.add_argument("--fmi-three-size-bytes", required=True, type=int)
    parser.add_argument("--fmi-three-sha256", required=True)
    parser.add_argument("--system-root", required=True, type=Path)
    parser.add_argument("--temporary-directory", required=True, type=Path)
    parser.add_argument("--processor-architecture", required=True)
    parser.add_argument("--process-timeout-seconds", required=True, type=float)
    parser.add_argument("--stream-limit-bytes", required=True, type=int)
    arguments: argparse.Namespace = parser.parse_args()
    config: TrainFmuGymComparisonConfig = TrainFmuGymComparisonConfig(
        output_directory=arguments.output_directory,
        source_branch=arguments.source_branch,
        source_revision=arguments.source_revision,
        source_tree_sha256=arguments.source_tree_sha256,
        upstream_root=arguments.upstream_root,
        upstream_commit=arguments.upstream_commit,
        upstream_git_tree=arguments.upstream_git_tree,
        runtime_root=arguments.runtime_root,
        runtime_file_count=arguments.runtime_file_count,
        runtime_total_size_bytes=arguments.runtime_total_size_bytes,
        runtime_tree_sha256=arguments.runtime_tree_sha256,
        python_size_bytes=arguments.python_size_bytes,
        python_sha256=arguments.python_sha256,
        cli_python_path=arguments.cli_python_path,
        cli_python_size_bytes=arguments.cli_python_size_bytes,
        cli_python_sha256=arguments.cli_python_sha256,
        worker_path=arguments.worker_path,
        worker_size_bytes=arguments.worker_size_bytes,
        worker_sha256=arguments.worker_sha256,
        fmi_two_path=arguments.fmi_two_path,
        fmi_two_size_bytes=arguments.fmi_two_size_bytes,
        fmi_two_sha256=arguments.fmi_two_sha256,
        fmi_three_path=arguments.fmi_three_path,
        fmi_three_size_bytes=arguments.fmi_three_size_bytes,
        fmi_three_sha256=arguments.fmi_three_sha256,
        system_root=arguments.system_root,
        temporary_directory=arguments.temporary_directory,
        processor_architecture=arguments.processor_architecture,
        process_timeout_seconds=arguments.process_timeout_seconds,
        stream_limit_bytes=arguments.stream_limit_bytes,
    )
    package_path: Path = generate_train_fmu_gym_comparison(config)
    print(package_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

