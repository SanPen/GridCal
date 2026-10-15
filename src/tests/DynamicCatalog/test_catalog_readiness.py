from __future__ import annotations

import re
from typing import Sequence

import pytest

from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Templates.BasicBlockCatalog import BasicBlockTemplateDescriptor
from VeraGridEngine.Templates.BasicBlockCatalog import ExactMathematicalBlockDescriptor
from VeraGridEngine.Templates.BasicBlockCatalog import build_exact_mathematical_block_descriptors
from VeraGridEngine.Templates.BasicBlockCatalog import build_exact_mathematical_block_template
from VeraGridEngine.Templates.BasicBlockCatalog import get_editor_ready_basic_block_catalog_descriptors
from VeraGridEngine.Templates.BasicBlockCatalog import get_pending_basic_block_catalog_descriptors
from VeraGridEngine.Templates.BasicBlockCatalog import get_basic_block_catalog_pending_template_reason
from VeraGridEngine.Templates.BasicBlockCatalog import load_basic_block_catalog_template
from VeraGridEngine.Utils.Symbolic.symbolic import Var
from VeraGridEngine.enumerations import ExactMathematicalBlockOperation
from VeraGridEngine.enumerations import ExactMathematicalValue

from DynamicCatalog._catalog_support import build_templates_dir
from DynamicCatalog._catalog_support import build_template
from DynamicCatalog._catalog_support import descriptor_entries
from DynamicCatalog._catalog_support import descriptor_lookup_by_key
from DynamicCatalog._catalog_support import find_template_path


def build_descriptor_parameters() -> Sequence[BasicBlockTemplateDescriptor]:
    """
    Return every shipped catalog descriptor as pytest parameters.

    :returns: Full descriptor sequence.
    """

    return descriptor_entries()


def build_ready_descriptor_parameters() -> Sequence[BasicBlockTemplateDescriptor]:
    """
    Return the editor-ready catalog descriptors as pytest parameters.

    :returns: Editor-ready descriptor sequence.
    """

    return get_editor_ready_basic_block_catalog_descriptors()


def build_pending_descriptor_parameters() -> Sequence[BasicBlockTemplateDescriptor]:
    """
    Return the pending catalog descriptors as pytest parameters.

    :returns: Pending descriptor sequence.
    """

    return get_pending_basic_block_catalog_descriptors()


def build_constant_descriptor_parameters() -> Sequence[BasicBlockTemplateDescriptor]:
    """
    Return the constant descriptors that previously risked controller misclassification.

    :returns: Constant descriptor sequence.
    """

    descriptor_by_key: dict[str, BasicBlockTemplateDescriptor] = descriptor_lookup_by_key()
    template_keys: Sequence[str] = ("2pi_form_a", "2pi_form_b", "pi", "pi_2")
    descriptors: list[BasicBlockTemplateDescriptor] = list()
    template_key: str

    for template_key in template_keys:
        descriptors.append(descriptor_by_key[template_key])

    return descriptors


def build_long_symbol_descriptor_parameters() -> Sequence[BasicBlockTemplateDescriptor]:
    """Return representative descriptors that previously generated very long symbols.

    The selected blocks cover a nested transfer function, procedural timer
    logic, and a coordinate transform with internal mathematical constants.

    :returns: Descriptors spanning the long-name catalogue cases.
    """
    descriptor_by_key: dict[str, BasicBlockTemplateDescriptor] = descriptor_lookup_by_key()
    template_keys: Sequence[str] = (
        "1_kstc_1_sta_1_stb_1_stc_bypass",
        "timer_reset_hold_reset_t0_reset_incfw",
        "abc_dq0_power_invariant_align_a_d",
    )
    descriptors: list[BasicBlockTemplateDescriptor] = list()
    template_key: str

    for template_key in template_keys:
        descriptors.append(descriptor_by_key[template_key])

    return descriptors


def collect_factory_variables(var_factory: VarFactory) -> Sequence[Var]:
    """Collect each regular and differential variable from one factory once.

    :param var_factory: Factory populated by catalogue materialization.
    :returns: Variables in deterministic factory insertion order.
    """
    variables: list[Var] = list()
    collected_identities: set[int] = set()
    variable: Var

    # A differential variable can also be registered as a regular variable
    # when it owns a shared reference. Stable identity avoids counting it twice.
    for variable in var_factory.get_vars_dict().values():
        variables.append(variable)
        collected_identities.add(variable.non_mutable_uid)

    for variable in var_factory.get_diff_var_dict().values():
        if variable.non_mutable_uid not in collected_identities:
            variables.append(variable)
            collected_identities.add(variable.non_mutable_uid)
        else:
            pass

    return tuple(variables)


def build_descriptor_test_id(descriptor: BasicBlockTemplateDescriptor) -> str:
    """
    Build the pytest id for one catalog descriptor.

    :param descriptor: Catalog descriptor.
    :returns: Stable pytest id.
    """

    return descriptor.template_key


def read_template_module_text(descriptor: BasicBlockTemplateDescriptor) -> str:
    """
    Read the generated standalone module text for one catalog descriptor.

    :param descriptor: Catalog descriptor.
    :returns: Generated module text.
    """

    template_path = find_template_path(descriptor.template_key)
    return template_path.read_text(encoding="utf-8")


def build_expected_generated_template_license_header() -> str:
    """
    Return the standard MPL header expected at the top of generated templates.

    :returns: Generated-template license header text.
    """
    return "\n".join(
        (
            "# This Source Code Form is subject to the terms of the Mozilla Public",
            "# License, v. 2.0. If a copy of the MPL was not distributed with this",
            "# file, You can obtain one at https://mozilla.org/MPL/2.0/.",
            "# SPDX-License-Identifier: MPL-2.0",
            "",
        )
    )


@pytest.mark.filterwarnings("error")
def test_catalog_artifacts_exist() -> None:
    """
    Validate that the shipped standalone template directory exists and is complete.

    :returns: None.
    """

    descriptors: Sequence[BasicBlockTemplateDescriptor] = build_descriptor_parameters()
    assert build_templates_dir().exists()
    assert len(descriptors) == 548


@pytest.mark.filterwarnings("error")
def test_editor_ready_subset_counts_are_clean() -> None:
    """
    Validate the expected ready-versus-pending descriptor counts.

    :returns: None.
    """

    ready_descriptors: Sequence[BasicBlockTemplateDescriptor] = build_ready_descriptor_parameters()
    pending_descriptors: Sequence[BasicBlockTemplateDescriptor] = build_pending_descriptor_parameters()

    assert len(ready_descriptors) == 542
    assert len(pending_descriptors) == 6
    assert all(descriptor.unsupported_lines == tuple() for descriptor in ready_descriptors)


@pytest.mark.filterwarnings("error")
def test_editor_ready_labels_are_unique() -> None:
    """
    Validate that every editor-ready descriptor exposes a unique visible label.

    :returns: None.
    """

    ready_descriptors: Sequence[BasicBlockTemplateDescriptor] = build_ready_descriptor_parameters()
    labels: list[str] = [descriptor.display_label for descriptor in ready_descriptors]
    assert len(labels) == len(set(labels))


@pytest.mark.filterwarnings("error")
def test_catalogue_labels_follow_the_editor_naming_convention() -> None:
    """Validate representative human-facing labels after name normalization.

    :returns: None.
    """
    descriptor_by_key: dict[str, BasicBlockTemplateDescriptor] = descriptor_lookup_by_key()
    expected_labels: tuple[tuple[str, str], ...] = (
        ("balanced", "Balanced sequence"),
        ("2pi_form_a", "2pi (form A)"),
        ("e", "e"),
        ("pi", "Constant pi"),
        ("sqrt2", "Constant sqrt(2)"),
        ("time_form_a", "Simulation time (form A)"),
        ("time_form_b", "Simulation time"),
        ("add_complex", "Complex addition"),
        ("gear_box", "Gearbox"),
    )
    expected_label: tuple[str, str]

    for expected_label in expected_labels:
        assert descriptor_by_key[expected_label[0]].display_label == expected_label[1]


@pytest.mark.filterwarnings("error")
def test_reciprocal_descriptions_distinguish_exact_and_protected_behaviour() -> None:
    """Ensure the two reciprocal variants document their different zero handling.

    :returns: None.
    """
    descriptor_by_key: dict[str, BasicBlockTemplateDescriptor] = descriptor_lookup_by_key()
    exact_description: str = descriptor_by_key["reciprocal"].description
    protected_description: str = descriptor_by_key["reciprocal_fb"].description

    assert "1 / u" in exact_description
    assert "undefined when u = 0" in exact_description
    assert "max(abs(u), 1e-6)" in protected_description
    assert exact_description != protected_description


@pytest.mark.filterwarnings("error")
@pytest.mark.parametrize(
    "descriptor",
    build_long_symbol_descriptor_parameters(),
    ids=build_descriptor_test_id,
)
def test_catalogue_materialization_uses_concise_unique_symbol_names(
        descriptor: BasicBlockTemplateDescriptor,
) -> None:
    """Validate concise symbols without changing stable catalogue identities.

    :param descriptor: Representative descriptor with historically long names.
    :returns: None.
    """
    var_factory: VarFactory = VarFactory()
    first_template: EmtModelTemplate = load_basic_block_catalog_template(
        descriptor=descriptor,
        var_factory=var_factory,
        name="catalogue_symbol_name_that_is_deliberately_long_a",
    )
    second_template: EmtModelTemplate = load_basic_block_catalog_template(
        descriptor=descriptor,
        var_factory=var_factory,
        name="catalogue_symbol_name_that_is_deliberately_long_b",
    )
    variables: Sequence[Var] = collect_factory_variables(var_factory=var_factory)
    names: list[str] = list()
    variable: Var

    # Every identifier must remain directly usable by the equation editor and
    # short enough to scan, including the collision suffix on a second instance.
    for variable in variables:
        names.append(variable.name)
        assert variable.name.isidentifier()
        assert len(variable.name) <= 48
        assert "catalogue_symbol_name_that_is_deliberately_long" not in variable.name

    assert len(names) == len(set(names))

    # Public interfaces keep the source-local port names, so existing equation
    # searches remain readable even though generated block prefixes disappear.
    input_index: int
    for input_index in range(len(descriptor.inputs)):
        assert first_template.block.in_vars[input_index].name.startswith(f"{descriptor.inputs[input_index]}_")
        assert second_template.block.in_vars[input_index].name.startswith(f"{descriptor.inputs[input_index]}_")

    output_index: int
    for output_index in range(len(descriptor.outputs)):
        assert first_template.block.out_vars[output_index].name.startswith(f"{descriptor.outputs[output_index]}_")
        assert second_template.block.out_vars[output_index].name.startswith(f"{descriptor.outputs[output_index]}_")


@pytest.mark.filterwarnings("error")
@pytest.mark.parametrize(
    "descriptor",
    build_pending_descriptor_parameters(),
    ids=build_descriptor_test_id,
)
def test_pending_descriptor_is_lookup_only(descriptor: BasicBlockTemplateDescriptor) -> None:
    """
    Validate one pending descriptor that must remain in the lookup-only subset.

    :param descriptor: Pending descriptor.
    :returns: None.
    """

    assert descriptor.category_path == ("Native", "Lookup and Tables", "Arrays and Matrices")
    assert descriptor.unsupported_lines == (get_basic_block_catalog_pending_template_reason(),)


@pytest.mark.filterwarnings("error")
@pytest.mark.parametrize(
    "descriptor",
    build_descriptor_parameters(),
    ids=build_descriptor_test_id,
)
def test_every_catalog_entry_has_one_exported_template(descriptor: BasicBlockTemplateDescriptor) -> None:
    """
    Validate one shipped descriptor and its exported standalone module artifact.

    :param descriptor: Catalog descriptor.
    :returns: None.
    """

    assert find_template_path(descriptor.template_key).exists()


@pytest.mark.filterwarnings("error")
@pytest.mark.parametrize(
    "descriptor",
    build_descriptor_parameters(),
    ids=build_descriptor_test_id,
)
def test_exported_template_module_text_is_clean(descriptor: BasicBlockTemplateDescriptor) -> None:
    """
    Validate one generated standalone module against the catalog hygiene rules.

    :param descriptor: Catalog descriptor.
    :returns: None.
    """

    module_text: str = read_template_module_text(descriptor)

    assert module_text.startswith(build_expected_generated_template_license_header())
    assert "\n\"\"\"\nStandalone EMT template for the basic catalog block" in module_text
    assert "AUTO-GENERATED EMT TEMPLATE FROM DGS" not in module_text
    assert "# Source:" not in module_text
    assert "C:\\Users\\" not in module_text
    assert re.search(r"def get_[^(]+_emt_template", module_text) is None
    assert "getattr(" not in module_text
    assert "lambda" not in module_text
    assert "continue" not in module_text
    assert "..." not in module_text
    assert f"def build_{descriptor.module_name}_default_template_name() -> str:" in module_text
    assert f"def build_{descriptor.module_name}_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:" in module_text
    assert "def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:" not in module_text


@pytest.mark.filterwarnings("error")
@pytest.mark.parametrize(
    "descriptor",
    build_ready_descriptor_parameters(),
    ids=build_descriptor_test_id,
)
def test_editor_ready_descriptor_is_fully_categorized(descriptor: BasicBlockTemplateDescriptor) -> None:
    """
    Validate one editor-ready descriptor and its library categorization.

    :param descriptor: Editor-ready descriptor.
    :returns: None.
    """

    assert len(descriptor.category_path) >= 2
    assert descriptor.category_path[0] == "Native"
    assert descriptor.category_path[-1] != "Other"


@pytest.mark.filterwarnings("error")
@pytest.mark.parametrize(
    "descriptor",
    build_ready_descriptor_parameters(),
    ids=build_descriptor_test_id,
)
def test_editor_ready_label_does_not_expose_internal_typ_ids(descriptor: BasicBlockTemplateDescriptor) -> None:
    """
    Validate one editor-ready descriptor label and ensure it hides imported ids.

    :param descriptor: Editor-ready descriptor.
    :returns: None.
    """

    assert re.search(r"\[\d+\]", descriptor.display_label) is None


@pytest.mark.filterwarnings("error")
@pytest.mark.parametrize(
    "descriptor",
    build_constant_descriptor_parameters(),
    ids=build_descriptor_test_id,
)
def test_constant_catalog_block_is_not_classified_as_controller(descriptor: BasicBlockTemplateDescriptor) -> None:
    """
    Validate one constant descriptor that historically risked controller classification.

    :param descriptor: Constant descriptor.
    :returns: None.
    """

    assert descriptor.category_path[1:] == ("Math and Functions", "Constants and Scaling")


@pytest.mark.filterwarnings("error")
@pytest.mark.parametrize(
    "descriptor",
    build_ready_descriptor_parameters(),
    ids=build_descriptor_test_id,
)
def test_editor_ready_template_materializes_as_executable_device(descriptor: BasicBlockTemplateDescriptor) -> None:
    """
    Validate one editor-ready template and its executable symbolic surface.

    :param descriptor: Editor-ready descriptor.
    :returns: None.
    """

    templ = build_template(descriptor.template_key)

    # The materialized template must preserve the declared public surface described
    # by the descriptor, otherwise the editor tree and runtime import would diverge.
    assert len(templ.block.in_vars) == len(descriptor.inputs)
    assert len(templ.block.out_vars) == len(descriptor.outputs)

    declared_state_surface: int = (
        len(templ.block.state_vars)
        + len(templ.block.diff_vars)
        + len(templ.block.init_eqs)
        + len(templ.block.diff_init_eqs)
    )
    if len(descriptor.states) > 0:
        assert declared_state_surface > 0
    else:
        pass

    executable_content: int = (
        len(templ.block.state_eqs)
        + len(templ.block.algebraic_eqs)
        + len(templ.block.init_eqs)
        + len(templ.block.diff_init_eqs)
        + len(templ.block.procedural_logic)
        + len(templ.block.children)
    )
    assert executable_content > 0


@pytest.mark.filterwarnings("error")
def test_exact_mathematical_values_have_matching_source_and_gain_templates() -> None:
    """Validate the paired canonical constant-source and fixed-gain families.

    :returns: None.
    """
    descriptors: tuple[ExactMathematicalBlockDescriptor, ...] = build_exact_mathematical_block_descriptors()
    assert len(descriptors) == len(ExactMathematicalValue) * len(ExactMathematicalBlockOperation)

    descriptor: ExactMathematicalBlockDescriptor
    for descriptor in descriptors:
        var_factory: VarFactory = VarFactory()
        template: EmtModelTemplate = build_exact_mathematical_block_template(
            descriptor=descriptor,
            var_factory=var_factory,
        )
        assert template.name == descriptor.display_label
        assert len(template.block.out_vars) == 1
        assert len(template.block.algebraic_eqs) == 1
        if descriptor.operation == ExactMathematicalBlockOperation.CONSTANT:
            assert len(template.block.in_vars) == 0
        else:
            assert len(template.block.in_vars) == 1
