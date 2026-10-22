"""Contract tests for the international-standard RMS model catalog."""

from __future__ import annotations

import keyword
from pathlib import Path

from VeraGridEngine.Devices.Dynamic.rms_template import RmsModelTemplate
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Templates.InternationalStandardsCatalog import (
    InternationalStandardTemplateDescriptor,
    load_international_standard_template,
)
from VeraGrid.Gui.DynamicModelEditor.Editor.DynamicLibrary.dynamic_editor_library import (
    get_dynamic_library_international_standard_descriptors,
)
from VeraGridEngine.Templates.Rms.international_standards import InternationalStandardModel
from VeraGridEngine.enumerations import DeviceType


def get_library_device_standard_descriptors() -> list[InternationalStandardTemplateDescriptor]:
    """Return standards registered as complete devices by the GUI Library.

    :return: Device-compatible international-standard descriptors.
    """
    return list(
        descriptor
        for descriptor in get_dynamic_library_international_standard_descriptors()
        if descriptor.device_type is not None
    )


def test_international_standards_catalog_covers_every_model_once() -> None:
    """Ensure the typed catalog contains every supported standard exactly once.

    :return: None.
    """
    descriptors: list[InternationalStandardTemplateDescriptor] = list(
        get_dynamic_library_international_standard_descriptors()
    )
    catalog_models: list[InternationalStandardModel] = list(
        descriptor.model for descriptor in descriptors
    )

    assert len(catalog_models) == len(set(catalog_models))
    assert set(catalog_models) == set(InternationalStandardModel)


def test_international_standards_catalog_paths_match_model_packages() -> None:
    """Ensure descriptor metadata points to the reorganized physical module.

    :return: None.
    """
    source_root: Path = Path(__file__).parents[2]
    standards_root: Path = (
        source_root / "VeraGridEngine" / "Templates" / "Rms" / "international_standards"
    )
    root_python_files: set[str] = set(path.name for path in standards_root.glob("*.py"))

    assert root_python_files == set(("__init__.py",))

    descriptor: InternationalStandardTemplateDescriptor
    for descriptor in get_dynamic_library_international_standard_descriptors():
        model_path: Path = standards_root / Path(descriptor.module_relative_path)
        assert model_path.is_file(), descriptor.module_relative_path
        assert len(descriptor.category_path) == 1


def test_international_standard_device_catalog_excludes_control_families() -> None:
    """Keep only complete circuit-device models in the reusable catalog.

    :return: None.
    """
    device_descriptors: list[InternationalStandardTemplateDescriptor] = list(
        get_library_device_standard_descriptors()
    )
    device_models: set[InternationalStandardModel] = set(
        descriptor.model for descriptor in device_descriptors
    )
    expected_models: set[InternationalStandardModel] = set((
        InternationalStandardModel.GENSAL,
        InternationalStandardModel.GENROU,
        InternationalStandardModel.GENTRA,
        InternationalStandardModel.GENROE,
        InternationalStandardModel.GENSAE,
        InternationalStandardModel.CIMTR1,
        InternationalStandardModel.CIMW,
        InternationalStandardModel.WT4ACURRENTSOURCE,
        InternationalStandardModel.WT4ACURRENTSOURCE2020,
        InternationalStandardModel.WT4BCURRENTSOURCE,
        InternationalStandardModel.WT4BCURRENTSOURCE2020,
        InternationalStandardModel.WT4INJECTOR,
        InternationalStandardModel.WTG4ACURRENTSOURCE,
        InternationalStandardModel.WTG4BCURRENTSOURCE,
        InternationalStandardModel.WPP4BCURRENTSOURCE2020,
        InternationalStandardModel.PVCURRENTSOURCEBNOPLANTCONTROL,
        InternationalStandardModel.PVVOLTAGESOURCEANOPLANTCONTROL,
        InternationalStandardModel.PVVOLTAGESOURCEBNOPLANTCONTROL,
        InternationalStandardModel.BESSCBCURRENTSOURCENOPLANTCONTROL,
    ))

    assert device_models == expected_models
    descriptor: InternationalStandardTemplateDescriptor
    for descriptor in device_descriptors:
        assert isinstance(descriptor.device_type, DeviceType)

    control_descriptors: list[InternationalStandardTemplateDescriptor] = list(
        descriptor
        for descriptor in get_dynamic_library_international_standard_descriptors()
        if descriptor.model not in device_models
    )
    for descriptor in control_descriptors:
        assert descriptor.device_type is None


def test_international_standard_descriptor_materializes_rms_template() -> None:
    """Ensure a catalog leaf delegates to the existing standard-model builder.

    :return: None.
    """
    descriptor: InternationalStandardTemplateDescriptor = list(
        get_dynamic_library_international_standard_descriptors()
    )[0]
    template: RmsModelTemplate = load_international_standard_template(
        descriptor=descriptor,
        var_factory=VarFactory(),
    )

    assert isinstance(template, RmsModelTemplate)
    assert template.block is not None
    assert template.name == descriptor.display_label


def test_imported_model_interfaces_and_symbol_names_are_editor_safe() -> None:
    """Keep imported model ports visible and their equation source parseable.

    :return: None.
    """
    expected_interfaces: tuple[tuple[InternationalStandardModel, int, int], ...] = (
        (InternationalStandardModel.IEEEG1, 3, 3),
        (InternationalStandardModel.IEEEG2, 3, 1),
        (InternationalStandardModel.GOVSTEAMEU, 6, 1),
        (InternationalStandardModel.AC1C, 6, 3),
        (InternationalStandardModel.AC8B, 6, 3),
        (InternationalStandardModel.AC7B, 7, 3),
        (InternationalStandardModel.AC7C, 10, 6),
        (InternationalStandardModel.AC8C, 10, 5),
        (InternationalStandardModel.ST4C, 10, 5),
        (InternationalStandardModel.ST6C, 10, 5),
        (InternationalStandardModel.DC4C, 9, 3),
        (InternationalStandardModel.ST5B, 7, 6),
        (InternationalStandardModel.ST5C, 7, 6),
        (InternationalStandardModel.IVOST, 1, 1),
        (InternationalStandardModel.IVOGO, 2, 2),
        (InternationalStandardModel.DEGOV, 3, 3),
        (InternationalStandardModel.DEGOV1, 3, 3),
        (InternationalStandardModel.DEGOV1D, 3, 3),
        (InternationalStandardModel.BESSCBCURRENTSOURCENOPLANTCONTROL, 6, 2),
        (InternationalStandardModel.WPP4BCURRENTSOURCE2020, 6, 2),
        (InternationalStandardModel.MAXEX2, 1, 1),
        (InternationalStandardModel.OEL2C, 1, 1),
        (InternationalStandardModel.SCL1C, 5, 4),
        (InternationalStandardModel.SCL2C, 6, 2),
        (InternationalStandardModel.UEL2C, 6, 1),
        (InternationalStandardModel.AC6A, 5, 1),
        (InternationalStandardModel.AC6C, 8, 1),
        (InternationalStandardModel.PSS2B, 3, 1),
        (InternationalStandardModel.PSS2C, 3, 1),
    )
    descriptors: list[InternationalStandardTemplateDescriptor] = list(
        get_dynamic_library_international_standard_descriptors()
    )
    model: InternationalStandardModel
    expected_input_count: int
    expected_output_count: int

    for model, expected_input_count, expected_output_count in expected_interfaces:
        descriptor: InternationalStandardTemplateDescriptor | None = None
        candidate_descriptor: InternationalStandardTemplateDescriptor
        for candidate_descriptor in descriptors:
            if candidate_descriptor.model == model:
                descriptor = candidate_descriptor
            else:
                pass

        assert descriptor is not None
        var_factory: VarFactory = VarFactory()
        template: RmsModelTemplate = load_international_standard_template(
            descriptor=descriptor,
            var_factory=var_factory,
        )
        assert len(template.block.in_vars) == expected_input_count
        assert len(template.block.out_vars) == expected_output_count

        # The properties editor emits these names directly into Python source.
        variable_names: list[str] = list(
            variable.name for variable in var_factory.get_vars_dict().values()
        )
        variable_names.extend(list(
            variable.name for variable in var_factory.get_diff_var_dict().values()
        ))
        assert len(variable_names) > 0
        assert all(variable_name.isidentifier() for variable_name in variable_names)
        assert all(not keyword.iskeyword(variable_name) for variable_name in variable_names)


def test_every_international_standard_exposes_inputs_and_outputs() -> None:
    """Prevent generated standard models from losing their public connectors.

    :return: None.
    """
    descriptors: list[InternationalStandardTemplateDescriptor] = list(
        get_dynamic_library_international_standard_descriptors()
    )
    descriptor: InternationalStandardTemplateDescriptor

    for descriptor in descriptors:
        template: RmsModelTemplate = load_international_standard_template(
            descriptor=descriptor,
            var_factory=VarFactory(),
        )

        assert template.block is not None
        assert len(template.block.in_vars) > 0, descriptor.display_label
        assert len(template.block.out_vars) > 0, descriptor.display_label
