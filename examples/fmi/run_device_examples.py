# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
"""Run all FMU device import examples and print the generated reports."""

from __future__ import annotations

import argparse
from pathlib import Path

from examples.fmi.fmi_example_runner import (
    run_emt_cs_example,
    run_emt_me_example,
    run_rms_cs_example,
    run_rms_me_example,
)


def main() -> int:
    """Execute the four FMU device import examples and print their report paths.

    :return: Process exit code.
    """

    parser: argparse.ArgumentParser = argparse.ArgumentParser(
        description="Run the four repository FMI device examples."
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        required=True,
        help="Directory that will own generated FMUs and reports.",
    )
    arguments: argparse.Namespace = parser.parse_args()
    output_dir: Path = arguments.output_dir.resolve()
    reports: tuple[Path, ...] = (
        run_rms_cs_example(output_dir),
        run_rms_me_example(output_dir),
        run_emt_cs_example(output_dir),
        run_emt_me_example(output_dir),
    )
    report_path: Path
    for report_path in reports:
        print(report_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
