# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

import keyword
import re
from functools import lru_cache
from pathlib import Path
from typing import Sequence

from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Templates.BasicBlockCatalog.Functions import BasicBlockCatalogTemplateBuilder
from VeraGridEngine.Templates.BasicBlockCatalog.Functions import get_basic_block_catalog_template_builder_by_module_name
from VeraGridEngine.Templates.BasicBlockCatalog.catalog_static_registry import BasicBlockCatalogStaticRecord
from VeraGridEngine.Templates.BasicBlockCatalog.catalog_static_registry import build_basic_block_catalog_pending_template_reason
from VeraGridEngine.Templates.BasicBlockCatalog.catalog_static_registry import get_basic_block_catalog_static_records
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.symbolic import Expr, Var


class BasicBlockTemplateDescriptor:
    """
    Explicit, typed description of one shipped catalog template.
    """

    __slots__ = (
        "_template_key",
        "_typ_id",
        "_blkdef_name",
        "_sample_display_name",
        "_display_label",
        "_category_path",
        "_inputs",
        "_outputs",
        "_states",
        "_params",
        "_unsupported_lines",
        "_module_name",
        "_module_filename",
    )

    def __init__(
        self,
        template_key: str,
        typ_id: str,
        blkdef_name: str,
        sample_display_name: str,
        display_label: str,
        category_path: Sequence[str],
        inputs: Sequence[str],
        outputs: Sequence[str],
        states: Sequence[str],
        params: Sequence[str],
        unsupported_lines: Sequence[str],
        module_name: str,
        module_filename: str,
    ) -> None:
        """
        Store one immutable catalog descriptor.

        :param template_key: Stable semantic lookup key.
        :param typ_id: Imported numeric type identifier.
        :param blkdef_name: Raw source block name.
        :param sample_display_name: Clean human-facing source name.
        :param display_label: Unique label exposed in the editor.
        :param category_path: Full editor category path.
        :param inputs: Input names.
        :param outputs: Output names.
        :param states: State names.
        :param params: Runtime parameter names.
        :param unsupported_lines: Pending markers for non editor-ready templates.
        :param module_name: Standalone module stem inside the shipped catalog.
        :param module_filename: Standalone module filename inside the shipped catalog.
        :returns: None.
        """
        self._template_key = template_key
        self._typ_id = typ_id
        self._blkdef_name = blkdef_name
        self._sample_display_name = sample_display_name
        self._display_label = display_label
        self._category_path = tuple(category_path)
        self._inputs = tuple(inputs)
        self._outputs = tuple(outputs)
        self._states = tuple(states)
        self._params = tuple(params)
        self._unsupported_lines = tuple(unsupported_lines)
        self._module_name = module_name
        self._module_filename = module_filename

    @property
    def template_key(self) -> str:
        """
        Return the stable semantic lookup key.

        :returns: Template lookup key.
        """
        return self._template_key

    @property
    def typ_id(self) -> str:
        """
        Return the imported numeric type identifier.

        :returns: Imported type identifier.
        """
        return self._typ_id

    @property
    def blkdef_name(self) -> str:
        """
        Return the raw imported block name.

        :returns: Raw block name.
        """
        return self._blkdef_name

    @property
    def sample_display_name(self) -> str:
        """
        Return the clean display name derived from the shipped module.

        :returns: Clean source name.
        """
        return self._sample_display_name

    @property
    def display_label(self) -> str:
        """
        Return the unique label exposed by the editor.

        :returns: Unique label.
        """
        return self._display_label

    @property
    def category_path(self) -> Sequence[str]:
        """
        Return the full library category path.

        :returns: Category path.
        """
        return self._category_path

    @property
    def inputs(self) -> Sequence[str]:
        """
        Return the input names.

        :returns: Input-name tuple.
        """
        return self._inputs

    @property
    def outputs(self) -> Sequence[str]:
        """
        Return the output names.

        :returns: Output-name tuple.
        """
        return self._outputs

    @property
    def states(self) -> Sequence[str]:
        """
        Return the state names.

        :returns: State-name tuple.
        """
        return self._states

    @property
    def params(self) -> Sequence[str]:
        """
        Return the runtime parameter names.

        :returns: Parameter-name tuple.
        """
        return self._params

    @property
    def unsupported_lines(self) -> Sequence[str]:
        """
        Return the pending markers for non editor-ready templates.

        :returns: Unsupported marker tuple.
        """
        return self._unsupported_lines

    @property
    def module_name(self) -> str:
        """
        Return the standalone Python module stem.

        :returns: Module stem.
        """
        return self._module_name

    @property
    def module_filename(self) -> str:
        """
        Return the standalone Python filename.

        :returns: Module filename.
        """
        return self._module_filename

    @property
    def is_editor_ready(self) -> bool:
        """
        Return whether the template can be exposed in the editor.

        :returns: ``True`` when the template has executable content.
        """
        if len(self._unsupported_lines) == 0:
            return True
        else:
            return False

    @property
    def search_text(self) -> str:
        """
        Build the normalized search text used by the editor filter.

        :returns: Search text.
        """
        tokens: list[str] = list()
        category_name: str

        # The search index mixes the stable human-facing fields so one filter can
        # match label, source name, semantic key, imported type id, or category.
        tokens.append(self._display_label)
        tokens.append(self._blkdef_name)
        tokens.append(self._sample_display_name)
        tokens.append(self._template_key)
        tokens.append(self._typ_id)

        for category_name in self._category_path:
            tokens.append(category_name)

        return " ".join(tokens).strip()


def get_basic_block_catalog_root() -> Path:
    """
    Return the directory containing the shipped basic block catalog.

    :returns: Catalog root directory.
    """
    return Path(__file__).resolve().parent


def get_basic_block_catalog_templates_dir() -> Path:
    """
    Return the directory with the shipped standalone template modules.

    :returns: Standalone-template directory.
    """
    return get_basic_block_catalog_root() / "Functions"


def get_basic_block_catalog_pending_template_reason() -> str:
    """
    Return the canonical pending reason for non-executable catalog templates.

    :returns: Pending reason.
    """
    return build_basic_block_catalog_pending_template_reason()


def _descriptor_sort_key(descriptor: BasicBlockTemplateDescriptor) -> tuple[int, str]:
    """
    Build the deterministic sort key for one descriptor.

    :param descriptor: Catalog descriptor.
    :returns: Sort key ordered by type identifier and module name.
    """
    return int(descriptor.typ_id), descriptor.module_name


def _build_descriptor_from_static_record(record: BasicBlockCatalogStaticRecord) -> BasicBlockTemplateDescriptor:
    """
    Convert one static record into the public descriptor object.

    :param record: Static snapshot record.
    :returns: Public catalog descriptor.
    """
    return BasicBlockTemplateDescriptor(
        template_key=record.template_key,
        typ_id=record.typ_id,
        blkdef_name=record.blkdef_name,
        sample_display_name=record.sample_display_name,
        display_label=record.display_label,
        category_path=record.category_path,
        inputs=record.inputs,
        outputs=record.outputs,
        states=record.states,
        params=record.params,
        unsupported_lines=record.unsupported_lines,
        module_name=record.module_name,
        module_filename=record.module_filename,
    )


def _resolve_template_builder_from_descriptor(descriptor: BasicBlockTemplateDescriptor) -> BasicBlockCatalogTemplateBuilder:
    """
    Resolve one shipped standalone template builder from the static package registry.

    :param descriptor: Catalog descriptor for the target module.
    :returns: Imported standalone template builder.
    :raises KeyError: Raised when the generated package registry does not expose the descriptor module.
    """
    template_builder: BasicBlockCatalogTemplateBuilder | None = (
        get_basic_block_catalog_template_builder_by_module_name(descriptor.module_name)
    )

    # The descriptor snapshot owns the canonical module name, so the runtime can
    # resolve one explicit builder without probing the filesystem or imported module state.
    if template_builder is None:
        raise KeyError(f"Could not resolve standalone template builder for module '{descriptor.module_name}'")
    else:
        return template_builder


@lru_cache(maxsize=1)
def get_basic_block_catalog_descriptors() -> Sequence[BasicBlockTemplateDescriptor]:
    """
    Return the shipped basic block catalog descriptors.

    :returns: Full descriptor tuple.
    """
    descriptors: list[BasicBlockTemplateDescriptor] = list()
    static_record: BasicBlockCatalogStaticRecord

    # The runtime now consumes one generated static snapshot instead of discovering
    # modules dynamically, so the catalog shape is stable across refactors.
    for static_record in get_basic_block_catalog_static_records():
        descriptors.append(_build_descriptor_from_static_record(static_record))

    descriptors.sort(key=_descriptor_sort_key)
    return tuple(descriptors)


@lru_cache(maxsize=1)
def get_editor_ready_basic_block_catalog_descriptors() -> Sequence[BasicBlockTemplateDescriptor]:
    """
    Return only the shipped templates that are ready for editor exposure.

    :returns: Editor-ready descriptor tuple.
    """
    ready_descriptors: list[BasicBlockTemplateDescriptor] = list()
    descriptor: BasicBlockTemplateDescriptor

    for descriptor in get_basic_block_catalog_descriptors():
        if descriptor.is_editor_ready:
            ready_descriptors.append(descriptor)
        else:
            pass

    return tuple(ready_descriptors)


@lru_cache(maxsize=1)
def get_pending_basic_block_catalog_descriptors() -> Sequence[BasicBlockTemplateDescriptor]:
    """
    Return only the shipped templates that are not ready for editor exposure.

    :returns: Pending descriptor tuple.
    """
    pending_descriptors: list[BasicBlockTemplateDescriptor] = list()
    descriptor: BasicBlockTemplateDescriptor

    for descriptor in get_basic_block_catalog_descriptors():
        if descriptor.is_editor_ready:
            pass
        else:
            pending_descriptors.append(descriptor)

    return tuple(pending_descriptors)


@lru_cache(maxsize=1)
def get_basic_block_catalog_descriptor_by_key() -> dict[str, BasicBlockTemplateDescriptor]:
    """
    Return the descriptor lookup indexed by semantic key.

    :returns: Descriptor lookup by semantic key.
    """
    descriptor_lookup: dict[str, BasicBlockTemplateDescriptor] = dict()
    descriptor: BasicBlockTemplateDescriptor

    for descriptor in get_basic_block_catalog_descriptors():
        descriptor_lookup[descriptor.template_key] = descriptor

    return descriptor_lookup


def _build_python_symbol_name(raw_name: str) -> str:
    """Convert one catalogue variable name into a valid Python identifier.

    Catalogue display names may contain spaces and mathematical punctuation,
    while the equation editor exposes every symbolic variable as Python source.
    This conversion deliberately affects only variable names and therefore does
    not alter the human-facing template or block labels.

    :param raw_name: Symbolic name emitted by a catalogue template builder.
    :return: Identifier-safe symbolic name.
    """
    # Replace display punctuation with separators while retaining the readable
    # portions of the source name used to identify generated internal symbols.
    safe_name: str = re.sub(r"[^0-9a-zA-Z_]", "_", raw_name)
    safe_name = re.sub(r"_+", "_", safe_name).strip("_")

    if safe_name == "":
        safe_name = "symbol"
    else:
        pass

    # Python identifiers cannot begin with a number or equal a language keyword.
    if safe_name[0].isdigit():
        safe_name = f"symbol_{safe_name}"
    else:
        pass

    if keyword.iskeyword(safe_name):
        safe_name = f"{safe_name}_symbol"
    else:
        pass

    return safe_name


def _rename_new_catalogue_variables(
    variables_by_identity: dict[int, Var],
    previous_identities: set[int],
    reserved_names: set[str],
    renamed_identities: set[int],
    procedural_name_mapping: dict[Expr | str, Expr],
) -> None:
    """Give newly materialized catalogue variables unique Python-safe names.

    :param variables_by_identity: Factory variables keyed by stable identity.
    :param previous_identities: Identities that existed before materialization.
    :param reserved_names: Names already owned by the surrounding model.
    :param renamed_identities: New identities already handled through another
        factory collection.
    :param procedural_name_mapping: Old names mapped to their renamed symbolic variables.
    :return: None.
    """
    variable_identity: int
    variable: Var

    for variable_identity, variable in variables_by_identity.items():
        if (
            variable_identity not in previous_identities
            and variable_identity not in renamed_identities
        ):
            original_name: str = variable.name
            base_name: str = _build_python_symbol_name(variable.name)
            candidate_name: str = base_name
            suffix: int = 2

            # Normalization can merge punctuation variants. Allocate a stable
            # suffix so the editor namespace never loses one of those symbols.
            while candidate_name in reserved_names:
                candidate_name = f"{base_name}_{suffix}"
                suffix += 1

            variable.set_name(candidate_name)
            reserved_names.add(candidate_name)
            renamed_identities.add(variable_identity)
            if original_name != candidate_name:
                procedural_name_mapping[original_name] = variable
            else:
                pass
        else:
            pass


def _remap_catalogue_procedural_logic(
    root_block: Block,
    procedural_name_mapping: dict[Expr | str, Expr],
) -> None:
    """Synchronize name-backed procedural references after symbol normalization.

    Procedural entries retain some targets as strings for persisted legacy
    compatibility. Their typed ``remap`` operation updates those strings while
    preserving symbolic expression identities and the concrete logic type.

    :param root_block: Complete materialized catalogue block tree.
    :param procedural_name_mapping: Old symbol names mapped to renamed variables.
    :return: None.
    """
    if len(procedural_name_mapping) > 0:
        owner: Block
        for owner in root_block.get_all_blocks():
            if len(owner.procedural_logic) > 0:
                owner.procedural_logic = list(
                    entry.remap(procedural_name_mapping)
                    for entry in owner.procedural_logic
                )
            else:
                pass
    else:
        pass


def _normalize_materialized_catalogue_symbol_names(
    var_factory: VarFactory,
    root_block: Block,
    previous_var_identities: set[int],
    previous_diff_var_identities: set[int],
) -> None:
    """Normalize only the variables created by one catalogue materialization.

    The factory can already contain symbols belonging to the surrounding model.
    Those names remain untouched; they only reserve their namespace so newly
    created catalogue variables cannot collide with them.

    :param var_factory: Factory containing old and newly created variables.
    :param root_block: Complete materialized catalogue block tree.
    :param previous_var_identities: Regular-variable identities present before
        loading.
    :param previous_diff_var_identities: Differential-variable identities present
        before loading.
    :return: None.
    """
    regular_variables: dict[int, Var] = var_factory.get_vars_dict()
    differential_variables: dict[int, Var] = var_factory.get_diff_var_dict()
    reserved_names: set[str] = set()
    renamed_identities: set[int] = set()
    procedural_name_mapping: dict[Expr | str, Expr] = dict()
    variable: Var

    # Existing symbols define the namespace that the new template must respect.
    for variable in regular_variables.values():
        if variable.non_mutable_uid in previous_var_identities:
            reserved_names.add(variable.name)
        else:
            pass

    for variable in differential_variables.values():
        if variable.non_mutable_uid in previous_diff_var_identities:
            reserved_names.add(variable.name)
        else:
            pass

    _rename_new_catalogue_variables(
        variables_by_identity=regular_variables,
        previous_identities=previous_var_identities,
        reserved_names=reserved_names,
        renamed_identities=renamed_identities,
        procedural_name_mapping=procedural_name_mapping,
    )
    _rename_new_catalogue_variables(
        variables_by_identity=differential_variables,
        previous_identities=previous_diff_var_identities,
        reserved_names=reserved_names,
        renamed_identities=renamed_identities,
        procedural_name_mapping=procedural_name_mapping,
    )
    _remap_catalogue_procedural_logic(
        root_block=root_block,
        procedural_name_mapping=procedural_name_mapping,
    )


def load_basic_block_catalog_template(
    descriptor: BasicBlockTemplateDescriptor,
    var_factory: VarFactory,
    name: str | None = None,
) -> EmtModelTemplate:
    """
    Materialize one shipped catalog-derived template on demand.

    :param descriptor: Template descriptor.
    :param var_factory: Variable factory for the new instance.
    :param name: Optional explicit instance name.
    :returns: Materialized EMT template.
    """
    # Snapshot the surrounding model so normalization is strictly limited to
    # the variables allocated by this catalogue builder call.
    previous_var_identities: set[int] = set(var_factory.get_vars_dict().keys())
    previous_diff_var_identities: set[int] = set(var_factory.get_diff_var_dict().keys())
    template_builder: BasicBlockCatalogTemplateBuilder = _resolve_template_builder_from_descriptor(descriptor)
    template: EmtModelTemplate = template_builder(var_factory, name)
    _normalize_materialized_catalogue_symbol_names(
        var_factory=var_factory,
        root_block=template.block,
        previous_var_identities=previous_var_identities,
        previous_diff_var_identities=previous_diff_var_identities,
    )
    return template
