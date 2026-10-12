# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations

from pathlib import Path
import shutil
import zipfile


def prepare_fmu_staging_dir(staging_dir: str | Path) -> Path:
    """Execute the `prepare_fmu_staging_dir` operation.

    :param staging_dir: Function input.
    :return: Function result.
    """
    root = Path(staging_dir)
    if root.exists():
        shutil.rmtree(root)
    (root / "resources").mkdir(parents=True, exist_ok=True)
    return root


def package_fmu(staging_dir: str | Path, output_path: str | Path) -> Path:
    """Execute the `package_fmu` operation.

    :param staging_dir: Function input.
    :param output_path: Function input.
    :return: Function result.
    """
    staging_root = Path(staging_dir)
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    tmp_zip = output.with_suffix(".zip")
    if tmp_zip.exists():
        tmp_zip.unlink()
    with zipfile.ZipFile(tmp_zip, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for file_path in sorted(staging_root.rglob("*")):
            if file_path.is_file():
                archive.write(file_path, file_path.relative_to(staging_root).as_posix())
    if output.exists():
        output.unlink()
    tmp_zip.replace(output)
    return output
