# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations

import argparse
from pathlib import Path

from examples.fmi.rms_comparison import (
    RmsFmiComparisonConfig,
    generate_rms_fmi_comparison,
)


def main() -> int:
    """Generate one RMS FMI comparison package from explicit caller inputs.

    :return: Process exit status.
    """

    parser: argparse.ArgumentParser = argparse.ArgumentParser(
        description=(
            "Generate atomically published candidate evidence for VeraGrid "
            "RMS FMI 2 Co-Simulation and Model Exchange integration."
        )
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        required=True,
        help="Nonexistent final package directory.",
    )
    parser.add_argument(
        "--source-revision",
        required=True,
        help="Caller-declared source revision; the generator does not invoke Git.",
    )
    parser.add_argument(
        "--source-tree-sha256",
        required=True,
        help="Caller-declared lowercase SHA-256 of the complete source tree.",
    )
    parser.add_argument(
        "--omsimulator-executable",
        type=Path,
        required=True,
        help="Explicit installed OMSimulator executable.",
    )
    parser.add_argument(
        "--absolute-tolerance",
        type=float,
        default=1.0e-12,
        help="Floating-point absolute comparison term.",
    )
    parser.add_argument(
        "--relative-tolerance",
        type=float,
        default=1.0e-10,
        help="Floating-point relative comparison coefficient.",
    )
    arguments: argparse.Namespace = parser.parse_args()
    config: RmsFmiComparisonConfig = RmsFmiComparisonConfig(
        output_dir=arguments.output_dir,
        source_revision=arguments.source_revision,
        source_tree_sha256=arguments.source_tree_sha256,
        omsimulator_executable=arguments.omsimulator_executable,
        absolute_tolerance=arguments.absolute_tolerance,
        relative_tolerance=arguments.relative_tolerance,
    )
    published_dir: Path = generate_rms_fmi_comparison(config)
    print(published_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
else:
    pass
