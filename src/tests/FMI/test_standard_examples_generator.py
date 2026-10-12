"""Focused platform-publication tests for the standard FMI example generator."""

from __future__ import annotations

import json
from pathlib import Path
import tempfile

import pytest

from VeraGridEngine.IO.fmu.config import TargetPlatform
from examples.fmi.veragrid_standard_examples.generate_standard_examples import (
    resolve_publication_layout,
    write_manifest,
)


def test_publication_layout_contract() -> None:
    """Accept only an absent destination matching one shared host platform.

    :return: None.
    """
    with tempfile.TemporaryDirectory() as temporary_name:
        temporary_root: Path = Path(temporary_name)
        # Compare canonical destinations, including macOS /tmp alias resolution.
        repository_root: Path = (temporary_root / "repository").resolve(strict=False)
        repository_root.mkdir()
        target_platform: TargetPlatform
        for target_platform in TargetPlatform:
            publication_root: Path = (
                repository_root / "examples" / "fmi" / "veragrid_standard_examples"
                / "published" / target_platform.value
            )
            observed_platform: TargetPlatform
            stage_root: Path
            observed_platform, stage_root = resolve_publication_layout(
                repository_root, publication_root, target_platform, target_platform,
            )
            assert observed_platform is target_platform
            assert stage_root == publication_root.parent / (
                "." + target_platform.value + "-stage"
            )

        linux_root: Path = (
            repository_root / "examples" / "fmi" / "veragrid_standard_examples"
            / "published" / TargetPlatform.LINUX64.value
        )
        with pytest.raises(RuntimeError, match="different host platforms"):
            resolve_publication_layout(
                repository_root, linux_root,
                TargetPlatform.LINUX64, TargetPlatform.DARWIN_ARM64,
            )
        with pytest.raises(ValueError, match="contracted published/linux64"):
            resolve_publication_layout(
                repository_root, linux_root.parent / "wrong",
                TargetPlatform.LINUX64, TargetPlatform.LINUX64,
            )

        linux_root.mkdir(parents=True)
        with pytest.raises(FileExistsError, match="root already exists"):
            resolve_publication_layout(
                repository_root, linux_root,
                TargetPlatform.LINUX64, TargetPlatform.LINUX64,
            )
        linux_root.rmdir()
        linux_stage: Path = linux_root.parent / ".linux64-stage"
        linux_stage.mkdir()
        with pytest.raises(FileExistsError, match="stage already exists"):
            resolve_publication_layout(
                repository_root, linux_root,
                TargetPlatform.LINUX64, TargetPlatform.LINUX64,
            )


def test_manifest_platform_contract() -> None:
    """Record the supplied existing platform key and canonical public origin.

    :return: None.
    """
    with tempfile.TemporaryDirectory() as temporary_name:
        manifest_path: Path = Path(temporary_name) / "manifest.json"
        family_metrics: dict[str, dict[str, float]] = dict()
        write_manifest(
            manifest_path, "0" * 40, "1" * 64, "2" * 64,
            TargetPlatform.LINUX64.value, tuple(), family_metrics,
        )
        manifest_value: object = json.loads(manifest_path.read_text(encoding="utf-8"))
        assert isinstance(manifest_value, dict)
        assert manifest_value["platform"] == TargetPlatform.LINUX64.value
        assert manifest_value["source_origin"] == "https://github.com/SanPen/VeraGrid"
        assert manifest_value["distribution_status"] == (
            "PENDING_PUBLIC_URL_ACTIVATION_AFTER_INTEGRATION"
        )
        assert manifest_value["presentation_status"] == (
            "FMI_TOOLS_GUIDE_CONFORMANT"
        )
        assert manifest_value["interoperability_evidence"] == (
            "../../../INTEROPERABILITY_STATUS.md"
        )


def test_generated_metadata_contract() -> None:
    """Reject live Windows-only or obsolete-origin metadata in the recipe.

    :return: None.
    """
    generator_path: Path = (
        Path(__file__).resolve().parents[3]
        / "examples" / "fmi" / "veragrid_standard_examples"
        / "generate_standard_examples.py"
    )
    generator_source: str = generator_path.read_text(encoding="utf-8")
    forbidden_literals: tuple[str, ...] = (
        "win" + "64",
        "https://github.com/eRoots-Analytics/" + "VeraGrid",
    )
    forbidden_literal: str
    for forbidden_literal in forbidden_literals:
        assert forbidden_literal not in generator_source
    assert "https://github.com/SanPen/VeraGrid" in generator_source
    assert "platform_key" in generator_source
