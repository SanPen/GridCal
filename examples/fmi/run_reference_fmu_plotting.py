# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
"""Command-line entry point for accepted Reference-FMU scientific figures."""
from __future__ import annotations

import argparse
from pathlib import Path

from examples.fmi.reference_fmu_plotting import (
    ReferenceFmuFigureConfig,
    generate_reference_fmu_figures,
)


def main() -> int:
    """Parse explicit paths and generate one closed figure package.

    :return: Process status code, zero after successful publication.
    """

    parser: argparse.ArgumentParser = argparse.ArgumentParser(
        description="Render scientific figures from accepted Reference-FMU evidence."
    )
    parser.add_argument("--manifest-path", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    arguments: argparse.Namespace = parser.parse_args()
    config: ReferenceFmuFigureConfig = ReferenceFmuFigureConfig(
        manifest_path=arguments.manifest_path,
        output_directory=arguments.output_dir,
    )
    manifest_path: Path = generate_reference_fmu_figures(config)
    print(manifest_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
else:
    pass
