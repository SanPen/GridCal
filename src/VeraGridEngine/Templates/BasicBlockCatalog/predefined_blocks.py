# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

from typing import Tuple, Sequence, List

from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Templates.template_definition import TemplateDefinition, TemplateProp
from VeraGridEngine.basic_structures import Vec
from VeraGridEngine.enumerations import BlockType, DeviceType
import VeraGridEngine.Utils.Symbolic.symbolic as sym
from VeraGridEngine.Utils.Symbolic.block import Block



# ----------------------------------------------------------------------------------------------------------------------
# Pre defined blocks
# ----------------------------------------------------------------------------------------------------------------------

def constant(var_factory: VarFactory, item_name: str = "") -> Block:
    """

    :param var_factory:
    :param item_name:
    :return:
    """
    name: str = "const_"
    y = var_factory.add_var(name + item_name)
    param = var_factory.add_var("param_" + item_name)

    blk = Block(
        algebraic_vars=[y],
        algebraic_eqs=[y - param],
        out_vars=[y],
        event_dict={param: var_factory.add_const(0.0)},
        name="const",
        is_decomposable=False
    )

    return blk


def gain(var_factory: VarFactory, item_name: str = "") -> Block:
    """

    :param var_factory:
    :param item_name:
    :return:
    """
    inputs = [var_factory.add_var("inp_num_" + item_name)]
    name: str = "gain"
    y = var_factory.add_var(name + item_name)
    gain_param = var_factory.add_var("gain_param_" + item_name)

    expr: sym.Expr = gain_param * inputs[0]
    blk = Block(
        algebraic_vars=[y],
        algebraic_eqs=[y - expr],
        out_vars=[y],
        in_vars=inputs,
        event_dict={gain_param: var_factory.add_const(0.0)},
        name="gain",
        is_decomposable=False
    )
    return blk


def variable(var_factory: VarFactory, name: str = "variable_", vartype: str = "vartype_") -> Tuple[sym.Var, Block]:
    """

    :param var_factory:
    :param name:
    :param vartype:
    :return:
    """
    y = var_factory.add_var(name)
    if vartype == 'state':
        blk = Block(state_vars=[y])
    else:
        blk = Block(algebraic_vars=[y])
    return y, blk



class AdderTemplate(TemplateDefinition):
    __slots__ = ()

    def __init__(self, vf):
        super().__init__(
            vf,
            params=[
                TemplateProp(name="minuend_inputs", units="", descr="Number of positive (added) inputs.", tpe=int, value=1),
                TemplateProp(name="subtrahend_inputs", units="", descr="Number of negative (subtracted) inputs.", tpe=int, value=1)
            ]
        )

    def eval(self) -> Block:
        minuend_inputs: int = self.get_value("minuend_inputs")
        subtrahend_inputs: int = self.get_value("subtrahend_inputs")

        return adder(self.vf, minuend_inputs, subtrahend_inputs)





def adder(var_factory: VarFactory, minuend_inputs: int = 1, subtrahend_inputs: int = 1, name: str = "sum") -> Block:
    """

    :param var_factory:
    :param item_name:
    :param minuend_inputs:
    :param subtrahend_inputs:
    :return:
    """
    equation: sym.Expr | None = None
    inputs: List[sym.Var] = list()

    for i in range(minuend_inputs):
        if not equation:
            var = var_factory.add_var("add_" + str(i))
            inputs.append(var)
            equation = var

        else:
            var = var_factory.add_var("add_" + str(i))
            inputs.append(var)
            equation += var

    for i in range(subtrahend_inputs):
        if not equation:
            var = var_factory.add_var("subtract_" + str(i))
            inputs.append(var)
            equation = - var
        else:
            var = var_factory.add_var("subtract_" + str(i))
            inputs.append(var)
            equation -= var


    y = var_factory.add_var("sum_out_")


    blk = Block(
        algebraic_vars=[y],
        algebraic_eqs=[y - equation],
        in_vars=inputs,
        out_vars=[y],
        name="sum",
        is_decomposable=False
    )

    return blk

class ProductTemplate(TemplateDefinition):
    __slots__ = ()

    def __init__(self, vf):
        super().__init__(
            vf,
            params=[
                TemplateProp(name="divident_inputs", units="", descr="Number of dividend (multiplied) inputs.", tpe=int, value=1),
                TemplateProp(name="divisor_inputs", units="", descr="Number of divisor (divided) inputs.", tpe=int, value=1)
            ]
        )

    def eval(self) -> Block:
        divident_inputs: int = self.get_value("divident_inputs")
        divisor_inputs: int = self.get_value("divisor_inputs")

        return product(self.vf, divident_inputs, divisor_inputs)


class MinimumTemplate(TemplateDefinition):
    """Structural definition of a minimum block with configurable arity."""

    __slots__ = ()

    def __init__(self, vf: VarFactory) -> None:
        """Create a minimum-block definition with two inputs by default.

        :param vf: Variable factory receiving the generated block variables.
        :return: None.
        """
        TemplateDefinition.__init__(
            self,
            vf,
            list((
                TemplateProp(
                    name="input_count",
                    units="",
                    descr="Number of signals compared by the minimum operation.",
                    tpe=int,
                    value=2,
                ),
            )),
        )

    def eval(self) -> EmtModelTemplate:
        """Build the minimum block using the configured input count.

        :return: EMT template containing a minimum block with the requested input count.
        """
        input_count: int = int(self.get_value("input_count"))
        return build_extremum_template(
            var_factory=self.vf,
            input_count=input_count,
            block_type=BlockType.MIN,
        )


class MaximumTemplate(TemplateDefinition):
    """Structural definition of a maximum block with configurable arity."""

    __slots__ = ()

    def __init__(self, vf: VarFactory) -> None:
        """Create a maximum-block definition with two inputs by default.

        :param vf: Variable factory receiving the generated block variables.
        :return: None.
        """
        TemplateDefinition.__init__(
            self,
            vf,
            list((
                TemplateProp(
                    name="input_count",
                    units="",
                    descr="Number of signals compared by the maximum operation.",
                    tpe=int,
                    value=2,
                ),
            )),
        )

    def eval(self) -> EmtModelTemplate:
        """Build the maximum block using the configured input count.

        :return: EMT template containing a maximum block with the requested input count.
        """
        input_count: int = int(self.get_value("input_count"))
        return build_extremum_template(
            var_factory=self.vf,
            input_count=input_count,
            block_type=BlockType.MAX,
        )


def build_extremum_template(
        var_factory: VarFactory,
        input_count: int,
        block_type: BlockType,
) -> EmtModelTemplate:
    """Wrap a configurable minimum or maximum block in the builder contract.

    Builder-backed Library entries return model templates so creation,
    preflight validation, and structural editing all consume the same type.
    The inner block remains an ordinary symbolic block and retains the
    configurable ``input_count`` structure.

    :param var_factory: Variable factory receiving the generated variables.
    :param input_count: Number of signals participating in the reduction.
    :param block_type: ``BlockType.MIN`` or ``BlockType.MAX``.
    :return: EMT template containing the requested extremum block.
    """
    block: Block = extremum(
        var_factory=var_factory,
        input_count=input_count,
        block_type=block_type,
    )
    template: EmtModelTemplate = EmtModelTemplate(name=block.name)
    template.tpe = DeviceType.NoDevice
    template.block = block
    return template


def extremum(var_factory: VarFactory, input_count: int, block_type: BlockType) -> Block:
    """Build a minimum or maximum reduction over a configurable number of inputs.

    The operation is represented by ordinary binary symbolic function nodes.
    Folding those nodes keeps the model proportional to the number of inputs
    instead of expanding every comparison into repeated Heaviside expressions.

    :param var_factory: Variable factory receiving the generated block variables.
    :param input_count: Number of input signals participating in the reduction.
    :param block_type: ``BlockType.MIN`` or ``BlockType.MAX``.
    :return: Structural minimum or maximum block.
    :raises ValueError: If fewer than two inputs or an unsupported block type is requested.
    """
    if input_count < 2:
        raise ValueError("Minimum and maximum blocks require at least two inputs")
    else:
        pass

    if block_type == BlockType.MIN:
        function_name: str = "min"
        block_name: str = "minimum"
    elif block_type == BlockType.MAX:
        function_name = "max"
        block_name = "maximum"
    else:
        raise ValueError("Extremum blocks support only BlockType.MIN or BlockType.MAX")

    # Create stable positional names so existing connections survive a later
    # increase or decrease of the configured input count.
    inputs: List[sym.Var] = list()
    input_index: int
    for input_index in range(input_count):
        inputs.append(var_factory.add_var("extremum_input_" + str(input_index)))

    # Reduce the inputs through native symbolic min/max nodes. Each additional
    # port contributes exactly one comparison node to the symbolic model.
    expression: sym.Expr = inputs[0]
    input_variable: sym.Var
    for input_variable in inputs[1:]:
        expression = sym.Func2(function_name, expression, input_variable)

    output_variable: sym.Var = var_factory.add_var("extremum_output_")
    block: Block = Block(
        algebraic_vars=list((output_variable,)),
        algebraic_eqs=list((output_variable - expression,)),
        in_vars=inputs,
        out_vars=list((output_variable,)),
        name=block_name,
        is_decomposable=False,
    )
    return block

def product(var_factory: VarFactory, divident_inputs: int = 1, divisor_inputs: int = 1) -> Block:
    """

    :param var_factory:
    :param item_name:
    :param divident_inputs:
    :param divisor_inputs:
    :return:
    """
    equation: sym.Expr | None = None
    inputs: List[sym.Var] = list()

    for i in range(divident_inputs):
        if equation is None:
            var = var_factory.add_var("mul_" + str(i))
            inputs.append(var)
            equation = var

        else:
            var = var_factory.add_var("mul_" + str(i))
            inputs.append(var)
            equation *= var

    for i in range(divisor_inputs):
        if equation is None:
            var = var_factory.add_var("div_" + str(i))
            inputs.append(var)
            equation = 1 / var
        else:
            var = var_factory.add_var("div_" + str(i))
            inputs.append(var)
            equation /= var


    y = var_factory.add_var("prod_out_")


    blk = Block(
        algebraic_vars=[y],
        algebraic_eqs=[y - equation],
        in_vars=inputs,
        out_vars=[y],
        name="product",
        is_decomposable=False
    )

    return blk


def substract(var_factory: VarFactory, item_name: str = "") -> Block:
    """

    :param var_factory:
    :param item_name:
    :return:
    """
    inputs = [var_factory.add_var("minuend_" + item_name), var_factory.add_var("subtrahend_" + item_name)]
    y = var_factory.add_var("difference_" + item_name)

    expr: sym.Expr = inputs[0] - inputs[1]

    blk = Block(
        algebraic_vars=[y],
        algebraic_eqs=[y - expr],
        in_vars=inputs,
        out_vars=[y],
        name="substraction",
        is_decomposable=False
    )

    return blk


def product_2(var_factory: VarFactory, item_name: str = "") -> Block:
    """

    :param var_factory:
    :param item_name:
    :return:
    """
    inputs = [var_factory.add_var("factor1_" + item_name),
              var_factory.add_var("factor2_" + item_name)]  # will not be specified if inputs can be more than 2
    y = var_factory.add_var("product_out_" + item_name)

    expr: sym.Expr = inputs[0] * inputs[1]

    blk = Block(
        algebraic_vars=[y],
        algebraic_eqs=[y - expr],
        in_vars=inputs,
        out_vars=[y],
        name="product",
        is_decomposable=False
    )

    return blk


def divide(var_factory: VarFactory, item_name: str = "") -> Block:
    """

    :param var_factory:
    :param item_name:
    :return:
    """
    inputs = [var_factory.add_var("divident_" + item_name),
              var_factory.add_var("divisor_" + item_name)]  # will not be specified if inputs can be more than 2
    y = var_factory.add_var("quotient_" + item_name)

    expr: sym.Expr = inputs[0] / inputs[1]

    blk = Block(
        algebraic_vars=[y],
        algebraic_eqs=[y - expr],
        in_vars=inputs,
        out_vars=[y],
        name="divide",
        is_decomposable=False
    )

    return blk


def absolut(var_factory: VarFactory, item_name: str = "") -> Block:
    """

    :param var_factory:
    :param item_name:
    :return:
    """
    inputs = [var_factory.add_var("inp_num_" + item_name)]  # will not be specified if inputs can be more than 2
    y = var_factory.add_var("absolut_" + item_name)

    expr: sym.Expr = sym.abs(inputs[0])

    blk = Block(
        algebraic_vars=[y],
        algebraic_eqs=[y - expr],
        in_vars=inputs,
        out_vars=[y],
        name="abs",
        is_decomposable=False
    )

    return blk


def integrator(var_factory: VarFactory, u: sym.Var | sym.Const, name: str = "x") -> Tuple[sym.Var, Block]:
    """

    :param var_factory:
    :param u:
    :param name:
    :return:
    """
    x = var_factory.add_var(name)
    blk = Block(state_vars=[x], state_eqs=[u], is_decomposable=False)
    return x, blk


def pi_controller(var_factory: VarFactory, err: sym.Var, kp: float, ki: float, name: str = "pi") -> Block:
    """

    :param var_factory:
    :param err:
    :param kp:
    :param ki:
    :param name:
    :return:
    """
    up, blk_kp = gain(var_factory=var_factory)
    ie, blk_int = integrator(var_factory=var_factory, u=err)
    ui, blk_ki = gain(var_factory=var_factory)
    u, blk_sum = adder(var_factory=var_factory)
    return Block(name="",
                 children=[blk_kp, blk_int, blk_ki, blk_sum],
                 in_vars=[err],
                 out_vars=[u],
                 is_decomposable=False)


def signal_pair(var_factory: VarFactory, item_name: str = "") -> Tuple[Block, Block]:
    """
    Create a signal pair: one block with an input port and one block with
    an output port that share the same variable. When an external output
    is connected to the input block, the output block exposes the same
    variable automatically.

    :param var_factory:
    :param item_name:
    :return: (input_block, output_block)
    """
    v = var_factory.add_var("signal_" + item_name)

    blk_in = Block(
        in_vars=[v],
        name="From" + item_name
    )

    blk_out = Block(
        # algebraic_vars=[v],
        out_vars=[v],
        name="To" + item_name
    )

    return blk_in, blk_out


def generic(var_factory: VarFactory, 
            inputs: int,
            outputs: int,
            ) -> Block:
    """Build an empty generic block with deterministic interface initialization.

    :param var_factory: Factory that owns every new symbolic identity.
    :param inputs: Number of incoming signal variables to create.
    :param outputs: Number of outgoing signal variables to create.
    :return: Generic block whose outputs start from zero until edited.
    """
    input_variables: list[sym.Var] = list()
    input_index: int
    for input_index in range(inputs):
        input_variables.append(var_factory.add_var(f"input{input_index}"))

    output_variables: list[sym.Var] = list()
    output_index: int
    for output_index in range(outputs):
        output_variables.append(var_factory.add_var(f"output{output_index}"))

    initial_equations: dict[sym.Var, sym.Const] = dict()
    output_variable: sym.Var
    for output_variable in output_variables:
        # Generic outputs are block-owned signals even before the user writes
        # their runtime equations. Give each one a deterministic initialization
        # that remains editable from Block Properties.
        initial_equations[output_variable] = sym.Const(0.0)

    blk: Block = Block(
        name="generic",
        in_vars=input_variables,
        out_vars=output_variables,
        init_eqs=initial_equations,
    )
    return blk

