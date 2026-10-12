# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

from typing import cast

import pytest

from VeraGridEngine.enumerations import FmiVersion
from VeraGridEngine.IO.fmu.config import normalize_fmi_export_version, parse_declared_fmi_version


def test_fmi_version_members_have_stable_identity_and_order() -> None:
    """Verify the canonical family values and their presentation order."""

    versions: tuple[FmiVersion, ...] = tuple(FmiVersion)

    assert versions == (
        FmiVersion.FMI_1_0,
        FmiVersion.FMI_2_0,
        FmiVersion.FMI_3_0,
    )
    assert tuple(version.value for version in versions) == ("1.0", "2.0", "3.0")


@pytest.mark.parametrize(
    ("declared_version", "expected_family"),
    (
        ("1.0", FmiVersion.FMI_1_0),
        ("2.0", FmiVersion.FMI_2_0),
        ("3.0", FmiVersion.FMI_3_0),
        ("3.0.0", FmiVersion.FMI_3_0),
        ("3.0.1", FmiVersion.FMI_3_0),
        ("3.0.2", FmiVersion.FMI_3_0),
        ("3.0.999", FmiVersion.FMI_3_0),
    ),
)
def test_declared_versions_resolve_to_supported_families(
    declared_version: str,
    expected_family: FmiVersion,
) -> None:
    """Verify strict declarations map to the expected runtime family.

    :param declared_version: External version declaration under test.
    :param expected_family: Canonical family expected from the declaration.
    :return: None.
    """

    assert parse_declared_fmi_version(declared_version) is expected_family


@pytest.mark.parametrize(
    "declared_version",
    (
        "",
        "1",
        "2",
        "3",
        " 3.0.12 ",
        "3.00",
        "3.0.00",
        "3.0.02",
        "3.0-alpha.2",
        "3.1",
        "3.1.0",
        "３.０",
    ),
)
def test_invalid_or_unverified_declarations_fail_closed(declared_version: str) -> None:
    """Verify malformed and unvalidated versions cannot reach dispatch.

    :param declared_version: Unsupported declaration under test.
    :return: None.
    """

    with pytest.raises(ValueError, match="Invalid or unsupported FMI version declaration"):
        parse_declared_fmi_version(declared_version)


@pytest.mark.parametrize(
    "document_release",
    ("1.0.1", "2.0.1", "2.0.2", "2.0.3", "2.0.4", "2.0.5"),
)
def test_maintenance_document_labels_are_not_xml_declarations(document_release: str) -> None:
    """Verify maintenance document labels are not mistaken for XML values.

    FMI 1.0.1 FMUs still declare ``1.0`` and FMI 2.0.x FMUs still declare
    ``2.0``. Supporting those maintenance specifications therefore must not
    make their document release labels valid ``fmiVersion`` attributes.

    :param document_release: Maintenance specification label under test.
    :return: None.
    """

    with pytest.raises(ValueError, match="Invalid or unsupported FMI version declaration"):
        parse_declared_fmi_version(document_release)


@pytest.mark.parametrize("invalid_value", (None, 3))
def test_declared_version_rejects_non_text_values(invalid_value: object) -> None:
    """Verify the XML boundary reports a stable error for incorrect types.

    :param invalid_value: Non-textual declaration supplied at runtime.
    :return: None.
    """

    with pytest.raises(TypeError, match="FMI version declaration must be text"):
        parse_declared_fmi_version(cast(str, invalid_value))


@pytest.mark.parametrize(
    ("selection", "expected_version"),
    (
        (FmiVersion.FMI_1_0, FmiVersion.FMI_1_0),
        ("1.0", FmiVersion.FMI_1_0),
        (FmiVersion.FMI_2_0, FmiVersion.FMI_2_0),
        ("2.0", FmiVersion.FMI_2_0),
        (FmiVersion.FMI_3_0, FmiVersion.FMI_3_0),
        ("3.0", FmiVersion.FMI_3_0),
        (" 3.0 ", FmiVersion.FMI_3_0),
    ),
)
def test_public_selections_normalize_to_one_canonical_type(
    selection: FmiVersion | str,
    expected_version: FmiVersion,
) -> None:
    """Verify API values never create a second version identity.

    :param selection: Enum member or textual API selection under test.
    :param expected_version: Canonical member expected from normalization.
    :return: None.
    """

    assert normalize_fmi_export_version(selection) is expected_version


@pytest.mark.parametrize(
    "selection",
    ("", "1", "1.0.1", "2", "2.0.5", "3", "3.0.2", "3.1"),
)
def test_public_selections_do_not_silently_reduce_patch_versions(selection: str) -> None:
    """Verify export-like selections cannot discard declared patch identity.

    :param selection: Unsupported API selection under test.
    :return: None.
    """

    with pytest.raises(ValueError, match="Unsupported FMI version selection"):
        normalize_fmi_export_version(selection)


@pytest.mark.parametrize("invalid_value", (None, 3))
def test_export_version_rejects_non_text_values(invalid_value: object) -> None:
    """Verify the export boundary reports a stable error for incorrect types.

    :param invalid_value: Non-textual selection supplied at runtime.
    :return: None.
    """

    with pytest.raises(TypeError, match="FMI export-version selection must be text or FmiVersion"):
        normalize_fmi_export_version(cast(FmiVersion | str, invalid_value))
