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
        "_description",
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
        description: str = "",
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
        :param description: Human-facing explanation of the block behavior.
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
        self._description = description

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
    def description(self) -> str:
        """
        Return the human-facing behavior description.

        :returns: Block behavior description, or an empty string when unspecified.
        """
        return self._description

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
        tokens.append(self._description)

        for category_name in self._category_path:
            tokens.append(category_name)

        return " ".join(tokens).strip()


def build_basic_block_catalog_functional_description(record: BasicBlockCatalogStaticRecord) -> str:
    """Build a functional description for one imported basic-block record.

    The shipped catalogue contains hundreds of variants whose labels encode
    their equations and optional behaviours. This function turns that stable
    metadata into useful Library text while explicit hand-written descriptions
    remain authoritative for exceptional blocks.

    :param record: Static catalogue record requiring a description.
    :returns: Functional, human-facing explanation of the block behaviour.
    """
    template_key: str = record.template_key
    display_label: str = record.display_label
    category_path: tuple[str, ...] = tuple(record.category_path)
    if len(category_path) > 0:
        family: str = category_path[-1]
    else:
        family = ""

    # Elementary functions are described by their mathematical operation.
    if family == "Elementary Functions":
        if template_key == "equal":
            description: str = "Compares two input signals and outputs one when they are equal, otherwise zero."
        elif template_key == "abs":
            description = "Returns the absolute value of the input signal."
        elif template_key == "ceil":
            description = "Rounds the input signal upward to the nearest integer."
        elif template_key == "floor":
            description = "Rounds the input signal downward to the nearest integer."
        elif template_key == "frac":
            description = "Returns the fractional part of the input signal."
        elif template_key == "round":
            description = "Rounds the input signal to the nearest integer."
        elif template_key == "modulo":
            description = "Returns the remainder after dividing the first input signal by the second."
        elif template_key == "reciprocal_fb":
            description = "Returns a sign-preserving protected reciprocal with a minimum denominator magnitude."
        elif template_key == "reciprocal":
            description = "Returns the exact reciprocal of the input signal; the result is undefined at zero."
        elif template_key == "sign":
            description = "Returns the sign of the input signal as -1, 0, or 1."
        elif template_key == "sqrt":
            description = "Returns the square root of the absolute input value."
        elif template_key == "x_2":
            description = "Squares the input signal: y = x²."
        elif template_key == "x_p":
            description = "Raises the input signal to the configurable exponent p."
        elif template_key == "exp":
            description = "Applies the natural exponential function to the input signal."
        elif template_key == "ln":
            description = "Applies the natural logarithm to the input signal."
        elif template_key == "log":
            description = "Applies the base-10 logarithm to the input signal."
        elif template_key == "atan2":
            description = "Returns the four-quadrant angle atan2(y, x) in radians."
        elif template_key == "atan2d":
            description = "Returns the four-quadrant angle atan2(y, x) in degrees."
        elif template_key in ("coshd", "sinhd", "tanhd"):
            description = f"Applies the {display_label} hyperbolic function to an input expressed in degrees."
        elif template_key.endswith("d"):
            description = f"Applies the {display_label} trigonometric function using degrees."
        elif template_key in ("acos", "asin", "atan"):
            description = f"Applies the inverse {display_label} trigonometric function in radians."
        elif template_key in ("cos", "sin", "tan"):
            description = f"Applies the {display_label} trigonometric function in radians."
        elif template_key in ("cosh", "sinh", "tanh"):
            description = f"Applies the {display_label} hyperbolic function to the input signal."
        else:
            description = f"Applies the {display_label} mathematical operation to the input signal."
    elif family == "Constants and Scaling":
        # Records without input ports are sources; the remaining records scale a signal.
        if len(record.inputs) == 0:
            description = f"Outputs the constant value {display_label}."
        else:
            description = f"Scales the input signal using the factor {display_label}."
    elif family == "Scaling and Products":
        if template_key == "a_x_c1_x_c2":
            description = "Evaluates the factored quadratic y = a(x - c1)(x - c2)."
        elif template_key == "ax_2_bx_c":
            description = "Evaluates the quadratic polynomial y = ax² + bx + c."
        elif template_key == "mx_n":
            description = "Applies the affine transformation y = m·x + n."
        elif template_key == "bias":
            description = "Provides an initial bias value determined from the initialized output."
        elif "Saturated" in display_label:
            description = f"Applies {display_label.lower()} to the input and clamps the result to configured bounds."
        else:
            description = f"Multiplies the input signal by {display_label}."
    elif family == "Integrators and Derivatives":
        # The leading numerator distinguishes integrators from differentiators.
        if template_key.startswith("1_s"):
            description = f"Integrates the input using the {display_label} formulation."
        else:
            description = f"Applies the continuous differentiating transfer function {display_label}."
    elif family == "Transfer Functions and Filters":
        if "butterworth" in template_key:
            description = f"Applies a {display_label} low-pass filter to the input signal."
        elif template_key.startswith("max"):
            description = f"Outputs the largest of the {len(record.inputs)} input signals."
        elif template_key.startswith("min"):
            description = f"Outputs the smallest of the {len(record.inputs)} input signals."
        elif template_key.startswith("multiply"):
            description = f"Scales the input signal by {display_label}."
        else:
            description = f"Applies the continuous transfer function {display_label} to the input signal."
    elif family == "Controllers":
        if template_key.startswith("picdro"):
            description = "Applies PI droop control with configurable pickup and dropoff timing."
        else:
            description = f"Implements the continuous controller or compensator {display_label}."
    elif family == "Delays and Memory":
        if "lastvalue" in template_key:
            description = f"Retains the previous sampled input value using the {display_label} variant."
        elif template_key == "movingavg":
            description = "Returns the moving average of the input over a configurable delayed time window."
        elif template_key == "delay":
            description = "Outputs the input signal after a configurable exact time delay."
        elif "pade" in template_key:
            description = f"Approximates a time delay with the {display_label} rational transfer function."
        else:
            description = f"Applies the transport-delay model {display_label} to the input signal."
    elif family == "Comparators":
        description = f"Compares signals using the condition “{display_label}” and outputs a Boolean result."
    elif family == "Gates and Memory":
        logic_keys: tuple[str, ...] = ("and2", "and3", "and4", "eor", "nor", "not", "or2", "or3", "or4")
        if template_key in logic_keys:
            description = f"Applies the {display_label} Boolean logic operation to its inputs."
        elif "flipflop" in template_key or template_key == "bistable":
            description = f"Stores a latched value using the {display_label} set/reset behaviour."
        elif template_key == "edge_detector":
            description = "Outputs a pulse when it detects the configured transition of the input signal."
        elif template_key == "monostable":
            description = "Generates a pulse of configurable duration when triggered."
        else:
            description = f"Selects between input signals according to the {display_label} condition."
    elif family == "Switching and Selection":
        if template_key.startswith("select"):
            description = f"Selects an output value according to the {display_label} condition."
        elif template_key.startswith("selfix"):
            description = "Sets and retains the input value when the enabling condition becomes true."
        else:
            description = f"Routes input signals according to the {display_label} switching rule."
    elif family == "Timers and Enables":
        if template_key.startswith("enable"):
            description = f"Enables or holds its signal channels according to the {display_label} control rule."
        else:
            description = f"Applies the enabled continuous response {display_label}."
    elif family == "Limiters":
        if template_key.startswith("rate_limiter") or template_key == "gradlim_const":
            description = f"Limits how quickly the input can change using the {display_label} bounds."
        elif template_key == "limit_lower_p":
            description = "Clamps the input signal to a configurable lower bound."
        elif template_key == "limit_upper":
            description = "Clamps the input signal to a configurable upper bound."
        else:
            description = f"Clamps the input signal using the {display_label} upper and lower bounds."
    elif family == "Deadbands and Rate Limiters":
        if template_key == "backlash":
            description = "Models mechanical backlash with a configurable hysteresis gap."
        else:
            description = f"Applies the {display_label} deadband characteristic around zero."
    elif family == "Signal Generators":
        if template_key.endswith("_ip") and "wave_generator" not in template_key:
            description = f"Generates a timed pulse while the condition “{display_label}” is active."
        elif "sine_wave" in template_key:
            description = f"Generates a configurable sinusoidal waveform using the {display_label} timing variant."
        elif "square_wave" in template_key:
            description = f"Generates a configurable square waveform using the {display_label} timing variant."
        elif "triangle_wave" in template_key:
            description = f"Generates a configurable triangular waveform using the {display_label} timing variant."
        elif "sawtooth_wave" in template_key:
            description = f"Generates a configurable sawtooth waveform using the {display_label} timing variant."
        elif template_key == "pulse":
            description = "Generates a pulse with configurable start time and duration."
        else:
            description = f"Generates the {display_label} source waveform."
    elif family == "Time Sources and Timers":
        if template_key.startswith("time_"):
            description = "Outputs the current global simulation time."
        elif template_key.startswith("clock"):
            description = f"Generates a periodic clock signal using the {display_label} configuration."
        else:
            description = f"Measures elapsed simulation time using the {display_label} reset and hold behaviour."
    elif family == "Arrays and Matrices":
        if "inverse" in template_key or template_key == "invlapprox":
            description = f"Finds the input corresponding to a tabulated output using {display_label}."
        elif "matrix" in template_key or template_key in ("lapprox2", "sapprox2"):
            description = f"Interpolates a two-dimensional table using {display_label}."
        else:
            description = f"Interpolates a one-dimensional table using {display_label}."
    elif family == "Clarke, Park and dq0":
        description = f"Applies the {display_label} coordinate transformation."
    elif family == "RMS and Sequence":
        if "rms" in template_key:
            description = f"Computes the {display_label} magnitude from the input signals."
        else:
            description = f"Converts phase quantities using the {display_label} sequence transformation."
    elif family == "Operations":
        if template_key.startswith("limit"):
            description = f"Limits a complex signal using the {display_label} magnitude constraint."
        else:
            description = f"Performs {display_label.lower()} on complex-valued signals."
    elif family == "Measurements and Units":
        conversion_keys: tuple[str, ...] = ("deg_rad", "rad_deg", "rad_s_rpm", "rpm_rad_s")
        if "_p_u" in template_key or template_key.startswith("p_u_") or template_key in conversion_keys:
            description = f"Converts a signal from {display_label.replace('->', 'to')}."
        elif template_key == "power_base":
            description = "Computes the power base used for per-unit conversion."
        elif template_key.startswith("accelerating_power"):
            description = f"Computes machine accelerating power using the {display_label} formulation."
        else:
            description = f"Computes the {display_label} electrical measurement."
    elif family == "Drive Train":
        if template_key == "gear_box":
            description = "Transforms shaft speed and torque through a configurable gearbox ratio."
        elif template_key == "mass_j":
            description = "Models rotational inertia and integrates accelerating torque into shaft speed."
        elif template_key == "spring":
            description = "Models torsional spring torque from the relative shaft angle."
        elif template_key.startswith("shaft"):
            description = f"Models the {display_label} torsional shaft section and its inertial coupling."
        else:
            description = f"Applies the {display_label} mechanical drive-train relation."
    else:
        description = f"Implements the {display_label} basic dynamic-model operation."

    # Shared modifiers make closely related continuous variants explicit.
    modifier_parts: list[str] = list()
    lower_label: str = display_label.lower()
    if "bypass" in lower_label:
        modifier_parts.append("supports a bypass path")
    else:
        pass
    if "reset signal" in lower_label or "reset sig" in lower_label:
        modifier_parts.append("accepts an external reset value")
    elif "reset" in lower_label:
        modifier_parts.append("can be reset")
    else:
        pass
    if "hold" in lower_label:
        modifier_parts.append("can hold its current state")
    else:
        pass
    if "freeze" in lower_label:
        modifier_parts.append("can freeze integration")
    else:
        pass
    if len(modifier_parts) > 0:
        description = f"{description.rstrip('.')} It also {', '.join(modifier_parts)}."
    else:
        pass

    return description


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
    # Explicit descriptions document exceptional equations. All remaining
    # records receive a family-aware description from their stable metadata.
    if len(record.description) > 0:
        description: str = record.description
    else:
        description = build_basic_block_catalog_functional_description(record=record)

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
        description=description,
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


def _build_catalogue_local_symbol_name(
        variable: Var,
        descriptor: BasicBlockTemplateDescriptor,
        template_name: str,
        role_name: str,
        role_index: int,
) -> str:
    """Build one concise local name from generated catalogue metadata.

    Generated modules prefix internal variables with the complete block name
    and append the complete runtime instance name. Removing both repetitions
    retains the meaningful local token while keeping the result compact.

    :param variable: Materialized symbolic variable being named.
    :param descriptor: Stable descriptor of the source catalogue block.
    :param template_name: Runtime block name appended by the generated builder.
    :param role_name: Fallback symbolic role such as ``state`` or ``mode``.
    :param role_index: Zero-based position inside that symbolic role.
    :return: Python-safe local name without the per-template namespace.
    """
    runtime_free_name: str = variable.name
    runtime_suffix: str = f"_{template_name}"
    if runtime_free_name.endswith(runtime_suffix):
        runtime_free_name = runtime_free_name[:-len(runtime_suffix)]
    else:
        pass

    # Differential symbols add ``d_`` before the same generated block prefix.
    # Preserve that mathematical role while normalizing the shared payload.
    is_derivative: bool = runtime_free_name.startswith("d_")
    if is_derivative:
        generated_name: str = runtime_free_name[2:]
    else:
        generated_name = runtime_free_name

    # The standalone generators use either one or two separators between the
    # imported block name and the actual local symbol. Remove only that exact
    # descriptor-owned prefix; mathematical underscores inside local names are
    # therefore preserved.
    double_separator_prefix: str = f"{descriptor.blkdef_name}__"
    single_separator_prefix: str = f"{descriptor.blkdef_name}_"
    if generated_name.startswith(double_separator_prefix):
        local_name: str = generated_name[len(double_separator_prefix):]
    elif generated_name.startswith(single_separator_prefix):
        local_name = generated_name[len(single_separator_prefix):]
    else:
        local_name = generated_name

    if is_derivative:
        local_name = f"d_{local_name}"
    else:
        pass

    safe_local_name: str = _build_python_symbol_name(raw_name=local_name)
    if len(safe_local_name) > 32:
        safe_local_name = f"{role_name}_{role_index + 1}"
    else:
        pass
    return safe_local_name


def _register_catalogue_role_symbol_names(
        variables: Sequence[Var],
        descriptor: BasicBlockTemplateDescriptor,
        template_name: str,
        namespace: str,
        role_name: str,
        preferred_names_by_identity: dict[int, str],
) -> None:
    """Register concise preferred names for one ordered variable role.

    The first role that owns a variable is authoritative. This matters for
    output variables that are also present in the algebraic collection and for
    differential variables that retain a reference to their base state.

    :param variables: Ordered variables belonging to the same symbolic role.
    :param descriptor: Stable descriptor of the source catalogue block.
    :param template_name: Runtime name used during materialization.
    :param namespace: Short stable namespace derived from the catalogue type.
    :param role_name: Fallback role used when an imported local name is long.
    :param preferred_names_by_identity: Destination lookup by stable identity.
    :return: None.
    """
    role_index: int
    variable: Var
    for role_index, variable in enumerate(variables):
        variable_identity: int = variable.non_mutable_uid
        if variable_identity not in preferred_names_by_identity:
            local_name: str = _build_catalogue_local_symbol_name(
                variable=variable,
                descriptor=descriptor,
                template_name=template_name,
                role_name=role_name,
                role_index=role_index,
            )
            preferred_names_by_identity[variable_identity] = f"{local_name}_{namespace}"
        else:
            pass


def _build_catalogue_preferred_symbol_names(
        descriptor: BasicBlockTemplateDescriptor,
        root_block: Block,
        template_name: str,
) -> dict[int, str]:
    """Build concise role-aware names for one materialized catalogue tree.

    :param descriptor: Stable descriptor of the source catalogue block.
    :param root_block: Root of the freshly materialized block tree.
    :param template_name: Runtime name used by the generated builder.
    :return: Preferred Python-safe names keyed by non-mutable variable identity.
    """
    preferred_names_by_identity: dict[int, str] = dict()
    namespace: str = f"bb{descriptor.typ_id}"
    owner: Block

    # Public ports and states receive priority because these are the names that
    # users see most often in equations and on the block interface.
    for owner in root_block.get_all_blocks():
        _register_catalogue_role_symbol_names(
            variables=owner.in_vars,
            descriptor=descriptor,
            template_name=template_name,
            namespace=namespace,
            role_name="input",
            preferred_names_by_identity=preferred_names_by_identity,
        )
        _register_catalogue_role_symbol_names(
            variables=owner.out_vars,
            descriptor=descriptor,
            template_name=template_name,
            namespace=namespace,
            role_name="output",
            preferred_names_by_identity=preferred_names_by_identity,
        )
        _register_catalogue_role_symbol_names(
            variables=owner.state_vars,
            descriptor=descriptor,
            template_name=template_name,
            namespace=namespace,
            role_name="state",
            preferred_names_by_identity=preferred_names_by_identity,
        )
        _register_catalogue_role_symbol_names(
            variables=owner.diff_vars,
            descriptor=descriptor,
            template_name=template_name,
            namespace=namespace,
            role_name="derivative",
            preferred_names_by_identity=preferred_names_by_identity,
        )
        _register_catalogue_role_symbol_names(
            variables=tuple(owner.event_dict.keys()),
            descriptor=descriptor,
            template_name=template_name,
            namespace=namespace,
            role_name="parameter",
            preferred_names_by_identity=preferred_names_by_identity,
        )
        _register_catalogue_role_symbol_names(
            variables=tuple(owner.mode_dict.keys()),
            descriptor=descriptor,
            template_name=template_name,
            namespace=namespace,
            role_name="mode",
            preferred_names_by_identity=preferred_names_by_identity,
        )
        _register_catalogue_role_symbol_names(
            variables=owner.algebraic_vars,
            descriptor=descriptor,
            template_name=template_name,
            namespace=namespace,
            role_name="auxiliary",
            preferred_names_by_identity=preferred_names_by_identity,
        )
    return preferred_names_by_identity


def _rename_new_catalogue_variables(
    variables_by_identity: dict[int, Var],
    previous_identities: set[int],
    reserved_names: set[str],
    renamed_identities: set[int],
    procedural_name_mapping: dict[Expr | str, Expr],
    preferred_names_by_identity: dict[int, str],
    descriptor: BasicBlockTemplateDescriptor,
    template_name: str,
    namespace: str,
) -> None:
    """Give newly materialized catalogue variables unique Python-safe names.

    :param variables_by_identity: Factory variables keyed by stable identity.
    :param previous_identities: Identities that existed before materialization.
    :param reserved_names: Names already owned by the surrounding model.
    :param renamed_identities: New identities already handled through another
        factory collection.
    :param procedural_name_mapping: Old names mapped to their renamed symbolic variables.
    :param preferred_names_by_identity: Role-aware names for variables exposed by the block.
    :param descriptor: Stable descriptor of the source catalogue block.
    :param template_name: Runtime name used during materialization.
    :param namespace: Stable short namespace used for unclassified helper variables.
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
            preferred_name: str | None = preferred_names_by_identity.get(variable.non_mutable_uid, None)
            if preferred_name is not None:
                base_name: str = _build_python_symbol_name(raw_name=preferred_name)
            else:
                # A generated helper that is referenced only from an expression
                # retains its local token even though it is not part of one of
                # the explicit block collections.
                local_name: str = _build_catalogue_local_symbol_name(
                    variable=variable,
                    descriptor=descriptor,
                    template_name=template_name,
                    role_name="symbol",
                    role_index=len(renamed_identities),
                )
                base_name = f"{local_name}_{namespace}"
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
    descriptor: BasicBlockTemplateDescriptor,
    var_factory: VarFactory,
    root_block: Block,
    template_name: str,
    previous_var_identities: set[int],
    previous_diff_var_identities: set[int],
) -> None:
    """Normalize only the variables created by one catalogue materialization.

    The factory can already contain symbols belonging to the surrounding model.
    Those names remain untouched; they only reserve their namespace so newly
    created catalogue variables cannot collide with them.

    :param descriptor: Stable descriptor of the source catalogue block.
    :param var_factory: Factory containing old and newly created variables.
    :param root_block: Complete materialized catalogue block tree.
    :param template_name: Runtime name used by the generated builder.
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
    preferred_names_by_identity: dict[int, str] = _build_catalogue_preferred_symbol_names(
        descriptor=descriptor,
        root_block=root_block,
        template_name=template_name,
    )
    namespace: str = f"bb{descriptor.typ_id}"
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
        preferred_names_by_identity=preferred_names_by_identity,
        descriptor=descriptor,
        template_name=template_name,
        namespace=namespace,
    )
    _rename_new_catalogue_variables(
        variables_by_identity=differential_variables,
        previous_identities=previous_diff_var_identities,
        reserved_names=reserved_names,
        renamed_identities=renamed_identities,
        procedural_name_mapping=procedural_name_mapping,
        preferred_names_by_identity=preferred_names_by_identity,
        descriptor=descriptor,
        template_name=template_name,
        namespace=namespace,
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
        descriptor=descriptor,
        var_factory=var_factory,
        root_block=template.block,
        template_name=template.name,
        previous_var_identities=previous_var_identities,
        previous_diff_var_identities=previous_diff_var_identities,
    )
    return template
