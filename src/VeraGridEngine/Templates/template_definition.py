# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations
from enum import Enum
from typing import Sequence, Any, Union, Type

from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.basic_structures import Vec
from VeraGridEngine.enumerations import (ConverterControlType, WindingType, V_I_CurveSequenceType,
                                         WaveformSequenceType, X_Y_SequenceType, X_Y_Z_Matrix,
                                         IntegratorScalingMode, IntegratorHoldMode,
                                         IntegratorResetMode, IntegratorSaturationMode,
                                         IntegratorBoundSource, TheveninSourceVoltageMode)




TEMPLATEPROP_TYPES = Union[
    Type[int],
    Type[bool],
    Type[float],
    Type[str],
    Type[Sequence[Vec]],
    Type[ConverterControlType],
    Type[WindingType],
    Type[V_I_CurveSequenceType],
    Type[WaveformSequenceType],
    Type[X_Y_SequenceType],
    Type[X_Y_Z_Matrix],
    Type[IntegratorScalingMode],
    Type[IntegratorHoldMode],
    Type[IntegratorResetMode],
    Type[IntegratorSaturationMode],
    Type[IntegratorBoundSource],
    Type[TheveninSourceVoltageMode]

]

class TemplateProp:
    """
    property representing a template input
    """

    __slots__ = (
        "name",
        "units",
        "descr",
        "tpe",
        "display",
        "editable",
        "value",
        "allowed_values",

    )

    def __init__(self,
                 name: str,
                 units: str,
                 descr: str,
                 tpe: TEMPLATEPROP_TYPES,
                 value: Any = None,
                 allowed_values: Sequence[Enum] | None = None) -> None:
        """Describe one editable input of a symbolic template builder.

        When ``allowed_values`` is provided for an enum property, editors must
        offer only that subset instead of every member of the enum class.

        :param name: Property identifier used by the template builder.
        :param units: Units displayed by property editors.
        :param descr: Human-readable explanation of the property.
        :param tpe: Runtime type expected by the template builder.
        :param value: Default property value.
        :param allowed_values: Optional ordered subset of permitted enum members.
        :return: None.
        """
        self.name: str = name
        self.units: str = units
        self.descr: str = descr
        self.tpe: TEMPLATEPROP_TYPES = tpe
        self.display: bool = True
        self.editable: bool = True
        self.value: Any = value
        self.allowed_values: tuple[Enum, ...] | None = (
            None if allowed_values is None else tuple(allowed_values)
        )


class TemplateDefinition:

    __slots__ = (
        'vf',
        'params',
        'params_dict',
    )

    def __init__(self, vf, params):
        """

        :param vf:
        :param params:
        """
        self.vf = vf
        self.params = params
        self.params_dict = {p.name: p for p in params}

    def get_value(self, name: str) -> Any:
        """

        :param name:
        :return:
        """
        prp = self.params_dict.get(name, None)
        if prp is None:
            raise ValueError(f"Unknown parameter: {name}")
        else:
            return prp.value

    def eval(self) -> Any:
        raise NotImplementedError("Not implemented eval")



# class ArbitraryWaveformVoltageSourceEmtTemplate(TemplateDefinition):
#
#     def __init__(self, vf):
#         """
#
#         :param vf: variable factory.
#         """
#         super().__init__(
#             vf,
#             params=[
#                 TemplateProp(name="phN", units="", descr="Whether neutral is active.", tpe=bool),
#                 TemplateProp(name="phA", units="", descr="Whether phase A is active.", tpe=bool),
#                 TemplateProp(name="phB", units="", descr="Whether phase B is active.", tpe=bool),
#                 TemplateProp(name="phC", units="", descr="Whether phase C is active.", tpe=bool),
#                 TemplateProp(name="time_points", units="s", descr="Strictly increasing waveform times.", tpe=Sequence[float]),
#                 TemplateProp(name="value_points", units="", descr="Matching waveform values.", tpe=Sequence[float]),
#                 TemplateProp(name="source_conductance_value", units="Siemens", descr="Norton conductance.", tpe=float),
#                 TemplateProp(name="name", units="", descr="Name of the emt model.", tpe=str),
#             ]
#         )
#
#     def eval(self) -> EmtModelTemplate:
#         """
#         """
#
#         phN: bool = self.get_value("phN")
#         phA: bool = self.get_value("phN")
#         phB: bool = self.get_value("phN")
#         phC: bool = self.get_value("phN")
#         time_points: Sequence[float] = self.get_value("time_points")
#         value_points: Sequence[float] = self.get_value("value_points")
#         source_conductance_value: float = self.get_value("source_conductance_value")
#         name: str = self.get_value("name")
#
#         return get_arbitrary_waveform_voltage_source_emt_template(
#             self.vf, phN, phA, phB, phC, time_points, value_points, source_conductance_value, name
#         )
