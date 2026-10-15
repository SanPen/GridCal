# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.symbolic import Const, Expr, Var
from VeraGridEngine.enumerations import (
    DeviceType,
    ExactMathematicalBlockOperation,
    ExactMathematicalValue,
)


class ExactMathematicalBlockDescriptor:
    """Describe one canonical mathematical constant source or fixed gain."""

    __slots__ = ("_operation", "_mathematical_value")

    def __init__(
            self,
            operation: ExactMathematicalBlockOperation,
            mathematical_value: ExactMathematicalValue,
    ) -> None:
        """Store the operation and named mathematical value.

        :param operation: Whether the block outputs a constant or scales an input.
        :param mathematical_value: Exact named value used by the symbolic equation.
        :return: None.
        """
        self._operation: ExactMathematicalBlockOperation = operation
        self._mathematical_value: ExactMathematicalValue = mathematical_value

    @property
    def operation(self) -> ExactMathematicalBlockOperation:
        """Return whether this descriptor represents a source or a gain.

        :return: Exact mathematical block operation.
        """
        return self._operation

    @property
    def mathematical_value(self) -> ExactMathematicalValue:
        """Return the named value used by the block.

        :return: Exact mathematical value.
        """
        return self._mathematical_value

    @property
    def display_label(self) -> str:
        """Return the canonical Library label.

        Constant sources are prefixed explicitly so they cannot be confused
        with fixed gains carrying the same mathematical value.

        :return: Human-facing Library label.
        """
        value_label: str = self._mathematical_value.display_label
        if self._operation == ExactMathematicalBlockOperation.CONSTANT:
            label: str = f"Constant {value_label}"
        else:
            label = value_label
        return label

    @property
    def description(self) -> str:
        """Return a functional explanation of the generated equation.

        :return: Human-facing block description.
        """
        value_label: str = self._mathematical_value.display_label
        if self._operation == ExactMathematicalBlockOperation.CONSTANT:
            description: str = f"Outputs the mathematical constant {value_label}."
        else:
            description = f"Fixed gain {value_label}: yo = {value_label} * yi."
        return description

    @property
    def search_text(self) -> str:
        """Return searchable terms for the Library filter.

        :return: Search text containing the operation, label, and description.
        """
        return f"{self._operation.value} {self.display_label} {self.description}"


def build_exact_mathematical_block_descriptors() -> tuple[ExactMathematicalBlockDescriptor, ...]:
    """Build matching constant-source and fixed-gain descriptors.

    Every named value is deliberately registered on both sides. This keeps the
    Library symmetric and makes the difference between a source and a gain
    visible through both the category and the label.

    :return: Canonical descriptors ordered by operation and mathematical value.
    """
    # Declare the complete fixed-size pair inventory explicitly. Besides
    # avoiding dynamic growth, the side-by-side groups make an omitted pair
    # visible during review.
    descriptors: tuple[ExactMathematicalBlockDescriptor, ...] = (
        ExactMathematicalBlockDescriptor(ExactMathematicalBlockOperation.CONSTANT, ExactMathematicalValue.E),
        ExactMathematicalBlockDescriptor(ExactMathematicalBlockOperation.CONSTANT, ExactMathematicalValue.PI),
        ExactMathematicalBlockDescriptor(
            ExactMathematicalBlockOperation.CONSTANT,
            ExactMathematicalValue.PI_OVER_TWO,
        ),
        ExactMathematicalBlockDescriptor(ExactMathematicalBlockOperation.CONSTANT, ExactMathematicalValue.TWO_PI),
        ExactMathematicalBlockDescriptor(ExactMathematicalBlockOperation.CONSTANT, ExactMathematicalValue.SQRT_TWO),
        ExactMathematicalBlockDescriptor(ExactMathematicalBlockOperation.CONSTANT, ExactMathematicalValue.SQRT_THREE),
        ExactMathematicalBlockDescriptor(
            ExactMathematicalBlockOperation.CONSTANT,
            ExactMathematicalValue.SQRT_TWO_THIRDS,
        ),
        ExactMathematicalBlockDescriptor(
            ExactMathematicalBlockOperation.CONSTANT,
            ExactMathematicalValue.SQRT_THREE_HALVES,
        ),
        ExactMathematicalBlockDescriptor(
            ExactMathematicalBlockOperation.CONSTANT,
            ExactMathematicalValue.INVERSE_SQRT_TWO,
        ),
        ExactMathematicalBlockDescriptor(
            ExactMathematicalBlockOperation.CONSTANT,
            ExactMathematicalValue.INVERSE_SQRT_THREE,
        ),
        ExactMathematicalBlockDescriptor(ExactMathematicalBlockOperation.GAIN, ExactMathematicalValue.E),
        ExactMathematicalBlockDescriptor(ExactMathematicalBlockOperation.GAIN, ExactMathematicalValue.PI),
        ExactMathematicalBlockDescriptor(ExactMathematicalBlockOperation.GAIN, ExactMathematicalValue.PI_OVER_TWO),
        ExactMathematicalBlockDescriptor(ExactMathematicalBlockOperation.GAIN, ExactMathematicalValue.TWO_PI),
        ExactMathematicalBlockDescriptor(ExactMathematicalBlockOperation.GAIN, ExactMathematicalValue.SQRT_TWO),
        ExactMathematicalBlockDescriptor(ExactMathematicalBlockOperation.GAIN, ExactMathematicalValue.SQRT_THREE),
        ExactMathematicalBlockDescriptor(
            ExactMathematicalBlockOperation.GAIN,
            ExactMathematicalValue.SQRT_TWO_THIRDS,
        ),
        ExactMathematicalBlockDescriptor(
            ExactMathematicalBlockOperation.GAIN,
            ExactMathematicalValue.SQRT_THREE_HALVES,
        ),
        ExactMathematicalBlockDescriptor(
            ExactMathematicalBlockOperation.GAIN,
            ExactMathematicalValue.INVERSE_SQRT_TWO,
        ),
        ExactMathematicalBlockDescriptor(
            ExactMathematicalBlockOperation.GAIN,
            ExactMathematicalValue.INVERSE_SQRT_THREE,
        ),
    )

    return descriptors


def build_exact_mathematical_block_template(
        descriptor: ExactMathematicalBlockDescriptor,
        var_factory: VarFactory,
) -> EmtModelTemplate:
    """Materialize one canonical exact source or fixed gain as a normal block.

    The resulting template has no special runtime behavior. It contains the
    same ordinary algebraic variables and equation nodes used by imported Basic
    catalog templates, while avoiding one generated module per scalar value.

    :param descriptor: Typed operation and named value to materialize.
    :param var_factory: Variable factory receiving the block variables.
    :return: EMT template containing the generated symbolic block.
    :raises ValueError: If an unsupported operation is supplied.
    """
    template_name: str = descriptor.display_label
    output_variable: Var = var_factory.add_var("yo_" + template_name)
    constant_value: Const = Const(descriptor.mathematical_value.numerical_value)
    input_variables: list[Var]
    equation: Expr

    # A constant source has no input. A fixed gain has one input and multiplies
    # it by the same scalar represented by the paired source descriptor.
    if descriptor.operation == ExactMathematicalBlockOperation.CONSTANT:
        input_variables = list()
        equation = output_variable - constant_value
    elif descriptor.operation == ExactMathematicalBlockOperation.GAIN:
        input_variable: Var = var_factory.add_var("yi_" + template_name)
        input_variables = list((input_variable,))
        equation = output_variable - constant_value * input_variable
    else:
        raise ValueError(f"Unsupported exact mathematical operation {descriptor.operation!r}")

    block: Block = Block(
        algebraic_vars=list((output_variable,)),
        algebraic_eqs=list((equation,)),
        in_vars=input_variables,
        out_vars=list((output_variable,)),
        name=template_name,
        is_decomposable=False,
    )

    # Wrap the ordinary symbolic block in the same template container used by
    # every draggable imported Basic block.
    template: EmtModelTemplate = EmtModelTemplate(name=template_name)
    template.tpe = DeviceType.NoDevice
    template.comment = descriptor.description
    template.block = block
    return template
