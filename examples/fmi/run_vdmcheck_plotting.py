# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
"""Command-line adapter for authenticated VDMCheck evidence figures."""
from __future__ import annotations

import argparse
from pathlib import Path

from examples.fmi.vdmcheck_plotting import (
    VdmCheckFigureConfig,
    generate_vdmcheck_figures,
)


def main() -> int:
    """Parse explicit identities and publish the figure package.

    :return: Zero after verified atomic publication.
    """

    parser: argparse.ArgumentParser = argparse.ArgumentParser(
        description="Render authenticated VDMCheck completed-with-findings evidence.",
    )
    parser.add_argument("--source-manifest", type=Path, required=True)
    parser.add_argument("--source-manifest-size-bytes", type=int, required=True)
    parser.add_argument("--source-manifest-sha256", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    arguments: argparse.Namespace = parser.parse_args()
    config: VdmCheckFigureConfig = VdmCheckFigureConfig(
        source_manifest_path=arguments.source_manifest,
        source_manifest_expected_size_bytes=arguments.source_manifest_size_bytes,
        source_manifest_expected_sha256=arguments.source_manifest_sha256,
        output_directory=arguments.output_dir,
    )
    manifest_path: Path = generate_vdmcheck_figures(config)
    print(manifest_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
else:
    pass
